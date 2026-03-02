"""ACCSC Accreditor Package.

Accrediting Commission of Career Schools and Colleges (ACCSC)
- Type: Institutional (national)
- Scope: Career colleges, certificates through master's degrees
- Recognition: USDE
"""

from src.accreditors.accsc.sources import (
    get_sources,
    get_source,
    get_section_structure,
    get_fetch_urls,
    SOURCES,
    SECTION_STRUCTURE,
)
from src.accreditors.accsc.parser import (
    parse_standards,
    parse_checklist,
    ACCSCParser,
)

__all__ = [
    "get_sources",
    "get_source",
    "get_section_structure",
    "get_fetch_urls",
    "SOURCES",
    "SECTION_STRUCTURE",
    "parse_standards",
    "parse_checklist",
    "ACCSCParser",
]
