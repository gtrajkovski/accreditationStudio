"""Audit domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import (
    ComplianceStatus,
    FindingSeverity,
    RegulatorySource,
    AuditStatus,
)


@dataclass
class AuditFinding:
    """A finding from a document audit."""
    id: str = field(default_factory=lambda: generate_id("find"))
    audit_id: str = ""
    item_number: str = ""
    item_description: str = ""
    status: ComplianceStatus = ComplianceStatus.NA
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    regulatory_source: RegulatorySource = RegulatorySource.ACCREDITOR
    regulatory_citation: str = ""
    evidence_in_document: str = ""
    finding_detail: str = ""
    recommendation: str = ""
    page_numbers: str = ""
    ai_confidence: float = 0.0
    human_override_status: Optional[str] = None
    human_notes: Optional[str] = None
    pass_discovered: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "item_number": self.item_number,
            "item_description": self.item_description,
            "status": self.status.value,
            "severity": self.severity.value,
            "regulatory_source": self.regulatory_source.value,
            "regulatory_citation": self.regulatory_citation,
            "evidence_in_document": self.evidence_in_document,
            "finding_detail": self.finding_detail,
            "recommendation": self.recommendation,
            "page_numbers": self.page_numbers,
            "ai_confidence": self.ai_confidence,
            "human_override_status": self.human_override_status,
            "human_notes": self.human_notes,
            "pass_discovered": self.pass_discovered,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditFinding":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("find")),
            audit_id=data.get("audit_id", ""),
            item_number=data.get("item_number", ""),
            item_description=data.get("item_description", ""),
            status=ComplianceStatus(data.get("status", "na")),
            severity=FindingSeverity(data.get("severity", "informational")),
            regulatory_source=RegulatorySource(data.get("regulatory_source", "accreditor")),
            regulatory_citation=data.get("regulatory_citation", ""),
            evidence_in_document=data.get("evidence_in_document", ""),
            finding_detail=data.get("finding_detail", ""),
            recommendation=data.get("recommendation", ""),
            page_numbers=data.get("page_numbers", ""),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_override_status=data.get("human_override_status"),
            human_notes=data.get("human_notes"),
            pass_discovered=data.get("pass_discovered", 1),
        )


@dataclass
class Audit:
    """An audit of a document."""
    id: str = field(default_factory=lambda: generate_id("audit"))
    document_id: str = ""
    program_id: Optional[str] = None
    standards_library_id: str = ""
    regulatory_stack_id: str = ""
    audit_type: str = "full"
    status: AuditStatus = AuditStatus.DRAFT
    summary: Dict[str, int] = field(default_factory=dict)
    summary_by_source: Dict[str, Dict[str, int]] = field(default_factory=dict)
    findings: List[AuditFinding] = field(default_factory=list)
    passes_completed: int = 0
    ai_model_used: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "program_id": self.program_id,
            "standards_library_id": self.standards_library_id,
            "regulatory_stack_id": self.regulatory_stack_id,
            "audit_type": self.audit_type,
            "status": self.status.value,
            "summary": self.summary,
            "summary_by_source": self.summary_by_source,
            "findings": [f.to_dict() for f in self.findings],
            "passes_completed": self.passes_completed,
            "ai_model_used": self.ai_model_used,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Audit":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("audit")),
            document_id=data.get("document_id", ""),
            program_id=data.get("program_id"),
            standards_library_id=data.get("standards_library_id", ""),
            regulatory_stack_id=data.get("regulatory_stack_id", ""),
            audit_type=data.get("audit_type", "full"),
            status=AuditStatus(data.get("status", "draft")),
            summary=data.get("summary", {}),
            summary_by_source=data.get("summary_by_source", {}),
            findings=[AuditFinding.from_dict(f) for f in data.get("findings", [])],
            passes_completed=data.get("passes_completed", 0),
            ai_model_used=data.get("ai_model_used", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )
