"""Submission packet domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


class SubmissionType(str, Enum):
    """Types of accreditation submissions."""
    INITIAL_ACCREDITATION = "initial_accreditation"
    RENEWAL = "renewal"
    SUBSTANTIVE_CHANGE = "substantive_change"
    COMPLIANCE_REPORT = "compliance_report"
    RESPONSE_TO_FINDINGS = "response_to_findings"
    ANNUAL_REPORT = "annual_report"
    TEACH_OUT_PLAN = "teach_out_plan"
    OTHER = "other"


class PacketStatus(str, Enum):
    """Status of submission packet assembly."""
    DRAFT = "draft"
    ASSEMBLING = "assembling"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    READY = "ready"
    APPROVED = "approved"
    EXPORTED = "exported"
    SUBMITTED = "submitted"


class PacketSectionType(str, Enum):
    """Types of sections in a submission packet."""
    COVER_PAGE = "cover_page"
    TABLE_OF_CONTENTS = "table_of_contents"
    EXECUTIVE_SUMMARY = "executive_summary"
    NARRATIVE_RESPONSE = "narrative_response"
    CORRECTIVE_ACTION_PLAN = "corrective_action_plan"
    EVIDENCE_INDEX = "evidence_index"
    EXHIBIT_LIST = "exhibit_list"
    CROSSWALK = "crosswalk"
    SIGNATURE_PAGE = "signature_page"
    APPENDIX = "appendix"


@dataclass
class PacketSection:
    """A section within a submission packet."""
    id: str = field(default_factory=lambda: generate_id("psec"))
    section_type: PacketSectionType = PacketSectionType.NARRATIVE_RESPONSE
    title: str = ""
    order: int = 0
    content: str = ""
    finding_id: str = ""           # Link to finding being addressed
    standard_refs: List[str] = field(default_factory=list)  # Standards referenced
    evidence_refs: List[str] = field(default_factory=list)  # Evidence document IDs
    word_count: int = 0
    page_count: int = 0
    ai_generated: bool = False
    human_reviewed: bool = False
    approved: bool = False
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section_type": self.section_type.value,
            "title": self.title,
            "order": self.order,
            "content": self.content,
            "finding_id": self.finding_id,
            "standard_refs": self.standard_refs,
            "evidence_refs": self.evidence_refs,
            "word_count": self.word_count,
            "page_count": self.page_count,
            "ai_generated": self.ai_generated,
            "human_reviewed": self.human_reviewed,
            "approved": self.approved,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PacketSection":
        return cls(
            id=data.get("id", generate_id("psec")),
            section_type=PacketSectionType(data.get("section_type", "narrative_response")),
            title=data.get("title", ""),
            order=data.get("order", 0),
            content=data.get("content", ""),
            finding_id=data.get("finding_id", ""),
            standard_refs=data.get("standard_refs", []),
            evidence_refs=data.get("evidence_refs", []),
            word_count=data.get("word_count", 0),
            page_count=data.get("page_count", 0),
            ai_generated=data.get("ai_generated", False),
            human_reviewed=data.get("human_reviewed", False),
            approved=data.get("approved", False),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class ExhibitEntry:
    """An exhibit in the submission packet."""
    id: str = field(default_factory=lambda: generate_id("exh"))
    exhibit_number: str = ""       # e.g., "A-1", "B-3"
    title: str = ""
    description: str = ""
    document_id: str = ""          # Link to source document
    file_path: str = ""            # Path in workspace
    standard_refs: List[str] = field(default_factory=list)
    finding_refs: List[str] = field(default_factory=list)
    page_range: str = ""           # e.g., "1-5" or "all"
    file_type: str = ""            # pdf, docx, xlsx, etc.
    included: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "exhibit_number": self.exhibit_number,
            "title": self.title,
            "description": self.description,
            "document_id": self.document_id,
            "file_path": self.file_path,
            "standard_refs": self.standard_refs,
            "finding_refs": self.finding_refs,
            "page_range": self.page_range,
            "file_type": self.file_type,
            "included": self.included,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExhibitEntry":
        return cls(
            id=data.get("id", generate_id("exh")),
            exhibit_number=data.get("exhibit_number", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            document_id=data.get("document_id", ""),
            file_path=data.get("file_path", ""),
            standard_refs=data.get("standard_refs", []),
            finding_refs=data.get("finding_refs", []),
            page_range=data.get("page_range", ""),
            file_type=data.get("file_type", ""),
            included=data.get("included", True),
        )


@dataclass
class ValidationIssue:
    """An issue found during packet validation."""
    issue_type: str = ""           # missing_evidence, missing_standard, low_confidence, etc.
    severity: str = "warning"      # error, warning, info
    message: str = ""
    standard_ref: str = ""
    section_id: str = ""
    finding_id: str = ""
    can_override: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "standard_ref": self.standard_ref,
            "section_id": self.section_id,
            "finding_id": self.finding_id,
            "can_override": self.can_override,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationIssue":
        return cls(
            issue_type=data.get("issue_type", ""),
            severity=data.get("severity", "warning"),
            message=data.get("message", ""),
            standard_ref=data.get("standard_ref", ""),
            section_id=data.get("section_id", ""),
            finding_id=data.get("finding_id", ""),
            can_override=data.get("can_override", True),
        )


@dataclass
class SubmissionPacket:
    """A complete submission packet for accreditation.

    Contains all sections, exhibits, and metadata needed for
    a formal accreditation submission.
    """
    id: str = field(default_factory=lambda: generate_id("pkt"))
    institution_id: str = ""
    submission_type: SubmissionType = SubmissionType.RESPONSE_TO_FINDINGS
    accrediting_body: str = ""
    name: str = ""
    description: str = ""
    status: PacketStatus = PacketStatus.DRAFT
    version: int = 1

    # Sections and exhibits
    sections: List[PacketSection] = field(default_factory=list)
    exhibits: List[ExhibitEntry] = field(default_factory=list)

    # Source data links
    findings_report_id: str = ""
    audit_ids: List[str] = field(default_factory=list)
    checklist_id: str = ""

    # Validation
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    is_valid: bool = False
    validated_at: Optional[str] = None

    # Statistics
    total_sections: int = 0
    sections_approved: int = 0
    total_exhibits: int = 0
    standards_covered: List[str] = field(default_factory=list)
    findings_addressed: int = 0

    # Export paths
    docx_path: str = ""
    pdf_path: str = ""
    zip_path: str = ""

    # Timestamps
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    approved_at: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "submission_type": self.submission_type.value,
            "accrediting_body": self.accrediting_body,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "version": self.version,
            "sections": [s.to_dict() for s in self.sections],
            "exhibits": [e.to_dict() for e in self.exhibits],
            "findings_report_id": self.findings_report_id,
            "audit_ids": self.audit_ids,
            "checklist_id": self.checklist_id,
            "validation_issues": [v.to_dict() for v in self.validation_issues],
            "is_valid": self.is_valid,
            "validated_at": self.validated_at,
            "total_sections": self.total_sections,
            "sections_approved": self.sections_approved,
            "total_exhibits": self.total_exhibits,
            "standards_covered": self.standards_covered,
            "findings_addressed": self.findings_addressed,
            "docx_path": self.docx_path,
            "pdf_path": self.pdf_path,
            "zip_path": self.zip_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
            "submitted_at": self.submitted_at,
            "approved_by": self.approved_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubmissionPacket":
        return cls(
            id=data.get("id", generate_id("pkt")),
            institution_id=data.get("institution_id", ""),
            submission_type=SubmissionType(data.get("submission_type", "response_to_findings")),
            accrediting_body=data.get("accrediting_body", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=PacketStatus(data.get("status", "draft")),
            version=data.get("version", 1),
            sections=[PacketSection.from_dict(s) for s in data.get("sections", [])],
            exhibits=[ExhibitEntry.from_dict(e) for e in data.get("exhibits", [])],
            findings_report_id=data.get("findings_report_id", ""),
            audit_ids=data.get("audit_ids", []),
            checklist_id=data.get("checklist_id", ""),
            validation_issues=[ValidationIssue.from_dict(v) for v in data.get("validation_issues", [])],
            is_valid=data.get("is_valid", False),
            validated_at=data.get("validated_at"),
            total_sections=data.get("total_sections", 0),
            sections_approved=data.get("sections_approved", 0),
            total_exhibits=data.get("total_exhibits", 0),
            standards_covered=data.get("standards_covered", []),
            findings_addressed=data.get("findings_addressed", 0),
            docx_path=data.get("docx_path", ""),
            pdf_path=data.get("pdf_path", ""),
            zip_path=data.get("zip_path", ""),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            approved_at=data.get("approved_at"),
            submitted_at=data.get("submitted_at"),
            approved_by=data.get("approved_by", ""),
        )

    def update_stats(self) -> None:
        """Recalculate packet statistics."""
        self.total_sections = len(self.sections)
        self.sections_approved = sum(1 for s in self.sections if s.approved)
        self.total_exhibits = len([e for e in self.exhibits if e.included])

        # Collect unique standards covered
        all_refs = set()
        for section in self.sections:
            all_refs.update(section.standard_refs)
        for exhibit in self.exhibits:
            all_refs.update(exhibit.standard_refs)
        self.standards_covered = list(all_refs)

        # Count addressed findings
        finding_ids = set()
        for section in self.sections:
            if section.finding_id:
                finding_ids.add(section.finding_id)
        self.findings_addressed = len(finding_ids)

        self.updated_at = now_iso()
