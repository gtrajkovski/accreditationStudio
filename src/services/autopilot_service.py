"""Autopilot Service - Scheduled nightly jobs for document maintenance.

Runs:
1. Document re-indexing (parse and embed new/changed docs)
2. Consistency checks (detect cross-document mismatches)
3. Compliance audits (optional, slower)
4. Readiness score computation
"""

import hashlib
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4

from src.config import Config
from src.db.connection import get_conn

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of autopilot tasks."""
    REINDEX = "reindex"
    CONSISTENCY = "consistency"
    AUDIT = "audit"
    READINESS = "readiness"


class RunStatus(str, Enum):
    """Status of an autopilot run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    """How the run was triggered."""
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    STARTUP = "startup"


@dataclass
class AutopilotConfig:
    """Configuration for an institution's autopilot."""
    id: str = field(default_factory=lambda: f"apc_{uuid4().hex[:12]}")
    institution_id: str = ""
    enabled: bool = False
    schedule_hour: int = 2  # 2 AM default
    schedule_minute: int = 0
    run_reindex: bool = True
    run_consistency: bool = True
    run_audit: bool = False  # Off by default (expensive)
    run_readiness: bool = True
    notify_on_complete: bool = True
    notify_on_error: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "enabled": self.enabled,
            "schedule_hour": self.schedule_hour,
            "schedule_minute": self.schedule_minute,
            "run_reindex": self.run_reindex,
            "run_consistency": self.run_consistency,
            "run_audit": self.run_audit,
            "run_readiness": self.run_readiness,
            "notify_on_complete": self.notify_on_complete,
            "notify_on_error": self.notify_on_error,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AutopilotConfig":
        return cls(
            id=row["id"],
            institution_id=row["institution_id"],
            enabled=bool(row["enabled"]),
            schedule_hour=row["schedule_hour"],
            schedule_minute=row["schedule_minute"],
            run_reindex=bool(row["run_reindex"]),
            run_consistency=bool(row["run_consistency"]),
            run_audit=bool(row["run_audit"]),
            run_readiness=bool(row["run_readiness"]),
            notify_on_complete=bool(row["notify_on_complete"]),
            notify_on_error=bool(row["notify_on_error"]),
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
        )


@dataclass
class AutopilotRun:
    """Record of an autopilot run."""
    id: str = field(default_factory=lambda: f"apr_{uuid4().hex[:12]}")
    institution_id: str = ""
    trigger_type: TriggerType = TriggerType.SCHEDULED
    status: RunStatus = RunStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    docs_indexed: int = 0
    docs_failed: int = 0
    consistency_issues_found: int = 0
    consistency_issues_resolved: int = 0
    audit_findings_count: int = 0
    readiness_score_before: Optional[int] = None
    readiness_score_after: Optional[int] = None
    error_message: Optional[str] = None
    error_details: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "trigger_type": self.trigger_type.value if isinstance(self.trigger_type, Enum) else self.trigger_type,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "docs_indexed": self.docs_indexed,
            "docs_failed": self.docs_failed,
            "consistency_issues_found": self.consistency_issues_found,
            "consistency_issues_resolved": self.consistency_issues_resolved,
            "audit_findings_count": self.audit_findings_count,
            "readiness_score_before": self.readiness_score_before,
            "readiness_score_after": self.readiness_score_after,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AutopilotRun":
        return cls(
            id=row["id"],
            institution_id=row["institution_id"],
            trigger_type=TriggerType(row["trigger_type"]) if row["trigger_type"] else TriggerType.SCHEDULED,
            status=RunStatus(row["status"]) if row["status"] else RunStatus.PENDING,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_seconds=row["duration_seconds"],
            docs_indexed=row["docs_indexed"] or 0,
            docs_failed=row["docs_failed"] or 0,
            consistency_issues_found=row["consistency_issues_found"] or 0,
            consistency_issues_resolved=row["consistency_issues_resolved"] or 0,
            audit_findings_count=row["audit_findings_count"] or 0,
            readiness_score_before=row["readiness_score_before"],
            readiness_score_after=row["readiness_score_after"],
            error_message=row["error_message"],
            created_at=row["created_at"],
        )


# =============================================================================
# Configuration Management
# =============================================================================

def get_autopilot_config(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[AutopilotConfig]:
    """Get autopilot configuration for an institution."""
    conn = conn or get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM autopilot_config WHERE institution_id = ?",
            (institution_id,)
        )
        row = cursor.fetchone()
        return AutopilotConfig.from_row(row) if row else None
    except sqlite3.OperationalError:
        return None


def save_autopilot_config(
    config: AutopilotConfig,
    conn: Optional[sqlite3.Connection] = None
) -> AutopilotConfig:
    """Save or update autopilot configuration."""
    conn = conn or get_conn()

    conn.execute("""
        INSERT INTO autopilot_config (
            id, institution_id, enabled, schedule_hour, schedule_minute,
            run_reindex, run_consistency, run_audit, run_readiness,
            notify_on_complete, notify_on_error, last_run_at, next_run_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(institution_id) DO UPDATE SET
            enabled = excluded.enabled,
            schedule_hour = excluded.schedule_hour,
            schedule_minute = excluded.schedule_minute,
            run_reindex = excluded.run_reindex,
            run_consistency = excluded.run_consistency,
            run_audit = excluded.run_audit,
            run_readiness = excluded.run_readiness,
            notify_on_complete = excluded.notify_on_complete,
            notify_on_error = excluded.notify_on_error,
            updated_at = datetime('now')
    """, (
        config.id, config.institution_id, int(config.enabled),
        config.schedule_hour, config.schedule_minute,
        int(config.run_reindex), int(config.run_consistency),
        int(config.run_audit), int(config.run_readiness),
        int(config.notify_on_complete), int(config.notify_on_error),
        config.last_run_at, config.next_run_at,
    ))
    conn.commit()

    return config


def get_enabled_configs(conn: Optional[sqlite3.Connection] = None) -> List[AutopilotConfig]:
    """Get all enabled autopilot configurations."""
    conn = conn or get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM autopilot_config WHERE enabled = 1"
        )
        return [AutopilotConfig.from_row(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


# =============================================================================
# Run History Management
# =============================================================================

def create_run(
    institution_id: str,
    trigger_type: TriggerType = TriggerType.MANUAL,
    conn: Optional[sqlite3.Connection] = None
) -> AutopilotRun:
    """Create a new autopilot run record."""
    conn = conn or get_conn()
    run = AutopilotRun(
        institution_id=institution_id,
        trigger_type=trigger_type,
        status=RunStatus.PENDING,
    )

    conn.execute("""
        INSERT INTO autopilot_runs (
            id, institution_id, trigger_type, status, created_at
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        run.id, run.institution_id, run.trigger_type.value,
        run.status.value, run.created_at,
    ))
    conn.commit()

    return run


def update_run(
    run: AutopilotRun,
    conn: Optional[sqlite3.Connection] = None
) -> None:
    """Update an autopilot run record."""
    conn = conn or get_conn()

    conn.execute("""
        UPDATE autopilot_runs SET
            status = ?,
            started_at = ?,
            completed_at = ?,
            duration_seconds = ?,
            docs_indexed = ?,
            docs_failed = ?,
            consistency_issues_found = ?,
            consistency_issues_resolved = ?,
            audit_findings_count = ?,
            readiness_score_before = ?,
            readiness_score_after = ?,
            error_message = ?,
            error_details = ?
        WHERE id = ?
    """, (
        run.status.value if isinstance(run.status, Enum) else run.status,
        run.started_at, run.completed_at, run.duration_seconds,
        run.docs_indexed, run.docs_failed,
        run.consistency_issues_found, run.consistency_issues_resolved,
        run.audit_findings_count,
        run.readiness_score_before, run.readiness_score_after,
        run.error_message, run.error_details,
        run.id,
    ))
    conn.commit()


def get_run(run_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[AutopilotRun]:
    """Get a specific run by ID."""
    conn = conn or get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM autopilot_runs WHERE id = ?",
            (run_id,)
        )
        row = cursor.fetchone()
        return AutopilotRun.from_row(row) if row else None
    except sqlite3.OperationalError:
        return None


def get_run_history(
    institution_id: str,
    limit: int = 20,
    conn: Optional[sqlite3.Connection] = None
) -> List[AutopilotRun]:
    """Get recent autopilot runs for an institution."""
    conn = conn or get_conn()
    try:
        cursor = conn.execute("""
            SELECT * FROM autopilot_runs
            WHERE institution_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (institution_id, limit))
        return [AutopilotRun.from_row(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def get_latest_run(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[AutopilotRun]:
    """Get the most recent run for an institution."""
    history = get_run_history(institution_id, limit=1, conn=conn)
    return history[0] if history else None


# =============================================================================
# Job Execution
# =============================================================================

def _reindex_documents(
    institution_id: str,
    workspace_manager,
    conn: sqlite3.Connection
) -> Dict[str, int]:
    """Re-index unprocessed documents for an institution."""
    from src.importers import parse_document, chunk_document

    indexed = 0
    failed = 0

    # Get documents needing indexing
    cursor = conn.execute("""
        SELECT id, file_path, doc_type
        FROM documents
        WHERE institution_id = ?
          AND status IN ('uploaded', 'parsed')
          AND file_path IS NOT NULL
        LIMIT 50
    """, (institution_id,))

    docs = cursor.fetchall()

    for doc in docs:
        try:
            file_path = Path(doc["file_path"])
            if not file_path.exists():
                logger.warning(f"Document file not found: {file_path}")
                failed += 1
                continue

            # Parse document
            parsed = parse_document(str(file_path))

            # Chunk document
            chunked = chunk_document(parsed, doc["id"])

            # Update document status
            conn.execute("""
                UPDATE documents
                SET status = 'indexed',
                    chunk_count = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (len(chunked.chunks), doc["id"]))

            indexed += 1
            logger.info(f"Indexed document {doc['id']} with {len(chunked.chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to index document {doc['id']}: {e}")
            failed += 1

    conn.commit()
    return {"indexed": indexed, "failed": failed}


def _run_consistency_checks(
    institution_id: str,
    conn: sqlite3.Connection
) -> Dict[str, int]:
    """Run consistency checks across documents."""
    from src.services.readiness_service import compute_readiness

    # Count existing open issues before
    cursor = conn.execute("""
        SELECT COUNT(*) as count
        FROM readiness_consistency_issues
        WHERE institution_id = ? AND status = 'open'
    """, (institution_id,))
    before_count = cursor.fetchone()["count"]

    # For now, we just count existing issues
    # Full consistency check would invoke the consistency agent
    # which requires AI calls - we'll mark this as a TODO

    cursor = conn.execute("""
        SELECT COUNT(*) as count
        FROM readiness_consistency_issues
        WHERE institution_id = ? AND status = 'open'
    """, (institution_id,))
    after_count = cursor.fetchone()["count"]

    return {
        "found": after_count,
        "resolved": max(0, before_count - after_count),
    }


def _compute_readiness(
    institution_id: str,
    accreditor_code: str,
    conn: sqlite3.Connection
) -> Dict[str, Any]:
    """Compute and persist readiness score."""
    from src.services.readiness_service import compute_readiness, persist_snapshot

    score = compute_readiness(institution_id, accreditor_code, conn)
    persist_snapshot(institution_id, score, conn)

    return {
        "total": score.total,
        "documents": score.documents,
        "compliance": score.compliance,
        "evidence": score.evidence,
        "consistency": score.consistency,
    }


def _compute_file_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        SHA256 hex digest, or None if file doesn't exist
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to compute hash for {file_path}: {e}")
        return None


def _detect_changed_documents(
    institution_id: str,
    conn: sqlite3.Connection
) -> List[Dict[str, Any]]:
    """Detect documents that have changed since last indexing via SHA256.

    Args:
        institution_id: Institution ID
        conn: Database connection

    Returns:
        List of changed document dicts with id, file_path, old_hash, new_hash
    """
    changed = []

    # Get documents with file paths
    cursor = conn.execute("""
        SELECT id, file_path, content_hash
        FROM documents
        WHERE institution_id = ?
          AND file_path IS NOT NULL
    """, (institution_id,))

    for row in cursor.fetchall():
        file_path = row["file_path"]
        old_hash = row["content_hash"]

        new_hash = _compute_file_hash(file_path)
        if new_hash is None:
            continue

        if old_hash != new_hash:
            changed.append({
                "id": row["id"],
                "file_path": file_path,
                "old_hash": old_hash,
                "new_hash": new_hash,
            })

    return changed


def _update_document_hash(
    doc_id: str,
    content_hash: str,
    conn: sqlite3.Connection
) -> None:
    """Update document content hash after indexing."""
    conn.execute("""
        UPDATE documents
        SET content_hash = ?, updated_at = datetime('now')
        WHERE id = ?
    """, (content_hash, doc_id))


def _run_compliance_audit(
    institution_id: str,
    workspace_manager,
    conn: sqlite3.Connection
) -> Dict[str, int]:
    """Run compliance audit using ComplianceAuditAgent.

    Args:
        institution_id: Institution ID
        workspace_manager: Workspace manager instance
        conn: Database connection

    Returns:
        Dict with findings_count
    """
    from src.agents.registry import AgentRegistry
    from src.agents.base_agent import AgentType
    from src.core.models import AgentSession, SessionStatus

    findings_count = 0

    # Get documents to audit
    cursor = conn.execute("""
        SELECT d.id as doc_id, d.doc_type
        FROM documents d
        WHERE d.institution_id = ?
          AND d.status = 'indexed'
        LIMIT 10
    """, (institution_id,))

    docs = cursor.fetchall()
    if not docs:
        logger.info(f"No indexed documents to audit for {institution_id}")
        return {"findings_count": 0}

    # Get standards library
    cursor = conn.execute("""
        SELECT id FROM standards_libraries
        WHERE institution_id = ? OR institution_id IS NULL
        ORDER BY institution_id DESC NULLS LAST
        LIMIT 1
    """, (institution_id,))
    lib_row = cursor.fetchone()
    standards_library_id = lib_row["id"] if lib_row else "std_accsc"

    # Create session for the audit agent
    session = AgentSession(
        institution_id=institution_id,
        agent_type=AgentType.COMPLIANCE_AUDIT.value,
        status=SessionStatus.RUNNING,
        orchestrator_request="Autopilot compliance audit",
    )

    # Create agent
    agent = AgentRegistry.create(
        AgentType.COMPLIANCE_AUDIT, session, workspace_manager
    )

    if agent is None:
        logger.error("Failed to create ComplianceAuditAgent")
        return {"findings_count": 0}

    # Run audit for each document
    for doc in docs:
        try:
            # Initialize audit
            init_result = agent._execute_tool("initialize_audit", {
                "institution_id": institution_id,
                "document_id": doc["doc_id"],
                "standards_library_id": standards_library_id,
            })

            if "error" in init_result:
                logger.warning(f"Audit init failed for {doc['doc_id']}: {init_result['error']}")
                continue

            audit_id = init_result.get("audit_id")
            if not audit_id:
                continue

            # Run completeness pass
            agent._execute_tool("run_completeness_pass", {"audit_id": audit_id})

            # Get findings count
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM audit_findings
                WHERE audit_run_id = ?
            """, (audit_id,))
            count_row = cursor.fetchone()
            if count_row:
                findings_count += count_row["count"]

        except Exception as e:
            logger.error(f"Audit failed for {doc['doc_id']}: {e}")
            continue

    return {"findings_count": findings_count}


def _generate_morning_brief(
    institution_id: str,
    run: "AutopilotRun",
    workspace_manager,
    conn: sqlite3.Connection
) -> Optional[str]:
    """Generate morning brief markdown file.

    Args:
        institution_id: Institution ID
        run: Completed autopilot run
        workspace_manager: Workspace manager instance
        conn: Database connection

    Returns:
        Path to generated brief file, or None on error
    """
    from src.services.readiness_service import get_next_actions, compute_readiness

    # Get institution info
    cursor = conn.execute(
        "SELECT name, accreditor_primary FROM institutions WHERE id = ?",
        (institution_id,)
    )
    row = cursor.fetchone()
    inst_name = row["name"] if row else "Institution"
    accreditor = row["accreditor_primary"] if row else "ACCSC"

    # Get readiness
    readiness = compute_readiness(institution_id, accreditor, conn)

    # Calculate delta from yesterday
    cursor = conn.execute("""
        SELECT score_total
        FROM institution_readiness_snapshots
        WHERE institution_id = ?
          AND DATE(created_at) < DATE('now')
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    yesterday = cursor.fetchone()
    yesterday_score = yesterday["score_total"] if yesterday else readiness.total
    delta = readiness.total - yesterday_score

    # Get next actions
    actions = get_next_actions(institution_id, readiness, accreditor, limit=5)

    # Format date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build brief content
    brief_lines = [
        f"# Morning Brief - {today}",
        "",
        f"**Institution:** {inst_name}",
        "",
        "## Readiness Score",
        "",
        f"**{readiness.total}%** ({delta:+d} from yesterday)",
        "",
        "## Top Blockers",
        "",
    ]

    if readiness.blockers:
        for i, blocker in enumerate(readiness.blockers[:5], 1):
            brief_lines.append(f"{i}. {blocker.message}")
    else:
        brief_lines.append("*No critical blockers*")

    brief_lines.extend([
        "",
        "## Next Best Actions",
        "",
    ])

    if actions:
        for i, action in enumerate(actions[:5], 1):
            brief_lines.append(f"{i}. **{action.title}** - {action.reason}")
    else:
        brief_lines.append("*No pending actions*")

    brief_lines.extend([
        "",
        "## Autopilot Run Summary",
        "",
        f"- Documents indexed: {run.docs_indexed}",
        f"- Consistency issues found: {run.consistency_issues_found}",
        f"- Audit findings: {run.audit_findings_count}",
        f"- Duration: {run.duration_seconds or 0} seconds",
        "",
        "---",
        f"*Generated by AccreditAI Autopilot at {datetime.now(timezone.utc).isoformat()}*",
    ])

    brief_content = "\n".join(brief_lines)

    # Write to workspace
    try:
        workspace_dir = Config.WORKSPACE_DIR
        briefs_dir = Path(workspace_dir) / institution_id / "briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)

        brief_path = briefs_dir / f"{today}.md"
        brief_path.write_text(brief_content, encoding="utf-8")

        logger.info(f"Generated morning brief: {brief_path}")
        return str(brief_path)

    except Exception as e:
        logger.error(f"Failed to write morning brief: {e}")
        return None


def execute_autopilot_run(
    institution_id: str,
    trigger_type: TriggerType = TriggerType.MANUAL,
    config: Optional[AutopilotConfig] = None,
    workspace_manager=None,
    on_progress: Optional[Callable[[str, int], None]] = None
) -> AutopilotRun:
    """
    Execute a full autopilot run for an institution.

    Args:
        institution_id: Institution to process
        trigger_type: How the run was triggered
        config: Optional config (loaded if not provided)
        workspace_manager: Workspace manager instance
        on_progress: Callback for progress updates (message, percent)

    Returns:
        Completed AutopilotRun with results
    """
    conn = get_conn()

    # Load config if not provided
    if config is None:
        config = get_autopilot_config(institution_id, conn)
        if config is None:
            config = AutopilotConfig(institution_id=institution_id)

    # Get accreditor code
    cursor = conn.execute(
        "SELECT accreditor_primary FROM institutions WHERE id = ?",
        (institution_id,)
    )
    row = cursor.fetchone()
    accreditor_code = row["accreditor_primary"] if row else "ACCSC"

    # Create run record
    run = create_run(institution_id, trigger_type, conn)
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(timezone.utc).isoformat()

    # Get readiness score before
    try:
        from src.services.readiness_service import compute_readiness
        before_score = compute_readiness(institution_id, accreditor_code, conn)
        run.readiness_score_before = before_score.total
    except Exception:
        run.readiness_score_before = None

    update_run(run, conn)

    try:
        # 1. Re-index documents
        if config.run_reindex:
            if on_progress:
                on_progress("Re-indexing documents...", 10)
            result = _reindex_documents(institution_id, workspace_manager, conn)
            run.docs_indexed = result["indexed"]
            run.docs_failed = result["failed"]
            logger.info(f"Reindex: {result['indexed']} indexed, {result['failed']} failed")

        # 2. Consistency checks
        if config.run_consistency:
            if on_progress:
                on_progress("Running consistency checks...", 40)
            result = _run_consistency_checks(institution_id, conn)
            run.consistency_issues_found = result["found"]
            run.consistency_issues_resolved = result["resolved"]
            logger.info(f"Consistency: {result['found']} issues, {result['resolved']} resolved")

        # 3. Compliance audit (optional, expensive)
        if config.run_audit:
            if on_progress:
                on_progress("Running compliance audit...", 60)
            result = _run_compliance_audit(institution_id, workspace_manager, conn)
            run.audit_findings_count = result["findings_count"]
            logger.info(f"Audit: {result['findings_count']} findings")

        # 4. Compute readiness
        if config.run_readiness:
            if on_progress:
                on_progress("Computing readiness score...", 80)
            result = _compute_readiness(institution_id, accreditor_code, conn)
            run.readiness_score_after = result["total"]
            logger.info(f"Readiness: {result['total']}")

        # Mark complete
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc).isoformat()

        if run.started_at:
            start = datetime.fromisoformat(run.started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(run.completed_at.replace("Z", "+00:00"))
            run.duration_seconds = int((end - start).total_seconds())

        # 5. Generate morning brief
        if on_progress:
            on_progress("Generating morning brief...", 95)
        brief_path = _generate_morning_brief(institution_id, run, workspace_manager, conn)
        if brief_path:
            logger.info(f"Morning brief generated: {brief_path}")

        if on_progress:
            on_progress("Complete!", 100)

    except Exception as e:
        logger.exception(f"Autopilot run failed: {e}")
        run.status = RunStatus.FAILED
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc).isoformat()

    update_run(run, conn)

    # Update config last_run_at
    config.last_run_at = run.completed_at
    save_autopilot_config(config, conn)

    return run


# =============================================================================
# Scheduler
# =============================================================================

_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler():
    """Get or create the global scheduler instance."""
    global _scheduler

    with _scheduler_lock:
        if _scheduler is None:
            try:
                from apscheduler.schedulers.background import BackgroundScheduler
                from apscheduler.triggers.cron import CronTrigger

                _scheduler = BackgroundScheduler(
                    timezone="UTC",
                    job_defaults={
                        "coalesce": True,
                        "max_instances": 1,
                        "misfire_grace_time": 3600,  # 1 hour
                    }
                )
                _scheduler.start()
                logger.info("Autopilot scheduler started")

            except ImportError:
                logger.warning("APScheduler not installed, scheduler disabled")
                return None

        return _scheduler


def schedule_institution(
    institution_id: str,
    config: AutopilotConfig,
    workspace_manager=None
) -> bool:
    """Schedule autopilot for an institution based on config."""
    scheduler = get_scheduler()
    if scheduler is None:
        return False

    from apscheduler.triggers.cron import CronTrigger

    job_id = f"autopilot_{institution_id}"

    # Remove existing job if any
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    if not config.enabled:
        logger.info(f"Autopilot disabled for {institution_id}")
        return True

    # Schedule the job
    trigger = CronTrigger(
        hour=config.schedule_hour,
        minute=config.schedule_minute,
        timezone="UTC"
    )

    scheduler.add_job(
        execute_autopilot_run,
        trigger=trigger,
        id=job_id,
        args=[institution_id],
        kwargs={
            "trigger_type": TriggerType.SCHEDULED,
            "config": config,
            "workspace_manager": workspace_manager,
        },
        replace_existing=True,
    )

    # Calculate next run time
    next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    config.next_run_at = next_run.isoformat() if next_run else None
    save_autopilot_config(config)

    logger.info(f"Scheduled autopilot for {institution_id} at {config.schedule_hour:02d}:{config.schedule_minute:02d} UTC")
    return True


def schedule_all_institutions(workspace_manager=None) -> int:
    """Schedule autopilot for all enabled institutions."""
    configs = get_enabled_configs()
    scheduled = 0

    for config in configs:
        if schedule_institution(config.institution_id, config, workspace_manager):
            scheduled += 1

    logger.info(f"Scheduled {scheduled} institutions for autopilot")
    return scheduled


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler

    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Autopilot scheduler stopped")
