"""Tests for the Narrative Agent."""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.narrative_agent import NarrativeAgent, NarrativeSection
from src.core.models import AgentSession, SessionStatus


@pytest.fixture
def mock_workspace():
    manager = MagicMock()
    manager.save_file.return_value = None
    return manager


@pytest.fixture
def agent_session():
    return AgentSession(id="sess_test", agent_type="narrative", status=SessionStatus.RUNNING)


@pytest.fixture
@patch("src.agents.base_agent.Anthropic")
def narrative_agent(mock_anthropic, agent_session, mock_workspace):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="The institution demonstrates compliance through documented policies.")]
    )
    return NarrativeAgent(agent_session, mock_workspace)


class TestNarrativeSection:
    def test_serialization(self):
        section = NarrativeSection(
            section_type="issue_response",
            standard_reference="I.A.1",
            title="Test Section",
            content="Test content",
            word_count=2,
        )
        data = section.to_dict()
        assert data["section_type"] == "issue_response"
        assert data["standard_reference"] == "I.A.1"


class TestWriteIssueResponse:
    def test_generates_response(self, narrative_agent):
        result = narrative_agent._tool_write_issue_response({
            "item_number": "I.A.1",
            "finding_description": "Mission statement not published",
            "evidence_text": "Catalog page 5",
        })
        assert result["success"] is True
        assert "section_id" in result
        assert result["word_count"] > 0


class TestWriteSelfStudy:
    def test_generates_section(self, narrative_agent):
        result = narrative_agent._tool_write_self_study({
            "standard_number": "I.A",
            "standard_title": "Mission",
            "compliance_status": "compliant",
        })
        assert result["success"] is True
        assert "content" in result


class TestSetVoice:
    def test_sets_voice(self, narrative_agent):
        result = narrative_agent._tool_set_voice({
            "institution_name": "Test University",
            "voice_guidelines": "Professional and formal",
        })
        assert result["success"] is True
        assert narrative_agent._institution_voice == "Professional and formal"


class TestSaveNarratives:
    def test_saves_to_workspace(self, narrative_agent, mock_workspace):
        narrative_agent._tool_write_issue_response({
            "item_number": "I.A.1",
            "finding_description": "Test finding",
        })
        result = narrative_agent._tool_save({"institution_id": "inst_test"})
        assert result["success"] is True
        mock_workspace.save_file.assert_called_once()
