"""Remediation Agent.

Produces redlines, clean finals, and crossrefs from audit findings.
Never modifies originals - all changes are versioned in the workspace.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.REMEDIATION)
class RemediationAgent(BaseAgent):
    """Remediation Agent.

    Rules:
    - Never modify originals (read-only)
    - Use truth index as authoritative source
    - Every inserted clause linked to finding and standard citation
    - Generate clean final + redline version

    Outputs:
    - redlines/<doc_id>_<timestamp>.docx
    - finals/<doc_id>_<timestamp>.docx
    - crossrefs/<doc_id>_<timestamp>.docx
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.REMEDIATION

    @property
    def system_prompt(self) -> str:
        return """You are the Remediation Agent for AccreditAI.

You generate corrected document versions based on audit findings.

CRITICAL RULES:
1. NEVER modify files in originals/ folder
2. Use truth_index.json as the authoritative source for all values
3. Every inserted compliance statement must cite the governing standard
4. Link changes to the finding that triggered them
5. Generate both redline (tracked changes) and clean final versions

OUTPUT FILES:
- redlines/<doc_id>_<timestamp>.docx - Shows tracked changes
- finals/<doc_id>_<timestamp>.docx - Clean version with all corrections
- crossrefs/<doc_id>_<timestamp>.docx - Version with checklist tags"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_remediation",
                "description": "Generate redlines and finals for a document based on findings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id": {"type": "string"},
                        "audit_id": {"type": "string"},
                        "finding_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id", "document_id", "audit_id"]
                }
            },
            {
                "name": "apply_truth_index",
                "description": "Apply truth index values to document",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id": {"type": "string"},
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id", "document_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a remediation tool."""
        if tool_name == "generate_remediation":
            return self._tool_generate_remediation(tool_input)
        elif tool_name == "apply_truth_index":
            return self._tool_apply_truth_index(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_generate_remediation(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate remediation documents (stub)."""
        return {
            "success": True,
            "message": "Remediation generation requires document editing capabilities",
            "status": "stub",
            "would_create": [
                "redlines/<doc_id>_<timestamp>.docx",
                "finals/<doc_id>_<timestamp>.docx",
                "crossrefs/<doc_id>_<timestamp>.docx"
            ]
        }

    def _tool_apply_truth_index(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Apply truth index values (stub)."""
        return {
            "success": True,
            "message": "Truth index application requires document editing",
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a remediation workflow."""
        return AgentResult.success(
            data={"message": f"Remediation workflow '{action}' not yet implemented"},
            confidence=0.5
        )
