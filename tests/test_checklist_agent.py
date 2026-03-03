"""Tests for the Checklist Auto-Fill Agent."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.checklist_agent import ChecklistAgent
from src.core.models import (
    AgentSession,
    SessionStatus,
    Institution,
    ChecklistItem,
    ChecklistResponse,
    ChecklistResponseStatus,
    FilledChecklist,
    FilledChecklistStatus,
    ComplianceStatus,
    AuditFinding,
    FindingSeverity,
)


@pytest.fixture
def mock_workspace_manager():
    """Create mock workspace manager."""
    manager = MagicMock()

    institution = Institution(id="inst_test", name="Test University")
    manager.load_institution.return_value = institution
    manager.save_file.return_value = MagicMock()
    manager.list_audits.return_value = []
    manager.load_file.return_value = None

    return manager


@pytest.fixture
def agent_session():
    """Create agent session."""
    return AgentSession(
        id="sess_test",
        agent_type="checklist",
        institution_id="inst_test",
        status=SessionStatus.RUNNING,
    )


@pytest.fixture
def mock_standards_library():
    """Create mock standards library."""
    from src.core.models import StandardsLibrary, AccreditingBody

    return StandardsLibrary(
        id="std_test",
        accrediting_body=AccreditingBody.ACCSC,
        name="Test Standards",
        version="2024",
        checklist_items=[
            ChecklistItem(
                number="I.A.1",
                category="Mission",
                description="School has a written mission statement",
                section_reference="I.A",
                applies_to=["catalog"],
            ),
            ChecklistItem(
                number="I.A.2",
                category="Mission",
                description="Mission statement is published",
                section_reference="I.A",
                applies_to=["catalog"],
            ),
            ChecklistItem(
                number="I.C.1",
                category="Financial",
                description="Tuition and fees are disclosed",
                section_reference="I.C",
                applies_to=["catalog", "enrollment_agreement"],
            ),
        ],
    )


@pytest.fixture
@patch("src.agents.base_agent.Anthropic")
def checklist_agent(mock_anthropic, agent_session, mock_workspace_manager):
    """Create checklist agent."""
    mock_anthropic.return_value = MagicMock()
    return ChecklistAgent(agent_session, mock_workspace_manager)


class TestModels:
    """Tests for checklist data models."""

    def test_checklist_response_serialization(self):
        """Test ChecklistResponse serialization."""
        response = ChecklistResponse(
            item_number="I.A.1",
            item_description="Test description",
            category="Mission",
            compliance_status=ComplianceStatus.COMPLIANT,
            response_status=ChecklistResponseStatus.AUTO_FILLED,
            narrative_response="The institution has a mission statement.",
            ai_confidence=0.85,
        )

        data = response.to_dict()
        assert data["item_number"] == "I.A.1"
        assert data["compliance_status"] == "compliant"
        assert data["response_status"] == "auto_filled"
        assert data["ai_confidence"] == 0.85

        # Round-trip
        restored = ChecklistResponse.from_dict(data)
        assert restored.item_number == "I.A.1"
        assert restored.compliance_status == ComplianceStatus.COMPLIANT

    def test_filled_checklist_serialization(self):
        """Test FilledChecklist serialization."""
        checklist = FilledChecklist(
            institution_id="inst_test",
            standards_library_id="std_test",
            name="Test Checklist",
            status=FilledChecklistStatus.IN_PROGRESS,
            total_items=5,
        )
        checklist.responses.append(ChecklistResponse(
            item_number="I.A.1",
            compliance_status=ComplianceStatus.COMPLIANT,
        ))

        data = checklist.to_dict()
        assert data["institution_id"] == "inst_test"
        assert data["status"] == "in_progress"
        assert len(data["responses"]) == 1

        # Round-trip
        restored = FilledChecklist.from_dict(data)
        assert restored.institution_id == "inst_test"
        assert len(restored.responses) == 1

    def test_filled_checklist_update_stats(self):
        """Test FilledChecklist.update_stats()."""
        checklist = FilledChecklist()
        checklist.responses = [
            ChecklistResponse(
                item_number="1",
                compliance_status=ComplianceStatus.COMPLIANT,
                response_status=ChecklistResponseStatus.AUTO_FILLED,
            ),
            ChecklistResponse(
                item_number="2",
                compliance_status=ComplianceStatus.PARTIAL,
                response_status=ChecklistResponseStatus.AUTO_FILLED,
            ),
            ChecklistResponse(
                item_number="3",
                compliance_status=ComplianceStatus.NON_COMPLIANT,
                response_status=ChecklistResponseStatus.NEEDS_REVIEW,
            ),
            ChecklistResponse(
                item_number="4",
                compliance_status=ComplianceStatus.NA,
                response_status=ChecklistResponseStatus.NOT_STARTED,
            ),
        ]

        checklist.update_stats()

        assert checklist.total_items == 4
        assert checklist.items_completed == 2  # AUTO_FILLED count
        assert checklist.items_compliant == 1
        assert checklist.items_partial == 1
        assert checklist.items_non_compliant == 1
        assert checklist.items_needs_review == 1


class TestAgentInit:
    """Tests for agent initialization."""

    def test_agent_has_tools(self, checklist_agent):
        """Test agent has required tools."""
        tools = checklist_agent.tools
        tool_names = [t["name"] for t in tools]

        assert "load_checklist_template" in tool_names
        assert "load_audit_findings" in tool_names
        assert "auto_fill_from_findings" in tool_names
        assert "search_evidence" in tool_names
        assert "generate_narrative" in tool_names
        assert "update_item_response" in tool_names
        assert "save_checklist" in tool_names
        assert "get_checklist_summary" in tool_names


class TestLoadTemplate:
    """Tests for load_checklist_template tool."""

    @patch("src.core.standards_store.StandardsStore")
    def test_load_template_success(self, mock_store_class, checklist_agent, mock_standards_library):
        """Test loading checklist template from standards library."""
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        result = checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "std_test",
            "name": "My Checklist",
        })

        assert result["success"] is True
        assert result["total_items"] == 3
        assert "Mission" in result["categories"]
        assert checklist_agent._current_checklist is not None
        assert len(checklist_agent._current_checklist.responses) == 3

    @patch("src.core.standards_store.StandardsStore")
    def test_load_template_not_found(self, mock_store_class, checklist_agent):
        """Test error when standards library not found."""
        mock_store = MagicMock()
        mock_store.get.return_value = None
        mock_store_class.return_value = mock_store

        result = checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "invalid",
        })

        assert "error" in result


class TestAutoFillFindings:
    """Tests for auto_fill_from_findings tool."""

    @patch("src.core.standards_store.StandardsStore")
    def test_auto_fill_matches_findings(self, mock_store_class, checklist_agent, mock_standards_library):
        """Test auto-fill matches audit findings to checklist items."""
        # Setup checklist
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "std_test",
        })

        # Setup findings
        checklist_agent._audit_findings = [
            AuditFinding(
                id="find_1",
                audit_id="audit_1",
                item_number="I.A.1",
                status=ComplianceStatus.COMPLIANT,
                evidence_in_document="Mission statement found on page 3",
                finding_detail="School has documented mission",
            ),
            AuditFinding(
                id="find_2",
                audit_id="audit_1",
                item_number="I.C.1",
                status=ComplianceStatus.NON_COMPLIANT,
                severity=FindingSeverity.CRITICAL,
                evidence_in_document="No tuition disclosure found",
                finding_detail="Tuition not clearly disclosed",
            ),
        ]

        result = checklist_agent._tool_auto_fill_findings({})

        assert result["success"] is True
        assert result["items_filled"] == 2
        assert result["matches_made"] == 2

        # Check responses were updated
        responses = checklist_agent._current_checklist.responses
        resp_ia1 = next(r for r in responses if r.item_number == "I.A.1")
        assert resp_ia1.compliance_status == ComplianceStatus.COMPLIANT
        assert resp_ia1.response_status == ChecklistResponseStatus.AUTO_FILLED

        resp_ic1 = next(r for r in responses if r.item_number == "I.C.1")
        assert resp_ic1.compliance_status == ComplianceStatus.NON_COMPLIANT
        assert resp_ic1.response_status == ChecklistResponseStatus.NEEDS_REVIEW

    def test_auto_fill_no_checklist(self, checklist_agent):
        """Test error when no checklist loaded."""
        result = checklist_agent._tool_auto_fill_findings({})
        assert "error" in result


class TestUpdateResponse:
    """Tests for update_item_response tool."""

    @patch("src.core.standards_store.StandardsStore")
    def test_update_response(self, mock_store_class, checklist_agent, mock_standards_library):
        """Test updating a checklist response."""
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "std_test",
        })

        result = checklist_agent._tool_update_response({
            "item_number": "I.A.1",
            "compliance_status": "compliant",
            "narrative_response": "Custom narrative",
        })

        assert result["success"] is True

        response = next(
            r for r in checklist_agent._current_checklist.responses
            if r.item_number == "I.A.1"
        )
        assert response.compliance_status == ComplianceStatus.COMPLIANT
        assert response.narrative_response == "Custom narrative"


class TestSaveChecklist:
    """Tests for save_checklist tool."""

    @patch("src.core.standards_store.StandardsStore")
    def test_save_checklist(self, mock_store_class, checklist_agent, mock_workspace_manager, mock_standards_library):
        """Test saving checklist to workspace."""
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "std_test",
        })

        result = checklist_agent._tool_save_checklist({"mark_complete": True})

        assert result["success"] is True
        assert result["status"] == "auto_fill_complete"
        mock_workspace_manager.save_file.assert_called_once()


class TestGetSummary:
    """Tests for get_checklist_summary tool."""

    @patch("src.core.standards_store.StandardsStore")
    def test_get_summary(self, mock_store_class, checklist_agent, mock_standards_library):
        """Test getting checklist summary."""
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        checklist_agent._tool_load_template({
            "institution_id": "inst_test",
            "standards_library_id": "std_test",
        })

        # Set some statuses
        for resp in checklist_agent._current_checklist.responses[:2]:
            resp.compliance_status = ComplianceStatus.COMPLIANT
            resp.response_status = ChecklistResponseStatus.AUTO_FILLED

        result = checklist_agent._tool_get_summary({})

        assert result["total_items"] == 3
        assert result["items_completed"] == 2
        assert result["items_compliant"] == 2
        assert "by_category" in result
        assert "Mission" in result["by_category"]


class TestWorkflow:
    """Tests for workflow methods."""

    @patch("src.core.standards_store.StandardsStore")
    def test_run_auto_fill_workflow(self, mock_store_class, checklist_agent, mock_workspace_manager, mock_standards_library):
        """Test complete auto-fill workflow."""
        mock_store = MagicMock()
        mock_store.get.return_value = mock_standards_library
        mock_store_class.return_value = mock_store

        # Mock audit data with one audit
        mock_workspace_manager.list_audits.return_value = [
            {"id": "audit_1", "status": "completed"}
        ]
        mock_workspace_manager.load_file.return_value = {
            "id": "audit_1",
            "findings": [
                {
                    "id": "find_1",
                    "audit_id": "audit_1",
                    "item_number": "I.A.1",
                    "status": "compliant",
                    "severity": "informational",
                    "regulatory_source": "accreditor",
                    "evidence_in_document": "Mission found",
                }
            ]
        }

        result = checklist_agent.run_auto_fill(
            institution_id="inst_test",
            standards_library_id="std_test",
            name="Test Checklist",
        )

        # Workflow should complete and return summary
        assert "total_items" in result
        assert result["total_items"] == 3
