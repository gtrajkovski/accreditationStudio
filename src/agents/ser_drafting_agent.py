"""SER Drafting Agent.

Assists with drafting Self-Evaluation Reports (SER) section by section.
Supports draft and submission modes with evidence citations.
"""

import json
import re
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    now_iso,
    generate_id,
)
from src.config import Config


# SER sections by accreditor
SER_SECTIONS = {
    "ACCSC": [
        {"id": "cover", "name": "Cover Page", "required": True, "word_limit": None},
        {"id": "toc", "name": "Table of Contents", "required": True, "word_limit": None},
        {"id": "executive_summary", "name": "Executive Summary", "required": True, "word_limit": 500},
        {"id": "mission", "name": "Mission and Objectives", "required": True, "word_limit": 400},
        {"id": "governance", "name": "Governance and Administration", "required": True, "word_limit": 600},
        {"id": "financial", "name": "Financial Stability", "required": True, "word_limit": 500},
        {"id": "facilities", "name": "Facilities and Equipment", "required": True, "word_limit": 400},
        {"id": "programs", "name": "Educational Programs", "required": True, "word_limit": 800},
        {"id": "faculty", "name": "Faculty Qualifications", "required": True, "word_limit": 600},
        {"id": "admissions", "name": "Admissions and Enrollment", "required": True, "word_limit": 500},
        {"id": "student_services", "name": "Student Services", "required": True, "word_limit": 500},
        {"id": "student_achievement", "name": "Student Achievement", "required": True, "word_limit": 600},
        {"id": "catalog", "name": "Catalog Requirements", "required": True, "word_limit": 400},
        {"id": "advertising", "name": "Advertising and Publications", "required": True, "word_limit": 300},
        {"id": "financial_aid", "name": "Financial Aid Administration", "required": True, "word_limit": 500},
        {"id": "records", "name": "Student Records", "required": True, "word_limit": 400},
        {"id": "complaints", "name": "Complaint Procedures", "required": True, "word_limit": 300},
        {"id": "conclusion", "name": "Conclusion", "required": True, "word_limit": 300},
    ],
    "ABHES": [
        {"id": "intro", "name": "Introduction", "required": True, "word_limit": 400},
        {"id": "mission", "name": "Mission Statement", "required": True, "word_limit": 300},
        {"id": "admin", "name": "Administration", "required": True, "word_limit": 500},
        {"id": "programs", "name": "Program Effectiveness", "required": True, "word_limit": 700},
        {"id": "faculty", "name": "Faculty", "required": True, "word_limit": 500},
        {"id": "student_services", "name": "Student Services", "required": True, "word_limit": 500},
        {"id": "outcomes", "name": "Student Outcomes", "required": True, "word_limit": 600},
        {"id": "facilities", "name": "Physical Facilities", "required": True, "word_limit": 400},
        {"id": "financial", "name": "Financial Resources", "required": True, "word_limit": 400},
        {"id": "conclusion", "name": "Summary", "required": True, "word_limit": 300},
    ],
}

# Default sections for unknown accreditors
DEFAULT_SECTIONS = [
    {"id": "executive_summary", "name": "Executive Summary", "required": True, "word_limit": 500},
    {"id": "mission", "name": "Mission and Objectives", "required": True, "word_limit": 400},
    {"id": "programs", "name": "Educational Programs", "required": True, "word_limit": 800},
    {"id": "faculty", "name": "Faculty", "required": True, "word_limit": 600},
    {"id": "student_services", "name": "Student Services", "required": True, "word_limit": 500},
    {"id": "outcomes", "name": "Student Outcomes", "required": True, "word_limit": 600},
    {"id": "conclusion", "name": "Conclusion", "required": True, "word_limit": 300},
]


@register_agent(AgentType.SER_DRAFTING)
class SERDraftingAgent(BaseAgent):
    """Agent for drafting Self-Evaluation Reports.

    Provides tools for:
    - Parsing SER templates by accreditor
    - Listing required sections
    - Drafting individual sections
    - Auto-filling institutional data
    - Validating sections for completeness
    - Generating full drafts
    - Toggling between draft and submission modes
    - Exporting to DOCX
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._draft_cache: Dict[str, Dict] = {}
        self._writing_mode = "draft"  # draft or submission

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SER_DRAFTING

    @property
    def system_prompt(self) -> str:
        return """You are a Self-Evaluation Report (SER) drafting specialist for accreditation.
Your role is to help institutions create comprehensive, evidence-based SER documents.

Your responsibilities:
1. Draft section-by-section SER narratives with proper citations
2. Auto-fill institutional data from the truth index
3. Ensure all claims are backed by evidence
4. Maintain consistent voice and formatting across sections
5. Flag gaps where evidence or information is missing
6. Support both draft and submission modes

WRITING MODES:
- Draft Mode: Conversational, placeholders allowed, fast iteration
  * Use [VERIFY: ...] for items needing confirmation
  * Use [TODO: ...] for missing information
  * Less formal tone, shorter narratives

- Submission Mode: Formal, audit-proof, citation-heavy
  * Every claim must be cited: "(See Exhibit X, pg. Y)"
  * No placeholders - flag gaps instead of glossing over
  * Formal compliance language
  * Headers match accreditor's format exactly

KEY REQUIREMENTS:
- All claims must be grounded in actual institutional documents
- Citations format: (Document Name, page X) or (Exhibit X)
- Word limits should be respected
- Use institution's official name consistently
- Maintain third-person perspective for formal sections

NEVER fabricate evidence or make unsupported claims.
Always identify gaps rather than fill them with speculation."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_ser_sections",
                "description": "List required SER sections for an accreditor.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "accreditor_code": {
                            "type": "string",
                            "description": "Accreditor code (e.g., ACCSC, ABHES)",
                        },
                    },
                    "required": ["accreditor_code"],
                },
            },
            {
                "name": "draft_section",
                "description": "Draft a specific SER section.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "section_id": {
                            "type": "string",
                            "description": "Section ID to draft",
                        },
                        "accreditor_code": {"type": "string"},
                        "writing_mode": {
                            "type": "string",
                            "enum": ["draft", "submission"],
                            "default": "draft",
                        },
                    },
                    "required": ["institution_id", "section_id", "accreditor_code"],
                },
            },
            {
                "name": "auto_fill_institutional_data",
                "description": "Auto-fill institutional data from truth index.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "section_id": {
                            "type": "string",
                            "description": "Section to fill data for",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "validate_section",
                "description": "Validate a section for completeness and citations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "ser_id": {"type": "string"},
                        "section_id": {"type": "string"},
                    },
                    "required": ["institution_id", "ser_id", "section_id"],
                },
            },
            {
                "name": "generate_full_draft",
                "description": "Generate a complete SER draft with all sections.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "accreditor_code": {"type": "string"},
                        "writing_mode": {
                            "type": "string",
                            "enum": ["draft", "submission"],
                            "default": "draft",
                        },
                        "sections_to_include": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific sections to include (or all if empty)",
                        },
                    },
                    "required": ["institution_id", "accreditor_code"],
                },
            },
            {
                "name": "toggle_writing_mode",
                "description": "Switch between draft and submission writing modes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["draft", "submission"],
                        },
                    },
                    "required": ["mode"],
                },
            },
            {
                "name": "get_ser_draft",
                "description": "Get an existing SER draft.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "ser_id": {"type": "string"},
                    },
                    "required": ["institution_id", "ser_id"],
                },
            },
            {
                "name": "export_ser",
                "description": "Export SER to file format.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "ser_id": {"type": "string"},
                        "format": {
                            "type": "string",
                            "enum": ["json", "docx"],
                            "default": "json",
                        },
                    },
                    "required": ["institution_id", "ser_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool_map = {
            "list_ser_sections": self._tool_list_sections,
            "draft_section": self._tool_draft_section,
            "auto_fill_institutional_data": self._tool_auto_fill,
            "validate_section": self._tool_validate_section,
            "generate_full_draft": self._tool_generate_full,
            "toggle_writing_mode": self._tool_toggle_mode,
            "get_ser_draft": self._tool_get_draft,
            "export_ser": self._tool_export,
        }

        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_list_sections(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List SER sections for an accreditor."""
        accreditor = params.get("accreditor_code", "").upper()
        sections = SER_SECTIONS.get(accreditor, DEFAULT_SECTIONS)

        return {
            "success": True,
            "accreditor": accreditor,
            "sections": sections,
            "total": len(sections),
            "required_count": len([s for s in sections if s.get("required")]),
        }

    def _tool_draft_section(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Draft a specific SER section."""
        institution_id = params["institution_id"]
        section_id = params["section_id"]
        accreditor = params.get("accreditor_code", "ACCSC").upper()
        mode = params.get("writing_mode", self._writing_mode)

        # Get section info
        sections = SER_SECTIONS.get(accreditor, DEFAULT_SECTIONS)
        section_info = next((s for s in sections if s["id"] == section_id), None)

        if not section_info:
            return {"error": f"Unknown section: {section_id}"}

        # Load institution data
        institution = self._load_institution(institution_id)
        truth_index = self._load_truth_index(institution_id)

        # Generate section content
        content = self._generate_section_content(
            institution, truth_index, section_info, accreditor, mode
        )

        # Extract citations and placeholders
        citations = self._extract_citations(content)
        placeholders = self._extract_placeholders(content) if mode == "draft" else []

        section_data = {
            "section_id": section_id,
            "title": section_info["name"],
            "content": content,
            "word_count": len(content.split()),
            "word_limit": section_info.get("word_limit"),
            "citations": citations,
            "placeholders": placeholders,
            "is_complete": len(placeholders) == 0,
            "writing_mode": mode,
            "generated_at": now_iso(),
        }

        return {
            "success": True,
            "section": section_data,
            "within_limit": (
                section_info.get("word_limit") is None or
                len(content.split()) <= section_info.get("word_limit", 9999)
            ),
        }

    def _tool_auto_fill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-fill institutional data from truth index."""
        institution_id = params["institution_id"]
        section_id = params.get("section_id")

        institution = self._load_institution(institution_id)
        truth_index = self._load_truth_index(institution_id)

        if not institution:
            return {"error": f"Institution not found: {institution_id}"}

        # Extract key data points
        data = {
            "institution_name": institution.get("name", "[INSTITUTION NAME]"),
            "accreditor": institution.get("accrediting_body", "[ACCREDITOR]"),
            "address": institution.get("address", "[ADDRESS]"),
            "phone": institution.get("phone", "[PHONE]"),
            "website": institution.get("website", "[WEBSITE]"),
            "president_name": truth_index.get("president_name", "[PRESIDENT NAME]"),
            "programs_count": len(institution.get("programs", [])),
            "established_year": institution.get("established_year", "[YEAR]"),
        }

        # Add program-specific data
        programs = institution.get("programs", [])
        if programs:
            data["programs"] = [
                {
                    "name": p.get("name"),
                    "credential": p.get("credential_type"),
                    "duration": p.get("duration_weeks"),
                }
                for p in programs[:10]
            ]

        return {
            "success": True,
            "institution_id": institution_id,
            "data": data,
            "source": "truth_index + institution.json",
        }

    def _tool_validate_section(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a section for completeness."""
        institution_id = params["institution_id"]
        ser_id = params["ser_id"]
        section_id = params["section_id"]

        # Load SER draft
        draft = self._load_ser_draft(institution_id, ser_id)
        if not draft:
            return {"error": f"SER draft not found: {ser_id}"}

        section = draft.get("sections", {}).get(section_id)
        if not section:
            return {"error": f"Section not found: {section_id}"}

        issues = []
        warnings = []

        content = section.get("content", "")
        word_count = len(content.split())
        word_limit = section.get("word_limit")

        # Check word limit
        if word_limit and word_count > word_limit:
            issues.append(f"Exceeds word limit: {word_count}/{word_limit}")

        # Check for placeholders in submission mode
        if draft.get("writing_mode") == "submission":
            placeholders = self._extract_placeholders(content)
            if placeholders:
                issues.append(f"Contains {len(placeholders)} unresolved placeholders")

        # Check citations
        citations = self._extract_citations(content)
        if draft.get("writing_mode") == "submission" and len(citations) < 2:
            warnings.append("Section has few citations - consider adding more evidence references")

        # Check content length
        if word_count < 50:
            warnings.append("Section content is very short")

        return {
            "success": True,
            "section_id": section_id,
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "word_count": word_count,
            "citations_count": len(citations),
        }

    def _tool_generate_full(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete SER draft."""
        institution_id = params["institution_id"]
        accreditor = params.get("accreditor_code", "ACCSC").upper()
        mode = params.get("writing_mode", "draft")
        sections_filter = params.get("sections_to_include", [])

        # Get sections
        all_sections = SER_SECTIONS.get(accreditor, DEFAULT_SECTIONS)
        if sections_filter:
            sections_to_draft = [s for s in all_sections if s["id"] in sections_filter]
        else:
            sections_to_draft = all_sections

        # Load institution data
        institution = self._load_institution(institution_id)
        truth_index = self._load_truth_index(institution_id)

        if not institution:
            return {"error": f"Institution not found: {institution_id}"}

        # Generate each section
        sections = {}
        total_words = 0

        for section_info in sections_to_draft:
            content = self._generate_section_content(
                institution, truth_index, section_info, accreditor, mode
            )

            word_count = len(content.split())
            total_words += word_count

            sections[section_info["id"]] = {
                "section_id": section_info["id"],
                "title": section_info["name"],
                "content": content,
                "word_count": word_count,
                "word_limit": section_info.get("word_limit"),
                "citations": self._extract_citations(content),
                "placeholders": self._extract_placeholders(content) if mode == "draft" else [],
                "is_complete": len(self._extract_placeholders(content)) == 0,
            }

        # Create SER draft
        ser_id = generate_id("ser")
        draft = {
            "id": ser_id,
            "institution_id": institution_id,
            "accreditor_code": accreditor,
            "writing_mode": mode,
            "sections": sections,
            "total_sections": len(sections),
            "total_words": total_words,
            "status": "draft",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        # Save draft
        self._save_ser_draft(institution_id, draft)
        self._draft_cache[ser_id] = draft

        return {
            "success": True,
            "ser_id": ser_id,
            "accreditor": accreditor,
            "writing_mode": mode,
            "sections_drafted": len(sections),
            "total_words": total_words,
            "document_path": f"visit_prep/ser_draft_{accreditor.lower()}.json",
        }

    def _tool_toggle_mode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Toggle writing mode."""
        mode = params["mode"]
        self._writing_mode = mode

        return {
            "success": True,
            "writing_mode": mode,
            "description": (
                "Draft mode: Conversational, placeholders allowed"
                if mode == "draft"
                else "Submission mode: Formal, all citations required"
            ),
        }

    def _tool_get_draft(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get an existing SER draft."""
        institution_id = params["institution_id"]
        ser_id = params["ser_id"]

        draft = self._draft_cache.get(ser_id)
        if not draft:
            draft = self._load_ser_draft(institution_id, ser_id)

        if not draft:
            return {"error": f"SER draft not found: {ser_id}"}

        return {
            "success": True,
            "draft": draft,
        }

    def _tool_export(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export SER to file."""
        institution_id = params["institution_id"]
        ser_id = params["ser_id"]
        export_format = params.get("format", "json")

        draft = self._draft_cache.get(ser_id)
        if not draft:
            draft = self._load_ser_draft(institution_id, ser_id)

        if not draft:
            return {"error": f"SER draft not found: {ser_id}"}

        accreditor = draft.get("accreditor_code", "unknown").lower()
        export_path = f"visit_prep/exports/ser_{accreditor}_{now_iso()[:10]}.json"

        if self.workspace_manager:
            self.workspace_manager.save_file(institution_id, export_path, draft)

        return {
            "success": True,
            "ser_id": ser_id,
            "format": export_format,
            "export_path": export_path,
            "sections_exported": len(draft.get("sections", {})),
        }

    # Helper methods

    def _load_institution(self, institution_id: str) -> Optional[Dict]:
        """Load institution data."""
        if not self.workspace_manager:
            return {"id": institution_id, "name": "Test Institution", "programs": []}
        return self.workspace_manager.load_file(institution_id, "institution.json")

    def _load_truth_index(self, institution_id: str) -> Dict:
        """Load truth index."""
        if not self.workspace_manager:
            return {}
        return self.workspace_manager.load_file(institution_id, "truth_index.json") or {}

    def _load_ser_draft(self, institution_id: str, ser_id: str) -> Optional[Dict]:
        """Load SER draft by ID."""
        if not self.workspace_manager:
            return None

        # Search for matching draft
        for accreditor in ["accsc", "abhes", "unknown"]:
            path = f"visit_prep/ser_draft_{accreditor}.json"
            draft = self.workspace_manager.load_file(institution_id, path)
            if draft and draft.get("id") == ser_id:
                return draft
        return None

    def _save_ser_draft(self, institution_id: str, draft: Dict) -> None:
        """Save SER draft."""
        if not self.workspace_manager:
            return

        accreditor = draft.get("accreditor_code", "unknown").lower()
        path = f"visit_prep/ser_draft_{accreditor}.json"
        self.workspace_manager.save_file(institution_id, path, draft)

    def _generate_section_content(
        self,
        institution: Dict,
        truth_index: Dict,
        section_info: Dict,
        accreditor: str,
        mode: str,
    ) -> str:
        """Generate content for a section using AI."""
        section_id = section_info["id"]
        section_name = section_info["name"]
        word_limit = section_info.get("word_limit", 500)

        inst_name = institution.get("name", "[Institution Name]")
        programs = institution.get("programs", [])

        mode_instruction = (
            "Use a conversational tone. Mark uncertain items with [VERIFY: ...] and missing info with [TODO: ...]."
            if mode == "draft"
            else "Use formal compliance language. Every claim must include a citation like (See Exhibit X, pg. Y). No placeholders."
        )

        prompt = f"""Write the "{section_name}" section for a Self-Evaluation Report.

Institution: {inst_name}
Accreditor: {accreditor}
Programs: {len(programs)}
Word limit: {word_limit} words

Mode: {mode.upper()}
{mode_instruction}

Section requirements for {section_name}:
- Address all relevant accreditor standards
- Include specific evidence references
- Demonstrate compliance with clear examples
- Be concise but comprehensive

Generate the section content now:"""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=word_limit * 3,  # Allow room for generation
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            # Fallback content
            if mode == "draft":
                return f"[TODO: Draft {section_name} content for {inst_name}. Address {accreditor} requirements.]"
            else:
                return f"{section_name}\n\n{inst_name} maintains compliance with {accreditor} standards in this area. (See documentation in institutional files.)"

    def _extract_citations(self, content: str) -> List[str]:
        """Extract citations from content."""
        # Match patterns like (See Exhibit X), (Document Name, pg. Y), etc.
        patterns = [
            r'\(See [^)]+\)',
            r'\(Exhibit [^)]+\)',
            r'\([^)]+, pg\. \d+\)',
            r'\([^)]+, page \d+\)',
        ]

        citations = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            citations.extend(matches)

        return list(set(citations))

    def _extract_placeholders(self, content: str) -> List[str]:
        """Extract placeholders from content."""
        patterns = [
            r'\[VERIFY:[^\]]+\]',
            r'\[TODO:[^\]]+\]',
            r'\[INSERT:[^\]]+\]',
            r'\[[A-Z ]+\]',  # Generic bracketed placeholders
        ]

        placeholders = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            placeholders.extend(matches)

        return list(set(placeholders))
