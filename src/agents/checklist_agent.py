"""Checklist Auto-Fill Agent.

Automatically populates accreditation checklists by:
1. Loading checklist items from standards libraries
2. Matching audit findings to checklist items
3. Searching documents for supporting evidence
4. Generating narrative responses with AI
5. Tracking compliance status per item
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    ComplianceStatus,
    ChecklistItem,
    ChecklistResponse,
    ChecklistResponseStatus,
    FilledChecklist,
    FilledChecklistStatus,
    AuditFinding,
    now_iso,
    generate_id,
)
from src.config import Config


@register_agent(AgentType.WORKFLOW_COACH)
class ChecklistAgent(BaseAgent):
    """Agent for auto-filling accreditation checklists.

    Uses audit findings, document evidence, and AI to populate
    checklist items with compliance status and narrative responses.
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._current_checklist: Optional[FilledChecklist] = None
        self._audit_findings: List[AuditFinding] = []
        self._checklist_items: List[ChecklistItem] = []

    @property
    def agent_type(self) -> AgentType:
        return AgentType.WORKFLOW_COACH

    @property
    def system_prompt(self) -> str:
        return """You are an accreditation checklist specialist. Your job is to help
institutions complete their accreditation self-evaluation checklists by:

1. Analyzing audit findings and matching them to checklist items
2. Searching institutional documents for supporting evidence
3. Generating clear, professional narrative responses
4. Determining compliance status based on available evidence

For each checklist item, you should:
- Cite specific evidence from documents
- Reference audit findings when available
- Write responses in third person ("The institution...")
- Be factual and evidence-based
- Flag items that need human review when evidence is insufficient

Always prioritize accuracy over completeness. It's better to flag an item
for review than to provide an unsupported compliance claim."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "load_checklist_template",
                "description": "Load checklist items from a standards library to create a new filled checklist.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "standards_library_id": {"type": "string", "description": "Standards library to use"},
                        "program_id": {"type": "string", "description": "Optional program ID for program-specific checklist"},
                        "name": {"type": "string", "description": "Name for the checklist"},
                    },
                    "required": ["institution_id", "standards_library_id"],
                },
            },
            {
                "name": "load_audit_findings",
                "description": "Load audit findings for matching to checklist items.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "audit_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of audit IDs to load findings from",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "auto_fill_from_findings",
                "description": "Auto-fill checklist items using loaded audit findings.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "match_threshold": {
                            "type": "number",
                            "description": "Minimum confidence threshold for matching (0-1)",
                            "default": 0.7,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "search_evidence",
                "description": "Search documents for evidence to support a specific checklist item.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_number": {"type": "string", "description": "Checklist item number to find evidence for"},
                        "query": {"type": "string", "description": "Search query based on item description"},
                        "document_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Document types to search",
                        },
                    },
                    "required": ["item_number", "query"],
                },
            },
            {
                "name": "generate_narrative",
                "description": "Generate a narrative response for a checklist item using AI.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_number": {"type": "string", "description": "Checklist item number"},
                        "evidence_context": {"type": "string", "description": "Evidence and findings to base narrative on"},
                        "compliance_status": {
                            "type": "string",
                            "enum": ["compliant", "partial", "non_compliant", "na"],
                            "description": "Determined compliance status",
                        },
                    },
                    "required": ["item_number", "evidence_context", "compliance_status"],
                },
            },
            {
                "name": "update_item_response",
                "description": "Update a specific checklist item's response.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "item_number": {"type": "string", "description": "Checklist item number"},
                        "compliance_status": {"type": "string", "enum": ["compliant", "partial", "non_compliant", "na"]},
                        "narrative_response": {"type": "string", "description": "Narrative response text"},
                        "evidence_summary": {"type": "string", "description": "Summary of supporting evidence"},
                        "needs_review": {"type": "boolean", "description": "Whether item needs human review"},
                    },
                    "required": ["item_number"],
                },
            },
            {
                "name": "save_checklist",
                "description": "Save the current filled checklist to workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mark_complete": {"type": "boolean", "description": "Mark auto-fill as complete"},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_checklist_summary",
                "description": "Get summary statistics of the current checklist.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return results."""
        tool_map = {
            "load_checklist_template": self._tool_load_template,
            "load_audit_findings": self._tool_load_findings,
            "auto_fill_from_findings": self._tool_auto_fill_findings,
            "search_evidence": self._tool_search_evidence,
            "generate_narrative": self._tool_generate_narrative,
            "update_item_response": self._tool_update_response,
            "save_checklist": self._tool_save_checklist,
            "get_checklist_summary": self._tool_get_summary,
        }

        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_load_template(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load checklist template from standards library."""
        institution_id = params["institution_id"]
        standards_id = params["standards_library_id"]
        program_id = params.get("program_id", "")
        name = params.get("name", "")

        # Load standards library
        from src.core.standards_store import StandardsStore
        store = StandardsStore()
        library = store.get(standards_id)

        if not library:
            return {"error": f"Standards library not found: {standards_id}"}

        self._checklist_items = library.checklist_items

        if not self._checklist_items:
            return {"error": "Standards library has no checklist items"}

        # Create filled checklist with empty responses
        checklist_name = name or f"{library.name} - {now_iso()[:10]}"

        self._current_checklist = FilledChecklist(
            institution_id=institution_id,
            program_id=program_id,
            standards_library_id=standards_id,
            accrediting_body=library.accrediting_body.value if hasattr(library.accrediting_body, 'value') else str(library.accrediting_body),
            name=checklist_name,
            status=FilledChecklistStatus.IN_PROGRESS,
            responses=[],
            total_items=len(self._checklist_items),
        )

        # Create empty response for each item
        for item in self._checklist_items:
            response = ChecklistResponse(
                item_number=item.number,
                item_description=item.description,
                category=item.category,
                section_reference=item.section_reference,
            )
            self._current_checklist.responses.append(response)

        return {
            "success": True,
            "checklist_id": self._current_checklist.id,
            "total_items": len(self._checklist_items),
            "categories": list(set(item.category for item in self._checklist_items)),
            "message": f"Created checklist with {len(self._checklist_items)} items",
        }

    def _tool_load_findings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load audit findings for matching."""
        institution_id = params["institution_id"]
        audit_ids = params.get("audit_ids", [])

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        institution = self.workspace_manager.load_institution(institution_id)
        if not institution:
            return {"error": f"Institution not found: {institution_id}"}

        # Load audits
        all_findings = []

        if audit_ids:
            # Load specific audits
            for audit_id in audit_ids:
                audit_data = self.workspace_manager.load_file(
                    institution_id, f"audits/{audit_id}.json"
                )
                if audit_data:
                    findings = audit_data.get("findings", [])
                    for f in findings:
                        finding = AuditFinding.from_dict(f)
                        all_findings.append(finding)
        else:
            # Load all audits
            audits = self.workspace_manager.list_audits(institution_id)
            for audit_meta in audits:
                audit_data = self.workspace_manager.load_file(
                    institution_id, f"audits/{audit_meta['id']}.json"
                )
                if audit_data:
                    findings = audit_data.get("findings", [])
                    for f in findings:
                        finding = AuditFinding.from_dict(f)
                        all_findings.append(finding)

        self._audit_findings = all_findings

        # Summarize findings by status
        by_status = {}
        for f in all_findings:
            status = f.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "success": True,
            "findings_loaded": len(all_findings),
            "by_status": by_status,
            "message": f"Loaded {len(all_findings)} audit findings",
        }

    def _tool_auto_fill_findings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-fill checklist from audit findings."""
        if not self._current_checklist:
            return {"error": "No checklist loaded. Call load_checklist_template first."}

        if not self._audit_findings:
            return {"error": "No findings loaded. Call load_audit_findings first."}

        threshold = params.get("match_threshold", 0.7)
        matches_made = 0
        items_filled = 0

        # Build finding lookup by item number
        findings_by_item = {}
        for finding in self._audit_findings:
            item_num = finding.item_number
            if item_num not in findings_by_item:
                findings_by_item[item_num] = []
            findings_by_item[item_num].append(finding)

        # Match findings to checklist items
        for response in self._current_checklist.responses:
            item_num = response.item_number
            section_ref = response.section_reference

            # Try exact match on item number
            matched_findings = findings_by_item.get(item_num, [])

            # Also try section reference match
            if not matched_findings and section_ref:
                matched_findings = findings_by_item.get(section_ref, [])

            if matched_findings:
                matches_made += len(matched_findings)
                items_filled += 1

                # Determine compliance from findings
                statuses = [f.status for f in matched_findings]
                if ComplianceStatus.NON_COMPLIANT in statuses:
                    response.compliance_status = ComplianceStatus.NON_COMPLIANT
                elif ComplianceStatus.PARTIAL in statuses:
                    response.compliance_status = ComplianceStatus.PARTIAL
                elif all(s == ComplianceStatus.COMPLIANT for s in statuses):
                    response.compliance_status = ComplianceStatus.COMPLIANT
                else:
                    response.compliance_status = ComplianceStatus.NA

                # Build evidence summary
                evidence_parts = []
                sources = []
                finding_ids = []

                for f in matched_findings:
                    finding_ids.append(f.id)
                    if f.evidence_in_document:
                        evidence_parts.append(f.evidence_in_document[:200])
                    if f.finding_detail:
                        evidence_parts.append(f"Finding: {f.finding_detail[:200]}")
                    sources.append({
                        "finding_id": f.id,
                        "status": f.status.value,
                        "evidence": f.evidence_in_document[:100] if f.evidence_in_document else "",
                    })

                response.evidence_summary = "\n\n".join(evidence_parts)
                response.evidence_sources = sources
                response.audit_finding_ids = finding_ids
                response.ai_confidence = min(1.0, len(matched_findings) * 0.3 + 0.4)
                response.response_status = ChecklistResponseStatus.AUTO_FILLED

                # Mark for review if non-compliant or low confidence
                if response.compliance_status == ComplianceStatus.NON_COMPLIANT:
                    response.response_status = ChecklistResponseStatus.NEEDS_REVIEW
                elif response.ai_confidence < threshold:
                    response.response_status = ChecklistResponseStatus.NEEDS_REVIEW

                response.last_updated = now_iso()

        # Update checklist stats
        self._current_checklist.update_stats()
        self._current_checklist.auto_fill_sources["audit_ids"] = list(
            set(f.audit_id for f in self._audit_findings)
        )

        return {
            "success": True,
            "items_filled": items_filled,
            "matches_made": matches_made,
            "items_needing_review": self._current_checklist.items_needs_review,
            "compliance_summary": {
                "compliant": self._current_checklist.items_compliant,
                "partial": self._current_checklist.items_partial,
                "non_compliant": self._current_checklist.items_non_compliant,
            },
        }

    def _tool_search_evidence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search documents for evidence supporting a checklist item."""
        item_number = params["item_number"]
        query = params["query"]
        doc_types = params.get("document_types", [])

        if not self._current_checklist:
            return {"error": "No checklist loaded"}

        # Find the response
        response = next(
            (r for r in self._current_checklist.responses if r.item_number == item_number),
            None
        )
        if not response:
            return {"error": f"Item not found: {item_number}"}

        # Search using semantic search
        try:
            from src.search import get_search_service
            search_service = get_search_service()

            results = search_service.search(
                query=query,
                institution_id=self._current_checklist.institution_id,
                top_k=5,
            )

            # Filter by document type if specified
            if doc_types:
                results = [r for r in results if any(
                    dt in r.chunk.document_id.lower() for dt in doc_types
                )]

            evidence_found = []
            for result in results[:5]:
                evidence_found.append({
                    "document_id": result.chunk.document_id,
                    "page": result.chunk.page_number,
                    "text": result.chunk.text_anonymized[:300],
                    "score": result.score,
                })

            # Update response with evidence
            if evidence_found:
                response.evidence_sources.extend(evidence_found)
                summaries = [e["text"][:100] for e in evidence_found[:3]]
                response.evidence_summary = (
                    response.evidence_summary + "\n\n" + "\n".join(summaries)
                ).strip()
                response.last_updated = now_iso()

            return {
                "success": True,
                "item_number": item_number,
                "evidence_count": len(evidence_found),
                "evidence": evidence_found,
            }

        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}

    def _tool_generate_narrative(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate narrative response for a checklist item."""
        item_number = params["item_number"]
        evidence_context = params["evidence_context"]
        compliance_status = params["compliance_status"]

        if not self._current_checklist:
            return {"error": "No checklist loaded"}

        # Find the response
        response = next(
            (r for r in self._current_checklist.responses if r.item_number == item_number),
            None
        )
        if not response:
            return {"error": f"Item not found: {item_number}"}

        # Generate narrative with AI
        prompt = f"""Generate a professional narrative response for an accreditation checklist item.

Checklist Item: {item_number} - {response.item_description}
Category: {response.category}
Standard Reference: {response.section_reference}
Compliance Status: {compliance_status}

Evidence and Context:
{evidence_context}

Write a clear, factual narrative response (2-4 sentences) that:
1. States the compliance status
2. Summarizes the supporting evidence
3. Uses third person ("The institution...")
4. Is appropriate for accreditation documentation

Respond with just the narrative text, no additional formatting."""

        try:
            ai_response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            narrative = ai_response.content[0].text.strip()

            # Update response
            response.narrative_response = narrative
            response.compliance_status = ComplianceStatus(compliance_status)
            response.response_status = ChecklistResponseStatus.AUTO_FILLED
            response.ai_confidence = 0.8
            response.last_updated = now_iso()

            return {
                "success": True,
                "item_number": item_number,
                "narrative": narrative,
                "compliance_status": compliance_status,
            }

        except Exception as e:
            return {"error": f"AI generation failed: {str(e)}"}

    def _tool_update_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update a checklist item response."""
        item_number = params["item_number"]

        if not self._current_checklist:
            return {"error": "No checklist loaded"}

        # Find the response
        response = next(
            (r for r in self._current_checklist.responses if r.item_number == item_number),
            None
        )
        if not response:
            return {"error": f"Item not found: {item_number}"}

        # Update fields
        if "compliance_status" in params:
            response.compliance_status = ComplianceStatus(params["compliance_status"])
        if "narrative_response" in params:
            response.narrative_response = params["narrative_response"]
        if "evidence_summary" in params:
            response.evidence_summary = params["evidence_summary"]
        if params.get("needs_review"):
            response.response_status = ChecklistResponseStatus.NEEDS_REVIEW
        else:
            response.response_status = ChecklistResponseStatus.AUTO_FILLED

        response.last_updated = now_iso()

        # Update stats
        self._current_checklist.update_stats()

        return {
            "success": True,
            "item_number": item_number,
            "updated": True,
        }

    def _tool_save_checklist(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save the checklist to workspace."""
        if not self._current_checklist:
            return {"error": "No checklist loaded"}

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        mark_complete = params.get("mark_complete", False)

        if mark_complete:
            self._current_checklist.status = FilledChecklistStatus.AUTO_FILL_COMPLETE

        # Update stats
        self._current_checklist.update_stats()
        self._current_checklist.updated_at = now_iso()

        # Save to workspace
        institution_id = self._current_checklist.institution_id
        program_id = self._current_checklist.program_id or "institution"
        filename = f"checklists/{self._current_checklist.id}.json"

        if program_id != "institution":
            filename = f"programs/{program_id}/checklists/{self._current_checklist.id}.json"

        self.workspace_manager.save_file(
            institution_id,
            filename,
            self._current_checklist.to_dict(),
        )

        return {
            "success": True,
            "checklist_id": self._current_checklist.id,
            "path": filename,
            "status": self._current_checklist.status.value,
            "stats": {
                "total": self._current_checklist.total_items,
                "completed": self._current_checklist.items_completed,
                "compliant": self._current_checklist.items_compliant,
                "partial": self._current_checklist.items_partial,
                "non_compliant": self._current_checklist.items_non_compliant,
                "needs_review": self._current_checklist.items_needs_review,
            },
        }

    def _tool_get_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get checklist summary."""
        if not self._current_checklist:
            return {"error": "No checklist loaded"}

        self._current_checklist.update_stats()

        # Group by category
        by_category = {}
        for response in self._current_checklist.responses:
            cat = response.category or "Other"
            if cat not in by_category:
                by_category[cat] = {"total": 0, "compliant": 0, "partial": 0, "non_compliant": 0}
            by_category[cat]["total"] += 1
            if response.compliance_status == ComplianceStatus.COMPLIANT:
                by_category[cat]["compliant"] += 1
            elif response.compliance_status == ComplianceStatus.PARTIAL:
                by_category[cat]["partial"] += 1
            elif response.compliance_status == ComplianceStatus.NON_COMPLIANT:
                by_category[cat]["non_compliant"] += 1

        return {
            "checklist_id": self._current_checklist.id,
            "name": self._current_checklist.name,
            "status": self._current_checklist.status.value,
            "total_items": self._current_checklist.total_items,
            "items_completed": self._current_checklist.items_completed,
            "items_compliant": self._current_checklist.items_compliant,
            "items_partial": self._current_checklist.items_partial,
            "items_non_compliant": self._current_checklist.items_non_compliant,
            "items_needs_review": self._current_checklist.items_needs_review,
            "by_category": by_category,
            "completion_rate": round(
                (self._current_checklist.items_completed / self._current_checklist.total_items) * 100
                if self._current_checklist.total_items > 0 else 0
            ),
        }

    # ===========================
    # Workflow Methods
    # ===========================

    def run_auto_fill(
        self,
        institution_id: str,
        standards_library_id: str,
        audit_ids: Optional[List[str]] = None,
        program_id: str = "",
        name: str = "",
    ) -> Dict[str, Any]:
        """Run complete auto-fill workflow.

        1. Load checklist template
        2. Load audit findings
        3. Auto-fill from findings
        4. Save checklist

        Returns filled checklist summary.
        """
        # Step 1: Load template
        result = self._tool_load_template({
            "institution_id": institution_id,
            "standards_library_id": standards_library_id,
            "program_id": program_id,
            "name": name,
        })
        if "error" in result:
            return result

        # Step 2: Load findings
        result = self._tool_load_findings({
            "institution_id": institution_id,
            "audit_ids": audit_ids or [],
        })
        if "error" in result:
            return result

        # Step 3: Auto-fill
        result = self._tool_auto_fill_findings({})
        if "error" in result:
            return result

        # Step 4: Save
        result = self._tool_save_checklist({"mark_complete": True})
        if "error" in result:
            return result

        # Return summary
        return self._tool_get_summary({})

    def run_workflow(self, workflow_name: str, params: Dict[str, Any]) -> Any:
        """Run a named workflow."""
        from src.core.models import AgentResult

        if workflow_name == "auto_fill":
            result = self.run_auto_fill(
                institution_id=params.get("institution_id", ""),
                standards_library_id=params.get("standards_library_id", ""),
                audit_ids=params.get("audit_ids"),
                program_id=params.get("program_id", ""),
                name=params.get("name", ""),
            )
            if "error" in result:
                return AgentResult(status="error", data=result, message=result["error"])
            return AgentResult(
                status="success",
                data=result,
                message=f"Auto-filled checklist with {result.get('items_completed', 0)} items",
            )

        return AgentResult(status="error", data={}, message=f"Unknown workflow: {workflow_name}")
