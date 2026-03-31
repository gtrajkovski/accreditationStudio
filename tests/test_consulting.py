"""Tests for Consulting Service.

Tests readiness assessment, pre-visit checklist, and self-assessment generation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.consulting_service import (
    generate_readiness_assessment,
    generate_pre_visit_checklist,
    get_self_assessment_questions,
    get_self_assessment_with_ai,
    _categorize_standard,
    _determine_overall_rating,
    _estimate_remediation_effort,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_conn():
    """Mock database connection."""
    conn = MagicMock()

    def execute_side_effect(query, params=None):
        cursor = MagicMock()

        # Mock institution lookup
        if "SELECT name FROM institutions" in query:
            cursor.fetchone.return_value = {"name": "Test Institution"}

        # Mock audit runs
        elif "SELECT id FROM audit_runs" in query and "ORDER BY created_at DESC" in query:
            cursor.fetchone.return_value = {"id": "audit_001"}

        # Mock audit findings for sections
        elif "SELECT\n            status," in query:
            cursor.fetchall.return_value = [
                {"status": "compliant", "severity": "moderate", "count": 10},
                {"status": "partial", "severity": "advisory", "count": 2},
                {"status": "non_compliant", "severity": "critical", "count": 1},
            ]

        # Mock standards count
        elif "SELECT COUNT(*) as count" in query and "FROM standards" in query:
            cursor.fetchone.return_value = {"count": 15}

        # Mock critical gaps query
        elif "severity IN ('critical', 'significant')" in query:
            cursor.fetchall.return_value = [
                {
                    "id": "finding_001",
                    "severity": "critical",
                    "summary": "Missing policy",
                    "recommendation": "Create policy"
                }
            ]

        # Mock standards for checklist
        elif "SELECT s.id, s.standard_code, s.title" in query:
            cursor.fetchall.return_value = [
                {"id": "std_001", "standard_code": "I.A.1", "title": "Administration structure"},
                {"id": "std_002", "standard_code": "II.A.1", "title": "Curriculum design"},
            ]

        # Mock checklist items with findings
        elif "SELECT\n            f.id," in query and "FROM audit_findings f" in query:
            cursor.fetchall.return_value = [
                {
                    "id": "finding_001",
                    "status": "compliant",
                    "summary": "Policy meets requirements",
                    "recommendation": None,
                    "severity": "moderate",
                    "item_text": "Administration structure",
                    "standard_code": "I.A.1",
                    "standard_title": "Administration",
                    "evidence": "5:Evidence text|7:More evidence"
                }
            ]

        # Mock standards for self-assessment
        elif "SELECT\n            s.id," in query and "JOIN accreditors a" in query:
            cursor.fetchall.return_value = [
                {
                    "id": "std_001",
                    "standard_code": "I.A.1",
                    "title": "Administration structure",
                    "body_text": "The institution must maintain clear administrative structure."
                },
                {
                    "id": "std_002",
                    "standard_code": "II.A.1",
                    "title": "Curriculum design",
                    "body_text": "Programs must have documented curriculum."
                }
            ]

        # Mock AI findings for self-assessment
        elif "SELECT f.status, f.summary, f.confidence" in query:
            cursor.fetchone.return_value = {
                "status": "compliant",
                "summary": "Current policy meets requirements",
                "confidence": 0.85
            }

        else:
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []

        return cursor

    conn.execute = Mock(side_effect=execute_side_effect)
    return conn


# =============================================================================
# Readiness Assessment Tests
# =============================================================================

def test_readiness_assessment_generates_structure(mock_conn):
    """Test that readiness assessment generates complete structure."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn), \
         patch('src.services.consulting_service.compute_readiness') as mock_readiness:

        # Mock readiness score
        mock_score = MagicMock()
        mock_score.total = 85
        mock_score.documents = 90
        mock_score.compliance = 80
        mock_score.evidence = 85
        mock_score.consistency = 90
        mock_score.blockers = []
        mock_readiness.return_value = mock_score

        assessment = generate_readiness_assessment("inst_001", "ACCSC")

        assert assessment.institution_id == "inst_001"
        assert assessment.institution_name == "Test Institution"
        assert assessment.accreditor_code == "ACCSC"
        assert assessment.overall_rating in ["ready", "conditionally_ready", "not_ready"]
        assert assessment.readiness_score == 85
        assert len(assessment.sections) == 8  # 8 ACCSC sections
        assert assessment.timeline_recommendation != ""
        assert assessment.remediation_effort in ["low", "medium", "high"]
        assert assessment.executive_summary != ""


def test_rating_logic(mock_conn):
    """Test overall rating determination logic."""
    # Score >= 90, no critical blockers -> Ready
    rating = _determine_overall_rating(92, [])
    assert rating == "ready"

    # Score >= 70, 1 critical blocker -> Conditionally ready
    blocker = MagicMock()
    blocker.severity = "critical"
    rating = _determine_overall_rating(75, [blocker])
    assert rating == "conditionally_ready"

    # Score < 70 -> Not ready
    rating = _determine_overall_rating(65, [])
    assert rating == "not_ready"

    # Score >= 90, multiple critical blockers -> Not ready (overrides score)
    rating = _determine_overall_rating(95, [blocker, blocker, blocker])
    assert rating == "not_ready"


def test_empty_institution_assessment(mock_conn):
    """Test assessment with no audit data."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn), \
         patch('src.services.consulting_service.compute_readiness') as mock_readiness:

        # Mock empty readiness
        mock_score = MagicMock()
        mock_score.total = 0
        mock_score.documents = 0
        mock_score.compliance = 0
        mock_score.evidence = 0
        mock_score.consistency = 0
        mock_score.blockers = []
        mock_readiness.return_value = mock_score

        # Mock no audit data
        def no_audit_execute(query, params=None):
            cursor = MagicMock()
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
            if "SELECT name FROM institutions" in query:
                cursor.fetchone.return_value = {"name": "Empty Institution"}
            return cursor

        mock_conn.execute = Mock(side_effect=no_audit_execute)

        assessment = generate_readiness_assessment("inst_002", "ACCSC")

        assert assessment.readiness_score == 0
        assert assessment.overall_rating == "not_ready"
        assert len(assessment.sections) == 8  # Still generates all sections
        # All sections should have "unknown" rating when no data
        for section in assessment.sections:
            assert section.total_standards == 0


def test_remediation_effort_estimation():
    """Test remediation effort calculation."""
    # High score, few gaps -> low effort
    effort = _estimate_remediation_effort(87, 2)
    assert effort == "low"

    # Medium score, moderate gaps -> medium effort
    effort = _estimate_remediation_effort(75, 6)
    assert effort == "medium"

    # Low score, many gaps -> high effort
    effort = _estimate_remediation_effort(55, 15)
    assert effort == "high"


# =============================================================================
# Pre-Visit Checklist Tests
# =============================================================================

def test_checklist_generation(mock_conn):
    """Test pre-visit checklist generation."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_001", "ACCSC")

        assert checklist.institution_id == "inst_001"
        assert checklist.accreditor_code == "ACCSC"
        assert len(checklist.sections) > 0
        assert checklist.overall_progress["total"] > 0


def test_checklist_progress_calculation(mock_conn):
    """Test checklist progress tracking."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_001", "ACCSC")

        # Verify progress sums correctly
        overall = checklist.overall_progress
        assert overall["met"] + overall["partial"] + overall["not_met"] == overall["total"]

        # Verify section progress
        for section_code, section_progress in checklist.section_progress.items():
            items = checklist.sections[section_code]
            assert len(items) == section_progress["total"]

        # Verify percentage calculation
        if overall["total"] > 0:
            expected_pct = int((overall["met"] / overall["total"]) * 100)
            assert overall["percent_complete"] == expected_pct


def test_checklist_from_audit(mock_conn):
    """Test checklist population from audit findings."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_001", "ACCSC")

        # Should have items from mocked findings
        all_items = [item for items in checklist.sections.values() for item in items]
        assert len(all_items) > 0

        # Check that evidence references are extracted
        items_with_evidence = [i for i in all_items if i.evidence_reference]
        assert len(items_with_evidence) > 0


def test_checklist_without_audit(mock_conn):
    """Test checklist generation with no audit data."""
    def no_audit_execute(query, params=None):
        cursor = MagicMock()
        if "SELECT id FROM audit_runs" in query:
            cursor.fetchone.return_value = None
        elif "SELECT s.id, s.standard_code, s.title" in query:
            cursor.fetchall.return_value = [
                {"id": "std_001", "standard_code": "I.A.1", "title": "Test standard"}
            ]
        else:
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
        return cursor

    mock_conn.execute = Mock(side_effect=no_audit_execute)

    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_002", "ACCSC")

        # Should fall back to basic checklist from standards
        all_items = [item for items in checklist.sections.values() for item in items]
        assert len(all_items) > 0

        # All items should have "not_met" status (no audit evidence)
        for item in all_items:
            assert item.status == "not_met"


# =============================================================================
# Self-Assessment Tests
# =============================================================================

def test_self_assessment_questions(mock_conn):
    """Test self-assessment question generation."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        questions = get_self_assessment_questions("ACCSC")

        assert len(questions) > 0
        for q in questions:
            assert q.standard_code != ""
            assert q.section != ""
            assert q.requirement_text != ""
            assert q.what_to_look_for != ""
            assert len(q.evidence_to_prepare) > 0
            assert len(q.common_deficiencies) > 0


def test_self_assessment_section_filter(mock_conn):
    """Test filtering questions by section."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        # Get all questions
        all_questions = get_self_assessment_questions("ACCSC")

        # Get admin questions only
        admin_questions = get_self_assessment_questions("ACCSC", section="admin")

        # Admin questions should be subset
        assert len(admin_questions) <= len(all_questions)

        # All admin questions should be in admin section
        for q in admin_questions:
            assert "Administration" in q.section or "Management" in q.section


def test_self_assessment_with_ai(mock_conn):
    """Test self-assessment with AI findings included."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        questions = get_self_assessment_with_ai("inst_001", "ACCSC")

        assert len(questions) > 0

        # Some questions should have AI assessments
        # (based on mock data returning findings for first standard)
        questions_with_ai = [q for q in questions if q.ai_assessment]
        assert len(questions_with_ai) > 0


def test_standard_categorization():
    """Test section categorization logic."""
    # Test keyword matching
    assert _categorize_standard("Administrative structure and governance") == "admin"
    assert _categorize_standard("Curriculum development and assessment") == "academics"
    assert _categorize_standard("Admission requirements") == "admissions"
    assert _categorize_standard("Student support services") == "student_services"
    assert _categorize_standard("Financial stability") == "financial"
    assert _categorize_standard("Facilities and equipment") == "facilities"
    assert _categorize_standard("Catalog disclosures") == "catalog"
    assert _categorize_standard("Student achievement outcomes") == "achievement"

    # Test default (no match)
    assert _categorize_standard("Unrelated text") == "admin"


# =============================================================================
# PDF/DOCX Export Tests
# =============================================================================

def test_pdf_export_validation(mock_conn):
    """Test PDF export generates valid output."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn), \
         patch('src.services.consulting_service.compute_readiness') as mock_readiness:

        mock_score = MagicMock()
        mock_score.total = 85
        mock_score.documents = 90
        mock_score.compliance = 80
        mock_score.evidence = 85
        mock_score.consistency = 90
        mock_score.blockers = []
        mock_readiness.return_value = mock_score

        assessment = generate_readiness_assessment("inst_001", "ACCSC")

        # Import PDF generation function
        from src.api.consulting import _generate_assessment_pdf

        try:
            pdf_bytes = _generate_assessment_pdf(assessment)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 0

            # Check it's a valid PDF (starts with PDF magic number)
            if pdf_bytes.startswith(b"%PDF"):
                assert True  # Valid PDF
            else:
                # If WeasyPrint not installed, expect error message
                assert b"WeasyPrint" in pdf_bytes

        except (ImportError, OSError) as e:
            # WeasyPrint not installed or GTK libraries missing - skip
            pytest.skip(f"WeasyPrint not available: {str(e)}")


def test_docx_export_validation(mock_conn):
    """Test DOCX export generates valid output."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_001", "ACCSC")

        # Import DOCX generation function
        from src.api.consulting import _generate_checklist_docx

        try:
            docx_bytes = _generate_checklist_docx(checklist)
            assert isinstance(docx_bytes, bytes)
            assert len(docx_bytes) > 0

            # Check it's a valid DOCX (ZIP format with specific structure)
            if docx_bytes.startswith(b"PK"):
                assert True  # Valid DOCX (ZIP file)
            else:
                # If python-docx not installed, expect error message
                assert b"python-docx" in docx_bytes

        except ImportError:
            # python-docx not installed - skip
            pytest.skip("python-docx not available")


def test_pdf_empty_institution(mock_conn):
    """Test PDF generation handles empty institution gracefully."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn), \
         patch('src.services.consulting_service.compute_readiness') as mock_readiness:

        mock_score = MagicMock()
        mock_score.total = 0
        mock_score.documents = 0
        mock_score.compliance = 0
        mock_score.evidence = 0
        mock_score.consistency = 0
        mock_score.blockers = []
        mock_readiness.return_value = mock_score

        def no_data_execute(query, params=None):
            cursor = MagicMock()
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []
            if "SELECT name FROM institutions" in query:
                cursor.fetchone.return_value = {"name": "Empty Institution"}
            return cursor

        mock_conn.execute = Mock(side_effect=no_data_execute)

        assessment = generate_readiness_assessment("inst_002", "ACCSC")

        from src.api.consulting import _generate_assessment_html

        # Should generate HTML without errors
        html = _generate_assessment_html(assessment)
        assert isinstance(html, str)
        assert "Empty Institution" in html
        assert "NOT READY" in html  # Zero score = not ready


def test_docx_empty_checklist(mock_conn):
    """Test DOCX generation handles empty checklist gracefully."""
    def no_data_execute(query, params=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        return cursor

    mock_conn.execute = Mock(side_effect=no_data_execute)

    with patch('src.services.consulting_service.get_conn', return_value=mock_conn):
        checklist = generate_pre_visit_checklist("inst_002", "ACCSC")

        from src.api.consulting import _generate_checklist_docx

        try:
            # Should generate DOCX even with no items
            docx_bytes = _generate_checklist_docx(checklist)
            assert isinstance(docx_bytes, bytes)
        except ImportError:
            pytest.skip("python-docx not available")


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_consulting_workflow(mock_conn):
    """Test complete consulting workflow."""
    with patch('src.services.consulting_service.get_conn', return_value=mock_conn), \
         patch('src.services.consulting_service.compute_readiness') as mock_readiness:

        mock_score = MagicMock()
        mock_score.total = 82
        mock_score.documents = 85
        mock_score.compliance = 78
        mock_score.evidence = 80
        mock_score.consistency = 88
        mock_score.blockers = []
        mock_readiness.return_value = mock_score

        # Generate assessment
        assessment = generate_readiness_assessment("inst_001", "ACCSC")
        assert assessment.overall_rating == "conditionally_ready"

        # Generate checklist
        checklist = generate_pre_visit_checklist("inst_001", "ACCSC")
        assert checklist.overall_progress["total"] > 0

        # Get self-assessment questions
        questions = get_self_assessment_with_ai("inst_001", "ACCSC")
        assert len(questions) > 0

        # Verify consistency across deliverables
        # All should reference same institution
        assert assessment.institution_id == checklist.institution_id == "inst_001"
        assert assessment.accreditor_code == checklist.accreditor_code == "ACCSC"
