"""Site Visit Prep Agent.

Creates on-site binder materials and Q&A preparation for site visits.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.SITE_VISIT_PREP)
class SiteVisitPrepAgent(BaseAgent):
    """Site Visit Prep Agent.

    Produces:
    - Exhibit binder map
    - Likely reviewer questions + evidence pointers
    - Role-based prep lists (registrar, financial aid, program chair)
    - Quick retrieval system for on-the-fly requests

    Outputs:
    - Site visit binder ZIP
    - Q&A playbook
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SITE_VISIT_PREP

    @property
    def system_prompt(self) -> str:
        return """You are the Site Visit Prep Agent for AccreditAI.

You prepare institutions for accreditation site visits.

PREPARATION MATERIALS:
1. Exhibit binder with organized evidence
2. Likely reviewer questions based on standards and audit findings
3. Role-based preparation (what each staff member should know)
4. Quick reference guide for common requests

QUESTION CATEGORIES:
- Standards-based (directly from requirements)
- Finding-based (follow up on audit issues)
- Trend-based (changes since last visit)
- Policy-based (how policies are implemented)

For each question, provide:
- The question
- Relevant standard citation
- Suggested evidence to reference
- Key talking points"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_exhibit_binder",
                "description": "Generate organized exhibit binder for site visit",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "visit_type": {
                            "type": "string",
                            "enum": ["renewal", "initial", "substantive_change", "complaint"]
                        }
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "generate_likely_questions",
                "description": "Generate likely reviewer questions with suggested responses",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "standards_id": {"type": "string"},
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "generate_role_prep",
                "description": "Generate role-specific preparation guide",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": ["director", "registrar", "financial_aid",
                                     "admissions", "program_chair", "instructor"]
                        }
                    },
                    "required": ["institution_id", "role"]
                }
            },
            {
                "name": "quick_evidence_lookup",
                "description": "Quick lookup for on-the-fly evidence requests during visit",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "request": {"type": "string"}
                    },
                    "required": ["institution_id", "request"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a site visit prep tool."""
        if tool_name == "generate_exhibit_binder":
            return self._tool_generate_binder(tool_input)
        elif tool_name == "generate_likely_questions":
            return self._tool_generate_questions(tool_input)
        elif tool_name == "generate_role_prep":
            return self._tool_generate_role_prep(tool_input)
        elif tool_name == "quick_evidence_lookup":
            return self._tool_quick_lookup(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_generate_binder(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate exhibit binder (stub)."""
        return {
            "success": True,
            "message": "Binder generation requires evidence map and documents",
            "status": "stub",
            "sections": [
                "Tab 1: Institutional Overview",
                "Tab 2: Programs",
                "Tab 3: Faculty",
                "Tab 4: Student Services",
                "Tab 5: Financial Information",
                "Tab 6: Policies and Procedures"
            ]
        }

    def _tool_generate_questions(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate likely questions (stub with examples)."""
        sample_questions = [
            {
                "question": "How do you monitor student attendance?",
                "standard": "ACCSC Section V.A.3",
                "evidence": ["Attendance policy", "LMS reports", "Instructor procedures"],
                "key_points": ["Daily tracking", "Warning thresholds", "Makeup policy"]
            },
            {
                "question": "How is the refund policy disclosed to students?",
                "standard": "ACCSC Section VII.A.4",
                "evidence": ["Enrollment agreement", "Catalog", "Website"],
                "key_points": ["Before enrollment", "Written acknowledgment", "Clear calculations"]
            }
        ]

        return {
            "success": True,
            "questions": sample_questions,
            "note": "Full question generation requires standards analysis"
        }

    def _tool_generate_role_prep(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate role-specific prep (stub)."""
        role = tool_input.get("role", "director")

        role_topics = {
            "director": ["Institutional mission", "Governance", "Strategic planning", "Compliance overview"],
            "registrar": ["Enrollment process", "Student records", "Transcripts", "Attendance tracking"],
            "financial_aid": ["Title IV compliance", "R2T4 calculations", "Default rates", "Disclosures"],
            "admissions": ["Enrollment process", "Ability to benefit", "Disclosures", "Documentation"],
            "program_chair": ["Curriculum", "Faculty qualifications", "Advisory committees", "Outcomes"],
            "instructor": ["Teaching methods", "Assessment", "Student support", "Records"]
        }

        return {
            "success": True,
            "role": role,
            "topics": role_topics.get(role, []),
            "note": "Full prep guide requires institution-specific data"
        }

    def _tool_quick_lookup(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Quick evidence lookup using semantic search."""
        try:
            from src.search import get_search_service

            institution_id = tool_input.get("institution_id")
            request = tool_input.get("request")

            search_service = get_search_service(institution_id)
            results = search_service.search(request, n_results=5)

            evidence = []
            for result in results:
                evidence.append({
                    "document_id": result.chunk.document_id,
                    "page": result.chunk.page_number,
                    "section": result.chunk.section_header,
                    "text": result.chunk.text_anonymized[:300],
                    "relevance": result.score
                })

            return {
                "success": True,
                "request": request,
                "evidence": evidence,
                "count": len(evidence)
            }

        except Exception as e:
            return {"error": str(e)}

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a site visit prep workflow."""
        if action == "full_prep_package":
            return self._workflow_full_prep(inputs)
        return AgentResult.success(
            data={"message": f"Site visit workflow '{action}' not yet implemented"},
            confidence=0.5
        )

    def _workflow_full_prep(self, inputs: Dict[str, Any]) -> AgentResult:
        """Generate full site visit prep package."""
        return AgentResult.success(
            data={
                "message": "Full prep package workflow",
                "components": [
                    "exhibit_binder",
                    "question_bank",
                    "role_guides",
                    "quick_reference"
                ]
            },
            confidence=0.5,
            next_actions=[
                {"action": "generate_exhibit_binder", "priority": "high"},
                {"action": "generate_likely_questions", "priority": "high"},
                {"action": "generate_role_prep", "priority": "medium"}
            ]
        )
