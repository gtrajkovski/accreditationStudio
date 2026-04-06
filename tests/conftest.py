"""Pytest configuration for AccreditAI tests.

This module sets up the Python path and provides common fixtures.
"""

import sys
from pathlib import Path

# Add project root to Python path so 'src' imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import tempfile
import sqlite3
import os
from unittest.mock import MagicMock, patch

# Global test database path - set per session
_TEST_DB_PATH = None


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(tmp_path_factory):
    """Create a session-wide test database with proper isolation.

    This fixture:
    1. Creates a temp database file for the entire test session
    2. Patches get_db_path to return the test database
    3. Applies all migrations once
    4. Enables WAL mode for better concurrent access
    """
    global _TEST_DB_PATH

    # Create temp directory for test database
    test_dir = tmp_path_factory.mktemp("test_db")
    _TEST_DB_PATH = test_dir / "test_accreditai.db"

    # Patch the config and connection module
    import src.db.connection as conn_module
    original_get_db_path = conn_module.get_db_path

    def test_get_db_path():
        return _TEST_DB_PATH

    conn_module.get_db_path = test_get_db_path

    # Apply migrations to the test database
    from src.db.migrate import apply_migrations
    apply_migrations()

    # Enable WAL mode for better concurrent access
    conn = sqlite3.connect(str(_TEST_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.close()

    yield _TEST_DB_PATH

    # Restore original function (cleanup)
    conn_module.get_db_path = original_get_db_path


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn

    conn.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client for agent tests."""
    with patch("src.agents.base_agent.Anthropic") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client

        # Default successful response
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Test response")],
            usage=MagicMock(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

        yield mock_client


@pytest.fixture
def sample_institution():
    """Return a sample institution dict for testing."""
    return {
        "id": "inst_test123",
        "name": "Test University",
        "accreditor_code": "ACCSC",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_document():
    """Return a sample document dict for testing."""
    return {
        "id": "doc_test123",
        "institution_id": "inst_test123",
        "filename": "test_policy.pdf",
        "doc_type": "policy",
        "status": "indexed",
        "created_at": "2024-01-01T00:00:00Z"
    }
