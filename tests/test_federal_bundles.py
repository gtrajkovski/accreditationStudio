"""Tests for federal regulation bundles."""

import pytest
from src.regulatory.federal.bundles import FederalBundleService
from src.regulatory.federal.models import FederalBundle, FederalRequirement


class TestFederalBundleService:
    """Test suite for FederalBundleService."""

    def setup_method(self):
        """Reset bundle cache before each test."""
        FederalBundleService.reload()

    def test_list_bundles_returns_all(self):
        """Verify all bundles are loaded."""
        bundles = FederalBundleService.list_bundles()
        assert len(bundles) >= 7
        ids = [b["id"] for b in bundles]
        assert "title_iv" in ids
        assert "ferpa" in ids
        assert "clery" in ids
        assert "title_ix" in ids
        assert "ada" in ids
        assert "gainful_employment" in ids
        assert "coppa" in ids

    def test_list_bundles_has_required_fields(self):
        """Verify bundle summaries have required fields."""
        bundles = FederalBundleService.list_bundles()
        for bundle in bundles:
            assert "id" in bundle
            assert "name" in bundle
            assert "short_name" in bundle
            assert "requirement_count" in bundle
            assert "applicability_rule" in bundle
            assert bundle["requirement_count"] >= 1

    def test_get_bundle_returns_full_bundle(self):
        """Verify get_bundle returns complete bundle."""
        bundle = FederalBundleService.get_bundle("title_iv")
        assert bundle is not None
        assert isinstance(bundle, FederalBundle)
        assert bundle.id == "title_iv"
        assert bundle.name == "Title IV Student Financial Aid"
        assert len(bundle.requirements) >= 1

    def test_get_bundle_has_requirements(self):
        """Verify bundle has requirements with correct structure."""
        bundle = FederalBundleService.get_bundle("title_iv")
        assert bundle is not None
        assert len(bundle.requirements) >= 1

        req = bundle.requirements[0]
        assert isinstance(req, FederalRequirement)
        assert req.citation.startswith("34 CFR")
        assert req.title
        assert req.description

    def test_get_bundle_not_found(self):
        """Verify get_bundle returns None for unknown ID."""
        bundle = FederalBundleService.get_bundle("nonexistent")
        assert bundle is None

    def test_applicability_title_iv(self):
        """Verify Title IV applicability rule."""
        profile = {"title_iv_eligible": True}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "title_iv" in bundle_ids

        profile_no = {"title_iv_eligible": False}
        bundles_no = FederalBundleService.get_applicable_bundles(profile_no)
        bundle_ids_no = [b.id for b in bundles_no]
        assert "title_iv" not in bundle_ids_no

    def test_applicability_clery(self):
        """Verify Clery Act ties to Title IV eligibility."""
        profile = {"title_iv_eligible": True}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "clery" in bundle_ids

        profile_no = {"title_iv_eligible": False}
        bundles_no = FederalBundleService.get_applicable_bundles(profile_no)
        bundle_ids_no = [b.id for b in bundles_no]
        assert "clery" not in bundle_ids_no

    def test_ferpa_always_applicable(self):
        """Verify FERPA applies to all institutions."""
        profile = {"title_iv_eligible": False}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "ferpa" in bundle_ids

    def test_title_ix_always_applicable(self):
        """Verify Title IX applies to all institutions."""
        profile = {"title_iv_eligible": False, "serves_minors": False}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "title_ix" in bundle_ids

    def test_ada_always_applicable(self):
        """Verify ADA/504 applies to all institutions."""
        profile = {}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "ada" in bundle_ids

    def test_coppa_requires_serves_minors(self):
        """Verify COPPA only applies when serving minors."""
        profile = {"serves_minors": True}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "coppa" in bundle_ids

        profile_no = {"serves_minors": False}
        bundles_no = FederalBundleService.get_applicable_bundles(profile_no)
        bundle_ids_no = [b.id for b in bundles_no]
        assert "coppa" not in bundle_ids_no

    def test_gainful_employment_applicability(self):
        """Verify GE applies to certificate programs or for-profit."""
        profile = {"offers_certificates": True}
        bundles = FederalBundleService.get_applicable_bundles(profile)
        bundle_ids = [b.id for b in bundles]
        assert "gainful_employment" in bundle_ids

        profile_fp = {"for_profit": True}
        bundles_fp = FederalBundleService.get_applicable_bundles(profile_fp)
        bundle_ids_fp = [b.id for b in bundles_fp]
        assert "gainful_employment" in bundle_ids_fp

        profile_no = {"offers_certificates": False, "for_profit": False}
        bundles_no = FederalBundleService.get_applicable_bundles(profile_no)
        bundle_ids_no = [b.id for b in bundles_no]
        assert "gainful_employment" not in bundle_ids_no

    def test_search_requirements(self):
        """Verify search works across bundles."""
        results = FederalBundleService.search_requirements("refund")
        assert len(results) >= 1
        assert any("refund" in r["requirement"]["title"].lower() for r in results)

    def test_search_requirements_by_citation(self):
        """Verify search works with citation reference."""
        results = FederalBundleService.search_requirements("668.43")
        assert len(results) >= 1
        assert any("668.43" in r["requirement"]["citation"] for r in results)

    def test_search_requirements_case_insensitive(self):
        """Verify search is case insensitive."""
        results_lower = FederalBundleService.search_requirements("ferpa")
        results_upper = FederalBundleService.search_requirements("FERPA")
        # Both should return same results (might find FERPA in descriptions)
        assert len(results_lower) == len(results_upper)

    def test_get_requirement(self):
        """Verify getting specific requirement by ID."""
        result = FederalBundleService.get_requirement("title_iv", "t4-001")
        assert result is not None
        assert result["bundle_id"] == "title_iv"
        assert result["requirement"]["id"] == "t4-001"

    def test_get_requirement_not_found(self):
        """Verify get_requirement returns None for unknown."""
        result = FederalBundleService.get_requirement("title_iv", "nonexistent")
        assert result is None

        result = FederalBundleService.get_requirement("nonexistent", "t4-001")
        assert result is None

    def test_get_total_requirements(self):
        """Verify total requirements count."""
        total = FederalBundleService.get_total_requirements()
        # 7 bundles with ~5 requirements each
        assert total >= 25

    def test_bundle_to_dict(self):
        """Verify bundle serialization."""
        bundle = FederalBundleService.get_bundle("ferpa")
        assert bundle is not None

        data = bundle.to_dict()
        assert data["id"] == "ferpa"
        assert data["name"] == "Family Educational Rights and Privacy Act"
        assert "requirements" in data
        assert "requirement_count" in data
        assert data["requirement_count"] == len(data["requirements"])

    def test_requirement_to_dict(self):
        """Verify requirement serialization."""
        bundle = FederalBundleService.get_bundle("ferpa")
        assert bundle is not None

        req = bundle.requirements[0]
        data = req.to_dict()
        assert "id" in data
        assert "citation" in data
        assert "title" in data
        assert "description" in data
        assert "evidence_types" in data
        assert "common_violations" in data


class TestFederalModels:
    """Test federal regulation models."""

    def test_federal_requirement_from_dict(self):
        """Test FederalRequirement.from_dict with filtering."""
        data = {
            "id": "test-001",
            "citation": "34 CFR 123",
            "title": "Test Requirement",
            "description": "A test requirement",
            "evidence_types": ["doc1", "doc2"],
            "unknown_field": "should be ignored",
        }
        req = FederalRequirement.from_dict(data)
        assert req.id == "test-001"
        assert req.citation == "34 CFR 123"
        assert not hasattr(req, "unknown_field")

    def test_federal_bundle_from_dict(self):
        """Test FederalBundle.from_dict with nested requirements."""
        data = {
            "id": "test_bundle",
            "name": "Test Bundle",
            "short_name": "TB",
            "description": "A test bundle",
            "requirements": [
                {
                    "id": "req-001",
                    "citation": "34 CFR 999",
                    "title": "Requirement 1",
                    "description": "First requirement",
                }
            ],
        }
        bundle = FederalBundle.from_dict(data)
        assert bundle.id == "test_bundle"
        assert len(bundle.requirements) == 1
        assert bundle.requirements[0].id == "req-001"
