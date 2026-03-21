"""Tests for AuditTrailService."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from src.services.audit_trail_service import AuditTrailService


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test sessions."""
    inst_id = "inst_test123"
    sessions_dir = tmp_path / inst_id / "agent_sessions"
    sessions_dir.mkdir(parents=True)

    # Create test sessions
    sessions = [
        {
            "id": "sess_001",
            "agent_type": "compliance_audit",
            "created_at": "2026-03-15T10:00:00Z",
            "status": "completed",
            "tool_calls": [{"name": "audit_document", "input": {}}],
            "metadata": {"operation": "full_audit"},
        },
        {
            "id": "sess_002",
            "agent_type": "remediation",
            "created_at": "2026-03-16T14:30:00Z",
            "status": "completed",
            "tool_calls": [{"name": "apply_fix", "input": {}}],
            "metadata": {"operation": "auto_fix"},
        },
        {
            "id": "sess_003",
            "agent_type": "compliance_audit",
            "created_at": "2026-03-20T08:00:00Z",
            "status": "completed",
            "tool_calls": [{"name": "audit_document", "input": {}}],
            "metadata": {"operation": "quick_check"},
        },
    ]

    for session in sessions:
        session_file = sessions_dir / f"{session['id']}.json"
        with open(session_file, "w") as f:
            json.dump(session, f)

    return tmp_path, inst_id


def test_query_sessions_returns_empty_when_no_sessions(tmp_path):
    """Test query_sessions returns empty list for nonexistent institution."""
    inst_id = "nonexistent_inst"
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        workspace_dir=tmp_path
    )
    assert result == []


def test_query_sessions_returns_all_without_filters(temp_workspace):
    """Test query_sessions returns all sessions when no filters."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        workspace_dir=tmp_path
    )
    assert len(result) == 3
    # Should be sorted by created_at descending
    assert result[0]["id"] == "sess_003"
    assert result[1]["id"] == "sess_002"
    assert result[2]["id"] == "sess_001"


def test_query_sessions_filters_by_start_date(temp_workspace):
    """Test query_sessions filters by start_date inclusive."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        start_date="2026-03-16T00:00:00Z",
        workspace_dir=tmp_path
    )
    assert len(result) == 2
    ids = [s["id"] for s in result]
    assert "sess_002" in ids
    assert "sess_003" in ids
    assert "sess_001" not in ids


def test_query_sessions_filters_by_end_date(temp_workspace):
    """Test query_sessions filters by end_date inclusive."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        end_date="2026-03-16T23:59:59Z",
        workspace_dir=tmp_path
    )
    assert len(result) == 2
    ids = [s["id"] for s in result]
    assert "sess_001" in ids
    assert "sess_002" in ids
    assert "sess_003" not in ids


def test_query_sessions_filters_by_agent_type(temp_workspace):
    """Test query_sessions filters by agent_type."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        agent_type="compliance_audit",
        workspace_dir=tmp_path
    )
    assert len(result) == 2
    for s in result:
        assert s["agent_type"] == "compliance_audit"


def test_query_sessions_filters_by_operation(temp_workspace):
    """Test query_sessions filters by operation in metadata."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        operation="full_audit",
        workspace_dir=tmp_path
    )
    assert len(result) == 1
    assert result[0]["id"] == "sess_001"


def test_query_sessions_combined_filters(temp_workspace):
    """Test query_sessions with multiple filters."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        agent_type="compliance_audit",
        start_date="2026-03-17T00:00:00Z",
        workspace_dir=tmp_path
    )
    assert len(result) == 1
    assert result[0]["id"] == "sess_003"


def test_session_includes_tool_calls(temp_workspace):
    """Test that exported sessions include tool_calls."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.query_sessions(
        institution_id=inst_id,
        workspace_dir=tmp_path
    )
    for session in result:
        assert "tool_calls" in session
        assert isinstance(session["tool_calls"], list)


def test_get_session_returns_single_session(temp_workspace):
    """Test get_session returns a single session by ID."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.get_session(
        institution_id=inst_id,
        session_id="sess_001",
        workspace_dir=tmp_path
    )
    assert result is not None
    assert result["id"] == "sess_001"


def test_get_session_returns_none_for_nonexistent(temp_workspace):
    """Test get_session returns None for nonexistent session."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.get_session(
        institution_id=inst_id,
        session_id="nonexistent",
        workspace_dir=tmp_path
    )
    assert result is None


def test_get_agent_types(temp_workspace):
    """Test get_agent_types returns unique agent types."""
    tmp_path, inst_id = temp_workspace
    result = AuditTrailService.get_agent_types(
        institution_id=inst_id,
        workspace_dir=tmp_path
    )
    assert "compliance_audit" in result
    assert "remediation" in result
    assert len(result) == 2
