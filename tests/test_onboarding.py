"""Tests for onboarding wizard service and API.

Tests cover:
- Onboarding progress CRUD
- Step completion flow
- Skip functionality
- should_show_onboarding logic
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock

from src.services import onboarding_service
from src.db.connection import get_conn


@pytest.fixture
def test_db():
    """Create in-memory database with required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create required tables
    conn.executescript("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            institution_id TEXT
        );

        CREATE TABLE onboarding_progress (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL UNIQUE,
            current_step INTEGER NOT NULL DEFAULT 1,
            completed INTEGER NOT NULL DEFAULT 0,
            profile_complete INTEGER NOT NULL DEFAULT 0,
            documents_uploaded INTEGER NOT NULL DEFAULT 0,
            initial_audit_run INTEGER NOT NULL DEFAULT 0,
            review_complete INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (institution_id) REFERENCES institutions(id)
        );
    """)

    # Insert test data
    conn.execute("INSERT INTO institutions (id, name) VALUES ('inst_001', 'Test Institute')")
    conn.execute("INSERT INTO users (id, institution_id) VALUES ('user_001', 'inst_001')")
    conn.commit()

    yield conn
    conn.close()


class TestStartOnboarding:
    """Tests for start_onboarding function."""

    def test_creates_progress_record(self, test_db):
        """Start onboarding creates a new progress record."""
        result = onboarding_service.start_onboarding("inst_001", conn=test_db)

        assert result["institution_id"] == "inst_001"
        assert result["current_step"] == 1
        assert result["completed"] is False
        assert result["profile_complete"] is False

    def test_returns_existing_record(self, test_db):
        """Start onboarding returns existing record if already started."""
        # Start once
        first = onboarding_service.start_onboarding("inst_001", conn=test_db)

        # Start again - should return same record
        second = onboarding_service.start_onboarding("inst_001", conn=test_db)

        assert first["id"] == second["id"]

    def test_generates_unique_id(self, test_db):
        """Each progress record gets a unique ID."""
        result = onboarding_service.start_onboarding("inst_001", conn=test_db)

        assert result["id"].startswith("onb_")
        assert len(result["id"]) > 4


class TestUpdateStep:
    """Tests for update_step function."""

    def test_advances_to_next_step(self, test_db):
        """Completing a step advances current_step."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        result = onboarding_service.update_step("inst_001", 1, conn=test_db)

        assert result["current_step"] == 2
        assert result["profile_complete"] is True

    def test_marks_step_complete_flag(self, test_db):
        """Each step sets its corresponding completion flag."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        # Complete step 1
        result = onboarding_service.update_step("inst_001", 1, conn=test_db)
        assert result["profile_complete"] is True
        assert result["documents_uploaded"] is False

        # Complete step 2
        result = onboarding_service.update_step("inst_001", 2, conn=test_db)
        assert result["documents_uploaded"] is True
        assert result["initial_audit_run"] is False

    def test_step_4_marks_completed(self, test_db):
        """Completing step 4 sets completed=True."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        # Complete all steps
        for step in range(1, 5):
            result = onboarding_service.update_step("inst_001", step, conn=test_db)

        assert result["completed"] is True
        assert result["review_complete"] is True

    def test_invalid_step_raises_error(self, test_db):
        """Invalid step number raises ValueError."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        with pytest.raises(ValueError, match="Invalid step"):
            onboarding_service.update_step("inst_001", 5, conn=test_db)

    def test_starts_onboarding_if_not_started(self, test_db):
        """Updating step for new institution starts onboarding first."""
        # Don't call start_onboarding first
        test_db.execute("INSERT INTO institutions (id, name) VALUES ('inst_002', 'Another Institute')")
        test_db.commit()

        result = onboarding_service.update_step("inst_002", 1, conn=test_db)

        assert result["institution_id"] == "inst_002"
        assert result["profile_complete"] is True


class TestGetProgress:
    """Tests for get_progress function."""

    def test_returns_progress_dict(self, test_db):
        """Get progress returns formatted dict."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        result = onboarding_service.get_progress("inst_001", conn=test_db)

        assert "id" in result
        assert "institution_id" in result
        assert "current_step" in result
        assert "completed" in result
        assert isinstance(result["completed"], bool)

    def test_returns_none_if_not_started(self, test_db):
        """Get progress returns None for institutions without onboarding."""
        test_db.execute("INSERT INTO institutions (id, name) VALUES ('inst_new', 'New Institute')")
        test_db.commit()

        result = onboarding_service.get_progress("inst_new", conn=test_db)

        assert result is None


class TestIsOnboardingComplete:
    """Tests for is_onboarding_complete function."""

    def test_returns_false_if_not_started(self, test_db):
        """Returns False if onboarding not started."""
        test_db.execute("INSERT INTO institutions (id, name) VALUES ('inst_new', 'New')")
        test_db.commit()

        result = onboarding_service.is_onboarding_complete("inst_new", conn=test_db)

        assert result is False

    def test_returns_false_if_in_progress(self, test_db):
        """Returns False if onboarding started but not complete."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)
        onboarding_service.update_step("inst_001", 1, conn=test_db)

        result = onboarding_service.is_onboarding_complete("inst_001", conn=test_db)

        assert result is False

    def test_returns_true_if_completed(self, test_db):
        """Returns True if all steps completed."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)
        for step in range(1, 5):
            onboarding_service.update_step("inst_001", step, conn=test_db)

        result = onboarding_service.is_onboarding_complete("inst_001", conn=test_db)

        assert result is True


class TestShouldShowOnboarding:
    """Tests for should_show_onboarding function."""

    def test_returns_false_for_user_without_institution(self, test_db):
        """Users without institution don't see onboarding."""
        test_db.execute("INSERT INTO users (id, institution_id) VALUES ('user_new', NULL)")
        test_db.commit()

        result = onboarding_service.should_show_onboarding("user_new", conn=test_db)

        assert result is False

    def test_returns_true_for_incomplete_onboarding(self, test_db):
        """Users with incomplete onboarding should see wizard."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        result = onboarding_service.should_show_onboarding("user_001", conn=test_db)

        assert result is True

    def test_returns_false_for_completed_onboarding(self, test_db):
        """Users with completed onboarding don't see wizard."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)
        for step in range(1, 5):
            onboarding_service.update_step("inst_001", step, conn=test_db)

        result = onboarding_service.should_show_onboarding("user_001", conn=test_db)

        assert result is False

    def test_returns_false_for_nonexistent_user(self, test_db):
        """Nonexistent users don't see onboarding."""
        result = onboarding_service.should_show_onboarding("user_fake", conn=test_db)

        assert result is False


class TestSkipOnboarding:
    """Tests for skip_onboarding function."""

    def test_marks_onboarding_complete(self, test_db):
        """Skip sets completed=True."""
        onboarding_service.start_onboarding("inst_001", conn=test_db)

        result = onboarding_service.skip_onboarding("inst_001", conn=test_db)

        assert result["completed"] is True
        assert result["current_step"] == 4

    def test_starts_onboarding_if_needed(self, test_db):
        """Skip starts onboarding first if not started."""
        test_db.execute("INSERT INTO institutions (id, name) VALUES ('inst_skip', 'Skip')")
        test_db.commit()

        result = onboarding_service.skip_onboarding("inst_skip", conn=test_db)

        assert result["completed"] is True

    def test_skipped_users_dont_see_onboarding(self, test_db):
        """After skip, should_show_onboarding returns False."""
        onboarding_service.skip_onboarding("inst_001", conn=test_db)

        result = onboarding_service.should_show_onboarding("user_001", conn=test_db)

        assert result is False


class TestOnboardingAPI:
    """Tests for onboarding API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app

        app.config['TESTING'] = True
        app.config['AUTH_ENABLED'] = False

        with app.test_client() as client:
            yield client

    def test_invalid_step_returns_400(self, client):
        """POST /step/5 returns 400 for invalid step."""
        response = client.post('/api/onboarding/step/5?institution_id=inst_test')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_missing_institution_returns_400(self, client):
        """Endpoints without institution_id return 400."""
        response = client.get('/api/onboarding/progress')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_check_endpoint_returns_should_show(self, client):
        """GET /check returns should_show boolean."""
        response = client.get('/api/onboarding/check')

        assert response.status_code == 200
        data = response.get_json()
        assert 'should_show' in data
        assert isinstance(data['should_show'], bool)
