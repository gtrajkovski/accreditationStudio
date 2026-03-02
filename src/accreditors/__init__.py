"""Accreditor Package System for AccreditationStudio.

Each accreditor has a package with:
- manifest.json: metadata (id, name, type, scope)
- sources.py: official URLs and fetch configuration
- parser.py: normalize standards into StandardsTree schema
"""

from src.accreditors.registry import AccreditorRegistry, get_accreditor, list_accreditors

__all__ = ["AccreditorRegistry", "get_accreditor", "list_accreditors"]
