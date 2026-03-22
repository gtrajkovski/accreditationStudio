"""Change Detection Service - Detect document changes and trigger re-audits."""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import HtmlDiff
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.config import Config
from src.db.connection import get_conn

logger = logging.getLogger(__name__)


@dataclass
class ChangeEvent:
    """Record of a document change event."""
    id: str
    document_id: str
    institution_id: str
    change_type: str  # 'content_modified', 'new_version'
    previous_sha256: Optional[str]
    new_sha256: str
    detected_at: str
    reaudit_required: bool = True
    processed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "institution_id": self.institution_id,
            "change_type": self.change_type,
            "previous_sha256": self.previous_sha256,
            "new_sha256": self.new_sha256,
            "detected_at": self.detected_at,
            "reaudit_required": self.reaudit_required,
            "processed_at": self.processed_at,
        }


def compute_file_hash(file_path: str) -> Optional[str]:
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


def detect_change(
    document_id: str,
    new_file_path: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Detect if a document has changed by comparing SHA256 hashes.

    Args:
        document_id: ID of the document to check
        new_file_path: Path to the new version of the file
        conn: Optional database connection

    Returns:
        Dictionary with keys:
        - changed: bool (True if hash differs, False if same or no old hash)
        - old_hash: Optional[str] (previous hash, None if new document)
        - new_hash: str (newly computed hash)
    """
    if conn is None:
        conn = get_conn()

    # Query current document hash
    cursor = conn.execute(
        "SELECT file_sha256 FROM documents WHERE id = ?",
        (document_id,)
    )
    row = cursor.fetchone()

    old_hash = row["file_sha256"] if row and row["file_sha256"] else None
    new_hash = compute_file_hash(new_file_path)

    # Change only if old hash exists and differs from new hash
    changed = bool(old_hash and old_hash != new_hash)

    return {
        "changed": changed,
        "old_hash": old_hash,
        "new_hash": new_hash,
    }


def record_change(
    document_id: str,
    institution_id: str,
    old_hash: Optional[str],
    new_hash: str,
    old_text_path: Optional[str],
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Record a document change event in the database.

    Args:
        document_id: ID of the document
        institution_id: ID of the institution
        old_hash: Previous SHA256 hash (None for new documents)
        new_hash: New SHA256 hash
        old_text_path: Path to stored previous text (for diff comparison)
        conn: Optional database connection

    Returns:
        ID of the created change record
    """
    if conn is None:
        conn = get_conn()

    change_id = f"chg_{uuid4().hex[:12]}"
    change_type = "content_modified" if old_hash else "new_version"

    conn.execute("""
        INSERT INTO document_changes (
            id, document_id, institution_id, change_type,
            previous_sha256, new_sha256, reaudit_required
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        change_id,
        document_id,
        institution_id,
        change_type,
        old_hash,
        new_hash,
        1,  # reaudit_required = True by default
    ))
    conn.commit()

    return change_id


def get_pending_changes(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[ChangeEvent]:
    """Get unprocessed document changes for an institution.

    Args:
        institution_id: ID of the institution
        conn: Optional database connection

    Returns:
        List of ChangeEvent objects for unprocessed changes
    """
    if conn is None:
        conn = get_conn()

    cursor = conn.execute("""
        SELECT * FROM document_changes
        WHERE institution_id = ?
          AND processed_at IS NULL
        ORDER BY detected_at DESC
    """, (institution_id,))

    changes = []
    for row in cursor.fetchall():
        change = ChangeEvent(
            id=row["id"],
            document_id=row["document_id"],
            institution_id=row["institution_id"],
            change_type=row["change_type"],
            previous_sha256=row["previous_sha256"],
            new_sha256=row["new_sha256"],
            detected_at=row["detected_at"],
            reaudit_required=bool(row["reaudit_required"]),
            processed_at=row["processed_at"],
        )
        changes.append(change)

    return changes


def get_change_count(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Get count of unprocessed document changes.

    Args:
        institution_id: ID of the institution
        conn: Optional database connection

    Returns:
        Count of unprocessed changes
    """
    if conn is None:
        conn = get_conn()

    cursor = conn.execute("""
        SELECT COUNT(*) as count FROM document_changes
        WHERE institution_id = ?
          AND processed_at IS NULL
    """, (institution_id,))

    row = cursor.fetchone()
    return row["count"] if row else 0


def store_previous_text(institution_id: str, document_id: str, text: str) -> str:
    """Store previous document text for diff comparison.

    Args:
        institution_id: ID of the institution
        document_id: ID of the document
        text: Previous document text content

    Returns:
        Path to the stored text file
    """
    workspace_dir = Config.WORKSPACE_DIR / institution_id / "change_history"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = workspace_dir / f"{document_id}_{timestamp}.txt"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return str(file_path)


# ========================================================================
# Cascade Scope Calculation (Task 1 - Phase 22-02)
# ========================================================================

@dataclass
class ReauditScope:
    """Re-audit scope with standards cascade calculation."""
    affected_standards: List[str]
    changed_documents: List[str]
    impacted_documents: List[str]
    total_to_audit: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "affected_standards": self.affected_standards,
            "changed_documents": self.changed_documents,
            "impacted_documents": self.impacted_documents,
            "total_to_audit": self.total_to_audit,
        }


def get_affected_standards(document_ids: List[str], conn: Optional[sqlite3.Connection] = None) -> List[str]:
    """Get all standards that have findings for given documents (per D-05).

    Args:
        document_ids: List of document IDs to check
        conn: Optional database connection

    Returns:
        List of standard IDs with findings for these documents
    """
    if not document_ids:
        return []

    if conn is None:
        conn = get_conn()

    placeholders = ','.join(['?' for _ in document_ids])
    cursor = conn.execute(f"""
        SELECT DISTINCT fsr.standard_id
        FROM audit_findings af
        JOIN finding_standard_refs fsr ON af.id = fsr.finding_id
        WHERE af.document_id IN ({placeholders})
    """, document_ids)

    return [row['standard_id'] for row in cursor.fetchall()]


def get_impacted_documents(
    standard_ids: List[str],
    exclude_doc_ids: List[str],
    conn: Optional[sqlite3.Connection] = None
) -> List[str]:
    """Get documents with findings for standards, excluding specified docs (per D-06).

    Args:
        standard_ids: List of standard IDs to check
        exclude_doc_ids: Document IDs to exclude from results
        conn: Optional database connection

    Returns:
        List of impacted document IDs (excluding changed documents)
    """
    if not standard_ids:
        return []

    if conn is None:
        conn = get_conn()

    std_placeholders = ','.join(['?' for _ in standard_ids])
    params = list(standard_ids)

    query = f"""
        SELECT DISTINCT af.document_id
        FROM audit_findings af
        JOIN finding_standard_refs fsr ON af.id = fsr.finding_id
        WHERE fsr.standard_id IN ({std_placeholders})
    """

    if exclude_doc_ids:
        exc_placeholders = ','.join(['?' for _ in exclude_doc_ids])
        query += f" AND af.document_id NOT IN ({exc_placeholders})"
        params.extend(exclude_doc_ids)

    cursor = conn.execute(query, params)
    return [row['document_id'] for row in cursor.fetchall()]


def calculate_reaudit_scope(
    changed_doc_ids: List[str],
    conn: Optional[sqlite3.Connection] = None
) -> ReauditScope:
    """Calculate full re-audit scope using standards cascade (per D-04).

    Algorithm:
    1. Find all findings for changed documents
    2. Extract all affected standards from those findings
    3. Find all OTHER documents with findings for those standards
    4. Return scope: affected standards + impacted documents

    Args:
        changed_doc_ids: List of changed document IDs
        conn: Optional database connection

    Returns:
        ReauditScope with affected standards, changed docs, impacted docs, and total count
    """
    if not changed_doc_ids:
        return ReauditScope([], [], [], 0)

    if conn is None:
        conn = get_conn()

    # Get affected standards
    affected_standards = get_affected_standards(changed_doc_ids, conn)

    # Get impacted documents (exclude changed docs to avoid duplicate work)
    impacted_docs = get_impacted_documents(affected_standards, changed_doc_ids, conn)

    return ReauditScope(
        affected_standards=affected_standards,
        changed_documents=changed_doc_ids,
        impacted_documents=impacted_docs,
        total_to_audit=len(changed_doc_ids) + len(impacted_docs),
    )


# ========================================================================
# Diff Generation (Task 1 - Phase 22-03)
# ========================================================================

def generate_diff(old_text: str, new_text: str) -> str:
    """Generate side-by-side HTML diff with inline highlights (per D-11).

    Uses difflib.HtmlDiff for standard Python diff rendering.
    Shows only changed sections + 3 lines context.

    Args:
        old_text: Previous document version text
        new_text: Current document version text

    Returns:
        HTML string with side-by-side diff table
    """
    if not old_text:
        return '<div class="diff-info">New document - no previous version for comparison</div>'

    differ = HtmlDiff(wrapcolumn=80)

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Generate side-by-side table with context
    html = differ.make_table(
        old_lines,
        new_lines,
        fromdesc="Previous Version",
        todesc="Current Version",
        context=True,   # Only show changed sections
        numlines=3      # 3 lines of context (per D-13)
    )

    return html


def get_change_diff(change_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Get diff HTML for a specific change event (per D-11, D-12).

    Loads old text from stored file path, new text from current document.

    Args:
        change_id: Change event ID
        conn: Optional database connection

    Returns:
        Dict with diff_html, old_version_path, document_id
    """
    conn = conn or get_conn()

    # Get change event
    cursor = conn.execute("""
        SELECT dc.*, d.file_path as current_file_path
        FROM document_changes dc
        JOIN documents d ON dc.document_id = d.id
        WHERE dc.id = ?
    """, (change_id,))
    row = cursor.fetchone()

    if not row:
        return {"error": "Change event not found"}

    # Get old text from stored path
    old_text = ""
    old_version_path = row.get("previous_version_id")  # This stores the text file path
    if old_version_path:
        try:
            old_text = Path(old_version_path).read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Failed to read old version: {e}")

    # Get new text from current document
    new_text = ""
    current_file = row.get("current_file_path")
    if current_file:
        try:
            from src.importers import parse_document
            parsed = parse_document(current_file)
            new_text = parsed.text or ""
        except Exception as e:
            logger.warning(f"Failed to parse current document: {e}")

    # Generate diff
    diff_html = generate_diff(old_text, new_text)

    return {
        "change_id": change_id,
        "document_id": row["document_id"],
        "diff_html": diff_html,
        "old_version_path": old_version_path,
        "change_type": row["change_type"],
        "detected_at": row["detected_at"],
    }


# ========================================================================
# Legacy API (for compatibility with existing code)
# ========================================================================

@dataclass
class DocumentChange:
    """Record of a document change (legacy dataclass for compatibility)."""
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


def get_pending_reaudits(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[DocumentChange]:
    """Get document changes that need re-audit (legacy API)."""
    conn = conn or get_conn()

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
    """Get change history for a document (legacy API)."""
    conn = conn or get_conn()

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
