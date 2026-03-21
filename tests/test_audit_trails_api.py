"""Integration tests for Audit Trails API endpoints."""

import json
import pytest
from pathlib import Path
from app import app
from src.core.workspace import WorkspaceManager


@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create temporary workspace with test sessions."""
    # Set workspace directory
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))

    # Create institution and sessions
    inst_id = "inst_testapi"
    sessions_dir = tmp_path / inst_id / "agent_sessions"
    sessions_dir.mkdir(parents=True)

    # Create institution.json (required for valid workspace)
    inst_file = tmp_path / inst_id / "institution.json"
    with open(inst_file, "w") as f:
        json.dump({"id": inst_id, "name": "Test Institution"}, f)

    # Create test sessions
    sessions = [
        {
            "id": "api_sess_001",
            "agent_type": "compliance_audit",
            "created_at": "2026-03-15T10:00:00Z",
            "status": "completed",
            "tool_calls": [
                {"name": "audit_document", "input": {"doc_id": "doc_123"}},
                {"name": "generate_finding", "input": {"severity": "high"}}
            ],
            "metadata": {"operation": "full_audit", "confidence": 0.85},
            "total_tokens": 1500,
        },
        {
            "id": "api_sess_002",
            "agent_type": "remediation",
            "created_at": "2026-03-20T14:30:00Z",
            "status": "completed",
            "tool_calls": [{"name": "apply_fix", "input": {}}],
            "metadata": {"operation": "auto_fix", "confidence": 0.92},
            "total_tokens": 800,
        },
    ]

    for session in sessions:
        session_file = sessions_dir / f"{session['id']}.json"
        with open(session_file, "w") as f:
            json.dump(session, f)

    return tmp_path, inst_id


def test_list_sessions_returns_all(client, temp_workspace):
    """Test GET /sessions returns all sessions."""
    _, inst_id = temp_workspace
    response = client.get(f"/api/audit-trails/institutions/{inst_id}/sessions")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 2
    assert len(data["sessions"]) == 2


def test_list_sessions_with_agent_type_filter(client, temp_workspace):
    """Test GET /sessions filters by agent_type."""
    _, inst_id = temp_workspace
    response = client.get(
        f"/api/audit-trails/institutions/{inst_id}/sessions",
        query_string={"agent_type": "compliance_audit"}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["sessions"][0]["agent_type"] == "compliance_audit"


def test_list_sessions_with_date_range(client, temp_workspace):
    """Test GET /sessions filters by date range."""
    _, inst_id = temp_workspace
    response = client.get(
        f"/api/audit-trails/institutions/{inst_id}/sessions",
        query_string={
            "start_date": "2026-03-18T00:00:00Z",
            "end_date": "2026-03-21T00:00:00Z"
        }
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 1
    assert data["sessions"][0]["id"] == "api_sess_002"


def test_get_single_session(client, temp_workspace):
    """Test GET /sessions/:id returns single session."""
    _, inst_id = temp_workspace
    response = client.get(
        f"/api/audit-trails/institutions/{inst_id}/sessions/api_sess_001"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["session"]["id"] == "api_sess_001"
    assert "tool_calls" in data["session"]


def test_get_session_not_found(client, temp_workspace):
    """Test GET /sessions/:id returns 404 for nonexistent."""
    _, inst_id = temp_workspace
    response = client.get(
        f"/api/audit-trails/institutions/{inst_id}/sessions/nonexistent"
    )

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False


def test_get_agent_types(client, temp_workspace):
    """Test GET /agent-types returns unique types."""
    _, inst_id = temp_workspace
    response = client.get(
        f"/api/audit-trails/institutions/{inst_id}/agent-types"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "compliance_audit" in data["agent_types"]
    assert "remediation" in data["agent_types"]


def test_export_json(client, temp_workspace):
    """Test POST /export returns JSON file."""
    _, inst_id = temp_workspace
    response = client.post(
        f"/api/audit-trails/institutions/{inst_id}/export",
        json={}
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert "attachment" in response.headers.get("Content-Disposition", "")

    # Parse response as JSON
    export_data = json.loads(response.data)
    assert export_data["institution_id"] == inst_id
    assert export_data["session_count"] == 2
    assert "sessions" in export_data
    assert "exported_at" in export_data


def test_export_json_with_filters(client, temp_workspace):
    """Test POST /export applies filters."""
    _, inst_id = temp_workspace
    response = client.post(
        f"/api/audit-trails/institutions/{inst_id}/export",
        json={"agent_type": "remediation"}
    )

    assert response.status_code == 200
    export_data = json.loads(response.data)
    assert export_data["session_count"] == 1
    assert export_data["sessions"][0]["agent_type"] == "remediation"
    assert export_data["filters"]["agent_type"] == "remediation"


def test_export_includes_tool_calls(client, temp_workspace):
    """Test exported sessions include tool_calls (AUD-04)."""
    _, inst_id = temp_workspace
    response = client.post(
        f"/api/audit-trails/institutions/{inst_id}/export",
        json={}
    )

    export_data = json.loads(response.data)
    for session in export_data["sessions"]:
        assert "tool_calls" in session
        assert isinstance(session["tool_calls"], list)
        assert "created_at" in session
        assert "metadata" in session


def test_export_includes_timestamps_and_confidence(client, temp_workspace):
    """Test exported sessions include timestamps and confidence (AUD-04)."""
    _, inst_id = temp_workspace
    response = client.post(
        f"/api/audit-trails/institutions/{inst_id}/export",
        json={}
    )

    export_data = json.loads(response.data)
    for session in export_data["sessions"]:
        assert "created_at" in session
        # Confidence is in metadata
        assert "metadata" in session
        assert "confidence" in session["metadata"]
