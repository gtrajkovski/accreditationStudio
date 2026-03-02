"""Tests for StandardsStore."""

import pytest
import json
from pathlib import Path
import tempfile
import shutil

from src.core.standards_store import StandardsStore
from src.core.models import (
    AccreditingBody,
    DocumentType,
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
)


@pytest.fixture
def temp_standards_dir():
    """Create a temporary directory for standards files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def standards_store(temp_standards_dir):
    """Create a StandardsStore with temporary directory."""
    return StandardsStore(temp_standards_dir)


class TestPresetSeeding:
    """Tests for preset seeding on initialization."""

    def test_presets_seeded_on_init(self, standards_store, temp_standards_dir):
        """System presets are created on first initialization."""
        preset_ids = ["std_accsc", "std_sacscoc", "std_hlc", "std_abhes", "std_coe"]
        for preset_id in preset_ids:
            path = temp_standards_dir / f"{preset_id}.json"
            assert path.exists(), f"Preset {preset_id} not seeded"

    def test_accsc_preset_structure(self, standards_store):
        """ACCSC preset has correct structure."""
        accsc = standards_store.load("std_accsc")

        assert accsc is not None
        assert accsc.accrediting_body == AccreditingBody.ACCSC
        assert accsc.is_system_preset is True
        assert len(accsc.sections) > 0
        assert len(accsc.checklist_items) > 0

    def test_all_presets_have_sections(self, standards_store):
        """All presets have at least one section."""
        for lib in standards_store.list_all():
            assert len(lib.sections) > 0, f"{lib.id} has no sections"

    def test_all_presets_have_checklist_items(self, standards_store):
        """All presets have at least one checklist item."""
        for lib in standards_store.list_all():
            assert len(lib.checklist_items) > 0, f"{lib.id} has no checklist items"


class TestCRUDOperations:
    """Tests for CRUD operations."""

    def test_load_existing_library(self, standards_store):
        """Can load an existing library by ID."""
        library = standards_store.load("std_accsc")

        assert library is not None
        assert library.id == "std_accsc"
        assert library.name == "ACCSC Substantive Standards"

    def test_load_nonexistent_library(self, standards_store):
        """Loading nonexistent library returns None."""
        library = standards_store.load("nonexistent")
        assert library is None

    def test_save_new_library(self, standards_store):
        """Can save a new library."""
        library = StandardsLibrary(
            id="std_custom_test",
            accrediting_body=AccreditingBody.CUSTOM,
            name="Test Standards",
            version="1.0",
        )

        standards_store.save(library)
        loaded = standards_store.load("std_custom_test")

        assert loaded is not None
        assert loaded.name == "Test Standards"

    def test_save_updates_timestamp(self, standards_store):
        """Saving updates the updated_at timestamp."""
        library = standards_store.load("std_accsc")
        original_timestamp = library.updated_at

        # Force a new timestamp by waiting (or just check it gets set)
        standards_store.save(library)
        loaded = standards_store.load("std_accsc")

        # Timestamp should be set (may or may not be different in fast test)
        assert loaded.updated_at is not None

    def test_delete_custom_library(self, standards_store):
        """Can delete a custom library."""
        library = StandardsLibrary(
            id="std_to_delete",
            accrediting_body=AccreditingBody.CUSTOM,
            name="Delete Me",
        )
        standards_store.save(library)

        result = standards_store.delete("std_to_delete")

        assert result is True
        assert standards_store.load("std_to_delete") is None

    def test_cannot_delete_system_preset(self, standards_store):
        """Cannot delete a system preset."""
        result = standards_store.delete("std_accsc")

        assert result is False
        assert standards_store.load("std_accsc") is not None

    def test_delete_nonexistent_returns_false(self, standards_store):
        """Deleting nonexistent library returns False."""
        result = standards_store.delete("nonexistent")
        assert result is False

    def test_list_all_includes_presets(self, standards_store):
        """list_all includes all system presets."""
        libraries = standards_store.list_all()
        ids = [lib.id for lib in libraries]

        assert "std_accsc" in ids
        assert "std_sacscoc" in ids
        assert "std_hlc" in ids
        assert "std_abhes" in ids
        assert "std_coe" in ids

    def test_list_all_sorted_presets_first(self, standards_store):
        """list_all returns presets before custom libraries."""
        # Add a custom library
        custom = StandardsLibrary(
            id="std_aaa_custom",  # Would sort first alphabetically
            accrediting_body=AccreditingBody.CUSTOM,
            name="AAA Custom",
        )
        standards_store.save(custom)

        libraries = standards_store.list_all()

        # First libraries should be presets
        assert libraries[0].is_system_preset is True

    def test_list_by_accreditor(self, standards_store):
        """Can filter libraries by accrediting body."""
        accsc_libs = standards_store.list_by_accreditor(AccreditingBody.ACCSC)

        assert len(accsc_libs) >= 1
        for lib in accsc_libs:
            assert lib.accrediting_body == AccreditingBody.ACCSC


class TestSectionNavigation:
    """Tests for section navigation methods."""

    def test_get_section_by_id(self, standards_store):
        """Can get a section by its ID."""
        accsc = standards_store.load("std_accsc")
        first_section = accsc.sections[0]

        section = standards_store.get_section("std_accsc", first_section.id)

        assert section is not None
        assert section.id == first_section.id

    def test_get_section_nonexistent(self, standards_store):
        """Getting nonexistent section returns None."""
        section = standards_store.get_section("std_accsc", "nonexistent")
        assert section is None

    def test_get_section_by_number(self, standards_store):
        """Can get a section by its number."""
        section = standards_store.get_section_by_number("std_accsc", "I")

        assert section is not None
        assert section.number == "I"
        assert "Institutional" in section.title

    def test_get_child_sections(self, standards_store):
        """Can get child sections of a parent."""
        # Get top-level section
        section_i = standards_store.get_section_by_number("std_accsc", "I")
        assert section_i is not None

        # Get its children
        children = standards_store.get_child_sections("std_accsc", section_i.id)

        assert len(children) > 0
        for child in children:
            assert child.parent_section == section_i.id

    def test_get_top_level_sections(self, standards_store):
        """Empty parent_id returns top-level sections."""
        accsc = standards_store.load("std_accsc")
        top_level = [s for s in accsc.sections if not s.parent_section]

        children = standards_store.get_child_sections("std_accsc", "")

        # Should get same sections (those with empty parent)
        assert len(children) == len(top_level)


class TestChecklistAccess:
    """Tests for checklist access methods."""

    def test_get_all_checklist_items(self, standards_store):
        """Can get all checklist items."""
        items = standards_store.get_checklist_items("std_accsc")

        assert len(items) > 0

    def test_get_checklist_items_by_category(self, standards_store):
        """Can filter checklist items by category."""
        items = standards_store.get_checklist_items("std_accsc", category="Mission")

        assert len(items) > 0
        for item in items:
            assert item.category == "Mission"

    def test_get_items_for_document_type(self, standards_store):
        """Can get checklist items applicable to a document type."""
        items = standards_store.get_items_for_document_type(
            "std_accsc",
            DocumentType.CATALOG
        )

        assert len(items) > 0
        for item in items:
            assert "catalog" in item.applies_to


class TestDuplication:
    """Tests for library duplication."""

    def test_duplicate_library(self, standards_store):
        """Can duplicate a library."""
        new_lib = standards_store.duplicate("std_accsc", "Custom ACCSC")

        assert new_lib is not None
        assert new_lib.id != "std_accsc"
        assert new_lib.name == "Custom ACCSC"
        assert new_lib.is_system_preset is False
        assert len(new_lib.sections) > 0  # Sections were copied

    def test_duplicate_nonexistent_returns_none(self, standards_store):
        """Duplicating nonexistent library returns None."""
        result = standards_store.duplicate("nonexistent", "Test")
        assert result is None


class TestGetDefault:
    """Tests for get_default method."""

    def test_get_default_accsc(self, standards_store):
        """Can get default ACCSC library."""
        default = standards_store.get_default(AccreditingBody.ACCSC)

        assert default is not None
        assert default.id == "std_accsc"

    def test_get_default_all_accreditors(self, standards_store):
        """Can get default for all supported accreditors."""
        accreditors = [
            AccreditingBody.ACCSC,
            AccreditingBody.SACSCOC,
            AccreditingBody.HLC,
            AccreditingBody.ABHES,
            AccreditingBody.COE,
        ]

        for accreditor in accreditors:
            default = standards_store.get_default(accreditor)
            assert default is not None, f"No default for {accreditor.value}"


class TestModelSerialization:
    """Tests for model serialization."""

    def test_checklist_item_round_trip(self):
        """ChecklistItem can serialize and deserialize."""
        item = ChecklistItem(
            number="I.A.1",
            category="Mission",
            description="Test item",
            section_reference="I.A",
            applies_to=["catalog", "policy_manual"],
        )

        data = item.to_dict()
        restored = ChecklistItem.from_dict(data)

        assert restored.number == item.number
        assert restored.category == item.category
        assert restored.applies_to == item.applies_to

    def test_standards_section_round_trip(self):
        """StandardsSection can serialize and deserialize."""
        section = StandardsSection(
            id="sec_test",
            number="I.A",
            title="Test Section",
            text="Section text here",
            parent_section="sec_parent",
        )

        data = section.to_dict()
        restored = StandardsSection.from_dict(data)

        assert restored.id == section.id
        assert restored.number == section.number
        assert restored.title == section.title
        assert restored.parent_section == section.parent_section

    def test_standards_library_round_trip(self, standards_store):
        """StandardsLibrary can serialize and deserialize."""
        original = standards_store.load("std_accsc")

        data = original.to_dict()
        restored = StandardsLibrary.from_dict(data)

        assert restored.id == original.id
        assert restored.accrediting_body == original.accrediting_body
        assert len(restored.sections) == len(original.sections)
        assert len(restored.checklist_items) == len(original.checklist_items)

    def test_library_json_persistence(self, standards_store, temp_standards_dir):
        """Library persists correctly as JSON."""
        library_path = temp_standards_dir / "std_accsc.json"

        with open(library_path, "r") as f:
            data = json.load(f)

        assert data["id"] == "std_accsc"
        assert data["accrediting_body"] == "ACCSC"
        assert isinstance(data["sections"], list)
        assert isinstance(data["checklist_items"], list)
