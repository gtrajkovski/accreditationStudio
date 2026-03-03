"""Tests for the Findings Agent."""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.findings_agent import (
    FindingsAgent,
    AggregatedFinding,
    FindingsReport,
)
from src.core.models import (
    AgentSession,
    SessionStatus,
    ComplianceStatus,
    FindingSeverity,
    RegulatorySource,
)


@pytest.fixture
def mock_workspace_manager():
    manager = MagicMock()
    manager.list_audits.return_value = [{"id": "audit_1", "status": "completed"}]
    manager.load_file.return_value = {
        "id": "audit_1",
        "findings": [
            {
                "id": "find_1",
                "item_number": "I.A.1",
                "item_description": "Mission statement",
                "status": "non_compliant",
                "severity": "critical",
                "regulatory_source": "accreditor",
                "evidence_in_document": "No mission found",
            },
            {
                "id": "find_2",
                "item_number": "I.A.1",
                "item_description": "Mission statement",
                "status": "partial",
                "severity": "critical",
                "regulatory_source": "accreditor",
                "evidence_in_document": "Partial mission",
            },
        ],
    }
    manager.save_file.return_value = None
    return manager


@pytest.fixture
def agent_session():
    return AgentSession(
        id="sess_test",
        agent_type="findings",
        institution_id="inst_test",
        status=SessionStatus.RUNNING,
    )


@pytest.fixture
@patch("src.agents.base_agent.Anthropic")
def findings_agent(mock_anthropic, agent_session, mock_workspace_manager):
    mock_anthropic.return_value = MagicMock()
    return FindingsAgent(agent_session, mock_workspace_manager)


class TestModels:
    def test_aggregated_finding_serialization(self):
        finding = AggregatedFinding(
            item_number="I.A.1",
            severity=FindingSeverity.CRITICAL,
            status=ComplianceStatus.NON_COMPLIANT,
            occurrence_count=3,
        )
        data = finding.to_dict()
        assert data["item_number"] == "I.A.1"
        assert data["severity"] == "critical"
        assert data["occurrence_count"] == 3

    def test_findings_report_serialization(self):
        report = FindingsReport(
            institution_id="inst_test",
            name="Test Report",
            total_findings=5,
        )
        data = report.to_dict()
        assert data["institution_id"] == "inst_test"
        assert data["total_findings"] == 5


class TestLoadFindings:
    def test_load_findings(self, findings_agent):
        result = findings_agent._tool_load_findings({"institution_id": "inst_test"})
        assert result["success"] is True
        assert result["findings_loaded"] == 2

    def test_load_with_status_filter(self, findings_agent, mock_workspace_manager):
        result = findings_agent._tool_load_findings({
            "institution_id": "inst_test",
            "status_filter": ["non_compliant"],
        })
        assert result["success"] is True
        assert result["findings_loaded"] == 1


class TestAggregate:
    def test_aggregate_findings(self, findings_agent):
        findings_agent._tool_load_findings({"institution_id": "inst_test"})
        result = findings_agent._tool_aggregate({})
        assert result["success"] is True
        assert result["aggregated_findings"] == 1  # Both findings share item_number


class TestPriorities:
    def test_calculate_priorities(self, findings_agent):
        findings_agent._tool_load_findings({"institution_id": "inst_test"})
        findings_agent._tool_aggregate({})
        result = findings_agent._tool_calculate_priorities({})
        assert result["success"] is True
        assert result["top_priority"] is not None
        assert result["top_priority"]["priority_score"] > 0


class TestSaveReport:
    def test_save_report(self, findings_agent, mock_workspace_manager):
        findings_agent._tool_load_findings({"institution_id": "inst_test"})
        findings_agent._tool_aggregate({})
        result = findings_agent._tool_save_report({"name": "Test Report"})
        assert result["success"] is True
        mock_workspace_manager.save_file.assert_called_once()
