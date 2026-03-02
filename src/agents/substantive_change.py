"""Substantive Change Agent.

Analyzes proposed institutional changes to determine if accreditor approval
is required and what documentation is needed.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.SUBSTANTIVE_CHANGE)
class SubstantiveChangeAgent(BaseAgent):
    """Substantive Change Agent.

    Analyzes changes that may require accreditor notification/approval:
    - New programs
    - New locations/branches
    - Online delivery
    - Ownership changes
    - Clock hour to credit hour conversions
    - Significant program modifications

    CRITICAL: Always requires human approval before final determination.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SUBSTANTIVE_CHANGE

    @property
    def system_prompt(self) -> str:
        return """You are the Substantive Change Agent for AccreditAI.

You analyze proposed institutional changes to determine if they require
accreditor approval and what documentation is needed.

COMMON SUBSTANTIVE CHANGES:
- New program (always requires approval)
- New location/branch campus
- Change to distance/online delivery
- Ownership change
- Clock-to-credit conversion
- Significant curriculum changes (>25%)
- Addition of credential level

FOR EACH ANALYSIS:
1. Identify the type of change
2. Cite specific accreditor requirements
3. Determine notification vs. approval requirement
4. List required documentation
5. Estimate timeline

CRITICAL: Substantive change determinations have legal/compliance implications.
ALWAYS flag for human review before final determination."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "analyze_change",
                "description": "Analyze a proposed change for substantive change requirements",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "change_type": {
                            "type": "string",
                            "enum": ["new_program", "new_location", "online_delivery",
                                     "ownership", "clock_to_credit", "curriculum_change",
                                     "credential_level", "other"]
                        },
                        "change_description": {"type": "string"},
                        "accreditor": {"type": "string"},
                        "institution_id": {"type": "string"}
                    },
                    "required": ["change_type", "change_description"]
                }
            },
            {
                "name": "get_required_documents",
                "description": "Get list of required documents for a substantive change",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "change_type": {"type": "string"},
                        "accreditor": {"type": "string"}
                    },
                    "required": ["change_type"]
                }
            },
            {
                "name": "estimate_timeline",
                "description": "Estimate approval timeline for a substantive change",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "change_type": {"type": "string"},
                        "accreditor": {"type": "string"}
                    },
                    "required": ["change_type"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a substantive change tool."""
        if tool_name == "analyze_change":
            return self._tool_analyze_change(tool_input)
        elif tool_name == "get_required_documents":
            return self._tool_get_documents(tool_input)
        elif tool_name == "estimate_timeline":
            return self._tool_estimate_timeline(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_analyze_change(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a proposed change."""
        change_type = tool_input.get("change_type")
        accreditor = tool_input.get("accreditor", "ACCSC")

        # Common determinations by type
        determinations = {
            "new_program": {
                "requires_approval": True,
                "notification_only": False,
                "typical_review_days": 90,
                "note": "New programs always require prior approval"
            },
            "new_location": {
                "requires_approval": True,
                "notification_only": False,
                "typical_review_days": 120,
                "note": "Branch campuses require approval; additional locations may vary"
            },
            "online_delivery": {
                "requires_approval": True,
                "notification_only": False,
                "typical_review_days": 90,
                "note": "Change in delivery modality requires approval"
            },
            "ownership": {
                "requires_approval": True,
                "notification_only": False,
                "typical_review_days": 180,
                "note": "Ownership changes require approval and may trigger site visit"
            },
            "curriculum_change": {
                "requires_approval": "depends",
                "notification_only": "if_under_25_percent",
                "typical_review_days": 30,
                "note": "Changes >25% require approval; smaller changes may be notification only"
            }
        }

        result = determinations.get(change_type, {
            "requires_approval": "unknown",
            "note": "Consult accreditor guidelines for this change type"
        })

        return {
            "success": True,
            "change_type": change_type,
            "accreditor": accreditor,
            "determination": result,
            "human_review_required": True,
            "disclaimer": "This is preliminary guidance. Final determination requires accreditor consultation."
        }

    def _tool_get_documents(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get required documents list."""
        change_type = tool_input.get("change_type")

        common_docs = [
            "Substantive change application form",
            "Program/change description",
            "Financial capability documentation",
            "Staffing plan"
        ]

        type_specific = {
            "new_program": [
                "Curriculum outline",
                "Faculty qualifications",
                "Market/demand analysis",
                "Equipment list",
                "Advisory committee input"
            ],
            "new_location": [
                "Facility description/photos",
                "Lease agreement",
                "State approval",
                "Enrollment projections"
            ]
        }

        docs = common_docs + type_specific.get(change_type, [])

        return {
            "success": True,
            "change_type": change_type,
            "required_documents": docs,
            "note": "Check accreditor-specific requirements for complete list"
        }

    def _tool_estimate_timeline(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate approval timeline."""
        change_type = tool_input.get("change_type")

        timelines = {
            "new_program": "90-120 days",
            "new_location": "120-180 days",
            "online_delivery": "90-120 days",
            "ownership": "180-365 days",
            "curriculum_change": "30-60 days"
        }

        return {
            "success": True,
            "change_type": change_type,
            "estimated_timeline": timelines.get(change_type, "Varies - consult accreditor"),
            "note": "Timelines are estimates; actual review time varies"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a substantive change workflow."""
        # Always require approval for substantive change determinations
        return AgentResult.needs_approval(
            reason="Substantive change determinations require human review",
            data={"action": action, "inputs": inputs}
        )
