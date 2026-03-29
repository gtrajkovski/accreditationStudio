import pytest
from src.accreditors.registry import AccreditorRegistry


def test_registry_discovers_packages():
    """Verify all packages are discovered."""
    packages = AccreditorRegistry.list_all()
    codes = [p.code for p in packages]
    assert "ACCSC" in codes
    assert len(packages) >= 5


def test_accsc_manifest_valid():
    """Verify ACCSC manifest has required fields."""
    manifest = AccreditorRegistry.get("ACCSC")
    assert manifest is not None
    assert manifest.code == "ACCSC"
    assert manifest.type == "institutional"
    assert manifest.name == "Accrediting Commission of Career Schools and Colleges"


def test_accsc_package_has_sources():
    """Verify ACCSC package returns sources."""
    sources_module = AccreditorRegistry.get_sources_module("ACCSC")
    assert sources_module is not None
    assert hasattr(sources_module, "get_sources")
    sources = sources_module.get_sources()
    assert len(sources) >= 1


def test_unknown_accreditor_returns_none():
    """Verify unknown code returns None."""
    manifest = AccreditorRegistry.get("UNKNOWN")
    assert manifest is None


def test_all_required_accreditors_present():
    """Verify all 5 required accreditors have manifests."""
    required_codes = ["ACCSC", "SACSCOC", "HLC", "ABHES", "COE"]
    packages = AccreditorRegistry.list_all()
    actual_codes = [p.code for p in packages]

    for code in required_codes:
        assert code in actual_codes, f"Missing required accreditor: {code}"


def test_sacscoc_manifest():
    """Verify SACSCOC manifest is valid."""
    manifest = AccreditorRegistry.get("SACSCOC")
    assert manifest is not None
    assert manifest.code == "SACSCOC"
    assert manifest.type == "institutional"
    assert manifest.scope == "regional"


def test_hlc_manifest():
    """Verify HLC manifest is valid."""
    manifest = AccreditorRegistry.get("HLC")
    assert manifest is not None
    assert manifest.code == "HLC"
    assert manifest.type == "institutional"
    assert manifest.scope == "regional"


def test_abhes_manifest():
    """Verify ABHES manifest is valid."""
    manifest = AccreditorRegistry.get("ABHES")
    assert manifest is not None
    assert manifest.code == "ABHES"
    assert manifest.type == "programmatic"
    assert manifest.scope == "national"
