"""Remediation domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


class RemediationStatus(str, Enum):
    """Status of a remediation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    APPLIED = "applied"


@dataclass
class RemediationChange:
    """A single change to be applied to a document."""
    id: str = field(default_factory=lambda: generate_id("chg"))
    finding_id: str = ""
    item_number: str = ""
    change_type: str = "insert"  # insert, replace, delete
    location: str = ""  # section/page reference
    original_text: str = ""
    corrected_text: str = ""
    standard_citation: str = ""
    rationale: str = ""
    ai_confidence: float = 0.0
    human_approved: bool = False
    human_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "item_number": self.item_number,
            "change_type": self.change_type,
            "location": self.location,
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "standard_citation": self.standard_citation,
            "rationale": self.rationale,
            "ai_confidence": self.ai_confidence,
            "human_approved": self.human_approved,
            "human_notes": self.human_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationChange":
        return cls(
            id=data.get("id", generate_id("chg")),
            finding_id=data.get("finding_id", ""),
            item_number=data.get("item_number", ""),
            change_type=data.get("change_type", "insert"),
            location=data.get("location", ""),
            original_text=data.get("original_text", ""),
            corrected_text=data.get("corrected_text", ""),
            standard_citation=data.get("standard_citation", ""),
            rationale=data.get("rationale", ""),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_approved=data.get("human_approved", False),
            human_notes=data.get("human_notes"),
        )


@dataclass
class RemediationResult:
    """Result of remediating a document based on audit findings."""
    id: str = field(default_factory=lambda: generate_id("remed"))
    audit_id: str = ""
    document_id: str = ""
    institution_id: str = ""
    status: RemediationStatus = RemediationStatus.PENDING
    changes: List[RemediationChange] = field(default_factory=list)
    findings_addressed: int = 0
    findings_skipped: int = 0
    redline_path: str = ""
    final_path: str = ""
    crossref_path: str = ""
    truth_index_applied: bool = False
    truth_index_changes: List[Dict[str, Any]] = field(default_factory=list)
    ai_model_used: str = ""
    created_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "document_id": self.document_id,
            "institution_id": self.institution_id,
            "status": self.status.value,
            "changes": [c.to_dict() for c in self.changes],
            "findings_addressed": self.findings_addressed,
            "findings_skipped": self.findings_skipped,
            "redline_path": self.redline_path,
            "final_path": self.final_path,
            "crossref_path": self.crossref_path,
            "truth_index_applied": self.truth_index_applied,
            "truth_index_changes": self.truth_index_changes,
            "ai_model_used": self.ai_model_used,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationResult":
        return cls(
            id=data.get("id", generate_id("remed")),
            audit_id=data.get("audit_id", ""),
            document_id=data.get("document_id", ""),
            institution_id=data.get("institution_id", ""),
            status=RemediationStatus(data.get("status", "pending")),
            changes=[RemediationChange.from_dict(c) for c in data.get("changes", [])],
            findings_addressed=data.get("findings_addressed", 0),
            findings_skipped=data.get("findings_skipped", 0),
            redline_path=data.get("redline_path", ""),
            final_path=data.get("final_path", ""),
            crossref_path=data.get("crossref_path", ""),
            truth_index_applied=data.get("truth_index_applied", False),
            truth_index_changes=data.get("truth_index_changes", []),
            ai_model_used=data.get("ai_model_used", ""),
            created_at=data.get("created_at", now_iso()),
            completed_at=data.get("completed_at"),
        )
