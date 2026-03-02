"""Calendar and Deadline Agent.

Tracks accreditation deadlines and generates reminders/tasks.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.CALENDAR_DEADLINE)
class CalendarDeadlineAgent(BaseAgent):
    """Calendar and Deadline Agent.

    Tracks:
    - Annual report timelines
    - Renewal site visit schedules
    - Substantive change deadlines
    - State license expirations
    - Document review due dates

    Outputs:
    - Calendar events
    - "What is due next" dashboard data
    - Escalating warnings
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CALENDAR_DEADLINE

    @property
    def system_prompt(self) -> str:
        return """You are the Calendar and Deadline Agent for AccreditAI.

You track all accreditation-related deadlines and generate timely reminders.

DEADLINE TYPES:
- Accreditor deadlines (annual reports, renewals)
- Federal deadlines (IPEDS, gainful employment)
- State deadlines (license renewals)
- Internal deadlines (document reviews, committee meetings)

REMINDER SCHEDULE:
- 90 days: Initial reminder
- 30 days: Urgent reminder
- 7 days: Critical reminder
- Overdue: Escalation

Generate task lists for each upcoming deadline with required actions."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_upcoming_deadlines",
                "description": "Get upcoming deadlines for an institution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "days_ahead": {"type": "integer", "default": 90}
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "add_deadline",
                "description": "Add a new deadline to track",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "deadline_type": {"type": "string"},
                        "due_date": {"type": "string"},
                        "description": {"type": "string"},
                        "accreditor": {"type": "string"}
                    },
                    "required": ["institution_id", "deadline_type", "due_date"]
                }
            },
            {
                "name": "generate_deadline_tasks",
                "description": "Generate task list for an upcoming deadline",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "deadline_id": {"type": "string"}
                    },
                    "required": ["deadline_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a calendar tool."""
        if tool_name == "get_upcoming_deadlines":
            return self._tool_get_deadlines(tool_input)
        elif tool_name == "add_deadline":
            return self._tool_add_deadline(tool_input)
        elif tool_name == "generate_deadline_tasks":
            return self._tool_generate_tasks(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_get_deadlines(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get upcoming deadlines (stub)."""
        return {
            "success": True,
            "deadlines": [],
            "message": "Deadline tracking requires calendar data",
            "status": "stub"
        }

    def _tool_add_deadline(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Add deadline (stub)."""
        return {
            "success": True,
            "message": "Deadline added (stub)",
            "deadline": tool_input
        }

    def _tool_generate_tasks(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate tasks for deadline (stub)."""
        return {
            "success": True,
            "tasks": [],
            "message": "Task generation requires deadline details",
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a calendar workflow."""
        return AgentResult.success(
            data={"message": f"Calendar workflow '{action}' not yet implemented"},
            confidence=0.5
        )
