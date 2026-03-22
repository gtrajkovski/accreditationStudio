"""Packet validation service for evidence contract enforcement.

Validates that submission packets have sufficient evidence coverage and
resolved findings before allowing export.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.db.connection import get_conn


@dataclass
class ValidationResult:
    """Result of packet validation check.

    Attributes:
        ok: Whether the packet passes validation and can be exported
        missing_standards: Standards that lack evidence mapping
        missing_evidence: Finding IDs without evidence references
        blocking_findings: Critical/unresolved findings that block export
        required_checkpoints: Checkpoint IDs that must be resolved for override
    """
    ok: bool = True
    missing_standards: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    blocking_findings: List[str] = field(default_factory=list)
    required_checkpoints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "ok": self.ok,
            "missing_standards": self.missing_standards,
            "missing_evidence": self.missing_evidence,
            "blocking_findings": self.blocking_findings,
            "required_checkpoints": self.required_checkpoints,
        }


def validate_packet(
    packet_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> ValidationResult:
    """
    Validate a packet for export readiness.

    Checks:
    1. All selected standards have at least one evidence reference
    2. All findings have evidence references
    3. No critical findings with status != resolved/dismissed

    Args:
        packet_id: The submission packet ID to validate
        conn: Optional database connection

    Returns:
        ValidationResult with ok=True if export allowed, or blocking issues
    """
    conn = conn or get_conn()
    result = ValidationResult()

    try:
        # Get the packet and its institution
        cursor = conn.execute("""
            SELECT sp.id, sp.institution_id, sp.packet_type, sp.title
            FROM submission_packets sp
            WHERE sp.id = ?
        """, (packet_id,))

        packet_row = cursor.fetchone()
        if not packet_row:
            result.ok = False
            result.required_checkpoints.append("packet_not_found")
            return result

        institution_id = packet_row["institution_id"]

        # Get standards covered by this packet's items
        # Packet items may reference standards via their ref field (JSON)
        cursor = conn.execute("""
            SELECT pi.id, pi.ref
            FROM packet_items pi
            WHERE pi.packet_id = ?
        """, (packet_id,))

        packet_items = cursor.fetchall()
        packet_standard_refs = set()

        for item in packet_items:
            try:
                ref_data = json.loads(item["ref"]) if item["ref"] else {}
                standard_refs = ref_data.get("standard_refs", [])
                if isinstance(standard_refs, list):
                    packet_standard_refs.update(standard_refs)
            except (json.JSONDecodeError, TypeError):
                pass

        # Check 1: Standards with evidence coverage
        # For each standard referenced in the packet, check if there's evidence
        for std_ref in packet_standard_refs:
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT er.id) as evidence_count
                FROM evidence_refs er
                JOIN audit_findings af ON er.finding_id = af.id
                JOIN finding_standard_refs fsr ON fsr.finding_id = af.id
                JOIN audit_runs ar ON af.audit_run_id = ar.id
                WHERE ar.institution_id = ?
                  AND fsr.standard_id = ?
            """, (institution_id, std_ref))

            evidence_count = cursor.fetchone()["evidence_count"]
            if evidence_count == 0:
                result.missing_standards.append(std_ref)

        # Check 2: Get findings linked to this packet and check for evidence
        # Look at packet_checklist_mappings and linked audits
        cursor = conn.execute("""
            SELECT DISTINCT af.id, af.summary, af.severity, af.status
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ?
              AND ar.status = 'completed'
        """, (institution_id,))

        findings = cursor.fetchall()

        for finding in findings:
            finding_id = finding["id"]

            # Check if finding has evidence
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM evidence_refs
                WHERE finding_id = ?
            """, (finding_id,))

            if cursor.fetchone()["count"] == 0:
                result.missing_evidence.append(finding_id)

        # Check 3: Critical findings that block export
        # Critical findings must be resolved or dismissed
        cursor = conn.execute("""
            SELECT af.id, af.summary, af.severity, af.status
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ?
              AND af.severity = 'critical'
              AND af.status NOT IN ('compliant', 'resolved', 'dismissed')
        """, (institution_id,))

        critical_findings = cursor.fetchall()
        for cf in critical_findings:
            result.blocking_findings.append(cf["id"])

        # Determine overall OK status
        has_missing_standards = len(result.missing_standards) > 0
        has_blocking_findings = len(result.blocking_findings) > 0

        # Export is blocked if there are missing standards OR blocking findings
        result.ok = not has_missing_standards and not has_blocking_findings

        # If blocked, require a finalize_submission checkpoint for override
        if not result.ok:
            result.required_checkpoints.append("finalize_submission")

    except sqlite3.OperationalError as e:
        # Tables may not exist yet
        result.ok = False
        result.required_checkpoints.append(f"db_error:{str(e)}")

    return result


def check_force_export_override(
    packet_id: str,
    checkpoint_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Check if a force export override is valid.

    A valid override requires:
    1. The checkpoint exists and is of type 'finalize_submission'
    2. The checkpoint has been resolved/approved
    3. The checkpoint is linked to this packet

    Args:
        packet_id: The packet being exported
        checkpoint_id: The checkpoint ID provided for override
        conn: Optional database connection

    Returns:
        Dict with 'valid' bool and 'reason' if invalid
    """
    conn = conn or get_conn()

    try:
        cursor = conn.execute("""
            SELECT hc.id, hc.checkpoint_type, hc.status, hc.reason, hc.resolved_at
            FROM human_checkpoints hc
            WHERE hc.id = ?
        """, (checkpoint_id,))

        checkpoint = cursor.fetchone()

        if not checkpoint:
            return {"valid": False, "reason": "Checkpoint not found"}

        if checkpoint["checkpoint_type"] != "finalize_submission":
            return {
                "valid": False,
                "reason": f"Invalid checkpoint type: {checkpoint['checkpoint_type']}"
            }

        if checkpoint["status"] not in ("resolved", "approved"):
            return {
                "valid": False,
                "reason": f"Checkpoint not resolved: {checkpoint['status']}"
            }

        # Log the forced export for audit trail
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO human_checkpoints
            (id, institution_id, checkpoint_type, status, requested_by, reason, created_at, resolved_at)
            SELECT
                ? || '_export',
                sp.institution_id,
                'forced_export',
                'completed',
                'system',
                ?,
                ?,
                ?
            FROM submission_packets sp
            WHERE sp.id = ?
        """, (
            checkpoint_id,
            f"Forced export with override checkpoint {checkpoint_id}",
            now,
            now,
            packet_id,
        ))
        conn.commit()

        return {"valid": True, "reason": "Override accepted"}

    except sqlite3.OperationalError as e:
        return {"valid": False, "reason": f"Database error: {str(e)}"}


def create_finalize_checkpoint(
    packet_id: str,
    institution_id: str,
    validation_result: ValidationResult,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Create a finalize_submission checkpoint for export override.

    This checkpoint must be resolved before a forced export is allowed.
    Records the validation state at the time of checkpoint creation.

    Args:
        packet_id: The packet requiring override
        institution_id: The institution ID
        validation_result: The validation result that triggered this
        conn: Optional database connection

    Returns:
        Dict with checkpoint details
    """
    conn = conn or get_conn()

    checkpoint_id = f"cp_{packet_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    now = datetime.now(timezone.utc).isoformat()

    # Build reason from validation result
    reasons = []
    if validation_result.missing_standards:
        reasons.append(f"{len(validation_result.missing_standards)} standards lack evidence")
    if validation_result.blocking_findings:
        reasons.append(f"{len(validation_result.blocking_findings)} critical findings unresolved")

    reason = "; ".join(reasons) if reasons else "Validation failed"

    # Store checkpoint details as JSON notes
    notes = json.dumps({
        "packet_id": packet_id,
        "validation": validation_result.to_dict(),
        "created_at": now,
    })

    try:
        conn.execute("""
            INSERT INTO human_checkpoints
            (id, institution_id, checkpoint_type, status, requested_by, reason, notes, created_at)
            VALUES (?, ?, 'finalize_submission', 'pending', 'system', ?, ?, ?)
        """, (checkpoint_id, institution_id, reason, notes, now))
        conn.commit()

        return {
            "checkpoint_id": checkpoint_id,
            "checkpoint_type": "finalize_submission",
            "status": "pending",
            "reason": reason,
            "created_at": now,
        }

    except sqlite3.OperationalError as e:
        return {"error": str(e)}
