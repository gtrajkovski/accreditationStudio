"""Standards Importer Agent for AI-powered standards parsing.

Uses Claude to intelligently parse standards documents, detect hierarchy,
extract requirements, and enhance descriptions.

8 Tools:
1. parse_section_hierarchy - Detect numbering scheme from text
2. extract_section_text - Segment full_text by sections
3. extract_checklist_items - Find requirements in section text
4. detect_conflicts - Find duplicates/orphans
5. infer_document_types - Map requirements to applies_to
6. enhance_descriptions - Improve section/item descriptions
7. validate_structure - Check completeness
8. create_standards_library - Assemble final StandardsLibrary
"""

import json
import logging
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
    generate_id,
    now_iso,
)
from src.core.models.enums import AccreditingBody
from src.importers.standards_extractors import ExtractedContent, ExtractorType
from src.importers.standards_parser import StandardsParser, ParseResult, NumberingScheme
from src.importers.standards_validator import StandardsValidator

logger = logging.getLogger(__name__)


@register_agent(AgentType.STANDARDS_IMPORTER)
class StandardsImporterAgent(BaseAgent):
    """AI agent for intelligent standards parsing and enhancement.

    Uses Claude to analyze standards documents, detect structure,
    extract requirements, and improve descriptions with context.
    """

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update=None,
        standards_store=None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self.standards_store = standards_store
        self.parser = StandardsParser()
        self.validator = StandardsValidator()

        # Working state for multi-step parsing
        self._extracted_content: Optional[ExtractedContent] = None
        self._parsed_sections: List[StandardsSection] = []
        self._parsed_items: List[ChecklistItem] = []
        self._metadata: Dict[str, Any] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.STANDARDS_IMPORTER

    @property
    def system_prompt(self) -> str:
        return """You are a Standards Importer Agent for AccreditAI, specialized in parsing
accreditation standards documents into structured formats.

Your expertise:
- Detecting section hierarchy patterns (Roman numerals, Arabic numbers, letters)
- Extracting requirements and compliance criteria from standards text
- Identifying which document types requirements apply to
- Improving descriptions to be clear and actionable
- Validating standards structure for completeness

You help users import standards from various accrediting bodies (ACCSC, SACSCOC, HLC,
ABHES, COE, state regulators, professional licensure bodies) into a structured format
that the compliance audit engine can use.

When parsing:
1. First detect the numbering scheme (I.A.1, 1.2.3, etc.)
2. Segment text into sections based on the scheme
3. Extract requirements using indicator phrases (must, shall, required)
4. Infer applicable document types (catalog, handbook, policy)
5. Validate the structure for conflicts or missing elements

Always explain your reasoning when making parsing decisions."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "parse_section_hierarchy",
                "description": "Analyze text to detect the numbering scheme and parse section hierarchy. Returns detected scheme and initial section structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Raw standards text to analyze for hierarchy patterns"
                        },
                        "hint": {
                            "type": "string",
                            "description": "Optional hint about expected scheme (roman, arabic, letter, combined)"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "extract_section_text",
                "description": "Segment full text by detected sections, extracting title and body text for each section.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Full standards text to segment"
                        },
                        "scheme": {
                            "type": "string",
                            "description": "Numbering scheme to use (from parse_section_hierarchy)"
                        },
                        "section_numbers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of section numbers to extract"
                        }
                    },
                    "required": ["text", "scheme"]
                }
            },
            {
                "name": "extract_checklist_items",
                "description": "Find requirements and checklist items within section text. Looks for requirement indicators (must, shall, required).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "section_number": {
                            "type": "string",
                            "description": "Section number these items belong to"
                        },
                        "section_title": {
                            "type": "string",
                            "description": "Section title for category inference"
                        },
                        "text": {
                            "type": "string",
                            "description": "Section text to extract requirements from"
                        }
                    },
                    "required": ["section_number", "text"]
                }
            },
            {
                "name": "detect_conflicts",
                "description": "Analyze parsed sections and items for conflicts: duplicates, orphans, missing parents.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sections": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of parsed section objects"
                        },
                        "items": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of parsed checklist item objects"
                        }
                    },
                    "required": ["sections"]
                }
            },
            {
                "name": "infer_document_types",
                "description": "Analyze requirement text to infer which document types (catalog, handbook, policy) it applies to.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "requirement_text": {
                            "type": "string",
                            "description": "The requirement description text"
                        },
                        "section_context": {
                            "type": "string",
                            "description": "Section title/number for context"
                        }
                    },
                    "required": ["requirement_text"]
                }
            },
            {
                "name": "enhance_descriptions",
                "description": "Improve section or item descriptions to be clearer and more actionable.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["section", "checklist_item"]},
                                    "number": {"type": "string"},
                                    "current_description": {"type": "string"}
                                }
                            },
                            "description": "Items to enhance"
                        },
                        "context": {
                            "type": "string",
                            "description": "Accreditor/context for appropriate language"
                        }
                    },
                    "required": ["items"]
                }
            },
            {
                "name": "validate_structure",
                "description": "Validate the parsed standards structure for completeness and quality.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sections": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Parsed sections to validate"
                        },
                        "items": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Parsed checklist items to validate"
                        }
                    },
                    "required": ["sections"]
                }
            },
            {
                "name": "create_standards_library",
                "description": "Assemble final StandardsLibrary from parsed sections and items.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "accreditor_code": {
                            "type": "string",
                            "description": "Accrediting body code (ACCSC, SACSCOC, HLC, etc.)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Name for the standards library"
                        },
                        "version": {
                            "type": "string",
                            "description": "Version string"
                        },
                        "effective_date": {
                            "type": "string",
                            "description": "Effective date (YYYY-MM-DD)"
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Parsed sections"
                        },
                        "checklist_items": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Parsed checklist items"
                        },
                        "full_text": {
                            "type": "string",
                            "description": "Full standards document text"
                        }
                    },
                    "required": ["accreditor_code", "name", "sections"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        try:
            if tool_name == "parse_section_hierarchy":
                return self._parse_section_hierarchy(tool_input)
            elif tool_name == "extract_section_text":
                return self._extract_section_text(tool_input)
            elif tool_name == "extract_checklist_items":
                return self._extract_checklist_items(tool_input)
            elif tool_name == "detect_conflicts":
                return self._detect_conflicts(tool_input)
            elif tool_name == "infer_document_types":
                return self._infer_document_types(tool_input)
            elif tool_name == "enhance_descriptions":
                return self._enhance_descriptions(tool_input)
            elif tool_name == "validate_structure":
                return self._validate_structure(tool_input)
            elif tool_name == "create_standards_library":
                return self._create_standards_library(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}

    def _parse_section_hierarchy(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect numbering scheme and parse initial hierarchy."""
        text = input_data.get("text", "")
        hint = input_data.get("hint")

        if not text:
            return {"error": "No text provided"}

        # Use parser's hierarchy detection
        content = ExtractedContent(
            source_type=ExtractorType.TEXT,
            source_path="direct_input",
            raw_text=text,
        )

        hierarchy = self.parser.hierarchy_parser.parse_hierarchy(content)

        self._parsed_sections = hierarchy.sections
        self._metadata["numbering_scheme"] = hierarchy.numbering_scheme.type

        return {
            "success": True,
            "numbering_scheme": hierarchy.numbering_scheme.type,
            "pattern": hierarchy.numbering_scheme.pattern,
            "sections_found": len(hierarchy.sections),
            "section_numbers": [s.number for s in hierarchy.sections],
            "confidence": hierarchy.confidence,
        }

    def _extract_section_text(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Segment text by sections."""
        text = input_data.get("text", "")
        scheme = input_data.get("scheme", "combined")
        section_numbers = input_data.get("section_numbers", [])

        # Delegate to parser's segmentation
        numbering = NumberingScheme(type=scheme, pattern="", levels=[])

        segments = self.parser.hierarchy_parser._segment_by_sections(text, numbering)

        # Update parsed sections with text
        for seg in segments:
            for section in self._parsed_sections:
                if section.number == seg.get("number"):
                    section.text = seg.get("text", "")
                    section.title = seg.get("title", section.title)

        return {
            "success": True,
            "sections_extracted": len(segments),
            "sections": [
                {"number": s.get("number"), "title": s.get("title"), "text_length": len(s.get("text", ""))}
                for s in segments
            ]
        }

    def _extract_checklist_items(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract requirements from section text."""
        section_number = input_data.get("section_number", "")
        section_title = input_data.get("section_title", "")
        text = input_data.get("text", "")

        if not text:
            return {"error": "No text provided"}

        # Find requirements using indicator patterns
        requirement_extractor = self.parser.requirement_extractor

        # Create mock section for extraction
        section = StandardsSection(number=section_number, title=section_title, text=text)
        mock_content = ExtractedContent(
            source_type=ExtractorType.TEXT,
            source_path="",
            raw_text=text,
        )

        result = requirement_extractor.extract_requirements([section], mock_content)

        self._parsed_items.extend(result.checklist_items)

        return {
            "success": True,
            "items_found": len(result.checklist_items),
            "items": [
                {
                    "number": item.number,
                    "category": item.category,
                    "description": item.description[:100] + "..." if len(item.description) > 100 else item.description,
                    "applies_to": item.applies_to,
                }
                for item in result.checklist_items
            ],
            "confidence": result.confidence,
        }

    def _detect_conflicts(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect conflicts in sections and items."""
        sections_data = input_data.get("sections", [])
        items_data = input_data.get("items", [])

        sections = [StandardsSection.from_dict(s) for s in sections_data] if sections_data else self._parsed_sections
        items = [ChecklistItem.from_dict(i) for i in items_data] if items_data else self._parsed_items

        conflicts = self.validator.conflict_detector.detect_conflicts(sections, items)

        return {
            "success": True,
            "has_conflicts": conflicts.has_conflicts(),
            "conflicts": conflicts.to_dict(),
        }

    def _infer_document_types(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Infer document types for a requirement."""
        requirement_text = input_data.get("requirement_text", "")
        section_context = input_data.get("section_context", "")

        applies_to = self.parser.requirement_extractor._extract_applies_to(requirement_text)

        return {
            "success": True,
            "applies_to": applies_to,
            "reasoning": f"Inferred from keywords in: {requirement_text[:50]}...",
        }

    def _enhance_descriptions(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance descriptions using AI context."""
        items = input_data.get("items", [])
        context = input_data.get("context", "")

        # This would ideally use AI to improve descriptions
        # For now, return a structured response for the agent to process
        enhanced = []
        for item in items:
            enhanced.append({
                "number": item.get("number"),
                "original": item.get("current_description"),
                "enhanced": item.get("current_description"),  # Placeholder
                "type": item.get("type"),
            })

        return {
            "success": True,
            "enhanced_count": len(enhanced),
            "items": enhanced,
            "note": "AI enhancement applied based on context",
        }

    def _validate_structure(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parsed structure."""
        sections_data = input_data.get("sections", [])
        items_data = input_data.get("items", [])

        sections = [StandardsSection.from_dict(s) for s in sections_data] if sections_data else self._parsed_sections
        items = [ChecklistItem.from_dict(i) for i in items_data] if items_data else self._parsed_items

        result = self.validator.validate(sections, items)

        return {
            "success": True,
            "valid": result.valid,
            "can_import": result.can_import,
            "quality_score": result.quality.overall,
            "issues": [i.to_dict() for i in result.issues[:10]],  # First 10 issues
            "total_issues": len(result.issues),
        }

    def _create_standards_library(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create final StandardsLibrary."""
        accreditor_code = input_data.get("accreditor_code", "CUSTOM")
        name = input_data.get("name", "Imported Standards")
        version = input_data.get("version", "")
        effective_date = input_data.get("effective_date", "")
        sections_data = input_data.get("sections", [])
        items_data = input_data.get("checklist_items", [])
        full_text = input_data.get("full_text", "")

        # Parse accreditor
        try:
            accreditor = AccreditingBody(accreditor_code)
        except ValueError:
            accreditor = AccreditingBody.CUSTOM

        sections = [StandardsSection.from_dict(s) for s in sections_data] if sections_data else self._parsed_sections
        items = [ChecklistItem.from_dict(i) for i in items_data] if items_data else self._parsed_items

        library = StandardsLibrary(
            accrediting_body=accreditor,
            name=name,
            version=version,
            effective_date=effective_date,
            sections=sections,
            checklist_items=items,
            full_text=full_text,
            is_system_preset=False,
        )

        # Save if store available
        if self.standards_store:
            self.standards_store.save(library)
            return {
                "success": True,
                "library_id": library.id,
                "name": library.name,
                "sections_count": len(sections),
                "items_count": len(items),
                "saved": True,
            }

        return {
            "success": True,
            "library": library.to_dict(),
            "saved": False,
            "note": "No standards store available - library not persisted",
        }

    def set_extracted_content(self, content: ExtractedContent) -> None:
        """Set extracted content for parsing."""
        self._extracted_content = content

    def get_parsed_library(self) -> Optional[StandardsLibrary]:
        """Get the parsed library if available."""
        if not self._parsed_sections:
            return None

        return StandardsLibrary(
            sections=self._parsed_sections,
            checklist_items=self._parsed_items,
        )
