"""Narrative Agent.

Writes issue narratives used in responses and self-studies with proper
citations and institutional voice.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.NARRATIVE)
class NarrativeAgent(BaseAgent):
    """Narrative Agent.

    Writes:
    - Issue response sections with citations
    - Self-study narratives
    - Compliance explanations

    Checkpoint: Required for final submission narratives.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NARRATIVE

    @property
    def system_prompt(self) -> str:
        return """You are the Narrative Agent for AccreditAI.

You write clear, professional narratives for accreditation documents:
- Issue responses explaining how the institution addresses findings
- Self-study sections describing compliance with standards
- Evidence summaries connecting documents to requirements

STYLE GUIDELINES:
1. Use formal, professional tone
2. Be specific with citations (standard number, page, section)
3. Include evidence references
4. Avoid vague claims - every statement needs support
5. Match institutional voice guidelines when provided

OUTPUT STRUCTURE:
- Introduction/context
- Standard requirement summary
- Evidence presentation
- Conclusion/compliance statement
- Citations list"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "write_issue_response",
                "description": "Write a response narrative for a finding",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string"},
                        "evidence_map": {"type": "object"},
                        "voice_guidelines": {"type": "string"}
                    },
                    "required": ["finding_id"]
                }
            },
            {
                "name": "write_self_study_section",
                "description": "Write a self-study section for a standard",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standard_id": {"type": "string"},
                        "evidence_map": {"type": "object"},
                        "institution_id": {"type": "string"}
                    },
                    "required": ["standard_id", "institution_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a narrative tool."""
        if tool_name == "write_issue_response":
            return self._tool_write_issue_response(tool_input)
        elif tool_name == "write_self_study_section":
            return self._tool_write_self_study(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_write_issue_response(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Write issue response (stub)."""
        return {
            "success": True,
            "message": "Issue response writing requires AI generation",
            "status": "stub",
            "checkpoint_required": True,
            "note": "Final submission narratives require human approval"
        }

    def _tool_write_self_study(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Write self-study section (stub)."""
        return {
            "success": True,
            "message": "Self-study writing requires AI generation",
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a narrative workflow."""
        # Narratives for submission require approval
        if action in ["write_submission_narrative", "finalize_self_study"]:
            return AgentResult.needs_approval(
                reason="Submission narratives require human review",
                data={"action": action, "inputs": inputs}
            )
        return AgentResult.success(
            data={"message": f"Narrative workflow '{action}' not yet implemented"},
            confidence=0.5
        )
