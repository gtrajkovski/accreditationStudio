"""Base agent class with Claude API integration.

Provides common functionality for all agents including:
- Claude API communication with tool use
- Session state management
- Token tracking
- Error handling with retries
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Generator
from datetime import datetime
from enum import Enum

from anthropic import Anthropic

from src.config import Config
from src.core.models import (
    AgentSession,
    AgentTask,
    SessionStatus,
    ToolCall,
    HumanCheckpoint,
)


class AgentType(Enum):
    """Types of specialized agents in the system (24 total).

    Tier 0 - Runtime & Governance:
        ORCHESTRATOR, POLICY_SAFETY, EVIDENCE_GUARDIAN
    Tier 1 - Intake, Organization & Retrieval:
        DOCUMENT_INTAKE, PARSING_STRUCTURE, PII_REDACTION, RETRIEVAL_TUNING
    Tier 2 - Standards & Regulatory Stack:
        STANDARDS_CURATOR, REGULATORY_STACK, STANDARDS_TRANSLATOR
    Tier 3 - Compliance Analysis & Quality:
        COMPLIANCE_AUDIT, CONSISTENCY, RISK_SCORER, GAP_FINDER
    Tier 4 - Remediation & Authoring:
        REMEDIATION, POLICY_AUTHOR, EXHIBIT_BUILDER, CHANGE_IMPACT
    Tier 5 - Submission & Audit Defense:
        NARRATIVE, CROSSWALK, PACKET, SITE_VISIT_COACH
    Tier 6 - Product Experience:
        WORKFLOW_COACH, LOCALIZATION_QA
    """
    # Tier 0 - Runtime & Governance
    ORCHESTRATOR = "orchestrator"
    POLICY_SAFETY = "policy_safety"
    EVIDENCE_GUARDIAN = "evidence_guardian"

    # Tier 1 - Intake, Organization & Retrieval
    DOCUMENT_INTAKE = "document_intake"
    INGESTION = "ingestion"  # Legacy alias for DOCUMENT_INTAKE
    PARSING_STRUCTURE = "parsing_structure"
    PII_REDACTION = "pii_redaction"
    RETRIEVAL_TUNING = "retrieval_tuning"

    # Tier 2 - Standards & Regulatory Stack
    STANDARDS_CURATOR = "standards_curator"
    STANDARDS_LIBRARIAN = "standards_librarian"  # Legacy alias
    REGULATORY_STACK = "regulatory_stack"
    STANDARDS_TRANSLATOR = "standards_translator"

    # Tier 3 - Compliance Analysis & Quality
    COMPLIANCE_AUDIT = "compliance_audit"
    CONSISTENCY = "consistency"
    POLICY_CONSISTENCY = "policy_consistency"  # Legacy alias
    RISK_SCORER = "risk_scorer"
    GAP_FINDER = "gap_finder"

    # Tier 4 - Remediation & Authoring
    REMEDIATION = "remediation"
    POLICY_AUTHOR = "policy_author"
    EXHIBIT_BUILDER = "exhibit_builder"
    CHANGE_IMPACT = "change_impact"
    TRUTH_INDEX_CURATOR = "truth_index_curator"  # Legacy
    SUBSTANTIVE_CHANGE = "substantive_change"  # Legacy alias

    # Tier 5 - Submission & Audit Defense
    NARRATIVE = "narrative"
    CROSSWALK = "crosswalk"
    CROSSWALK_BUILDER = "crosswalk_builder"  # Legacy alias
    PACKET = "packet"
    PACKET_ASSEMBLER = "packet_assembler"  # Legacy alias
    SITE_VISIT_COACH = "site_visit_coach"
    SITE_VISIT_PREP = "site_visit_prep"  # Legacy alias

    # Tier 6 - Product Experience
    WORKFLOW_COACH = "workflow_coach"
    LOCALIZATION_QA = "localization_qa"
    CALENDAR_DEADLINE = "calendar_deadline"  # Legacy
    EVIDENCE_MAPPER = "evidence_mapper"  # Legacy


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Provides Claude API integration, tool execution, and session management.
    Subclasses implement specific agent behavior via the tools and prompts.
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update: Optional[Callable[[AgentSession], None]] = None,
    ):
        """Initialize agent with session and dependencies.

        Args:
            session: The agent session to work with.
            workspace_manager: WorkspaceManager for institution persistence.
            on_update: Callback for session updates (for streaming to UI).
        """
        self.session = session
        self.workspace_manager = workspace_manager
        self.on_update = on_update
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.MODEL

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the agent type."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    @property
    def tools(self) -> List[Dict[str, Any]]:
        """Return the tools available to this agent.

        Override in subclasses to provide agent-specific tools.
        """
        return []

    def _notify_update(self) -> None:
        """Notify listeners of session update."""
        if self.on_update:
            self.on_update(self.session)

    def _add_message(self, role: str, content: Any) -> None:
        """Add a message to the conversation history."""
        self.session.messages.append({"role": role, "content": content})

    def _record_tool_call(
        self,
        tool_name: str,
        input_params: Dict[str, Any],
        output_result: Dict[str, Any],
        duration_ms: int,
        success: bool = True,
        error: Optional[str] = None,
    ) -> ToolCall:
        """Record a tool invocation."""
        tool_call = ToolCall(
            tool_name=tool_name,
            input_params=input_params,
            output_result=output_result,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self.session.tool_calls.append(tool_call)
        return tool_call

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result.

        Override in subclasses to implement tool execution.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Tool execution result.
        """
        return {"error": f"Tool '{tool_name}' not implemented"}

    def _check_confidence_threshold(self, confidence: float) -> bool:
        """Check if confidence meets threshold for auto-approval.

        Args:
            confidence: Confidence score (0.0-1.0).

        Returns:
            True if confidence meets threshold.
        """
        return confidence >= Config.AGENT_CONFIDENCE_THRESHOLD

    def request_approval(
        self,
        checkpoint_type: str,
        description: str,
        data: Optional[Dict[str, Any]] = None,
        confidence: float = 0.0,
    ) -> HumanCheckpoint:
        """Request human approval for an action.

        Args:
            checkpoint_type: Type of checkpoint (e.g., 'task_approval', 'content_review').
            description: Description of what needs approval.
            data: Additional data for the checkpoint.
            confidence: Agent's confidence in the action (0.0-1.0).

        Returns:
            The created checkpoint.
        """
        checkpoint = HumanCheckpoint(
            checkpoint_type=checkpoint_type,
            description=description,
            data=data or {},
            agent_confidence=confidence,
        )
        self.session.checkpoints.append(checkpoint)
        self.session.status = SessionStatus.AWAITING_APPROVAL
        self._notify_update()
        return checkpoint

    def run_turn(self, user_message: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """Run a single conversation turn with the agent.

        Args:
            user_message: Optional user message to start/continue conversation.

        Yields:
            Progress updates and results.
        """
        if user_message:
            self._add_message("user", user_message)

        api_params = {
            "model": self.model,
            "max_tokens": Config.MAX_TOKENS,
            "system": self.system_prompt,
            "messages": self.session.messages,
        }

        if self.tools:
            api_params["tools"] = self.tools

        try:
            start_time = time.time()
            response = self.client.messages.create(**api_params)
            duration_ms = int((time.time() - start_time) * 1000)

            self.session.total_input_tokens += response.usage.input_tokens
            self.session.total_output_tokens += response.usage.output_tokens
            self.session.total_api_calls += 1

            yield {
                "type": "api_call",
                "duration_ms": duration_ms,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

        except Exception as e:
            self.session.last_error = str(e)
            self.session.errors.append({
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "error", "error": str(e)}
            return

        assistant_content = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
                yield {"type": "text", "text": block.text}

            elif block.type == "tool_use":
                tool_uses.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                yield {
                    "type": "tool_use",
                    "tool_name": block.name,
                    "tool_input": block.input,
                }

        self._add_message("assistant", assistant_content)

        if tool_uses:
            tool_results = []

            for tool_use in tool_uses:
                start_time = time.time()
                try:
                    result = self._execute_tool(tool_use.name, tool_use.input)
                    success = True
                    error = None
                except Exception as e:
                    result = {"error": str(e)}
                    success = False
                    error = str(e)

                duration_ms = int((time.time() - start_time) * 1000)

                self._record_tool_call(
                    tool_name=tool_use.name,
                    input_params=tool_use.input,
                    output_result=result,
                    duration_ms=duration_ms,
                    success=success,
                    error=error,
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                })

                yield {
                    "type": "tool_result",
                    "tool_name": tool_use.name,
                    "result": result,
                    "success": success,
                }

            self._add_message("user", tool_results)

            if response.stop_reason == "tool_use":
                yield from self.run_turn()

        self._notify_update()
        yield {"type": "turn_complete", "stop_reason": response.stop_reason}

    def run_task(self, task: AgentTask) -> Generator[Dict[str, Any], None, None]:
        """Run a specific task.

        Args:
            task: The task to execute.

        Yields:
            Progress updates and results.
        """
        task.status = "in_progress"
        task.started_at = datetime.now().isoformat()
        self.session.current_task_id = task.id
        self._notify_update()

        yield {"type": "task_started", "task_id": task.id, "task_name": task.name}

        task_prompt = f"""Execute this task:

**Task:** {task.name}
**Description:** {task.description}

Please complete this task using the available tools."""

        try:
            for update in self.run_turn(task_prompt):
                yield update

            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            yield {"type": "task_completed", "task_id": task.id}

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.retries += 1
            yield {"type": "task_failed", "task_id": task.id, "error": str(e)}

        self._notify_update()

    def run_all_tasks(self) -> Generator[Dict[str, Any], None, None]:
        """Run all pending tasks in dependency order.

        Yields:
            Progress updates for each task.
        """
        self.session.status = SessionStatus.RUNNING
        self.session.started_at = datetime.now().isoformat()
        self._notify_update()

        yield {"type": "session_started", "session_id": self.session.id}

        while True:
            pending = [t for t in self.session.tasks if t.status == "pending"]
            if not pending:
                break

            pending.sort(key=lambda t: t.priority.value, reverse=True)
            task = pending[0]

            if task.requires_approval:
                checkpoint = self.request_approval(
                    checkpoint_type="task_approval",
                    description=f"Approval required before: {task.name}",
                    data={"task_id": task.id, "task_name": task.name},
                )
                yield {
                    "type": "checkpoint_created",
                    "checkpoint_id": checkpoint.id,
                    "checkpoint_type": checkpoint.checkpoint_type,
                }
                return

            for update in self.run_task(task):
                yield update

        self.session.status = SessionStatus.COMPLETED
        self.session.completed_at = datetime.now().isoformat()
        self.session.current_task_id = None
        self._notify_update()

        yield {
            "type": "session_completed",
            "session_id": self.session.id,
            "total_api_calls": self.session.total_api_calls,
            "total_input_tokens": self.session.total_input_tokens,
            "total_output_tokens": self.session.total_output_tokens,
        }

    def resume_after_approval(
        self,
        checkpoint_id: str,
        approved: bool,
        feedback: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """Resume execution after a checkpoint approval.

        Args:
            checkpoint_id: ID of the checkpoint being resolved.
            approved: Whether the checkpoint was approved.
            feedback: Optional feedback from reviewer.

        Yields:
            Progress updates.
        """
        checkpoint = None
        for cp in self.session.checkpoints:
            if cp.id == checkpoint_id:
                checkpoint = cp
                break

        if not checkpoint:
            yield {"type": "error", "error": f"Checkpoint {checkpoint_id} not found"}
            return

        checkpoint.status = "approved" if approved else "rejected"
        checkpoint.feedback = feedback
        checkpoint.resolved_at = datetime.now().isoformat()

        if not approved:
            self.session.status = SessionStatus.CANCELLED
            yield {"type": "session_cancelled", "reason": "Checkpoint rejected"}
            return

        self.session.status = SessionStatus.RUNNING
        yield from self.run_all_tasks()

    def get_institution(self) -> Optional[Any]:
        """Get the institution associated with this session.

        Returns:
            Institution object or None if not found.
        """
        if not self.workspace_manager or not self.session.institution_id:
            return None
        return self.workspace_manager.load_institution(self.session.institution_id)

    def save_session(self) -> None:
        """Persist the current session state to disk."""
        if self.workspace_manager and self.session.institution_id:
            self.workspace_manager.save_agent_session(
                self.session.institution_id,
                self.session.to_dict()
            )
