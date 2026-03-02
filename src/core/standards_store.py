"""Standards library storage and management.

Handles persistence of accreditation standards libraries to the standards/ directory.
Seeds system presets (ACCSC, SACSCOC, HLC, etc.) on first run.
"""

import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from src.core.models import (
    AccreditingBody,
    DocumentType,
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
    now_iso,
)


class StandardsStore:
    """Manages accreditation standards libraries on disk.

    Standards are stored as JSON files in the standards/ directory.
    System presets are seeded on first initialization.
    """

    def __init__(self, standards_dir: Path = Path("standards")):
        """Initialize the standards store.

        Args:
            standards_dir: Directory to store standards JSON files.
        """
        self.standards_dir = standards_dir
        self.standards_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_system_presets()

    def _ensure_system_presets(self) -> None:
        """Seed system presets if they don't exist."""
        presets = self._get_system_presets()
        for preset in presets:
            path = self.standards_dir / f"{preset.id}.json"
            if not path.exists():
                self.save(preset)

    def _get_system_presets(self) -> List[StandardsLibrary]:
        """Return all system preset libraries."""
        return [
            self._accsc_preset(),
            self._sacscoc_preset(),
            self._hlc_preset(),
            self._abhes_preset(),
            self._coe_preset(),
        ]

    def _accsc_preset(self) -> StandardsLibrary:
        """ACCSC (Accrediting Commission of Career Schools and Colleges) preset."""
        sections = [
            # Section I: Institutional Criteria
            StandardsSection(id="sec_accsc_i", number="I", title="Institutional Criteria", text="", parent_section=""),
            StandardsSection(id="sec_accsc_i_a", number="I.A", title="Mission", text="", parent_section="sec_accsc_i"),
            StandardsSection(id="sec_accsc_i_b", number="I.B", title="Institutional Assessment", text="", parent_section="sec_accsc_i"),
            StandardsSection(id="sec_accsc_i_c", number="I.C", title="Financial Resources", text="", parent_section="sec_accsc_i"),
            StandardsSection(id="sec_accsc_i_d", number="I.D", title="Organization", text="", parent_section="sec_accsc_i"),
            StandardsSection(id="sec_accsc_i_e", number="I.E", title="Administration", text="", parent_section="sec_accsc_i"),
            StandardsSection(id="sec_accsc_i_f", number="I.F", title="Facilities, Equipment, and Supplies", text="", parent_section="sec_accsc_i"),

            # Section II: Program Criteria
            StandardsSection(id="sec_accsc_ii", number="II", title="Program Criteria", text="", parent_section=""),
            StandardsSection(id="sec_accsc_ii_a", number="II.A", title="Program Development", text="", parent_section="sec_accsc_ii"),
            StandardsSection(id="sec_accsc_ii_b", number="II.B", title="Program Delivery", text="", parent_section="sec_accsc_ii"),
            StandardsSection(id="sec_accsc_ii_c", number="II.C", title="Educational Resources", text="", parent_section="sec_accsc_ii"),
            StandardsSection(id="sec_accsc_ii_d", number="II.D", title="Faculty Qualifications and Conditions of Employment", text="", parent_section="sec_accsc_ii"),
            StandardsSection(id="sec_accsc_ii_e", number="II.E", title="Distance Education", text="", parent_section="sec_accsc_ii"),

            # Section III: Student Services
            StandardsSection(id="sec_accsc_iii", number="III", title="Student Services", text="", parent_section=""),
            StandardsSection(id="sec_accsc_iii_a", number="III.A", title="Student Satisfaction and Complaints", text="", parent_section="sec_accsc_iii"),
            StandardsSection(id="sec_accsc_iii_b", number="III.B", title="Student Support Services", text="", parent_section="sec_accsc_iii"),
        ]

        checklist_items = [
            # Mission
            ChecklistItem(number="I.A.1", category="Mission", description="School has a written mission statement", section_reference="I.A", applies_to=["catalog", "policy_manual"]),
            ChecklistItem(number="I.A.2", category="Mission", description="Mission statement is published in catalog", section_reference="I.A", applies_to=["catalog"]),
            ChecklistItem(number="I.A.3", category="Mission", description="School objectives are consistent with mission", section_reference="I.A", applies_to=["catalog", "self_evaluation_report"]),

            # Institutional Assessment
            ChecklistItem(number="I.B.1", category="Assessment", description="School has a documented assessment plan", section_reference="I.B", applies_to=["policy_manual", "self_evaluation_report"]),
            ChecklistItem(number="I.B.2", category="Assessment", description="Student achievement rates are tracked", section_reference="I.B", applies_to=["self_evaluation_report"]),

            # Financial Resources
            ChecklistItem(number="I.C.1", category="Financial", description="Tuition and fees are clearly disclosed", section_reference="I.C", applies_to=["catalog", "enrollment_agreement"]),
            ChecklistItem(number="I.C.2", category="Financial", description="Refund policy is published", section_reference="I.C", applies_to=["catalog", "enrollment_agreement"]),

            # Program Development
            ChecklistItem(number="II.A.1", category="Program", description="Program objectives are clearly stated", section_reference="II.A", applies_to=["catalog"]),
            ChecklistItem(number="II.A.2", category="Program", description="Clock hours/credit hours are documented", section_reference="II.A", applies_to=["catalog"]),

            # Faculty
            ChecklistItem(number="II.D.1", category="Faculty", description="Faculty qualifications meet requirements", section_reference="II.D", applies_to=["faculty_handbook"]),
            ChecklistItem(number="II.D.2", category="Faculty", description="Faculty credentials are documented", section_reference="II.D", applies_to=["faculty_handbook"]),

            # Student Services
            ChecklistItem(number="III.A.1", category="Student Services", description="Complaint procedure is published", section_reference="III.A", applies_to=["catalog", "student_handbook"]),
            ChecklistItem(number="III.B.1", category="Student Services", description="Academic advising is available", section_reference="III.B", applies_to=["catalog"]),
        ]

        return StandardsLibrary(
            id="std_accsc",
            accrediting_body=AccreditingBody.ACCSC,
            name="ACCSC Substantive Standards",
            version="2023",
            effective_date="2023-01-01",
            sections=sections,
            checklist_items=checklist_items,
            full_text="",
            is_system_preset=True,
        )

    def _sacscoc_preset(self) -> StandardsLibrary:
        """SACSCOC (Southern Association of Colleges and Schools Commission on Colleges) preset."""
        sections = [
            StandardsSection(id="sec_sacscoc_1", number="1", title="The Principle of Integrity", text="", parent_section=""),
            StandardsSection(id="sec_sacscoc_2", number="2", title="Core Requirements", text="", parent_section=""),
            StandardsSection(id="sec_sacscoc_3", number="3", title="Comprehensive Standards", text="", parent_section=""),
            StandardsSection(id="sec_sacscoc_4", number="4", title="Federal Requirements", text="", parent_section=""),

            # Core Requirements
            StandardsSection(id="sec_sacscoc_2_1", number="2.1", title="Degree-Granting Authority", text="", parent_section="sec_sacscoc_2"),

            # Comprehensive Standards
            StandardsSection(id="sec_sacscoc_3_1", number="3.1", title="Institutional Mission", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_2", number="3.2", title="Governance and Administration", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_3", number="3.3", title="Educational Programs", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_4", number="3.4", title="Academic Programs", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_5", number="3.5", title="Faculty", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_6", number="3.6", title="Library and Learning Resources", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_7", number="3.7", title="Student Support Services", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_8", number="3.8", title="Physical Resources", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_9", number="3.9", title="Financial and Physical Resources", text="", parent_section="sec_sacscoc_3"),
            StandardsSection(id="sec_sacscoc_3_10", number="3.10", title="Institutional Planning", text="", parent_section="sec_sacscoc_3"),
        ]

        checklist_items = [
            ChecklistItem(number="1.1", category="Integrity", description="Institution operates with integrity", section_reference="1", applies_to=["policy_manual"]),
            ChecklistItem(number="2.1", category="Authorization", description="Institution has degree-granting authority", section_reference="2.1", applies_to=["catalog"]),
            ChecklistItem(number="3.1.1", category="Mission", description="Institution has a written mission statement", section_reference="3.1", applies_to=["catalog"]),
            ChecklistItem(number="3.4.1", category="Academic", description="Academic programs are consistent with mission", section_reference="3.4", applies_to=["catalog"]),
            ChecklistItem(number="3.5.1", category="Faculty", description="Faculty qualifications are appropriate", section_reference="3.5", applies_to=["faculty_handbook"]),
        ]

        return StandardsLibrary(
            id="std_sacscoc",
            accrediting_body=AccreditingBody.SACSCOC,
            name="SACSCOC Principles of Accreditation",
            version="2024",
            effective_date="2024-01-01",
            sections=sections,
            checklist_items=checklist_items,
            full_text="",
            is_system_preset=True,
        )

    def _hlc_preset(self) -> StandardsLibrary:
        """HLC (Higher Learning Commission) preset."""
        sections = [
            StandardsSection(id="sec_hlc_1", number="1", title="Mission", text="", parent_section=""),
            StandardsSection(id="sec_hlc_1_a", number="1.A", title="Core Component", text="", parent_section="sec_hlc_1"),
            StandardsSection(id="sec_hlc_1_b", number="1.B", title="Criteria for Accreditation", text="", parent_section="sec_hlc_1"),
            StandardsSection(id="sec_hlc_1_c", number="1.C", title="Assumed Practices", text="", parent_section="sec_hlc_1"),

            StandardsSection(id="sec_hlc_2", number="2", title="Integrity: Ethical and Responsible Conduct", text="", parent_section=""),
            StandardsSection(id="sec_hlc_2_a", number="2.A", title="Core Component", text="", parent_section="sec_hlc_2"),
            StandardsSection(id="sec_hlc_2_b", number="2.B", title="Criteria for Accreditation", text="", parent_section="sec_hlc_2"),

            StandardsSection(id="sec_hlc_3", number="3", title="Teaching and Learning: Quality, Resources, and Support", text="", parent_section=""),
            StandardsSection(id="sec_hlc_3_a", number="3.A", title="Core Component", text="", parent_section="sec_hlc_3"),
            StandardsSection(id="sec_hlc_3_b", number="3.B", title="Criteria for Accreditation", text="", parent_section="sec_hlc_3"),

            StandardsSection(id="sec_hlc_4", number="4", title="Teaching and Learning: Evaluation and Improvement", text="", parent_section=""),
            StandardsSection(id="sec_hlc_4_a", number="4.A", title="Core Component", text="", parent_section="sec_hlc_4"),

            StandardsSection(id="sec_hlc_5", number="5", title="Institutional Effectiveness, Resources and Planning", text="", parent_section=""),
            StandardsSection(id="sec_hlc_5_a", number="5.A", title="Core Component", text="", parent_section="sec_hlc_5"),
        ]

        checklist_items = [
            ChecklistItem(number="1.A.1", category="Mission", description="Institution's mission is articulated publicly", section_reference="1.A", applies_to=["catalog"]),
            ChecklistItem(number="1.A.2", category="Mission", description="Mission guides operations", section_reference="1.A", applies_to=["policy_manual"]),
            ChecklistItem(number="2.A.1", category="Integrity", description="Institution operates with integrity", section_reference="2.A", applies_to=["policy_manual"]),
            ChecklistItem(number="3.A.1", category="Teaching", description="Degree programs are appropriate", section_reference="3.A", applies_to=["catalog"]),
            ChecklistItem(number="4.A.1", category="Assessment", description="Institution evaluates programs", section_reference="4.A", applies_to=["self_evaluation_report"]),
            ChecklistItem(number="5.A.1", category="Resources", description="Institution has sufficient resources", section_reference="5.A", applies_to=["self_evaluation_report"]),
        ]

        return StandardsLibrary(
            id="std_hlc",
            accrediting_body=AccreditingBody.HLC,
            name="HLC Criteria for Accreditation",
            version="2024",
            effective_date="2024-01-01",
            sections=sections,
            checklist_items=checklist_items,
            full_text="",
            is_system_preset=True,
        )

    def _abhes_preset(self) -> StandardsLibrary:
        """ABHES (Accrediting Bureau of Health Education Schools) preset."""
        sections = [
            StandardsSection(id="sec_abhes_i", number="I", title="Institutional", text="", parent_section=""),
            StandardsSection(id="sec_abhes_i_a", number="I.A", title="Mission Statement", text="", parent_section="sec_abhes_i"),
            StandardsSection(id="sec_abhes_i_b", number="I.B", title="Administration", text="", parent_section="sec_abhes_i"),
            StandardsSection(id="sec_abhes_i_c", number="I.C", title="Financial Stability", text="", parent_section="sec_abhes_i"),

            StandardsSection(id="sec_abhes_ii", number="II", title="Program", text="", parent_section=""),
            StandardsSection(id="sec_abhes_ii_a", number="II.A", title="Program Scope", text="", parent_section="sec_abhes_ii"),
            StandardsSection(id="sec_abhes_ii_b", number="II.B", title="Clinical Experience", text="", parent_section="sec_abhes_ii"),

            StandardsSection(id="sec_abhes_iii", number="III", title="Distance Education", text="", parent_section=""),
        ]

        checklist_items = [
            ChecklistItem(number="I.A.1", category="Mission", description="Institution has a published mission", section_reference="I.A", applies_to=["catalog"]),
            ChecklistItem(number="I.B.1", category="Administration", description="Administration is qualified", section_reference="I.B", applies_to=["policy_manual"]),
            ChecklistItem(number="II.A.1", category="Program", description="Programs meet healthcare standards", section_reference="II.A", applies_to=["catalog"]),
            ChecklistItem(number="II.B.1", category="Clinical", description="Clinical experiences are documented", section_reference="II.B", applies_to=["catalog"]),
        ]

        return StandardsLibrary(
            id="std_abhes",
            accrediting_body=AccreditingBody.ABHES,
            name="ABHES Accreditation Manual",
            version="2023",
            effective_date="2023-07-01",
            sections=sections,
            checklist_items=checklist_items,
            full_text="",
            is_system_preset=True,
        )

    def _coe_preset(self) -> StandardsLibrary:
        """COE (Council on Occupational Education) preset."""
        sections = [
            StandardsSection(id="sec_coe_1", number="1", title="Mission and Objectives", text="", parent_section=""),
            StandardsSection(id="sec_coe_2", number="2", title="Administration", text="", parent_section=""),
            StandardsSection(id="sec_coe_3", number="3", title="Financial Stability", text="", parent_section=""),
            StandardsSection(id="sec_coe_4", number="4", title="Student Services", text="", parent_section=""),
            StandardsSection(id="sec_coe_5", number="5", title="Instructional Programs", text="", parent_section=""),
            StandardsSection(id="sec_coe_6", number="6", title="Faculty Qualifications", text="", parent_section=""),
            StandardsSection(id="sec_coe_7", number="7", title="Facilities", text="", parent_section=""),
            StandardsSection(id="sec_coe_8", number="8", title="Publications", text="", parent_section=""),
            StandardsSection(id="sec_coe_9", number="9", title="Research", text="", parent_section=""),
            StandardsSection(id="sec_coe_10", number="10", title="Planning and Evaluation", text="", parent_section=""),
        ]

        checklist_items = [
            ChecklistItem(number="1.1", category="Mission", description="Mission statement is published", section_reference="1", applies_to=["catalog"]),
            ChecklistItem(number="2.1", category="Administration", description="Administration is organized", section_reference="2", applies_to=["policy_manual"]),
            ChecklistItem(number="4.1", category="Student Services", description="Student services are adequate", section_reference="4", applies_to=["student_handbook"]),
            ChecklistItem(number="5.1", category="Programs", description="Programs are approved", section_reference="5", applies_to=["catalog"]),
            ChecklistItem(number="6.1", category="Faculty", description="Faculty meet qualifications", section_reference="6", applies_to=["faculty_handbook"]),
            ChecklistItem(number="8.1", category="Publications", description="Publications are accurate", section_reference="8", applies_to=["catalog"]),
        ]

        return StandardsLibrary(
            id="std_coe",
            accrediting_body=AccreditingBody.COE,
            name="COE Handbook of Accreditation",
            version="2024",
            effective_date="2024-01-01",
            sections=sections,
            checklist_items=checklist_items,
            full_text="",
            is_system_preset=True,
        )

    def _get_library_path(self, library_id: str) -> Path:
        """Get the file path for a library."""
        return self.standards_dir / f"{library_id}.json"

    def load(self, library_id: str) -> Optional[StandardsLibrary]:
        """Load a standards library by ID.

        Args:
            library_id: The library ID to load.

        Returns:
            The library if found, None otherwise.
        """
        path = self._get_library_path(library_id)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return StandardsLibrary.from_dict(data)

    def save(self, library: StandardsLibrary) -> None:
        """Save a standards library to disk.

        Args:
            library: The library to save.
        """
        library.updated_at = now_iso()
        path = self._get_library_path(library.id)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(library.to_dict(), f, indent=2)

    def delete(self, library_id: str) -> bool:
        """Delete a standards library by ID.

        System presets cannot be deleted.

        Args:
            library_id: The library ID to delete.

        Returns:
            True if deleted, False if not found or is system preset.
        """
        library = self.load(library_id)
        if library is None:
            return False
        if library.is_system_preset:
            return False

        path = self._get_library_path(library_id)
        path.unlink()
        return True

    def list_all(self) -> List[StandardsLibrary]:
        """List all standards libraries.

        Returns:
            List of all libraries, system presets first.
        """
        libraries = []
        for path in self.standards_dir.glob("*.json"):
            library = self.load(path.stem)
            if library:
                libraries.append(library)

        # Sort: system presets first, then by name
        libraries.sort(key=lambda lib: (not lib.is_system_preset, lib.name))
        return libraries

    def list_by_accreditor(self, accreditor: AccreditingBody) -> List[StandardsLibrary]:
        """List libraries for a specific accrediting body.

        Args:
            accreditor: The accrediting body to filter by.

        Returns:
            List of matching libraries.
        """
        all_libs = self.list_all()
        return [lib for lib in all_libs if lib.accrediting_body == accreditor]

    def get_default(self, accreditor: AccreditingBody) -> Optional[StandardsLibrary]:
        """Get the default (preset) library for an accreditor.

        Args:
            accreditor: The accrediting body.

        Returns:
            The preset library if it exists, None otherwise.
        """
        preset_id = f"std_{accreditor.value.lower()}"
        return self.load(preset_id)

    def get_section(self, library_id: str, section_id: str) -> Optional[StandardsSection]:
        """Get a specific section from a library.

        Args:
            library_id: The library ID.
            section_id: The section ID.

        Returns:
            The section if found, None otherwise.
        """
        library = self.load(library_id)
        if library is None:
            return None

        for section in library.sections:
            if section.id == section_id:
                return section
        return None

    def get_section_by_number(self, library_id: str, number: str) -> Optional[StandardsSection]:
        """Get a section by its number (e.g., "I.A.1").

        Args:
            library_id: The library ID.
            number: The section number.

        Returns:
            The section if found, None otherwise.
        """
        library = self.load(library_id)
        if library is None:
            return None

        for section in library.sections:
            if section.number == number:
                return section
        return None

    def get_child_sections(self, library_id: str, parent_id: str) -> List[StandardsSection]:
        """Get all child sections of a parent section.

        Args:
            library_id: The library ID.
            parent_id: The parent section ID (empty string for top-level).

        Returns:
            List of child sections.
        """
        library = self.load(library_id)
        if library is None:
            return []

        return [s for s in library.sections if s.parent_section == parent_id]

    def get_checklist_items(
        self,
        library_id: str,
        category: Optional[str] = None
    ) -> List[ChecklistItem]:
        """Get checklist items, optionally filtered by category.

        Args:
            library_id: The library ID.
            category: Optional category to filter by.

        Returns:
            List of matching checklist items.
        """
        library = self.load(library_id)
        if library is None:
            return []

        if category is None:
            return library.checklist_items

        return [item for item in library.checklist_items if item.category == category]

    def get_items_for_document_type(
        self,
        library_id: str,
        doc_type: DocumentType
    ) -> List[ChecklistItem]:
        """Get checklist items that apply to a document type.

        Args:
            library_id: The library ID.
            doc_type: The document type to filter by.

        Returns:
            List of applicable checklist items.
        """
        library = self.load(library_id)
        if library is None:
            return []

        doc_type_value = doc_type.value if isinstance(doc_type, DocumentType) else doc_type
        return [
            item for item in library.checklist_items
            if doc_type_value in item.applies_to
        ]

    def duplicate(
        self,
        library_id: str,
        new_name: str
    ) -> Optional[StandardsLibrary]:
        """Duplicate a library with a new name.

        Args:
            library_id: The library ID to duplicate.
            new_name: Name for the new library.

        Returns:
            The new library if successful, None if source not found.
        """
        source = self.load(library_id)
        if source is None:
            return None

        # Create new library with new ID and name
        new_data = source.to_dict()
        new_data["id"] = f"std_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_data["name"] = new_name
        new_data["is_system_preset"] = False
        new_data["created_at"] = now_iso()
        new_data["updated_at"] = now_iso()

        new_library = StandardsLibrary.from_dict(new_data)
        self.save(new_library)
        return new_library


# Module-level singleton
_standards_store: Optional[StandardsStore] = None


def get_standards_store(standards_dir: Optional[Path] = None) -> StandardsStore:
    """Get or create the standards store singleton.

    Args:
        standards_dir: Optional custom directory (only used on first call).

    Returns:
        The StandardsStore instance.
    """
    global _standards_store
    if _standards_store is None:
        if standards_dir:
            _standards_store = StandardsStore(standards_dir)
        else:
            _standards_store = StandardsStore()
    return _standards_store
