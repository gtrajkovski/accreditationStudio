"""COE Accreditor Package.

Council on Occupational Education (COE)
- Type: Institutional (national)
- Scope: Career and technical education, non-degree through associate degrees
- Recognition: USDE
"""

from src.accreditors.coe.sources import (
    get_sources,
    get_source,
    get_section_structure,
    get_criteria_structure,
    get_fetch_urls,
    SOURCES,
    SECTION_STRUCTURE,
    CRITERIA_STRUCTURE,
)
from src.accreditors.coe.parser import (
    parse_standards,
    parse_checklist,
    COEParser,
)

__all__ = [
    "get_sources",
    "get_source",
    "get_section_structure",
    "get_criteria_structure",
    "get_fetch_urls",
    "SOURCES",
    "SECTION_STRUCTURE",
    "CRITERIA_STRUCTURE",
    "parse_standards",
    "parse_checklist",
    "COEParser",
]
