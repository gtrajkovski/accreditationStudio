# Federal regulations library
"""
Federal regulation bundles with applicability rules.

Provides structured federal requirements that can be queried
based on institution profile (e.g., Title IV eligibility,
serves minors, etc.).
"""

from src.regulatory.federal.models import FederalBundle, FederalRequirement
from src.regulatory.federal.bundles import FederalBundleService

__all__ = ["FederalBundle", "FederalRequirement", "FederalBundleService"]
