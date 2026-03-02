"""COE Standards Parser.

Parses COE standards documents into normalized StandardsTree format.
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from src.accreditors.coe.sources import SECTION_STRUCTURE, CRITERIA_STRUCTURE


@dataclass
class StandardsNode:
    """A node in the standards tree."""
    id: str
    code: str  # e.g., "5.A" or "5"
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
    number: str  # e.g., "1", "1.a"
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
    accreditor: str = "COE"
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


class COEParser:
    """Parser for COE standards documents."""

    # Standard number pattern (e.g., "Standard 5" or "5.")
    STANDARD_PATTERN = re.compile(r'^(?:Standard\s+)?(\d{1,2})\.?\s*[-–—]?\s*(.+)?$', re.IGNORECASE)
    # Criteria pattern (e.g., "A.", "B.", "5.A")
    CRITERIA_PATTERN = re.compile(r'^([A-Z])\.?\s+(.+)$')
    # Combined code pattern (e.g., "5.A", "12.C")
    CODE_PATTERN = re.compile(r'^(\d{1,2})\.([A-Z])\.?\s*(.+)?$')
    # Checklist item pattern (e.g., "1.", "1.a")
    CHECKLIST_PATTERN = re.compile(r'^(\d+\.?[a-z]?)\s+(.+)$', re.IGNORECASE)

    def __init__(self):
        self.section_structure = SECTION_STRUCTURE
        self.criteria_structure = CRITERIA_STRUCTURE

    def parse_standards_pdf(self, pdf_path: Path, extracted_text: str) -> ParsedStandards:
        """Parse COE standards from PDF extracted text.

        Args:
            pdf_path: Path to source PDF
            extracted_text: Pre-extracted text from PDF

        Returns:
            ParsedStandards object
        """
        result = ParsedStandards(
            accreditor="COE",
            metadata={"source_file": str(pdf_path)}
        )

        # Build top-level standards from known structure (1-12)
        for num, title in self.section_structure.items():
            standard = StandardsNode(
                id=f"coe_{num}",
                code=num,
                title=title,
            )

            # Add criteria as children if known
            if num in self.criteria_structure:
                for letter, crit_title in self.criteria_structure[num].items():
                    criterion = StandardsNode(
                        id=f"coe_{num}_{letter}",
                        code=f"{num}.{letter}",
                        title=crit_title,
                        parent_id=standard.id,
                    )
                    standard.children.append(criterion)

            result.sections.append(standard)

        # Parse text to populate sections
        self._parse_section_content(extracted_text, result)

        return result

    def parse_checklist_pdf(
        self,
        pdf_path: Path,
        extracted_text: str,
        doc_type: str
    ) -> List[ChecklistItem]:
        """Parse COE checklist from PDF extracted text.

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

            # Check for standard reference headers (e.g., "Standard 5")
            std_match = self.STANDARD_PATTERN.match(line)
            if std_match and not self.CHECKLIST_PATTERN.match(line):
                current_category = f"Standard {std_match.group(1)}"
                continue

            # Check for checklist items
            match = self.CHECKLIST_PATTERN.match(line)
            if match:
                item_counter += 1
                number = match.group(1).strip('.')
                text = match.group(2).strip()

                # Extract standard references from text (e.g., "Standard 5.A")
                standard_refs = self._extract_standard_refs(text)

                item = ChecklistItem(
                    id=f"coe_{doc_type}_{item_counter}",
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
        current_standard = None
        current_criterion = None
        current_text = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for standard number header (e.g., "Standard 5 - Educational Programs")
            std_match = self.STANDARD_PATTERN.match(line)
            if std_match:
                # Save previous content
                self._save_current_text(current_standard, current_criterion, current_text)
                current_text = []
                current_criterion = None

                # Find matching standard
                num = std_match.group(1)
                for section in result.sections:
                    if section.code == num:
                        current_standard = section
                        break
                continue

            # Check for criteria header (e.g., "A. Program Content" or "5.A")
            code_match = self.CODE_PATTERN.match(line)
            crit_match = self.CRITERIA_PATTERN.match(line)

            if code_match and current_standard:
                self._save_current_text(current_standard, current_criterion, current_text)
                current_text = []

                letter = code_match.group(2)
                for child in current_standard.children:
                    if child.code == f"{current_standard.code}.{letter}":
                        current_criterion = child
                        break
                continue

            elif crit_match and current_standard:
                self._save_current_text(current_standard, current_criterion, current_text)
                current_text = []

                letter = crit_match.group(1)
                for child in current_standard.children:
                    if child.code == f"{current_standard.code}.{letter}":
                        current_criterion = child
                        break
                continue

            # Accumulate text for current section
            if current_standard:
                current_text.append(line)

        # Save last section
        self._save_current_text(current_standard, current_criterion, current_text)

    def _save_current_text(
        self,
        standard: Optional[StandardsNode],
        criterion: Optional[StandardsNode],
        text_lines: List[str]
    ) -> None:
        """Save accumulated text to the appropriate node."""
        if not text_lines:
            return

        text = '\n'.join(text_lines)
        if criterion:
            criterion.text = text
        elif standard:
            standard.text = text

    def _extract_standard_refs(self, text: str) -> List[str]:
        """Extract standard section references from text."""
        refs = []
        # Pattern for "Standard 5" or "5.A" or "Standard 5.A"
        pattern = re.compile(r'(?:Standard\s+)?(\d{1,2})(?:\.([A-Z]))?', re.IGNORECASE)
        for match in pattern.finditer(text):
            ref = match.group(1)
            if match.group(2):
                ref += f".{match.group(2).upper()}"
            refs.append(ref)
        return refs


def parse_standards(pdf_path: Path, extracted_text: str) -> Dict[str, Any]:
    """Parse COE standards PDF.

    Args:
        pdf_path: Path to PDF file
        extracted_text: Pre-extracted text

    Returns:
        Parsed standards as dict
    """
    parser = COEParser()
    result = parser.parse_standards_pdf(pdf_path, extracted_text)
    return result.to_dict()


def parse_checklist(pdf_path: Path, extracted_text: str, doc_type: str) -> List[Dict[str, Any]]:
    """Parse COE checklist PDF.

    Args:
        pdf_path: Path to PDF file
        extracted_text: Pre-extracted text
        doc_type: Document type

    Returns:
        List of checklist items as dicts
    """
    parser = COEParser()
    items = parser.parse_checklist_pdf(pdf_path, extracted_text, doc_type)
    return [item.to_dict() for item in items]
