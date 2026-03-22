"""Unit tests for change detection service.

Tests SHA256 hash computation, change detection, and change event recording.
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.services.change_detection_service import (
    compute_file_hash,
    detect_change,
    record_change,
    get_pending_changes,
    get_change_count,
    store_previous_text,
    ChangeEvent,
)


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    # Create required tables
    conn.execute("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            file_sha256 TEXT,
            file_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE document_changes (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            institution_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            previous_sha256 TEXT,
            new_sha256 TEXT,
            previous_version_id TEXT,
            new_version_id TEXT,
            sections_added INTEGER DEFAULT 0,
            sections_removed INTEGER DEFAULT 0,
            sections_modified INTEGER DEFAULT 0,
            diff_summary TEXT,
            affected_standards TEXT DEFAULT '[]',
            reaudit_required INTEGER DEFAULT 0,
            reaudit_triggered INTEGER DEFAULT 0,
            reaudit_session_id TEXT,
            detected_at TEXT NOT NULL DEFAULT (datetime('now')),
            processed_at TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
        )
    """)

    # Insert test data
    conn.execute("INSERT INTO institutions (id, name) VALUES ('inst_test', 'Test Institution')")
    conn.execute("INSERT INTO documents (id, institution_id, file_sha256) VALUES ('doc_test', 'inst_test', 'abc123')")
    conn.commit()

    yield conn
    conn.close()


def test_compute_file_hash_returns_sha256():
    """Test that compute_file_hash returns 64-character hex digest."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello, World!")
        temp_path = f.name

    try:
        result = compute_file_hash(temp_path)

        # SHA256 produces 64 character hex digest
        assert result is not None
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)
    finally:
        Path(temp_path).unlink()


def test_detect_change_returns_changed_true(test_db):
    """Test detect_change returns changed=True when hashes differ."""
    # Create a temp file with different content
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("New content")
        temp_path = f.name

    try:
        result = detect_change("doc_test", temp_path, test_db)

        assert result["changed"] is True
        assert result["old_hash"] == "abc123"
        assert result["new_hash"] is not None
        assert result["new_hash"] != "abc123"
    finally:
        Path(temp_path).unlink()


def test_detect_change_returns_changed_false_same_hash(test_db):
    """Test detect_change returns changed=False when hashes are the same."""
    # Create a temp file and compute its hash
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test content")
        temp_path = f.name

    try:
        file_hash = compute_file_hash(temp_path)

        # Update document with this hash
        test_db.execute("UPDATE documents SET file_sha256 = ? WHERE id = 'doc_test'", (file_hash,))
        test_db.commit()

        result = detect_change("doc_test", temp_path, test_db)

        assert result["changed"] is False
        assert result["old_hash"] == file_hash
        assert result["new_hash"] == file_hash
    finally:
        Path(temp_path).unlink()


def test_detect_change_returns_changed_false_new_document(test_db):
    """Test detect_change returns changed=False for new document (no old hash)."""
    # Insert document with no hash
    test_db.execute("INSERT INTO documents (id, institution_id, file_sha256) VALUES ('doc_new', 'inst_test', NULL)")
    test_db.commit()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("New document")
        temp_path = f.name

    try:
        result = detect_change("doc_new", temp_path, test_db)

        # Not a change - just a new document
        assert result["changed"] is False
        assert result["old_hash"] is None
        assert result["new_hash"] is not None
    finally:
        Path(temp_path).unlink()


def test_record_change_inserts_row(test_db):
    """Test record_change inserts a row into document_changes."""
    change_id = record_change(
        document_id="doc_test",
        institution_id="inst_test",
        old_hash="abc123",
        new_hash="def456",
        old_text_path=None,
        conn=test_db
    )

    assert change_id is not None
    assert change_id.startswith("chg_")

    # Verify row exists
    cursor = test_db.execute("SELECT * FROM document_changes WHERE id = ?", (change_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row["document_id"] == "doc_test"
    assert row["institution_id"] == "inst_test"
    assert row["change_type"] == "content_modified"
    assert row["previous_sha256"] == "abc123"
    assert row["new_sha256"] == "def456"
    assert row["reaudit_required"] == 1


def test_get_pending_changes_returns_unprocessed(test_db):
    """Test get_pending_changes returns only unprocessed changes."""
    # Insert 2 changes, mark 1 as processed
    record_change("doc_test", "inst_test", "abc", "def", None, test_db)
    change_id_2 = record_change("doc_test", "inst_test", "def", "ghi", None, test_db)

    # Mark first as processed
    test_db.execute(
        "UPDATE document_changes SET processed_at = datetime('now') WHERE id != ?",
        (change_id_2,)
    )
    test_db.commit()

    result = get_pending_changes("inst_test", test_db)

    assert len(result) == 1
    assert result[0].id == change_id_2


def test_get_change_count_counts_unprocessed(test_db):
    """Test get_change_count returns count of unprocessed changes."""
    # Insert 3 changes, mark 1 as processed
    record_change("doc_test", "inst_test", "a", "b", None, test_db)
    change_id_2 = record_change("doc_test", "inst_test", "b", "c", None, test_db)
    change_id_3 = record_change("doc_test", "inst_test", "c", "d", None, test_db)

    # Mark first as processed
    test_db.execute(
        "UPDATE document_changes SET processed_at = datetime('now') WHERE id NOT IN (?, ?)",
        (change_id_2, change_id_3)
    )
    test_db.commit()

    count = get_change_count("inst_test", test_db)

    assert count == 2


# ========================================================================
# Cascade Scope Calculation Tests (Task 1 - TDD RED phase)
# ========================================================================

@pytest.fixture
def test_db_with_audit_tables(test_db):
    """Extend test_db with audit tables for cascade scope tests."""
    # Create standards table
    test_db.execute("""
        CREATE TABLE standards (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Create audit_findings table
    test_db.execute("""
        CREATE TABLE audit_findings (
            id TEXT PRIMARY KEY,
            audit_run_id TEXT NOT NULL,
            document_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Create finding_standard_refs table
    test_db.execute("""
        CREATE TABLE finding_standard_refs (
            id TEXT PRIMARY KEY,
            finding_id TEXT NOT NULL,
            standard_id TEXT NOT NULL,
            FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
            FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE
        )
    """)

    test_db.commit()
    return test_db


def test_get_affected_standards_returns_standards(test_db_with_audit_tables):
    """Test get_affected_standards returns standard IDs for documents with findings."""
    from src.services.change_detection_service import get_affected_standards

    # Insert test data
    test_db_with_audit_tables.execute("INSERT INTO standards (id, code, name) VALUES ('std_01', 'STD-01', 'Standard 1')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_01', 'run_01', 'doc_test', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_01', 'find_01', 'std_01')")
    test_db_with_audit_tables.commit()

    result = get_affected_standards(['doc_test'], test_db_with_audit_tables)

    assert len(result) == 1
    assert 'std_01' in result


def test_get_affected_standards_empty_docs_returns_empty(test_db_with_audit_tables):
    """Test get_affected_standards returns empty list for empty input."""
    from src.services.change_detection_service import get_affected_standards

    result = get_affected_standards([], test_db_with_audit_tables)

    assert result == []


def test_get_impacted_documents_excludes_changed_docs(test_db_with_audit_tables):
    """Test get_impacted_documents excludes the originally changed documents."""
    from src.services.change_detection_service import get_impacted_documents

    # Insert test data: 2 documents with findings for same standard
    test_db_with_audit_tables.execute("INSERT INTO documents (id, institution_id) VALUES ('doc_02', 'inst_test')")
    test_db_with_audit_tables.execute("INSERT INTO standards (id, code, name) VALUES ('std_01', 'STD-01', 'Standard 1')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_01', 'run_01', 'doc_test', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_02', 'run_01', 'doc_02', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_01', 'find_01', 'std_01')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_02', 'find_02', 'std_01')")
    test_db_with_audit_tables.commit()

    result = get_impacted_documents(['std_01'], ['doc_test'], test_db_with_audit_tables)

    # Should return doc_02 only (doc_test excluded)
    assert len(result) == 1
    assert 'doc_02' in result
    assert 'doc_test' not in result


def test_calculate_reaudit_scope_full_cascade(test_db_with_audit_tables):
    """Test calculate_reaudit_scope performs full standards cascade."""
    from src.services.change_detection_service import calculate_reaudit_scope

    # Setup: 2 documents with findings for same standard
    test_db_with_audit_tables.execute("INSERT INTO documents (id, institution_id) VALUES ('doc_02', 'inst_test')")
    test_db_with_audit_tables.execute("INSERT INTO standards (id, code, name) VALUES ('std_01', 'STD-01', 'Standard 1')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_01', 'run_01', 'doc_test', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_02', 'run_01', 'doc_02', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_01', 'find_01', 'std_01')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_02', 'find_02', 'std_01')")
    test_db_with_audit_tables.commit()

    result = calculate_reaudit_scope(['doc_test'], test_db_with_audit_tables)

    assert result.affected_standards == ['std_01']
    assert result.changed_documents == ['doc_test']
    assert result.impacted_documents == ['doc_02']
    assert result.total_to_audit == 2


def test_calculate_reaudit_scope_empty_returns_zero(test_db_with_audit_tables):
    """Test calculate_reaudit_scope returns empty scope for empty input."""
    from src.services.change_detection_service import calculate_reaudit_scope

    result = calculate_reaudit_scope([], test_db_with_audit_tables)

    assert result.affected_standards == []
    assert result.changed_documents == []
    assert result.impacted_documents == []
    assert result.total_to_audit == 0


# ========================================================================
# Diff Generation Tests (Task 1 - TDD RED phase)
# ========================================================================

def test_generate_diff_returns_html_table():
    """Test generate_diff returns HTML table with side-by-side diff."""
    from src.services.change_detection_service import generate_diff

    old_text = "Line 1\nLine 2\nLine 3"
    new_text = "Line 1\nLine 2 modified\nLine 3"

    result = generate_diff(old_text, new_text)

    # Should return HTML table
    assert "<table" in result
    assert "diff" in result.lower()


def test_generate_diff_empty_old_returns_info_message():
    """Test generate_diff returns info message for new documents (empty old_text)."""
    from src.services.change_detection_service import generate_diff

    old_text = ""
    new_text = "New document content"

    result = generate_diff(old_text, new_text)

    # Should return info message
    assert "New document" in result
    assert "no previous version" in result


def test_generate_diff_shows_changes():
    """Test generate_diff highlights added lines in diff output."""
    from src.services.change_detection_service import generate_diff

    old_text = "Line 1\nLine 2"
    new_text = "Line 1\nLine 2\nLine 3 added"

    result = generate_diff(old_text, new_text)

    # Should contain the added line (HTML encodes spaces as &nbsp;)
    assert "Line&nbsp;3&nbsp;added" in result or "Line 3 added" in result


def test_get_change_diff_not_found_returns_error(test_db_with_audit_tables):
    """Test get_change_diff returns error for invalid change_id."""
    from src.services.change_detection_service import get_change_diff

    result = get_change_diff("invalid_id", test_db_with_audit_tables)

    assert "error" in result
    assert result["error"] == "Change event not found"


# ========================================================================
# Targeted Re-audit Execution Tests (Task 2 - TDD RED phase)
# ========================================================================

def test_mark_changes_processed_updates_rows(test_db):
    """Test mark_changes_processed sets processed_at and session_id."""
    from src.services.change_detection_service import mark_changes_processed

    # Insert change event
    change_id = record_change("doc_test", "inst_test", "abc", "def", None, test_db)

    # Mark as processed
    session_id = "session_123"
    rows_updated = mark_changes_processed([change_id], session_id, test_db)

    assert rows_updated == 1

    # Verify row updated
    cursor = test_db.execute("SELECT * FROM document_changes WHERE id = ?", (change_id,))
    row = cursor.fetchone()

    assert row["processed_at"] is not None
    assert row["reaudit_triggered"] == 1
    assert row["reaudit_session_id"] == session_id


def test_mark_changes_processed_links_session(test_db):
    """Test mark_changes_processed links change events to re-audit session."""
    from src.services.change_detection_service import mark_changes_processed

    # Insert 2 changes
    change_id_1 = record_change("doc_test", "inst_test", "abc", "def", None, test_db)
    change_id_2 = record_change("doc_test", "inst_test", "def", "ghi", None, test_db)

    # Mark both as processed with same session
    session_id = "session_456"
    mark_changes_processed([change_id_1, change_id_2], session_id, test_db)

    # Verify both linked to same session
    cursor = test_db.execute("""
        SELECT id, reaudit_session_id FROM document_changes
        WHERE id IN (?, ?)
    """, (change_id_1, change_id_2))
    rows = cursor.fetchall()

    assert len(rows) == 2
    assert all(row["reaudit_session_id"] == session_id for row in rows)


def test_get_pending_change_ids_returns_unprocessed(test_db):
    """Test get_pending_change_ids returns only unprocessed change IDs."""
    from src.services.change_detection_service import get_pending_change_ids

    # Insert 2 changes, mark 1 as processed
    change_id_1 = record_change("doc_test", "inst_test", "abc", "def", None, test_db)
    change_id_2 = record_change("doc_test", "inst_test", "def", "ghi", None, test_db)

    # Mark first as processed
    test_db.execute(
        "UPDATE document_changes SET processed_at = datetime('now') WHERE id = ?",
        (change_id_1,)
    )
    test_db.commit()

    result = get_pending_change_ids("inst_test", test_db)

    assert len(result) == 1
    assert change_id_2 in result
    assert change_id_1 not in result


def test_cascade_scope_filtering(test_db_with_audit_tables):
    """Test CHG-03: ONLY documents in cascade scope are audited (not entire library).

    Scenario:
    - 3 documents exist: doc_test, doc_02, doc_03
    - doc_test is changed
    - doc_test and doc_02 share standard std_01 (both in cascade scope)
    - doc_03 has NO findings for std_01 (OUT OF SCOPE)

    Expected: Re-audit ONLY doc_test and doc_02. doc_03 should NOT be audited.
    """
    from src.services.change_detection_service import calculate_reaudit_scope

    # Insert 3 documents
    test_db_with_audit_tables.execute("INSERT INTO documents (id, institution_id) VALUES ('doc_02', 'inst_test')")
    test_db_with_audit_tables.execute("INSERT INTO documents (id, institution_id) VALUES ('doc_03', 'inst_test')")

    # Insert standards
    test_db_with_audit_tables.execute("INSERT INTO standards (id, code, name) VALUES ('std_01', 'STD-01', 'Standard 1')")
    test_db_with_audit_tables.execute("INSERT INTO standards (id, code, name) VALUES ('std_02', 'STD-02', 'Standard 2')")

    # doc_test and doc_02 have findings for std_01 (cascade scope)
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_01', 'run_01', 'doc_test', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_02', 'run_01', 'doc_02', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_01', 'find_01', 'std_01')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_02', 'find_02', 'std_01')")

    # doc_03 has findings ONLY for std_02 (OUT OF SCOPE for std_01 cascade)
    test_db_with_audit_tables.execute("INSERT INTO audit_findings (id, audit_run_id, document_id, status) VALUES ('find_03', 'run_01', 'doc_03', 'non_compliant')")
    test_db_with_audit_tables.execute("INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES ('ref_03', 'find_03', 'std_02')")

    test_db_with_audit_tables.commit()

    # Calculate scope for changed doc_test
    result = calculate_reaudit_scope(['doc_test'], test_db_with_audit_tables)

    # CHG-03 CRITICAL: ONLY doc_test and doc_02 should be in scope
    # doc_03 should NOT be in scope because it has no findings for std_01
    assert result.affected_standards == ['std_01']
    assert result.changed_documents == ['doc_test']
    assert result.impacted_documents == ['doc_02']
    assert result.total_to_audit == 2

    # CRITICAL: doc_03 should NOT be in the scope
    assert 'doc_03' not in result.impacted_documents
