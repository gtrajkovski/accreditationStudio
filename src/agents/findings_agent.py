"""Findings Agent.

Aggregates, prioritizes, and manages compliance findings across all audits
for an institution. Provides a unified view of compliance issues with
prioritization by severity, regulatory source, and remediation status.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    AuditFinding,
    ComplianceStatus,
    FindingSeverity,
    RegulatorySource,
    now_iso,
    generate_id,
)
from src.config import Config


@dataclass
class AggregatedFinding:
    """A finding aggregated across multiple audits/documents."""
    id: str = field(default_factory=lambda: generate_id("agg"))
    item_number: str = ""
    item_description: str = ""
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    regulatory_source: RegulatorySource = RegulatorySource.ACCREDITOR
    regulatory_citation: str = ""
    status: ComplianceStatus = ComplianceStatus.NA
    occurrence_count: int = 0
    documents_affected: List[str] = field(default_factory=list)
    source_findings: List[str] = field(default_factory=list)  # Finding IDs
    evidence_summary: str = ""
    recommendation: str = ""
    remediation_status: str = "pending"  # pending, in_progress, resolved
    priority_score: float = 0.0  # Calculated priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_number": self.item_number,
            "item_description": self.item_description,
            "severity": self.severity.value,
            "regulatory_source": self.regulatory_source.value,
            "regulatory_citation": self.regulatory_citation,
            "status": self.status.value,
            "occurrence_count": self.occurrence_count,
            "documents_affected": self.documents_affected,
            "source_findings": self.source_findings,
            "evidence_summary": self.evidence_summary,
            "recommendation": self.recommendation,
            "remediation_status": self.remediation_status,
            "priority_score": self.priority_score,
        }


@dataclass
class FindingsReport:
    """Aggregated findings report for an institution."""
    id: str = field(default_factory=lambda: generate_id("frpt"))
    institution_id: str = ""
    name: str = ""
    findings: List[AggregatedFinding] = field(default_factory=list)
    total_findings: int = 0
    critical_count: int = 0
    significant_count: int = 0
    advisory_count: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    partial_count: int = 0
    audits_included: List[str] = field(default_factory=list)
    by_regulatory_source: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "name": self.name,
            "findings": [f.to_dict() for f in self.findings],
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "significant_count": self.significant_count,
            "advisory_count": self.advisory_count,
            "compliant_count": self.compliant_count,
            "non_compliant_count": self.non_compliant_count,
            "partial_count": self.partial_count,
            "audits_included": self.audits_included,
            "by_regulatory_source": self.by_regulatory_source,
            "by_category": self.by_category,
            "created_at": self.created_at,
        }


@register_agent(AgentType.GAP_FINDER)
class FindingsAgent(BaseAgent):
    """Agent for aggregating and prioritizing compliance findings.

    Consolidates findings across audits, calculates priority scores,
    and generates actionable reports for remediation planning.
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._current_report: Optional[FindingsReport] = None
        self._all_findings: List[AuditFinding] = []

    @property
    def agent_type(self) -> AgentType:
        return AgentType.GAP_FINDER

    @property
    def system_prompt(self) -> str:
        return """You are a compliance findings analyst. Your job is to:

1. Aggregate findings from multiple audits into a unified view
2. Calculate priority scores based on severity, regulatory source, and frequency
3. Identify patterns and systemic issues across documents
4. Generate actionable recommendations for remediation
5. Track remediation progress

Priority scoring factors:
- Critical severity: +100 points
- Significant severity: +50 points
- Federal regulation: +30 points
- Multiple occurrences: +10 per occurrence
- Non-compliant status: +20 points

Always prioritize findings that could result in:
- Loss of accreditation
- Federal compliance violations
- Student harm or financial impact"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "load_all_findings",
                "description": "Load findings from all audits for an institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "audit_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific audit IDs (optional, loads all if empty)",
                        },
                        "status_filter": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by compliance status",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "aggregate_findings",
                "description": "Aggregate loaded findings by item number, combining duplicates.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "enum": ["item_number", "regulatory_source", "severity"],
                            "default": "item_number",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "calculate_priorities",
                "description": "Calculate priority scores for all aggregated findings.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "weight_severity": {"type": "number", "default": 1.0},
                        "weight_frequency": {"type": "number", "default": 0.5},
                        "weight_regulatory": {"type": "number", "default": 0.8},
                    },
                    "required": [],
                },
            },
            {
                "name": "generate_action_items",
                "description": "Generate prioritized action items from findings using AI.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_items": {"type": "integer", "default": 10},
                        "focus_area": {
                            "type": "string",
                            "description": "Optional focus area (e.g., 'federal', 'critical')",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_findings_summary",
                "description": "Get summary statistics of the current findings report.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "save_report",
                "description": "Save the findings report to workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Report name"},
                    },
                    "required": [],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "load_all_findings": self._tool_load_findings,
            "aggregate_findings": self._tool_aggregate,
            "calculate_priorities": self._tool_calculate_priorities,
            "generate_action_items": self._tool_generate_actions,
            "get_findings_summary": self._tool_get_summary,
            "save_report": self._tool_save_report,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_load_findings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load findings from audits."""
        institution_id = params["institution_id"]
        audit_ids = params.get("audit_ids", [])
        status_filter = params.get("status_filter", [])

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        # Load audits
        audits = self.workspace_manager.list_audits(institution_id)
        if audit_ids:
            audits = [a for a in audits if a["id"] in audit_ids]

        self._all_findings = []
        audit_ids_loaded = []

        for audit_meta in audits:
            audit_data = self.workspace_manager.load_file(
                institution_id, f"audits/{audit_meta['id']}.json"
            )
            if audit_data:
                audit_ids_loaded.append(audit_meta["id"])
                for f_data in audit_data.get("findings", []):
                    finding = AuditFinding.from_dict(f_data)

                    # Apply status filter
                    if status_filter and finding.status.value not in status_filter:
                        continue

                    self._all_findings.append(finding)

        # Initialize report
        self._current_report = FindingsReport(
            institution_id=institution_id,
            audits_included=audit_ids_loaded,
        )

        return {
            "success": True,
            "findings_loaded": len(self._all_findings),
            "audits_processed": len(audit_ids_loaded),
        }

    def _tool_aggregate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate findings."""
        if not self._all_findings:
            return {"error": "No findings loaded"}

        group_by = params.get("group_by", "item_number")

        # Group findings
        groups = defaultdict(list)
        for finding in self._all_findings:
            if group_by == "item_number":
                key = finding.item_number or "unknown"
            elif group_by == "regulatory_source":
                key = finding.regulatory_source.value
            elif group_by == "severity":
                key = finding.severity.value
            else:
                key = finding.item_number or "unknown"
            groups[key].append(finding)

        # Create aggregated findings
        aggregated = []
        for key, findings in groups.items():
            # Use the most severe finding as the base
            findings.sort(key=lambda f: (
                ["critical", "significant", "advisory", "informational"].index(f.severity.value)
            ))
            base = findings[0]

            # Collect unique documents
            docs = list(set(f.audit_id for f in findings))

            # Combine evidence
            evidence_parts = [f.evidence_in_document for f in findings if f.evidence_in_document]
            evidence_summary = " | ".join(evidence_parts[:3])

            # Determine overall status (worst case)
            statuses = [f.status for f in findings]
            if ComplianceStatus.NON_COMPLIANT in statuses:
                overall_status = ComplianceStatus.NON_COMPLIANT
            elif ComplianceStatus.PARTIAL in statuses:
                overall_status = ComplianceStatus.PARTIAL
            elif ComplianceStatus.COMPLIANT in statuses:
                overall_status = ComplianceStatus.COMPLIANT
            else:
                overall_status = ComplianceStatus.NA

            agg = AggregatedFinding(
                item_number=base.item_number,
                item_description=base.item_description,
                severity=base.severity,
                regulatory_source=base.regulatory_source,
                regulatory_citation=base.regulatory_citation,
                status=overall_status,
                occurrence_count=len(findings),
                documents_affected=docs,
                source_findings=[f.id for f in findings],
                evidence_summary=evidence_summary[:500],
                recommendation=base.recommendation,
            )
            aggregated.append(agg)

        self._current_report.findings = aggregated
        self._update_report_stats()

        return {
            "success": True,
            "aggregated_findings": len(aggregated),
            "grouped_by": group_by,
        }

    def _tool_calculate_priorities(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate priority scores."""
        if not self._current_report or not self._current_report.findings:
            return {"error": "No aggregated findings"}

        w_severity = params.get("weight_severity", 1.0)
        w_frequency = params.get("weight_frequency", 0.5)
        w_regulatory = params.get("weight_regulatory", 0.8)

        severity_scores = {
            "critical": 100,
            "significant": 50,
            "advisory": 20,
            "informational": 5,
        }

        regulatory_scores = {
            "federal_title_iv": 30,
            "federal_ferpa": 25,
            "federal_title_ix": 25,
            "accreditor": 20,
            "state": 15,
            "professional": 10,
            "institutional": 5,
        }

        status_scores = {
            "non_compliant": 20,
            "partial": 10,
            "compliant": 0,
            "na": 0,
        }

        for finding in self._current_report.findings:
            score = 0

            # Severity component
            score += severity_scores.get(finding.severity.value, 0) * w_severity

            # Frequency component
            score += finding.occurrence_count * 10 * w_frequency

            # Regulatory source component
            score += regulatory_scores.get(finding.regulatory_source.value, 0) * w_regulatory

            # Status component
            score += status_scores.get(finding.status.value, 0)

            finding.priority_score = round(score, 1)

        # Sort by priority
        self._current_report.findings.sort(key=lambda f: f.priority_score, reverse=True)

        return {
            "success": True,
            "findings_scored": len(self._current_report.findings),
            "top_priority": self._current_report.findings[0].to_dict() if self._current_report.findings else None,
        }

    def _tool_generate_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate action items using AI."""
        if not self._current_report or not self._current_report.findings:
            return {"error": "No findings to process"}

        max_items = params.get("max_items", 10)
        focus_area = params.get("focus_area", "")

        # Filter findings if focus area specified
        findings = self._current_report.findings[:max_items * 2]
        if focus_area == "critical":
            findings = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        elif focus_area == "federal":
            findings = [f for f in findings if "federal" in f.regulatory_source.value]

        findings = findings[:max_items]

        # Build context for AI
        findings_text = "\n".join([
            f"- [{f.severity.value.upper()}] {f.item_number}: {f.item_description} "
            f"(Status: {f.status.value}, Occurrences: {f.occurrence_count})"
            for f in findings
        ])

        prompt = f"""Based on these compliance findings, generate a prioritized action plan.

Findings:
{findings_text}

For each finding, provide:
1. Immediate action required
2. Responsible party suggestion
3. Estimated effort (low/medium/high)
4. Dependencies on other actions

Format as a numbered list of action items."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            action_plan = response.content[0].text

            return {
                "success": True,
                "findings_processed": len(findings),
                "action_plan": action_plan,
            }
        except Exception as e:
            return {"error": f"AI generation failed: {str(e)}"}

    def _tool_get_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get report summary."""
        if not self._current_report:
            return {"error": "No report loaded"}

        self._update_report_stats()

        return {
            "institution_id": self._current_report.institution_id,
            "total_findings": self._current_report.total_findings,
            "critical_count": self._current_report.critical_count,
            "significant_count": self._current_report.significant_count,
            "advisory_count": self._current_report.advisory_count,
            "non_compliant_count": self._current_report.non_compliant_count,
            "partial_count": self._current_report.partial_count,
            "compliant_count": self._current_report.compliant_count,
            "audits_included": len(self._current_report.audits_included),
            "by_regulatory_source": self._current_report.by_regulatory_source,
        }

    def _tool_save_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save report to workspace."""
        if not self._current_report:
            return {"error": "No report to save"}

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        name = params.get("name", f"Findings Report {now_iso()[:10]}")
        self._current_report.name = name

        filename = f"findings/{self._current_report.id}.json"
        self.workspace_manager.save_file(
            self._current_report.institution_id,
            filename,
            self._current_report.to_dict(),
        )

        return {
            "success": True,
            "report_id": self._current_report.id,
            "path": filename,
            "total_findings": self._current_report.total_findings,
        }

    def _update_report_stats(self):
        """Update report statistics."""
        if not self._current_report:
            return

        findings = self._current_report.findings
        self._current_report.total_findings = len(findings)
        self._current_report.critical_count = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
        self._current_report.significant_count = sum(1 for f in findings if f.severity == FindingSeverity.SIGNIFICANT)
        self._current_report.advisory_count = sum(1 for f in findings if f.severity == FindingSeverity.ADVISORY)
        self._current_report.non_compliant_count = sum(1 for f in findings if f.status == ComplianceStatus.NON_COMPLIANT)
        self._current_report.partial_count = sum(1 for f in findings if f.status == ComplianceStatus.PARTIAL)
        self._current_report.compliant_count = sum(1 for f in findings if f.status == ComplianceStatus.COMPLIANT)

        # Count by regulatory source
        by_source = defaultdict(int)
        for f in findings:
            by_source[f.regulatory_source.value] += 1
        self._current_report.by_regulatory_source = dict(by_source)

    # Workflow methods
    def generate_findings_report(
        self,
        institution_id: str,
        name: str = "",
    ) -> Dict[str, Any]:
        """Generate a complete findings report."""
        # Load
        result = self._tool_load_findings({"institution_id": institution_id})
        if "error" in result:
            return result

        # Aggregate
        result = self._tool_aggregate({})
        if "error" in result:
            return result

        # Prioritize
        result = self._tool_calculate_priorities({})
        if "error" in result:
            return result

        # Save
        result = self._tool_save_report({"name": name})
        if "error" in result:
            return result

        return self._tool_get_summary({})
