"""Institution and Program domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from src.core.models.helpers import generate_id, now_iso
from src.core.models.enums import (
    AccreditingBody,
    CredentialLevel,
    Modality,
)

if TYPE_CHECKING:
    from src.core.models.document import Document


@dataclass
class Program:
    """A program offered by an institution."""
    id: str = field(default_factory=lambda: generate_id("prog"))
    name_en: str = ""
    name_es: Optional[str] = None
    credential_level: CredentialLevel = CredentialLevel.CERTIFICATE
    total_credits: int = 0
    total_cost: float = 0.0
    duration_months: int = 0
    academic_periods: int = 0
    cost_per_period: float = 0.0
    book_cost: float = 0.0
    other_costs: Dict[str, float] = field(default_factory=dict)
    modality: Modality = Modality.ON_GROUND
    licensure_required: bool = False
    licensure_exam: Optional[str] = None
    professional_body: Optional[str] = None
    programmatic_accreditor: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name_en": self.name_en,
            "name_es": self.name_es,
            "credential_level": self.credential_level.value,
            "total_credits": self.total_credits,
            "total_cost": self.total_cost,
            "duration_months": self.duration_months,
            "academic_periods": self.academic_periods,
            "cost_per_period": self.cost_per_period,
            "book_cost": self.book_cost,
            "other_costs": self.other_costs,
            "modality": self.modality.value,
            "licensure_required": self.licensure_required,
            "licensure_exam": self.licensure_exam,
            "professional_body": self.professional_body,
            "programmatic_accreditor": self.programmatic_accreditor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Program":
        """Deserialize from dictionary, filtering unknown fields."""
        return cls(
            id=data.get("id", generate_id("prog")),
            name_en=data.get("name_en", ""),
            name_es=data.get("name_es"),
            credential_level=CredentialLevel(data.get("credential_level", "certificate")),
            total_credits=data.get("total_credits", 0),
            total_cost=data.get("total_cost", 0.0),
            duration_months=data.get("duration_months", 0),
            academic_periods=data.get("academic_periods", 0),
            cost_per_period=data.get("cost_per_period", 0.0),
            book_cost=data.get("book_cost", 0.0),
            other_costs=data.get("other_costs", {}),
            modality=Modality(data.get("modality", "on_ground")),
            licensure_required=data.get("licensure_required", False),
            licensure_exam=data.get("licensure_exam"),
            professional_body=data.get("professional_body"),
            programmatic_accreditor=data.get("programmatic_accreditor"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class Institution:
    """An educational institution being managed."""
    id: str = field(default_factory=lambda: generate_id("inst"))
    name: str = ""
    accrediting_body: AccreditingBody = AccreditingBody.ACCSC
    opeid: str = ""
    website: str = ""
    school_ids: Dict[str, str] = field(default_factory=dict)
    campuses: List[Dict[str, Any]] = field(default_factory=list)
    state_authority: Dict[str, Any] = field(default_factory=dict)
    federal_characteristics: Dict[str, bool] = field(default_factory=dict)
    state_code: str = ""
    programs: List[Program] = field(default_factory=list)
    documents: List["Document"] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "accrediting_body": self.accrediting_body.value,
            "opeid": self.opeid,
            "website": self.website,
            "school_ids": self.school_ids,
            "campuses": self.campuses,
            "state_authority": self.state_authority,
            "federal_characteristics": self.federal_characteristics,
            "state_code": self.state_code,
            "programs": [p.to_dict() for p in self.programs],
            "documents": [d.to_dict() for d in self.documents],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Institution":
        """Deserialize from dictionary."""
        # Import here to avoid circular imports
        from src.core.models.document import Document

        return cls(
            id=data.get("id", generate_id("inst")),
            name=data.get("name", ""),
            accrediting_body=AccreditingBody(data.get("accrediting_body", "ACCSC")),
            opeid=data.get("opeid", ""),
            website=data.get("website", ""),
            school_ids=data.get("school_ids", {}),
            campuses=data.get("campuses", []),
            state_authority=data.get("state_authority", {}),
            federal_characteristics=data.get("federal_characteristics", {}),
            state_code=data.get("state_code", ""),
            programs=[Program.from_dict(p) for p in data.get("programs", [])],
            documents=[Document.from_dict(d) for d in data.get("documents", [])],
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
