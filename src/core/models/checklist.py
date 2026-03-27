"""Checklist auto-fill domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import ComplianceStatus


class ChecklistResponseStatus(str, Enum):
    """Status of a checklist item response."""
    NOT_STARTED = "not_started"
    AUTO_FILLED = "auto_filled"
    NEEDS_REVIEW = "needs_review"
    HUMAN_EDITED = "human_edited"
    APPROVED = "approved"


class FilledChecklistStatus(str, Enum):
    """Status of the overall filled checklist."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AUTO_FILL_COMPLETE = "auto_fill_complete"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EXPORTED = "exported"


@dataclass
class ChecklistResponse:
    """A filled response to a single checklist item.

    Contains the compliance status, evidence gathered, and narrative
    response for a specific checklist requirement.
    """
    id: str = field(default_factory=lambda: generate_id("resp"))
    item_number: str = ""                     # e.g., "I.A.1"
    item_description: str = ""                # Description from ChecklistItem
    category: str = ""                        # Category from ChecklistItem
    section_reference: str = ""               # Standard section reference
    compliance_status: ComplianceStatus = ComplianceStatus.NA
    response_status: ChecklistResponseStatus = ChecklistResponseStatus.NOT_STARTED
    narrative_response: str = ""              # AI-generated or human-written response
    evidence_summary: str = ""                # Summary of supporting evidence
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)  # [{doc_id, page, excerpt}]
    audit_finding_ids: List[str] = field(default_factory=list)  # Related finding IDs
    remediation_ids: List[str] = field(default_factory=list)    # Related remediation IDs
    ai_confidence: float = 0.0
    human_notes: str = ""
    last_updated: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_number": self.item_number,
            "item_description": self.item_description,
            "category": self.category,
            "section_reference": self.section_reference,
            "compliance_status": self.compliance_status.value,
            "response_status": self.response_status.value,
            "narrative_response": self.narrative_response,
            "evidence_summary": self.evidence_summary,
            "evidence_sources": self.evidence_sources,
            "audit_finding_ids": self.audit_finding_ids,
            "remediation_ids": self.remediation_ids,
            "ai_confidence": self.ai_confidence,
            "human_notes": self.human_notes,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistResponse":
        return cls(
            id=data.get("id", generate_id("resp")),
            item_number=data.get("item_number", ""),
            item_description=data.get("item_description", ""),
            category=data.get("category", ""),
            section_reference=data.get("section_reference", ""),
            compliance_status=ComplianceStatus(data.get("compliance_status", "na")),
            response_status=ChecklistResponseStatus(data.get("response_status", "not_started")),
            narrative_response=data.get("narrative_response", ""),
            evidence_summary=data.get("evidence_summary", ""),
            evidence_sources=data.get("evidence_sources", []),
            audit_finding_ids=data.get("audit_finding_ids", []),
            remediation_ids=data.get("remediation_ids", []),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_notes=data.get("human_notes", ""),
            last_updated=data.get("last_updated", now_iso()),
        )


@dataclass
class FilledChecklist:
    """A complete filled checklist for an institution.

    Links to a standards library and contains filled responses
    for each checklist item.
    """
    id: str = field(default_factory=lambda: generate_id("fcl"))
    institution_id: str = ""
    program_id: str = ""                      # Optional: program-specific checklist
    standards_library_id: str = ""            # Source standards library
    accrediting_body: str = ""                # e.g., "ACCSC"
    name: str = ""                            # e.g., "ACCSC Self-Evaluation 2024"
    status: FilledChecklistStatus = FilledChecklistStatus.NOT_STARTED
    responses: List[ChecklistResponse] = field(default_factory=list)
    total_items: int = 0
    items_completed: int = 0
    items_compliant: int = 0
    items_partial: int = 0
    items_non_compliant: int = 0
    items_needs_review: int = 0
    auto_fill_sources: Dict[str, Any] = field(default_factory=dict)  # {audit_ids, doc_ids}
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    exported_path: str = ""                   # Path to exported DOCX/PDF

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "standards_library_id": self.standards_library_id,
            "accrediting_body": self.accrediting_body,
            "name": self.name,
            "status": self.status.value,
            "responses": [r.to_dict() for r in self.responses],
            "total_items": self.total_items,
            "items_completed": self.items_completed,
            "items_compliant": self.items_compliant,
            "items_partial": self.items_partial,
            "items_non_compliant": self.items_non_compliant,
            "items_needs_review": self.items_needs_review,
            "auto_fill_sources": self.auto_fill_sources,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "exported_path": self.exported_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilledChecklist":
        return cls(
            id=data.get("id", generate_id("fcl")),
            institution_id=data.get("institution_id", ""),
            program_id=data.get("program_id", ""),
            standards_library_id=data.get("standards_library_id", ""),
            accrediting_body=data.get("accrediting_body", ""),
            name=data.get("name", ""),
            status=FilledChecklistStatus(data.get("status", "not_started")),
            responses=[ChecklistResponse.from_dict(r) for r in data.get("responses", [])],
            total_items=data.get("total_items", 0),
            items_completed=data.get("items_completed", 0),
            items_compliant=data.get("items_compliant", 0),
            items_partial=data.get("items_partial", 0),
            items_non_compliant=data.get("items_non_compliant", 0),
            items_needs_review=data.get("items_needs_review", 0),
            auto_fill_sources=data.get("auto_fill_sources", {}),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            completed_at=data.get("completed_at"),
            exported_path=data.get("exported_path", ""),
        )

    def update_stats(self) -> None:
        """Recalculate statistics from responses."""
        self.total_items = len(self.responses)
        self.items_completed = sum(
            1 for r in self.responses
            if r.response_status in (ChecklistResponseStatus.AUTO_FILLED,
                                     ChecklistResponseStatus.HUMAN_EDITED,
                                     ChecklistResponseStatus.APPROVED)
        )
        self.items_compliant = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.COMPLIANT
        )
        self.items_partial = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.PARTIAL
        )
        self.items_non_compliant = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.NON_COMPLIANT
        )
        self.items_needs_review = sum(
            1 for r in self.responses if r.response_status == ChecklistResponseStatus.NEEDS_REVIEW
        )
        self.updated_at = now_iso()
