"""Tests for Autopilot Service - Document change detection and morning brief generation."""

import hashlib
import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.services.autopilot_service import (
    AutopilotConfig,
    AutopilotRun,
    RunStatus,
    TriggerType,
    _compute_file_hash,
    _detect_changed_documents,
    _generate_morning_brief,
    _update_document_hash,
    get_autopilot_config,
    save_autopilot_config,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with autopilot schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT,
            accreditor_primary TEXT DEFAULT 'ACCSC',
            readiness_stale INTEGER DEFAULT 1,
            readiness_computed_at TEXT
        );

        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            doc_type TEXT,
            status TEXT DEFAULT 'uploaded',
            file_path TEXT,
            content_hash TEXT,
            title TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE autopilot_config (
            id TEXT PRIMARY KEY,
            institution_id TEXT UNIQUE,
            enabled INTEGER DEFAULT 0,
            schedule_hour INTEGER DEFAULT 2,
            schedule_minute INTEGER DEFAULT 0,
            run_reindex INTEGER DEFAULT 1,
            run_consistency INTEGER DEFAULT 1,
            run_audit INTEGER DEFAULT 0,
            run_readiness INTEGER DEFAULT 1,
            notify_on_complete INTEGER DEFAULT 1,
            notify_on_error INTEGER DEFAULT 1,
            last_run_at TEXT,
            next_run_at TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE autopilot_runs (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            trigger_type TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            duration_seconds INTEGER,
            docs_indexed INTEGER DEFAULT 0,
            docs_failed INTEGER DEFAULT 0,
            consistency_issues_found INTEGER DEFAULT 0,
            consistency_issues_resolved INTEGER DEFAULT 0,
            audit_findings_count INTEGER DEFAULT 0,
            readiness_score_before INTEGER,
            readiness_score_after INTEGER,
            error_message TEXT,
            error_details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE institution_readiness_snapshots (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            score_total INTEGER,
            score_documents INTEGER,
            score_compliance INTEGER,
            score_evidence INTEGER,
            score_consistency INTEGER,
            blockers_json TEXT,
            breakdown_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def test_files(tmp_path):
    """Create test files for hash computation."""
    file1 = tmp_path / "doc1.txt"
    file1.write_text("Test content for document 1", encoding="utf-8")

    file2 = tmp_path / "doc2.txt"
    file2.write_text("Test content for document 2", encoding="utf-8")

    return {"file1": file1, "file2": file2}


class TestFileHash:
    """Tests for _compute_file_hash."""

    def test_compute_hash_success(self, test_files):
        """Test computing SHA256 hash of existing file."""
        file_path = test_files["file1"]
        result = _compute_file_hash(str(file_path))

        assert result is not None
        assert len(result) == 64  # SHA256 hex digest length
        assert all(c in '0123456789abcdef' for c in result)

    def test_compute_hash_missing_file(self, tmp_path):
        """Test computing hash of non-existent file."""
        missing_file = tmp_path / "nonexistent.txt"
        result = _compute_file_hash(str(missing_file))

        assert result is None

    def test_compute_hash_consistent(self, test_files):
        """Test that hash is consistent for same file."""
        file_path = test_files["file1"]
        hash1 = _compute_file_hash(str(file_path))
        hash2 = _compute_file_hash(str(file_path))

        assert hash1 == hash2

    def test_compute_hash_different_files(self, test_files):
        """Test that different files have different hashes."""
        hash1 = _compute_file_hash(str(test_files["file1"]))
        hash2 = _compute_file_hash(str(test_files["file2"]))

        assert hash1 != hash2


class TestChangeDetection:
    """Tests for _detect_changed_documents."""

    def test_detect_new_file(self, test_db, test_files):
        """Test detecting a new document with no hash."""
        # Insert document without hash
        test_db.execute("""
            INSERT INTO documents (id, institution_id, file_path, content_hash)
            VALUES ('doc1', 'inst1', ?, NULL)
        """, (str(test_files["file1"]),))
        test_db.commit()

        changed = _detect_changed_documents("inst1", test_db)

        assert len(changed) == 1
        assert changed[0]["id"] == "doc1"
        assert changed[0]["old_hash"] is None
        assert changed[0]["new_hash"] is not None

    def test_detect_unchanged_file(self, test_db, test_files):
        """Test that unchanged file is not detected."""
        # Compute actual hash
        file_path = str(test_files["file1"])
        actual_hash = _compute_file_hash(file_path)

        # Insert document with correct hash
        test_db.execute("""
            INSERT INTO documents (id, institution_id, file_path, content_hash)
            VALUES ('doc1', 'inst1', ?, ?)
        """, (file_path, actual_hash))
        test_db.commit()

        changed = _detect_changed_documents("inst1", test_db)

        assert len(changed) == 0

    def test_detect_changed_file(self, test_db, test_files):
        """Test detecting a file that has changed."""
        file_path = str(test_files["file1"])
        old_hash = "0" * 64  # Fake old hash

        # Insert document with old hash
        test_db.execute("""
            INSERT INTO documents (id, institution_id, file_path, content_hash)
            VALUES ('doc1', 'inst1', ?, ?)
        """, (file_path, old_hash))
        test_db.commit()

        changed = _detect_changed_documents("inst1", test_db)

        assert len(changed) == 1
        assert changed[0]["id"] == "doc1"
        assert changed[0]["old_hash"] == old_hash
        assert changed[0]["new_hash"] != old_hash


class TestUpdateDocumentHash:
    """Tests for _update_document_hash."""

    def test_update_hash(self, test_db):
        """Test updating document hash."""
        # Insert document
        test_db.execute("""
            INSERT INTO documents (id, institution_id, content_hash)
            VALUES ('doc1', 'inst1', 'old_hash')
        """)
        test_db.commit()

        # Update hash
        new_hash = "a" * 64
        _update_document_hash("doc1", new_hash, test_db)
        test_db.commit()

        # Verify
        cursor = test_db.execute(
            "SELECT content_hash FROM documents WHERE id = ?",
            ("doc1",)
        )
        row = cursor.fetchone()
        assert row["content_hash"] == new_hash


class TestAutopilotConfig:
    """Tests for autopilot configuration."""

    def test_save_and_get_config(self, test_db):
        """Test saving and retrieving config."""
        config = AutopilotConfig(
            institution_id="inst1",
            enabled=True,
            schedule_hour=3,
            run_audit=True,
        )

        # Mock get_conn to return test_db
        with patch("src.services.autopilot_service.get_conn", return_value=test_db):
            save_autopilot_config(config, test_db)
            loaded = get_autopilot_config("inst1", test_db)

        assert loaded is not None
        assert loaded.institution_id == "inst1"
        assert loaded.enabled is True
        assert loaded.schedule_hour == 3
        assert loaded.run_audit is True

    def test_config_update(self, test_db):
        """Test updating existing config."""
        # Save initial config
        config = AutopilotConfig(
            institution_id="inst1",
            enabled=False,
        )
        save_autopilot_config(config, test_db)

        # Update config
        config.enabled = True
        config.schedule_hour = 5
        save_autopilot_config(config, test_db)

        # Verify
        loaded = get_autopilot_config("inst1", test_db)
        assert loaded.enabled is True
        assert loaded.schedule_hour == 5


class TestMorningBrief:
    """Tests for morning brief generation."""

    def test_generate_brief_content(self, test_db, tmp_path):
        """Test morning brief file generation."""
        # Setup institution
        test_db.execute("""
            INSERT INTO institutions (id, name, accreditor_primary)
            VALUES ('inst1', 'Test University', 'ACCSC')
        """)
        test_db.commit()

        # Create run record
        run = AutopilotRun(
            id="run1",
            institution_id="inst1",
            status=RunStatus.COMPLETED,
            docs_indexed=5,
            consistency_issues_found=2,
            audit_findings_count=3,
            duration_seconds=120,
        )

        # Mock config and readiness service
        with patch("src.services.autopilot_service.Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            with patch("src.services.readiness_service.compute_readiness") as mock_readiness:
                mock_score = MagicMock()
                mock_score.total = 75
                mock_score.blockers = []
                mock_readiness.return_value = mock_score

                with patch("src.services.readiness_service.get_next_actions") as mock_actions:
                    mock_actions.return_value = []

                    brief_path = _generate_morning_brief(
                        "inst1", run, None, test_db
                    )

        assert brief_path is not None
        assert Path(brief_path).exists()

        # Verify content
        content = Path(brief_path).read_text(encoding="utf-8")
        assert "Morning Brief" in content
        assert "Test University" in content
        assert "75%" in content
        assert "Documents indexed: 5" in content
        assert "Consistency issues found: 2" in content
        assert "Audit findings: 3" in content
        assert "Duration: 120 seconds" in content

    def test_brief_with_blockers(self, test_db, tmp_path):
        """Test brief includes blockers when present."""
        # Setup
        test_db.execute("""
            INSERT INTO institutions (id, name, accreditor_primary)
            VALUES ('inst1', 'Test University', 'ACCSC')
        """)
        test_db.commit()

        run = AutopilotRun(institution_id="inst1", status=RunStatus.COMPLETED)

        with patch("src.services.autopilot_service.Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            with patch("src.services.readiness_service.compute_readiness") as mock_readiness:
                mock_blocker = MagicMock()
                mock_blocker.message = "Missing catalog document"

                mock_score = MagicMock()
                mock_score.total = 60
                mock_score.blockers = [mock_blocker]
                mock_readiness.return_value = mock_score

                with patch("src.services.readiness_service.get_next_actions") as mock_actions:
                    mock_actions.return_value = []

                    brief_path = _generate_morning_brief(
                        "inst1", run, None, test_db
                    )

        content = Path(brief_path).read_text(encoding="utf-8")
        assert "Missing catalog document" in content

    def test_brief_delta_calculation(self, test_db, tmp_path):
        """Test readiness delta calculation from yesterday."""
        # Setup institution
        test_db.execute("""
            INSERT INTO institutions (id, name, accreditor_primary)
            VALUES ('inst1', 'Test University', 'ACCSC')
        """)

        # Insert yesterday's snapshot
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        test_db.execute("""
            INSERT INTO institution_readiness_snapshots
            (id, institution_id, score_total, blockers_json, breakdown_json, created_at)
            VALUES ('snap1', 'inst1', 70, '[]', '{}', ?)
        """, (yesterday,))
        test_db.commit()

        run = AutopilotRun(institution_id="inst1", status=RunStatus.COMPLETED)

        with patch("src.services.autopilot_service.Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            with patch("src.services.readiness_service.compute_readiness") as mock_readiness:
                mock_score = MagicMock()
                mock_score.total = 75  # +5 from yesterday
                mock_score.blockers = []
                mock_readiness.return_value = mock_score

                with patch("src.services.readiness_service.get_next_actions") as mock_actions:
                    mock_actions.return_value = []

                    brief_path = _generate_morning_brief(
                        "inst1", run, None, test_db
                    )

        content = Path(brief_path).read_text(encoding="utf-8")
        assert "+5" in content  # Delta should be +5
