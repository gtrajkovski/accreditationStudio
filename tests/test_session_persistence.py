"""Tests for AgentSession JSON round-trip serialization.

Verifies that fully populated AgentSession objects survive:
1. to_dict() -> JSON serialization -> JSON parsing -> from_dict()
2. Edge cases: empty sessions, unicode, 0 tool calls
"""

import json

from src.core.models import (
    AgentSession,
    AgentTask,
    HumanCheckpoint,
    ToolCall,
    SessionStatus,
    TaskPriority,
)


class TestSessionRoundTrip:
    """Test AgentSession JSON serialization round-trip."""

    def test_fully_populated_session_round_trip(self):
        """Verify all fields survive full round-trip."""
        # Build a fully populated session
        session = AgentSession(
            id="sess_test123",
            agent_type="orchestrator",
            institution_id="inst_abc",
            parent_session_id="sess_parent",
            orchestrator_request="Run compliance audit",
            status=SessionStatus.RUNNING,
            agents_involved=["orchestrator", "compliance_audit", "evidence_guardian"],
            artifacts_created=["audit_report.json", "findings.csv"],
            metadata={"current_stage": "COMPLIANCE_CHECK", "retry_count": 2},
            current_task_id="task_123",
            total_input_tokens=5000,
            total_output_tokens=3000,
            total_api_calls=15,
            errors=[{"type": "rate_limit", "message": "Retry succeeded"}],
            last_error=None,
            created_at="2024-01-15T10:00:00Z",
            started_at="2024-01-15T10:00:05Z",
            completed_at=None,
        )

        # Add tool calls
        session.tool_calls = [
            ToolCall(
                id="tc_001",
                tool_name="analyze_document",
                input_params={"document_id": "doc_123", "depth": "full"},
                output_result={"chunks": 45, "confidence": 0.92},
                duration_ms=1250,
                success=True,
                error=None,
                timestamp="2024-01-15T10:01:00Z",
            ),
            ToolCall(
                id="tc_002",
                tool_name="check_compliance",
                input_params={"standard_id": "ACCSC-5.2.1"},
                output_result={"status": "partial", "findings": 3},
                duration_ms=850,
                success=True,
                error=None,
                timestamp="2024-01-15T10:02:00Z",
            ),
        ]

        # Add checkpoints
        session.checkpoints = [
            HumanCheckpoint(
                id="cp_001",
                session_id="sess_test123",
                task_id="task_review",
                agent="compliance_audit",
                checkpoint_type="approval",
                question="Approve these findings?",
                context="Found 3 critical findings requiring attention.",
                options=["Approve", "Reject", "Request Changes"],
                user_response="Approve",
                status="answered",
                created_at="2024-01-15T10:05:00Z",
                answered_at="2024-01-15T10:07:00Z",
            ),
        ]

        # Add tasks
        session.tasks = [
            AgentTask(
                id="task_001",
                session_id="sess_test123",
                name="Document Analysis",
                description="Analyze uploaded documents for compliance",
                agent="ingestion",
                action="analyze",
                status="completed",
                priority=TaskPriority.HIGH,
                input_data={"document_ids": ["doc_1", "doc_2"]},
                result={"analyzed": 2, "issues": 0},
                confidence=0.95,
                citations=[{"doc_id": "doc_1", "page": 5}],
                duration_ms=5000,
                ai_tokens_used=1500,
                error=None,
                retries=0,
                requires_approval_before=False,
                requires_approval_after=True,
                depends_on=[],
                created_at="2024-01-15T10:00:10Z",
                started_at="2024-01-15T10:00:15Z",
                completed_at="2024-01-15T10:01:00Z",
            ),
        ]

        # Add messages
        session.messages = [
            {"role": "user", "content": "Run compliance audit for ACCSC"},
            {"role": "assistant", "content": "Starting compliance audit..."},
            {"role": "tool_use", "tool": "analyze_document", "id": "tc_001"},
        ]

        # Round-trip: to_dict -> JSON -> from_dict
        session_dict = session.to_dict()
        json_str = json.dumps(session_dict)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        # Verify all fields survive
        assert restored.id == session.id
        assert restored.agent_type == session.agent_type
        assert restored.institution_id == session.institution_id
        assert restored.parent_session_id == session.parent_session_id
        assert restored.orchestrator_request == session.orchestrator_request
        assert restored.status == session.status
        assert restored.agents_involved == session.agents_involved
        assert restored.artifacts_created == session.artifacts_created
        assert restored.metadata == session.metadata
        assert restored.current_task_id == session.current_task_id
        assert restored.total_input_tokens == session.total_input_tokens
        assert restored.total_output_tokens == session.total_output_tokens
        assert restored.total_api_calls == session.total_api_calls
        assert restored.errors == session.errors
        assert restored.last_error == session.last_error
        assert restored.created_at == session.created_at
        assert restored.started_at == session.started_at
        assert restored.completed_at == session.completed_at
        assert restored.messages == session.messages

        # Verify nested objects
        assert len(restored.tool_calls) == 2
        assert restored.tool_calls[0].tool_name == "analyze_document"
        assert restored.tool_calls[0].input_params == {"document_id": "doc_123", "depth": "full"}
        assert restored.tool_calls[0].output_result == {"chunks": 45, "confidence": 0.92}
        assert restored.tool_calls[0].duration_ms == 1250

        assert len(restored.checkpoints) == 1
        assert restored.checkpoints[0].question == "Approve these findings?"
        assert restored.checkpoints[0].user_response == "Approve"
        assert restored.checkpoints[0].status == "answered"

        assert len(restored.tasks) == 1
        assert restored.tasks[0].name == "Document Analysis"
        assert restored.tasks[0].priority == TaskPriority.HIGH
        assert restored.tasks[0].confidence == 0.95

    def test_empty_session_round_trip(self):
        """Verify empty session survives round-trip."""
        session = AgentSession()

        session_dict = session.to_dict()
        json_str = json.dumps(session_dict)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        assert restored.id == session.id
        assert restored.status == SessionStatus.PENDING
        assert restored.tool_calls == []
        assert restored.checkpoints == []
        assert restored.tasks == []
        assert restored.messages == []
        assert restored.total_input_tokens == 0

    def test_unicode_content_round_trip(self):
        """Verify unicode characters survive round-trip."""
        session = AgentSession(
            id="sess_unicode",
            institution_id="inst_español",
            orchestrator_request="审查合规性 🎓 Prüfung",
            metadata={"note": "日本語テスト", "emoji": "✅🚀💡"},
        )

        session.messages = [
            {"role": "user", "content": "Revisar el catálogo de la institución"},
            {"role": "assistant", "content": "Iniciando revisión... 📚"},
        ]

        session_dict = session.to_dict()
        json_str = json.dumps(session_dict, ensure_ascii=False)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        assert restored.institution_id == "inst_español"
        assert "审查合规性" in restored.orchestrator_request
        assert "🎓" in restored.orchestrator_request
        assert restored.metadata["note"] == "日本語テスト"
        assert restored.metadata["emoji"] == "✅🚀💡"
        assert "📚" in restored.messages[1]["content"]

    def test_zero_tool_calls_round_trip(self):
        """Verify session with 0 tool calls survives."""
        session = AgentSession(
            id="sess_notool",
            status=SessionStatus.COMPLETED,
            total_api_calls=1,
        )
        # Explicitly empty
        session.tool_calls = []

        session_dict = session.to_dict()
        json_str = json.dumps(session_dict)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        assert restored.tool_calls == []
        assert restored.total_api_calls == 1

    def test_failed_tool_call_round_trip(self):
        """Verify failed tool calls with errors survive."""
        session = AgentSession(id="sess_error")
        session.tool_calls = [
            ToolCall(
                id="tc_fail",
                tool_name="validate_evidence",
                input_params={"finding_id": "f_123"},
                output_result={},
                duration_ms=50,
                success=False,
                error="Document not found: doc_missing",
                timestamp="2024-01-15T10:00:00Z",
            ),
        ]
        session.last_error = "Tool execution failed"
        session.errors = [
            {"type": "tool_error", "tool": "validate_evidence", "message": "Document not found"}
        ]

        session_dict = session.to_dict()
        json_str = json.dumps(session_dict)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        assert restored.tool_calls[0].success is False
        assert "Document not found" in restored.tool_calls[0].error
        assert restored.last_error == "Tool execution failed"
        assert len(restored.errors) == 1

    def test_all_session_statuses_round_trip(self):
        """Verify all SessionStatus values survive round-trip."""
        for status in SessionStatus:
            session = AgentSession(id=f"sess_{status.value}", status=status)

            session_dict = session.to_dict()
            json_str = json.dumps(session_dict)
            loaded_dict = json.loads(json_str)
            restored = AgentSession.from_dict(loaded_dict)

            assert restored.status == status, f"Status {status} did not survive round-trip"

    def test_nested_metadata_round_trip(self):
        """Verify deeply nested metadata survives."""
        session = AgentSession(
            id="sess_nested",
            metadata={
                "level1": {
                    "level2": {
                        "level3": {"value": 123, "list": [1, 2, 3]},
                    },
                    "array": [{"key": "val"}, {"key": "val2"}],
                },
                "null_value": None,
                "bool_true": True,
                "bool_false": False,
                "float_val": 3.14159,
            },
        )

        session_dict = session.to_dict()
        json_str = json.dumps(session_dict)
        loaded_dict = json.loads(json_str)
        restored = AgentSession.from_dict(loaded_dict)

        assert restored.metadata["level1"]["level2"]["level3"]["value"] == 123
        assert restored.metadata["level1"]["level2"]["level3"]["list"] == [1, 2, 3]
        assert restored.metadata["null_value"] is None
        assert restored.metadata["bool_true"] is True
        assert restored.metadata["bool_false"] is False
        assert restored.metadata["float_val"] == 3.14159
