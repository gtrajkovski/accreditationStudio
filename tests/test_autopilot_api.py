"""Tests for Autopilot API endpoints.

These tests focus on testable units without requiring the full app context.
Integration tests for endpoints are handled via Flask test client in other files.
"""

import json
import pytest
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock optional dependencies before any imports that might trigger them
# These are optional dependencies that may not be installed in test environment
if "weasyprint" not in sys.modules:
    sys.modules["weasyprint"] = MagicMock()
    sys.modules["weasyprint.HTML"] = MagicMock()
if "flask_apscheduler" not in sys.modules:
    sys.modules["flask_apscheduler"] = MagicMock()
if "apscheduler" not in sys.modules:
    sys.modules["apscheduler"] = MagicMock()
    sys.modules["apscheduler.jobstores"] = MagicMock()
    sys.modules["apscheduler.jobstores.sqlalchemy"] = MagicMock()
    sys.modules["apscheduler.schedulers"] = MagicMock()
    sys.modules["apscheduler.schedulers.background"] = MagicMock()
    sys.modules["apscheduler.triggers"] = MagicMock()
    sys.modules["apscheduler.triggers.cron"] = MagicMock()

from src.services.autopilot_service import (
    AutopilotConfig,
    AutopilotRun,
    RunStatus,
    TriggerType,
    create_run,
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
            chunk_count INTEGER DEFAULT 0,
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

        CREATE TABLE readiness_consistency_issues (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            status TEXT DEFAULT 'open'
        );
    """)

    # Insert test institution
    conn.execute("""
        INSERT INTO institutions (id, name, accreditor_primary)
        VALUES ('inst_test', 'Test University', 'ACCSC')
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def briefs_dir(tmp_path):
    """Create a test briefs directory with sample briefs."""
    briefs_path = tmp_path / "inst_test" / "briefs"
    briefs_path.mkdir(parents=True)

    # Create sample briefs
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    brief_content = """# Morning Brief - {date}

**Institution:** Test University

## Readiness Score

**75%** (+5 from yesterday)

## Top Blockers

*No critical blockers*

## Next Best Actions

1. **Upload missing documents** - Policy manual required

## Autopilot Run Summary

- Documents indexed: 5
- Consistency issues found: 2
- Audit findings: 3
- Duration: 120 seconds

---
*Generated by AccreditAI Autopilot*
"""

    (briefs_path / f"{today}.md").write_text(
        brief_content.format(date=today), encoding="utf-8"
    )
    (briefs_path / f"{yesterday}.md").write_text(
        brief_content.format(date=yesterday).replace("75%", "70%"),
        encoding="utf-8"
    )

    return tmp_path


@pytest.fixture
def autopilot_module():
    """Import autopilot module with mocked dependencies."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "autopilot",
        "src/api/autopilot.py"
    )
    autopilot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(autopilot)
    return autopilot


class TestProgressTracking:
    """Tests for progress tracking functions used by SSE."""

    def test_progress_update_and_get(self, autopilot_module):
        """Test progress can be updated and retrieved."""
        autopilot = autopilot_module

        run_id = "test_progress_1"
        autopilot._update_progress(run_id, "Working...", 50, "running")

        progress = autopilot._get_progress(run_id)
        assert progress is not None
        assert progress["message"] == "Working..."
        assert progress["percent"] == 50
        assert progress["status"] == "running"
        assert "updated_at" in progress

        # Clean up
        autopilot._clear_progress(run_id)

    def test_progress_clear(self, autopilot_module):
        """Test progress can be cleared."""
        autopilot = autopilot_module

        run_id = "test_progress_2"
        autopilot._update_progress(run_id, "Working...", 50, "running")
        autopilot._clear_progress(run_id)

        progress = autopilot._get_progress(run_id)
        assert progress is None

    def test_progress_missing_returns_none(self, autopilot_module):
        """Test getting non-existent progress returns None."""
        autopilot = autopilot_module

        progress = autopilot._get_progress("nonexistent_run_id")
        assert progress is None

    def test_progress_thread_safety(self, autopilot_module):
        """Test progress tracking is thread-safe."""
        autopilot = autopilot_module

        results = []
        errors = []

        def update_thread(run_id, count):
            try:
                for i in range(count):
                    autopilot._update_progress(run_id, f"Step {i}", i, "running")
                    time.sleep(0.01)
                results.append(run_id)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(5):
            t = threading.Thread(target=update_thread, args=(f"run_{i}", 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All threads should complete without errors
        assert len(results) == 5
        assert len(errors) == 0

        # Clean up
        for i in range(5):
            autopilot._clear_progress(f"run_{i}")


class TestBriefsHelper:
    """Tests for brief listing helper functions."""

    def test_list_briefs_returns_sorted(self, briefs_dir, autopilot_module):
        """Test _list_briefs returns briefs sorted by date descending."""
        autopilot = autopilot_module

        with patch.object(autopilot, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            briefs = autopilot._list_briefs("inst_test", days=30)

            assert len(briefs) == 2
            # Should be sorted descending (today first)
            assert briefs[0]["date"] > briefs[1]["date"]

    def test_list_briefs_extracts_score(self, briefs_dir, autopilot_module):
        """Test _list_briefs extracts readiness score from content."""
        autopilot = autopilot_module

        with patch.object(autopilot, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            briefs = autopilot._list_briefs("inst_test", days=30)

            # Today's brief has 75%
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_brief = next((b for b in briefs if b["date"] == today), None)
            assert today_brief is not None
            assert today_brief["readiness_score"] == 75

    def test_list_briefs_filters_by_days(self, briefs_dir, autopilot_module):
        """Test _list_briefs respects days parameter."""
        autopilot = autopilot_module

        # Create an old brief
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        briefs_path = briefs_dir / "inst_test" / "briefs"
        (briefs_path / f"{old_date}.md").write_text("# Old Brief\n**50%**")

        with patch.object(autopilot, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            # With 30 days, should not include old brief
            briefs = autopilot._list_briefs("inst_test", days=30)
            assert len(briefs) == 2

            # With 90 days, should include old brief
            briefs = autopilot._list_briefs("inst_test", days=90)
            assert len(briefs) == 3

    def test_list_briefs_empty_dir(self, tmp_path, autopilot_module):
        """Test _list_briefs returns empty for non-existent directory."""
        autopilot = autopilot_module

        with patch.object(autopilot, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            briefs = autopilot._list_briefs("nonexistent_inst", days=30)
            assert briefs == []

    def test_get_briefs_dir(self, tmp_path, autopilot_module):
        """Test _get_briefs_dir returns correct path."""
        autopilot = autopilot_module

        with patch.object(autopilot, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            path = autopilot._get_briefs_dir("inst_123")
            assert path == tmp_path / "inst_123" / "briefs"


class TestRunModels:
    """Tests for run creation and tracking."""

    def test_create_run_record(self, test_db):
        """Test creating a run record."""
        run = create_run("inst_test", TriggerType.MANUAL, test_db)

        assert run.id.startswith("apr_")
        assert run.institution_id == "inst_test"
        assert run.trigger_type == TriggerType.MANUAL
        assert run.status == RunStatus.PENDING

        # Verify persisted to DB
        cursor = test_db.execute(
            "SELECT * FROM autopilot_runs WHERE id = ?",
            (run.id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["institution_id"] == "inst_test"

    def test_autopilot_config_to_dict(self):
        """Test AutopilotConfig serialization."""
        config = AutopilotConfig(
            institution_id="inst_test",
            enabled=True,
            schedule_hour=3,
            run_audit=True,
        )

        data = config.to_dict()

        assert data["institution_id"] == "inst_test"
        assert data["enabled"] is True
        assert data["schedule_hour"] == 3
        assert data["run_audit"] is True
        assert data["run_reindex"] is True  # default

    def test_autopilot_run_to_dict(self):
        """Test AutopilotRun serialization."""
        run = AutopilotRun(
            id="apr_test",
            institution_id="inst_test",
            trigger_type=TriggerType.MANUAL,
            status=RunStatus.COMPLETED,
            docs_indexed=5,
            readiness_score_after=85,
        )

        data = run.to_dict()

        assert data["id"] == "apr_test"
        assert data["trigger_type"] == "manual"
        assert data["status"] == "completed"
        assert data["docs_indexed"] == 5
        assert data["readiness_score_after"] == 85


class TestEndpointURLs:
    """Tests to verify endpoint URL patterns are correctly defined."""

    def test_endpoint_functions_defined(self, autopilot_module):
        """Verify all expected route functions are defined."""
        autopilot = autopilot_module

        # Check expected functions exist
        expected_functions = [
            "get_config",
            "update_config",
            "trigger_run",
            "run_now",
            "stream_progress",
            "get_history",
            "get_latest",
            "get_run_details",
            "get_scheduler_status",
            "get_latest_brief",
            "list_briefs",
            "download_brief",
        ]

        for func_name in expected_functions:
            assert hasattr(autopilot, func_name), f"Function {func_name} not found in autopilot module"


class TestAPIIntegration:
    """Integration tests using Flask test client."""

    @pytest.fixture
    def app(self, autopilot_module):
        """Create test Flask app with autopilot blueprint."""
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(autopilot_module.autopilot_bp)

        return app

    def test_list_briefs_endpoint(self, app, briefs_dir, autopilot_module):
        """Test GET briefs list endpoint."""
        with patch.object(autopilot_module, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            with app.test_client() as client:
                response = client.get("/api/autopilot/institutions/inst_test/briefs?days=30")

                assert response.status_code == 200
                data = response.get_json()
                assert "briefs" in data
                assert data["total"] == 2
                assert data["days"] == 30

    def test_latest_brief_endpoint(self, app, briefs_dir, autopilot_module):
        """Test GET latest brief endpoint."""
        with patch.object(autopilot_module, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            with app.test_client() as client:
                response = client.get("/api/autopilot/institutions/inst_test/briefs/latest")

                assert response.status_code == 200
                data = response.get_json()
                assert "brief" in data
                assert "content" in data["brief"]
                assert "Morning Brief" in data["brief"]["content"]

    def test_latest_brief_not_found(self, app, tmp_path, autopilot_module):
        """Test GET latest brief returns 404 when none exist."""
        with patch.object(autopilot_module, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(tmp_path)

            with app.test_client() as client:
                response = client.get("/api/autopilot/institutions/nonexistent/briefs/latest")

                assert response.status_code == 404

    def test_download_brief_invalid_date(self, app, briefs_dir, autopilot_module):
        """Test download with invalid date format returns 400."""
        with patch.object(autopilot_module, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            with app.test_client() as client:
                response = client.get("/api/autopilot/institutions/inst_test/briefs/invalid-date/download")

                assert response.status_code == 400

    def test_download_brief_not_found(self, app, briefs_dir, autopilot_module):
        """Test download non-existent brief returns 404."""
        with patch.object(autopilot_module, "Config") as mock_config:
            mock_config.WORKSPACE_DIR = str(briefs_dir)

            with app.test_client() as client:
                response = client.get("/api/autopilot/institutions/inst_test/briefs/2020-01-01/download")

                assert response.status_code == 404

    def test_run_now_returns_202(self, app, autopilot_module):
        """Test POST run-now returns 202 Accepted."""
        mock_run = AutopilotRun(
            id="apr_test123",
            institution_id="inst_test",
            status=RunStatus.PENDING,
        )

        with patch.object(autopilot_module, "get_autopilot_config", return_value=None):
            with patch.object(autopilot_module, "create_run", return_value=mock_run):
                with patch.object(autopilot_module, "execute_autopilot_run", return_value=mock_run):
                    with app.test_client() as client:
                        response = client.post("/api/autopilot/institutions/inst_test/run-now")

                        assert response.status_code == 202
                        data = response.get_json()
                        assert data["run_id"] == "apr_test123"
                        assert data["status"] == "running"
