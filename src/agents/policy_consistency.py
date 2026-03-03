"""Policy Consistency Agent.

Detects contradictions across institutional documents (catalog, handbook,
enrollment agreement, website) to prevent compliance issues.

Tools:
- check_policy_consistency: Check a specific policy across documents
- run_full_consistency_scan: Comprehensive scan of all policy types
- compare_to_truth_index: Validate documents against truth index
- extract_policy_values: Extract specific values from documents
- generate_consistency_report: Create full inconsistency report
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult, AgentSession, generate_id, now_iso


class InconsistencySeverity(str, Enum):
    """Severity of an inconsistency finding."""
    CRITICAL = "critical"      # Regulatory violation risk
    SIGNIFICANT = "significant"  # Must fix before submission
    ADVISORY = "advisory"      # Should fix for quality
    COSMETIC = "cosmetic"      # Minor formatting/style


@dataclass
class Inconsistency:
    """A detected inconsistency between documents."""
    id: str = field(default_factory=lambda: generate_id("incon"))
    category: str = ""  # refund, tuition, program_length, contact, etc.
    severity: InconsistencySeverity = InconsistencySeverity.ADVISORY
    description: str = ""
    documents_involved: List[Dict[str, Any]] = field(default_factory=list)
    truth_index_value: Optional[str] = None
    recommended_value: str = ""
    ai_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity.value,
            "description": self.description,
            "documents_involved": self.documents_involved,
            "truth_index_value": self.truth_index_value,
            "recommended_value": self.recommended_value,
            "ai_confidence": self.ai_confidence,
        }


@dataclass
class ConsistencyReport:
    """Full consistency check report."""
    id: str = field(default_factory=lambda: generate_id("conrpt"))
    institution_id: str = ""
    documents_scanned: int = 0
    policies_checked: List[str] = field(default_factory=list)
    inconsistencies: List[Inconsistency] = field(default_factory=list)
    truth_index_mismatches: int = 0
    overall_status: str = "pending"  # clean, issues_found, critical_issues
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "documents_scanned": self.documents_scanned,
            "policies_checked": self.policies_checked,
            "inconsistencies": [i.to_dict() for i in self.inconsistencies],
            "inconsistency_count": len(self.inconsistencies),
            "by_severity": {
                "critical": len([i for i in self.inconsistencies if i.severity == InconsistencySeverity.CRITICAL]),
                "significant": len([i for i in self.inconsistencies if i.severity == InconsistencySeverity.SIGNIFICANT]),
                "advisory": len([i for i in self.inconsistencies if i.severity == InconsistencySeverity.ADVISORY]),
                "cosmetic": len([i for i in self.inconsistencies if i.severity == InconsistencySeverity.COSMETIC]),
            },
            "truth_index_mismatches": self.truth_index_mismatches,
            "overall_status": self.overall_status,
            "created_at": self.created_at,
        }


SYSTEM_PROMPT = """You are the Policy Consistency Agent for AccreditAI.

Your mission is to detect contradictions across institutional documents that could
cause compliance issues during accreditation audits.

CRITICAL CONSISTENCY AREAS:
1. REFUND POLICY - Percentages, timeframes, calculation methods must match exactly
2. CANCELLATION POLICY - Deadlines, procedures, forms required
3. TUITION/FEES - Dollar amounts, payment schedules, additional costs
4. PROGRAM INFO - Clock hours, credit hours, weeks, months, schedules
5. CONTACT INFO - Addresses, phone numbers, emails, office hours
6. DATES - Effective dates, catalog years, policy revision dates
7. SAP POLICY - GPA requirements, completion rates, evaluation periods
8. ATTENDANCE - Requirements, tardiness, makeup policies

WHEN ANALYZING:
- Extract specific values (numbers, dates, percentages)
- Compare exact wording when regulatory
- Note which document should be authoritative (usually Enrollment Agreement for costs)
- Assess regulatory impact of inconsistency

SEVERITY GUIDELINES:
- CRITICAL: Could cause Title IV audit findings (refund calculations, costs)
- SIGNIFICANT: Accreditor would cite (program hours, SAP policy)
- ADVISORY: Should fix for quality (contact info, minor wording)
- COSMETIC: Style/formatting only"""


# Policy categories with search terms and regulatory weight
POLICY_CATEGORIES = {
    "refund": {
        "terms": ["refund", "refund policy", "tuition refund", "cancellation refund"],
        "regulatory_weight": "critical",
        "key_values": ["percentage", "days", "period", "calculation"],
    },
    "cancellation": {
        "terms": ["cancellation", "cancel enrollment", "three day", "3 day", "cooling off"],
        "regulatory_weight": "critical",
        "key_values": ["days", "business days", "written notice"],
    },
    "tuition": {
        "terms": ["tuition", "program cost", "total cost", "fees", "registration fee"],
        "regulatory_weight": "critical",
        "key_values": ["dollar amount", "payment schedule", "additional costs"],
    },
    "program_length": {
        "terms": ["clock hours", "credit hours", "program length", "weeks", "months"],
        "regulatory_weight": "significant",
        "key_values": ["hours", "weeks", "credits"],
    },
    "sap": {
        "terms": ["satisfactory academic progress", "SAP", "academic standing", "GPA"],
        "regulatory_weight": "significant",
        "key_values": ["GPA", "completion rate", "maximum timeframe", "evaluation"],
    },
    "attendance": {
        "terms": ["attendance", "absence", "tardy", "makeup", "excused absence"],
        "regulatory_weight": "significant",
        "key_values": ["percentage", "hours", "consecutive days"],
    },
    "grievance": {
        "terms": ["grievance", "complaint", "dispute resolution", "appeal"],
        "regulatory_weight": "advisory",
        "key_values": ["procedure", "timeline", "contact"],
    },
    "contact": {
        "terms": ["address", "phone", "email", "contact", "office hours"],
        "regulatory_weight": "advisory",
        "key_values": ["address", "phone number", "email", "hours"],
    },
}


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

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        """Initialize the Policy Consistency Agent."""
        super().__init__(session, workspace_manager, on_update)
        self._institution_id: Optional[str] = None
        self._report_cache: Dict[str, ConsistencyReport] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.POLICY_CONSISTENCY

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "check_policy_consistency",
                "description": "Check a specific policy type for consistency across all documents. Uses semantic search and AI analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "policy_type": {
                            "type": "string",
                            "enum": list(POLICY_CATEGORIES.keys()),
                            "description": "Type of policy to check"
                        }
                    },
                    "required": ["institution_id", "policy_type"]
                }
            },
            {
                "name": "run_full_consistency_scan",
                "description": "Run comprehensive consistency check across all policy types for an institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "policy_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific policy types to check (optional, defaults to all)"
                        }
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "compare_to_truth_index",
                "description": "Compare document values against the institution's truth index.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "value_categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Categories to check: institution_name, program_costs, program_hours, contact_info"
                        }
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "analyze_document_pair",
                "description": "Deep comparison of two specific documents for inconsistencies.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "document_id_1": {"type": "string"},
                        "document_id_2": {"type": "string"},
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific areas to focus on (optional)"
                        }
                    },
                    "required": ["institution_id", "document_id_1", "document_id_2"]
                }
            },
            {
                "name": "generate_consistency_report",
                "description": "Generate and save a full consistency report for the institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "report_id": {"type": "string", "description": "Optional existing report ID to finalize"}
                    },
                    "required": ["institution_id"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a consistency check tool."""
        if tool_name == "check_policy_consistency":
            return self._tool_check_policy(tool_input)
        elif tool_name == "run_full_consistency_scan":
            return self._tool_full_scan(tool_input)
        elif tool_name == "compare_to_truth_index":
            return self._tool_compare_truth_index(tool_input)
        elif tool_name == "analyze_document_pair":
            return self._tool_analyze_pair(tool_input)
        elif tool_name == "generate_consistency_report":
            return self._tool_generate_report(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _search_documents(
        self,
        institution_id: str,
        query: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search documents using semantic search."""
        try:
            from src.search import get_search_service
            search_service = get_search_service(institution_id)
            results = search_service.search(query, n_results=n_results)

            excerpts = []
            for result in results:
                excerpts.append({
                    "document_id": result.chunk.document_id,
                    "text": result.chunk.text_anonymized[:500] if hasattr(result.chunk, 'text_anonymized') else result.chunk.text_redacted[:500],
                    "page": getattr(result.chunk, 'page_number', None),
                    "score": result.score,
                })
            return excerpts
        except Exception:
            return []

    def _get_document_info(self, institution_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata."""
        if not self.workspace_manager:
            return None
        institution = self.workspace_manager.load_institution(institution_id)
        if not institution:
            return None
        for doc in institution.documents:
            if doc.id == document_id:
                return {
                    "id": doc.id,
                    "type": doc.doc_type.value,
                    "filename": doc.original_filename,
                }
        return None

    def _get_truth_index(self, institution_id: str) -> Optional[Dict[str, Any]]:
        """Load truth index."""
        if not self.workspace_manager:
            return None
        return self.workspace_manager.get_truth_index(institution_id)

    def _analyze_consistency_with_ai(
        self,
        policy_type: str,
        excerpts_by_document: Dict[str, List[Dict[str, Any]]],
        truth_value: Optional[str] = None
    ) -> List[Inconsistency]:
        """Use AI to analyze excerpts for inconsistencies."""
        if len(excerpts_by_document) < 2:
            return []

        # Build prompt with excerpts
        excerpt_text = ""
        for doc_id, excerpts in excerpts_by_document.items():
            excerpt_text += f"\n\n=== DOCUMENT: {doc_id} ===\n"
            for exc in excerpts[:3]:  # Limit excerpts per doc
                excerpt_text += f"Page {exc.get('page', '?')}: {exc['text']}\n"

        prompt = f"""Analyze these document excerpts for inconsistencies in {policy_type} policy:

{excerpt_text}

{f"TRUTH INDEX VALUE: {truth_value}" if truth_value else ""}

Find specific inconsistencies:
1. Different numbers/amounts
2. Conflicting timeframes
3. Contradictory procedures
4. Mismatched requirements

For each inconsistency found, provide:
- description: What is inconsistent
- severity: critical/significant/advisory/cosmetic
- documents: Which documents conflict
- recommended_value: What the correct value should be
- confidence: 0.0-1.0

Respond with JSON array:
[{{"description": "...", "severity": "...", "doc1": "...", "doc1_value": "...", "doc2": "...", "doc2_value": "...", "recommended_value": "...", "confidence": 0.8}}]

If no inconsistencies found, respond with: []"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are a compliance auditor checking document consistency. Be thorough but avoid false positives. Output only valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON
            if response_text.startswith("["):
                findings = json.loads(response_text)
            else:
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    findings = json.loads(json_match.group())
                else:
                    findings = []

            # Convert to Inconsistency objects
            inconsistencies = []
            for f in findings[:10]:  # Limit
                try:
                    severity = InconsistencySeverity(f.get("severity", "advisory"))
                except ValueError:
                    severity = InconsistencySeverity.ADVISORY

                inconsistencies.append(Inconsistency(
                    category=policy_type,
                    severity=severity,
                    description=f.get("description", ""),
                    documents_involved=[
                        {"document_id": f.get("doc1", ""), "value": f.get("doc1_value", "")},
                        {"document_id": f.get("doc2", ""), "value": f.get("doc2_value", "")},
                    ],
                    truth_index_value=truth_value,
                    recommended_value=f.get("recommended_value", ""),
                    ai_confidence=f.get("confidence", 0.7),
                ))

            return inconsistencies

        except Exception:
            return []

    def _get_or_create_report(self, institution_id: str) -> ConsistencyReport:
        """Get existing or create new report."""
        if institution_id in self._report_cache:
            return self._report_cache[institution_id]

        report = ConsistencyReport(institution_id=institution_id)
        self._report_cache[institution_id] = report
        return report

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _tool_check_policy(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Check policy consistency across documents."""
        institution_id = tool_input.get("institution_id", "")
        policy_type = tool_input.get("policy_type", "")

        if not institution_id or not policy_type:
            return {"error": "institution_id and policy_type are required"}

        if policy_type not in POLICY_CATEGORIES:
            return {"error": f"Unknown policy type: {policy_type}"}

        self._institution_id = institution_id
        category = POLICY_CATEGORIES[policy_type]

        # Search for policy content across documents
        excerpts_by_document: Dict[str, List[Dict[str, Any]]] = {}

        for term in category["terms"]:
            results = self._search_documents(institution_id, term, n_results=8)
            for r in results:
                doc_id = r["document_id"]
                if doc_id not in excerpts_by_document:
                    excerpts_by_document[doc_id] = []
                # Avoid duplicates
                if not any(e["text"] == r["text"] for e in excerpts_by_document[doc_id]):
                    excerpts_by_document[doc_id].append(r)

        if len(excerpts_by_document) < 2:
            return {
                "success": True,
                "policy_type": policy_type,
                "documents_found": len(excerpts_by_document),
                "inconsistencies": [],
                "message": "Found policy in fewer than 2 documents - no cross-document comparison possible"
            }

        # Get truth index value if available
        truth_index = self._get_truth_index(institution_id)
        truth_value = None
        if truth_index and policy_type in ["tuition", "program_length"]:
            programs = truth_index.get("programs", {})
            if programs:
                first_prog = list(programs.values())[0]
                if policy_type == "tuition":
                    truth_value = f"${first_prog.get('total_cost', 'N/A')}"
                elif policy_type == "program_length":
                    truth_value = f"{first_prog.get('duration_months', 'N/A')} months"

        # Analyze with AI
        inconsistencies = self._analyze_consistency_with_ai(
            policy_type, excerpts_by_document, truth_value
        )

        # Update report
        report = self._get_or_create_report(institution_id)
        if policy_type not in report.policies_checked:
            report.policies_checked.append(policy_type)
        report.inconsistencies.extend(inconsistencies)
        report.documents_scanned = max(report.documents_scanned, len(excerpts_by_document))

        return {
            "success": True,
            "policy_type": policy_type,
            "regulatory_weight": category["regulatory_weight"],
            "documents_found": len(excerpts_by_document),
            "document_ids": list(excerpts_by_document.keys()),
            "inconsistencies_found": len(inconsistencies),
            "inconsistencies": [i.to_dict() for i in inconsistencies],
            "truth_index_value": truth_value,
            "message": f"Found {len(inconsistencies)} inconsistencies in {policy_type} policy"
        }

    def _tool_full_scan(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run full consistency scan across all policy types."""
        institution_id = tool_input.get("institution_id", "")
        policy_types = tool_input.get("policy_types", list(POLICY_CATEGORIES.keys()))

        if not institution_id:
            return {"error": "institution_id is required"}

        self._institution_id = institution_id

        # Reset report for fresh scan
        report = ConsistencyReport(institution_id=institution_id)
        self._report_cache[institution_id] = report

        results_by_policy = {}
        total_inconsistencies = 0

        for policy_type in policy_types:
            if policy_type in POLICY_CATEGORIES:
                result = self._tool_check_policy({
                    "institution_id": institution_id,
                    "policy_type": policy_type
                })
                results_by_policy[policy_type] = {
                    "inconsistencies_found": result.get("inconsistencies_found", 0),
                    "documents_found": result.get("documents_found", 0),
                }
                total_inconsistencies += result.get("inconsistencies_found", 0)

        # Determine overall status
        critical_count = len([i for i in report.inconsistencies if i.severity == InconsistencySeverity.CRITICAL])
        if critical_count > 0:
            report.overall_status = "critical_issues"
        elif total_inconsistencies > 0:
            report.overall_status = "issues_found"
        else:
            report.overall_status = "clean"

        return {
            "success": True,
            "report_id": report.id,
            "policies_checked": len(policy_types),
            "total_inconsistencies": total_inconsistencies,
            "by_severity": report.to_dict()["by_severity"],
            "overall_status": report.overall_status,
            "results_by_policy": results_by_policy,
            "message": f"Scanned {len(policy_types)} policy types, found {total_inconsistencies} inconsistencies"
        }

    def _tool_compare_truth_index(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Compare documents against truth index."""
        institution_id = tool_input.get("institution_id", "")
        categories = tool_input.get("value_categories", ["institution_name", "program_costs", "contact_info"])

        if not institution_id:
            return {"error": "institution_id is required"}

        truth_index = self._get_truth_index(institution_id)
        if not truth_index:
            return {"error": "Truth index not found for institution"}

        mismatches = []

        # Check institution name
        if "institution_name" in categories:
            inst_name = truth_index.get("institution", {}).get("name", "")
            if inst_name:
                results = self._search_documents(institution_id, inst_name, n_results=5)
                # Check if variations exist
                for r in results:
                    if inst_name.lower() not in r["text"].lower():
                        mismatches.append({
                            "category": "institution_name",
                            "truth_value": inst_name,
                            "document_id": r["document_id"],
                            "document_text": r["text"][:200],
                            "severity": "advisory"
                        })

        # Check program costs
        if "program_costs" in categories:
            programs = truth_index.get("programs", {})
            for prog_id, prog_data in programs.items():
                cost = prog_data.get("total_cost")
                if cost:
                    results = self._search_documents(institution_id, f"${cost}", n_results=5)
                    # Could extend to check for mismatched costs

        # Update report
        report = self._get_or_create_report(institution_id)
        report.truth_index_mismatches = len(mismatches)

        return {
            "success": True,
            "categories_checked": categories,
            "truth_index_keys": list(truth_index.keys()),
            "mismatches_found": len(mismatches),
            "mismatches": mismatches[:10],
            "message": f"Found {len(mismatches)} potential truth index mismatches"
        }

    def _tool_analyze_pair(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Deep comparison of two documents."""
        institution_id = tool_input.get("institution_id", "")
        doc_id_1 = tool_input.get("document_id_1", "")
        doc_id_2 = tool_input.get("document_id_2", "")
        focus_areas = tool_input.get("focus_areas", [])

        if not all([institution_id, doc_id_1, doc_id_2]):
            return {"error": "institution_id, document_id_1, and document_id_2 are required"}

        doc1_info = self._get_document_info(institution_id, doc_id_1)
        doc2_info = self._get_document_info(institution_id, doc_id_2)

        if not doc1_info or not doc2_info:
            return {"error": "One or both documents not found"}

        # Get document texts
        doc1_text = ""
        doc2_text = ""

        if self.workspace_manager:
            institution = self.workspace_manager.load_institution(institution_id)
            if institution:
                for doc in institution.documents:
                    if doc.id == doc_id_1:
                        doc1_text = doc.extracted_text[:5000] if doc.extracted_text else ""
                    elif doc.id == doc_id_2:
                        doc2_text = doc.extracted_text[:5000] if doc.extracted_text else ""

        if not doc1_text or not doc2_text:
            return {"error": "Could not load document text"}

        # AI comparison
        focus_str = f"Focus on: {', '.join(focus_areas)}" if focus_areas else ""

        prompt = f"""Compare these two documents for inconsistencies:

=== DOCUMENT 1: {doc1_info['filename']} ({doc1_info['type']}) ===
{doc1_text[:3000]}

=== DOCUMENT 2: {doc2_info['filename']} ({doc2_info['type']}) ===
{doc2_text[:3000]}

{focus_str}

Find specific contradictions or inconsistencies between these documents.
Focus on: numbers, dates, procedures, requirements, contact info.

Respond with JSON array of inconsistencies:
[{{"description": "...", "severity": "critical|significant|advisory", "doc1_excerpt": "...", "doc2_excerpt": "...", "recommended_action": "..."}}]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are a compliance auditor. Find real inconsistencies, not style differences. Output valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()
            if response_text.startswith("["):
                findings = json.loads(response_text)
            else:
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                findings = json.loads(json_match.group()) if json_match else []

            return {
                "success": True,
                "document_1": doc1_info,
                "document_2": doc2_info,
                "inconsistencies_found": len(findings),
                "inconsistencies": findings[:10],
                "message": f"Found {len(findings)} inconsistencies between documents"
            }

        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    def _tool_generate_report(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and save consistency report."""
        institution_id = tool_input.get("institution_id", "")

        if not institution_id:
            return {"error": "institution_id is required"}

        report = self._get_or_create_report(institution_id)

        # Determine overall status if not set
        if report.overall_status == "pending":
            critical = len([i for i in report.inconsistencies if i.severity == InconsistencySeverity.CRITICAL])
            if critical > 0:
                report.overall_status = "critical_issues"
            elif len(report.inconsistencies) > 0:
                report.overall_status = "issues_found"
            else:
                report.overall_status = "clean"

        # Save to workspace
        if self.workspace_manager:
            report_path = f"consistency_reports/{report.id}.json"
            self.workspace_manager.save_file(
                institution_id,
                report_path,
                json.dumps(report.to_dict(), indent=2).encode("utf-8"),
                create_version=False
            )
            self.session.artifacts_created.append(report_path)

        return {
            "success": True,
            "report": report.to_dict(),
            "saved_path": f"consistency_reports/{report.id}.json",
            "message": f"Generated consistency report with {len(report.inconsistencies)} findings"
        }

    # =========================================================================
    # Workflow Methods
    # =========================================================================

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a consistency workflow."""
        if action == "full_scan":
            result = self._tool_full_scan(inputs)
            if "error" in result:
                return AgentResult.error(result["error"])

            # Generate report
            report_result = self._tool_generate_report(inputs)

            return AgentResult.success(
                data={
                    "scan": result,
                    "report": report_result.get("report", {}),
                },
                confidence=0.8,
                artifacts=[report_result.get("saved_path", "")],
            )

        elif action == "check_policy":
            result = self._tool_check_policy(inputs)
            if "error" in result:
                return AgentResult.error(result["error"])
            return AgentResult.success(data=result, confidence=0.8)

        return AgentResult.error(f"Unknown workflow: {action}")
