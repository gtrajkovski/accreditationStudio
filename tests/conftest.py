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
from unittest.mock import MagicMock, patch


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
