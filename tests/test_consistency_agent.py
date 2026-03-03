"""Tests for the Policy Consistency Agent."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.policy_consistency import (
    PolicyConsistencyAgent,
    Inconsistency,
    InconsistencySeverity,
    ConsistencyReport,
    POLICY_CATEGORIES,
)
from src.core.models import AgentSession, SessionStatus, Institution, Document, DocumentType


@pytest.fixture
def mock_workspace_manager():
    """Create mock workspace manager."""
    manager = MagicMock()

    institution = Institution(id="inst_test", name="Test University")
    doc1 = Document(id="doc_catalog", doc_type=DocumentType.CATALOG,
                    original_filename="catalog.pdf",
                    extracted_text="Refund policy: 100% refund within 3 days. Tuition: $15,000.")
    doc2 = Document(id="doc_ea", doc_type=DocumentType.ENROLLMENT_AGREEMENT,
                    original_filename="enrollment.pdf",
                    extracted_text="Refund policy: 100% refund within 5 business days. Tuition: $15,500.")
    institution.documents = [doc1, doc2]

    manager.load_institution.return_value = institution
    manager.get_truth_index.return_value = {
        "institution": {"name": "Test University"},
        "programs": {"prog_001": {"total_cost": 15000, "duration_months": 12}},
    }
    manager.save_file.return_value = MagicMock()

    return manager


@pytest.fixture
def agent_session():
    """Create agent session."""
    return AgentSession(
        id="sess_test",
        agent_type="policy_consistency",
        institution_id="inst_test",
        status=SessionStatus.RUNNING,
    )


@pytest.fixture
@patch("src.agents.base_agent.Anthropic")
def consistency_agent(mock_anthropic, agent_session, mock_workspace_manager):
    """Create consistency agent."""
    mock_anthropic.return_value = MagicMock()
    return PolicyConsistencyAgent(agent_session, mock_workspace_manager)


class TestModels:
    """Tests for data models."""

    def test_inconsistency_serialization(self):
        """Test Inconsistency serialization."""
        inc = Inconsistency(
            category="refund",
            severity=InconsistencySeverity.CRITICAL,
            description="Refund timeframes differ",
            documents_involved=[
                {"document_id": "doc1", "value": "3 days"},
                {"document_id": "doc2", "value": "5 days"},
            ],
            recommended_value="3 business days",
            ai_confidence=0.85,
        )

        data = inc.to_dict()
        assert data["category"] == "refund"
        assert data["severity"] == "critical"
        assert len(data["documents_involved"]) == 2

    def test_consistency_report_serialization(self):
        """Test ConsistencyReport serialization."""
        report = ConsistencyReport(
            institution_id="inst_test",
            documents_scanned=5,
            policies_checked=["refund", "tuition"],
        )
        report.inconsistencies.append(Inconsistency(
            category="refund",
            severity=InconsistencySeverity.CRITICAL,
        ))

        data = report.to_dict()
        assert data["institution_id"] == "inst_test"
        assert data["inconsistency_count"] == 1
        assert data["by_severity"]["critical"] == 1


class TestAgentInit:
    """Tests for agent initialization."""

    def test_agent_type(self, consistency_agent):
        """Test agent type."""
        from src.agents.base_agent import AgentType
        assert consistency_agent.agent_type == AgentType.POLICY_CONSISTENCY

    def test_tools_defined(self, consistency_agent):
        """Test tools are defined."""
        tools = consistency_agent.tools
        tool_names = [t["name"] for t in tools]

        assert "check_policy_consistency" in tool_names
        assert "run_full_consistency_scan" in tool_names
        assert "compare_to_truth_index" in tool_names
        assert "analyze_document_pair" in tool_names
        assert "generate_consistency_report" in tool_names


class TestCheckPolicy:
    """Tests for check_policy_consistency tool."""

    @patch("src.search.get_search_service")
    def test_check_policy_with_results(self, mock_search, consistency_agent):
        """Test policy check with search results."""
        # Mock search results
        mock_result = MagicMock()
        mock_result.chunk.document_id = "doc_catalog"
        mock_result.chunk.text_anonymized = "Refund: 100% within 3 days"
        mock_result.chunk.page_number = 5
        mock_result.score = 0.9

        mock_result2 = MagicMock()
        mock_result2.chunk.document_id = "doc_ea"
        mock_result2.chunk.text_anonymized = "Refund: 100% within 5 days"
        mock_result2.chunk.page_number = 2
        mock_result2.score = 0.85

        mock_service = MagicMock()
        mock_service.search.return_value = [mock_result, mock_result2]
        mock_search.return_value = mock_service

        # Mock AI response
        consistency_agent.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='[{"description": "Different refund periods", "severity": "critical", "doc1": "doc_catalog", "doc1_value": "3 days", "doc2": "doc_ea", "doc2_value": "5 days", "recommended_value": "3 business days", "confidence": 0.9}]')]
        )

        result = consistency_agent._tool_check_policy({
            "institution_id": "inst_test",
            "policy_type": "refund",
        })

        assert result["success"] is True
        assert result["policy_type"] == "refund"
        assert result["documents_found"] >= 1

    def test_check_policy_invalid_type(self, consistency_agent):
        """Test error for invalid policy type."""
        result = consistency_agent._tool_check_policy({
            "institution_id": "inst_test",
            "policy_type": "invalid_type",
        })

        assert "error" in result


class TestTruthIndexComparison:
    """Tests for compare_to_truth_index tool."""

    @patch("src.search.get_search_service")
    def test_compare_truth_index(self, mock_search, consistency_agent):
        """Test truth index comparison."""
        mock_service = MagicMock()
        mock_service.search.return_value = []
        mock_search.return_value = mock_service

        result = consistency_agent._tool_compare_truth_index({
            "institution_id": "inst_test",
            "value_categories": ["institution_name"],
        })

        assert result["success"] is True
        assert "institution_name" in result["categories_checked"]

    def test_compare_no_truth_index(self, consistency_agent, mock_workspace_manager):
        """Test error when no truth index."""
        mock_workspace_manager.get_truth_index.return_value = None

        result = consistency_agent._tool_compare_truth_index({
            "institution_id": "inst_test",
        })

        assert "error" in result


class TestGenerateReport:
    """Tests for generate_consistency_report tool."""

    def test_generate_report(self, consistency_agent):
        """Test report generation."""
        # Add some data to report cache
        report = consistency_agent._get_or_create_report("inst_test")
        report.policies_checked = ["refund", "tuition"]
        report.inconsistencies.append(Inconsistency(
            category="refund",
            severity=InconsistencySeverity.SIGNIFICANT,
        ))

        result = consistency_agent._tool_generate_report({
            "institution_id": "inst_test",
        })

        assert result["success"] is True
        assert "report" in result
        assert result["report"]["inconsistency_count"] == 1


class TestWorkflows:
    """Tests for workflow methods."""

    @patch("src.search.get_search_service")
    def test_full_scan_workflow(self, mock_search, consistency_agent):
        """Test full scan workflow."""
        mock_service = MagicMock()
        mock_service.search.return_value = []
        mock_search.return_value = mock_service

        result = consistency_agent.run_workflow("full_scan", {
            "institution_id": "inst_test",
            "policy_types": ["refund"],
        })

        assert result.status == "success"

    def test_unknown_workflow(self, consistency_agent):
        """Test error for unknown workflow."""
        result = consistency_agent.run_workflow("unknown", {})
        assert result.status == "error"


class TestPolicyCategories:
    """Tests for policy category definitions."""

    def test_all_categories_defined(self):
        """Test all expected categories exist."""
        expected = ["refund", "cancellation", "tuition", "program_length",
                   "sap", "attendance", "grievance", "contact"]
        for cat in expected:
            assert cat in POLICY_CATEGORIES
            assert "terms" in POLICY_CATEGORIES[cat]
            assert "regulatory_weight" in POLICY_CATEGORIES[cat]
