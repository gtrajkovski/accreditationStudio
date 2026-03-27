"""Standards validation and conflict detection.

Validates parsed standards structure, detects issues, and computes
quality/confidence scores.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Set, Optional
import logging

from src.core.models import StandardsSection, ChecklistItem

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "error"      # Must fix before import
    WARNING = "warning"  # Should fix but can proceed
    INFO = "info"        # Informational only


@dataclass
class ValidationIssue:
    """A validation issue found in parsed standards."""
    severity: ValidationSeverity
    code: str           # e.g., "DUPLICATE_SECTION", "MISSING_TITLE"
    message: str
    location: str       # e.g., "Section I.A.1" or "Checklist item 3"
    suggestion: str = ""
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationIssue":
        severity = data.get("severity", "warning")
        if isinstance(severity, str):
            try:
                severity = ValidationSeverity(severity)
            except ValueError:
                severity = ValidationSeverity.WARNING

        return cls(
            severity=severity,
            code=data.get("code", ""),
            message=data.get("message", ""),
            location=data.get("location", ""),
            suggestion=data.get("suggestion", ""),
            auto_fixable=data.get("auto_fixable", False),
        )


@dataclass
class ConflictReport:
    """Report of conflicts found during validation."""
    duplicate_sections: List[Dict[str, Any]] = field(default_factory=list)
    orphaned_sections: List[str] = field(default_factory=list)  # Children without parents
    missing_parents: List[str] = field(default_factory=list)
    duplicate_items: List[Dict[str, Any]] = field(default_factory=list)
    circular_references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duplicate_sections": self.duplicate_sections,
            "orphaned_sections": self.orphaned_sections,
            "missing_parents": self.missing_parents,
            "duplicate_items": self.duplicate_items,
            "circular_references": self.circular_references,
            "has_conflicts": self.has_conflicts(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictReport":
        return cls(
            duplicate_sections=data.get("duplicate_sections", []),
            orphaned_sections=data.get("orphaned_sections", []),
            missing_parents=data.get("missing_parents", []),
            duplicate_items=data.get("duplicate_items", []),
            circular_references=data.get("circular_references", []),
        )

    def has_conflicts(self) -> bool:
        return bool(
            self.duplicate_sections or
            self.orphaned_sections or
            self.duplicate_items or
            self.circular_references
        )


@dataclass
class QualityScore:
    """Quality assessment of parsed standards."""
    overall: float = 0.0           # 0-100
    structure_score: float = 0.0   # Hierarchy completeness
    content_score: float = 0.0     # Section text quality
    coverage_score: float = 0.0    # Requirements coverage
    breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "structure_score": self.structure_score,
            "content_score": self.content_score,
            "coverage_score": self.coverage_score,
            "breakdown": self.breakdown,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityScore":
        return cls(
            overall=data.get("overall", 0.0),
            structure_score=data.get("structure_score", 0.0),
            content_score=data.get("content_score", 0.0),
            coverage_score=data.get("coverage_score", 0.0),
            breakdown=data.get("breakdown", {}),
        )


@dataclass
class ValidationResult:
    """Complete validation result."""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    conflicts: ConflictReport = field(default_factory=ConflictReport)
    quality: QualityScore = field(default_factory=QualityScore)
    can_import: bool = True  # No ERROR-level issues

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "can_import": self.can_import,
            "issues": [i.to_dict() for i in self.issues],
            "conflicts": self.conflicts.to_dict(),
            "quality": self.quality.to_dict(),
            "error_count": len([i for i in self.issues if i.severity == ValidationSeverity.ERROR]),
            "warning_count": len([i for i in self.issues if i.severity == ValidationSeverity.WARNING]),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        return cls(
            valid=data.get("valid", False),
            issues=[ValidationIssue.from_dict(i) for i in data.get("issues", [])],
            conflicts=ConflictReport.from_dict(data.get("conflicts", {})),
            quality=QualityScore.from_dict(data.get("quality", {})),
            can_import=data.get("can_import", False),
        )


class SchemaValidator:
    """Validate required fields and data types."""

    REQUIRED_SECTION_FIELDS = ["number", "title"]
    REQUIRED_ITEM_FIELDS = ["number", "description"]

    def validate_section(self, section: StandardsSection) -> List[ValidationIssue]:
        """Validate a single section."""
        issues = []

        if not section.number:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="MISSING_NUMBER",
                message="Section is missing a number",
                location=f"Section '{section.title or 'untitled'}'",
                suggestion="Assign a section number (e.g., I.A.1)",
            ))

        if not section.title:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="MISSING_TITLE",
                message="Section is missing a title",
                location=f"Section {section.number}",
                suggestion="Add a descriptive title",
                auto_fixable=True,
            ))

        if section.title and len(section.title) > 500:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="TITLE_TOO_LONG",
                message=f"Section title is very long ({len(section.title)} chars)",
                location=f"Section {section.number}",
                suggestion="Consider shortening the title",
            ))

        if not section.text:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="EMPTY_TEXT",
                message="Section has no body text",
                location=f"Section {section.number}",
                suggestion="Consider adding descriptive text",
            ))

        return issues

    def validate_item(self, item: ChecklistItem) -> List[ValidationIssue]:
        """Validate a single checklist item."""
        issues = []

        if not item.number:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="MISSING_ITEM_NUMBER",
                message="Checklist item is missing a number",
                location=f"Item '{item.description[:50] if item.description else 'empty'}...'",
                suggestion="Assign an item number",
                auto_fixable=True,
            ))

        if not item.description:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="MISSING_DESCRIPTION",
                message="Checklist item has no description",
                location=f"Item {item.number or 'unknown'}",
                suggestion="Add a requirement description",
            ))

        if item.description and len(item.description) < 10:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="SHORT_DESCRIPTION",
                message=f"Checklist item description is very short ({len(item.description)} chars)",
                location=f"Item {item.number}",
                suggestion="Consider expanding the description",
            ))

        if not item.category:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code="MISSING_CATEGORY",
                message="Checklist item has no category",
                location=f"Item {item.number}",
                suggestion="Assign a category for better organization",
                auto_fixable=True,
            ))

        return issues

    def validate_all(
        self,
        sections: List[StandardsSection],
        items: List[ChecklistItem]
    ) -> List[ValidationIssue]:
        """Validate all sections and items."""
        issues = []

        # Validate sections
        for section in sections:
            issues.extend(self.validate_section(section))

        # Validate items
        for item in items:
            issues.extend(self.validate_item(item))

        # Check for empty inputs
        if not sections and not items:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="EMPTY_IMPORT",
                message="No sections or checklist items found in import",
                location="Import",
                suggestion="Check if the source document was parsed correctly",
            ))

        return issues


class ConflictDetector:
    """Detect conflicts in parsed standards."""

    def detect_conflicts(
        self,
        sections: List[StandardsSection],
        items: List[ChecklistItem]
    ) -> ConflictReport:
        """Detect all conflicts in the parsed data.

        Checks:
        - Duplicate section numbers
        - Duplicate checklist item numbers
        - Orphaned sections (reference non-existent parent)
        - Circular parent references
        """
        report = ConflictReport()

        # Check for duplicate sections
        report.duplicate_sections = self._find_duplicate_sections(sections)

        # Check for orphaned sections
        report.orphaned_sections, report.missing_parents = self._find_orphaned_sections(sections)

        # Check for circular references
        report.circular_references = self._detect_circular_refs(sections)

        # Check for duplicate items
        report.duplicate_items = self._find_duplicate_items(items)

        return report

    def _find_duplicate_sections(self, sections: List[StandardsSection]) -> List[Dict[str, Any]]:
        """Find sections with duplicate numbers."""
        duplicates = []
        seen: Dict[str, List[str]] = {}

        for section in sections:
            if section.number:
                if section.number not in seen:
                    seen[section.number] = []
                seen[section.number].append(section.id)

        for number, ids in seen.items():
            if len(ids) > 1:
                duplicates.append({
                    "number": number,
                    "count": len(ids),
                    "ids": ids,
                })

        return duplicates

    def _find_orphaned_sections(self, sections: List[StandardsSection]) -> tuple:
        """Find sections referencing non-existent parents."""
        orphaned = []
        missing_parents = []
        section_ids = {s.id for s in sections}

        for section in sections:
            if section.parent_section and section.parent_section not in section_ids:
                orphaned.append(section.number or section.id)
                if section.parent_section not in missing_parents:
                    missing_parents.append(section.parent_section)

        return orphaned, missing_parents

    def _detect_circular_refs(self, sections: List[StandardsSection]) -> List[str]:
        """Detect circular parent-child references."""
        circular = []
        id_to_section = {s.id: s for s in sections}

        for section in sections:
            if not section.parent_section:
                continue

            # Walk up the parent chain
            visited = {section.id}
            current_id = section.parent_section

            while current_id:
                if current_id in visited:
                    circular.append(section.number or section.id)
                    break
                visited.add(current_id)
                parent = id_to_section.get(current_id)
                current_id = parent.parent_section if parent else None

        return circular

    def _find_duplicate_items(self, items: List[ChecklistItem]) -> List[Dict[str, Any]]:
        """Find checklist items with duplicate numbers."""
        duplicates = []
        seen: Dict[str, int] = {}

        for item in items:
            if item.number:
                seen[item.number] = seen.get(item.number, 0) + 1

        for number, count in seen.items():
            if count > 1:
                duplicates.append({
                    "number": number,
                    "count": count,
                })

        return duplicates


class QualityScorer:
    """Compute quality scores for parsed standards."""

    def compute_scores(
        self,
        sections: List[StandardsSection],
        items: List[ChecklistItem],
        issues: List[ValidationIssue]
    ) -> QualityScore:
        """Compute overall quality score.

        Factors:
        - Structure: hierarchy depth, completeness
        - Content: average text length, descriptions present
        - Coverage: items per section, applies_to populated
        - Issues: deductions for warnings/errors
        """
        breakdown = {}

        # Structure score (0-100)
        structure_score = self._compute_structure_score(sections)
        breakdown["structure"] = structure_score

        # Content score (0-100)
        content_score = self._compute_content_score(sections, items)
        breakdown["content"] = content_score

        # Coverage score (0-100)
        coverage_score = self._compute_coverage_score(sections, items)
        breakdown["coverage"] = coverage_score

        # Issue deductions
        error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        warning_count = len([i for i in issues if i.severity == ValidationSeverity.WARNING])

        issue_penalty = min(40, error_count * 10 + warning_count * 2)
        breakdown["issue_penalty"] = -issue_penalty

        # Compute overall (weighted average)
        raw_score = (
            structure_score * 0.30 +
            content_score * 0.35 +
            coverage_score * 0.35
        )
        overall = max(0, min(100, raw_score - issue_penalty))

        return QualityScore(
            overall=round(overall, 1),
            structure_score=round(structure_score, 1),
            content_score=round(content_score, 1),
            coverage_score=round(coverage_score, 1),
            breakdown=breakdown,
        )

    def _compute_structure_score(self, sections: List[StandardsSection]) -> float:
        """Compute structure quality score."""
        if not sections:
            return 0.0

        score = 50.0  # Base score

        # Bonus for having sections
        section_count = len(sections)
        if section_count >= 5:
            score += 10
        if section_count >= 10:
            score += 10
        if section_count >= 20:
            score += 10

        # Bonus for hierarchy (sections with parents)
        sections_with_parents = len([s for s in sections if s.parent_section])
        if sections_with_parents > 0:
            parent_ratio = sections_with_parents / section_count
            score += 20 * parent_ratio

        # Penalty for missing numbers
        sections_without_numbers = len([s for s in sections if not s.number])
        if sections_without_numbers > 0:
            missing_ratio = sections_without_numbers / section_count
            score -= 20 * missing_ratio

        return max(0, min(100, score))

    def _compute_content_score(self, sections: List[StandardsSection], items: List[ChecklistItem]) -> float:
        """Compute content quality score."""
        score = 50.0  # Base score

        # Section text quality
        if sections:
            texts_with_content = len([s for s in sections if s.text and len(s.text) > 50])
            text_ratio = texts_with_content / len(sections)
            score += 25 * text_ratio

            # Average text length bonus
            total_text_len = sum(len(s.text) for s in sections if s.text)
            avg_text_len = total_text_len / len(sections) if sections else 0
            if avg_text_len > 100:
                score += 10
            if avg_text_len > 300:
                score += 5

        # Item description quality
        if items:
            items_with_desc = len([i for i in items if i.description and len(i.description) > 20])
            desc_ratio = items_with_desc / len(items)
            score += 10 * desc_ratio

        return max(0, min(100, score))

    def _compute_coverage_score(self, sections: List[StandardsSection], items: List[ChecklistItem]) -> float:
        """Compute coverage quality score."""
        score = 50.0  # Base score

        # Items per section ratio
        if sections and items:
            items_per_section = len(items) / len(sections)
            if items_per_section >= 1:
                score += 15
            if items_per_section >= 2:
                score += 10
            if items_per_section >= 3:
                score += 5

        # Items with categories
        if items:
            items_with_category = len([i for i in items if i.category and i.category != "general"])
            category_ratio = items_with_category / len(items)
            score += 10 * category_ratio

        # Items with applies_to
        if items:
            items_with_applies_to = len([i for i in items if i.applies_to])
            applies_ratio = items_with_applies_to / len(items)
            score += 10 * applies_ratio

        return max(0, min(100, score))


class StandardsValidator:
    """Main validator orchestrating all validation checks."""

    def __init__(self):
        self.schema_validator = SchemaValidator()
        self.conflict_detector = ConflictDetector()
        self.quality_scorer = QualityScorer()

    def validate(
        self,
        sections: List[StandardsSection],
        items: List[ChecklistItem]
    ) -> ValidationResult:
        """Run full validation suite.

        Returns:
            ValidationResult with issues, conflicts, and quality scores
        """
        logger.info(f"Validating {len(sections)} sections and {len(items)} checklist items")

        # Schema validation
        issues = self.schema_validator.validate_all(sections, items)

        # Conflict detection
        conflicts = self.conflict_detector.detect_conflicts(sections, items)

        # Add conflict issues
        for dup in conflicts.duplicate_sections:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="DUPLICATE_SECTION",
                message=f"Duplicate section number: {dup['number']} ({dup['count']} occurrences)",
                location=f"Sections with number {dup['number']}",
                suggestion="Ensure each section has a unique number",
            ))

        for orphan in conflicts.orphaned_sections:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="ORPHANED_SECTION",
                message=f"Section references non-existent parent",
                location=f"Section {orphan}",
                suggestion="Check parent section reference",
                auto_fixable=True,
            ))

        for circular in conflicts.circular_references:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code="CIRCULAR_REFERENCE",
                message="Section has circular parent reference",
                location=f"Section {circular}",
                suggestion="Fix parent-child relationships to remove cycle",
            ))

        for dup in conflicts.duplicate_items:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code="DUPLICATE_ITEM",
                message=f"Duplicate item number: {dup['number']} ({dup['count']} occurrences)",
                location=f"Items with number {dup['number']}",
                suggestion="Consider renumbering checklist items",
                auto_fixable=True,
            ))

        # Quality scoring
        quality = self.quality_scorer.compute_scores(sections, items, issues)

        # Determine validity
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        has_blocking_conflicts = bool(conflicts.duplicate_sections or conflicts.circular_references)

        valid = not has_errors and not has_blocking_conflicts
        can_import = not has_errors

        logger.info(f"Validation complete: valid={valid}, can_import={can_import}, "
                   f"errors={len([i for i in issues if i.severity == ValidationSeverity.ERROR])}, "
                   f"warnings={len([i for i in issues if i.severity == ValidationSeverity.WARNING])}, "
                   f"quality={quality.overall}")

        return ValidationResult(
            valid=valid,
            issues=issues,
            conflicts=conflicts,
            quality=quality,
            can_import=can_import,
        )
