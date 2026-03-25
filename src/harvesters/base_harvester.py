"""Base harvester class for standards fetching.

Defines the abstract interface for all harvester types.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any


class HarvesterType(str, Enum):
    """Enum for harvester source types."""
    WEB_SCRAPER = "web_scrape"
    PDF_PARSER = "pdf_parse"
    MANUAL_UPLOAD = "manual_upload"


class BaseHarvester(ABC):
    """Abstract base class for standards harvesters.

    All harvester implementations must extend this class and implement
    the fetch() method.
    """

    @abstractmethod
    def fetch(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch standards content from source.

        Args:
            source_config: Configuration dict with source-specific parameters.
                          Expected keys vary by harvester type:
                          - WebHarvester: {"url": str}
                          - PdfHarvester: {"file_path": str} or {"url": str}
                          - ManualHarvester: {"text": str, "notes": str (optional)}

        Returns:
            Dictionary with:
                - "text": str (extracted standards text)
                - "metadata": dict (source-specific metadata)

        Raises:
            ValueError: If required config parameters are missing or invalid
        """
        pass
