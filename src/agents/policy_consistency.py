"""Policy Consistency Agent.

Detects contradictions across institutional documents (catalog, handbook,
enrollment agreement, website) to prevent compliance issues.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.POLICY_CONSISTENCY)
class PolicyConsistencyAgent(BaseAgent):
    """Policy Consistency Agent.

    Checks for contradictions in:
    - Refund periods and calculations
    - Cancellation terms
    - Grievance procedures
    - Tuition amounts and fees
    - Program lengths and credit hours
    - Contact information
    - Policy effective dates

    Cross-references: catalog, student handbook, enrollment agreement, website
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.POLICY_CONSISTENCY

    @property
    def system_prompt(self) -> str:
        return """You are the Policy Consistency Agent for AccreditAI.

Your mission is to detect contradictions across institutional documents that could
cause compliance issues during audits.

Common contradiction areas:
1. Refund policy - periods, percentages, calculations must match everywhere
2. Cancellation policy - timeframes and procedures
3. Tuition/fees - amounts, payment schedules
4. Program information - hours, weeks, credits
5. Contact information - addresses, phone numbers, emails
6. Dates - effective dates, catalog dates

When you find inconsistencies:
- Cite exact text from each document
- Note page numbers
- Assess severity (critical if regulatory, advisory if cosmetic)
- Suggest which version should be authoritative"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "check_policy_consistency",
                "description": "Check a specific policy for consistency across documents",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "policy_type": {
                            "type": "string",
                            "enum": ["refund", "cancellation", "tuition", "attendance",
                                     "grievance", "transfer", "sap", "withdrawal"]
                        }
                    },
                    "required": ["institution_id", "policy_type"]
                }
            },
            {
                "name": "run_full_consistency_scan",
                "description": "Run comprehensive consistency check across all documents",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"}
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "compare_values",
                "description": "Compare specific values across documents",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "value_type": {"type": "string"},
                        "search_terms": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id", "value_type"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a consistency check tool."""
        if tool_name == "check_policy_consistency":
            return self._tool_check_policy(tool_input)
        elif tool_name == "run_full_consistency_scan":
            return self._tool_full_scan(tool_input)
        elif tool_name == "compare_values":
            return self._tool_compare_values(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_check_policy(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Check policy consistency (stub with search)."""
        try:
            from src.search import get_search_service

            institution_id = tool_input.get("institution_id")
            policy_type = tool_input.get("policy_type")

            search_service = get_search_service(institution_id)
            results = search_service.search(f"{policy_type} policy", n_results=20)

            # Group by document
            by_document = {}
            for result in results:
                doc_id = result.chunk.document_id
                if doc_id not in by_document:
                    by_document[doc_id] = []
                by_document[doc_id].append({
                    "text": result.chunk.text_anonymized[:300],
                    "page": result.chunk.page_number,
                    "score": result.score
                })

            return {
                "success": True,
                "policy_type": policy_type,
                "documents_found": len(by_document),
                "excerpts_by_document": by_document,
                "consistency_status": "manual_review_required",
                "note": "AI comparison of extracted values not yet implemented"
            }

        except Exception as e:
            return {"error": str(e)}

    def _tool_full_scan(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run full consistency scan (stub)."""
        return {
            "success": True,
            "message": "Full scan initiated",
            "status": "pending",
            "policies_to_check": [
                "refund", "cancellation", "tuition", "attendance",
                "grievance", "transfer", "sap", "withdrawal"
            ],
            "note": "Would run check_policy_consistency for each policy type"
        }

    def _tool_compare_values(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Compare specific values (stub)."""
        return {
            "success": True,
            "message": "Value comparison requires document parsing",
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a consistency workflow."""
        if action == "full_audit":
            result = self._tool_full_scan(inputs)
            return AgentResult.success(data=result, confidence=0.5)
        return AgentResult.error(f"Unknown workflow: {action}")
