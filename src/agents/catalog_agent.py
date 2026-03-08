"""Catalog Agent.

Builds, audits, and maintains institutional catalogs.
Catalogs are complex documents (50-100+ pages) that must satisfy
requirements from every regulatory body simultaneously.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    Institution,
    Program,
    DocumentType,
    ComplianceStatus,
    Language,
    now_iso,
    generate_id,
)
from src.config import Config


# Catalog section definitions by accreditor
CATALOG_SECTIONS = {
    "ACCSC": [
        {"id": "cover", "name": "Cover Page", "required": True},
        {"id": "toc", "name": "Table of Contents", "required": True},
        {"id": "mission", "name": "Mission Statement", "required": True},
        {"id": "history", "name": "School History", "required": True},
        {"id": "facilities", "name": "Facilities Description", "required": True},
        {"id": "accreditation", "name": "Accreditation & Approvals", "required": True},
        {"id": "admin", "name": "Administrative Staff", "required": True},
        {"id": "faculty", "name": "Faculty Listing", "required": True},
        {"id": "calendar", "name": "Academic Calendar", "required": True},
        {"id": "holidays", "name": "Holiday Schedule", "required": True},
        {"id": "admissions", "name": "Admissions Requirements", "required": True},
        {"id": "enrollment", "name": "Enrollment Procedures", "required": True},
        {"id": "transfer_credit", "name": "Transfer Credit Policy", "required": True},
        {"id": "attendance", "name": "Attendance Policy", "required": True},
        {"id": "sap", "name": "Satisfactory Academic Progress", "required": True},
        {"id": "grading", "name": "Grading System", "required": True},
        {"id": "probation", "name": "Academic Probation/Dismissal", "required": True},
        {"id": "leave", "name": "Leave of Absence Policy", "required": True},
        {"id": "conduct", "name": "Student Conduct", "required": True},
        {"id": "grievance", "name": "Grievance Procedures", "required": True},
        {"id": "tuition", "name": "Tuition & Fees", "required": True},
        {"id": "refund", "name": "Refund Policy", "required": True},
        {"id": "financial_aid", "name": "Financial Aid Information", "required": True},
        {"id": "services", "name": "Student Services", "required": True},
        {"id": "placement", "name": "Career Services/Placement", "required": True},
        {"id": "programs", "name": "Program Descriptions", "required": True},
        {"id": "course_desc", "name": "Course Descriptions", "required": True},
        {"id": "ferpa", "name": "FERPA Notice", "required": True},
        {"id": "nondiscrim", "name": "Non-Discrimination Policy", "required": True},
        {"id": "ada", "name": "ADA/Disability Services", "required": True},
        {"id": "drug_free", "name": "Drug-Free Policy", "required": True},
        {"id": "campus_safety", "name": "Campus Safety/Security", "required": True},
        {"id": "copyright", "name": "Copyright Policy", "required": False},
        {"id": "appendices", "name": "Appendices", "required": False},
    ],
    "ABHES": [
        {"id": "cover", "name": "Cover Page", "required": True},
        {"id": "toc", "name": "Table of Contents", "required": True},
        {"id": "mission", "name": "Mission & Objectives", "required": True},
        {"id": "accreditation", "name": "Accreditation Status", "required": True},
        {"id": "ownership", "name": "Ownership Information", "required": True},
        {"id": "admin", "name": "Administration", "required": True},
        {"id": "faculty", "name": "Faculty", "required": True},
        {"id": "calendar", "name": "Academic Calendar", "required": True},
        {"id": "admissions", "name": "Admissions", "required": True},
        {"id": "programs", "name": "Programs of Study", "required": True},
        {"id": "course_desc", "name": "Course Descriptions", "required": True},
        {"id": "grading", "name": "Grading Policies", "required": True},
        {"id": "sap", "name": "SAP Policy", "required": True},
        {"id": "attendance", "name": "Attendance", "required": True},
        {"id": "tuition", "name": "Tuition & Fees", "required": True},
        {"id": "refund", "name": "Cancellation & Refund", "required": True},
        {"id": "financial_aid", "name": "Financial Assistance", "required": True},
        {"id": "services", "name": "Student Services", "required": True},
        {"id": "grievance", "name": "Grievance Policy", "required": True},
        {"id": "ferpa", "name": "FERPA", "required": True},
    ],
}

# Default to ACCSC if not specified
DEFAULT_SECTIONS = CATALOG_SECTIONS["ACCSC"]


@register_agent(AgentType.CATALOG)
class CatalogAgent(BaseAgent):
    """Agent for building, auditing, and maintaining institutional catalogs.

    Provides tools for:
    - Auditing existing catalogs against regulatory requirements
    - Generating catalog sections from institution data
    - Building complete catalogs from scratch
    - Updating catalogs with truth index changes
    - Exporting to DOCX format
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._catalog_cache: Dict[str, Any] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CATALOG

    @property
    def system_prompt(self) -> str:
        return """You are a catalog specialist for educational institutions. Your responsibilities:

1. Build institutional catalogs that satisfy all regulatory requirements
2. Audit existing catalogs against accreditor standards and federal/state regulations
3. Generate catalog sections using institution data, programs, and policies
4. Ensure consistency between catalog content and enrollment agreements
5. Maintain truth index alignment for all catalog values

CATALOG REQUIREMENTS:
- Every accreditor has specific catalog checklist requirements
- Federal regulations (FERPA, Title IV, Clery, etc.) add mandatory disclosures
- State requirements vary by jurisdiction
- Catalogs must match enrollment agreement content exactly

WRITING STANDARDS:
- Clear, student-focused language
- Accurate representation of programs, costs, and policies
- Proper legal disclosures and disclaimers
- Bilingual content when required (English/Spanish)

Always cite the specific regulatory source for each required element."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_catalog_requirements",
                "description": "Get required catalog sections for an accreditor.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "accreditor_code": {
                            "type": "string",
                            "description": "Accreditor code (ACCSC, ABHES, etc.)",
                        },
                        "include_federal": {
                            "type": "boolean",
                            "default": True,
                        },
                        "state_code": {
                            "type": "string",
                            "description": "State code for state-specific requirements",
                        },
                    },
                    "required": ["accreditor_code"],
                },
            },
            {
                "name": "audit_catalog",
                "description": "Audit an existing catalog against regulatory requirements.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "catalog_id": {
                            "type": "string",
                            "description": "Document ID of catalog to audit",
                        },
                        "accreditor_code": {"type": "string"},
                        "check_consistency": {
                            "type": "boolean",
                            "default": True,
                            "description": "Cross-check against enrollment agreements",
                        },
                    },
                    "required": ["institution_id", "catalog_id"],
                },
            },
            {
                "name": "generate_catalog_section",
                "description": "Generate or update a specific catalog section.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "section_id": {
                            "type": "string",
                            "description": "Section ID (mission, programs, tuition, etc.)",
                        },
                        "language": {
                            "type": "string",
                            "enum": ["en", "es", "bilingual"],
                            "default": "en",
                        },
                        "draft_mode": {
                            "type": "boolean",
                            "default": False,
                            "description": "Draft mode uses informal tone with inline notes",
                        },
                        "program_id": {
                            "type": "string",
                            "description": "Specific program for program sections",
                        },
                    },
                    "required": ["institution_id", "section_id"],
                },
            },
            {
                "name": "build_catalog",
                "description": "Build a complete catalog from institution data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "language": {
                            "type": "string",
                            "enum": ["en", "es", "bilingual"],
                            "default": "en",
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific sections to generate (all if omitted)",
                        },
                        "draft_mode": {
                            "type": "boolean",
                            "default": True,
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "update_catalog_from_truth",
                "description": "Update catalog sections from truth index values.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "catalog_id": {"type": "string"},
                        "sections_to_update": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Sections to update (all changed if omitted)",
                        },
                    },
                    "required": ["institution_id", "catalog_id"],
                },
            },
            {
                "name": "validate_catalog",
                "description": "Validate catalog completeness and consistency.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "catalog_id": {"type": "string"},
                        "validation_level": {
                            "type": "string",
                            "enum": ["basic", "standard", "strict"],
                            "default": "standard",
                        },
                    },
                    "required": ["institution_id", "catalog_id"],
                },
            },
            {
                "name": "export_catalog",
                "description": "Export catalog to DOCX format.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "catalog_id": {"type": "string"},
                        "format": {
                            "type": "string",
                            "enum": ["docx", "pdf", "html"],
                            "default": "docx",
                        },
                        "include_toc": {
                            "type": "boolean",
                            "default": True,
                        },
                    },
                    "required": ["institution_id", "catalog_id"],
                },
            },
            {
                "name": "list_catalogs",
                "description": "List all catalogs for an institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "include_drafts": {
                            "type": "boolean",
                            "default": True,
                        },
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "get_catalog_requirements": self._tool_get_requirements,
            "audit_catalog": self._tool_audit_catalog,
            "generate_catalog_section": self._tool_generate_section,
            "build_catalog": self._tool_build_catalog,
            "update_catalog_from_truth": self._tool_update_from_truth,
            "validate_catalog": self._tool_validate_catalog,
            "export_catalog": self._tool_export_catalog,
            "list_catalogs": self._tool_list_catalogs,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _load_catalog_registry(self, institution_id: str) -> Dict[str, Any]:
        """Load catalog registry from workspace."""
        if not self.workspace_manager:
            return {"catalogs": [], "updated_at": now_iso()}

        data = self.workspace_manager.load_file(
            institution_id, "catalog/catalog_registry.json"
        )
        return data or {"catalogs": [], "updated_at": now_iso()}

    def _save_catalog_registry(self, institution_id: str, registry: Dict[str, Any]) -> None:
        """Save catalog registry to workspace."""
        if not self.workspace_manager:
            return

        registry["updated_at"] = now_iso()
        self.workspace_manager.save_file(
            institution_id, "catalog/catalog_registry.json", registry
        )

    def _load_catalog(self, institution_id: str, catalog_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific catalog."""
        if not self.workspace_manager:
            return None

        return self.workspace_manager.load_file(
            institution_id, f"catalog/drafts/{catalog_id}.json"
        )

    def _save_catalog(self, institution_id: str, catalog: Dict[str, Any]) -> None:
        """Save catalog to workspace."""
        if not self.workspace_manager:
            return

        catalog_id = catalog["id"]
        self.workspace_manager.save_file(
            institution_id, f"catalog/drafts/{catalog_id}.json", catalog
        )

    def _tool_get_requirements(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get required catalog sections for an accreditor."""
        accreditor_code = params["accreditor_code"].upper()
        include_federal = params.get("include_federal", True)
        state_code = params.get("state_code")

        sections = CATALOG_SECTIONS.get(accreditor_code, DEFAULT_SECTIONS)

        # Add federal requirements
        federal_requirements = []
        if include_federal:
            federal_requirements = [
                {"id": "ferpa", "name": "FERPA Notice", "source": "federal", "required": True},
                {"id": "title_iv", "name": "Title IV Disclosures", "source": "federal", "required": True},
                {"id": "voter_reg", "name": "Voter Registration", "source": "federal", "required": True},
                {"id": "constitution", "name": "Constitution Day", "source": "federal", "required": True},
                {"id": "copyright", "name": "Copyright/P2P Policy", "source": "federal", "required": True},
                {"id": "clery", "name": "Campus Security (Clery)", "source": "federal", "required": True},
                {"id": "drug_free", "name": "Drug-Free Schools", "source": "federal", "required": True},
            ]

        # Add state requirements
        state_requirements = []
        if state_code:
            state_code = state_code.upper()
            if state_code == "PR":
                state_requirements = [
                    {"id": "cepr_license", "name": "CEPR License Statement", "source": "state", "required": True},
                    {"id": "bilingual", "name": "Spanish Translation", "source": "state", "required": True},
                ]
            elif state_code == "FL":
                state_requirements = [
                    {"id": "cie_license", "name": "CIE License Statement", "source": "state", "required": True},
                ]
            elif state_code == "CA":
                state_requirements = [
                    {"id": "bppe_approval", "name": "BPPE Approval Statement", "source": "state", "required": True},
                    {"id": "strf", "name": "STRF Disclosure", "source": "state", "required": True},
                ]

        return {
            "success": True,
            "accreditor": accreditor_code,
            "sections": sections,
            "federal_requirements": federal_requirements,
            "state_requirements": state_requirements,
            "total_required": len([s for s in sections if s.get("required", True)]),
        }

    def _tool_audit_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Audit existing catalog against requirements."""
        institution_id = params["institution_id"]
        catalog_id = params["catalog_id"]
        accreditor_code = params.get("accreditor_code", "ACCSC")
        check_consistency = params.get("check_consistency", True)

        catalog = self._load_catalog(institution_id, catalog_id)
        if not catalog:
            return {"error": f"Catalog {catalog_id} not found"}

        # Get requirements
        requirements = self._tool_get_requirements({
            "accreditor_code": accreditor_code,
            "include_federal": True,
        })

        sections = requirements["sections"]
        catalog_sections = catalog.get("sections", {})

        findings = []
        missing_sections = []
        incomplete_sections = []

        for section in sections:
            section_id = section["id"]
            section_name = section["name"]
            required = section.get("required", True)

            if section_id not in catalog_sections:
                if required:
                    missing_sections.append(section_name)
                    findings.append({
                        "section": section_name,
                        "status": "missing",
                        "severity": "critical" if required else "advisory",
                        "message": f"Required section '{section_name}' is missing",
                    })
            else:
                content = catalog_sections[section_id]
                if not content.get("content") or len(content.get("content", "")) < 50:
                    incomplete_sections.append(section_name)
                    findings.append({
                        "section": section_name,
                        "status": "incomplete",
                        "severity": "significant",
                        "message": f"Section '{section_name}' appears incomplete",
                    })

        # Check consistency with truth index
        consistency_issues = []
        if check_consistency and self.workspace_manager:
            truth_index = self.workspace_manager.load_file(
                institution_id, "truth_index.json"
            )
            if truth_index:
                # Check tuition values
                if "tuition" in catalog_sections:
                    tuition_section = catalog_sections["tuition"]
                    # Would compare against truth_index values here
                    pass

        compliance_score = 100
        if missing_sections:
            compliance_score -= len(missing_sections) * 5
        if incomplete_sections:
            compliance_score -= len(incomplete_sections) * 2
        compliance_score = max(0, compliance_score)

        # Save audit results
        audit_result = {
            "id": generate_id("audit"),
            "catalog_id": catalog_id,
            "accreditor": accreditor_code,
            "audited_at": now_iso(),
            "compliance_score": compliance_score,
            "findings": findings,
            "missing_sections": missing_sections,
            "incomplete_sections": incomplete_sections,
            "consistency_issues": consistency_issues,
        }

        if self.workspace_manager:
            self.workspace_manager.save_file(
                institution_id,
                f"catalog/audits/{audit_result['id']}.json",
                audit_result
            )

        return {
            "success": True,
            "audit_id": audit_result["id"],
            "compliance_score": compliance_score,
            "total_findings": len(findings),
            "missing_sections": missing_sections,
            "incomplete_sections": incomplete_sections,
            "findings": findings[:10],  # Return first 10
        }

    def _tool_generate_section(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a specific catalog section."""
        institution_id = params["institution_id"]
        section_id = params["section_id"]
        language = params.get("language", "en")
        draft_mode = params.get("draft_mode", False)
        program_id = params.get("program_id")

        # Load institution data
        institution = None
        if self.workspace_manager:
            institution = self.workspace_manager.load_institution(institution_id)

        if not institution:
            return {"error": f"Institution {institution_id} not found"}

        # Build generation prompt based on section
        section_prompts = {
            "mission": self._build_mission_prompt,
            "programs": self._build_programs_prompt,
            "tuition": self._build_tuition_prompt,
            "admissions": self._build_admissions_prompt,
            "sap": self._build_sap_prompt,
            "refund": self._build_refund_prompt,
            "grading": self._build_grading_prompt,
            "attendance": self._build_attendance_prompt,
            "grievance": self._build_grievance_prompt,
            "ferpa": self._build_ferpa_prompt,
        }

        prompt_builder = section_prompts.get(section_id, self._build_generic_prompt)
        prompt = prompt_builder(institution, section_id, language, program_id)

        # Add draft mode instructions
        if draft_mode:
            prompt += "\n\nDRAFT MODE: Use conversational tone. Add inline notes like '>>> Need to verify this date' for items requiring confirmation."
        else:
            prompt += "\n\nFINAL MODE: Use formal, professional tone appropriate for an official catalog."

        # Generate content via AI
        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            return {
                "success": True,
                "section_id": section_id,
                "language": language,
                "draft_mode": draft_mode,
                "content": content,
                "word_count": len(content.split()),
                "generated_at": now_iso(),
            }
        except Exception as e:
            return {
                "error": f"Generation failed: {str(e)}",
                "section_id": section_id,
            }

    def _build_mission_prompt(self, institution: Institution, section_id: str,
                              language: str, program_id: Optional[str]) -> str:
        """Build prompt for mission section."""
        return f"""Generate a mission statement section for the institutional catalog.

Institution: {institution.name}
Accreditor: {institution.accrediting_body.value}
Programs offered: {len(institution.programs)}
Language: {language}

Include:
1. Mission statement (clear, student-focused)
2. Institutional objectives/goals
3. Philosophy of education
4. Brief history if available

The mission should reflect the institution's commitment to career education and student success."""

    def _build_programs_prompt(self, institution: Institution, section_id: str,
                               language: str, program_id: Optional[str]) -> str:
        """Build prompt for programs section."""
        programs_info = []
        target_programs = institution.programs

        if program_id:
            target_programs = [p for p in institution.programs if p.id == program_id]

        for prog in target_programs:
            programs_info.append(f"""
Program: {prog.name_en}
Credential: {prog.credential_level.value}
Duration: {prog.duration_months} months
Credits/Hours: {prog.total_credits}
Total Cost: ${prog.total_cost:,.2f}
Modality: {prog.modality.value}
Licensure Required: {prog.licensure_required}
""")

        return f"""Generate program description sections for the institutional catalog.

Institution: {institution.name}
Language: {language}

PROGRAMS:
{''.join(programs_info)}

For each program include:
1. Program name and credential awarded
2. Program description and objectives
3. Career opportunities
4. Admission requirements specific to program
5. Program length and schedule
6. Total credits/clock hours
7. Equipment/supplies provided
8. Licensure/certification information if applicable"""

    def _build_tuition_prompt(self, institution: Institution, section_id: str,
                              language: str, program_id: Optional[str]) -> str:
        """Build prompt for tuition section."""
        tuition_info = []
        for prog in institution.programs:
            tuition_info.append(f"""
{prog.name_en}:
- Total Program Cost: ${prog.total_cost:,.2f}
- Cost Per Period: ${prog.cost_per_period:,.2f}
- Books/Materials: ${prog.book_cost:,.2f}
- Other Costs: {prog.other_costs}
""")

        return f"""Generate the tuition and fees section for the institutional catalog.

Institution: {institution.name}
Language: {language}

TUITION BY PROGRAM:
{''.join(tuition_info)}

Include:
1. Tuition costs per program
2. Registration fees
3. Books and materials costs
4. Equipment/supply costs
5. Other fees (lab fees, certification exam fees, etc.)
6. Payment schedule options
7. Note about fee changes

Use a clear table format where appropriate."""

    def _build_admissions_prompt(self, institution: Institution, section_id: str,
                                 language: str, program_id: Optional[str]) -> str:
        """Build prompt for admissions section."""
        return f"""Generate the admissions requirements section for the institutional catalog.

Institution: {institution.name}
State: {institution.state_code}
Language: {language}

Include:
1. General admission requirements
2. Age requirements
3. Education requirements (diploma, GED, ATB)
4. Program-specific requirements
5. Documentation required
6. Enrollment process steps
7. Visa requirements for international students (if applicable)
8. Re-admission policy
9. Non-discrimination statement"""

    def _build_sap_prompt(self, institution: Institution, section_id: str,
                          language: str, program_id: Optional[str]) -> str:
        """Build prompt for SAP section."""
        return f"""Generate the Satisfactory Academic Progress (SAP) policy section.

Institution: {institution.name}
Accreditor: {institution.accrediting_body.value}
Language: {language}

Include all required SAP components:
1. Qualitative measure (GPA requirements)
2. Quantitative measure (pace/completion rate)
3. Maximum timeframe
4. Evaluation periods
5. Warning status
6. Probation status
7. Academic plan requirements
8. Appeal process
9. Reinstatement procedures
10. Impact on financial aid eligibility

Ensure compliance with federal Title IV regulations."""

    def _build_refund_prompt(self, institution: Institution, section_id: str,
                             language: str, program_id: Optional[str]) -> str:
        """Build prompt for refund section."""
        state = institution.state_code or "federal"
        return f"""Generate the cancellation and refund policy section.

Institution: {institution.name}
State: {state}
Accreditor: {institution.accrediting_body.value}
Language: {language}

Include:
1. Three-day cancellation right
2. Cancellation before class start
3. Withdrawal after classes begin
4. Refund calculation method (pro-rata or other)
5. Return of Title IV funds policy
6. Books/equipment refund policy
7. State-specific refund requirements for {state}
8. Sample refund calculation

Ensure compliance with both federal and state refund requirements."""

    def _build_grading_prompt(self, institution: Institution, section_id: str,
                              language: str, program_id: Optional[str]) -> str:
        """Build prompt for grading section."""
        return f"""Generate the grading system section for the catalog.

Institution: {institution.name}
Language: {language}

Include:
1. Grading scale (letter grades with percentages)
2. GPA calculation method
3. Grade point values
4. Pass/Fail designations
5. Incomplete grade policy
6. Repeat course policy
7. Grade appeal process
8. Academic honors recognition"""

    def _build_attendance_prompt(self, institution: Institution, section_id: str,
                                 language: str, program_id: Optional[str]) -> str:
        """Build prompt for attendance section."""
        return f"""Generate the attendance policy section.

Institution: {institution.name}
Modalities: {set(p.modality.value for p in institution.programs)}
Language: {language}

Include:
1. Attendance requirements
2. Tardiness policy
3. Absence documentation
4. Make-up work policy
5. Impact on grades
6. Excessive absence consequences
7. Leave of absence policy
8. Distance education attendance (if applicable)"""

    def _build_grievance_prompt(self, institution: Institution, section_id: str,
                                language: str, program_id: Optional[str]) -> str:
        """Build prompt for grievance section."""
        return f"""Generate the grievance procedures section.

Institution: {institution.name}
Accreditor: {institution.accrediting_body.value}
State: {institution.state_code}
Language: {language}

Include:
1. Definition of grievance
2. Informal resolution process
3. Formal grievance steps
4. Timeline for each step
5. Documentation requirements
6. Appeal process
7. Contact information for filing
8. State agency contact (for unresolved complaints)
9. Accreditor complaint contact
10. Non-retaliation statement"""

    def _build_ferpa_prompt(self, institution: Institution, section_id: str,
                            language: str, program_id: Optional[str]) -> str:
        """Build prompt for FERPA section."""
        return f"""Generate the FERPA (Family Educational Rights and Privacy Act) notice.

Institution: {institution.name}
Language: {language}

Include all required FERPA elements:
1. Right to inspect records
2. Right to request amendment
3. Right to consent to disclosure
4. Right to file complaint with Department of Education
5. Definition of education records
6. Definition of directory information
7. How to opt out of directory information release
8. Conditions for disclosure without consent
9. Record of disclosures
10. Annual notification statement"""

    def _build_generic_prompt(self, institution: Institution, section_id: str,
                              language: str, program_id: Optional[str]) -> str:
        """Build generic prompt for unlisted sections."""
        return f"""Generate the '{section_id}' section for the institutional catalog.

Institution: {institution.name}
Accreditor: {institution.accrediting_body.value}
Language: {language}

Generate appropriate content for this catalog section following regulatory requirements
and industry best practices for career education institutions."""

    def _tool_build_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build a complete catalog from institution data."""
        institution_id = params["institution_id"]
        language = params.get("language", "en")
        requested_sections = params.get("sections")
        draft_mode = params.get("draft_mode", True)

        # Load institution
        institution = None
        if self.workspace_manager:
            institution = self.workspace_manager.load_institution(institution_id)

        if not institution:
            return {"error": f"Institution {institution_id} not found"}

        accreditor = institution.accrediting_body.value
        all_sections = CATALOG_SECTIONS.get(accreditor, DEFAULT_SECTIONS)

        # Filter sections if specified
        if requested_sections:
            sections_to_build = [s for s in all_sections if s["id"] in requested_sections]
        else:
            sections_to_build = all_sections

        # Create new catalog
        catalog = {
            "id": generate_id("cat"),
            "institution_id": institution_id,
            "title": f"{institution.name} Catalog",
            "language": language,
            "accreditor": accreditor,
            "status": "draft",
            "sections": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        sections_generated = []
        sections_failed = []

        # Generate each section
        for section in sections_to_build:
            section_id = section["id"]
            result = self._tool_generate_section({
                "institution_id": institution_id,
                "section_id": section_id,
                "language": language,
                "draft_mode": draft_mode,
            })

            if result.get("success"):
                catalog["sections"][section_id] = {
                    "name": section["name"],
                    "content": result["content"],
                    "generated_at": result["generated_at"],
                    "word_count": result["word_count"],
                }
                sections_generated.append(section["name"])
            else:
                sections_failed.append(section["name"])

        # Save catalog
        self._save_catalog(institution_id, catalog)

        # Update registry
        registry = self._load_catalog_registry(institution_id)
        registry["catalogs"].append({
            "id": catalog["id"],
            "title": catalog["title"],
            "language": language,
            "status": "draft",
            "sections_count": len(sections_generated),
            "created_at": catalog["created_at"],
        })
        self._save_catalog_registry(institution_id, registry)

        return {
            "success": True,
            "catalog_id": catalog["id"],
            "title": catalog["title"],
            "sections_generated": len(sections_generated),
            "sections_failed": len(sections_failed),
            "generated": sections_generated,
            "failed": sections_failed,
        }

    def _tool_update_from_truth(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update catalog sections from truth index."""
        institution_id = params["institution_id"]
        catalog_id = params["catalog_id"]
        sections_to_update = params.get("sections_to_update")

        catalog = self._load_catalog(institution_id, catalog_id)
        if not catalog:
            return {"error": f"Catalog {catalog_id} not found"}

        # Load truth index
        truth_index = None
        if self.workspace_manager:
            truth_index = self.workspace_manager.load_file(
                institution_id, "truth_index.json"
            )

        if not truth_index:
            return {"error": "Truth index not found"}

        updated_sections = []

        # Update tuition section if truth index has cost changes
        if "tuition" in (sections_to_update or catalog["sections"]):
            if "programs" in truth_index:
                result = self._tool_generate_section({
                    "institution_id": institution_id,
                    "section_id": "tuition",
                    "language": catalog.get("language", "en"),
                    "draft_mode": False,
                })
                if result.get("success"):
                    catalog["sections"]["tuition"]["content"] = result["content"]
                    catalog["sections"]["tuition"]["updated_at"] = now_iso()
                    updated_sections.append("tuition")

        catalog["updated_at"] = now_iso()
        self._save_catalog(institution_id, catalog)

        return {
            "success": True,
            "catalog_id": catalog_id,
            "sections_updated": updated_sections,
            "updated_at": catalog["updated_at"],
        }

    def _tool_validate_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate catalog completeness and consistency."""
        institution_id = params["institution_id"]
        catalog_id = params["catalog_id"]
        validation_level = params.get("validation_level", "standard")

        catalog = self._load_catalog(institution_id, catalog_id)
        if not catalog:
            return {"error": f"Catalog {catalog_id} not found"}

        accreditor = catalog.get("accreditor", "ACCSC")
        required_sections = CATALOG_SECTIONS.get(accreditor, DEFAULT_SECTIONS)

        issues = []
        warnings = []

        # Check for required sections
        for section in required_sections:
            if section.get("required", True):
                if section["id"] not in catalog.get("sections", {}):
                    issues.append(f"Missing required section: {section['name']}")

        # Check section content length
        for section_id, section_data in catalog.get("sections", {}).items():
            content = section_data.get("content", "")
            word_count = len(content.split())

            if word_count < 50:
                issues.append(f"Section '{section_id}' is too short ({word_count} words)")
            elif word_count < 100 and validation_level == "strict":
                warnings.append(f"Section '{section_id}' may be insufficient ({word_count} words)")

        # Check for draft markers in final mode
        if validation_level != "basic":
            for section_id, section_data in catalog.get("sections", {}).items():
                content = section_data.get("content", "")
                if ">>>" in content or "[TBD]" in content or "[TODO]" in content:
                    warnings.append(f"Section '{section_id}' contains draft markers")

        is_valid = len(issues) == 0
        validation_result = {
            "id": generate_id("val"),
            "catalog_id": catalog_id,
            "validated_at": now_iso(),
            "validation_level": validation_level,
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
        }

        return {
            "success": True,
            "is_valid": is_valid,
            "issues_count": len(issues),
            "warnings_count": len(warnings),
            "issues": issues,
            "warnings": warnings,
        }

    def _tool_export_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export catalog to file format."""
        institution_id = params["institution_id"]
        catalog_id = params["catalog_id"]
        export_format = params.get("format", "docx")
        include_toc = params.get("include_toc", True)

        catalog = self._load_catalog(institution_id, catalog_id)
        if not catalog:
            return {"error": f"Catalog {catalog_id} not found"}

        # Build export content
        sections = catalog.get("sections", {})
        accreditor = catalog.get("accreditor", "ACCSC")
        section_order = [s["id"] for s in CATALOG_SECTIONS.get(accreditor, DEFAULT_SECTIONS)]

        # Order sections
        ordered_content = []
        for section_id in section_order:
            if section_id in sections:
                ordered_content.append({
                    "id": section_id,
                    "name": sections[section_id].get("name", section_id),
                    "content": sections[section_id].get("content", ""),
                })

        # For now, save as JSON (DOCX export would require python-docx)
        export_path = f"catalog/exports/{catalog_id}_{now_iso()[:10]}.json"
        export_data = {
            "title": catalog.get("title"),
            "institution_id": institution_id,
            "exported_at": now_iso(),
            "format": export_format,
            "sections": ordered_content,
        }

        if self.workspace_manager:
            self.workspace_manager.save_file(
                institution_id, export_path, export_data
            )

        return {
            "success": True,
            "catalog_id": catalog_id,
            "format": export_format,
            "sections_exported": len(ordered_content),
            "export_path": export_path,
            "note": "Full DOCX export requires python-docx integration",
        }

    def _tool_list_catalogs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all catalogs for an institution."""
        institution_id = params["institution_id"]
        include_drafts = params.get("include_drafts", True)

        registry = self._load_catalog_registry(institution_id)
        catalogs = registry.get("catalogs", [])

        if not include_drafts:
            catalogs = [c for c in catalogs if c.get("status") != "draft"]

        return {
            "success": True,
            "total": len(catalogs),
            "catalogs": catalogs,
        }
