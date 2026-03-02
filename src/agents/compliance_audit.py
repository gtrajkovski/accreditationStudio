"""Compliance Audit Agent.

Runs multi-pass compliance audits against accreditation standards and
regulatory requirements. The core audit engine of AccreditAI.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult, ComplianceStatus, FindingSeverity


@register_agent(AgentType.COMPLIANCE_AUDIT)
class ComplianceAuditAgent(BaseAgent):
    """Compliance Audit Agent.

    Runs multi-pass audits:
    1. Completeness - Are all required elements present?
    2. Standard-by-standard matching - Does content meet each requirement?
    3. Internal consistency - Do statements agree with each other?
    4. Risk/severity grading - How serious are the gaps?
    5. Remediation guidance - What needs to be fixed?

    Outputs findings with severity, confidence, citations, and evidence pointers.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.COMPLIANCE_AUDIT

    @property
    def system_prompt(self) -> str:
        return """You are the Compliance Audit Agent for AccreditAI.

You perform multi-pass compliance audits of institutional documents against
accreditation standards and regulatory requirements.

AUDIT PASSES:
1. COMPLETENESS: Check if all required sections/elements are present
2. STANDARDS MATCH: Verify content meets specific standard requirements
3. CONSISTENCY: Check for internal contradictions
4. RISK GRADING: Assess severity of each finding
5. REMEDIATION: Provide specific fix recommendations

FOR EACH FINDING:
- Cite the specific standard (e.g., "ACCSC Section VII.A.4")
- Quote the relevant document text
- Note page numbers
- Assess severity (critical/significant/advisory/informational)
- Provide confidence score
- Give specific remediation guidance

NEVER claim compliance without evidence. When uncertain, flag for human review."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "run_completeness_pass",
                "description": "Check document completeness against required elements",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id": {"type": "string"},
                        "standards_id": {"type": "string"},
                        "checklist_items": {
                            "type": "array",
                            "items": {"type": "object"}
                        }
                    },
                    "required": ["institution_id", "document_id"]
                }
            },
            {
                "name": "run_standards_pass",
                "description": "Check compliance against specific standards",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id": {"type": "string"},
                        "standards_id": {"type": "string"},
                        "section_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id", "document_id", "standards_id"]
                }
            },
            {
                "name": "run_consistency_pass",
                "description": "Check for internal inconsistencies",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "create_finding",
                "description": "Record an audit finding",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {"type": "string"},
                        "standard_citation": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["compliant", "partial", "non_compliant", "na"]
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "significant", "advisory", "informational"]
                        },
                        "evidence_text": {"type": "string"},
                        "finding_detail": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "page_numbers": {"type": "string"},
                        "confidence": {"type": "number"}
                    },
                    "required": ["audit_id", "standard_citation", "status", "finding_detail"]
                }
            },
            {
                "name": "generate_audit_report",
                "description": "Generate final audit report",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {"type": "string"},
                        "include_remediation": {"type": "boolean", "default": True}
                    },
                    "required": ["audit_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an audit tool."""
        if tool_name == "run_completeness_pass":
            return self._tool_completeness_pass(tool_input)
        elif tool_name == "run_standards_pass":
            return self._tool_standards_pass(tool_input)
        elif tool_name == "run_consistency_pass":
            return self._tool_consistency_pass(tool_input)
        elif tool_name == "create_finding":
            return self._tool_create_finding(tool_input)
        elif tool_name == "generate_audit_report":
            return self._tool_generate_report(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_completeness_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run completeness check (stub with search)."""
        try:
            from src.search import get_search_service

            institution_id = tool_input.get("institution_id")
            checklist_items = tool_input.get("checklist_items", [])

            if not checklist_items:
                return {"success": True, "message": "No checklist items provided", "results": []}

            search_service = get_search_service(institution_id)
            results = []

            for item in checklist_items[:10]:  # Limit for stub
                query = item.get("description", "")
                search_results = search_service.search(query, n_results=3)

                found = len(search_results) > 0 and search_results[0].score > 0.6
                results.append({
                    "item": item.get("number", ""),
                    "description": query[:100],
                    "found": found,
                    "confidence": search_results[0].score if search_results else 0,
                    "best_match": search_results[0].chunk.text_anonymized[:200] if search_results else None
                })

            return {
                "success": True,
                "pass": "completeness",
                "items_checked": len(results),
                "items_found": sum(1 for r in results if r["found"]),
                "results": results
            }

        except Exception as e:
            return {"error": str(e)}

    def _tool_standards_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run standards compliance pass (stub)."""
        return {
            "success": True,
            "pass": "standards",
            "message": "Standards pass requires AI analysis of document content",
            "status": "stub"
        }

    def _tool_consistency_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run consistency pass (stub)."""
        return {
            "success": True,
            "pass": "consistency",
            "message": "Consistency pass delegates to PolicyConsistencyAgent",
            "status": "stub"
        }

    def _tool_create_finding(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create an audit finding."""
        from src.core.models import AuditFinding, generate_id

        finding = AuditFinding(
            id=generate_id("find"),
            audit_id=tool_input.get("audit_id", ""),
            item_number=tool_input.get("standard_citation", ""),
            status=ComplianceStatus(tool_input.get("status", "na")),
            severity=FindingSeverity(tool_input.get("severity", "informational")),
            evidence_in_document=tool_input.get("evidence_text", ""),
            finding_detail=tool_input.get("finding_detail", ""),
            recommendation=tool_input.get("recommendation", ""),
            page_numbers=tool_input.get("page_numbers", ""),
            ai_confidence=tool_input.get("confidence", 0.0)
        )

        return {
            "success": True,
            "finding": finding.to_dict()
        }

    def _tool_generate_report(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate audit report (stub)."""
        return {
            "success": True,
            "message": "Report generation requires completed audit with findings",
            "status": "stub"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run an audit workflow."""
        if action == "full_audit":
            return self._workflow_full_audit(inputs)
        return AgentResult.error(f"Unknown workflow: {action}")

    def _workflow_full_audit(self, inputs: Dict[str, Any]) -> AgentResult:
        """Run full multi-pass audit (placeholder)."""
        return AgentResult.success(
            data={
                "message": "Full audit workflow orchestrates all passes",
                "passes": ["completeness", "standards", "consistency", "risk", "remediation"]
            },
            confidence=0.5,
            next_actions=[
                {"action": "run_completeness_pass", "priority": "high"},
                {"action": "run_standards_pass", "priority": "high"},
                {"action": "run_consistency_pass", "priority": "medium"}
            ]
        )
