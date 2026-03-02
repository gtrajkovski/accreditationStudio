"""Truth Index Curator Agent.

Maintains the Single Source of Truth (truth_index.json) containing canonical
institutional facts. Proposes updates, requires approval, and propagates
changes to remediation tasks.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.TRUTH_INDEX_CURATOR)
class TruthIndexCuratorAgent(BaseAgent):
    """Truth Index Curator Agent.

    Responsibilities:
    - Propose updates to truth index from authoritative documents
    - Require human approval before changing canonical values
    - Track change history with audit trail
    - Propagate changes to remediation tasks
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.TRUTH_INDEX_CURATOR

    @property
    def system_prompt(self) -> str:
        return """You are the Truth Index Curator Agent for AccreditAI.

You maintain the Single Source of Truth (truth_index.json) containing canonical
institutional facts like:
- Institution name, addresses, contact info
- Program details (hours, costs, lengths)
- Policy parameters (refund periods, SAP thresholds)
- Key dates and deadlines

CRITICAL RULES:
1. NEVER change truth index values without explicit human approval
2. Always cite the authoritative document source for any proposed change
3. Track all changes with timestamps and reasons
4. Flag conflicts when documents disagree on canonical values
5. Propagate approved changes to generate remediation tasks"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_truth_index",
                "description": "Get the current truth index for an institution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"}
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "propose_update",
                "description": "Propose an update to a truth index value (requires approval)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "field_path": {"type": "string"},
                        "new_value": {"type": "string"},
                        "source_document": {"type": "string"},
                        "source_page": {"type": "integer"},
                        "reason": {"type": "string"}
                    },
                    "required": ["institution_id", "field_path", "new_value", "reason"]
                }
            },
            {
                "name": "extract_facts_from_document",
                "description": "Extract potential truth index facts from a document",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id": {"type": "string"}
                    },
                    "required": ["institution_id", "document_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a truth index tool."""
        if tool_name == "get_truth_index":
            return self._tool_get_truth_index(tool_input)
        elif tool_name == "propose_update":
            return self._tool_propose_update(tool_input)
        elif tool_name == "extract_facts_from_document":
            return self._tool_extract_facts(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_get_truth_index(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get current truth index."""
        import json
        from pathlib import Path
        from src.config import Config

        institution_id = tool_input.get("institution_id")
        truth_path = Config.WORKSPACE_DIR / institution_id / "truth_index.json"

        if truth_path.exists():
            with open(truth_path) as f:
                return {"success": True, "truth_index": json.load(f)}
        return {"success": True, "truth_index": {}, "note": "No truth index exists yet"}

    def _tool_propose_update(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Propose an update (creates checkpoint for approval)."""
        # This should create a human checkpoint
        return {
            "success": True,
            "status": "pending_approval",
            "proposal": {
                "field": tool_input.get("field_path"),
                "new_value": tool_input.get("new_value"),
                "reason": tool_input.get("reason"),
                "source": tool_input.get("source_document")
            },
            "checkpoint_required": True,
            "message": "Truth index changes require human approval"
        }

    def _tool_extract_facts(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts from document (stub)."""
        return {
            "success": True,
            "message": "Fact extraction requires AI analysis of document",
            "status": "stub",
            "potential_facts": []
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a truth index workflow."""
        if action == "sync_from_documents":
            return AgentResult.needs_approval(
                reason="Truth index sync requires approval for each change",
                data={"action": action, "inputs": inputs}
            )
        return AgentResult.error(f"Unknown workflow: {action}")
