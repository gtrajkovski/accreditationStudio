"""Orchestrator Agent.

Master agent that coordinates the full accreditation workflow:
1. Document analysis and indexing
2. Gap analysis against standards
3. Evidence mapping
4. Compliance checking
5. Self-study drafting
6. Human review checkpoints

Manages checkpoints for human approval at key stages.
"""

from typing import Dict, Any, List, Optional, Callable, Generator
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent, AgentRegistry
from src.core.models import (
    AgentSession,
    SessionStatus,
    HumanCheckpoint,
    generate_id,
)


@register_agent(AgentType.ORCHESTRATOR)
class OrchestratorAgent(BaseAgent):
    """Master agent that coordinates the full accreditation workflow.

    Workflow stages:
    1. INTAKE - Receive requirements and initial documents
    2. DOCUMENT_ANALYSIS - Analyze uploaded documents
    3. GAP_ANALYSIS - Identify compliance gaps
    4. CHECKPOINT_GAPS - Human review of identified gaps
    5. EVIDENCE_MAPPING - Map evidence to standards
    6. COMPLIANCE_CHECK - Verify compliance status
    7. CHECKPOINT_COMPLIANCE - Human review before drafting
    8. SELF_STUDY_DRAFT - Draft self-study sections
    9. CHECKPOINT_DRAFT - Human review of drafts
    10. COMPLETE - Ready for submission

    The orchestrator can pause at checkpoints and resume after approval.
    """

    STAGES = [
        "INTAKE",
        "DOCUMENT_ANALYSIS",
        "GAP_ANALYSIS",
        "CHECKPOINT_GAPS",
        "EVIDENCE_MAPPING",
        "COMPLIANCE_CHECK",
        "CHECKPOINT_COMPLIANCE",
        "SELF_STUDY_DRAFT",
        "CHECKPOINT_DRAFT",
        "COMPLETE",
    ]

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ORCHESTRATOR

    @property
    def system_prompt(self) -> str:
        return """You are the AccreditAI Orchestrator, responsible for coordinating the complete accreditation preparation workflow.

Your workflow stages:
1. INTAKE - Receive institution information and initial documents
2. DOCUMENT_ANALYSIS - Analyze uploaded documents using DocumentAnalyzer agent
3. GAP_ANALYSIS - Identify compliance gaps using GapAnalyzer agent
4. CHECKPOINT_GAPS - Request human review of identified gaps
5. EVIDENCE_MAPPING - Map evidence to standards using EvidenceMapper agent
6. COMPLIANCE_CHECK - Verify compliance using ComplianceChecker agent
7. CHECKPOINT_COMPLIANCE - Request human review of compliance status
8. SELF_STUDY_DRAFT - Draft self-study sections using SelfStudyWriter agent
9. CHECKPOINT_DRAFT - Request human review of drafts
10. COMPLETE - Finalize for submission

Available tools:
- get_institution_status: Get current institution and document status
- analyze_documents: Delegate to DocumentAnalyzer agent
- run_gap_analysis: Delegate to GapAnalyzer agent
- request_gap_review: Create checkpoint for gap review
- map_evidence: Delegate to EvidenceMapper agent
- check_compliance: Delegate to ComplianceChecker agent
- request_compliance_review: Create checkpoint for compliance review
- draft_self_study: Delegate to SelfStudyWriter agent
- request_draft_review: Create checkpoint for draft review
- get_workflow_status: Check current workflow state
- complete_workflow: Mark workflow as complete

Always explain what you're doing and why. Keep the user informed of progress.
Respect confidence thresholds and request human approval when uncertain."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_institution_status",
                "description": "Get current institution information and document status",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "analyze_documents",
                "description": "Analyze uploaded documents to extract key information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of document IDs to analyze"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "run_gap_analysis",
                "description": "Run gap analysis against accreditation standards",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standard_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific standards to check (optional, defaults to all)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "request_gap_review",
                "description": "Request human review of identified gaps",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Summary of gaps identified"
                        },
                        "critical_gaps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of critical gaps requiring attention"
                        }
                    },
                    "required": ["summary"]
                }
            },
            {
                "name": "map_evidence",
                "description": "Map evidence documents to standards requirements",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "auto_assign": {
                            "type": "boolean",
                            "description": "Automatically assign high-confidence mappings"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "check_compliance",
                "description": "Check compliance status against all standards",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_recommendations": {
                            "type": "boolean",
                            "description": "Include improvement recommendations"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "request_compliance_review",
                "description": "Request human review of compliance status",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Summary of compliance status"
                        },
                        "compliance_score": {
                            "type": "number",
                            "description": "Overall compliance score (0-100)"
                        }
                    },
                    "required": ["summary"]
                }
            },
            {
                "name": "draft_self_study",
                "description": "Draft self-study narrative sections",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific sections to draft (optional, defaults to all)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "request_draft_review",
                "description": "Request human review of drafted sections",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Summary of drafted content"
                        },
                        "sections_drafted": {
                            "type": "integer",
                            "description": "Number of sections drafted"
                        }
                    },
                    "required": ["summary"]
                }
            },
            {
                "name": "get_workflow_status",
                "description": "Get the current workflow status and progress",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "complete_workflow",
                "description": "Mark the workflow as complete",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "final_summary": {
                            "type": "string",
                            "description": "Final summary of completed work"
                        }
                    },
                    "required": ["final_summary"]
                }
            }
        ]

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update: Optional[Callable[[AgentSession], None]] = None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._current_stage = "INTAKE"
        self._analysis_results = None
        self._gap_results = None
        self._compliance_results = None

        # Restore stage from session data if resuming
        if session.metadata.get("current_stage"):
            self._current_stage = session.metadata["current_stage"]

    def _delegate_to_agent(
        self,
        agent_type: AgentType,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Delegate a task to a specialist agent.

        Creates a child session, runs the agent, and returns the result.

        Args:
            agent_type: Type of agent to delegate to.
            prompt: Task prompt for the agent.
            context: Optional context data to include.

        Returns:
            Result from the delegated agent or error dict.
        """
        # Create child session for the delegated agent
        child_session = AgentSession(
            id=generate_id("ses"),
            agent_type=agent_type,
            institution_id=self.session.institution_id,
            status=SessionStatus.RUNNING,
            metadata={"parent_session": self.session.id, **(context or {})},
        )

        # Get the agent class from registry
        agent = AgentRegistry.create(
            agent_type=agent_type,
            session=child_session,
            workspace_manager=self._workspace_manager,
        )

        if agent is None:
            return {
                "error": f"Agent type {agent_type.value} not registered",
                "success": False,
            }

        # Run a single turn with the delegated agent
        result = None
        try:
            for update in agent.run_turn(prompt):
                if update.get("type") == "turn_complete":
                    result = update.get("result", {})
                    break
                elif update.get("type") == "error":
                    return {"error": update.get("message"), "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

        return result if result else {"success": True, "message": "Agent completed"}

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        if tool_name == "get_institution_status":
            return self._get_institution_status()
        elif tool_name == "analyze_documents":
            return self._analyze_documents(tool_input)
        elif tool_name == "run_gap_analysis":
            return self._run_gap_analysis(tool_input)
        elif tool_name == "request_gap_review":
            return self._request_gap_review(tool_input)
        elif tool_name == "map_evidence":
            return self._map_evidence(tool_input)
        elif tool_name == "check_compliance":
            return self._check_compliance(tool_input)
        elif tool_name == "request_compliance_review":
            return self._request_compliance_review(tool_input)
        elif tool_name == "draft_self_study":
            return self._draft_self_study(tool_input)
        elif tool_name == "request_draft_review":
            return self._request_draft_review(tool_input)
        elif tool_name == "get_workflow_status":
            return self._get_workflow_status()
        elif tool_name == "complete_workflow":
            return self._complete_workflow(tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _get_institution_status(self) -> Dict[str, Any]:
        """Get current institution information and document status."""
        institution = self.get_institution()
        if not institution:
            return {
                "error": "No institution loaded",
                "institution_id": self.session.institution_id,
            }

        return {
            "institution_id": institution.id,
            "name": institution.name,
            "accrediting_body": institution.accrediting_body.value,
            "document_count": len(institution.documents),
            "program_count": len(institution.programs),
            "current_stage": self._current_stage,
        }

    def _analyze_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze uploaded documents using the Ingestion agent."""
        self._current_stage = "DOCUMENT_ANALYSIS"
        self.session.metadata["current_stage"] = self._current_stage
        self._notify_update()

        institution = self.get_institution()
        if not institution:
            return {"error": "No institution loaded", "success": False}

        document_ids = params.get("document_ids", [])
        if not document_ids:
            # Analyze all documents if none specified
            document_ids = [doc.id for doc in institution.documents]

        if not document_ids:
            return {
                "success": True,
                "message": "No documents to analyze",
                "documents_analyzed": 0,
                "stage": self._current_stage,
            }

        # Delegate to Ingestion agent for document processing
        result = self._delegate_to_agent(
            agent_type=AgentType.INGESTION,
            prompt=f"Analyze and index the following documents for institution {institution.id}: {document_ids}. Extract key information, classify document types, and prepare for compliance auditing.",
            context={"document_ids": document_ids},
        )

        if result.get("error"):
            return result

        self._analysis_results = result
        return {
            "success": True,
            "message": f"Document analysis complete for {len(document_ids)} document(s)",
            "documents_analyzed": len(document_ids),
            "stage": self._current_stage,
            "analysis_summary": result.get("summary", "Analysis completed"),
        }

    def _run_gap_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run gap analysis against standards using the Gap Finder agent."""
        self._current_stage = "GAP_ANALYSIS"
        self.session.metadata["current_stage"] = self._current_stage
        self._notify_update()

        institution = self.get_institution()
        if not institution:
            return {"error": "No institution loaded", "success": False}

        standard_ids = params.get("standard_ids", [])
        standards_filter = f" for standards {standard_ids}" if standard_ids else ""

        # Delegate to Gap Finder agent
        result = self._delegate_to_agent(
            agent_type=AgentType.GAP_FINDER,
            prompt=f"Analyze compliance gaps for institution {institution.id}{standards_filter}. Identify missing evidence, incomplete documentation, and areas of non-compliance. Prioritize findings by severity.",
            context={"standard_ids": standard_ids, "institution_id": institution.id},
        )

        if result.get("error"):
            return result

        self._gap_results = result
        gaps = result.get("gaps", [])
        critical_count = len([g for g in gaps if g.get("severity") == "critical"])

        return {
            "success": True,
            "message": f"Gap analysis complete. Found {len(gaps)} gap(s), {critical_count} critical.",
            "gap_count": len(gaps),
            "critical_gaps": critical_count,
            "stage": self._current_stage,
            "gaps": gaps,
        }

    def _request_gap_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Request human review of identified gaps."""
        self._current_stage = "CHECKPOINT_GAPS"
        self.session.metadata["current_stage"] = self._current_stage

        checkpoint = self.request_approval(
            checkpoint_type="gap_review",
            description=params.get("summary", "Gap analysis complete - review required"),
            data={
                "critical_gaps": params.get("critical_gaps", []),
                "gap_results": self._gap_results,
            },
        )

        return {
            "success": True,
            "checkpoint_id": checkpoint.id,
            "checkpoint_type": "gap_review",
            "message": "Gap review requested. Waiting for human approval.",
            "awaiting_approval": True,
        }

    def _map_evidence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Map evidence to standards using the Evidence Mapper agent."""
        self._current_stage = "EVIDENCE_MAPPING"
        self.session.metadata["current_stage"] = self._current_stage
        self._notify_update()

        institution = self.get_institution()
        if not institution:
            return {"error": "No institution loaded", "success": False}

        auto_assign = params.get("auto_assign", False)
        auto_mode = "Auto-assign high-confidence mappings." if auto_assign else "Flag all mappings for review."

        # Delegate to Evidence Mapper agent
        result = self._delegate_to_agent(
            agent_type=AgentType.EVIDENCE_MAPPER,
            prompt=f"Map evidence documents to accreditation standards for institution {institution.id}. {auto_mode} Create crosswalk between documents and requirements.",
            context={"auto_assign": auto_assign, "institution_id": institution.id},
        )

        if result.get("error"):
            return result

        mappings = result.get("mappings", [])
        return {
            "success": True,
            "message": f"Evidence mapping complete. Created {len(mappings)} mapping(s).",
            "mappings_created": len(mappings),
            "auto_assign": auto_assign,
            "stage": self._current_stage,
            "mappings": mappings,
        }

    def _check_compliance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance status using the Compliance Audit agent."""
        self._current_stage = "COMPLIANCE_CHECK"
        self.session.metadata["current_stage"] = self._current_stage
        self._notify_update()

        institution = self.get_institution()
        if not institution:
            return {"error": "No institution loaded", "success": False}

        include_recommendations = params.get("include_recommendations", True)
        rec_mode = "Include remediation recommendations." if include_recommendations else ""

        # Delegate to Compliance Audit agent
        result = self._delegate_to_agent(
            agent_type=AgentType.COMPLIANCE_AUDIT,
            prompt=f"Run full compliance audit for institution {institution.id}. Evaluate all documents against applicable standards. {rec_mode} Generate findings with severity ratings and confidence scores.",
            context={"include_recommendations": include_recommendations, "institution_id": institution.id},
        )

        if result.get("error"):
            return result

        self._compliance_results = result
        findings = result.get("findings", [])
        compliance_score = result.get("compliance_score", 0)

        return {
            "success": True,
            "message": f"Compliance check complete. Score: {compliance_score}%. {len(findings)} finding(s).",
            "compliance_score": compliance_score,
            "finding_count": len(findings),
            "include_recommendations": include_recommendations,
            "stage": self._current_stage,
            "findings": findings,
        }

    def _request_compliance_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Request human review of compliance status."""
        self._current_stage = "CHECKPOINT_COMPLIANCE"
        self.session.metadata["current_stage"] = self._current_stage

        checkpoint = self.request_approval(
            checkpoint_type="compliance_review",
            description=params.get("summary", "Compliance check complete - review required"),
            data={
                "compliance_score": params.get("compliance_score"),
                "compliance_results": self._compliance_results,
            },
        )

        return {
            "success": True,
            "checkpoint_id": checkpoint.id,
            "checkpoint_type": "compliance_review",
            "message": "Compliance review requested. Waiting for human approval.",
            "awaiting_approval": True,
        }

    def _draft_self_study(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draft self-study sections using the SER Drafting agent."""
        self._current_stage = "SELF_STUDY_DRAFT"
        self.session.metadata["current_stage"] = self._current_stage
        self._notify_update()

        institution = self.get_institution()
        if not institution:
            return {"error": "No institution loaded", "success": False}

        sections = params.get("sections", [])
        section_filter = f"sections: {sections}" if sections else "all applicable sections"

        # Delegate to SER Drafting agent
        result = self._delegate_to_agent(
            agent_type=AgentType.SER_DRAFTING,
            prompt=f"Draft self-evaluation report (SER) for institution {institution.id}. Cover {section_filter}. Use compliance findings and evidence mappings to support narrative claims. Follow accreditor guidelines for structure and content.",
            context={"sections": sections, "institution_id": institution.id},
        )

        if result.get("error"):
            return result

        sections_drafted = result.get("sections_drafted", 0)
        return {
            "success": True,
            "message": f"Self-study drafting complete. {sections_drafted} section(s) drafted.",
            "sections_drafted": sections_drafted,
            "sections": sections if sections else "all",
            "stage": self._current_stage,
            "drafts": result.get("drafts", []),
        }

    def _request_draft_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Request human review of drafted sections."""
        self._current_stage = "CHECKPOINT_DRAFT"
        self.session.metadata["current_stage"] = self._current_stage

        checkpoint = self.request_approval(
            checkpoint_type="draft_review",
            description=params.get("summary", "Self-study draft complete - review required"),
            data={
                "sections_drafted": params.get("sections_drafted", 0),
            },
        )

        return {
            "success": True,
            "checkpoint_id": checkpoint.id,
            "checkpoint_type": "draft_review",
            "message": "Draft review requested. Waiting for human approval.",
            "awaiting_approval": True,
        }

    def _get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        stage_index = self.STAGES.index(self._current_stage) if self._current_stage in self.STAGES else 0
        progress_pct = (stage_index / (len(self.STAGES) - 1)) * 100

        return {
            "current_stage": self._current_stage,
            "stage_index": stage_index,
            "total_stages": len(self.STAGES),
            "progress_percent": round(progress_pct, 1),
            "stages": self.STAGES,
            "session_id": self.session.id,
            "institution_id": self.session.institution_id,
            "status": self.session.status.value,
            "checkpoints_pending": len([
                c for c in self.session.checkpoints if c.status == "pending"
            ]),
        }

    def _complete_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Complete the workflow."""
        self._current_stage = "COMPLETE"
        self.session.metadata["current_stage"] = self._current_stage
        self.session.status = SessionStatus.COMPLETED
        self.session.completed_at = datetime.now().isoformat()
        self._notify_update()

        return {
            "success": True,
            "institution_id": self.session.institution_id,
            "message": "Accreditation preparation complete!",
            "final_summary": params.get("final_summary"),
            "workflow_status": self._get_workflow_status(),
        }

    def run_workflow(
        self,
        institution_id: str,
        accrediting_body: str,
    ) -> Generator[Dict[str, Any], None, None]:
        """Run the full accreditation preparation workflow.

        Args:
            institution_id: Institution to prepare for accreditation.
            accrediting_body: Target accrediting body (e.g., 'HLC', 'SACSCOC').

        Yields:
            Progress updates throughout the workflow.
        """
        self.session.institution_id = institution_id
        self.session.status = SessionStatus.RUNNING
        self.session.started_at = datetime.now().isoformat()

        prompt = f"""Begin accreditation preparation workflow for institution.

Institution ID: {institution_id}
Accrediting Body: {accrediting_body}

Execute the workflow:
1. get_institution_status - Understand current state
2. analyze_documents - Process all uploaded documents
3. run_gap_analysis - Identify gaps against standards
4. request_gap_review - Get human approval of gaps (will pause)
5. map_evidence - Map evidence to requirements
6. check_compliance - Verify compliance status
7. request_compliance_review - Get human approval (will pause)
8. draft_self_study - Draft narrative sections
9. request_draft_review - Get human approval (will pause)
10. complete_workflow - Finalize preparation

Start with get_institution_status."""

        yield {"type": "workflow_started", "institution_id": institution_id}

        for update in self.run_turn(prompt):
            yield update

            if update.get("type") == "turn_complete":
                status = self._get_workflow_status()

                if status["current_stage"] == "COMPLETE":
                    break
                elif self.session.status == SessionStatus.AWAITING_APPROVAL:
                    yield {
                        "type": "checkpoint_reached",
                        "stage": status["current_stage"],
                        "message": "Workflow paused for human approval.",
                    }
                    break
                else:
                    for u in self.run_turn("Continue with the next step in the workflow."):
                        yield u
