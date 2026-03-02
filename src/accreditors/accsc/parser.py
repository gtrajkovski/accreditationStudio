"""ACCSC Standards Parser.

Parses ACCSC standards documents into normalized StandardsTree format.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from src.accreditors.accsc.sources import SECTION_STRUCTURE


@dataclass
class StandardsNode:
    """A node in the standards tree."""
    id: str
    code: str  # e.g., "VII.A.4"
    title: str
    text: str = ""
    parent_id: str = ""
    children: List["StandardsNode"] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    checklist_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "text": self.text,
            "parent_id": self.parent_id,
            "children": [c.to_dict() for c in self.children],
            "requirements": self.requirements,
            "checklist_refs": self.checklist_refs,
        }


@dataclass
class ChecklistItem:
    """A checklist item."""
    id: str
    number: str  # e.g., "1.a"
    text: str
    category: str = ""
    standard_refs: List[str] = field(default_factory=list)
    applies_to: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "text": self.text,
            "category": self.category,
            "standard_refs": self.standard_refs,
            "applies_to": self.applies_to,
        }


@dataclass
class ParsedStandards:
    """Parsed standards result."""
    accreditor: str = "ACCSC"
    version: str = ""
    effective_date: str = ""
    sections: List[StandardsNode] = field(default_factory=list)
    checklists: Dict[str, List[ChecklistItem]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accreditor": self.accreditor,
            "version": self.version,
            "effective_date": self.effective_date,
            "sections": [s.to_dict() for s in self.sections],
            "checklists": {k: [i.to_dict() for i in v] for k, v in self.checklists.items()},
            "metadata": self.metadata,
        }


class ACCSCParser:
    """Parser for ACCSC standards documents."""

    # Roman numeral pattern for section detection
    ROMAN_PATTERN = re.compile(r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,2})\.\s*(.+)$')
    # Subsection pattern (e.g., A., B., 1., 2.)
    SUBSECTION_PATTERN = re.compile(r'^([A-Z]|\d+)\.\s*(.+)$')
    # Checklist item pattern (e.g., 1., 1.a, 1.a.i)
    CHECKLIST_PATTERN = re.compile(r'^(\d+\.?[a-z]?\.?[ivx]?)\s+(.+)$', re.IGNORECASE)

    def __init__(self):
        self.section_structure = SECTION_STRUCTURE

    def parse_standards_pdf(self, pdf_path: Path, extracted_text: str) -> ParsedStandards:
        """Parse ACCSC standards from PDF extracted text.

        Args:
            pdf_path: Path to source PDF
            extracted_text: Pre-extracted text from PDF

        Returns:
            ParsedStandards object
        """
        result = ParsedStandards(
            accreditor="ACCSC",
            metadata={"source_file": str(pdf_path)}
        )

        # Build top-level sections from known structure
        for roman, title in self.section_structure.items():
            section = StandardsNode(
                id=f"accsc_{roman.lower()}",
                code=roman,
                title=title,
            )
            result.sections.append(section)

        # Parse text to populate sections
        self._parse_section_content(extracted_text, result)

        return result

    def parse_checklist_pdf(
        self,
        pdf_path: Path,
        extracted_text: str,
        doc_type: str
    ) -> List[ChecklistItem]:
        """Parse ACCSC checklist from PDF extracted text.

        Args:
            pdf_path: Path to source PDF
            extracted_text: Pre-extracted text from PDF
            doc_type: Document type (enrollment_agreement, catalog, etc.)

        Returns:
            List of ChecklistItem objects
        """
        items = []
        lines = extracted_text.split('\n')
        current_category = ""
        item_counter = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for category headers (usually ALL CAPS or bold in PDF)
            if line.isupper() and len(line) > 10:
                current_category = line.title()
                continue

            # Check for checklist items
            match = self.CHECKLIST_PATTERN.match(line)
            if match:
                item_counter += 1
                number = match.group(1).strip('.')
                text = match.group(2).strip()

                # Extract standard references from text (e.g., "Section VII.A.4")
                standard_refs = self._extract_standard_refs(text)

                item = ChecklistItem(
                    id=f"accsc_{doc_type}_{item_counter}",
                    number=number,
                    text=text,
                    category=current_category,
                    standard_refs=standard_refs,
                    applies_to=[doc_type],
                )
                items.append(item)

        return items

    def _parse_section_content(self, text: str, result: ParsedStandards) -> None:
        """Parse section content from extracted text."""
        lines = text.split('\n')
        current_section = None
        current_text = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for Roman numeral section header
            roman_match = self.ROMAN_PATTERN.match(line)
            if roman_match:
                # Save previous section's text
                if current_section and current_text:
                    current_section.text = '\n'.join(current_text)
                    current_text = []

                # Find matching section
                roman = roman_match.group(1)
                for section in result.sections:
                    if section.code == roman:
                        current_section = section
                        break
                continue

            # Accumulate text for current section
            if current_section:
                current_text.append(line)

        # Save last section
        if current_section and current_text:
            current_section.text = '\n'.join(current_text)

    def _extract_standard_refs(self, text: str) -> List[str]:
        """Extract standard section references from text."""
        refs = []
        # Pattern for "Section VII.A.4" or "VII.A.4"
        pattern = re.compile(r'(?:Section\s+)?(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,2})\.([A-Z])\.?(\d+)?', re.IGNORECASE)
        for match in pattern.finditer(text):
            ref = f"{match.group(1)}.{match.group(2)}"
            if match.group(3):
                ref += f".{match.group(3)}"
            refs.append(ref)
        return refs


def parse_standards(pdf_path: Path, extracted_text: str) -> Dict[str, Any]:
    """Parse ACCSC standards PDF.

    Args:
        pdf_path: Path to PDF file
        extracted_text: Pre-extracted text

    Returns:
        Parsed standards as dict
    """
    parser = ACCSCParser()
    result = parser.parse_standards_pdf(pdf_path, extracted_text)
    return result.to_dict()


def parse_checklist(pdf_path: Path, extracted_text: str, doc_type: str) -> List[Dict[str, Any]]:
    """Parse ACCSC checklist PDF.

    Args:
        pdf_path: Path to PDF file
        extracted_text: Pre-extracted text
        doc_type: Document type

    Returns:
        List of checklist items as dicts
    """
    parser = ACCSCParser()
    items = parser.parse_checklist_pdf(pdf_path, extracted_text, doc_type)
    return [item.to_dict() for item in items]
