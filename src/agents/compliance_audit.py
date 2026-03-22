"""Compliance Audit Agent.

Runs multi-pass compliance audits against accreditation standards and
regulatory requirements. The core audit engine of AccreditAI.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable, Generator

from src.agents.base_agent import BaseAgent, AgentType

logger = logging.getLogger(__name__)
from src.agents.registry import register_agent
from src.services.audit_reproducibility_service import (
    capture_audit_snapshot,
    save_audit_snapshot,
    record_finding_provenance,
)
from src.core.models import (
    AgentResult,
    AgentSession,
    Audit,
    AuditFinding,
    AuditStatus,
    ComplianceStatus,
    Document,
    DocumentType,
    FindingSeverity,
    RegulatorySource,
    generate_id,
    now_iso,
)


SYSTEM_PROMPT = """You are the Compliance Audit Agent for AccreditAI.

You perform multi-pass compliance audits of institutional documents against accreditation standards and regulatory requirements.

AUDIT WORKFLOW:
1. INITIALIZE: Create audit record and load applicable standards
2. COMPLETENESS PASS: Search for evidence of each requirement
3. STANDARDS PASS: Analyze if evidence actually meets requirements
4. CONSISTENCY PASS: Check for internal contradictions
5. SEVERITY PASS: Assess impact of each finding
6. REMEDIATION PASS: Generate specific fix recommendations
7. FINALIZE: Generate final audit report with summary

FOR EACH FINDING:
- Cite the specific standard (e.g., "ACCSC Section I.A.1")
- Quote the relevant document text verbatim
- Note page numbers when available
- Assess severity based on regulatory impact
- Provide specific remediation steps
- Include confidence score (0-1)

COMPLIANCE DETERMINATION:
- COMPLIANT: Evidence fully satisfies the requirement
- PARTIAL: Evidence addresses requirement but has gaps
- NON_COMPLIANT: Evidence missing or clearly fails requirement
- NA: Requirement does not apply to this document type

SEVERITY LEVELS:
- CRITICAL: Federal compliance violation, immediate action required
- SIGNIFICANT: Accreditor standard violation, must address before submission
- ADVISORY: Best practice gap, should address for stronger compliance
- INFORMATIONAL: Note for awareness, no action required

SAFETY RULES:
- NEVER fabricate evidence or compliance claims
- ALWAYS cite exact text from documents
- Flag low confidence determinations (<0.7) for human review
- When uncertain between statuses, choose the more conservative option
- REQUIRE human confirmation for compliance determinations on critical items"""


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

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update: Optional[Callable[[AgentSession], None]] = None,
    ):
        """Initialize the Compliance Audit Agent."""
        super().__init__(session, workspace_manager, on_update)
        self._audit_cache: Dict[str, Audit] = {}
        self._institution_id: Optional[str] = None
        self._current_snapshot: Optional[Any] = None

    @property
    def agent_type(self) -> AgentType:
        return AgentType.COMPLIANCE_AUDIT

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "initialize_audit",
                "description": "Create and initialize an audit for a document against a standards library. Sets up the audit record and loads applicable checklist items.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to audit"
                        },
                        "standards_library_id": {
                            "type": "string",
                            "description": "Standards library to audit against (e.g., std_accsc)"
                        },
                    },
                    "required": ["institution_id", "document_id", "standards_library_id"]
                }
            },
            {
                "name": "run_completeness_pass",
                "description": "Pass 1: Check document completeness against required checklist items. Uses semantic search to find evidence for each requirement.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit to run pass on"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
            {
                "name": "run_standards_pass",
                "description": "Pass 2: Analyze if found evidence actually meets each standard requirement. Uses AI to evaluate compliance quality.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
            {
                "name": "run_consistency_pass",
                "description": "Pass 3: Check for internal contradictions within the document (e.g., conflicting policy statements, inconsistent numbers).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
            {
                "name": "assess_severity",
                "description": "Pass 4: Assess severity of non-compliant and partial findings based on regulatory impact.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
            {
                "name": "generate_remediation",
                "description": "Pass 5: Generate specific fix recommendations for each finding that needs remediation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
            {
                "name": "finalize_audit",
                "description": "Finalize the audit and generate summary report.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "audit_id": {
                            "type": "string",
                            "description": "ID of the audit"
                        },
                    },
                    "required": ["audit_id"]
                }
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an audit tool."""
        if tool_name == "initialize_audit":
            return self._tool_initialize_audit(tool_input)
        elif tool_name == "run_completeness_pass":
            return self._tool_completeness_pass(tool_input)
        elif tool_name == "run_standards_pass":
            return self._tool_standards_pass(tool_input)
        elif tool_name == "run_consistency_pass":
            return self._tool_consistency_pass(tool_input)
        elif tool_name == "assess_severity":
            return self._tool_assess_severity(tool_input)
        elif tool_name == "generate_remediation":
            return self._tool_generate_remediation(tool_input)
        elif tool_name == "finalize_audit":
            return self._tool_finalize_audit(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _load_document(self, institution_id: str, document_id: str) -> Optional[Document]:
        """Load a document from the workspace."""
        if not self.workspace_manager:
            return None
        institution = self.workspace_manager.load_institution(institution_id)
        if not institution:
            return None
        for doc in institution.documents:
            if doc.id == document_id:
                return doc
        return None

    def _get_document_text(self, institution_id: str, document_id: str) -> Optional[str]:
        """Get full extracted text for a document."""
        doc = self._load_document(institution_id, document_id)
        if not doc:
            return None
        if doc.extracted_text:
            return doc.extracted_text
        # Fallback: try to load from chunks
        if self.workspace_manager:
            chunks_path = f"documents/{document_id}_chunks.json"
            try:
                chunks_data = self.workspace_manager.read_file(institution_id, chunks_path)
                if chunks_data:
                    chunks = json.loads(chunks_data.decode("utf-8"))
                    texts = [c.get("text_anonymized", "") for c in chunks.get("chunks", [])]
                    return "\n\n".join(texts)
            except Exception as e:
                logger.warning(f"Failed to load document chunks: {e}")
        return None

    def _get_applicable_standards(
        self,
        standards_id: str,
        doc_type: DocumentType
    ) -> List[Dict[str, Any]]:
        """Get checklist items applicable to a document type."""
        from src.core.standards_store import get_standards_store
        standards_store = get_standards_store()
        items = standards_store.get_items_for_document_type(standards_id, doc_type)
        return [
            {
                "number": item.number,
                "category": item.category,
                "description": item.description,
                "section_reference": item.section_reference,
            }
            for item in items
        ]

    def _search_for_evidence(
        self,
        institution_id: str,
        query: str,
        document_id: Optional[str] = None,
        n_results: int = 5,
        min_score: float = 0.4
    ) -> List[Dict[str, Any]]:
        """Search for evidence using semantic search."""
        try:
            from src.search import get_search_service
            search_service = get_search_service(institution_id)

            results = search_service.search(
                query=query,
                n_results=n_results,
                document_id=document_id
            )

            evidence = []
            for result in results:
                if result.score >= min_score:
                    evidence.append({
                        "text": result.chunk.text_anonymized if hasattr(result.chunk, 'text_anonymized') else result.chunk.text_redacted,
                        "page_number": getattr(result.chunk, 'page_number', None),
                        "score": result.score,
                        "document_id": result.chunk.document_id,
                    })
            return evidence
        except Exception as e:
            return []

    def _analyze_compliance(
        self,
        item_number: str,
        item_description: str,
        evidence_texts: List[str],
    ) -> Dict[str, Any]:
        """Use AI to analyze if evidence meets the requirement."""
        if not evidence_texts:
            return {
                "status": "non_compliant",
                "confidence": 0.8,
                "reasoning": "No evidence found for this requirement.",
                "evidence_used": "",
                "gaps": ["No relevant content found in document"]
            }

        evidence_combined = "\n---\n".join(evidence_texts[:3])

        prompt = f"""Analyze if the following evidence satisfies this accreditation requirement:

REQUIREMENT:
{item_number}: {item_description}

EVIDENCE FROM DOCUMENT:
{evidence_combined}

Analyze the evidence and determine:
1. Does the evidence FULLY satisfy the requirement? (compliant)
2. Does it PARTIALLY satisfy it with gaps? (partial)
3. Is it clearly NOT compliant? (non_compliant)

Consider:
- Is the requirement explicitly addressed?
- Is the language complete and clear?
- Are there any missing elements?

Respond ONLY with valid JSON in this exact format:
{{"status": "compliant|partial|non_compliant", "confidence": 0.0-1.0, "reasoning": "explanation", "evidence_used": "most relevant quote", "gaps": ["list of gaps if any"]}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are a compliance auditor. Analyze evidence objectively. Never fabricate. Output only valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Record finding provenance (per D-02)
            if self._current_snapshot:
                try:
                    record_finding_provenance(
                        finding_id=f"{self._current_snapshot.audit_run_id}_{item_number}",
                        snapshot_id=self._current_snapshot.id,
                        prompt=prompt,
                        response=response_text,
                        input_tokens=getattr(response.usage, 'input_tokens', 0),
                        output_tokens=getattr(response.usage, 'output_tokens', 0),
                    )
                except Exception as e:
                    logger.warning(f"Failed to record finding provenance: {e}")

            # Try to extract JSON from response
            if response_text.startswith("{"):
                result = json.loads(response_text)
            else:
                # Try to find JSON in response
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {
                        "status": "partial",
                        "confidence": 0.5,
                        "reasoning": response_text[:500],
                        "evidence_used": evidence_texts[0][:200] if evidence_texts else "",
                        "gaps": ["Unable to parse structured response"]
                    }
            return result
        except Exception as e:
            return {
                "status": "partial",
                "confidence": 0.5,
                "reasoning": f"Analysis error: {str(e)}",
                "evidence_used": evidence_texts[0][:200] if evidence_texts else "",
                "gaps": ["Analysis could not be completed"]
            }

    def _load_audit(self, audit_id: str) -> Optional[Audit]:
        """Load an audit from cache or workspace."""
        if audit_id in self._audit_cache:
            return self._audit_cache[audit_id]

        if self._institution_id and self.workspace_manager:
            audit_path = f"audits/{audit_id}.json"
            try:
                data = self.workspace_manager.read_file(self._institution_id, audit_path)
                if data:
                    audit = Audit.from_dict(json.loads(data.decode("utf-8")))
                    self._audit_cache[audit_id] = audit
                    return audit
            except Exception as e:
                logger.warning(f"Failed to load audit {audit_id}: {e}")
        return None

    def _save_audit(self, audit: Audit) -> None:
        """Persist audit to cache and workspace."""
        self._audit_cache[audit.id] = audit

        if self._institution_id and self.workspace_manager:
            audit_path = f"audits/{audit.id}.json"
            try:
                self.workspace_manager.save_file(
                    self._institution_id,
                    audit_path,
                    json.dumps(audit.to_dict(), indent=2).encode("utf-8"),
                    create_version=True
                )
            except Exception as e:
                logger.error(f"Failed to save audit {audit.id}: {e}")

    def _update_audit_summary(self, audit: Audit) -> None:
        """Recompute audit summary from findings."""
        summary = {
            "compliant": 0,
            "partial": 0,
            "non_compliant": 0,
            "na": 0,
        }

        severity_summary = {
            "critical": 0,
            "significant": 0,
            "advisory": 0,
            "informational": 0,
        }

        for finding in audit.findings:
            status_key = finding.status.value
            if status_key in summary:
                summary[status_key] += 1

            severity_key = finding.severity.value
            if severity_key in severity_summary:
                severity_summary[severity_key] += 1

        summary["total"] = len(audit.findings)
        audit.summary = summary
        audit.summary_by_source = {"severity": severity_summary}

    def _get_or_create_finding(self, audit: Audit, item_number: str) -> AuditFinding:
        """Get existing finding or create new one for an item."""
        for finding in audit.findings:
            if finding.item_number == item_number:
                return finding

        finding = AuditFinding(
            audit_id=audit.id,
            item_number=item_number,
        )
        audit.findings.append(finding)
        return finding

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _tool_initialize_audit(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a new audit."""
        institution_id = tool_input.get("institution_id", "")
        document_id = tool_input.get("document_id", "")
        standards_id = tool_input.get("standards_library_id", "")

        if not institution_id or not document_id or not standards_id:
            return {"error": "institution_id, document_id, and standards_library_id are required"}

        # Store institution_id for later use
        self._institution_id = institution_id

        # Load document to verify it exists and get type
        doc = self._load_document(institution_id, document_id)
        if not doc:
            return {"error": f"Document not found: {document_id}"}

        # Get applicable standards
        applicable_items = self._get_applicable_standards(standards_id, doc.doc_type)

        # Create audit record
        audit = Audit(
            id=generate_id("audit"),
            document_id=document_id,
            standards_library_id=standards_id,
            status=AuditStatus.IN_PROGRESS,
            started_at=now_iso(),
            ai_model_used=self.model,
        )

        self._save_audit(audit)

        # Capture reproducibility snapshot (per D-01, D-02)
        self._current_snapshot = capture_audit_snapshot(
            audit_run_id=audit.id,
            institution_id=institution_id,
            system_prompt=SYSTEM_PROMPT,
            tool_definitions=self.tools,
            accreditor_code=standards_id.replace("std_", "").upper(),
        )

        return {
            "success": True,
            "audit_id": audit.id,
            "document_id": document_id,
            "document_type": doc.doc_type.value,
            "standards_library_id": standards_id,
            "applicable_items_count": len(applicable_items),
            "applicable_items": applicable_items[:10],  # Preview first 10
            "message": f"Audit initialized with {len(applicable_items)} applicable checklist items"
        }

    def _tool_completeness_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run completeness check - Pass 1."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Load document
        doc = self._load_document(self._institution_id, audit.document_id)
        if not doc:
            return {"error": "Document not found"}

        # Get applicable standards
        items = self._get_applicable_standards(audit.standards_library_id, doc.doc_type)

        results = []
        items_with_evidence = 0
        items_missing = 0

        for item in items:
            # Search for evidence
            evidence = self._search_for_evidence(
                institution_id=self._institution_id,
                query=item["description"],
                document_id=audit.document_id,
                n_results=3,
                min_score=0.45
            )

            found = len(evidence) > 0
            best_score = evidence[0]["score"] if evidence else 0

            # Create/update finding
            finding = self._get_or_create_finding(audit, item["number"])
            finding.item_description = item["description"]
            finding.pass_discovered = 1
            finding.ai_confidence = best_score
            finding.regulatory_source = RegulatorySource.ACCREDITOR

            if found:
                finding.evidence_in_document = evidence[0]["text"][:1000]
                page_num = evidence[0].get("page_number")
                finding.page_numbers = str(page_num) if page_num else ""
                items_with_evidence += 1
            else:
                finding.status = ComplianceStatus.NON_COMPLIANT
                finding.finding_detail = "No evidence found for this requirement in the document."
                finding.severity = FindingSeverity.SIGNIFICANT
                items_missing += 1

            results.append({
                "item": item["number"],
                "description": item["description"][:80],
                "found": found,
                "confidence": round(best_score, 2),
            })

        audit.passes_completed = max(audit.passes_completed, 1)
        self._update_audit_summary(audit)
        self._save_audit(audit)

        return {
            "success": True,
            "pass": "completeness",
            "items_checked": len(items),
            "items_with_evidence": items_with_evidence,
            "items_missing": items_missing,
            "results": results,
            "message": f"Completeness pass complete: {items_with_evidence}/{len(items)} items have evidence"
        }

    def _tool_standards_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run standards analysis - Pass 2."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Filter to findings with evidence that haven't been analyzed
        findings_to_analyze = [
            f for f in audit.findings
            if f.evidence_in_document and f.status == ComplianceStatus.NA
        ]

        results = []
        for finding in findings_to_analyze:
            # Analyze compliance
            analysis = self._analyze_compliance(
                item_number=finding.item_number,
                item_description=finding.item_description,
                evidence_texts=[finding.evidence_in_document],
            )

            # Update finding
            try:
                finding.status = ComplianceStatus(analysis.get("status", "partial"))
            except ValueError:
                finding.status = ComplianceStatus.PARTIAL

            finding.ai_confidence = analysis.get("confidence", 0.5)
            finding.finding_detail = analysis.get("reasoning", "")
            if analysis.get("gaps"):
                finding.finding_detail += "\n\nGaps identified: " + "; ".join(analysis["gaps"])

            if finding.pass_discovered < 2:
                finding.pass_discovered = 2

            results.append({
                "item": finding.item_number,
                "status": finding.status.value,
                "confidence": round(finding.ai_confidence, 2),
                "reasoning": analysis.get("reasoning", "")[:150]
            })

        audit.passes_completed = max(audit.passes_completed, 2)
        self._update_audit_summary(audit)
        self._save_audit(audit)

        # Count by status
        status_counts = {"compliant": 0, "partial": 0, "non_compliant": 0}
        for r in results:
            if r["status"] in status_counts:
                status_counts[r["status"]] += 1

        return {
            "success": True,
            "pass": "standards",
            "findings_analyzed": len(results),
            "status_counts": status_counts,
            "results": results,
            "message": f"Standards analysis complete: {status_counts['compliant']} compliant, {status_counts['partial']} partial, {status_counts['non_compliant']} non-compliant"
        }

    def _tool_consistency_pass(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Run consistency check - Pass 3."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Get document text
        doc_text = self._get_document_text(self._institution_id, audit.document_id)
        if not doc_text:
            return {"error": "Could not load document text"}

        # Truncate for AI analysis
        doc_text_truncated = doc_text[:12000]

        prompt = f"""Analyze this document for internal inconsistencies:

{doc_text_truncated}

Look for:
1. Conflicting policy statements
2. Inconsistent numbers (costs, hours, dates, percentages)
3. Contradictory procedures
4. Mismatched references

For each inconsistency found, identify the specific conflicting statements.

Respond ONLY with valid JSON array:
[{{"description": "what is inconsistent", "location1": "first statement", "location2": "conflicting statement", "severity": "critical|significant|advisory"}}]

If no inconsistencies found, respond with: []"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are a document consistency auditor. Be thorough but avoid false positives. Output only valid JSON array.",
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()
            # Parse JSON
            if response_text.startswith("["):
                inconsistencies = json.loads(response_text)
            else:
                import re
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    inconsistencies = json.loads(json_match.group())
                else:
                    inconsistencies = []
        except Exception:
            inconsistencies = []

        # Create findings for inconsistencies
        consistency_findings = []
        for idx, inc in enumerate(inconsistencies[:5]):  # Limit to 5
            finding = AuditFinding(
                audit_id=audit.id,
                item_number=f"CONSISTENCY-{idx + 1}",
                item_description="Internal document consistency",
                status=ComplianceStatus.PARTIAL,
                finding_detail=inc.get("description", "Inconsistency detected"),
                evidence_in_document=f"Statement 1: {inc.get('location1', '')}\n\nStatement 2: {inc.get('location2', '')}",
                pass_discovered=3,
                ai_confidence=0.7,
                regulatory_source=RegulatorySource.ACCREDITOR,
            )
            try:
                finding.severity = FindingSeverity(inc.get("severity", "advisory"))
            except ValueError:
                finding.severity = FindingSeverity.ADVISORY

            audit.findings.append(finding)
            consistency_findings.append({
                "id": finding.item_number,
                "description": inc.get("description", "")[:100],
                "severity": finding.severity.value
            })

        audit.passes_completed = max(audit.passes_completed, 3)
        self._update_audit_summary(audit)
        self._save_audit(audit)

        return {
            "success": True,
            "pass": "consistency",
            "inconsistencies_found": len(consistency_findings),
            "results": consistency_findings,
            "message": f"Consistency pass complete: {len(consistency_findings)} inconsistencies identified"
        }

    def _tool_assess_severity(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Assess severity - Pass 4."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Filter to non-compliant/partial findings
        findings_to_assess = [
            f for f in audit.findings
            if f.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.PARTIAL]
            and not f.item_number.startswith("CONSISTENCY-")  # Already has severity
        ]

        # Severity rules based on regulatory source
        severity_rules = {
            RegulatorySource.FEDERAL_TITLE_IV: FindingSeverity.CRITICAL,
            RegulatorySource.FEDERAL_FERPA: FindingSeverity.SIGNIFICANT,
            RegulatorySource.FEDERAL_OTHER: FindingSeverity.SIGNIFICANT,
            RegulatorySource.ACCREDITOR: FindingSeverity.SIGNIFICANT,
            RegulatorySource.STATE: FindingSeverity.ADVISORY,
            RegulatorySource.PROFESSIONAL: FindingSeverity.ADVISORY,
        }

        assessed = []
        for finding in findings_to_assess:
            # Start with rule-based severity
            base_severity = severity_rules.get(
                finding.regulatory_source,
                FindingSeverity.ADVISORY
            )

            # Escalate non-compliant findings
            if finding.status == ComplianceStatus.NON_COMPLIANT:
                if base_severity == FindingSeverity.ADVISORY:
                    finding.severity = FindingSeverity.SIGNIFICANT
                elif base_severity == FindingSeverity.INFORMATIONAL:
                    finding.severity = FindingSeverity.ADVISORY
                else:
                    finding.severity = base_severity
            else:
                finding.severity = base_severity

            if finding.pass_discovered < 4:
                finding.pass_discovered = 4

            assessed.append({
                "item": finding.item_number,
                "status": finding.status.value,
                "severity": finding.severity.value
            })

        audit.passes_completed = max(audit.passes_completed, 4)
        self._update_audit_summary(audit)
        self._save_audit(audit)

        # Compute severity summary
        severity_summary = {"critical": 0, "significant": 0, "advisory": 0, "informational": 0}
        for f in audit.findings:
            if f.severity.value in severity_summary:
                severity_summary[f.severity.value] += 1

        return {
            "success": True,
            "pass": "severity",
            "findings_assessed": len(assessed),
            "severity_summary": severity_summary,
            "results": assessed,
            "message": f"Severity assessment complete: {severity_summary['critical']} critical, {severity_summary['significant']} significant"
        }

    def _tool_generate_remediation(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate remediation recommendations - Pass 5."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Filter to findings needing remediation
        findings_to_fix = [
            f for f in audit.findings
            if f.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.PARTIAL]
            and not f.recommendation
        ]

        remediated = []
        for finding in findings_to_fix[:10]:  # Limit to 10 to control API calls
            prompt = f"""Generate specific remediation guidance for this compliance finding:

FINDING:
- Item: {finding.item_number}
- Description: {finding.item_description}
- Status: {finding.status.value}
- Severity: {finding.severity.value}
- Issue: {finding.finding_detail}
- Current Evidence: {finding.evidence_in_document[:500] if finding.evidence_in_document else 'None'}

Provide a concise remediation plan:
1. Specific steps to achieve compliance
2. Example language to add if applicable
3. Priority: immediate, short-term, or long-term

Keep response under 300 words."""

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=512,
                    system="You are an accreditation compliance expert. Provide specific, actionable remediation guidance.",
                    messages=[{"role": "user", "content": prompt}]
                )
                finding.recommendation = response.content[0].text.strip()
            except Exception as e:
                finding.recommendation = f"Remediation required. Please review the finding and add appropriate content to address: {finding.item_description}"

            if finding.pass_discovered < 5:
                finding.pass_discovered = 5

            remediated.append({
                "item": finding.item_number,
                "recommendation_preview": finding.recommendation[:150] + "..." if len(finding.recommendation) > 150 else finding.recommendation
            })

        audit.passes_completed = max(audit.passes_completed, 5)
        self._save_audit(audit)

        return {
            "success": True,
            "pass": "remediation",
            "findings_remediated": len(remediated),
            "results": remediated,
            "message": f"Remediation pass complete: {len(remediated)} findings have remediation guidance"
        }

    def _tool_finalize_audit(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize audit and generate report."""
        audit_id = tool_input.get("audit_id")
        if not audit_id:
            return {"error": "audit_id is required"}

        audit = self._load_audit(audit_id)
        if not audit:
            return {"error": f"Audit not found: {audit_id}"}

        # Update status and timestamp
        audit.status = AuditStatus.COMPLETED
        audit.completed_at = now_iso()

        # Final summary update
        self._update_audit_summary(audit)
        self._save_audit(audit)

        # Save reproducibility bundle (per D-08, D-09)
        if self._current_snapshot and self._current_snapshot.audit_run_id == audit.id:
            save_audit_snapshot(self._current_snapshot)

        # Build report
        report = {
            "audit_id": audit.id,
            "document_id": audit.document_id,
            "standards_library_id": audit.standards_library_id,
            "status": audit.status.value,
            "started_at": audit.started_at,
            "completed_at": audit.completed_at,
            "passes_completed": audit.passes_completed,
            "summary": audit.summary,
            "findings_by_status": {
                "compliant": [f.to_dict() for f in audit.findings if f.status == ComplianceStatus.COMPLIANT],
                "partial": [f.to_dict() for f in audit.findings if f.status == ComplianceStatus.PARTIAL],
                "non_compliant": [f.to_dict() for f in audit.findings if f.status == ComplianceStatus.NON_COMPLIANT],
            },
            "critical_findings": [
                f.to_dict() for f in audit.findings
                if f.severity == FindingSeverity.CRITICAL
            ],
            "remediation_needed": len([f for f in audit.findings if f.status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.PARTIAL]]),
        }

        return {
            "success": True,
            "audit_id": audit.id,
            "status": "completed",
            "summary": audit.summary,
            "total_findings": len(audit.findings),
            "critical_count": len(report["critical_findings"]),
            "remediation_needed": report["remediation_needed"],
            "report": report,
            "message": f"Audit complete: {audit.summary.get('compliant', 0)} compliant, {audit.summary.get('partial', 0)} partial, {audit.summary.get('non_compliant', 0)} non-compliant findings"
        }

    # =========================================================================
    # Workflow Methods
    # =========================================================================

    def audit_document(
        self,
        institution_id: str,
        document_id: str,
        standards_library_id: str,
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """High-level entry point for running a full document audit.

        Args:
            institution_id: Institution ID
            document_id: Document to audit
            standards_library_id: Standards to audit against

        Yields:
            Progress updates during audit

        Returns:
            Final audit result with summary
        """
        self._institution_id = institution_id

        prompt = f"""Run a complete compliance audit on this document:

Institution: {institution_id}
Document ID: {document_id}
Standards Library: {standards_library_id}

Please execute all audit passes in order:
1. initialize_audit - Set up the audit
2. run_completeness_pass - Find evidence for each requirement
3. run_standards_pass - Analyze if evidence meets requirements
4. run_consistency_pass - Check for internal contradictions
5. assess_severity - Grade the severity of findings
6. generate_remediation - Create fix recommendations
7. finalize_audit - Complete and generate report

Report your findings after each pass."""

        for update in self.run_turn(prompt):
            yield update

        # Return final result
        return {
            "status": "completed",
            "institution_id": institution_id,
            "document_id": document_id,
        }

    def run_programmatic_audit(
        self,
        institution_id: str,
        document_id: str,
        standards_library_id: str,
    ) -> Audit:
        """Run audit programmatically without AI orchestration.

        Useful for batch processing or testing.
        """
        self._institution_id = institution_id

        # Initialize
        init_result = self._tool_initialize_audit({
            "institution_id": institution_id,
            "document_id": document_id,
            "standards_library_id": standards_library_id
        })

        if "error" in init_result:
            raise ValueError(init_result["error"])

        audit_id = init_result["audit_id"]

        # Run all passes
        self._tool_completeness_pass({"audit_id": audit_id})
        self._tool_standards_pass({"audit_id": audit_id})
        self._tool_consistency_pass({"audit_id": audit_id})
        self._tool_assess_severity({"audit_id": audit_id})
        self._tool_generate_remediation({"audit_id": audit_id})
        self._tool_finalize_audit({"audit_id": audit_id})

        return self._load_audit(audit_id)

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run an audit workflow."""
        if action == "full_audit":
            try:
                audit = self.run_programmatic_audit(
                    institution_id=inputs.get("institution_id", ""),
                    document_id=inputs.get("document_id", ""),
                    standards_library_id=inputs.get("standards_library_id", ""),
                )
                return AgentResult.success(
                    data=audit.to_dict() if audit else {},
                    confidence=0.8,
                )
            except Exception as e:
                return AgentResult.error(str(e))
        return AgentResult.error(f"Unknown workflow: {action}")
