"""Crosswalk Builder Agent.

Maps overlapping requirements across regulatory bodies (accreditor, DOE,
state, programmatic) to enable evidence reuse and comprehensive compliance.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.CROSSWALK_BUILDER)
class CrosswalkBuilderAgent(BaseAgent):
    """Crosswalk Builder Agent.

    Responsibilities:
    - Map accreditor standard ↔ DOE Title IV ↔ state regs ↔ programmatic
    - Cluster similar obligations across bodies
    - Recommend evidence reuse opportunities

    Outputs:
    - regulatory_crosswalk.json
    - Reuse recommendations
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CROSSWALK_BUILDER

    @property
    def system_prompt(self) -> str:
        return """You are the Crosswalk Builder Agent for AccreditAI.

Your mission is to identify overlapping requirements across regulatory bodies:
- Accreditor standards (ACCSC, HLC, SACSCOC, etc.)
- Federal regulations (Title IV, FERPA, Clery, ADA, etc.)
- State licensing requirements
- Programmatic accreditor standards

When requirements overlap, evidence can often be reused, saving significant effort.

For each crosswalk you create, document:
1. The primary requirement (accreditor standard)
2. Related federal regulations with CFR citations
3. Related state requirements
4. Programmatic equivalents
5. Evidence that satisfies multiple requirements"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "find_related_requirements",
                "description": "Find related requirements across regulatory bodies",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "requirement_text": {"type": "string"},
                        "source_body": {"type": "string"},
                        "target_bodies": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["requirement_text"]
                }
            },
            {
                "name": "build_crosswalk",
                "description": "Build a regulatory crosswalk for an institution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "standards_id": {"type": "string"},
                        "include_federal": {"type": "boolean", "default": True},
                        "include_state": {"type": "boolean", "default": True}
                    },
                    "required": ["institution_id", "standards_id"]
                }
            },
            {
                "name": "identify_reuse_opportunities",
                "description": "Identify where evidence can be reused across requirements",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "crosswalk_id": {"type": "string"},
                        "evidence_map_id": {"type": "string"}
                    },
                    "required": ["crosswalk_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a crosswalk builder tool."""
        if tool_name == "find_related_requirements":
            return self._tool_find_related(tool_input)
        elif tool_name == "build_crosswalk":
            return self._tool_build_crosswalk(tool_input)
        elif tool_name == "identify_reuse_opportunities":
            return self._tool_identify_reuse(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_find_related(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Find related requirements (stub with common mappings)."""
        requirement = tool_input.get("requirement_text", "").lower()

        # Common crosswalk patterns
        crosswalks = []

        if "refund" in requirement:
            crosswalks = [
                {"body": "DOE Title IV", "citation": "34 CFR 668.22", "topic": "Return of Title IV funds"},
                {"body": "State", "citation": "Varies", "topic": "State refund requirements"}
            ]
        elif "attendance" in requirement:
            crosswalks = [
                {"body": "DOE Title IV", "citation": "34 CFR 668.22", "topic": "Attendance for R2T4"},
                {"body": "VA", "citation": "38 CFR 21.4253", "topic": "VA attendance requirements"}
            ]
        elif "disclosure" in requirement or "consumer" in requirement:
            crosswalks = [
                {"body": "DOE", "citation": "34 CFR 668.41-49", "topic": "Consumer information"},
                {"body": "FTC", "citation": "16 CFR 254", "topic": "Guides for private vocational schools"}
            ]

        return {
            "success": True,
            "requirement_preview": requirement[:100],
            "related_requirements": crosswalks,
            "count": len(crosswalks)
        }

    def _tool_build_crosswalk(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Build a full crosswalk (stub)."""
        return {
            "success": True,
            "message": "Full crosswalk building requires federal/state regulation database",
            "status": "stub",
            "note": "Would iterate all standards and find related requirements"
        }

    def _tool_identify_reuse(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Identify reuse opportunities (stub)."""
        return {
            "success": True,
            "message": "Reuse analysis requires completed crosswalk and evidence map",
            "opportunities": [],
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a crosswalk workflow."""
        return AgentResult.success(
            data={"message": f"Crosswalk workflow '{action}' not yet implemented"},
            confidence=0.5
        )
