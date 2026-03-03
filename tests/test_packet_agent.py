"""Tests for the Packet Agent.

Tests packet assembly, validation, and export functionality.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.packet_agent import PacketAgent
from src.agents.base_agent import AgentType
from src.core.models import (
    AgentSession,
    PacketStatus,
    PacketSectionType,
    SubmissionType,
)


@pytest.fixture
def mock_workspace():
    """Create a mock workspace manager."""
    manager = MagicMock()

    # Mock findings report
    findings_report = {
        "id": "frpt_test123",
        "findings": [
            {
                "id": "find_001",
                "item_number": "I.A.1",
                "item_description": "Mission Statement",
                "severity": "significant",
                "status": "non_compliant",
            },
            {
                "id": "find_002",
                "item_number": "I.B.2",
                "item_description": "Program Objectives",
                "severity": "advisory",
                "status": "partial",
            },
        ],
    }

    def load_file(inst_id, path):
        if "findings" in path and "frpt_test123" in path:
            return findings_report
        return None

    manager.load_file = MagicMock(side_effect=load_file)
    manager.save_file = MagicMock(return_value=True)

    return manager


@pytest.fixture
def agent(mock_workspace):
    """Create a packet agent instance."""
    session = AgentSession(
        agent_type="packet",
        institution_id="inst_test",
    )
    return PacketAgent(session, workspace_manager=mock_workspace)


class TestPacketAgentInit:
    """Tests for agent initialization."""

    def test_agent_type(self, agent):
        """Test agent type is correct."""
        assert agent.agent_type == AgentType.PACKET

    def test_has_tools(self, agent):
        """Test agent has tools defined."""
        tools = agent.tools
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "create_packet" in tool_names
        assert "add_narrative_section" in tool_names
        assert "add_exhibit" in tool_names
        assert "validate_packet" in tool_names
        assert "export_docx" in tool_names
        assert "export_zip" in tool_names

    def test_system_prompt(self, agent):
        """Test system prompt is defined."""
        assert len(agent.system_prompt) > 100
        assert "Packet Agent" in agent.system_prompt


class TestCreatePacket:
    """Tests for packet creation."""

    def test_create_packet_success(self, agent):
        """Test successful packet creation."""
        result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "ACCSC Renewal 2024",
            "accrediting_body": "ACCSC",
            "submission_type": "renewal",
            "description": "Annual renewal submission",
        })

        assert result["success"]
        assert "packet_id" in result
        assert result["name"] == "ACCSC Renewal 2024"
        assert result["accrediting_body"] == "ACCSC"
        assert result["submission_type"] == "renewal"

    def test_create_packet_missing_fields(self, agent):
        """Test packet creation fails with missing fields."""
        result = agent._tool_create_packet({
            "institution_id": "inst_001",
        })

        assert "error" in result

    def test_create_packet_default_type(self, agent):
        """Test packet creation with default submission type."""
        result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Response to Team Report",
            "accrediting_body": "SACSCOC",
        })

        assert result["success"]
        assert result["submission_type"] == "response_to_findings"


class TestLoadFindings:
    """Tests for loading findings into packet."""

    def test_load_findings_success(self, agent, mock_workspace):
        """Test loading findings from report."""
        # Create packet first
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Load findings
        result = agent._tool_load_findings({
            "packet_id": packet_id,
            "findings_report_id": "frpt_test123",
        })

        assert result["success"]
        assert result["findings_loaded"] == 2
        assert result["sections_created"] == 2
        assert result["severity_breakdown"]["significant"] == 1
        assert result["severity_breakdown"]["advisory"] == 1

    def test_load_findings_with_filter(self, agent, mock_workspace):
        """Test loading findings with severity filter."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_load_findings({
            "packet_id": packet_id,
            "findings_report_id": "frpt_test123",
            "severity_filter": ["significant"],
        })

        assert result["success"]
        assert result["findings_loaded"] == 1
        assert result["sections_created"] == 1

    def test_load_findings_packet_not_found(self, agent):
        """Test loading findings with invalid packet."""
        result = agent._tool_load_findings({
            "packet_id": "invalid_id",
            "findings_report_id": "frpt_test123",
        })

        assert "error" in result


class TestAddSections:
    """Tests for adding sections to packet."""

    def test_add_narrative_section(self, agent):
        """Test adding a narrative section."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_add_narrative({
            "packet_id": packet_id,
            "title": "Response to Finding I.A.1",
            "content": "The institution has addressed this finding by...",
            "finding_id": "find_001",
            "standard_refs": ["I.A.1"],
            "evidence_refs": ["doc_001", "doc_002"],
        })

        assert result["success"]
        assert "section_id" in result
        assert result["title"] == "Response to Finding I.A.1"
        assert result["word_count"] > 0

    def test_add_exhibit(self, agent):
        """Test adding an exhibit."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_add_exhibit({
            "packet_id": packet_id,
            "exhibit_number": "A-1",
            "title": "Catalog 2024",
            "description": "Current institutional catalog",
            "document_id": "doc_catalog_001",
            "file_path": "catalog/catalog_2024.pdf",
            "standard_refs": ["I.A.1", "I.B.2"],
        })

        assert result["success"]
        assert result["exhibit_number"] == "A-1"
        assert result["total_exhibits"] == 1


class TestCoverAndIndex:
    """Tests for cover page and evidence index."""

    def test_generate_cover_page(self, agent):
        """Test cover page generation."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
            "submission_type": "renewal",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_generate_cover({
            "packet_id": packet_id,
            "institution_name": "Test Technical Institute",
            "submission_date": "2024-06-15",
            "contact_name": "Jane Doe",
            "contact_title": "Director of Compliance",
        })

        assert result["success"]
        assert result["institution_name"] == "Test Technical Institute"
        assert "section_id" in result

    def test_build_evidence_index(self, agent):
        """Test evidence index building."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Add some sections with evidence
        agent._tool_add_narrative({
            "packet_id": packet_id,
            "title": "Response 1",
            "content": "Content here",
            "standard_refs": ["I.A.1"],
            "evidence_refs": ["doc_001"],
        })

        agent._tool_add_exhibit({
            "packet_id": packet_id,
            "exhibit_number": "A-1",
            "title": "Exhibit 1",
            "file_path": "exhibits/ex1.pdf",
            "standard_refs": ["I.A.1", "I.B.2"],
        })

        result = agent._tool_build_evidence_index({"packet_id": packet_id})

        assert result["success"]
        assert result["standards_indexed"] >= 1


class TestValidation:
    """Tests for packet validation."""

    def test_validate_empty_packet(self, agent):
        """Test validation of empty packet."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_validate({"packet_id": packet_id})

        assert result["success"]
        # Empty packet should be valid (no content to validate)
        assert result["is_valid"]

    def test_validate_missing_content(self, agent, mock_workspace):
        """Test validation catches missing content."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Load findings (creates sections without content)
        agent._tool_load_findings({
            "packet_id": packet_id,
            "findings_report_id": "frpt_test123",
        })

        result = agent._tool_validate({"packet_id": packet_id})

        assert result["success"]
        assert not result["is_valid"]
        assert result["errors"] > 0

    def test_validate_complete_packet(self, agent, mock_workspace):
        """Test validation passes for complete packet."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Add complete narrative
        agent._tool_add_narrative({
            "packet_id": packet_id,
            "title": "Response",
            "content": "This is a complete response to the finding.",
            "standard_refs": ["I.A.1"],
            "evidence_refs": ["doc_001"],
        })

        result = agent._tool_validate({"packet_id": packet_id})

        assert result["success"]
        assert result["is_valid"]


class TestExport:
    """Tests for packet export."""

    def test_export_docx(self, agent):
        """Test DOCX export."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Add content
        agent._tool_generate_cover({
            "packet_id": packet_id,
            "institution_name": "Test Institute",
        })

        agent._tool_add_narrative({
            "packet_id": packet_id,
            "title": "Response Section",
            "content": "This is the response content.",
            "standard_refs": ["I.A.1"],
        })

        # Validate first
        agent._tool_validate({"packet_id": packet_id})

        # Export
        result = agent._tool_export_docx({"packet_id": packet_id})

        assert result["success"]
        assert "path" in result
        assert result["path"].endswith(".docx")
        assert result["sections_included"] > 0

    def test_export_requires_validation(self, agent, mock_workspace):
        """Test that export requires validation."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        # Load findings without filling content
        agent._tool_load_findings({
            "packet_id": packet_id,
            "findings_report_id": "frpt_test123",
        })

        # Validate (should fail)
        agent._tool_validate({"packet_id": packet_id})

        # Export should fail
        result = agent._tool_export_docx({"packet_id": packet_id})

        assert "error" in result

    def test_export_zip(self, agent):
        """Test ZIP export."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        agent._tool_add_narrative({
            "packet_id": packet_id,
            "title": "Response",
            "content": "Content here",
        })

        agent._tool_validate({"packet_id": packet_id})

        result = agent._tool_export_zip({"packet_id": packet_id})

        assert result["success"]
        assert result["path"].endswith(".zip")


class TestPacketSummary:
    """Tests for packet summary."""

    def test_get_summary(self, agent, mock_workspace):
        """Test getting packet summary."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
            "submission_type": "response_to_findings",
        })
        packet_id = create_result["packet_id"]

        # Load findings
        agent._tool_load_findings({
            "packet_id": packet_id,
            "findings_report_id": "frpt_test123",
        })

        # Add exhibit
        agent._tool_add_exhibit({
            "packet_id": packet_id,
            "exhibit_number": "A-1",
            "title": "Evidence Doc",
            "standard_refs": ["I.A.1"],
        })

        result = agent._tool_get_summary({"packet_id": packet_id})

        assert result["name"] == "Test Packet"
        assert result["accrediting_body"] == "ACCSC"
        assert result["total_sections"] == 2  # From findings
        assert result["total_exhibits"] == 1


class TestSavePacket:
    """Tests for packet persistence."""

    def test_save_packet(self, agent, mock_workspace):
        """Test saving packet to workspace."""
        create_result = agent._tool_create_packet({
            "institution_id": "inst_001",
            "name": "Test Packet",
            "accrediting_body": "ACCSC",
        })
        packet_id = create_result["packet_id"]

        result = agent._tool_save({"packet_id": packet_id})

        assert result["success"]
        assert "path" in result
        mock_workspace.save_file.assert_called()


class TestWorkflow:
    """Tests for workflow methods."""

    def test_assemble_packet_workflow(self, agent, mock_workspace):
        """Test the assemble_packet workflow."""
        result = agent.assemble_packet(
            institution_id="inst_001",
            name="Assembled Packet",
            accrediting_body="ACCSC",
            findings_report_id="frpt_test123",
        )

        assert "packet_id" in result
        assert result["name"] == "Assembled Packet"
        assert result["findings_addressed"] >= 0

    def test_run_workflow(self, agent, mock_workspace):
        """Test run_workflow method."""
        result = agent.run_workflow("assemble_packet", {
            "institution_id": "inst_001",
            "name": "Workflow Packet",
            "accrediting_body": "ACCSC",
            "findings_report_id": "frpt_test123",
        })

        assert result.success
        assert result.data is not None
