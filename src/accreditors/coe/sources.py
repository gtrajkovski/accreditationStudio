"""COE Standards Sources.

Official URLs for COE standards, checklists, and guidance documents.
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class StandardsSource:
    """A source document for standards."""
    id: str
    name: str
    url: str
    format: str  # pdf | html | docx
    doc_type: str  # standards | checklist | guidance | form
    parser_hint: str = ""
    fetch_cadence: str = "monthly"  # daily | weekly | monthly | manual


# COE Official Sources
SOURCES: List[StandardsSource] = [
    StandardsSource(
        id="handbook",
        name="Handbook of Accreditation",
        url="https://council.org/wp-content/uploads/2024/01/2024-Handbook-of-Accreditation.pdf",
        format="pdf",
        doc_type="standards",
        parser_hint="numbered_standards",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="self_study_report",
        name="Self-Study Report Guidelines",
        url="https://council.org/wp-content/uploads/2024/01/Self-Study-Report-Guidelines.pdf",
        format="pdf",
        doc_type="guidance",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="catalog_checklist",
        name="Catalog Checklist",
        url="https://council.org/wp-content/uploads/2024/01/Catalog-Checklist.pdf",
        format="pdf",
        doc_type="checklist",
        parser_hint="numbered_items",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="enrollment_agreement_checklist",
        name="Enrollment Agreement Checklist",
        url="https://council.org/wp-content/uploads/2024/01/Enrollment-Agreement-Checklist.pdf",
        format="pdf",
        doc_type="checklist",
        parser_hint="numbered_items",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="substantive_change_policy",
        name="Substantive Change Policy",
        url="https://council.org/wp-content/uploads/2024/01/Substantive-Change-Policy.pdf",
        format="pdf",
        doc_type="guidance",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="annual_report_instructions",
        name="Annual Report Instructions",
        url="https://council.org/wp-content/uploads/2024/01/Annual-Report-Instructions.pdf",
        format="pdf",
        doc_type="guidance",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
]


# COE Standards Structure (12 Standards with lettered criteria)
SECTION_STRUCTURE = {
    "1": "Mission",
    "2": "Organization",
    "3": "Administration",
    "4": "Relations with Students",
    "5": "Educational Programs",
    "6": "Program Advisory Committees",
    "7": "Instructional Staff",
    "8": "Instructional Resources and Equipment",
    "9": "Media and Learning Resources",
    "10": "Facilities",
    "11": "Financial Resources",
    "12": "Planning and Institutional Assessment",
}

# Criteria structure within each standard (example for Standard 5)
CRITERIA_STRUCTURE = {
    "5": {
        "A": "Program Content",
        "B": "Student Progress",
        "C": "Program Completion",
        "D": "Satisfactory Progress",
        "E": "Attendance Requirements",
        "F": "Placement Assistance",
        "G": "Externships/Clinical",
    },
}


def get_sources() -> List[StandardsSource]:
    """Get all COE sources."""
    return SOURCES


def get_source(source_id: str) -> StandardsSource:
    """Get a specific source by ID."""
    for source in SOURCES:
        if source.id == source_id:
            return source
    return None


def get_section_structure() -> Dict[str, str]:
    """Get COE standards section structure."""
    return SECTION_STRUCTURE


def get_criteria_structure() -> Dict[str, Dict[str, str]]:
    """Get COE criteria structure within standards."""
    return CRITERIA_STRUCTURE


def get_fetch_urls() -> Dict[str, str]:
    """Get URL map for fetching."""
    return {s.id: s.url for s in SOURCES}
