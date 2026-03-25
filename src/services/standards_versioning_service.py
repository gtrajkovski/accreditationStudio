"""Standards Versioning Service.

Handles version storage, hash-based change detection, and diff generation
for accreditation standards.
"""

import hashlib
import json
import logging
import os
import sqlite3
from difflib import HtmlDiff
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from src.db.connection import get_conn
from src.core.models import now_iso


logger = logging.getLogger(__name__)


# ========================================================================
# Text Normalization & Hashing
# ========================================================================

def normalize_text(text: str) -> str:
    """Normalize text for consistent hashing.

    Strips leading/trailing whitespace, normalizes line endings,
    and collapses multiple blank lines.

    Args:
        text: Raw text content

    Returns:
        Normalized text
    """
    # Strip whitespace
    text = text.strip()

    # Normalize line endings
    text = text.replace('\r\n', '\n')

    # Collapse multiple blank lines to double newline
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')

    return text


def compute_text_hash(text: str) -> str:
    """Compute SHA256 hash of normalized text.

    Args:
        text: Text content to hash

    Returns:
        SHA256 hex digest (64 characters)
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


# ========================================================================
# Version Storage
# ========================================================================

def store_version(
    accreditor_code: str,
    text: str,
    source_type: str,
    source_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    version_date: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Store a new standards version.

    Args:
        accreditor_code: Accreditor code (e.g., "ACCSC")
        text: Standards text content
        source_type: Type of source ("web_scrape", "pdf_parse", "manual_upload")
        source_url: Optional URL of source
        metadata: Optional metadata dict
        version_date: Optional version date (ISO format). Defaults to now.
        conn: Optional database connection

    Returns:
        Dictionary with version info:
            - id: str
            - accreditor_code: str
            - version_date: str
            - content_hash: str
            - source_type: str
            - is_new: bool (True if first version for this accreditor)
            - changed: bool (True if hash differs from previous version)
    """
    if conn is None:
        conn = get_conn()

    # Compute hash
    content_hash = compute_text_hash(text)

    # Generate ID and version date
    version_id = str(uuid4())
    if version_date is None:
        version_date = now_iso()

    # Save text to file
    file_path = f"standards_library/versions/{accreditor_code}/{version_id}.txt"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

    logger.info(f"Saved version text to {file_path}")

    # Check if this is a new version (different hash)
    cursor = conn.execute("""
        SELECT content_hash, version_date
        FROM standards_versions
        WHERE accreditor_code = ?
        ORDER BY version_date DESC
        LIMIT 1
    """, (accreditor_code,))

    row = cursor.fetchone()

    is_new = row is None
    changed = (row is None) or (row["content_hash"] != content_hash)

    # Insert into database
    metadata_json = json.dumps(metadata or {})

    conn.execute("""
        INSERT INTO standards_versions (
            id, accreditor_code, version_date, content_hash, file_path,
            source_type, source_url, extracted_text_length, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        version_id,
        accreditor_code,
        version_date,
        content_hash,
        file_path,
        source_type,
        source_url,
        len(text),
        metadata_json
    ))

    conn.commit()

    logger.info(
        f"Stored version {version_id} for {accreditor_code} "
        f"(hash: {content_hash[:8]}..., changed: {changed})"
    )

    return {
        "id": version_id,
        "accreditor_code": accreditor_code,
        "version_date": version_date,
        "content_hash": content_hash,
        "source_type": source_type,
        "is_new": is_new,
        "changed": changed
    }


# ========================================================================
# Version Retrieval
# ========================================================================

def get_versions(
    accreditor_code: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Get all versions for an accreditor, ordered by date descending.

    Args:
        accreditor_code: Accreditor code
        conn: Optional database connection

    Returns:
        List of version dicts
    """
    if conn is None:
        conn = get_conn()

    cursor = conn.execute("""
        SELECT id, accreditor_code, version_date, content_hash, file_path,
               source_type, source_url, extracted_text_length, metadata, created_at
        FROM standards_versions
        WHERE accreditor_code = ?
        ORDER BY version_date DESC
    """, (accreditor_code,))

    versions = []
    for row in cursor.fetchall():
        versions.append({
            "id": row["id"],
            "accreditor_code": row["accreditor_code"],
            "version_date": row["version_date"],
            "content_hash": row["content_hash"],
            "file_path": row["file_path"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "extracted_text_length": row["extracted_text_length"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"]
        })

    return versions


def get_latest_version(
    accreditor_code: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Get the latest version for an accreditor.

    Args:
        accreditor_code: Accreditor code
        conn: Optional database connection

    Returns:
        Version dict or None if no versions exist
    """
    if conn is None:
        conn = get_conn()

    cursor = conn.execute("""
        SELECT id, accreditor_code, version_date, content_hash, file_path,
               source_type, source_url, extracted_text_length, metadata, created_at
        FROM standards_versions
        WHERE accreditor_code = ?
        ORDER BY version_date DESC
        LIMIT 1
    """, (accreditor_code,))

    row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "accreditor_code": row["accreditor_code"],
        "version_date": row["version_date"],
        "content_hash": row["content_hash"],
        "file_path": row["file_path"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "extracted_text_length": row["extracted_text_length"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "created_at": row["created_at"]
    }


def get_version_text(
    version_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[str]:
    """Load text content for a specific version.

    Args:
        version_id: Version ID
        conn: Optional database connection

    Returns:
        Text content or None if version not found
    """
    if conn is None:
        conn = get_conn()

    cursor = conn.execute("""
        SELECT file_path
        FROM standards_versions
        WHERE id = ?
    """, (version_id,))

    row = cursor.fetchone()

    if not row:
        return None

    file_path = row["file_path"]
    if not os.path.exists(file_path):
        logger.warning(f"Version file not found: {file_path}")
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# ========================================================================
# Change Detection
# ========================================================================

def detect_change(
    accreditor_code: str,
    new_text: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Detect if new text differs from the latest version.

    Args:
        accreditor_code: Accreditor code
        new_text: New standards text
        conn: Optional database connection

    Returns:
        Dictionary with:
            - changed: bool (True if hash differs)
            - is_new: bool (True if no previous version)
            - previous_hash: Optional[str]
            - new_hash: str
    """
    if conn is None:
        conn = get_conn()

    new_hash = compute_text_hash(new_text)

    # Get latest version
    latest = get_latest_version(accreditor_code, conn)

    if not latest:
        return {
            "changed": True,
            "is_new": True,
            "previous_hash": None,
            "new_hash": new_hash
        }

    previous_hash = latest["content_hash"]
    changed = (previous_hash != new_hash)

    return {
        "changed": changed,
        "is_new": False,
        "previous_hash": previous_hash,
        "new_hash": new_hash
    }


# ========================================================================
# Diff Generation
# ========================================================================

def generate_diff(
    old_version_id: Optional[str],
    new_version_id: str,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Generate side-by-side HTML diff between two versions.

    Args:
        old_version_id: ID of old version (None for first version)
        new_version_id: ID of new version
        old_text: Optional old text (if not provided, loaded from version)
        new_text: Optional new text (if not provided, loaded from version)
        conn: Optional database connection

    Returns:
        HTML diff string
    """
    if conn is None:
        conn = get_conn()

    # Load text if not provided
    if old_version_id and old_text is None:
        old_text = get_version_text(old_version_id, conn)

    if new_text is None:
        new_text = get_version_text(new_version_id, conn)

    # Handle first version case
    if not old_text:
        return '<div class="diff-info">First version - no previous version to compare</div>'

    # Generate diff
    differ = HtmlDiff(wrapcolumn=80)

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    html = differ.make_table(
        old_lines,
        new_lines,
        fromdesc="Previous Version",
        todesc="Current Version",
        context=True,   # Only show changed sections
        numlines=3      # 3 lines of context
    )

    return html
