"""Narrative Agent.

Generates professional narratives for accreditation documents including:
- Issue responses to findings
- Self-study sections
- Compliance explanations with citations
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, AgentResult, now_iso, generate_id
from src.config import Config


@dataclass
class NarrativeSection:
    """A generated narrative section."""
    id: str = field(default_factory=lambda: generate_id("narr"))
    section_type: str = ""  # issue_response, self_study, compliance_summary
    standard_reference: str = ""
    title: str = ""
    content: str = ""
    citations: List[Dict[str, str]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    word_count: int = 0
    ai_confidence: float = 0.0
    requires_review: bool = True
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section_type": self.section_type,
            "standard_reference": self.standard_reference,
            "title": self.title,
            "content": self.content,
            "citations": self.citations,
            "evidence_refs": self.evidence_refs,
            "word_count": self.word_count,
            "ai_confidence": self.ai_confidence,
            "requires_review": self.requires_review,
            "created_at": self.created_at,
        }


@register_agent(AgentType.NARRATIVE)
class NarrativeAgent(BaseAgent):
    """Agent for generating accreditation narratives."""

    def __init__(self, session: AgentSession, workspace_manager=None, on_update=None):
        super().__init__(session, workspace_manager, on_update)
        self._sections: List[NarrativeSection] = []
        self._institution_voice: str = ""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NARRATIVE

    @property
    def system_prompt(self) -> str:
        return """You are an expert accreditation narrative writer. Generate professional,
evidence-based narratives for accreditation documents.

STYLE:
- Formal, professional third-person voice ("The institution...")
- Specific citations with standard numbers and page references
- Evidence-backed statements only
- Clear structure: introduction, evidence, conclusion

REQUIREMENTS:
- Every claim must reference supporting evidence
- Include specific document citations
- Match the institution's voice guidelines when provided
- Flag any gaps in evidence"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "write_issue_response",
                "description": "Write a narrative response to a compliance finding.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string"},
                        "item_number": {"type": "string"},
                        "finding_description": {"type": "string"},
                        "evidence_text": {"type": "string"},
                        "remediation_actions": {"type": "string"},
                    },
                    "required": ["item_number", "finding_description"],
                },
            },
            {
                "name": "write_self_study_section",
                "description": "Write a self-study narrative for a standard section.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standard_number": {"type": "string"},
                        "standard_title": {"type": "string"},
                        "standard_text": {"type": "string"},
                        "evidence_summary": {"type": "string"},
                        "compliance_status": {"type": "string"},
                    },
                    "required": ["standard_number", "standard_title"],
                },
            },
            {
                "name": "write_compliance_summary",
                "description": "Write a compliance summary across multiple standards.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standards_covered": {"type": "array", "items": {"type": "string"}},
                        "overall_status": {"type": "string"},
                        "key_findings": {"type": "string"},
                    },
                    "required": ["standards_covered"],
                },
            },
            {
                "name": "set_institution_voice",
                "description": "Set the institutional voice guidelines for narratives.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "voice_guidelines": {"type": "string"},
                        "institution_name": {"type": "string"},
                    },
                    "required": ["institution_name"],
                },
            },
            {
                "name": "get_generated_sections",
                "description": "Get all generated narrative sections.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "save_narratives",
                "description": "Save generated narratives to workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "filename": {"type": "string"},
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "write_issue_response": self._tool_write_issue_response,
            "write_self_study_section": self._tool_write_self_study,
            "write_compliance_summary": self._tool_write_summary,
            "set_institution_voice": self._tool_set_voice,
            "get_generated_sections": self._tool_get_sections,
            "save_narratives": self._tool_save,
        }
        handler = handlers.get(tool_name)
        return handler(tool_input) if handler else {"error": f"Unknown tool: {tool_name}"}

    def _tool_write_issue_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate issue response narrative."""
        item_number = params.get("item_number", "")
        finding_desc = params.get("finding_description", "")
        evidence = params.get("evidence_text", "")
        remediation = params.get("remediation_actions", "")

        prompt = f"""Write a professional accreditation issue response narrative.

Standard/Item: {item_number}
Finding: {finding_desc}
Evidence Available: {evidence or 'None provided'}
Remediation Actions: {remediation or 'None specified'}
{f'Voice Guidelines: {self._institution_voice}' if self._institution_voice else ''}

Write a 150-300 word response that:
1. Acknowledges the finding
2. Presents relevant evidence
3. Describes corrective actions taken or planned
4. Concludes with compliance commitment

Use formal third-person voice. Include [CITATION NEEDED] where evidence references should be added."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            section = NarrativeSection(
                section_type="issue_response",
                standard_reference=item_number,
                title=f"Response to {item_number}",
                content=content,
                word_count=len(content.split()),
                ai_confidence=0.8,
                requires_review=True,
            )
            self._sections.append(section)

            return {"success": True, "section_id": section.id, "word_count": section.word_count, "content": content}
        except Exception as e:
            return {"error": str(e)}

    def _tool_write_self_study(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate self-study section."""
        standard_num = params.get("standard_number", "")
        standard_title = params.get("standard_title", "")
        standard_text = params.get("standard_text", "")
        evidence = params.get("evidence_summary", "")
        status = params.get("compliance_status", "compliant")

        prompt = f"""Write a self-study narrative section for an accreditation document.

Standard: {standard_num} - {standard_title}
Standard Text: {standard_text or 'Not provided'}
Evidence Summary: {evidence or 'None provided'}
Compliance Status: {status}
{f'Voice Guidelines: {self._institution_voice}' if self._institution_voice else ''}

Write a 200-400 word self-study section that:
1. Introduces the standard requirement
2. Describes how the institution meets this requirement
3. References specific evidence and documentation
4. Concludes with compliance affirmation

Use formal third-person voice."""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            section = NarrativeSection(
                section_type="self_study",
                standard_reference=standard_num,
                title=f"{standard_num}: {standard_title}",
                content=content,
                word_count=len(content.split()),
                ai_confidence=0.75,
                requires_review=True,
            )
            self._sections.append(section)

            return {"success": True, "section_id": section.id, "word_count": section.word_count, "content": content}
        except Exception as e:
            return {"error": str(e)}

    def _tool_write_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance summary."""
        standards = params.get("standards_covered", [])
        status = params.get("overall_status", "")
        findings = params.get("key_findings", "")

        prompt = f"""Write an executive compliance summary for accreditation review.

Standards Covered: {', '.join(standards)}
Overall Status: {status or 'Under review'}
Key Findings: {findings or 'None specified'}

Write a 150-250 word executive summary that:
1. States the scope of review
2. Summarizes compliance status
3. Highlights key strengths and areas for improvement
4. Provides a compliance conclusion"""

        try:
            response = self.client.messages.create(
                model=Config.MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

            section = NarrativeSection(
                section_type="compliance_summary",
                title="Compliance Summary",
                content=content,
                word_count=len(content.split()),
                ai_confidence=0.7,
                requires_review=True,
            )
            self._sections.append(section)

            return {"success": True, "section_id": section.id, "content": content}
        except Exception as e:
            return {"error": str(e)}

    def _tool_set_voice(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set institutional voice guidelines."""
        self._institution_voice = params.get("voice_guidelines", "")
        name = params.get("institution_name", "")
        if name and not self._institution_voice:
            self._institution_voice = f"Write in the voice of {name}."
        return {"success": True, "voice_set": bool(self._institution_voice)}

    def _tool_get_sections(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get all generated sections."""
        return {
            "sections": [s.to_dict() for s in self._sections],
            "total": len(self._sections),
            "total_words": sum(s.word_count for s in self._sections),
        }

    def _tool_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save narratives to workspace."""
        institution_id = params.get("institution_id")
        filename = params.get("filename", f"narratives_{now_iso()[:10]}.json")

        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        data = {
            "sections": [s.to_dict() for s in self._sections],
            "total_sections": len(self._sections),
            "created_at": now_iso(),
        }

        path = f"self_study/{filename}"
        self.workspace_manager.save_file(institution_id, path, data)

        return {"success": True, "path": path, "sections_saved": len(self._sections)}

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run narrative workflow."""
        if action == "generate_issue_response":
            result = self._tool_write_issue_response(inputs)
            if "error" in result:
                return AgentResult.error(result["error"])
            return AgentResult.success(data=result, confidence=0.8)

        return AgentResult.error(f"Unknown workflow: {action}")
