"""Agent system domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import SessionStatus, TaskPriority


@dataclass
class ToolCall:
    """Record of a tool invocation by an agent."""
    id: str = field(default_factory=lambda: generate_id("tc"))
    tool_name: str = ""
    input_params: Dict[str, Any] = field(default_factory=dict)
    output_result: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "input_params": self.input_params,
            "output_result": self.output_result,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=data.get("id", generate_id("tc")),
            tool_name=data.get("tool_name", ""),
            input_params=data.get("input_params", {}),
            output_result=data.get("output_result", {}),
            duration_ms=data.get("duration_ms", 0),
            success=data.get("success", True),
            error=data.get("error"),
            timestamp=data.get("timestamp", now_iso()),
        )


@dataclass
class HumanCheckpoint:
    """A point where human input is required."""
    id: str = field(default_factory=lambda: generate_id("cp"))
    session_id: str = ""
    task_id: Optional[str] = None
    agent: str = ""
    checkpoint_type: str = "approval"
    question: str = ""
    context: str = ""
    options: List[str] = field(default_factory=list)
    user_response: Optional[str] = None
    status: str = "pending"
    created_at: str = field(default_factory=now_iso)
    answered_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent": self.agent,
            "checkpoint_type": self.checkpoint_type,
            "question": self.question,
            "context": self.context,
            "options": self.options,
            "user_response": self.user_response,
            "status": self.status,
            "created_at": self.created_at,
            "answered_at": self.answered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanCheckpoint":
        return cls(
            id=data.get("id", generate_id("cp")),
            session_id=data.get("session_id", ""),
            task_id=data.get("task_id"),
            agent=data.get("agent", ""),
            checkpoint_type=data.get("checkpoint_type", "approval"),
            question=data.get("question", ""),
            context=data.get("context", ""),
            options=data.get("options", []),
            user_response=data.get("user_response"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", now_iso()),
            answered_at=data.get("answered_at"),
        )


@dataclass
class AgentTask:
    """A task for an agent to execute."""
    id: str = field(default_factory=lambda: generate_id("task"))
    session_id: str = ""
    name: str = ""
    description: str = ""
    agent: str = ""
    action: str = ""
    status: str = "pending"
    priority: TaskPriority = TaskPriority.NORMAL
    input_data: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    citations: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    ai_tokens_used: int = 0
    error: Optional[str] = None
    retries: int = 0
    requires_approval_before: bool = False
    requires_approval_after: bool = False
    depends_on: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "action": self.action,
            "status": self.status,
            "priority": self.priority.value,
            "input_data": self.input_data,
            "result": self.result,
            "confidence": self.confidence,
            "citations": self.citations,
            "duration_ms": self.duration_ms,
            "ai_tokens_used": self.ai_tokens_used,
            "error": self.error,
            "retries": self.retries,
            "requires_approval_before": self.requires_approval_before,
            "requires_approval_after": self.requires_approval_after,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        return cls(
            id=data.get("id", generate_id("task")),
            session_id=data.get("session_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            agent=data.get("agent", ""),
            action=data.get("action", ""),
            status=data.get("status", "pending"),
            priority=TaskPriority(data.get("priority", "normal")),
            input_data=data.get("input_data", {}),
            result=data.get("result", {}),
            confidence=data.get("confidence", 0.0),
            citations=data.get("citations", []),
            duration_ms=data.get("duration_ms", 0),
            ai_tokens_used=data.get("ai_tokens_used", 0),
            error=data.get("error"),
            retries=data.get("retries", 0),
            requires_approval_before=data.get("requires_approval_before", False),
            requires_approval_after=data.get("requires_approval_after", False),
            depends_on=data.get("depends_on", []),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class AgentSession:
    """A session tracking agent workflow execution."""
    id: str = field(default_factory=lambda: generate_id("sess"))
    agent_type: str = "orchestrator"
    institution_id: str = ""
    parent_session_id: Optional[str] = None
    orchestrator_request: str = ""
    status: SessionStatus = SessionStatus.PENDING
    agents_involved: List[str] = field(default_factory=list)
    tasks: List[AgentTask] = field(default_factory=list)
    checkpoints: List[HumanCheckpoint] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_api_calls: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "institution_id": self.institution_id,
            "parent_session_id": self.parent_session_id,
            "orchestrator_request": self.orchestrator_request,
            "status": self.status.value,
            "agents_involved": self.agents_involved,
            "tasks": [t.to_dict() for t in self.tasks],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "messages": self.messages,
            "artifacts_created": self.artifacts_created,
            "metadata": self.metadata,
            "current_task_id": self.current_task_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_api_calls": self.total_api_calls,
            "errors": self.errors,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSession":
        return cls(
            id=data.get("id", generate_id("sess")),
            agent_type=data.get("agent_type", "orchestrator"),
            institution_id=data.get("institution_id", ""),
            parent_session_id=data.get("parent_session_id"),
            orchestrator_request=data.get("orchestrator_request", ""),
            status=SessionStatus(data.get("status", "pending")),
            agents_involved=data.get("agents_involved", []),
            tasks=[AgentTask.from_dict(t) for t in data.get("tasks", [])],
            checkpoints=[HumanCheckpoint.from_dict(c) for c in data.get("checkpoints", [])],
            tool_calls=[ToolCall.from_dict(tc) for tc in data.get("tool_calls", [])],
            messages=data.get("messages", []),
            artifacts_created=data.get("artifacts_created", []),
            metadata=data.get("metadata", {}),
            current_task_id=data.get("current_task_id"),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_api_calls=data.get("total_api_calls", 0),
            errors=data.get("errors", []),
            last_error=data.get("last_error"),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    def add_task(self, task: AgentTask) -> None:
        """Add a task to the session."""
        task.session_id = self.id
        self.tasks.append(task)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call record to the session."""
        self.tool_calls.append(tool_call)

    def get_pending_tasks(self) -> List[AgentTask]:
        """Get tasks that are ready to execute."""
        completed_ids = {t.id for t in self.tasks if t.status == "completed"}
        pending = []
        for task in self.tasks:
            if task.status == "pending":
                # Check if all dependencies are complete
                if all(dep_id in completed_ids for dep_id in task.depends_on):
                    pending.append(task)
        return pending

    def request_approval(
        self,
        checkpoint_type: str,
        description: str,
        data: Dict[str, Any] = None
    ) -> HumanCheckpoint:
        """Create a human checkpoint for approval."""
        checkpoint = HumanCheckpoint(
            session_id=self.id,
            task_id=self.current_task_id,
            checkpoint_type=checkpoint_type,
            question=description,
            context=str(data) if data else "",
        )
        self.checkpoints.append(checkpoint)
        self.status = SessionStatus.WAITING_FOR_HUMAN
        return checkpoint


@dataclass
class ChatMessage:
    """A message in the chat interface."""
    id: str = field(default_factory=lambda: generate_id("msg"))
    session_id: Optional[str] = None
    institution_id: str = ""
    role: str = "user"
    message_type: str = "text"
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "institution_id": self.institution_id,
            "role": self.role,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "agent": self.agent,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            id=data.get("id", generate_id("msg")),
            session_id=data.get("session_id"),
            institution_id=data.get("institution_id", ""),
            role=data.get("role", "user"),
            message_type=data.get("message_type", "text"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            agent=data.get("agent"),
            timestamp=data.get("timestamp", now_iso()),
        )


@dataclass
class AgentResult:
    """Standardized result from any agent execution.

    All agents return this structure for consistent handling by the
    orchestrator and workflow engine.
    """
    status: str = "success"  # success, error, pending_approval
    confidence: float = 0.0  # 0.0-1.0, triggers checkpoint if < threshold
    citations: List[Dict[str, Any]] = field(default_factory=list)  # Evidence pointers
    artifacts: List[str] = field(default_factory=list)  # Paths to created files
    data: Dict[str, Any] = field(default_factory=dict)  # Agent-specific output
    human_checkpoint_required: bool = False
    checkpoint_reason: str = ""
    next_actions: List[Dict[str, Any]] = field(default_factory=list)  # Suggested follow-ups
    error: Optional[str] = None
    duration_ms: int = 0
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "citations": self.citations,
            "artifacts": self.artifacts,
            "data": self.data,
            "human_checkpoint_required": self.human_checkpoint_required,
            "checkpoint_reason": self.checkpoint_reason,
            "next_actions": self.next_actions,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        return cls(
            status=data.get("status", "success"),
            confidence=data.get("confidence", 0.0),
            citations=data.get("citations", []),
            artifacts=data.get("artifacts", []),
            data=data.get("data", {}),
            human_checkpoint_required=data.get("human_checkpoint_required", False),
            checkpoint_reason=data.get("checkpoint_reason", ""),
            next_actions=data.get("next_actions", []),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0),
            tokens_used=data.get("tokens_used", 0),
        )

    @classmethod
    def success(cls, data: Dict[str, Any], confidence: float = 1.0,
                citations: List[Dict[str, Any]] = None,
                artifacts: List[str] = None) -> "AgentResult":
        """Create a successful result."""
        return cls(
            status="success",
            confidence=confidence,
            citations=citations or [],
            artifacts=artifacts or [],
            data=data,
        )

    @classmethod
    def error(cls, message: str) -> "AgentResult":
        """Create an error result."""
        return cls(status="error", error=message)

    @classmethod
    def needs_approval(cls, reason: str, data: Dict[str, Any] = None) -> "AgentResult":
        """Create a result that requires human approval."""
        return cls(
            status="pending_approval",
            human_checkpoint_required=True,
            checkpoint_reason=reason,
            data=data or {},
        )
