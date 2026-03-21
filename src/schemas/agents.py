"""Agent session schemas for API documentation.

These schemas document the request/response formats for:
- GET /api/agents/sessions (list sessions)
- GET /api/agents/sessions/{id} (get session)
- POST /api/agents/sessions/{id}/tasks (add task)
"""

from marshmallow import Schema, fields, validate


class TaskSchema(Schema):
    """Schema for an agent task."""

    id = fields.Str(
        metadata={
            "description": "Task ID",
            "example": "task_001"
        }
    )
    description = fields.Str(
        metadata={
            "description": "Task description",
            "example": "Audit document for ACCSC Section III compliance"
        }
    )
    status = fields.Str(
        validate=validate.OneOf(["pending", "running", "completed", "failed", "cancelled"]),
        metadata={
            "description": "Task execution status",
            "example": "completed"
        }
    )
    result = fields.Dict(
        metadata={
            "description": "Task result data",
            "example": {"findings": 3, "compliant": True}
        }
    )
    started_at = fields.Str(
        metadata={
            "description": "ISO 8601 start timestamp",
            "example": "2026-03-21T10:30:00Z"
        }
    )
    completed_at = fields.Str(
        metadata={
            "description": "ISO 8601 completion timestamp",
            "example": "2026-03-21T10:35:00Z"
        }
    )


class AgentSessionSchema(Schema):
    """Full agent session schema."""

    id = fields.Str(
        metadata={
            "description": "Session ID",
            "example": "sess_abc123def456"
        }
    )
    agent_type = fields.Str(
        validate=validate.OneOf([
            "ORCHESTRATOR", "COMPLIANCE_AUDIT", "REMEDIATION",
            "CONSISTENCY", "EVIDENCE_GUARDIAN", "DOCUMENT_INTAKE",
            "STANDARDS_CURATOR", "FINDINGS", "NARRATIVE", "PACKET",
            "CHECKLIST", "FACULTY", "CATALOG", "EVIDENCE",
            "ACHIEVEMENT", "INTERVIEW_PREP", "SER", "TEAM_RESPONSE",
            "CALENDAR", "DOCUMENT_REVIEW", "KNOWLEDGE_GRAPH",
            "SIMULATION", "WORKFLOW_COACH", "LOCALIZATION_QA"
        ]),
        metadata={
            "description": "Type of AI agent",
            "example": "COMPLIANCE_AUDIT"
        }
    )
    institution_id = fields.Str(
        metadata={
            "description": "Institution this session belongs to",
            "example": "inst_xyz789"
        }
    )
    status = fields.Str(
        validate=validate.OneOf([
            "pending", "running", "completed", "failed",
            "cancelled", "waiting_for_human", "paused"
        ]),
        metadata={
            "description": "Session status",
            "example": "running"
        }
    )
    tasks = fields.List(
        fields.Nested(TaskSchema),
        metadata={
            "description": "Tasks in this session"
        }
    )
    total_tokens = fields.Int(
        metadata={
            "description": "Total tokens consumed",
            "example": 15000
        }
    )
    created_at = fields.Str(
        metadata={
            "description": "ISO 8601 creation timestamp",
            "example": "2026-03-21T10:30:00Z"
        }
    )
    updated_at = fields.Str(
        metadata={
            "description": "ISO 8601 last update timestamp",
            "example": "2026-03-21T10:45:00Z"
        }
    )


class AgentSessionListSchema(Schema):
    """Response schema for listing agent sessions."""

    sessions = fields.List(
        fields.Nested(AgentSessionSchema),
        metadata={
            "description": "List of agent sessions"
        }
    )


class TaskCreateSchema(Schema):
    """Schema for adding a task to a session."""

    description = fields.Str(
        required=True,
        metadata={
            "description": "Task description",
            "example": "Audit catalog section for compliance"
        }
    )
    priority = fields.Int(
        load_default=0,
        validate=validate.Range(min=0, max=10),
        metadata={
            "description": "Task priority (0=normal, 10=highest)",
            "example": 5
        }
    )
