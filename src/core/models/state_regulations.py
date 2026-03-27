"""State Regulatory domain models.

Track state authorizations, catalog requirements compliance,
and program-level licensing board approvals.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


@dataclass
class StateAuthorization:
    """Track state authorization status per institution.

    Represents an institution's authorization to operate in a specific
    state, including SARA reciprocity status and renewal dates.
    """
    id: str = field(default_factory=lambda: generate_id("stauth"))
    institution_id: str = ""
    state_code: str = ""  # e.g., "CA", "TX", "NY"
    authorization_status: str = "pending"  # authorized, pending, restricted, denied
    sara_member: bool = False  # SARA reciprocity
    effective_date: Optional[str] = None
    renewal_date: Optional[str] = None
    contact_agency: Optional[str] = None
    contact_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "state_code": self.state_code,
            "authorization_status": self.authorization_status,
            "sara_member": self.sara_member,
            "effective_date": self.effective_date,
            "renewal_date": self.renewal_date,
            "contact_agency": self.contact_agency,
            "contact_url": self.contact_url,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateAuthorization":
        return cls(
            id=data.get("id", generate_id("stauth")),
            institution_id=data.get("institution_id", ""),
            state_code=data.get("state_code", ""),
            authorization_status=data.get("authorization_status", "pending"),
            sara_member=data.get("sara_member", False),
            effective_date=data.get("effective_date"),
            renewal_date=data.get("renewal_date"),
            contact_agency=data.get("contact_agency"),
            contact_url=data.get("contact_url"),
            notes=data.get("notes"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class StateCatalogRequirement:
    """State-specific catalog disclosure requirements.

    Defines what catalog disclosures are required by each state
    for educational institutions operating there.
    """
    id: str = field(default_factory=lambda: generate_id("streq"))
    state_code: str = ""
    requirement_key: str = ""  # e.g., "hours_of_operation", "refund_policy"
    requirement_name: str = ""
    requirement_text: Optional[str] = None
    category: str = "disclosure"  # disclosure, consumer_info, completion_rates
    required: bool = True
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state_code": self.state_code,
            "requirement_key": self.requirement_key,
            "requirement_name": self.requirement_name,
            "requirement_text": self.requirement_text,
            "category": self.category,
            "required": self.required,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateCatalogRequirement":
        return cls(
            id=data.get("id", generate_id("streq")),
            state_code=data.get("state_code", ""),
            requirement_key=data.get("requirement_key", ""),
            requirement_name=data.get("requirement_name", ""),
            requirement_text=data.get("requirement_text"),
            category=data.get("category", "disclosure"),
            required=data.get("required", True),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class StateCatalogCompliance:
    """Institution compliance with catalog requirements.

    Tracks whether an institution satisfies specific state
    catalog disclosure requirements.
    """
    id: str = field(default_factory=lambda: generate_id("stcomp"))
    institution_id: str = ""
    state_code: str = ""
    requirement_id: str = ""
    status: str = "missing"  # satisfied, partial, missing
    evidence_doc_id: Optional[str] = None
    page_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "state_code": self.state_code,
            "requirement_id": self.requirement_id,
            "status": self.status,
            "evidence_doc_id": self.evidence_doc_id,
            "page_reference": self.page_reference,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateCatalogCompliance":
        return cls(
            id=data.get("id", generate_id("stcomp")),
            institution_id=data.get("institution_id", ""),
            state_code=data.get("state_code", ""),
            requirement_id=data.get("requirement_id", ""),
            status=data.get("status", "missing"),
            evidence_doc_id=data.get("evidence_doc_id"),
            page_reference=data.get("page_reference"),
            notes=data.get("notes"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class StateProgramApproval:
    """Program-level licensing board approvals.

    Tracks whether programs are approved by state licensing boards
    and monitors exam pass rates against requirements.
    """
    id: str = field(default_factory=lambda: generate_id("stprog"))
    institution_id: str = ""
    program_id: str = ""
    state_code: str = ""
    board_name: str = ""
    board_url: Optional[str] = None
    approved: bool = False
    approval_date: Optional[str] = None
    expiration_date: Optional[str] = None
    license_exam: Optional[str] = None
    min_pass_rate: Optional[float] = None
    current_pass_rate: Optional[float] = None
    notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "state_code": self.state_code,
            "board_name": self.board_name,
            "board_url": self.board_url,
            "approved": self.approved,
            "approval_date": self.approval_date,
            "expiration_date": self.expiration_date,
            "license_exam": self.license_exam,
            "min_pass_rate": self.min_pass_rate,
            "current_pass_rate": self.current_pass_rate,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateProgramApproval":
        return cls(
            id=data.get("id", generate_id("stprog")),
            institution_id=data.get("institution_id", ""),
            program_id=data.get("program_id", ""),
            state_code=data.get("state_code", ""),
            board_name=data.get("board_name", ""),
            board_url=data.get("board_url"),
            approved=data.get("approved", False),
            approval_date=data.get("approval_date"),
            expiration_date=data.get("expiration_date"),
            license_exam=data.get("license_exam"),
            min_pass_rate=data.get("min_pass_rate"),
            current_pass_rate=data.get("current_pass_rate"),
            notes=data.get("notes"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class StateReadinessScore:
    """Per-state compliance score.

    Aggregates authorization, catalog, and program approval
    scores into an overall state readiness score.
    """
    state_code: str = ""
    total: int = 0  # 0-100
    authorization_score: int = 0  # 0-100
    catalog_score: int = 0  # 0-100
    program_score: int = 0  # 0-100
    breakdown: Dict[str, Any] = field(default_factory=dict)
    computed_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_code": self.state_code,
            "total": self.total,
            "authorization_score": self.authorization_score,
            "catalog_score": self.catalog_score,
            "program_score": self.program_score,
            "breakdown": self.breakdown,
            "computed_at": self.computed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateReadinessScore":
        return cls(
            state_code=data.get("state_code", ""),
            total=data.get("total", 0),
            authorization_score=data.get("authorization_score", 0),
            catalog_score=data.get("catalog_score", 0),
            program_score=data.get("program_score", 0),
            breakdown=data.get("breakdown", {}),
            computed_at=data.get("computed_at", now_iso()),
        )


@dataclass
class StateSummary:
    """Summary view for list display.

    Provides a compact overview of an institution's compliance
    status in a specific state.
    """
    state_code: str = ""
    state_name: str = ""
    authorization_status: str = "pending"
    sara_member: bool = False
    renewal_date: Optional[str] = None
    catalog_compliance_pct: int = 0  # 0-100
    programs_approved: int = 0
    programs_total: int = 0
    overall_score: int = 0  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_code": self.state_code,
            "state_name": self.state_name,
            "authorization_status": self.authorization_status,
            "sara_member": self.sara_member,
            "renewal_date": self.renewal_date,
            "catalog_compliance_pct": self.catalog_compliance_pct,
            "programs_approved": self.programs_approved,
            "programs_total": self.programs_total,
            "overall_score": self.overall_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSummary":
        return cls(
            state_code=data.get("state_code", ""),
            state_name=data.get("state_name", ""),
            authorization_status=data.get("authorization_status", "pending"),
            sara_member=data.get("sara_member", False),
            renewal_date=data.get("renewal_date"),
            catalog_compliance_pct=data.get("catalog_compliance_pct", 0),
            programs_approved=data.get("programs_approved", 0),
            programs_total=data.get("programs_total", 0),
            overall_score=data.get("overall_score", 0),
        )
