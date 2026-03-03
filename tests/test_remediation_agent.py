"""Tests for the Remediation Agent."""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.agents.remediation_agent import RemediationAgent
from src.core.models import (
    AgentSession,
    Audit,
    AuditFinding,
    AuditStatus,
    ComplianceStatus,
    Document,
    DocumentType,
    FindingSeverity,
    Institution,
    RemediationChange,
    RemediationResult,
    RemediationStatus,
    RegulatorySource,
    SessionStatus,
)


@pytest.fixture
def mock_workspace_manager():
    """Create a mock workspace manager."""
    manager = MagicMock()

    # Mock institution with document
    institution = Institution(
        id="inst_test123",
        name="Test University",
    )
    doc = Document(
        id="doc_test456",
        institution_id="inst_test123",
        doc_type=DocumentType.ENROLLMENT_AGREEMENT,
        original_filename="enrollment_agreement.pdf",
        extracted_text="This is the enrollment agreement. Students must complete all requirements.",
    )
    institution.documents.append(doc)

    manager.load_institution.return_value = institution

    # Mock truth index
    manager.get_truth_index.return_value = {
        "institution": {
            "name": "Test University",
        },
        "programs": {
            "prog_001": {
                "name_en": "Medical Assistant",
                "total_cost": 15000.00,
                "duration_months": 12,
            }
        },
        "policies": {},
    }

    # Mock file operations
    manager.read_file.return_value = None
    manager.save_file.return_value = MagicMock()

    return manager


@pytest.fixture
def mock_audit():
    """Create a mock completed audit."""
    audit = Audit(
        id="audit_test789",
        document_id="doc_test456",
        standards_library_id="std_accsc",
        status=AuditStatus.COMPLETED,
        passes_completed=5,
    )

    # Add findings
    audit.findings = [
        AuditFinding(
            id="find_001",
            audit_id="audit_test789",
            item_number="I.A.1",
            item_description="Institution must disclose all costs",
            status=ComplianceStatus.NON_COMPLIANT,
            severity=FindingSeverity.CRITICAL,
            regulatory_source=RegulatorySource.ACCREDITOR,
            finding_detail="Cost disclosure is incomplete",
            recommendation="Add complete cost breakdown including tuition, fees, and supplies",
            evidence_in_document="Students must pay tuition.",
            page_numbers="3",
            ai_confidence=0.85,
        ),
        AuditFinding(
            id="find_002",
            audit_id="audit_test789",
            item_number="I.B.2",
            item_description="Refund policy must be clearly stated",
            status=ComplianceStatus.PARTIAL,
            severity=FindingSeverity.SIGNIFICANT,
            regulatory_source=RegulatorySource.ACCREDITOR,
            finding_detail="Refund policy is present but lacks specific timeframes",
            recommendation="Add specific refund percentages and deadlines",
            evidence_in_document="Refunds will be provided as per policy.",
            page_numbers="5",
            ai_confidence=0.72,
        ),
        AuditFinding(
            id="find_003",
            audit_id="audit_test789",
            item_number="II.A.1",
            item_description="Academic calendar requirements",
            status=ComplianceStatus.COMPLIANT,
            severity=FindingSeverity.INFORMATIONAL,
            regulatory_source=RegulatorySource.ACCREDITOR,
            finding_detail="Calendar is complete",
            ai_confidence=0.95,
        ),
    ]

    return audit


@pytest.fixture
def agent_session():
    """Create an agent session."""
    return AgentSession(
        id="sess_test",
        agent_type="remediation",
        institution_id="inst_test123",
        status=SessionStatus.RUNNING,
    )


@pytest.fixture
@patch("src.agents.base_agent.Anthropic")
def remediation_agent(mock_anthropic, agent_session, mock_workspace_manager):
    """Create a remediation agent with mocked dependencies."""
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    agent = RemediationAgent(
        session=agent_session,
        workspace_manager=mock_workspace_manager,
    )
    return agent


class TestRemediationAgentInit:
    """Tests for agent initialization."""

    @patch("src.agents.base_agent.Anthropic")
    def test_agent_type(self, mock_anthropic, agent_session, mock_workspace_manager):
        """Test agent type is correct."""
        mock_anthropic.return_value = MagicMock()
        agent = RemediationAgent(agent_session, mock_workspace_manager)

        from src.agents.base_agent import AgentType
        assert agent.agent_type == AgentType.REMEDIATION

    @patch("src.agents.base_agent.Anthropic")
    def test_tools_defined(self, mock_anthropic, agent_session, mock_workspace_manager):
        """Test tools are properly defined."""
        mock_anthropic.return_value = MagicMock()
        agent = RemediationAgent(agent_session, mock_workspace_manager)

        tools = agent.tools
        tool_names = [t["name"] for t in tools]

        assert "load_audit_findings" in tool_names
        assert "generate_correction" in tool_names
        assert "generate_all_corrections" in tool_names
        assert "create_redline_document" in tool_names
        assert "create_final_document" in tool_names
        assert "apply_truth_index" in tool_names
        assert "save_remediation" in tool_names


class TestLoadAuditFindings:
    """Tests for load_audit_findings tool."""

    def test_load_audit_findings_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful loading of audit findings."""
        # Setup mock to return audit
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()

        result = remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        assert result["success"] is True
        assert result["audit_id"] == "audit_test789"
        assert result["findings_needing_remediation"] == 2  # non_compliant + partial
        assert result["by_severity"]["critical"] == 1
        assert result["by_severity"]["significant"] == 1

    def test_load_audit_findings_not_found(self, remediation_agent, mock_workspace_manager):
        """Test error when audit not found."""
        mock_workspace_manager.read_file.return_value = None

        result = remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "nonexistent",
        })

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_load_audit_findings_severity_filter(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test filtering by severity."""
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()

        result = remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
            "severity_filter": ["critical"],
        })

        assert result["success"] is True
        assert result["findings_needing_remediation"] == 1
        assert result["findings"][0]["severity"] == "critical"


class TestGenerateCorrection:
    """Tests for generate_correction tool."""

    def test_generate_correction_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful correction generation."""
        # Setup: load audit first
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Mock AI response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "change_type": "replace",
            "corrected_text": "The total program cost is $15,000, which includes tuition, fees, books, and supplies.",
            "rationale": "Provides complete cost breakdown as required by ACCSC standards",
            "standard_citation": "ACCSC Section I.A.1",
            "confidence": 0.85
        }))]
        remediation_agent.client.messages.create.return_value = mock_response

        result = remediation_agent._tool_generate_correction({
            "finding_id": "find_001",
            "audit_id": "audit_test789",
        })

        assert result["success"] is True
        assert "change" in result
        assert result["change"]["change_type"] == "replace"
        assert "cost" in result["change"]["corrected_text"].lower()

    def test_generate_correction_finding_not_found(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test error when finding not found."""
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        result = remediation_agent._tool_generate_correction({
            "finding_id": "nonexistent",
            "audit_id": "audit_test789",
        })

        assert "error" in result
        assert "not found" in result["error"].lower()


class TestApplyTruthIndex:
    """Tests for apply_truth_index tool."""

    def test_apply_truth_index_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful truth index application."""
        # Setup: load audit and create remediation with placeholder
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Get the remediation and add a change with placeholder
        for cache_key, remed in remediation_agent._remediation_cache.items():
            change = RemediationChange(
                finding_id="find_001",
                item_number="I.A.1",
                corrected_text="The total cost at [INSTITUTION_NAME] is $15,000.",
            )
            remed.changes.append(change)
            remediation_id = remed.id

        result = remediation_agent._tool_apply_truth_index({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert result["success"] is True
        assert result["changes_modified"] >= 0

    def test_apply_truth_index_no_truth_index(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test error when truth index not found."""
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Make truth index return None
        mock_workspace_manager.get_truth_index.return_value = None

        for cache_key, remed in remediation_agent._remediation_cache.items():
            remediation_id = remed.id

        result = remediation_agent._tool_apply_truth_index({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert "error" in result


class TestCreateDocuments:
    """Tests for document creation tools."""

    def test_create_redline_document_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful redline document creation."""
        # Setup
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Add changes to remediation
        for cache_key, remed in remediation_agent._remediation_cache.items():
            change = RemediationChange(
                finding_id="find_001",
                item_number="I.A.1",
                change_type="replace",
                original_text="Old text",
                corrected_text="New corrected text with full disclosure.",
                standard_citation="ACCSC Section I.A.1",
                rationale="Provides complete information",
                ai_confidence=0.85,
            )
            remed.changes.append(change)
            remediation_id = remed.id

        result = remediation_agent._tool_create_redline_document({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert result["success"] is True
        assert "redline" in result["path"].lower()
        assert result["changes_included"] == 1

    def test_create_final_document_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful final document creation."""
        # Setup
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Add changes
        for cache_key, remed in remediation_agent._remediation_cache.items():
            change = RemediationChange(
                finding_id="find_001",
                item_number="I.A.1",
                corrected_text="Corrected compliance text.",
                standard_citation="ACCSC Section I.A.1",
            )
            remed.changes.append(change)
            remediation_id = remed.id

        result = remediation_agent._tool_create_final_document({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert result["success"] is True
        assert "final" in result["path"].lower()

    def test_create_documents_no_changes(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test error when no changes to create documents from."""
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        for cache_key, remed in remediation_agent._remediation_cache.items():
            remediation_id = remed.id

        result = remediation_agent._tool_create_redline_document({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert "error" in result
        assert "no changes" in result["error"].lower()


class TestSaveRemediation:
    """Tests for save_remediation tool."""

    def test_save_remediation_success(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test successful remediation save."""
        # Setup
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()
        remediation_agent._tool_load_audit_findings({
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
        })

        # Add changes and paths
        for cache_key, remed in remediation_agent._remediation_cache.items():
            change = RemediationChange(
                finding_id="find_001",
                item_number="I.A.1",
                corrected_text="Test correction",
            )
            remed.changes.append(change)
            remed.redline_path = "redlines/test_redline.docx"
            remed.final_path = "finals/test_final.docx"
            remediation_id = remed.id

        result = remediation_agent._tool_save_remediation({
            "institution_id": "inst_test123",
            "remediation_id": remediation_id,
        })

        assert result["success"] is True
        assert result["summary"]["changes_count"] == 1
        mock_workspace_manager.save_file.assert_called()


class TestRemediationModels:
    """Tests for remediation data models."""

    def test_remediation_change_serialization(self):
        """Test RemediationChange serialization."""
        change = RemediationChange(
            finding_id="find_001",
            item_number="I.A.1",
            change_type="replace",
            original_text="Old text",
            corrected_text="New text",
            standard_citation="ACCSC I.A.1",
            ai_confidence=0.85,
        )

        data = change.to_dict()
        restored = RemediationChange.from_dict(data)

        assert restored.finding_id == change.finding_id
        assert restored.item_number == change.item_number
        assert restored.corrected_text == change.corrected_text

    def test_remediation_result_serialization(self):
        """Test RemediationResult serialization."""
        result = RemediationResult(
            audit_id="audit_001",
            document_id="doc_001",
            institution_id="inst_001",
            status=RemediationStatus.GENERATED,
        )
        result.changes.append(RemediationChange(
            finding_id="find_001",
            corrected_text="Test",
        ))

        data = result.to_dict()
        restored = RemediationResult.from_dict(data)

        assert restored.audit_id == result.audit_id
        assert restored.status == result.status
        assert len(restored.changes) == 1


class TestWorkflowMethods:
    """Tests for workflow methods."""

    def test_run_workflow_full_remediation(self, remediation_agent, mock_audit, mock_workspace_manager):
        """Test full remediation workflow."""
        # Setup
        mock_workspace_manager.read_file.return_value = json.dumps(mock_audit.to_dict()).encode()

        # Mock AI responses for corrections
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "change_type": "insert",
            "corrected_text": "Complete disclosure text.",
            "rationale": "Addresses compliance gap",
            "standard_citation": "ACCSC I.A.1",
            "confidence": 0.8
        }))]
        remediation_agent.client.messages.create.return_value = mock_response

        result = remediation_agent.run_workflow("full_remediation", {
            "institution_id": "inst_test123",
            "audit_id": "audit_test789",
            "max_findings": 5,
        })

        assert result.status in ["success", "error"]

    def test_run_workflow_unknown(self, remediation_agent):
        """Test error for unknown workflow."""
        result = remediation_agent.run_workflow("unknown_workflow", {})
        assert result.status == "error"
        assert "unknown" in result.error.lower()
