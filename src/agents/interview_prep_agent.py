"""Interview Prep Agent.

Generates role-specific interview preparation documents for accreditation site visits.
Tailored to prepare institutional representatives for evaluator interviews.
"""

import json
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    now_iso,
    generate_id,
)
from src.config import Config


# Interview roles and their focus areas
INTERVIEW_ROLES = {
    "director": {
        "title": "Director/President",
        "description": "Institution leadership - strategic planning, governance, financial oversight",
        "focus_areas": [
            "Mission and strategic planning",
            "Governance and decision-making",
            "Financial stability and resource allocation",
            "Accreditation standards knowledge",
            "Enrollment management",
            "Response to prior findings",
            "Substantive changes since last visit",
        ],
    },
    "academic_dean": {
        "title": "Academic Dean",
        "description": "Academic leadership - curriculum, faculty, student outcomes",
        "focus_areas": [
            "Curriculum development and review",
            "Program Advisory Committee involvement",
            "Faculty hiring, evaluation, development",
            "SAP policy administration",
            "Student complaint handling",
            "Distance education oversight",
            "Student achievement data usage",
        ],
    },
    "faculty": {
        "title": "Faculty Member",
        "description": "Teaching staff - qualifications, instruction, assessment",
        "focus_areas": [
            "Qualifications for courses taught",
            "Curriculum development involvement",
            "Student assessment methods",
            "Feedback provision to students",
            "Professional development activities",
            "Student outcome data awareness",
            "Distance education delivery",
            "Instructional resources",
        ],
    },
    "financial_aid": {
        "title": "Financial Aid Director",
        "description": "Title IV administration - eligibility, disbursement, compliance",
        "focus_areas": [
            "Title IV administration procedures",
            "R2T4 calculation process",
            "Student eligibility verification",
            "Loan counseling procedures",
            "Cohort default rate management",
            "FAFSA processing timeline",
            "Student communication about aid",
        ],
    },
    "registrar": {
        "title": "Registrar",
        "description": "Records management - transcripts, FERPA, attendance",
        "focus_areas": [
            "Student records management",
            "FERPA compliance procedures",
            "Transcript evaluation process",
            "Transfer credit policies",
            "Attendance tracking",
            "SAP monitoring and notification",
            "Grade change procedures",
        ],
    },
    "admissions": {
        "title": "Admissions Representative",
        "description": "Enrollment - recruitment, disclosures, enrollment process",
        "focus_areas": [
            "Admissions criteria and process",
            "School presentation accuracy",
            "Pre-enrollment disclosures",
            "Employment/outcome questions handling",
            "Advertising compliance training",
            "Enrollment agreement understanding",
        ],
    },
    "career_services": {
        "title": "Career Services/Placement",
        "description": "Graduate outcomes - placement rates, employer relations",
        "focus_areas": [
            "Employment verification methodology",
            "Graduate job placement assistance",
            "Employer relationship development",
            "Employment rate calculation",
            "Placement documentation",
            "Graduate follow-up",
        ],
    },
    "students": {
        "title": "Current Students",
        "description": "Student perspective - experience, quality, support",
        "focus_areas": [
            "Reason for choosing school",
            "Admissions experience",
            "Complaint procedure awareness",
            "Catalog access",
            "Instruction quality consistency",
            "Resource adequacy",
            "Assignment feedback timeliness",
            "Achievement rate awareness",
        ],
    },
    "graduates": {
        "title": "Graduate Students",
        "description": "Alumni perspective - preparation, outcomes, satisfaction",
        "focus_areas": [
            "Program preparation for employment",
            "Job placement assistance received",
            "Education quality satisfaction",
            "School recommendation likelihood",
            "Training consistency with representation",
        ],
    },
}


@register_agent(AgentType.INTERVIEW_PREP)
class InterviewPrepAgent(BaseAgent):
    """Agent for generating role-specific interview preparation documents.

    Provides tools for:
    - Listing available interview roles
    - Generating role-specific prep documents
    - Creating likely questions based on standards and findings
    - Building talking points from institutional evidence
    - Identifying red flag areas from audit findings
    - Generating do-not-say lists
    - Exporting prep documents
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._prep_cache: Dict[str, Dict] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.INTERVIEW_PREP

    @property
    def system_prompt(self) -> str:
        return """You are an interview preparation specialist for accreditation site visits.
Your role is to prepare institutional staff for evaluator interviews during on-site visits.

Your responsibilities:
1. Generate role-specific interview preparation documents
2. Create likely questions based on accreditor standards and institutional findings
3. Develop talking points grounded in actual institutional evidence
4. Identify red flag areas that evaluators may probe
5. Provide honest, constructive response guidance
6. Create do-not-say lists to prevent common interview pitfalls

KEY REQUIREMENTS:
- All talking points must be backed by actual institutional evidence
- Red flag areas must derive from real audit findings, not speculation
- Questions should reflect both general standards AND institution-specific concerns
- Guidance must be honest - never suggest misleading or evasive responses
- Responses should demonstrate knowledge of accreditor expectations

When generating prep materials:
- Review the institution's audit findings to identify weak areas
- Map questions to specific standards being evaluated
- Include evidence citations for all talking points
- Flag areas where the institution may need to acknowledge improvement needs
- Provide guidance on redirecting to strengths without being evasive

NEVER fabricate evidence or suggest responses that misrepresent institutional reality.
Always recommend honest, direct communication with evaluators."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_interview_roles",
                "description": "List available interview roles with descriptions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_focus_areas": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include focus areas for each role",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "generate_role_prep",
                "description": "Generate a complete interview prep document for a specific role.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": list(INTERVIEW_ROLES.keys()),
                            "description": "The interview role to prepare for",
                        },
                        "program_id": {
                            "type": "string",
                            "description": "Specific program ID (required for faculty role)",
                        },
                        "accreditor_code": {
                            "type": "string",
                            "description": "Accreditor code (e.g., ACCSC, ABHES)",
                        },
                        "include_red_flags": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include red flag areas from audit findings",
                        },
                    },
                    "required": ["institution_id", "role"],
                },
            },
            {
                "name": "generate_likely_questions",
                "description": "Generate likely interview questions for a role based on standards and findings.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": list(INTERVIEW_ROLES.keys()),
                        },
                        "focus_area": {
                            "type": "string",
                            "description": "Specific focus area to generate questions for",
                        },
                        "include_audit_based": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include questions based on audit findings",
                        },
                    },
                    "required": ["institution_id", "role"],
                },
            },
            {
                "name": "generate_talking_points",
                "description": "Generate evidence-backed talking points for specific topics.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": list(INTERVIEW_ROLES.keys()),
                        },
                        "topic": {
                            "type": "string",
                            "description": "Topic to generate talking points for",
                        },
                    },
                    "required": ["institution_id", "role", "topic"],
                },
            },
            {
                "name": "identify_red_flags",
                "description": "Identify areas of concern from audit findings relevant to a role.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": list(INTERVIEW_ROLES.keys()),
                        },
                        "include_guidance": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include response guidance for each red flag",
                        },
                    },
                    "required": ["institution_id", "role"],
                },
            },
            {
                "name": "generate_do_not_list",
                "description": "Generate a list of things to avoid saying during interviews.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": list(INTERVIEW_ROLES.keys()),
                        },
                    },
                    "required": ["institution_id", "role"],
                },
            },
            {
                "name": "export_prep_document",
                "description": "Export interview prep document to file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "prep_id": {"type": "string"},
                        "format": {
                            "type": "string",
                            "enum": ["json", "docx"],
                            "default": "json",
                        },
                    },
                    "required": ["institution_id", "prep_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with the given input."""
        tool_map = {
            "list_interview_roles": self._tool_list_roles,
            "generate_role_prep": self._tool_generate_role_prep,
            "generate_likely_questions": self._tool_generate_questions,
            "generate_talking_points": self._tool_generate_talking_points,
            "identify_red_flags": self._tool_identify_red_flags,
            "generate_do_not_list": self._tool_generate_do_not_list,
            "export_prep_document": self._tool_export_prep,
        }

        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_list_roles(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available interview roles."""
        include_focus = params.get("include_focus_areas", True)

        roles = []
        for role_id, role_data in INTERVIEW_ROLES.items():
            role_info = {
                "id": role_id,
                "title": role_data["title"],
                "description": role_data["description"],
            }
            if include_focus:
                role_info["focus_areas"] = role_data["focus_areas"]
            roles.append(role_info)

        return {
            "success": True,
            "total": len(roles),
            "roles": roles,
        }

    def _tool_generate_role_prep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete interview prep document."""
        institution_id = params["institution_id"]
        role = params["role"]
        program_id = params.get("program_id")
        accreditor_code = params.get("accreditor_code", "ACCSC")
        include_red_flags = params.get("include_red_flags", True)

        if role not in INTERVIEW_ROLES:
            return {"error": f"Unknown role: {role}"}

        role_data = INTERVIEW_ROLES[role]

        # Load institution context
        institution = self._load_institution(institution_id)
        if not institution:
            return {"error": f"Institution not found: {institution_id}"}

        # Load audit findings for red flags
        audit_findings = self._load_audit_findings(institution_id, role)

        # Generate questions using AI
        questions = self._generate_ai_questions(
            institution, role_data, accreditor_code, audit_findings
        )

        # Generate talking points
        talking_points = self._generate_ai_talking_points(
            institution, role_data, audit_findings
        )

        # Identify red flags
        red_flags = []
        if include_red_flags and audit_findings:
            red_flags = self._map_findings_to_red_flags(audit_findings, role_data)

        # Generate do-not-say list
        do_not_list = self._generate_do_not_items(role)

        # Build prep document
        prep_id = generate_id("prep")
        prep_doc = {
            "id": prep_id,
            "institution_id": institution_id,
            "role": role,
            "role_title": role_data["title"],
            "program_id": program_id,
            "accreditor_code": accreditor_code,
            "focus_areas": role_data["focus_areas"],
            "likely_questions": questions,
            "talking_points": talking_points,
            "red_flags": red_flags,
            "do_not_list": do_not_list,
            "general_guidance": self._get_general_guidance(),
            "status": "draft",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        # Save to workspace
        self._save_prep_document(institution_id, prep_doc)
        self._prep_cache[prep_id] = prep_doc

        return {
            "success": True,
            "prep_id": prep_id,
            "role": role,
            "role_title": role_data["title"],
            "questions_count": len(questions),
            "talking_points_count": len(talking_points),
            "red_flags_count": len(red_flags),
            "document_path": f"visit_prep/interview_prep_{role}.json",
        }

    def _tool_generate_questions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate likely interview questions."""
        institution_id = params["institution_id"]
        role = params["role"]
        focus_area = params.get("focus_area")
        include_audit_based = params.get("include_audit_based", True)

        if role not in INTERVIEW_ROLES:
            return {"error": f"Unknown role: {role}"}

        role_data = INTERVIEW_ROLES[role]
        institution = self._load_institution(institution_id)

        # Filter focus areas if specified
        focus_areas = [focus_area] if focus_area else role_data["focus_areas"]

        # Load audit findings if needed
        audit_findings = []
        if include_audit_based:
            audit_findings = self._load_audit_findings(institution_id, role)

        # Generate questions via AI
        questions = self._generate_ai_questions(
            institution, role_data, "ACCSC", audit_findings, focus_areas
        )

        return {
            "success": True,
            "role": role,
            "focus_areas": focus_areas,
            "questions": questions,
            "total": len(questions),
            "includes_audit_based": include_audit_based and len(audit_findings) > 0,
        }

    def _tool_generate_talking_points(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate talking points for a topic."""
        institution_id = params["institution_id"]
        role = params["role"]
        topic = params["topic"]

        institution = self._load_institution(institution_id)
        if not institution:
            return {"error": f"Institution not found: {institution_id}"}

        # Generate via AI
        prompt = f"""Generate evidence-backed talking points for the topic: "{topic}"

Institution: {institution.get('name', 'Unknown')}
Role: {INTERVIEW_ROLES.get(role, {}).get('title', role)}

Generate 3-5 talking points that:
1. Are factual and verifiable
2. Include specific evidence references where possible
3. Demonstrate competence in this area
4. Are concise and memorable

Return as JSON array of objects with 'point' and 'evidence_source' fields."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            # Parse JSON from response
            try:
                # Find JSON array in response
                import re
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    points = json.loads(json_match.group())
                else:
                    points = [{"point": content, "evidence_source": "General knowledge"}]
            except json.JSONDecodeError:
                points = [{"point": content, "evidence_source": "General knowledge"}]

            return {
                "success": True,
                "topic": topic,
                "role": role,
                "talking_points": points,
            }
        except Exception as e:
            return {"error": f"Failed to generate talking points: {str(e)}"}

    def _tool_identify_red_flags(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Identify red flag areas for a role."""
        institution_id = params["institution_id"]
        role = params["role"]
        include_guidance = params.get("include_guidance", True)

        if role not in INTERVIEW_ROLES:
            return {"error": f"Unknown role: {role}"}

        role_data = INTERVIEW_ROLES[role]
        audit_findings = self._load_audit_findings(institution_id, role)

        red_flags = self._map_findings_to_red_flags(
            audit_findings, role_data, include_guidance
        )

        return {
            "success": True,
            "role": role,
            "red_flags": red_flags,
            "total": len(red_flags),
            "findings_analyzed": len(audit_findings),
        }

    def _tool_generate_do_not_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate do-not-say list for a role."""
        institution_id = params["institution_id"]
        role = params["role"]

        do_not_items = self._generate_do_not_items(role)

        return {
            "success": True,
            "role": role,
            "do_not_list": do_not_items,
            "total": len(do_not_items),
        }

    def _tool_export_prep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export prep document to file."""
        institution_id = params["institution_id"]
        prep_id = params["prep_id"]
        export_format = params.get("format", "json")

        # Load prep document
        prep_doc = self._prep_cache.get(prep_id)
        if not prep_doc:
            prep_doc = self._load_prep_document(institution_id, prep_id)

        if not prep_doc:
            return {"error": f"Prep document not found: {prep_id}"}

        role = prep_doc.get("role", "unknown")

        if export_format == "json":
            export_path = f"visit_prep/exports/interview_prep_{role}_{now_iso()[:10]}.json"
            if self.workspace_manager:
                self.workspace_manager.save_file(institution_id, export_path, prep_doc)

            return {
                "success": True,
                "prep_id": prep_id,
                "format": "json",
                "export_path": export_path,
            }
        else:
            # DOCX export would require python-docx
            return {
                "success": True,
                "prep_id": prep_id,
                "format": "json",  # Fallback
                "export_path": f"visit_prep/exports/interview_prep_{role}.json",
                "note": "DOCX export requires python-docx integration",
            }

    # Helper methods

    def _load_institution(self, institution_id: str) -> Optional[Dict]:
        """Load institution data."""
        if not self.workspace_manager:
            return {"id": institution_id, "name": "Test Institution"}

        data = self.workspace_manager.load_file(institution_id, "institution.json")
        return data

    def _load_audit_findings(self, institution_id: str, role: str) -> List[Dict]:
        """Load audit findings relevant to a role."""
        if not self.workspace_manager:
            return []

        # Load audit results
        audits_data = self.workspace_manager.load_file(institution_id, "audits/latest_audit.json")
        if not audits_data:
            return []

        findings = audits_data.get("findings", [])

        # Filter findings relevant to the role
        role_data = INTERVIEW_ROLES.get(role, {})
        focus_areas = role_data.get("focus_areas", [])

        # Simple keyword matching for now
        relevant = []
        focus_keywords = " ".join(focus_areas).lower()

        for finding in findings:
            desc = finding.get("description", "").lower()
            standard = finding.get("standard_ref", "").lower()

            # Check if finding relates to role's focus areas
            if any(keyword in desc or keyword in standard for keyword in focus_keywords.split()):
                relevant.append(finding)

        return relevant[:10]  # Limit to top 10

    def _generate_ai_questions(
        self,
        institution: Dict,
        role_data: Dict,
        accreditor_code: str,
        audit_findings: List[Dict],
        focus_areas: List[str] = None,
    ) -> List[Dict]:
        """Generate interview questions using AI."""
        if not focus_areas:
            focus_areas = role_data.get("focus_areas", [])

        # Build context
        findings_context = ""
        if audit_findings:
            findings_text = "\n".join([
                f"- {f.get('standard_ref', 'N/A')}: {f.get('description', '')[:100]}"
                for f in audit_findings[:5]
            ])
            findings_context = f"\n\nRecent audit findings:\n{findings_text}"

        prompt = f"""Generate likely interview questions for {role_data['title']} during an {accreditor_code} site visit.

Institution: {institution.get('name', 'Unknown')}
Focus areas: {', '.join(focus_areas)}{findings_context}

Generate 8-10 questions that:
1. Relate to the focus areas listed
2. Reflect accreditor standards
3. Probe areas of concern from findings (if any)
4. Mix general compliance questions with institution-specific ones

Return as JSON array with objects containing:
- question: The interview question
- standards_area: The focus area it relates to
- standard_ref: Relevant standard reference (e.g., "ACCSC Section I.A")
- suggested_response: Brief guidance on how to respond"""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            # Parse JSON
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                questions = json.loads(json_match.group())
                return questions
        except Exception:
            pass

        # Fallback: generate basic questions from focus areas
        return [
            {
                "question": f"How do you handle {area.lower()}?",
                "standards_area": area,
                "standard_ref": f"{accreditor_code} standards",
                "suggested_response": "Describe your procedures and evidence.",
            }
            for area in focus_areas[:5]
        ]

    def _generate_ai_talking_points(
        self,
        institution: Dict,
        role_data: Dict,
        audit_findings: List[Dict],
    ) -> List[Dict]:
        """Generate talking points using AI."""
        focus_areas = role_data.get("focus_areas", [])

        prompt = f"""Generate key talking points for {role_data['title']} to use during an accreditation interview.

Institution: {institution.get('name', 'Unknown')}
Focus areas: {', '.join(focus_areas[:5])}

Generate 5-7 talking points that:
1. Highlight institutional strengths
2. Demonstrate knowledge of procedures
3. Show awareness of compliance requirements
4. Are memorable and concise

Return as JSON array with objects containing:
- topic: The talking point topic
- points: Array of 2-3 specific things to mention
- evidence_sources: Array of document/evidence types that support this"""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        # Fallback
        return [
            {
                "topic": area,
                "points": [f"Describe {area.lower()} procedures"],
                "evidence_sources": ["Policy manual", "Procedure documentation"],
            }
            for area in focus_areas[:3]
        ]

    def _map_findings_to_red_flags(
        self,
        findings: List[Dict],
        role_data: Dict,
        include_guidance: bool = True,
    ) -> List[Dict]:
        """Map audit findings to red flag areas."""
        red_flags = []

        for finding in findings:
            severity = finding.get("severity", "advisory")
            if severity in ["critical", "significant"]:
                red_flag = {
                    "area": finding.get("standard_ref", "General compliance"),
                    "issue": finding.get("description", "")[:200],
                    "finding_id": finding.get("id"),
                    "severity": severity,
                }

                if include_guidance:
                    red_flag["honest_response"] = (
                        f"Acknowledge awareness of this area. Describe specific steps "
                        f"taken or planned to address: {finding.get('description', '')[:100]}..."
                    )

                red_flags.append(red_flag)

        return red_flags

    def _generate_do_not_items(self, role: str) -> List[str]:
        """Generate do-not-say items for a role."""
        # Universal do-not items
        universal = [
            "Don't guess or speculate - say 'I'll need to verify that' instead",
            "Don't contradict the Self-Evaluation Report",
            "Don't speak negatively about other departments or staff",
            "Don't volunteer information beyond what's asked",
            "Don't promise things you can't deliver",
            "Don't use phrases like 'We should be doing...' or 'We hope to...'",
        ]

        # Role-specific additions
        role_specific = {
            "director": [
                "Don't claim unaware of compliance issues if asked directly",
                "Don't deflect responsibility to subordinates",
            ],
            "financial_aid": [
                "Don't discuss individual student financial information",
                "Don't speculate on Title IV regulatory changes",
            ],
            "admissions": [
                "Don't make outcome guarantees or employment promises",
                "Don't discuss competitor institutions",
            ],
            "faculty": [
                "Don't claim expertise outside your teaching areas",
                "Don't discuss student performance specifics",
            ],
        }

        return universal + role_specific.get(role, [])

    def _get_general_guidance(self) -> List[str]:
        """Get general interview guidance."""
        return [
            "Be truthful and specific - evaluators appreciate honesty",
            "Refer to documentation when possible",
            "If you don't know something, say so and offer to find out",
            "Use 'we' language to show teamwork",
            "Stay calm and professional, even with difficult questions",
            "Keep answers focused and concise",
            "Provide examples to illustrate your points",
        ]

    def _save_prep_document(self, institution_id: str, prep_doc: Dict) -> None:
        """Save prep document to workspace."""
        if not self.workspace_manager:
            return

        role = prep_doc.get("role", "unknown")
        path = f"visit_prep/interview_prep_{role}.json"
        self.workspace_manager.save_file(institution_id, path, prep_doc)

    def _load_prep_document(self, institution_id: str, prep_id: str) -> Optional[Dict]:
        """Load a prep document by ID."""
        if not self.workspace_manager:
            return None

        # Search visit_prep directory for matching document
        for role in INTERVIEW_ROLES.keys():
            path = f"visit_prep/interview_prep_{role}.json"
            doc = self.workspace_manager.load_file(institution_id, path)
            if doc and doc.get("id") == prep_id:
                return doc

        return None
