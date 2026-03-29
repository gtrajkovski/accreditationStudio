"""Federal bundle loading and applicability service."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.regulatory.federal.models import FederalBundle


class FederalBundleService:
    """Service for loading and querying federal regulation bundles."""

    _bundles: Dict[str, FederalBundle] = {}
    _loaded: bool = False

    @classmethod
    def _load_bundles(cls) -> None:
        """Load all bundle JSON files."""
        if cls._loaded:
            return

        bundle_dir = Path(__file__).parent
        for json_file in bundle_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                bundle = FederalBundle.from_dict(data)
                cls._bundles[bundle.id] = bundle

        cls._loaded = True

    @classmethod
    def reload(cls) -> None:
        """Force reload of all bundles (useful for testing)."""
        cls._bundles = {}
        cls._loaded = False
        cls._load_bundles()

    @classmethod
    def list_bundles(cls) -> List[Dict[str, Any]]:
        """Return all bundles as summary dicts."""
        cls._load_bundles()
        return [
            {
                "id": b.id,
                "name": b.name,
                "short_name": b.short_name,
                "description": b.description,
                "requirement_count": len(b.requirements),
                "applicability_rule": b.applicability_rule,
                "enforcement_agency": b.enforcement_agency,
            }
            for b in cls._bundles.values()
        ]

    @classmethod
    def get_bundle(cls, bundle_id: str) -> Optional[FederalBundle]:
        """Get full bundle by ID."""
        cls._load_bundles()
        return cls._bundles.get(bundle_id)

    @classmethod
    def get_all_bundles(cls) -> List[FederalBundle]:
        """Get all bundles as full objects."""
        cls._load_bundles()
        return list(cls._bundles.values())

    @classmethod
    def get_applicable_bundles(
        cls, institution_profile: Dict[str, Any]
    ) -> List[FederalBundle]:
        """Return bundles applicable to institution based on profile.

        Args:
            institution_profile: Dict with keys like:
                - title_iv_eligible: bool
                - serves_minors: bool
                - for_profit: bool
                - offers_certificates: bool
                - modality: str ("ground", "online", "hybrid")

        Returns:
            List of applicable FederalBundle objects.
        """
        cls._load_bundles()
        applicable = []

        for bundle in cls._bundles.values():
            if cls._evaluate_applicability(bundle.applicability_rule, institution_profile):
                applicable.append(bundle)

        return applicable

    @classmethod
    def _evaluate_applicability(cls, rule: str, profile: Dict[str, Any]) -> bool:
        """Safely evaluate applicability rule against profile.

        The rule is a simple Python expression like:
            "institution.title_iv_eligible == True"
            "True"
            "institution.serves_minors == True"

        Args:
            rule: Python expression string
            profile: Dict of institution attributes

        Returns:
            True if the rule evaluates to True, False otherwise.
        """
        if not rule or rule == "True":
            return True

        # Create a simple namespace object from the profile dict
        class Namespace:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

            def __getattr__(self, name):
                # Return False for any missing attribute (safe default)
                return False

        context = {"institution": Namespace(**profile)}

        try:
            # Evaluate with restricted builtins for safety
            return bool(eval(rule, {"__builtins__": {}}, context))
        except Exception:
            # If evaluation fails, default to not applicable
            return False

    @classmethod
    def search_requirements(cls, query: str) -> List[Dict[str, Any]]:
        """Search across all bundles for matching requirements.

        Args:
            query: Search term to match against title, description, or citation.

        Returns:
            List of dicts with bundle info and matching requirement.
        """
        cls._load_bundles()
        results = []
        query_lower = query.lower()

        for bundle in cls._bundles.values():
            for req in bundle.requirements:
                if (
                    query_lower in req.title.lower()
                    or query_lower in req.description.lower()
                    or query_lower in req.citation.lower()
                ):
                    results.append(
                        {
                            "bundle_id": bundle.id,
                            "bundle_name": bundle.short_name,
                            "requirement": req.to_dict(),
                        }
                    )

        return results

    @classmethod
    def get_requirement(cls, bundle_id: str, requirement_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific requirement by bundle and requirement ID.

        Args:
            bundle_id: The bundle containing the requirement
            requirement_id: The requirement ID

        Returns:
            Requirement dict with bundle context, or None if not found.
        """
        bundle = cls.get_bundle(bundle_id)
        if not bundle:
            return None

        for req in bundle.requirements:
            if req.id == requirement_id:
                return {
                    "bundle_id": bundle.id,
                    "bundle_name": bundle.short_name,
                    "requirement": req.to_dict(),
                }

        return None

    @classmethod
    def get_total_requirements(cls) -> int:
        """Get total count of requirements across all bundles."""
        cls._load_bundles()
        return sum(len(b.requirements) for b in cls._bundles.values())
