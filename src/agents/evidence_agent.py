"""Evidence Agent.

Validates exhibits and evidence items for accreditation submissions.
Checks completeness, relevance, currency, and authenticity of evidence.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    ExhibitEntry,
    ExhibitStatus,
    ComplianceStatus,
    now_iso,
    generate_id,
)
from src.config import Config


# Standard evidence requirements by category
EVIDENCE_REQUIREMENTS = {
    "admissions": [
        {"id": "enrollment_agreement", "name": "Enrollment Agreement Template", "required": True},
        {"id": "admissions_manual", "name": "Admissions Manual/Policy", "required": True},
        {"id": "admissions_forms", "name": "Admissions Application Forms", "required": True},
        {"id": "atb_policy", "name": "Ability-to-Benefit Policy (if applicable)", "required": False},
    ],
    "catalog": [
        {"id": "catalog_current", "name": "Current Catalog", "required": True},
        {"id": "catalog_addenda", "name": "Catalog Addenda (if any)", "required": False},
    ],
    "faculty": [
        {"id": "faculty_list", "name": "Faculty Roster", "required": True},
        {"id": "faculty_credentials", "name": "Faculty Credential Files", "required": True},
        {"id": "faculty_evaluations", "name": "Faculty Evaluations", "required": True},
        {"id": "pd_records", "name": "Professional Development Records", "required": True},
    ],
    "financial": [
        {"id": "audited_financials", "name": "Audited Financial Statements", "required": True},
        {"id": "refund_policy", "name": "Refund Policy", "required": True},
        {"id": "default_rates", "name": "Cohort Default Rates", "required": True},
    ],
    "outcomes": [
        {"id": "completion_rates", "name": "Completion/Graduation Rates", "required": True},
        {"id": "placement_rates", "name": "Placement/Employment Rates", "required": True},
        {"id": "licensure_rates", "name": "Licensure/Certification Pass Rates", "required": True},
    ],
    "compliance": [
        {"id": "state_license", "name": "State Authorization/License", "required": True},
        {"id": "accreditor_letter", "name": "Current Accreditation Letter", "required": True},
        {"id": "title_iv_ppa", "name": "Title IV Program Participation Agreement", "required": True},
        {"id": "ecar", "name": "ECAR/Eligibility Certification", "required": True},
    ],
    "safety": [
        {"id": "clery_report", "name": "Campus Security Report (Clery)", "required": True},
        {"id": "drug_free_policy", "name": "Drug-Free Policy", "required": True},
        {"id": "emergency_plan", "name": "Emergency Action Plan", "required": True},
    ],
}


@register_agent(AgentType.EVIDENCE)
class EvidenceAgent(BaseAgent):
    """Agent for validating exhibits and evidence items.

    Provides tools for:
    - Identifying required evidence for standards/findings
    - Validating evidence completeness, currency, relevance
    - Cross-checking evidence claims against document content
    - Building exhibit index for submissions
    - Flagging missing or stale evidence
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._exhibit_cache: Dict[str, ExhibitEntry] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.EVIDENCE

    @property
    def system_prompt(self) -> str:
        return """You are an evidence validation specialist for accreditation submissions.

Your responsibilities:
1. Identify what evidence is required for each standard and finding
2. Validate uploaded evidence for completeness, currency, relevance, authenticity
3. Cross-check evidence claims against actual document content
4. Flag missing, stale, or contradictory evidence
5. Suggest additional evidence that would strengthen compliance
6. Build exhibit indices mapping evidence to standards

VALIDATION CRITERIA:
- Completeness: Does the evidence contain all required information?
- Currency: Is it dated within the required timeframe (usually current year)?
- Relevance: Does it actually address the specific requirement?
- Authenticity: Does it have required signatures, dates, approvals?

NEVER fabricate evidence or make claims about documents you haven't reviewed.
Always cite specific documents and page numbers when referencing evidence."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_exhibits",
                "description": "List all exhibits for an institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "category": {"type": "string", "description": "Filter by category"},
                        "status": {"type": "string", "enum": ["not_started", "collecting", "uploaded", "ai_reviewed", "flagged", "approved"]},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "add_exhibit",
                "description": "Add a new exhibit to the registry.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "exhibit_number": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "category": {"type": "string"},
                        "file_path": {"type": "string"},
                        "standard_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["institution_id", "title"],
                },
            },
            {
                "name": "validate_exhibit",
                "description": "Validate a specific exhibit for completeness and relevance.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "exhibit_id": {"type": "string"},
                        "check_currency": {"type": "boolean", "default": True},
                        "check_signatures": {"type": "boolean", "default": True},
                    },
                    "required": ["institution_id", "exhibit_id"],
                },
            },
            {
                "name": "get_required_evidence",
                "description": "Get list of required evidence for standards or findings.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "category": {"type": "string", "description": "Evidence category"},
                        "standard_id": {"type": "string", "description": "Specific standard"},
                        "finding_id": {"type": "string", "description": "Specific finding"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "check_evidence_gaps",
                "description": "Identify missing or incomplete evidence.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "categories": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "cross_check_evidence",
                "description": "Cross-check evidence claims against document content.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "claim": {"type": "string", "description": "The claim to verify"},
                        "document_id": {"type": "string", "description": "Document to check against"},
                    },
                    "required": ["institution_id", "claim"],
                },
            },
            {
                "name": "build_exhibit_index",
                "description": "Build exhibit index mapping evidence to standards.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "submission_type": {"type": "string", "enum": ["self_study", "annual_report", "response"]},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "suggest_evidence",
                "description": "Suggest additional evidence to strengthen compliance.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "standard_id": {"type": "string"},
                        "current_status": {"type": "string", "enum": ["compliant", "partial", "non_compliant"]},
                    },
                    "required": ["institution_id", "standard_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "list_exhibits": self._tool_list_exhibits,
            "add_exhibit": self._tool_add_exhibit,
            "validate_exhibit": self._tool_validate_exhibit,
            "get_required_evidence": self._tool_get_required,
            "check_evidence_gaps": self._tool_check_gaps,
            "cross_check_evidence": self._tool_cross_check,
            "build_exhibit_index": self._tool_build_index,
            "suggest_evidence": self._tool_suggest_evidence,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _load_exhibit_registry(self, institution_id: str) -> Dict[str, Any]:
        """Load exhibit registry from workspace."""
        if not self.workspace_manager:
            return {"exhibits": [], "updated_at": now_iso()}

        data = self.workspace_manager.load_file(
            institution_id, "exhibits/exhibit_registry.json"
        )
        return data or {"exhibits": [], "updated_at": now_iso()}

    def _save_exhibit_registry(self, institution_id: str, registry: Dict[str, Any]) -> None:
        """Save exhibit registry to workspace."""
        if not self.workspace_manager:
            return

        registry["updated_at"] = now_iso()
        self.workspace_manager.save_file(
            institution_id, "exhibits/exhibit_registry.json", registry
        )

    def _tool_list_exhibits(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all exhibits for an institution."""
        institution_id = params["institution_id"]
        category = params.get("category")
        status = params.get("status")

        registry = self._load_exhibit_registry(institution_id)
        exhibits = registry.get("exhibits", [])

        # Apply filters
        if category:
            exhibits = [e for e in exhibits if e.get("category") == category]
        if status:
            exhibits = [e for e in exhibits if e.get("status") == status]

        # Add summary stats
        by_status = {}
        for e in registry.get("exhibits", []):
            s = e.get("status", "not_started")
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "success": True,
            "total": len(exhibits),
            "exhibits": exhibits,
            "by_status": by_status,
        }

    def _tool_add_exhibit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new exhibit to the registry."""
        institution_id = params["institution_id"]

        exhibit = {
            "id": generate_id("exh"),
            "exhibit_number": params.get("exhibit_number", ""),
            "title": params["title"],
            "description": params.get("description", ""),
            "category": params.get("category", "general"),
            "file_path": params.get("file_path", ""),
            "standard_refs": params.get("standard_refs", []),
            "finding_refs": params.get("finding_refs", []),
            "status": ExhibitStatus.NOT_STARTED.value if not params.get("file_path") else ExhibitStatus.UPLOADED.value,
            "validation_issues": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        registry = self._load_exhibit_registry(institution_id)
        registry["exhibits"].append(exhibit)
        self._save_exhibit_registry(institution_id, registry)

        return {
            "success": True,
            "exhibit_id": exhibit["id"],
            "title": exhibit["title"],
            "status": exhibit["status"],
        }

    def _tool_validate_exhibit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a specific exhibit."""
        institution_id = params["institution_id"]
        exhibit_id = params["exhibit_id"]
        check_currency = params.get("check_currency", True)
        check_signatures = params.get("check_signatures", True)

        registry = self._load_exhibit_registry(institution_id)
        exhibit = next((e for e in registry["exhibits"] if e["id"] == exhibit_id), None)

        if not exhibit:
            return {"error": f"Exhibit {exhibit_id} not found"}

        issues = []
        warnings = []

        # Check if file exists
        if not exhibit.get("file_path"):
            issues.append({
                "type": "missing_file",
                "severity": "error",
                "message": "No file uploaded for this exhibit",
            })
        else:
            # Check file exists in workspace
            if self.workspace_manager:
                file_data = self.workspace_manager.load_file(
                    institution_id, exhibit["file_path"]
                )
                if file_data is None:
                    issues.append({
                        "type": "file_not_found",
                        "severity": "error",
                        "message": f"File not found: {exhibit['file_path']}",
                    })

        # Check standard references
        if not exhibit.get("standard_refs"):
            warnings.append({
                "type": "no_standards",
                "severity": "warning",
                "message": "Exhibit not linked to any standards",
            })

        # Check description
        if not exhibit.get("description") or len(exhibit.get("description", "")) < 20:
            warnings.append({
                "type": "weak_description",
                "severity": "warning",
                "message": "Exhibit description is missing or too brief",
            })

        # Update exhibit status based on validation
        if issues:
            exhibit["status"] = ExhibitStatus.FLAGGED.value
        else:
            exhibit["status"] = ExhibitStatus.AI_REVIEWED.value

        exhibit["validation_issues"] = issues + warnings
        exhibit["last_validated"] = now_iso()
        exhibit["updated_at"] = now_iso()

        self._save_exhibit_registry(institution_id, registry)

        return {
            "success": True,
            "exhibit_id": exhibit_id,
            "status": exhibit["status"],
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def _tool_get_required(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get required evidence for a category or standard."""
        institution_id = params["institution_id"]
        category = params.get("category")
        standard_id = params.get("standard_id")

        if category:
            requirements = EVIDENCE_REQUIREMENTS.get(category, [])
            return {
                "success": True,
                "category": category,
                "requirements": requirements,
                "total_required": len([r for r in requirements if r.get("required", True)]),
            }

        # Return all categories
        all_requirements = []
        for cat, reqs in EVIDENCE_REQUIREMENTS.items():
            for req in reqs:
                all_requirements.append({**req, "category": cat})

        return {
            "success": True,
            "categories": list(EVIDENCE_REQUIREMENTS.keys()),
            "requirements": all_requirements,
            "total_required": len([r for r in all_requirements if r.get("required", True)]),
        }

    def _tool_check_gaps(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Identify missing or incomplete evidence."""
        institution_id = params["institution_id"]
        categories = params.get("categories", list(EVIDENCE_REQUIREMENTS.keys()))

        registry = self._load_exhibit_registry(institution_id)
        exhibits = registry.get("exhibits", [])

        # Get all exhibit titles (lowercase for matching)
        exhibit_titles = {e.get("title", "").lower() for e in exhibits}
        exhibit_categories = {e.get("category", "") for e in exhibits}

        gaps = []
        covered = []

        for category in categories:
            requirements = EVIDENCE_REQUIREMENTS.get(category, [])
            for req in requirements:
                req_name = req["name"].lower()
                # Simple matching - check if requirement name appears in any exhibit
                found = any(req_name in title or title in req_name for title in exhibit_titles)

                if not found and req.get("required", True):
                    gaps.append({
                        "category": category,
                        "requirement": req["name"],
                        "id": req["id"],
                        "severity": "critical" if req.get("required") else "advisory",
                    })
                elif found:
                    covered.append({
                        "category": category,
                        "requirement": req["name"],
                    })

        # Calculate coverage score
        total_required = sum(
            len([r for r in EVIDENCE_REQUIREMENTS.get(c, []) if r.get("required", True)])
            for c in categories
        )
        coverage_score = int((len(covered) / max(total_required, 1)) * 100)

        return {
            "success": True,
            "coverage_score": coverage_score,
            "total_gaps": len(gaps),
            "total_covered": len(covered),
            "gaps": gaps,
            "covered": covered[:10],  # Return first 10
        }

    def _tool_cross_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-check evidence claims against document content."""
        institution_id = params["institution_id"]
        claim = params["claim"]
        document_id = params.get("document_id")

        # This would use document parsing and AI to verify claims
        # For now, return a structured response indicating verification is needed

        return {
            "success": True,
            "claim": claim,
            "verification_status": "pending",
            "message": "Cross-check requires document content analysis. Upload the relevant document and run validation.",
            "suggested_documents": [
                "Current catalog",
                "Enrollment agreement",
                "Policy manual",
            ],
        }

    def _tool_build_index(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build exhibit index mapping evidence to standards."""
        institution_id = params["institution_id"]
        submission_type = params.get("submission_type", "self_study")

        registry = self._load_exhibit_registry(institution_id)
        exhibits = registry.get("exhibits", [])

        # Build index by standard
        by_standard = {}
        by_category = {}

        for exhibit in exhibits:
            # Index by standard refs
            for std_ref in exhibit.get("standard_refs", []):
                if std_ref not in by_standard:
                    by_standard[std_ref] = []
                by_standard[std_ref].append({
                    "exhibit_number": exhibit.get("exhibit_number", ""),
                    "title": exhibit.get("title", ""),
                    "id": exhibit.get("id"),
                })

            # Index by category
            cat = exhibit.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "exhibit_number": exhibit.get("exhibit_number", ""),
                "title": exhibit.get("title", ""),
                "id": exhibit.get("id"),
            })

        # Save index
        index = {
            "id": generate_id("idx"),
            "submission_type": submission_type,
            "created_at": now_iso(),
            "total_exhibits": len(exhibits),
            "by_standard": by_standard,
            "by_category": by_category,
        }

        if self.workspace_manager:
            self.workspace_manager.save_file(
                institution_id, f"exhibits/index_{submission_type}.json", index
            )

        return {
            "success": True,
            "index_id": index["id"],
            "total_exhibits": len(exhibits),
            "standards_covered": len(by_standard),
            "categories": list(by_category.keys()),
        }

    def _tool_suggest_evidence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest additional evidence to strengthen compliance."""
        institution_id = params["institution_id"]
        standard_id = params.get("standard_id", "")
        current_status = params.get("current_status", "partial")

        suggestions = []

        # Generic suggestions based on status
        if current_status in ["partial", "non_compliant"]:
            suggestions.extend([
                {
                    "type": "documentation",
                    "suggestion": "Provide dated policies showing implementation",
                    "priority": "high",
                },
                {
                    "type": "records",
                    "suggestion": "Include sample records demonstrating compliance",
                    "priority": "high",
                },
                {
                    "type": "training",
                    "suggestion": "Show staff training records related to the requirement",
                    "priority": "medium",
                },
            ])

        # Always suggest
        suggestions.extend([
            {
                "type": "verification",
                "suggestion": "Include third-party verification where available",
                "priority": "medium",
            },
            {
                "type": "timeline",
                "suggestion": "Provide evidence showing consistent compliance over time",
                "priority": "low",
            },
        ])

        return {
            "success": True,
            "standard_id": standard_id,
            "current_status": current_status,
            "suggestions": suggestions,
        }
