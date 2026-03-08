"""Team Report Response Agent.

Handles accreditor team visit report findings and drafts institutional responses:
- Parse team reports to extract findings
- Categorize findings by severity, standard, timeline
- Draft professional responses with evidence citations
- Create action plans for remediation
- Export response packets for submission
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, AgentResult, now_iso, generate_id
from src.config import Config


@dataclass
class TeamReportFinding:
    """A finding extracted from accreditor team report."""
    id: str = field(default_factory=lambda: generate_id("trf"))
    finding_number: str = ""
    standard_reference: str = ""
    severity: str = "moderate"  # critical, moderate, minor, observation
    finding_text: str = ""
    requirement_text: str = ""
    evidence_cited: List[str] = field(default_factory=list)
    response_deadline: Optional[str] = None
    response_status: str = "pending"  # pending, drafted, reviewed, submitted
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_number": self.finding_number,
            "standard_reference": self.standard_reference,
            "severity": self.severity,
            "finding_text": self.finding_text,
            "requirement_text": self.requirement_text,
            "evidence_cited": self.evidence_cited,
            "response_deadline": self.response_deadline,
            "response_status": self.response_status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamReportFinding":
        known_fields = {
            "id", "finding_number", "standard_reference", "severity",
            "finding_text", "requirement_text", "evidence_cited",
            "response_deadline", "response_status", "created_at"
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class FindingResponse:
    """Institution's response to a team report finding."""
    id: str = field(default_factory=lambda: generate_id("resp"))
    finding_id: str = ""
    response_text: str = ""
    evidence_refs: List[Dict[str, str]] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    word_count: int = 0
    ai_confidence: float = 0.0
    requires_review: bool = True
    reviewer_notes: str = ""
    status: str = "draft"  # draft, reviewed, approved, submitted
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "response_text": self.response_text,
            "evidence_refs": self.evidence_refs,
            "action_items": self.action_items,
            "word_count": self.word_count,
            "ai_confidence": self.ai_confidence,
            "requires_review": self.requires_review,
            "reviewer_notes": self.reviewer_notes,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class TeamReport:
    """A parsed accreditor team visit report."""
    id: str = field(default_factory=lambda: generate_id("tr"))
    institution_id: str = ""
    accreditor_code: str = ""
    visit_date: str = ""
    report_date: str = ""
    team_chair: str = ""
    findings: List[TeamReportFinding] = field(default_factory=list)
    commendations: List[str] = field(default_factory=list)
    response_due_date: str = ""
    overall_recommendation: str = ""  # reaffirm, defer, warning, probation, withdraw
    status: str = "received"  # received, analyzing, responding, submitted
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "accreditor_code": self.accreditor_code,
            "visit_date": self.visit_date,
            "report_date": self.report_date,
            "team_chair": self.team_chair,
            "findings": [f.to_dict() for f in self.findings],
            "commendations": self.commendations,
            "response_due_date": self.response_due_date,
            "overall_recommendation": self.overall_recommendation,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamReport":
        findings_data = data.pop("findings", [])
        findings = [TeamReportFinding.from_dict(f) for f in findings_data]
        known_fields = {
            "id", "institution_id", "accreditor_code", "visit_date",
            "report_date", "team_chair", "commendations", "response_due_date",
            "overall_recommendation", "status", "created_at", "updated_at"
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(findings=findings, **filtered)


@register_agent(AgentType.TEAM_REPORT)
class TeamReportAgent(BaseAgent):
    """Agent for parsing team reports and drafting institutional responses."""

    def __init__(self, session: AgentSession, workspace_manager=None, on_update=None):
        super().__init__(session, workspace_manager, on_update)
        self._current_report: Optional[TeamReport] = None
        self._responses: Dict[str, FindingResponse] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.TEAM_REPORT

    @property
    def system_prompt(self) -> str:
        return """You are an expert accreditation response specialist. Your role is to help
institutions respond professionally and effectively to accreditor team visit reports.

EXPERTISE:
- Deep understanding of accreditation standards and processes
- Knowledge of proper response formats and evidence requirements
- Experience with remediation planning and timeline management

RESPONSE STYLE:
- Professional, formal third-person voice
- Evidence-based with specific citations
- Clear action items with responsible parties and deadlines
- Acknowledge findings without being defensive

REQUIREMENTS:
- Every response must reference supporting evidence
- Include specific corrective actions with timelines
- Flag any gaps in available evidence
- Prioritize findings by severity for response order"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "parse_team_report",
                "description": "Parse an accreditor team report document to extract findings, commendations, and recommendations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "accreditor_code": {"type": "string", "description": "Accreditor code (e.g., ACCSC, SACSCOC)"},
                        "report_text": {"type": "string", "description": "Full text of the team report"},
                        "visit_date": {"type": "string", "description": "Date of the site visit (YYYY-MM-DD)"},
                        "response_due_date": {"type": "string", "description": "Deadline for institutional response"},
                    },
                    "required": ["institution_id", "report_text"],
                },
            },
            {
                "name": "categorize_finding",
                "description": "Categorize a finding by severity, standard area, and response timeline.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "Finding ID to categorize"},
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "moderate", "minor", "observation"],
                            "description": "Severity level"
                        },
                        "standard_area": {"type": "string", "description": "Standard area category"},
                        "response_priority": {
                            "type": "integer",
                            "description": "Priority order (1=highest)"
                        },
                    },
                    "required": ["finding_id", "severity"],
                },
            },
            {
                "name": "draft_response",
                "description": "Draft a professional response narrative for a specific finding.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "Finding ID to respond to"},
                        "evidence_summary": {"type": "string", "description": "Summary of available evidence"},
                        "corrective_actions": {"type": "string", "description": "Planned corrective actions"},
                        "responsible_party": {"type": "string", "description": "Person/role responsible"},
                        "completion_date": {"type": "string", "description": "Target completion date"},
                    },
                    "required": ["finding_id"],
                },
            },
            {
                "name": "gather_evidence",
                "description": "Search for and gather evidence to support a finding response.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "Finding ID needing evidence"},
                        "evidence_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of evidence to search for"
                        },
                        "search_query": {"type": "string", "description": "Search query for evidence"},
                    },
                    "required": ["finding_id"],
                },
            },
            {
                "name": "create_action_plan",
                "description": "Create a detailed action plan for addressing a finding.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "Finding ID"},
                        "action_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "responsible_party": {"type": "string"},
                                    "due_date": {"type": "string"},
                                    "deliverables": {"type": "array", "items": {"type": "string"}},
                                },
                            },
                            "description": "List of action items"
                        },
                    },
                    "required": ["finding_id", "action_items"],
                },
            },
            {
                "name": "validate_response",
                "description": "Validate a response meets accreditor requirements.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "Finding ID"},
                        "response_id": {"type": "string", "description": "Response ID to validate"},
                    },
                    "required": ["finding_id"],
                },
            },
            {
                "name": "export_response_packet",
                "description": "Export all responses as a submission-ready document packet.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "report_id": {"type": "string", "description": "Team report ID"},
                        "format": {
                            "type": "string",
                            "enum": ["docx", "pdf", "json"],
                            "description": "Export format"
                        },
                        "include_evidence": {"type": "boolean", "description": "Include evidence attachments"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "get_report_status",
                "description": "Get the current status of team report analysis and responses.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "report_id": {"type": "string", "description": "Team report ID"},
                    },
                    "required": [],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "parse_team_report": self._tool_parse_report,
            "categorize_finding": self._tool_categorize_finding,
            "draft_response": self._tool_draft_response,
            "gather_evidence": self._tool_gather_evidence,
            "create_action_plan": self._tool_create_action_plan,
            "validate_response": self._tool_validate_response,
            "export_response_packet": self._tool_export_packet,
            "get_report_status": self._tool_get_status,
        }
        handler = handlers.get(tool_name)
        return handler(tool_input) if handler else {"error": f"Unknown tool: {tool_name}"}

    def _tool_parse_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse team report to extract findings."""
        institution_id = params.get("institution_id", "")
        accreditor_code = params.get("accreditor_code", "")
        report_text = params.get("report_text", "")
        visit_date = params.get("visit_date", "")
        response_due_date = params.get("response_due_date", "")

        if not report_text:
            return {"error": "Report text is required"}

        # Use AI to parse the report
        prompt = f"""Analyze this accreditor team report and extract structured information.

REPORT TEXT:
{report_text[:8000]}  # Truncate for context limits

Extract the following in JSON format:
{{
    "team_chair": "Name of team chair",
    "visit_date": "YYYY-MM-DD or from text",
    "overall_recommendation": "reaffirm|defer|warning|probation|withdraw",
    "commendations": ["List of commendations"],
    "findings": [
        {{
            "finding_number": "Finding identifier",
            "standard_reference": "Standard number/section",
            "severity": "critical|moderate|minor|observation",
            "finding_text": "Full finding text",
            "requirement_text": "The requirement not met"
        }}
    ]
}}

Be thorough - extract ALL findings mentioned."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse the AI response
            content = response.content[0].text

            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                return {"error": "Could not parse report structure"}

            # Create findings
            findings = []
            for f_data in parsed.get("findings", []):
                finding = TeamReportFinding(
                    finding_number=f_data.get("finding_number", ""),
                    standard_reference=f_data.get("standard_reference", ""),
                    severity=f_data.get("severity", "moderate"),
                    finding_text=f_data.get("finding_text", ""),
                    requirement_text=f_data.get("requirement_text", ""),
                )
                findings.append(finding)

            # Create team report
            self._current_report = TeamReport(
                institution_id=institution_id,
                accreditor_code=accreditor_code,
                visit_date=visit_date or parsed.get("visit_date", ""),
                team_chair=parsed.get("team_chair", ""),
                findings=findings,
                commendations=parsed.get("commendations", []),
                response_due_date=response_due_date,
                overall_recommendation=parsed.get("overall_recommendation", ""),
                status="analyzing",
            )

            # Save to workspace
            if self.workspace_manager and institution_id:
                self.workspace_manager.save_file(
                    institution_id,
                    f"responses/team_reports/{self._current_report.id}.json",
                    self._current_report.to_dict()
                )

            return {
                "success": True,
                "report_id": self._current_report.id,
                "findings_count": len(findings),
                "commendations_count": len(self._current_report.commendations),
                "overall_recommendation": self._current_report.overall_recommendation,
                "findings_summary": [
                    {
                        "id": f.id,
                        "number": f.finding_number,
                        "severity": f.severity,
                        "standard": f.standard_reference,
                    }
                    for f in findings
                ],
            }

        except Exception as e:
            return {"error": str(e)}

    def _tool_categorize_finding(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize a finding."""
        finding_id = params.get("finding_id", "")
        severity = params.get("severity", "")
        standard_area = params.get("standard_area", "")

        if not self._current_report:
            return {"error": "No team report loaded"}

        finding = None
        for f in self._current_report.findings:
            if f.id == finding_id:
                finding = f
                break

        if not finding:
            return {"error": f"Finding {finding_id} not found"}

        if severity:
            finding.severity = severity

        return {
            "success": True,
            "finding_id": finding_id,
            "severity": finding.severity,
            "standard_area": standard_area or finding.standard_reference,
        }

    def _tool_draft_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draft a response for a finding."""
        finding_id = params.get("finding_id", "")
        evidence_summary = params.get("evidence_summary", "")
        corrective_actions = params.get("corrective_actions", "")
        responsible_party = params.get("responsible_party", "")
        completion_date = params.get("completion_date", "")

        if not self._current_report:
            return {"error": "No team report loaded"}

        finding = None
        for f in self._current_report.findings:
            if f.id == finding_id:
                finding = f
                break

        if not finding:
            return {"error": f"Finding {finding_id} not found"}

        # Generate response using AI
        prompt = f"""Write a professional institutional response to this accreditation finding.

FINDING:
Number: {finding.finding_number}
Standard: {finding.standard_reference}
Severity: {finding.severity}
Finding: {finding.finding_text}
Requirement: {finding.requirement_text}

AVAILABLE EVIDENCE:
{evidence_summary or 'None provided - note evidence gaps'}

PLANNED CORRECTIVE ACTIONS:
{corrective_actions or 'None specified'}

RESPONSIBLE PARTY: {responsible_party or 'To be determined'}
TARGET COMPLETION: {completion_date or 'To be determined'}

Write a 200-400 word response that:
1. Acknowledges the finding professionally (without being defensive)
2. Presents evidence of compliance or progress
3. Details specific corrective actions with timeline
4. Identifies responsible parties
5. Commits to ongoing compliance

Use formal third-person voice ("The institution..."). Include [EVIDENCE: description] placeholders where specific evidence should be cited."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text

            # Create response object
            finding_response = FindingResponse(
                finding_id=finding_id,
                response_text=response_text,
                word_count=len(response_text.split()),
                ai_confidence=0.75,
                requires_review=True,
            )

            if corrective_actions:
                finding_response.action_items.append({
                    "description": corrective_actions,
                    "responsible_party": responsible_party,
                    "due_date": completion_date,
                })

            self._responses[finding_id] = finding_response
            finding.response_status = "drafted"

            return {
                "success": True,
                "response_id": finding_response.id,
                "finding_id": finding_id,
                "word_count": finding_response.word_count,
                "response_text": response_text,
                "requires_review": True,
            }

        except Exception as e:
            return {"error": str(e)}

    def _tool_gather_evidence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for evidence to support a response."""
        finding_id = params.get("finding_id", "")
        evidence_types = params.get("evidence_types", [])
        search_query = params.get("search_query", "")

        if not self._current_report:
            return {"error": "No team report loaded"}

        finding = None
        for f in self._current_report.findings:
            if f.id == finding_id:
                finding = f
                break

        if not finding:
            return {"error": f"Finding {finding_id} not found"}

        # Build search query
        query = search_query or f"{finding.standard_reference} {finding.requirement_text}"

        evidence_found = []

        # Search workspace documents if available
        if self.workspace_manager and self._current_report.institution_id:
            try:
                # Get document list
                docs = self.workspace_manager.list_documents(
                    self._current_report.institution_id
                )

                # Filter by evidence types if specified
                relevant_types = evidence_types or [
                    "policy", "procedure", "catalog", "report", "form"
                ]

                for doc in docs[:10]:  # Limit search
                    doc_type = doc.get("doc_type", "").lower()
                    if any(t.lower() in doc_type for t in relevant_types):
                        evidence_found.append({
                            "document_id": doc.get("id", ""),
                            "title": doc.get("title", doc.get("filename", "")),
                            "type": doc_type,
                            "relevance": "potential",
                        })

            except Exception:
                pass

        return {
            "success": True,
            "finding_id": finding_id,
            "query": query,
            "evidence_count": len(evidence_found),
            "evidence": evidence_found,
            "evidence_types_searched": evidence_types or ["all"],
        }

    def _tool_create_action_plan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create an action plan for a finding."""
        finding_id = params.get("finding_id", "")
        action_items = params.get("action_items", [])

        if not self._current_report:
            return {"error": "No team report loaded"}

        if finding_id not in self._responses:
            return {"error": f"No response drafted for finding {finding_id}"}

        response = self._responses[finding_id]
        response.action_items = action_items
        response.updated_at = now_iso()

        return {
            "success": True,
            "finding_id": finding_id,
            "response_id": response.id,
            "action_items_count": len(action_items),
            "action_items": action_items,
        }

    def _tool_validate_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a response meets requirements."""
        finding_id = params.get("finding_id", "")

        if not self._current_report:
            return {"error": "No team report loaded"}

        if finding_id not in self._responses:
            return {"error": f"No response found for finding {finding_id}"}

        response = self._responses[finding_id]
        finding = None
        for f in self._current_report.findings:
            if f.id == finding_id:
                finding = f
                break

        # Validation checks
        issues = []
        warnings = []

        # Check word count
        if response.word_count < 100:
            issues.append("Response is too brief (< 100 words)")
        elif response.word_count < 150:
            warnings.append("Response may be too brief")

        # Check for evidence
        if not response.evidence_refs and "[EVIDENCE:" in response.response_text:
            warnings.append("Evidence placeholders not filled")

        # Check for action items for non-observation findings
        if finding and finding.severity != "observation":
            if not response.action_items:
                if finding.severity == "critical":
                    issues.append("Critical finding requires action items")
                else:
                    warnings.append("Consider adding action items")

        # Check confidence
        if response.ai_confidence < 0.7:
            warnings.append("Low AI confidence - human review recommended")

        is_valid = len(issues) == 0

        return {
            "valid": is_valid,
            "finding_id": finding_id,
            "response_id": response.id,
            "issues": issues,
            "warnings": warnings,
            "word_count": response.word_count,
            "has_evidence": len(response.evidence_refs) > 0,
            "has_action_items": len(response.action_items) > 0,
        }

    def _tool_export_packet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export responses as a submission packet."""
        institution_id = params.get("institution_id", "")
        export_format = params.get("format", "json")
        include_evidence = params.get("include_evidence", False)

        if not self._current_report:
            return {"error": "No team report loaded"}

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        # Build packet data
        packet = {
            "report_id": self._current_report.id,
            "institution_id": institution_id or self._current_report.institution_id,
            "accreditor_code": self._current_report.accreditor_code,
            "visit_date": self._current_report.visit_date,
            "response_date": now_iso()[:10],
            "findings_count": len(self._current_report.findings),
            "responses": [],
        }

        for finding in self._current_report.findings:
            response_data = {
                "finding_number": finding.finding_number,
                "standard_reference": finding.standard_reference,
                "severity": finding.severity,
                "finding_text": finding.finding_text,
                "response_status": finding.response_status,
            }

            if finding.id in self._responses:
                resp = self._responses[finding.id]
                response_data["response"] = {
                    "text": resp.response_text,
                    "evidence_refs": resp.evidence_refs if include_evidence else [],
                    "action_items": resp.action_items,
                    "status": resp.status,
                }

            packet["responses"].append(response_data)

        # Save packet
        filename = f"response_packet_{self._current_report.id}_{now_iso()[:10]}.json"
        path = f"responses/packets/{filename}"

        try:
            self.workspace_manager.save_file(
                institution_id or self._current_report.institution_id,
                path,
                packet
            )

            return {
                "success": True,
                "path": path,
                "format": export_format,
                "findings_count": len(packet["responses"]),
                "responses_drafted": sum(
                    1 for r in packet["responses"]
                    if "response" in r
                ),
            }

        except Exception as e:
            return {"error": str(e)}

    def _tool_get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current report and response status."""
        if not self._current_report:
            return {
                "report_loaded": False,
                "message": "No team report currently loaded",
            }

        findings_by_status = {"pending": 0, "drafted": 0, "reviewed": 0, "submitted": 0}
        findings_by_severity = {"critical": 0, "moderate": 0, "minor": 0, "observation": 0}

        for finding in self._current_report.findings:
            findings_by_status[finding.response_status] = (
                findings_by_status.get(finding.response_status, 0) + 1
            )
            findings_by_severity[finding.severity] = (
                findings_by_severity.get(finding.severity, 0) + 1
            )

        return {
            "report_loaded": True,
            "report_id": self._current_report.id,
            "accreditor_code": self._current_report.accreditor_code,
            "overall_recommendation": self._current_report.overall_recommendation,
            "response_due_date": self._current_report.response_due_date,
            "total_findings": len(self._current_report.findings),
            "findings_by_status": findings_by_status,
            "findings_by_severity": findings_by_severity,
            "commendations_count": len(self._current_report.commendations),
            "responses_drafted": len(self._responses),
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run team report workflow actions."""
        if action == "parse_report":
            result = self._tool_parse_report(inputs)
            if "error" in result:
                return AgentResult.error(result["error"])
            return AgentResult.success(data=result, confidence=0.85)

        elif action == "draft_all_responses":
            if not self._current_report:
                return AgentResult.error("No team report loaded")

            results = []
            for finding in self._current_report.findings:
                resp_result = self._tool_draft_response({"finding_id": finding.id})
                results.append({
                    "finding_id": finding.id,
                    "success": "error" not in resp_result,
                })

            return AgentResult.success(
                data={"responses": results, "total": len(results)},
                confidence=0.75
            )

        return AgentResult.error(f"Unknown workflow: {action}")
