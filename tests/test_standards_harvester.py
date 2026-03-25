"""Tests for Standards Harvester MVP (Phase 24-01).

Tests cover:
- HARV-01: Web scraping, PDF parsing, manual upload
- HARV-02: Version storage with SHA256 hash
- HARV-03: Diff generation
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.harvesters import (
    HarvesterType,
    BaseHarvester,
    WebHarvester,
    PdfHarvester,
    ManualHarvester,
    create_harvester,
)
from src.services.standards_versioning_service import (
    normalize_text,
    compute_text_hash,
    store_version,
    get_versions,
    get_latest_version,
    get_version_text,
    detect_change,
    generate_diff,
)


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture
def test_db():
    """Create an in-memory SQLite database with migration applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply migration
    migration_sql = """
    CREATE TABLE IF NOT EXISTS standards_versions (
        id TEXT PRIMARY KEY,
        accreditor_code TEXT NOT NULL,
        version_date TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        file_path TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_url TEXT,
        extracted_text_length INTEGER DEFAULT 0,
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_sv_accreditor ON standards_versions(accreditor_code);
    CREATE INDEX IF NOT EXISTS idx_sv_accreditor_date ON standards_versions(accreditor_code, version_date DESC);
    CREATE INDEX IF NOT EXISTS idx_sv_hash ON standards_versions(content_hash);
    """
    conn.executescript(migration_sql)

    yield conn
    conn.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory for file storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_html_response():
    """Mock HTML response for web scraping tests."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ACCSC Standards of Accreditation</title>
        <meta charset="utf-8">
    </head>
    <body>
        <main>
            <h1>Standards of Accreditation</h1>
            <div class="content">
                <h2>Section I: Mission and Objectives</h2>
                <p>Standard I.A: The institution must have a clearly defined mission.</p>
                <h2>Section II: Educational Programs</h2>
                <p>Standard II.A: Programs must demonstrate learning outcomes.</p>
            </div>
        </main>
    </body>
    </html>
    """


@pytest.fixture
def sample_pdf_path(temp_dir):
    """Create a sample PDF file for testing."""
    # Note: This would create a real PDF in implementation
    # For now, we'll use a text file as placeholder
    pdf_path = temp_dir / "sample_standards.pdf"
    pdf_path.write_text("Sample standards PDF content\nSection I\nSection II", encoding="utf-8")
    return pdf_path


# ========================================================================
# Harvester Tests (HARV-01)
# ========================================================================

def test_web_harvester_fetch_returns_text_and_metadata():
    """WebHarvester.fetch() should return dict with text and metadata keys."""
    with patch('src.harvesters.web_harvester.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.content = b"""
        <html>
            <body>
                <main>
                    <p>Standards content here</p>
                </main>
            </body>
        </html>
        """
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        harvester = WebHarvester()
        result = harvester.fetch({"url": "https://example.com/standards"})

        assert "text" in result
        assert "metadata" in result
        assert isinstance(result["text"], str)
        assert isinstance(result["metadata"], dict)
        assert len(result["text"]) > 0


def test_pdf_harvester_fetch_extracts_text_from_file():
    """PdfHarvester.fetch() should return extracted text from PDF file path."""
    harvester = PdfHarvester()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp.write("Sample PDF text content\nLine 2\nLine 3")
        tmp_path = tmp.name

    try:
        # Mock pdfplumber to return text
        with patch('src.harvesters.pdf_harvester.pdfplumber.open') as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample PDF text content\nLine 2\nLine 3"
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__.return_value = mock_pdf
            mock_open.return_value = mock_pdf

            result = harvester.fetch({"file_path": tmp_path})

            assert "text" in result
            assert "metadata" in result
            assert "Sample PDF text" in result["text"]
    finally:
        os.unlink(tmp_path)


def test_manual_harvester_fetch_returns_provided_text():
    """ManualHarvester.fetch() should return text from provided content string."""
    harvester = ManualHarvester()
    result = harvester.fetch({
        "text": "Manually uploaded standards text",
        "notes": "Version 2024 update"
    })

    assert "text" in result
    assert "metadata" in result
    assert result["text"] == "Manually uploaded standards text"
    assert result["metadata"]["notes"] == "Version 2024 update"


def test_create_harvester_factory():
    """create_harvester() should return correct harvester instance."""
    web = create_harvester(HarvesterType.WEB_SCRAPER)
    pdf = create_harvester(HarvesterType.PDF_PARSER)
    manual = create_harvester(HarvesterType.MANUAL_UPLOAD)

    assert isinstance(web, WebHarvester)
    assert isinstance(pdf, PdfHarvester)
    assert isinstance(manual, ManualHarvester)


# ========================================================================
# Versioning Service Tests (HARV-02, HARV-03)
# ========================================================================

def test_normalize_text_strips_whitespace_and_normalizes_line_endings():
    """normalize_text() should strip whitespace and normalize \r\n to \n."""
    text = "  \n\nLine 1\r\nLine 2\r\n\r\n  Line 3  \n\n\n"
    normalized = normalize_text(text)

    assert normalized.startswith("Line 1")
    assert "\r" not in normalized
    assert normalized.endswith("Line 3")


def test_compute_text_hash_returns_sha256_hex():
    """compute_text_hash() should return SHA256 hex digest."""
    text = "Standard text content"
    hash1 = compute_text_hash(text)
    hash2 = compute_text_hash(text)

    assert len(hash1) == 64  # SHA256 hex length
    assert hash1 == hash2  # Deterministic
    assert hash1.isalnum()  # Hex string


def test_store_version_inserts_row_with_hash(test_db, temp_dir):
    """store_version() should insert row into standards_versions with SHA256 hash."""
    text = "Sample ACCSC standards content"

    with patch('src.services.standards_versioning_service.get_conn', return_value=test_db):
        with patch('src.services.standards_versioning_service.os.makedirs'):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                result = store_version(
                    accreditor_code="ACCSC",
                    text=text,
                    source_type="web_scrape",
                    source_url="https://example.com/standards",
                    metadata={"title": "Standards"},
                    version_date="2024-01-15T00:00:00Z"
                )

    assert "id" in result
    assert result["accreditor_code"] == "ACCSC"
    assert "content_hash" in result
    assert len(result["content_hash"]) == 64


def test_get_versions_returns_list_ordered_by_date_desc(test_db):
    """get_versions() should return list ordered by version_date DESC."""
    # Insert test versions
    test_db.execute("""
        INSERT INTO standards_versions (id, accreditor_code, version_date, content_hash, file_path, source_type)
        VALUES ('v1', 'ACCSC', '2024-01-01T00:00:00Z', 'hash1', '/path1', 'web_scrape'),
               ('v2', 'ACCSC', '2024-02-01T00:00:00Z', 'hash2', '/path2', 'web_scrape'),
               ('v3', 'ACCSC', '2024-03-01T00:00:00Z', 'hash3', '/path3', 'pdf_parse')
    """)
    test_db.commit()

    with patch('src.services.standards_versioning_service.get_conn', return_value=test_db):
        versions = get_versions("ACCSC")

    assert len(versions) == 3
    assert versions[0]["version_date"] == "2024-03-01T00:00:00Z"  # Most recent first
    assert versions[1]["version_date"] == "2024-02-01T00:00:00Z"
    assert versions[2]["version_date"] == "2024-01-01T00:00:00Z"


def test_get_latest_version_returns_most_recent(test_db):
    """get_latest_version() should return most recent version for accreditor."""
    # Insert test versions
    test_db.execute("""
        INSERT INTO standards_versions (id, accreditor_code, version_date, content_hash, file_path, source_type)
        VALUES ('v1', 'ACCSC', '2024-01-01T00:00:00Z', 'hash1', '/path1', 'web_scrape'),
               ('v2', 'ACCSC', '2024-03-01T00:00:00Z', 'hash2', '/path2', 'web_scrape')
    """)
    test_db.commit()

    with patch('src.services.standards_versioning_service.get_conn', return_value=test_db):
        latest = get_latest_version("ACCSC")

    assert latest is not None
    assert latest["version_date"] == "2024-03-01T00:00:00Z"


def test_detect_change_returns_changed_true_when_hash_differs(test_db):
    """detect_change() should return changed=True when hash differs."""
    # Insert old version
    test_db.execute("""
        INSERT INTO standards_versions (id, accreditor_code, version_date, content_hash, file_path, source_type)
        VALUES ('v1', 'ACCSC', '2024-01-01T00:00:00Z', 'oldhash', '/path1', 'web_scrape')
    """)
    test_db.commit()

    new_text = "Different standards content"

    with patch('src.services.standards_versioning_service.get_conn', return_value=test_db):
        result = detect_change("ACCSC", new_text)

    assert result["changed"] is True
    assert result["is_new"] is False
    assert result["previous_hash"] == "oldhash"


def test_detect_change_returns_changed_false_when_hash_identical(test_db):
    """detect_change() should return changed=False when hash identical."""
    text = "Same standards content"
    hash_val = compute_text_hash(text)

    # Insert version with same hash
    test_db.execute("""
        INSERT INTO standards_versions (id, accreditor_code, version_date, content_hash, file_path, source_type)
        VALUES ('v1', 'ACCSC', '2024-01-01T00:00:00Z', ?, '/path1', 'web_scrape')
    """, (hash_val,))
    test_db.commit()

    with patch('src.services.standards_versioning_service.get_conn', return_value=test_db):
        result = detect_change("ACCSC", text)

    assert result["changed"] is False


def test_generate_diff_returns_html_diff_string():
    """generate_diff() should return HTML diff string with difflib.HtmlDiff."""
    old_text = "Line 1\nLine 2\nLine 3"
    new_text = "Line 1\nLine 2 modified\nLine 3\nLine 4"

    diff_html = generate_diff("old_v1", "new_v2", old_text=old_text, new_text=new_text)

    assert isinstance(diff_html, str)
    assert "<table" in diff_html.lower()
    assert "modified" in diff_html.lower()


def test_generate_diff_returns_new_version_message_when_no_previous():
    """generate_diff() should return 'New version' message when no previous version."""
    new_text = "First version of standards"

    diff_html = generate_diff(None, "new_v1", old_text=None, new_text=new_text)

    assert "first version" in diff_html.lower() or "new version" in diff_html.lower()
    assert "no previous" in diff_html.lower()
