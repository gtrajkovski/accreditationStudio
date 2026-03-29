from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class StandardsSource:
    """A source URL for standards documents."""
    url: str
    format: str  # pdf, html, docx
    name: str
    fetch_cadence: str = "monthly"


@dataclass
class StandardsTree:
    """Parsed standards hierarchy."""
    accreditor: str
    version: str
    parsed_at: str
    sections: List[Dict[str, Any]]
    total_standards: int


class AccreditorPackage(ABC):
    """Base class for accreditor packages."""

    @property
    @abstractmethod
    def manifest(self) -> Dict[str, Any]:
        """Return package manifest."""
        pass

    @abstractmethod
    def get_sources(self) -> List[StandardsSource]:
        """Return list of standards source URLs."""
        pass

    @abstractmethod
    def parse_standards(self, raw_path: str) -> StandardsTree:
        """Parse raw standards file into structured tree."""
        pass

    def get_crosswalk_seeds(self) -> Optional[Dict[str, Any]]:
        """Return optional crosswalk mappings to federal/state requirements."""
        return None

    def get_fetch_cadence(self) -> str:
        """Return fetch cadence: daily, weekly, monthly."""
        return self.manifest.get("fetch_cadence", "monthly")

    @property
    def code(self) -> str:
        """Return accreditor code."""
        return self.manifest["id"]

    @property
    def name(self) -> str:
        """Return accreditor full name."""
        return self.manifest["name"]
