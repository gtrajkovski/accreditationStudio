"""Standards parsing and structure detection.

Transforms raw extracted content into StandardsSection and ChecklistItem
objects using hierarchy detection and requirement extraction.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import logging

from src.core.models import StandardsSection, ChecklistItem, generate_id
from src.importers.standards_extractors import ExtractedContent, ExtractorType

logger = logging.getLogger(__name__)


@dataclass
class NumberingScheme:
    """Detected numbering scheme for sections."""
    type: str  # "roman", "arabic", "letter", "combined", "accsc_style"
    pattern: str  # Regex pattern
    levels: List[str]  # e.g., ["I", "A", "1"] for combined
    separator: str = "."  # e.g., "I.A.1" vs "I-A-1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "pattern": self.pattern,
            "levels": self.levels,
            "separator": self.separator,
        }


@dataclass
class ParsedHierarchy:
    """Result of hierarchy parsing."""
    numbering_scheme: NumberingScheme
    sections: List[StandardsSection]
    section_tree: Dict[str, List[str]]  # parent_id -> [child_ids]
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "numbering_scheme": self.numbering_scheme.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "section_tree": self.section_tree,
            "confidence": self.confidence,
        }


@dataclass
class ParsedRequirements:
    """Result of requirement extraction."""
    checklist_items: List[ChecklistItem]
    by_section: Dict[str, List[str]]  # section_number -> [item_numbers]
    categories_detected: List[str]
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checklist_items": [c.to_dict() for c in self.checklist_items],
            "by_section": self.by_section,
            "categories_detected": self.categories_detected,
            "confidence": self.confidence,
        }


@dataclass
class ParseResult:
    """Complete parsing result."""
    hierarchy: ParsedHierarchy
    requirements: ParsedRequirements
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sections": [s.to_dict() for s in self.hierarchy.sections],
            "checklist_items": [c.to_dict() for c in self.requirements.checklist_items],
            "section_count": len(self.hierarchy.sections),
            "item_count": len(self.requirements.checklist_items),
            "categories": self.requirements.categories_detected,
            "numbering_scheme": self.hierarchy.numbering_scheme.type,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "errors": self.errors,
            "confidence": min(self.hierarchy.confidence, self.requirements.confidence),
        }


class HierarchyParser:
    """Detect and parse section hierarchy from text."""

    # Common numbering patterns with capture groups
    PATTERNS = {
        "roman_upper": (r"^(I{1,3}|IV|V|VI{0,3}|IX|X{1,3}|XI{1,3}|XII)\.\s*(.+)$", ["roman"]),
        "roman_lower": (r"^(i{1,3}|iv|v|vi{0,3}|ix|x{1,3}|xi{1,3}|xii)\.\s*(.+)$", ["roman_lower"]),
        "arabic": (r"^(\d+)\.\s+(.+)$", ["arabic"]),
        "letter_upper": (r"^([A-Z])\.\s+(.+)$", ["letter"]),
        "letter_lower": (r"^([a-z])\.\s+(.+)$", ["letter_lower"]),
        "parenthetical_num": (r"^\((\d+)\)\s+(.+)$", ["paren_num"]),
        "parenthetical_letter": (r"^\(([a-z])\)\s+(.+)$", ["paren_letter"]),
        "combined_decimal": (r"^(\d+)\.(\d+)\s+(.+)$", ["arabic", "arabic"]),
        "triple_decimal": (r"^(\d+)\.(\d+)\.(\d+)\s+(.+)$", ["arabic", "arabic", "arabic"]),
        "accsc_style": (r"^(I{1,3}|IV|V|VI{0,3}|IX|X{1,3})\.([A-Z])(\.(\d+))?\s+(.+)$", ["roman", "letter", "arabic"]),
        "sacscoc_style": (r"^(\d+)\.([A-Z])\.?(\d*)\s+(.+)$", ["arabic", "letter", "arabic"]),
    }

    def detect_scheme(self, text: str) -> NumberingScheme:
        """Detect the numbering scheme used in the text.

        Analyzes first 50 potential headings to determine scheme.
        """
        lines = text.split('\n')
        pattern_counts: Dict[str, int] = {}

        for line in lines[:500]:  # Check first 500 lines
            line = line.strip()
            if not line or len(line) > 200:  # Skip empty and very long lines
                continue

            for scheme_name, (pattern, levels) in self.PATTERNS.items():
                if re.match(pattern, line, re.MULTILINE):
                    pattern_counts[scheme_name] = pattern_counts.get(scheme_name, 0) + 1

        if not pattern_counts:
            logger.warning("No numbering scheme detected, defaulting to arabic")
            return NumberingScheme(
                type="arabic",
                pattern=r"^(\d+)\.\s+(.+)$",
                levels=["arabic"],
                separator=".",
            )

        # Find most common pattern
        best_scheme = max(pattern_counts, key=pattern_counts.get)
        pattern, levels = self.PATTERNS[best_scheme]

        logger.info(f"Detected numbering scheme: {best_scheme} (found {pattern_counts[best_scheme]} matches)")

        return NumberingScheme(
            type=best_scheme,
            pattern=pattern,
            levels=levels,
            separator=".",
        )

    def parse_hierarchy(self, content: ExtractedContent) -> ParsedHierarchy:
        """Parse section hierarchy from extracted content.

        Returns:
            ParsedHierarchy with sections and parent-child relationships
        """
        text = content.raw_text
        scheme = self.detect_scheme(text)

        # Segment text into sections
        raw_sections = self._segment_by_sections(text, scheme)

        # Create StandardsSection objects
        sections = []
        number_to_id: Dict[str, str] = {}

        for raw in raw_sections:
            section = StandardsSection(
                number=raw["number"],
                title=raw["title"],
                text=raw["text"],
            )
            sections.append(section)
            number_to_id[raw["number"]] = section.id

        # Build parent links
        parent_links = self._build_parent_links(sections)

        # Apply parent references
        for section in sections:
            parent_number = parent_links.get(section.number, "")
            if parent_number and parent_number in number_to_id:
                section.parent_section = number_to_id[parent_number]

        # Build section tree
        section_tree: Dict[str, List[str]] = {}
        for section in sections:
            if section.parent_section:
                if section.parent_section not in section_tree:
                    section_tree[section.parent_section] = []
                section_tree[section.parent_section].append(section.id)

        # Calculate confidence
        confidence = 0.7  # Base confidence
        if len(sections) > 5:
            confidence += 0.1
        if len(sections) > 20:
            confidence += 0.1
        if section_tree:  # Has hierarchy
            confidence += 0.1

        return ParsedHierarchy(
            numbering_scheme=scheme,
            sections=sections,
            section_tree=section_tree,
            confidence=min(1.0, confidence),
        )

    def _segment_by_sections(self, text: str, scheme: NumberingScheme) -> List[Dict[str, Any]]:
        """Split text into sections based on detected scheme.

        Returns list of {"number": "I.A", "title": "...", "text": "..."}
        """
        sections = []
        lines = text.split('\n')

        current_section = None
        current_text_lines = []

        # Build multi-level pattern for hierarchical detection
        level_patterns = self._get_level_patterns(scheme)

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if current_section:
                    current_text_lines.append("")
                continue

            # Check if line is a section header
            section_match = None
            for level, pattern in level_patterns:
                match = re.match(pattern, line_stripped)
                if match:
                    section_match = (level, match)
                    break

            if section_match:
                # Save previous section
                if current_section:
                    current_section["text"] = "\n".join(current_text_lines).strip()
                    sections.append(current_section)

                level, match = section_match
                groups = match.groups()

                # Extract number and title based on pattern
                if len(groups) >= 2:
                    number = groups[0]
                    title = groups[-1]  # Last group is usually title

                    # Handle multi-part numbers
                    if scheme.type in ["combined_decimal", "triple_decimal", "accsc_style", "sacscoc_style"]:
                        number_parts = [g for g in groups[:-1] if g]
                        number = ".".join(number_parts)

                    current_section = {
                        "number": number,
                        "title": title,
                        "level": level,
                    }
                    current_text_lines = []
                else:
                    current_text_lines.append(line)
            else:
                current_text_lines.append(line)

        # Save last section
        if current_section:
            current_section["text"] = "\n".join(current_text_lines).strip()
            sections.append(current_section)

        logger.info(f"Segmented text into {len(sections)} sections")
        return sections

    def _get_level_patterns(self, scheme: NumberingScheme) -> List[Tuple[int, str]]:
        """Get patterns for each hierarchy level."""
        patterns = []

        # Primary pattern
        patterns.append((1, scheme.pattern))

        # Add secondary patterns based on scheme type
        if scheme.type == "roman_upper":
            patterns.append((2, r"^([A-Z])\.\s+(.+)$"))
            patterns.append((3, r"^(\d+)\.\s+(.+)$"))
        elif scheme.type == "arabic":
            patterns.append((2, r"^(\d+)\.(\d+)\s+(.+)$"))
            patterns.append((3, r"^(\d+)\.(\d+)\.(\d+)\s+(.+)$"))
        elif scheme.type in ["accsc_style", "sacscoc_style"]:
            # Already handles multiple levels
            pass

        return patterns

    def _build_parent_links(self, sections: List[StandardsSection]) -> Dict[str, str]:
        """Determine parent_section for each section based on numbering.

        E.g., I.A.1's parent is I.A, which parent is I
        """
        parent_map: Dict[str, str] = {}
        section_numbers = {s.number for s in sections}

        for section in sections:
            number = section.number
            if not number:
                continue

            # Try removing last component to find parent
            if "." in number:
                parts = number.rsplit(".", 1)
                potential_parent = parts[0]
                if potential_parent in section_numbers:
                    parent_map[number] = potential_parent
                    continue

            # For single-level numbers, no parent
            # This handles cases like "I", "II", "1", "2"

        return parent_map


class RequirementExtractor:
    """Extract checklist items/requirements from section text."""

    # Patterns indicating requirements
    REQUIREMENT_INDICATORS = [
        r"\bmust\s+",
        r"\bshall\s+",
        r"\brequired\s+to\b",
        r"\binstitution\s+is\s+required\b",
        r"\bdemonstrate\s+that\b",
        r"\bprovide\s+evidence\b",
        r"\bdocument\s+that\b",
        r"\bmaintain\s+records\b",
        r"\bensure\s+that\b",
        r"\bverify\s+that\b",
        r"\bestablish\b",
        r"\bimplement\b",
        r"\bcomply\s+with\b",
    ]

    # Category keywords
    CATEGORY_KEYWORDS = {
        "institutional": ["institution", "governance", "administration", "management", "organization"],
        "program": ["program", "curriculum", "course", "instruction", "educational"],
        "faculty": ["faculty", "instructor", "teacher", "staff", "qualification"],
        "student": ["student", "enrollment", "admission", "completion", "placement"],
        "facility": ["facility", "equipment", "resource", "library", "laboratory"],
        "financial": ["financial", "fiscal", "budget", "tuition", "refund"],
        "admission": ["admission", "enrollment", "recruitment", "application"],
        "assessment": ["assessment", "evaluation", "outcome", "achievement", "competency"],
        "catalog": ["catalog", "publication", "disclosure", "information"],
    }

    # Document type keywords for applies_to
    DOC_TYPE_KEYWORDS = {
        "catalog": ["catalog", "catalogue", "publication"],
        "handbook": ["handbook", "manual", "guide"],
        "policy": ["policy", "policies", "procedure"],
        "syllabus": ["syllabus", "syllabi", "course outline"],
        "faculty_records": ["faculty", "credential", "qualification"],
        "student_records": ["student", "enrollment", "record"],
    }

    def extract_requirements(
        self,
        sections: List[StandardsSection],
        content: ExtractedContent
    ) -> ParsedRequirements:
        """Extract checklist items from parsed sections.

        For each section:
        1. Find requirement indicators
        2. Extract specific requirements
        3. Assign category from section title
        4. Generate item numbers
        """
        checklist_items = []
        by_section: Dict[str, List[str]] = {}
        categories_detected = set()
        item_counter = 0

        for section in sections:
            section_items = self._extract_from_section(section, item_counter)

            for item in section_items:
                item_counter += 1
                item.number = f"{section.number}.{item_counter}" if section.number else str(item_counter)
                item.section_reference = f"Section {section.number}" if section.number else ""
                checklist_items.append(item)

                if section.number:
                    if section.number not in by_section:
                        by_section[section.number] = []
                    by_section[section.number].append(item.number)

                if item.category:
                    categories_detected.add(item.category)

        # Calculate confidence
        confidence = 0.5  # Base
        if checklist_items:
            confidence += 0.2
        if len(checklist_items) > 10:
            confidence += 0.1
        if categories_detected:
            confidence += 0.2

        return ParsedRequirements(
            checklist_items=checklist_items,
            by_section=by_section,
            categories_detected=list(categories_detected),
            confidence=min(1.0, confidence),
        )

    def _extract_from_section(self, section: StandardsSection, start_counter: int) -> List[ChecklistItem]:
        """Extract requirements from a single section."""
        items = []
        text = section.text
        if not text:
            return items

        # Infer category from section title/text
        category = self._infer_category(section)

        # Find sentences with requirement indicators
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            # Check for requirement indicators
            is_requirement = any(
                re.search(pattern, sentence, re.IGNORECASE)
                for pattern in self.REQUIREMENT_INDICATORS
            )

            if is_requirement:
                # Extract applies_to document types
                applies_to = self._extract_applies_to(sentence)

                items.append(ChecklistItem(
                    category=category,
                    description=sentence,
                    applies_to=applies_to,
                ))

        return items

    def _infer_category(self, section: StandardsSection) -> str:
        """Infer checklist category from section title/content."""
        search_text = (section.title + " " + section.text[:500]).lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in search_text for keyword in keywords):
                return category

        return "general"

    def _extract_applies_to(self, requirement_text: str) -> List[str]:
        """Infer which document types a requirement applies to.

        Looks for keywords: catalog, handbook, policy, etc.
        """
        applies_to = []
        text_lower = requirement_text.lower()

        for doc_type, keywords in self.DOC_TYPE_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                applies_to.append(doc_type)

        return applies_to


class MetadataExtractor:
    """Extract standards metadata (title, version, date) from content."""

    # Version patterns
    VERSION_PATTERNS = [
        r"version\s*[:.]?\s*(\d+\.?\d*)",
        r"v(\d+\.?\d*)",
        r"(\d{4})\s*edition",
        r"effective\s*(\d{4})",
        r"revised\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    ]

    # Date patterns
    DATE_PATTERNS = [
        r"effective\s*(?:date)?[:.]?\s*(\w+\s+\d{1,2},?\s+\d{4})",
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"(\w+\s+\d{4})",  # "January 2024"
    ]

    # Accrediting body patterns
    ACCREDITOR_PATTERNS = [
        (r"ACCSC|Accrediting Commission of Career Schools and Colleges", "ACCSC"),
        (r"SACSCOC|Southern Association of Colleges and Schools", "SACSCOC"),
        (r"HLC|Higher Learning Commission", "HLC"),
        (r"ABHES|Accrediting Bureau of Health Education Schools", "ABHES"),
        (r"COE|Council on Occupational Education", "COE"),
        (r"ACICS|Accrediting Council for Independent Colleges", "ACICS"),
        (r"DEAC|Distance Education Accrediting Commission", "DEAC"),
    ]

    def extract_metadata(self, content: ExtractedContent) -> Dict[str, Any]:
        """Extract metadata from content.

        Looks for:
        - Title (first major heading or document title)
        - Version (version patterns, year)
        - Effective date (date patterns)
        - Accrediting body (agency name patterns)
        """
        metadata = {}
        text = content.raw_text[:3000]  # Check first 3000 chars for metadata

        # Extract title
        title = self._extract_title(content)
        if title:
            metadata["title"] = title

        # Extract version
        for pattern in self.VERSION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["version"] = match.group(1)
                break

        # Extract effective date
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["effective_date"] = match.group(1)
                break

        # Extract accrediting body
        for pattern, code in self.ACCREDITOR_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                metadata["accreditor"] = code
                break

        # Add source metadata
        metadata["source_type"] = content.source_type.value
        metadata["source_path"] = content.source_path
        metadata["page_count"] = content.page_count

        return metadata

    def _extract_title(self, content: ExtractedContent) -> Optional[str]:
        """Extract document title from content."""
        # Check structural hints for first heading
        if content.structural_hints:
            for hint in content.structural_hints:
                if hint.get("type") == "heading" and hint.get("level", 99) <= 2:
                    return hint.get("text", "")

        # Fall back to first non-empty line
        lines = content.raw_text.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                # Skip page markers
                if not re.match(r"^\[Page \d+\]", line):
                    return line

        return None


class StandardsParser:
    """Main parser orchestrating hierarchy, requirements, and metadata extraction."""

    def __init__(self):
        self.hierarchy_parser = HierarchyParser()
        self.requirement_extractor = RequirementExtractor()
        self.metadata_extractor = MetadataExtractor()

    def parse(self, content: ExtractedContent) -> ParseResult:
        """Parse extracted content into structured standards.

        Pipeline:
        1. Detect numbering scheme
        2. Parse section hierarchy
        3. Extract requirements from each section
        4. Extract metadata
        5. Validate and compute confidence
        """
        logger.info(f"Parsing content from {content.source_path}")

        warnings = []
        errors = []

        # Check if tabular content
        if content.tables and content.source_type in [ExtractorType.EXCEL, ExtractorType.CSV]:
            return self.parse_tabular(content)

        # Parse hierarchy
        try:
            hierarchy = self.hierarchy_parser.parse_hierarchy(content)
        except Exception as e:
            logger.error(f"Hierarchy parsing failed: {e}")
            errors.append(f"Hierarchy parsing error: {e}")
            hierarchy = ParsedHierarchy(
                numbering_scheme=NumberingScheme(type="unknown", pattern="", levels=[]),
                sections=[],
                section_tree={},
                confidence=0.0,
            )

        # Extract requirements
        try:
            requirements = self.requirement_extractor.extract_requirements(
                hierarchy.sections, content
            )
        except Exception as e:
            logger.error(f"Requirement extraction failed: {e}")
            errors.append(f"Requirement extraction error: {e}")
            requirements = ParsedRequirements(
                checklist_items=[],
                by_section={},
                categories_detected=[],
                confidence=0.0,
            )

        # Extract metadata
        try:
            metadata = self.metadata_extractor.extract_metadata(content)
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            warnings.append(f"Metadata extraction warning: {e}")
            metadata = {}

        # Add warnings for sparse results
        if len(hierarchy.sections) == 0:
            warnings.append("No sections detected. Document may need manual structure definition.")
        if len(requirements.checklist_items) == 0:
            warnings.append("No requirements detected. Consider manual review for checklist items.")

        logger.info(f"Parsed {len(hierarchy.sections)} sections, {len(requirements.checklist_items)} requirements")

        return ParseResult(
            hierarchy=hierarchy,
            requirements=requirements,
            metadata=metadata,
            warnings=warnings,
            errors=errors,
        )

    def parse_tabular(self, content: ExtractedContent) -> ParseResult:
        """Parse tabular content (Excel/CSV) into structured standards.

        Expects columns: number, title, description, category, applies_to
        """
        logger.info(f"Parsing tabular content from {content.source_path}")

        warnings = []
        errors = []
        sections = []
        checklist_items = []
        categories_detected = set()

        # Column name mappings (flexible matching)
        column_mappings = {
            "number": ["number", "section", "id", "code", "ref", "standard"],
            "title": ["title", "name", "heading", "subject"],
            "description": ["description", "text", "content", "requirement", "criteria"],
            "category": ["category", "type", "area", "domain"],
            "applies_to": ["applies_to", "applies", "document", "doc_type"],
        }

        for table in content.tables:
            headers = [h.lower().strip() if h else "" for h in table.get("headers", [])]
            rows = table.get("rows", [])

            # Map headers to columns
            col_indices = {}
            for field, possible_names in column_mappings.items():
                for i, header in enumerate(headers):
                    if any(name in header for name in possible_names):
                        col_indices[field] = i
                        break

            # Process rows
            for row in rows:
                if not row or not any(cell and str(cell).strip() for cell in row):
                    continue

                # Extract values
                number = str(row[col_indices.get("number", 0)]).strip() if col_indices.get("number") is not None and len(row) > col_indices.get("number", 0) else ""
                title = str(row[col_indices.get("title", 1)]).strip() if col_indices.get("title") is not None and len(row) > col_indices.get("title", 1) else ""
                description = str(row[col_indices.get("description", 2)]).strip() if col_indices.get("description") is not None and len(row) > col_indices.get("description", 2) else ""
                category = str(row[col_indices.get("category", -1)]).strip() if col_indices.get("category") is not None and len(row) > col_indices.get("category", -1) else "general"
                applies_to_str = str(row[col_indices.get("applies_to", -1)]).strip() if col_indices.get("applies_to") is not None and len(row) > col_indices.get("applies_to", -1) else ""

                # Skip if no meaningful content
                if not number and not title and not description:
                    continue

                # Parse applies_to
                applies_to = [a.strip() for a in applies_to_str.split(",") if a.strip()] if applies_to_str else []

                # Determine if this is a section or checklist item
                # Sections typically have short descriptions or just titles
                if title and (not description or len(description) < 50):
                    sections.append(StandardsSection(
                        number=number,
                        title=title or description,
                        text=description,
                    ))
                else:
                    # Create checklist item
                    checklist_items.append(ChecklistItem(
                        number=number,
                        category=category,
                        description=description or title,
                        section_reference=f"Section {number}" if number else "",
                        applies_to=applies_to,
                    ))
                    if category:
                        categories_detected.add(category)

        # Build basic hierarchy
        number_to_id = {s.number: s.id for s in sections}
        section_tree = {}

        for section in sections:
            parent_number = self._find_parent_number(section.number, number_to_id)
            if parent_number:
                section.parent_section = number_to_id[parent_number]
                if parent_number not in section_tree:
                    section_tree[parent_number] = []
                section_tree[parent_number].append(section.id)

        # Calculate confidence
        confidence = 0.7 if (sections or checklist_items) else 0.3

        hierarchy = ParsedHierarchy(
            numbering_scheme=NumberingScheme(type="tabular", pattern="", levels=[]),
            sections=sections,
            section_tree=section_tree,
            confidence=confidence,
        )

        requirements = ParsedRequirements(
            checklist_items=checklist_items,
            by_section={},
            categories_detected=list(categories_detected),
            confidence=confidence,
        )

        metadata = self.metadata_extractor.extract_metadata(content)

        logger.info(f"Parsed {len(sections)} sections, {len(checklist_items)} items from tabular data")

        return ParseResult(
            hierarchy=hierarchy,
            requirements=requirements,
            metadata=metadata,
            warnings=warnings,
            errors=errors,
        )

    def _find_parent_number(self, number: str, existing_numbers: Dict[str, str]) -> Optional[str]:
        """Find parent section number."""
        if not number or "." not in number:
            return None

        parts = number.rsplit(".", 1)
        potential_parent = parts[0]

        if potential_parent in existing_numbers:
            return potential_parent

        return None
