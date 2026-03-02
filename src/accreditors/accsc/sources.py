"""ACCSC Standards Sources.

Official URLs for ACCSC standards, checklists, and guidance documents.
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


# ACCSC Official Sources
SOURCES: List[StandardsSource] = [
    StandardsSource(
        id="substantive_standards",
        name="Substantive Standards and Reports",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/Substantive-Standards-and-Reports.pdf",
        format="pdf",
        doc_type="standards",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="enrollment_agreement_checklist",
        name="Enrollment Agreement Checklist",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/Enrollment-Agreement-Checklist.pdf",
        format="pdf",
        doc_type="checklist",
        parser_hint="numbered_items",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="catalog_checklist",
        name="School Catalog Checklist",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/School-Catalog-Checklist.pdf",
        format="pdf",
        doc_type="checklist",
        parser_hint="numbered_items",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="student_handbook_checklist",
        name="Student Handbook Checklist",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/Student-Handbook-Checklist.pdf",
        format="pdf",
        doc_type="checklist",
        parser_hint="numbered_items",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="rules_process_procedure",
        name="Rules of Process and Procedure",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/Rules-of-Process-and-Procedure.pdf",
        format="pdf",
        doc_type="guidance",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
    StandardsSource(
        id="instructions_reports",
        name="Instructions for the Preparation of Reports",
        url="https://www.accsc.org/UploadedDocuments/Accreditation/Instructions-for-the-Preparation-of-Reports.pdf",
        format="pdf",
        doc_type="guidance",
        parser_hint="section_headers",
        fetch_cadence="monthly",
    ),
]


# ACCSC Standards Section Structure (for parsing)
SECTION_STRUCTURE = {
    "I": "Rules of Process and Procedure",
    "II": "Governance, Management, and Administration",
    "III": "Relations with Students",
    "IV": "Faculty and Staff Qualifications",
    "V": "Educational Program and Outcomes",
    "VI": "Student Progress, Attendance, and Satisfactory Progress",
    "VII": "Financial Practices and Refund Policies",
    "VIII": "Student Support Services",
    "IX": "Educational Facilities and Equipment",
    "X": "Publications and Advertising",
    "XI": "Library and Learning Resources",
    "XII": "Admissions and Enrollment",
}


def get_sources() -> List[StandardsSource]:
    """Get all ACCSC sources."""
    return SOURCES


def get_source(source_id: str) -> StandardsSource:
    """Get a specific source by ID."""
    for source in SOURCES:
        if source.id == source_id:
            return source
    return None


def get_section_structure() -> Dict[str, str]:
    """Get ACCSC standards section structure."""
    return SECTION_STRUCTURE


def get_fetch_urls() -> Dict[str, str]:
    """Get URL map for fetching."""
    return {s.id: s.url for s in SOURCES}
