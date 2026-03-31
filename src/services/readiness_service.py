"""Readiness Score Computation Service.

Computes a single Readiness Score (0-100) for an institution with sub-scores:
- Documents (0-100): Completeness of required documents
- Compliance (0-100): Audit findings status
- Evidence Coverage (0-100): Standards with supporting evidence
- Consistency (0-100): Cross-document consistency

Provides explanation breakdowns, blockers, and next best actions.
"""

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from src.db.connection import get_conn


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Blocker:
    """A blocking issue that reduces readiness."""
    type: str  # 'missing_doc', 'critical_finding', 'consistency', 'evidence'
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    action: str
    link: Optional[str] = None
    doc_type: Optional[str] = None
    finding_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class NextAction:
    """A recommended next action to improve readiness."""
    title: str
    reason: str
    action_type: str  # 'upload', 'index', 'fix', 'audit', 'consistency', 'packet'
    priority: int  # 1 = highest
    payload: Optional[Dict[str, Any]] = None
    link: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ReadinessScore:
    """Complete readiness assessment for an institution."""
    total: int
    documents: int
    compliance: int
    evidence: int
    consistency: int
    blockers: List[Blocker] = field(default_factory=list)
    breakdown: Dict[str, Any] = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "documents": self.documents,
            "compliance": self.compliance,
            "evidence": self.evidence,
            "consistency": self.consistency,
            "blockers": [b.to_dict() for b in self.blockers],
            "breakdown": self.breakdown,
            "computed_at": self.computed_at,
        }


# =============================================================================
# Score Weights
# =============================================================================

SCORE_WEIGHTS = {
    "compliance": 0.40,
    "evidence": 0.25,
    "documents": 0.20,
    "consistency": 0.15,
}

# Cache window in minutes
CACHE_WINDOW_MINUTES = 10

# Minimum score to recommend packet generation
PACKET_THRESHOLD = 80


# =============================================================================
# Document Score Computation
# =============================================================================

def _compute_documents_score(
    conn: sqlite3.Connection,
    institution_id: str,
    accreditor_code: str
) -> Tuple[int, Dict[str, Any], List[Blocker]]:
    """Compute documents sub-score (0-100).

    Start at 100.
    For each required doc type missing: -15 (or custom weight)
    For each required doc type uploaded but not indexed: -8
    """
    score = 100
    blockers = []

    # Get required doc types for this accreditor
    cursor = conn.execute("""
        SELECT doc_type, doc_type_label, weight
        FROM institution_required_doc_types
        WHERE accreditor_code = ? AND required = 1
    """, (accreditor_code,))
    required_types = {row["doc_type"]: {
        "label": row["doc_type_label"],
        "weight": row["weight"]
    } for row in cursor.fetchall()}

    if not required_types:
        # Fallback defaults if no seed data
        required_types = {
            "catalog": {"label": "Catalog", "weight": 15},
            "enrollment_agreement": {"label": "Enrollment Agreement", "weight": 15},
            "refund_policy": {"label": "Refund Policy", "weight": 15},
        }

    # Get documents for this institution
    cursor = conn.execute("""
        SELECT doc_type, status, COUNT(*) as count
        FROM documents
        WHERE institution_id = ?
        GROUP BY doc_type, status
    """, (institution_id,))

    doc_inventory = {}
    for row in cursor.fetchall():
        doc_type = row["doc_type"]
        status = row["status"]
        if doc_type not in doc_inventory:
            doc_inventory[doc_type] = {"uploaded": 0, "indexed": 0, "parsed": 0}
        doc_inventory[doc_type][status] = row["count"]
        doc_inventory[doc_type]["uploaded"] += row["count"]

    # Calculate penalties
    missing_required = []
    unindexed = []

    for doc_type, info in required_types.items():
        inv = doc_inventory.get(doc_type, {})

        if inv.get("uploaded", 0) == 0:
            # Missing entirely
            penalty = info["weight"]
            score -= penalty
            missing_required.append({
                "doc_type": doc_type,
                "label": info["label"],
                "penalty": penalty
            })
            blockers.append(Blocker(
                type="missing_doc",
                severity="critical" if penalty >= 15 else "high",
                message=f"Missing required document: {info['label']}",
                action=f"Upload {info['label']}",
                link=f"/institutions/{institution_id}/documents?upload={doc_type}",
                doc_type=doc_type
            ))
        elif inv.get("indexed", 0) == 0:
            # Uploaded but not indexed
            penalty = 8
            score -= penalty
            unindexed.append({
                "doc_type": doc_type,
                "label": info["label"],
                "penalty": penalty
            })

    breakdown = {
        "required_types": list(required_types.keys()),
        "missing_required": missing_required,
        "unindexed": unindexed,
        "inventory": doc_inventory,
        "total_required": len(required_types),
        "total_present": len(required_types) - len(missing_required),
    }

    return max(0, min(100, score)), breakdown, blockers


# =============================================================================
# Compliance Score Computation
# =============================================================================

def _compute_compliance_score(
    conn: sqlite3.Connection,
    institution_id: str
) -> Tuple[int, Dict[str, Any], List[Blocker]]:
    """Compute compliance sub-score (0-100).

    Penalties from unresolved findings:
    - critical non_compliant: -12
    - significant non_compliant: -7
    - advisory non_compliant: -3
    - partial: half of above
    - needs_info: treat as significant until resolved
    """
    score = 100
    blockers = []

    # Get latest audit run
    cursor = conn.execute("""
        SELECT id, status, completed_at
        FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    latest_audit = cursor.fetchone()

    if not latest_audit:
        # No audits run yet - cannot assess compliance
        return 0, {
            "audit_completed_at": None,
            "critical_open": 0,
            "moderate_open": 0,
            "advisory_open": 0,
            "by_severity": {},
            "message": "No audits completed yet"
        }, [Blocker(
            type="no_audit",
            severity="high",
            message="No compliance audit has been run",
            action="Run initial compliance audit",
            link=f"/institutions/{institution_id}/compliance?action=audit"
        )]

    audit_id = latest_audit["id"]

    # Get unresolved findings
    cursor = conn.execute("""
        SELECT
            severity,
            status,
            COUNT(*) as count
        FROM audit_findings
        WHERE audit_run_id = ?
          AND status NOT IN ('compliant', 'resolved', 'dismissed')
        GROUP BY severity, status
    """, (audit_id,))

    # Penalty matrix
    penalties = {
        "critical": {"non_compliant": 12, "partial": 6, "needs_info": 7},
        "significant": {"non_compliant": 7, "partial": 4, "needs_info": 7},
        "moderate": {"non_compliant": 5, "partial": 3, "needs_info": 5},
        "advisory": {"non_compliant": 3, "partial": 2, "needs_info": 3},
    }

    by_severity = {"critical": 0, "significant": 0, "moderate": 0, "advisory": 0}
    critical_open = 0

    for row in cursor.fetchall():
        severity = row["severity"] or "moderate"
        status = row["status"] or "non_compliant"
        count = row["count"]

        penalty_map = penalties.get(severity, penalties["moderate"])
        penalty = penalty_map.get(status, 5) * count
        score -= penalty

        by_severity[severity] = by_severity.get(severity, 0) + count

        if severity == "critical" and status in ("non_compliant", "needs_info"):
            critical_open += count

    # Get critical findings for blockers
    if critical_open > 0:
        cursor = conn.execute("""
            SELECT id, summary
            FROM audit_findings
            WHERE audit_run_id = ?
              AND severity = 'critical'
              AND status IN ('non_compliant', 'needs_info')
            LIMIT 5
        """, (audit_id,))

        for row in cursor.fetchall():
            blockers.append(Blocker(
                type="critical_finding",
                severity="critical",
                message=f"Critical finding: {row['summary'][:60]}",
                action="Fix this finding",
                link=f"/institutions/{institution_id}/compliance?finding={row['id']}",
                finding_id=row["id"]
            ))

    # Factor in overdue tasks (Phase 44)
    overdue_tasks = 0
    task_penalty = 0
    try:
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM tasks
            WHERE institution_id = ?
              AND due_date < datetime('now')
              AND status != 'completed'
        """, (institution_id,))
        row = cursor.fetchone()
        if row:
            overdue_tasks = row["count"]
            # Penalty: 2 points per overdue task (cap at 20 points)
            task_penalty = min(overdue_tasks * 2, 20)
            score -= task_penalty

            if overdue_tasks > 5:
                blockers.append(Blocker(
                    type="overdue_tasks",
                    severity="high",
                    message=f"{overdue_tasks} overdue tasks blocking compliance",
                    action="Complete or reassign overdue tasks",
                    link="/tasks?filter=overdue"
                ))
    except Exception:
        # Tasks table may not exist yet (Phase 44 not deployed)
        pass

    breakdown = {
        "audit_id": audit_id,
        "audit_completed_at": latest_audit["completed_at"],
        "audit_status": latest_audit["status"],
        "critical_open": critical_open,
        "moderate_open": by_severity.get("significant", 0) + by_severity.get("moderate", 0),
        "advisory_open": by_severity.get("advisory", 0),
        "by_severity": by_severity,
        "overdue_tasks": overdue_tasks,
        "task_penalty": task_penalty,
    }

    return max(0, min(100, score)), breakdown, blockers


# =============================================================================
# Evidence Score Computation
# =============================================================================

def _compute_evidence_score(
    conn: sqlite3.Connection,
    institution_id: str
) -> Tuple[int, Dict[str, Any], List[Blocker]]:
    """Compute evidence coverage sub-score (0-100).

    Penalties:
    - Finding without evidence_refs: -8 (critical), -5 (significant), -2 (advisory)
    - Weak evidence (low confidence or human_review_required): -2 each
    """
    score = 100
    blockers = []

    # Get latest audit
    cursor = conn.execute("""
        SELECT id FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    latest = cursor.fetchone()

    if not latest:
        return 0, {
            "uncovered_standards": 0,
            "weak_evidence_findings": 0,
            "message": "No audits completed yet"
        }, []

    audit_id = latest["id"]

    # Count findings lacking evidence
    cursor = conn.execute("""
        SELECT f.id, f.severity, f.summary,
               (SELECT COUNT(*) FROM evidence_refs e WHERE e.finding_id = f.id) as evidence_count
        FROM audit_findings f
        WHERE f.audit_run_id = ?
          AND f.status NOT IN ('compliant', 'dismissed')
    """, (audit_id,))

    penalties = {"critical": 8, "significant": 5, "moderate": 4, "advisory": 2}
    uncovered = 0
    weak_evidence = 0

    for row in cursor.fetchall():
        if row["evidence_count"] == 0:
            severity = row["severity"] or "moderate"
            penalty = penalties.get(severity, 4)
            score -= penalty
            uncovered += 1

            if severity in ("critical", "significant"):
                blockers.append(Blocker(
                    type="evidence",
                    severity="high" if severity == "critical" else "medium",
                    message=f"Finding lacks evidence: {row['summary'][:50]}",
                    action="Map evidence to this finding",
                    finding_id=row["id"]
                ))

    # Check for findings requiring human review (low confidence)
    cursor = conn.execute("""
        SELECT COUNT(*) as count
        FROM audit_findings
        WHERE audit_run_id = ?
          AND (confidence < 0.70 OR human_review_required = 1)
          AND status NOT IN ('compliant', 'dismissed')
    """, (audit_id,))

    weak_row = cursor.fetchone()
    if weak_row:
        weak_evidence = weak_row["count"]
        score -= weak_evidence * 2

    breakdown = {
        "audit_id": audit_id,
        "uncovered_standards": uncovered,
        "low_confidence_findings": weak_evidence,
        "total_findings_checked": uncovered + weak_evidence,
    }

    return max(0, min(100, score)), breakdown, blockers


# =============================================================================
# Consistency Score Computation
# =============================================================================

def _compute_consistency_score(
    conn: sqlite3.Connection,
    institution_id: str
) -> Tuple[int, Dict[str, Any], List[Blocker]]:
    """Compute consistency sub-score (0-100).

    Penalties:
    - high severity mismatch: -10
    - medium: -6
    - low: -2
    """
    score = 100
    blockers = []

    # Get consistency issues
    cursor = conn.execute("""
        SELECT severity, COUNT(*) as count
        FROM readiness_consistency_issues
        WHERE institution_id = ?
          AND status != 'resolved'
        GROUP BY severity
    """, (institution_id,))

    penalties = {"high": 10, "medium": 6, "low": 2}
    by_severity = {"high": 0, "medium": 0, "low": 0}

    for row in cursor.fetchall():
        severity = row["severity"] or "medium"
        count = row["count"]
        penalty = penalties.get(severity, 6) * count
        score -= penalty
        by_severity[severity] = count

    # Get high severity issues for blockers
    if by_severity["high"] > 0:
        cursor = conn.execute("""
            SELECT id, truth_key, message
            FROM readiness_consistency_issues
            WHERE institution_id = ?
              AND severity = 'high'
              AND status != 'resolved'
            LIMIT 3
        """, (institution_id,))

        for row in cursor.fetchall():
            blockers.append(Blocker(
                type="consistency",
                severity="high",
                message=f"Consistency issue: {row['message'][:50]}",
                action="Resolve mismatch in Truth Index",
                link=f"/institutions/{institution_id}/consistency?issue={row['id']}"
            ))

    # Get latest consistency check timestamp
    cursor = conn.execute("""
        SELECT MAX(created_at) as last_check
        FROM readiness_consistency_issues
        WHERE institution_id = ?
    """, (institution_id,))
    last_check = cursor.fetchone()

    breakdown = {
        "total_mismatches": sum(by_severity.values()),
        "high_severity_mismatches": by_severity["high"],
        "medium_severity_mismatches": by_severity["medium"],
        "low_severity_mismatches": by_severity["low"],
        "last_check": last_check["last_check"] if last_check else None,
    }

    return max(0, min(100, score)), breakdown, blockers


# =============================================================================
# Main Computation
# =============================================================================

def compute_readiness(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    conn: Optional[sqlite3.Connection] = None
) -> ReadinessScore:
    """Compute complete readiness score for an institution.

    Args:
        institution_id: Institution ID
        accreditor_code: Accreditor code (ACCSC, COE, etc.)
        conn: Optional database connection

    Returns:
        ReadinessScore with all sub-scores and breakdown
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Compute each sub-score
        doc_score, doc_breakdown, doc_blockers = _compute_documents_score(
            conn, institution_id, accreditor_code
        )

        comp_score, comp_breakdown, comp_blockers = _compute_compliance_score(
            conn, institution_id
        )

        evid_score, evid_breakdown, evid_blockers = _compute_evidence_score(
            conn, institution_id
        )

        cons_score, cons_breakdown, cons_blockers = _compute_consistency_score(
            conn, institution_id
        )

        # Weighted total
        total = int(
            doc_score * SCORE_WEIGHTS["documents"] +
            comp_score * SCORE_WEIGHTS["compliance"] +
            evid_score * SCORE_WEIGHTS["evidence"] +
            cons_score * SCORE_WEIGHTS["consistency"]
        )

        # CRITICAL FINDINGS CAP: If any critical findings exist, cap at 40%
        # This prevents misleading high scores when serious issues remain
        critical_open = comp_breakdown.get("critical_open", 0)
        has_critical_cap = False
        if critical_open > 0 and total > 40:
            total = 40
            has_critical_cap = True

        # Combine and sort blockers by severity
        all_blockers = doc_blockers + comp_blockers + evid_blockers + cons_blockers
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_blockers.sort(key=lambda b: severity_order.get(b.severity, 2))

        # Limit to top 8 blockers
        top_blockers = all_blockers[:8]

        breakdown = {
            "documents": doc_breakdown,
            "compliance": comp_breakdown,
            "evidence": evid_breakdown,
            "consistency": cons_breakdown,
            "weights": SCORE_WEIGHTS,
            "critical_cap_applied": has_critical_cap,
        }

        return ReadinessScore(
            total=total,
            documents=doc_score,
            compliance=comp_score,
            evidence=evid_score,
            consistency=cons_score,
            blockers=top_blockers,
            breakdown=breakdown,
        )

    finally:
        if should_close:
            conn.close()


# =============================================================================
# Next Best Actions
# =============================================================================

def get_next_actions(
    institution_id: str,
    readiness: Optional[ReadinessScore] = None,
    accreditor_code: str = "ACCSC",
    limit: int = 5
) -> List[NextAction]:
    """Generate prioritized next best actions.

    Priority order:
    1) Upload missing required docs
    2) Run indexing/parsing for unindexed docs
    3) Fix critical findings (generate remediation)
    4) Resolve high severity mismatches
    5) Re-run audit after fixes
    6) Generate packet only when total >= threshold
    """
    if readiness is None:
        readiness = compute_readiness(institution_id, accreditor_code)

    actions = []
    priority = 1

    # 1) Missing documents
    doc_breakdown = readiness.breakdown.get("documents", {})
    for missing in doc_breakdown.get("missing_required", [])[:2]:
        actions.append(NextAction(
            title=f"Upload {missing['label']}",
            reason=f"Required document missing (-{missing['penalty']} points)",
            action_type="upload",
            priority=priority,
            payload={"doc_type": missing["doc_type"]},
            link=f"/institutions/{institution_id}/documents?upload={missing['doc_type']}"
        ))
        priority += 1

    # 2) Unindexed documents
    for unindexed in doc_breakdown.get("unindexed", [])[:2]:
        actions.append(NextAction(
            title=f"Index {unindexed['label']}",
            reason="Document uploaded but not searchable",
            action_type="index",
            priority=priority,
            payload={"doc_type": unindexed["doc_type"]},
            link=f"/institutions/{institution_id}/documents"
        ))
        priority += 1

    # 3) Critical findings
    comp_breakdown = readiness.breakdown.get("compliance", {})
    if comp_breakdown.get("critical_open", 0) > 0:
        actions.append(NextAction(
            title=f"Fix {comp_breakdown['critical_open']} critical finding(s)",
            reason="Critical findings block accreditation",
            action_type="fix",
            priority=priority,
            link=f"/institutions/{institution_id}/remediation?severity=critical"
        ))
        priority += 1

    # 4) High severity consistency issues
    cons_breakdown = readiness.breakdown.get("consistency", {})
    if cons_breakdown.get("high_severity_mismatches", 0) > 0:
        actions.append(NextAction(
            title="Resolve consistency mismatches",
            reason=f"{cons_breakdown['high_severity_mismatches']} high-severity inconsistencies",
            action_type="consistency",
            priority=priority,
            link=f"/institutions/{institution_id}/consistency"
        ))
        priority += 1

    # 5) Run audit if none exists
    if comp_breakdown.get("audit_completed_at") is None:
        actions.append(NextAction(
            title="Run compliance audit",
            reason="No audit has been completed yet",
            action_type="audit",
            priority=priority,
            link=f"/institutions/{institution_id}/compliance?action=audit"
        ))
        priority += 1

    # 6) Generate packet if ready
    if readiness.total >= PACKET_THRESHOLD and len(actions) == 0:
        actions.append(NextAction(
            title="Generate submission packet",
            reason=f"Readiness score ({readiness.total}%) meets threshold",
            action_type="packet",
            priority=priority,
            link=f"/institutions/{institution_id}/packets/new"
        ))

    return actions[:limit]


def get_blockers(
    institution_id: str,
    readiness: Optional[ReadinessScore] = None,
    accreditor_code: str = "ACCSC"
) -> List[Dict[str, Any]]:
    """Get blockers list for alerts panel."""
    if readiness is None:
        readiness = compute_readiness(institution_id, accreditor_code)

    return [b.to_dict() for b in readiness.blockers]


# =============================================================================
# Persistence
# =============================================================================

def persist_snapshot(
    institution_id: str,
    readiness: ReadinessScore,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Persist a readiness snapshot for history tracking.

    Returns:
        Snapshot ID
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        snapshot_id = f"snap_{uuid4().hex[:12]}"

        conn.execute("""
            INSERT INTO institution_readiness_snapshots (
                id, institution_id, score_total, score_documents,
                score_compliance, score_evidence, score_consistency,
                blockers_json, breakdown_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            institution_id,
            readiness.total,
            readiness.documents,
            readiness.compliance,
            readiness.evidence,
            readiness.consistency,
            json.dumps([b.to_dict() for b in readiness.blockers]),
            json.dumps(readiness.breakdown),
            readiness.computed_at,
        ))

        # Update institution cache marker
        conn.execute("""
            UPDATE institutions
            SET readiness_stale = 0, readiness_computed_at = ?
            WHERE id = ?
        """, (readiness.computed_at, institution_id))

        conn.commit()
        return snapshot_id

    finally:
        if should_close:
            conn.close()


def get_latest_snapshot(
    institution_id: str,
    max_age_minutes: int = CACHE_WINDOW_MINUTES,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Get latest snapshot if within cache window.

    Returns:
        Snapshot dict or None if stale/missing
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()

        cursor = conn.execute("""
            SELECT * FROM institution_readiness_snapshots
            WHERE institution_id = ?
              AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (institution_id, cutoff))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "institution_id": row["institution_id"],
            "total": row["score_total"],
            "documents": row["score_documents"],
            "compliance": row["score_compliance"],
            "evidence": row["score_evidence"],
            "consistency": row["score_consistency"],
            "blockers": json.loads(row["blockers_json"]),
            "breakdown": json.loads(row["breakdown_json"]),
            "computed_at": row["created_at"],
        }

    finally:
        if should_close:
            conn.close()


def get_readiness_history(
    institution_id: str,
    days: int = 90,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Get readiness score history for trend chart.

    Returns:
        List of snapshot summaries
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = conn.execute("""
            SELECT
                id,
                score_total as total,
                score_documents as documents,
                score_compliance as compliance,
                score_evidence as evidence,
                score_consistency as consistency,
                created_at
            FROM institution_readiness_snapshots
            WHERE institution_id = ?
              AND created_at > ?
            ORDER BY created_at ASC
        """, (institution_id, cutoff))

        return [dict(row) for row in cursor.fetchall()]

    finally:
        if should_close:
            conn.close()


def ensure_daily_snapshot(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    conn: Optional[sqlite3.Connection] = None
) -> Optional[str]:
    """Ensure at least one snapshot exists for today.

    This function creates a new snapshot only if no snapshot exists for
    the current UTC date. Use this to maintain regular historical data
    without creating excessive snapshots.

    Args:
        institution_id: Institution ID
        accreditor_code: Accreditor code (ACCSC, COE, etc.)
        conn: Optional database connection

    Returns:
        Snapshot ID if new snapshot created, None if one already exists
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Check if snapshot exists for today
        today = datetime.now(timezone.utc).date().isoformat()

        cursor = conn.execute("""
            SELECT id FROM institution_readiness_snapshots
            WHERE institution_id = ?
              AND DATE(created_at) = ?
            LIMIT 1
        """, (institution_id, today))

        if cursor.fetchone():
            return None  # Already have today's snapshot

        # Compute and persist new snapshot
        readiness = compute_readiness(institution_id, accreditor_code, conn)
        return persist_snapshot(institution_id, readiness, conn)

    finally:
        if should_close:
            conn.close()


# =============================================================================
# Cache Management
# =============================================================================

def mark_readiness_stale(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> None:
    """Mark institution readiness as stale (needs recomputation)."""
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        conn.execute("""
            UPDATE institutions
            SET readiness_stale = 1
            WHERE id = ?
        """, (institution_id,))
        conn.commit()
    finally:
        if should_close:
            conn.close()


def get_or_compute_readiness(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    force_recompute: bool = False
) -> Dict[str, Any]:
    """Get cached readiness or compute fresh.

    This is the main entry point for the API.
    """
    if not force_recompute:
        cached = get_latest_snapshot(institution_id)
        if cached:
            return cached

    # Compute fresh
    readiness = compute_readiness(institution_id, accreditor_code)

    # Persist snapshot
    persist_snapshot(institution_id, readiness)

    # Record trend snapshot for executive dashboard (Phase 45)
    record_readiness_snapshot(
        institution_id,
        readiness.total,
        sub_scores={
            "documents_score": readiness.documents,
            "compliance_score": readiness.compliance,
            "evidence_score": readiness.evidence,
            "consistency_score": readiness.consistency,
        }
    )

    return readiness.to_dict()


# =============================================================================
# Phase 45: Executive Dashboard - Readiness Trend Tracking
# =============================================================================

def record_readiness_snapshot(
    institution_id: str,
    score: float,
    sub_scores: Optional[Dict[str, float]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Record a readiness snapshot for trend tracking.

    This function stores timestamped readiness scores in the readiness_snapshots
    table (Phase 45) for historical trending and executive dashboard visualization.

    Args:
        institution_id: Institution ID
        score: Total readiness score (0-100)
        sub_scores: Optional dict with keys: documents_score, compliance_score,
                    evidence_score, consistency_score
        conn: Optional database connection

    Returns:
        Snapshot ID
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        snapshot_id = f"snap_{uuid4().hex[:12]}"

        # Extract sub-scores if provided
        documents_score = sub_scores.get("documents_score") if sub_scores else None
        compliance_score = sub_scores.get("compliance_score") if sub_scores else None
        evidence_score = sub_scores.get("evidence_score") if sub_scores else None
        consistency_score = sub_scores.get("consistency_score") if sub_scores else None

        conn.execute("""
            INSERT INTO readiness_snapshots (
                id, institution_id, score, documents_score,
                compliance_score, evidence_score, consistency_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            institution_id,
            score,
            documents_score,
            compliance_score,
            evidence_score,
            consistency_score
        ))

        conn.commit()
        return snapshot_id

    finally:
        if should_close:
            conn.close()


def get_readiness_trend(
    institution_id: str,
    days: int = 90,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Get readiness trend data for the specified time period.

    Returns chronological list of readiness snapshots for trend visualization
    in the executive dashboard.

    Args:
        institution_id: Institution ID
        days: Number of days to look back (default 90)
        conn: Optional database connection

    Returns:
        List of dicts with keys: date, score, documents_score, compliance_score,
        evidence_score, consistency_score
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = conn.execute("""
            SELECT
                DATE(recorded_at) as date,
                score,
                documents_score,
                compliance_score,
                evidence_score,
                consistency_score,
                recorded_at
            FROM readiness_snapshots
            WHERE institution_id = ?
              AND recorded_at >= ?
            ORDER BY recorded_at ASC
        """, (institution_id, cutoff))

        return [dict(row) for row in cursor.fetchall()]

    finally:
        if should_close:
            conn.close()
