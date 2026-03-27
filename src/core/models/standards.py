"""Standards and regulatory domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import AccreditingBody


@dataclass
class ChecklistItem:
    """A checklist item within a standards section.

    Represents a specific requirement or criterion that documents
    must satisfy for accreditation compliance.
    """
    number: str = ""                          # e.g., "1.a", "2.b.i"
    category: str = ""                        # e.g., "Institutional", "Program"
    description: str = ""
    section_reference: str = ""               # e.g., "Section I.A.1"
    applies_to: List[str] = field(default_factory=list)  # DocumentType values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "category": self.category,
            "description": self.description,
            "section_reference": self.section_reference,
            "applies_to": self.applies_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistItem":
        return cls(
            number=data.get("number", ""),
            category=data.get("category", ""),
            description=data.get("description", ""),
            section_reference=data.get("section_reference", ""),
            applies_to=data.get("applies_to", []),
        )


@dataclass
class StandardsSection:
    """A section within a standards library.

    Sections form a hierarchy (e.g., I -> I.A -> I.A.1) linked
    via parent_section references.
    """
    id: str = field(default_factory=lambda: generate_id("sec"))
    number: str = ""                          # e.g., "I", "I.A", "I.A.1"
    title: str = ""
    text: str = ""                            # Full section text
    parent_section: str = ""                  # ID of parent section (empty for top-level)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "text": self.text,
            "parent_section": self.parent_section,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardsSection":
        return cls(
            id=data.get("id", generate_id("sec")),
            number=data.get("number", ""),
            title=data.get("title", ""),
            text=data.get("text", ""),
            parent_section=data.get("parent_section", ""),
        )


@dataclass
class StandardsLibrary:
    """A set of accreditation standards for an accrediting body.

    Contains the hierarchical structure of standards sections and
    checklist items used for compliance auditing.
    """
    id: str = field(default_factory=lambda: generate_id("std"))
    accrediting_body: AccreditingBody = AccreditingBody.ACCSC
    name: str = ""                            # e.g., "ACCSC Substantive Standards"
    version: str = ""                         # e.g., "2023"
    effective_date: str = ""
    sections: List[StandardsSection] = field(default_factory=list)
    checklist_items: List[ChecklistItem] = field(default_factory=list)
    full_text: str = ""                       # Complete standards document text
    is_system_preset: bool = False
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "accrediting_body": self.accrediting_body.value if isinstance(self.accrediting_body, AccreditingBody) else self.accrediting_body,
            "name": self.name,
            "version": self.version,
            "effective_date": self.effective_date,
            "sections": [s.to_dict() for s in self.sections],
            "checklist_items": [c.to_dict() for c in self.checklist_items],
            "full_text": self.full_text,
            "is_system_preset": self.is_system_preset,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardsLibrary":
        accreditor = data.get("accrediting_body", "ACCSC")
        if isinstance(accreditor, str):
            try:
                accreditor = AccreditingBody(accreditor)
            except ValueError:
                accreditor = AccreditingBody.CUSTOM

        return cls(
            id=data.get("id", generate_id("std")),
            accrediting_body=accreditor,
            name=data.get("name", ""),
            version=data.get("version", ""),
            effective_date=data.get("effective_date", ""),
            sections=[StandardsSection.from_dict(s) for s in data.get("sections", [])],
            checklist_items=[ChecklistItem.from_dict(c) for c in data.get("checklist_items", [])],
            full_text=data.get("full_text", ""),
            is_system_preset=data.get("is_system_preset", False),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class CrosswalkEntry:
    """Single row in a crosswalk table.

    Maps a standard requirement to its supporting evidence from documents.
    """
    standard_ref: str = ""
    section_reference: str = ""
    category: str = ""
    requirement: str = ""
    evidence_found: bool = False
    quality: str = "missing"  # strong, adequate, weak, missing
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    confidence: float = 0.0
    exhibit_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_ref": self.standard_ref,
            "section_reference": self.section_reference,
            "category": self.category,
            "requirement": self.requirement,
            "evidence_found": self.evidence_found,
            "quality": self.quality,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page": self.page,
            "snippet": self.snippet,
            "confidence": self.confidence,
            "exhibit_label": self.exhibit_label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrosswalkEntry":
        return cls(
            standard_ref=data.get("standard_ref", ""),
            section_reference=data.get("section_reference", ""),
            category=data.get("category", ""),
            requirement=data.get("requirement", ""),
            evidence_found=data.get("evidence_found", False),
            quality=data.get("quality", "missing"),
            document_id=data.get("document_id"),
            document_name=data.get("document_name"),
            page=data.get("page"),
            snippet=data.get("snippet"),
            confidence=data.get("confidence", 0.0),
            exhibit_label=data.get("exhibit_label"),
        )


@dataclass
class EvidenceMapping:
    """Maps a single standard to its supporting evidence.

    Contains all evidence found for a requirement with quality assessment.
    """
    standard_id: str = ""
    standard_number: str = ""
    standard_text: str = ""
    status: str = "missing"  # satisfied, partial, weak, missing
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    suggested_exhibit: Optional[str] = None
    gap_notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "standard_number": self.standard_number,
            "standard_text": self.standard_text,
            "status": self.status,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "suggested_exhibit": self.suggested_exhibit,
            "gap_notes": self.gap_notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceMapping":
        return cls(
            standard_id=data.get("standard_id", ""),
            standard_number=data.get("standard_number", ""),
            standard_text=data.get("standard_text", ""),
            status=data.get("status", "missing"),
            confidence=data.get("confidence", 0.0),
            evidence=data.get("evidence", []),
            suggested_exhibit=data.get("suggested_exhibit"),
            gap_notes=data.get("gap_notes"),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class EvidenceMap:
    """Complete evidence map for an institution against a standards library.

    Contains all standard-to-evidence mappings with coverage statistics.
    """
    id: str = field(default_factory=lambda: generate_id("evmap"))
    institution_id: str = ""
    standards_library_id: str = ""
    mappings: List[EvidenceMapping] = field(default_factory=list)
    coverage_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "standards_library_id": self.standards_library_id,
            "mappings": [m.to_dict() if hasattr(m, 'to_dict') else m for m in self.mappings],
            "coverage_stats": self.coverage_stats,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceMap":
        mappings_data = data.get("mappings", [])
        mappings = [
            EvidenceMapping.from_dict(m) if isinstance(m, dict) else m
            for m in mappings_data
        ]
        return cls(
            id=data.get("id", generate_id("evmap")),
            institution_id=data.get("institution_id", ""),
            standards_library_id=data.get("standards_library_id", ""),
            mappings=mappings,
            coverage_stats=data.get("coverage_stats", {}),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class EvidenceGap:
    """An identified gap in evidence coverage.

    Represents a standard that lacks sufficient evidence, with
    severity classification and remediation suggestions.
    """
    standard_id: str = ""
    standard_number: str = ""
    standard_text: str = ""
    severity: str = "advisory"  # critical, high, advisory
    current_coverage: str = "missing"  # weak, missing
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    related_doc_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "standard_number": self.standard_number,
            "standard_text": self.standard_text,
            "severity": self.severity,
            "current_coverage": self.current_coverage,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "related_doc_types": self.related_doc_types,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceGap":
        return cls(
            standard_id=data.get("standard_id", ""),
            standard_number=data.get("standard_number", ""),
            standard_text=data.get("standard_text", ""),
            severity=data.get("severity", "advisory"),
            current_coverage=data.get("current_coverage", "missing"),
            confidence=data.get("confidence", 0.0),
            suggestions=data.get("suggestions", []),
            related_doc_types=data.get("related_doc_types", []),
        )


@dataclass
class RegulatoryStack:
    """Combined regulatory requirements for an institution.

    Aggregates accreditor standards with federal, state, and
    professional requirements for comprehensive compliance tracking.
    """
    id: str = field(default_factory=lambda: generate_id("stack"))
    institution_id: str = ""
    accreditor_standards_id: str = ""         # Reference to StandardsLibrary
    federal_regulations: List[Dict[str, Any]] = field(default_factory=list)
    state_regulations: List[Dict[str, Any]] = field(default_factory=list)
    professional_requirements: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "accreditor_standards_id": self.accreditor_standards_id,
            "federal_regulations": self.federal_regulations,
            "state_regulations": self.state_regulations,
            "professional_requirements": self.professional_requirements,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegulatoryStack":
        return cls(
            id=data.get("id", generate_id("stack")),
            institution_id=data.get("institution_id", ""),
            accreditor_standards_id=data.get("accreditor_standards_id", ""),
            federal_regulations=data.get("federal_regulations", []),
            state_regulations=data.get("state_regulations", []),
            professional_requirements=data.get("professional_requirements", []),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
