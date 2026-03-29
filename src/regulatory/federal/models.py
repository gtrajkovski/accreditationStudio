"""Federal regulation models."""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class FederalRequirement:
    """A specific federal requirement within a bundle."""

    id: str
    citation: str  # e.g., "34 CFR 668.43(a)(1)"
    title: str
    description: str
    evidence_types: List[str] = field(default_factory=list)
    common_violations: List[str] = field(default_factory=list)
    penalty_range: str = ""
    effective_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "citation": self.citation,
            "title": self.title,
            "description": self.description,
            "evidence_types": self.evidence_types,
            "common_violations": self.common_violations,
            "penalty_range": self.penalty_range,
            "effective_date": self.effective_date,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FederalRequirement":
        """Create from dictionary, filtering unknown fields."""
        known_fields = {
            "id",
            "citation",
            "title",
            "description",
            "evidence_types",
            "common_violations",
            "penalty_range",
            "effective_date",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class FederalBundle:
    """A federal regulation bundle with applicability rules."""

    id: str
    name: str
    short_name: str
    description: str
    citations: List[str] = field(default_factory=list)
    applicability_rule: str = ""  # Python expression
    requirements: List[FederalRequirement] = field(default_factory=list)
    last_updated: str = ""
    effective_date: str = ""
    enforcement_agency: str = ""
    penalty_authority: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "description": self.description,
            "citations": self.citations,
            "applicability_rule": self.applicability_rule,
            "requirements": [r.to_dict() for r in self.requirements],
            "last_updated": self.last_updated,
            "effective_date": self.effective_date,
            "enforcement_agency": self.enforcement_agency,
            "penalty_authority": self.penalty_authority,
            "requirement_count": len(self.requirements),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FederalBundle":
        """Create from dictionary, parsing nested requirements."""
        requirements = [
            FederalRequirement.from_dict(r) for r in data.get("requirements", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            short_name=data["short_name"],
            description=data.get("description", ""),
            citations=data.get("citations", []),
            applicability_rule=data.get("applicability_rule", ""),
            requirements=requirements,
            last_updated=data.get("last_updated", ""),
            effective_date=data.get("effective_date", ""),
            enforcement_agency=data.get("enforcement_agency", ""),
            penalty_authority=data.get("penalty_authority", ""),
        )
