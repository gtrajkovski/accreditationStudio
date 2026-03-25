"""Standards Harvester package.

Provides three harvester types for fetching standards:
- WebHarvester: Scrape standards from accreditor websites
- PdfHarvester: Parse standards from PDF files
- ManualHarvester: Accept manually uploaded standards text
"""

from src.harvesters.base_harvester import HarvesterType, BaseHarvester
from src.harvesters.web_harvester import WebHarvester
from src.harvesters.pdf_harvester import PdfHarvester
from src.harvesters.manual_harvester import ManualHarvester


def create_harvester(harvester_type: HarvesterType) -> BaseHarvester:
    """Factory function to create harvester instances.

    Args:
        harvester_type: Type of harvester to create

    Returns:
        Harvester instance

    Raises:
        ValueError: If harvester_type is invalid
    """
    if harvester_type == HarvesterType.WEB_SCRAPER:
        return WebHarvester()
    elif harvester_type == HarvesterType.PDF_PARSER:
        return PdfHarvester()
    elif harvester_type == HarvesterType.MANUAL_UPLOAD:
        return ManualHarvester()
    else:
        raise ValueError(f"Unknown harvester type: {harvester_type}")


__all__ = [
    "HarvesterType",
    "BaseHarvester",
    "WebHarvester",
    "PdfHarvester",
    "ManualHarvester",
    "create_harvester",
]
