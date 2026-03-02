"""Change Detection Service - Detect document changes and trigger re-audits."""

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.db.connection import get_conn


@dataclass
class DocumentChange:
    """Record of a document change."""
    id: str = field(default_factory=lambda: f"chg_{uuid4().hex[:12]}")
    document_id: str = ""
    institution_id: str = ""
    change_type: str = "modified"  # created, modified, replaced
    previous_sha256: Optional[str] = None
    new_sha256: Optional[str] = None
    sections_added: int = 0
    sections_removed: int = 0
    sections_modified: int = 0
    diff_summary: Optional[str] = None
    affected_standards: List[str] = field(default_factory=list)
    reaudit_required: bool = False
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "institution_id": self.institution_id,
            "change_type": self.change_type,
            "previous_sha256": self.previous_sha256,
            "new_sha256": self.new_sha256,
            "sections_added": self.sections_added,
            "sections_removed": self.sections_removed,
            "sections_modified": self.sections_modified,
            "diff_summary": self.diff_summary,
            "affected_standards": self.affected_standards,
            "reaudit_required": self.reaudit_required,
            "detected_at": self.detected_at,
        }


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_change(
    document_id: str,
    new_file_path: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[DocumentChange]:
    """
    Detect if a document has changed by comparing hashes.

    Returns DocumentChange if changed, None if unchanged.
    """
    conn = conn or get_conn()

    # Get current document info
    cursor = conn.execute(
        "SELECT institution_id, file_sha256, doc_type FROM documents WHERE id = ?",
        (document_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    old_hash = row["file_sha256"]
    new_hash = compute_file_hash(new_file_path)

    if old_hash == new_hash:
        return None  # No change

    change = DocumentChange(
        document_id=document_id,
        institution_id=row["institution_id"],
        change_type="modified",
        previous_sha256=old_hash,
        new_sha256=new_hash,
    )

    # Find affected standards from existing audit findings
    cursor = conn.execute("""
        SELECT DISTINCT fsr.standard_ref
        FROM finding_standard_refs fsr
        JOIN audit_findings af ON fsr.finding_id = af.id
        JOIN evidence_refs er ON er.finding_id = af.id
        WHERE er.document_id = ?
    """, (document_id,))

    change.affected_standards = [r["standard_ref"] for r in cursor.fetchall()]
    change.reaudit_required = len(change.affected_standards) > 0

    return change


def record_change(
    change: DocumentChange,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Record a document change in the database."""
    conn = conn or get_conn()

    import json
    conn.execute("""
        INSERT INTO document_changes (
            id, document_id, institution_id, change_type,
            previous_sha256, new_sha256,
            sections_added, sections_removed, sections_modified,
            diff_summary, affected_standards, reaudit_required
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        change.id, change.document_id, change.institution_id, change.change_type,
        change.previous_sha256, change.new_sha256,
        change.sections_added, change.sections_removed, change.sections_modified,
        change.diff_summary, json.dumps(change.affected_standards),
        int(change.reaudit_required),
    ))
    conn.commit()

    return change.id


def get_pending_reaudits(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[DocumentChange]:
    """Get document changes that need re-audit."""
    conn = conn or get_conn()

    import json
    try:
        cursor = conn.execute("""
            SELECT * FROM document_changes
            WHERE institution_id = ?
              AND reaudit_required = 1
              AND reaudit_triggered = 0
            ORDER BY detected_at DESC
        """, (institution_id,))

        changes = []
        for row in cursor.fetchall():
            change = DocumentChange(
                id=row["id"],
                document_id=row["document_id"],
                institution_id=row["institution_id"],
                change_type=row["change_type"],
                previous_sha256=row["previous_sha256"],
                new_sha256=row["new_sha256"],
                sections_added=row["sections_added"] or 0,
                sections_removed=row["sections_removed"] or 0,
                sections_modified=row["sections_modified"] or 0,
                diff_summary=row["diff_summary"],
                affected_standards=json.loads(row["affected_standards"] or "[]"),
                reaudit_required=bool(row["reaudit_required"]),
                detected_at=row["detected_at"],
            )
            changes.append(change)
        return changes
    except sqlite3.OperationalError:
        return []


def get_change_history(
    document_id: str,
    limit: int = 20,
    conn: Optional[sqlite3.Connection] = None
) -> List[DocumentChange]:
    """Get change history for a document."""
    conn = conn or get_conn()

    import json
    try:
        cursor = conn.execute("""
            SELECT * FROM document_changes
            WHERE document_id = ?
            ORDER BY detected_at DESC
            LIMIT ?
        """, (document_id, limit))

        changes = []
        for row in cursor.fetchall():
            change = DocumentChange(
                id=row["id"],
                document_id=row["document_id"],
                institution_id=row["institution_id"],
                change_type=row["change_type"],
                previous_sha256=row["previous_sha256"],
                new_sha256=row["new_sha256"],
                affected_standards=json.loads(row["affected_standards"] or "[]"),
                reaudit_required=bool(row["reaudit_required"]),
                detected_at=row["detected_at"],
            )
            changes.append(change)
        return changes
    except sqlite3.OperationalError:
        return []


def invalidate_findings(
    change: DocumentChange,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Mark audit findings as needing re-validation due to document change."""
    conn = conn or get_conn()

    # Find findings that referenced this document
    cursor = conn.execute("""
        SELECT af.id, fsr.standard_ref
        FROM audit_findings af
        JOIN evidence_refs er ON er.finding_id = af.id
        LEFT JOIN finding_standard_refs fsr ON fsr.finding_id = af.id
        WHERE er.document_id = ?
    """, (change.document_id,))

    count = 0
    for row in cursor.fetchall():
        try:
            conn.execute("""
                INSERT INTO audit_invalidations (id, change_id, finding_id, standard_ref, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"inv_{uuid4().hex[:12]}",
                change.id,
                row["id"],
                row["standard_ref"],
                f"Source document modified: {change.change_type}",
            ))
            count += 1
        except sqlite3.IntegrityError:
            pass  # Already invalidated

    conn.commit()
    return count
