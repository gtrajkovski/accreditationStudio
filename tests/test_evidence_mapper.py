"""Tests for Evidence Mapper Agent."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from src.agents.evidence_mapper import EvidenceMapperAgent
from src.agents.base_agent import AgentType
from src.core.models import (
    AgentSession,
    EvidenceMapping,
    EvidenceMap,
    EvidenceGap,
    CrosswalkEntry,
    StandardsLibrary,
    StandardsSection,
    ChecklistItem,
    AccreditingBody,
)


@pytest.fixture
def mock_workspace_manager():
    """Create a mock workspace manager."""
    manager = MagicMock()
    manager.workspace_dir = Path("/tmp/test_workspace")
    return manager


@pytest.fixture
def mock_session():
    """Create a mock agent session."""
    return AgentSession(
        agent_type="evidence_mapper",
        institution_id="inst_test123"
    )


@pytest.fixture
def mock_search_results():
    """Create mock search results."""
    chunk1 = MagicMock()
    chunk1.id = "chunk_001"
    chunk1.document_id = "doc_001"
    chunk1.page_number = 5
    chunk1.section_header = "Refund Policy"
    chunk1.text_anonymized = "The institution maintains a refund policy that complies with all federal and state requirements. Students who withdraw within the first week receive a full refund of tuition."

    chunk2 = MagicMock()
    chunk2.id = "chunk_002"
    chunk2.document_id = "doc_002"
    chunk2.page_number = 12
    chunk2.section_header = "Financial Policies"
    chunk2.text_anonymized = "All financial policies are documented in the student handbook and reviewed annually."

    result1 = MagicMock()
    result1.chunk = chunk1
    result1.score = 0.88

    result2 = MagicMock()
    result2.chunk = chunk2
    result2.score = 0.72

    return [result1, result2]


@pytest.fixture
def mock_standards_library():
    """Create a mock standards library."""
    return StandardsLibrary(
        id="std_accsc",
        accrediting_body=AccreditingBody.ACCSC,
        name="ACCSC Substantive Standards",
        version="2023",
        sections=[
            StandardsSection(id="sec_1", number="I", title="Institutional", text=""),
            StandardsSection(id="sec_1a", number="I.A", title="Mission", text="", parent_section="sec_1"),
        ],
        checklist_items=[
            ChecklistItem(
                number="I.A.1",
                category="Mission",
                description="School has a written mission statement",
                section_reference="I.A",
                applies_to=["catalog", "policy_manual"]
            ),
            ChecklistItem(
                number="I.C.1",
                category="Financial",
                description="Tuition and fees are clearly disclosed",
                section_reference="I.C",
                applies_to=["catalog", "enrollment_agreement"]
            ),
            ChecklistItem(
                number="I.C.2",
                category="Financial",
                description="Refund policy is published",
                section_reference="I.C",
                applies_to=["catalog", "enrollment_agreement"]
            ),
        ]
    )


class TestEvidenceMapperAgent:
    """Test suite for EvidenceMapperAgent."""

    @patch("src.agents.base_agent.Anthropic")
    def test_agent_initialization(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test agent initializes correctly."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

        assert agent.agent_type == AgentType.EVIDENCE_MAPPER
        assert "Evidence Mapper Agent" in agent.system_prompt
        assert len(agent.tools) == 6  # All 6 tools

    @patch("src.agents.base_agent.Anthropic")
    def test_tools_defined(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test all tools are properly defined."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

        tool_names = [t["name"] for t in agent.tools]
        assert "search_evidence" in tool_names
        assert "map_standard_to_evidence" in tool_names
        assert "generate_crosswalk_table" in tool_names
        assert "identify_evidence_gaps" in tool_names
        assert "save_evidence_map" in tool_names
        assert "get_evidence_summary" in tool_names


class TestSearchEvidence:
    """Tests for search_evidence tool."""

    @patch("src.agents.base_agent.Anthropic")
    def test_search_evidence_success(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_search_results
    ):
        """Test successful evidence search."""
        with patch("src.search.get_search_service") as mock_get_search:
            mock_service = MagicMock()
            mock_service.search.return_value = mock_search_results
            mock_get_search.return_value = mock_service

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_search_evidence({
                "requirement_text": "refund policy requirements",
                "institution_id": "inst_test123",
                "n_results": 10
            })

            assert result["success"] is True
            assert result["evidence_found"] == 2
            assert len(result["evidence"]) == 2
            assert result["evidence"][0]["quality"] == "strong"
            assert result["evidence"][1]["quality"] == "adequate"

    @patch("src.agents.base_agent.Anthropic")
    def test_search_evidence_missing_params(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test search_evidence with missing parameters."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

        result = agent._tool_search_evidence({
            "requirement_text": "test"
            # missing institution_id
        })

        assert "error" in result

    @patch("src.agents.base_agent.Anthropic")
    def test_search_evidence_no_results(
        self, mock_anthropic,
        mock_session, mock_workspace_manager
    ):
        """Test search when no evidence found."""
        with patch("src.search.get_search_service") as mock_get_search:
            mock_service = MagicMock()
            mock_service.search.return_value = []
            mock_get_search.return_value = mock_service

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_search_evidence({
                "requirement_text": "obscure requirement",
                "institution_id": "inst_test123"
            })

            assert result["success"] is True
            assert result["evidence_found"] == 0
            assert result["evidence"] == []


class TestAssessEvidenceQuality:
    """Tests for evidence quality assessment."""

    @patch("src.agents.base_agent.Anthropic")
    def test_quality_strong(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test strong quality rating."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)
        assert agent._assess_evidence_quality(0.90) == "strong"
        assert agent._assess_evidence_quality(0.85) == "strong"

    @patch("src.agents.base_agent.Anthropic")
    def test_quality_adequate(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test adequate quality rating."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)
        assert agent._assess_evidence_quality(0.75) == "adequate"
        assert agent._assess_evidence_quality(0.70) == "adequate"

    @patch("src.agents.base_agent.Anthropic")
    def test_quality_weak(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test weak quality rating."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)
        assert agent._assess_evidence_quality(0.60) == "weak"
        assert agent._assess_evidence_quality(0.50) == "weak"

    @patch("src.agents.base_agent.Anthropic")
    def test_quality_insufficient(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test insufficient quality rating."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)
        assert agent._assess_evidence_quality(0.40) == "insufficient"
        assert agent._assess_evidence_quality(0.0) == "insufficient"


class TestMapStandardToEvidence:
    """Tests for map_standard_to_evidence tool."""

    @patch("src.agents.base_agent.Anthropic")
    def test_map_with_strong_evidence(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_search_results
    ):
        """Test mapping with strong evidence found."""
        with patch("src.search.get_search_service") as mock_get_search:
            mock_service = MagicMock()
            mock_service.search.return_value = mock_search_results
            mock_get_search.return_value = mock_service

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_map_standard_to_evidence({
                "standard_id": "I.C.2",
                "standard_text": "Refund policy is published",
                "institution_id": "inst_test123"
            })

            assert result["success"] is True
            mapping = result["mapping"]
            assert mapping["status"] == "satisfied"
            assert mapping["confidence"] == 0.9
            assert mapping["suggested_exhibit"] == "Exhibit I.C.2"
            assert mapping["gap_notes"] is None

    @patch("src.agents.base_agent.Anthropic")
    def test_map_with_no_evidence(
        self, mock_anthropic,
        mock_session, mock_workspace_manager
    ):
        """Test mapping when no evidence found."""
        with patch("src.search.get_search_service") as mock_get_search:
            mock_service = MagicMock()
            mock_service.search.return_value = []
            mock_get_search.return_value = mock_service

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_map_standard_to_evidence({
                "standard_id": "X.Y.Z",
                "standard_text": "Obscure requirement",
                "institution_id": "inst_test123"
            })

            assert result["success"] is True
            mapping = result["mapping"]
            assert mapping["status"] == "missing"
            assert mapping["confidence"] == 0.0
            assert mapping["suggested_exhibit"] is None
            assert "missing" in mapping["gap_notes"].lower()


class TestGenerateCrosswalkTable:
    """Tests for generate_crosswalk_table tool."""

    @patch("src.agents.base_agent.Anthropic")
    def test_generate_crosswalk_json(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_standards_library, mock_search_results, tmp_path
    ):
        """Test crosswalk table generation in JSON format."""
        with patch("src.core.standards_store.get_standards_store") as mock_get_store, \
             patch("src.search.get_search_service") as mock_get_search, \
             patch("src.agents.evidence_mapper.Config") as mock_config:

            # Setup mocks
            mock_store = MagicMock()
            mock_store.load.return_value = mock_standards_library
            mock_get_store.return_value = mock_store

            mock_service = MagicMock()
            mock_service.search.return_value = mock_search_results
            mock_get_search.return_value = mock_service

            mock_config.WORKSPACE_DIR = tmp_path
            mock_config.AGENT_CONFIDENCE_THRESHOLD = 0.7

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_generate_crosswalk_table({
                "standards_id": "std_accsc",
                "institution_id": "inst_test123",
                "output_format": "json"
            })

            assert result["success"] is True
            assert "crosswalk_id" in result
            assert result["format"] == "json"
            assert "statistics" in result
            assert result["statistics"]["total_standards"] == 3

            # Verify file was created
            output_path = Path(result["output_path"])
            assert output_path.exists()

            # Verify content
            with open(output_path) as f:
                data = json.load(f)
            assert len(data["entries"]) == 3

    @patch("src.agents.base_agent.Anthropic")
    def test_generate_crosswalk_csv(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_standards_library, mock_search_results, tmp_path
    ):
        """Test crosswalk table generation in CSV format."""
        with patch("src.core.standards_store.get_standards_store") as mock_get_store, \
             patch("src.search.get_search_service") as mock_get_search, \
             patch("src.agents.evidence_mapper.Config") as mock_config:

            mock_store = MagicMock()
            mock_store.load.return_value = mock_standards_library
            mock_get_store.return_value = mock_store

            mock_service = MagicMock()
            mock_service.search.return_value = mock_search_results
            mock_get_search.return_value = mock_service

            mock_config.WORKSPACE_DIR = tmp_path
            mock_config.AGENT_CONFIDENCE_THRESHOLD = 0.7

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_generate_crosswalk_table({
                "standards_id": "std_accsc",
                "institution_id": "inst_test123",
                "output_format": "csv"
            })

            assert result["success"] is True
            assert result["format"] == "csv"
            assert result["output_path"].endswith(".csv")


class TestIdentifyEvidenceGaps:
    """Tests for identify_evidence_gaps tool."""

    @patch("src.agents.base_agent.Anthropic")
    def test_identify_gaps(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_standards_library, tmp_path
    ):
        """Test gap identification with mixed results."""
        with patch("src.core.standards_store.get_standards_store") as mock_get_store, \
             patch("src.search.get_search_service") as mock_get_search, \
             patch("src.agents.evidence_mapper.Config") as mock_config:

            mock_store = MagicMock()
            mock_store.load.return_value = mock_standards_library
            mock_get_store.return_value = mock_store

            # Return no results to create gaps
            mock_service = MagicMock()
            mock_service.search.return_value = []
            mock_get_search.return_value = mock_service

            mock_config.WORKSPACE_DIR = tmp_path
            mock_config.AGENT_CONFIDENCE_THRESHOLD = 0.7

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_identify_evidence_gaps({
                "institution_id": "inst_test123",
                "standards_id": "std_accsc"
            })

            assert result["success"] is True
            assert result["total_gaps"] > 0
            assert "critical_gaps" in result
            assert "high_gaps" in result
            assert "advisory_gaps" in result
            assert "summary" in result


class TestGetEvidenceSummary:
    """Tests for get_evidence_summary tool."""

    @patch("src.agents.base_agent.Anthropic")
    def test_summary_no_maps(self, mock_anthropic, mock_session, mock_workspace_manager, tmp_path):
        """Test summary when no evidence maps exist."""
        with patch("src.agents.evidence_mapper.Config") as mock_config:
            mock_config.WORKSPACE_DIR = tmp_path

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_get_evidence_summary({
                "institution_id": "inst_test123"
            })

        assert result["success"] is True
        assert result["has_evidence_map"] is False
        assert result["status"] == "not_started"

    @patch("src.agents.base_agent.Anthropic")
    def test_summary_with_existing_map(self, mock_anthropic, mock_session, mock_workspace_manager, tmp_path):
        """Test summary with existing evidence map."""
        # Create test evidence map
        maps_dir = tmp_path / "inst_test123" / "evidence_maps"
        maps_dir.mkdir(parents=True)
        test_map = {
            "id": "evmap_test",
            "standards_library_id": "std_accsc",
            "created_at": "2024-01-01T00:00:00Z",
            "statistics": {
                "total_standards": 10,
                "with_evidence": 8,
                "strong": 5,
                "adequate": 2,
                "weak": 1,
                "missing": 2,
                "coverage_percent": 80.0
            }
        }
        with open(maps_dir / "evidence_map_std_accsc.json", "w") as f:
            json.dump(test_map, f)

        with patch("src.agents.evidence_mapper.Config") as mock_config:
            mock_config.WORKSPACE_DIR = tmp_path

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent._tool_get_evidence_summary({
                "institution_id": "inst_test123"
            })

        assert result["success"] is True
        assert result["has_evidence_map"] is True
        assert result["status"] == "mostly_ready"
        assert result["coverage_stats"]["coverage_percent"] == 80.0


class TestWorkflows:
    """Tests for workflow methods."""

    @patch("src.agents.base_agent.Anthropic")
    def test_workflow_map_all_standards(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_standards_library, mock_search_results, tmp_path
    ):
        """Test map_all_standards workflow."""
        with patch("src.core.standards_store.get_standards_store") as mock_get_store, \
             patch("src.search.get_search_service") as mock_get_search, \
             patch("src.agents.evidence_mapper.Config") as mock_config:

            mock_store = MagicMock()
            mock_store.load.return_value = mock_standards_library
            mock_get_store.return_value = mock_store

            mock_service = MagicMock()
            mock_service.search.return_value = mock_search_results
            mock_get_search.return_value = mock_service

            mock_config.WORKSPACE_DIR = tmp_path
            mock_config.AGENT_CONFIDENCE_THRESHOLD = 0.7

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent.run_workflow("map_all_standards", {
                "institution_id": "inst_test123",
                "standards_id": "std_accsc"
            })

            assert result.status == "success"
            assert "evidence_map_id" in result.data
            assert "coverage_stats" in result.data
            assert result.data["coverage_stats"]["total_standards"] == 3

    @patch("src.agents.base_agent.Anthropic")
    def test_workflow_gap_analysis(
        self, mock_anthropic,
        mock_session, mock_workspace_manager, mock_standards_library, tmp_path
    ):
        """Test gap_analysis workflow."""
        with patch("src.core.standards_store.get_standards_store") as mock_get_store, \
             patch("src.search.get_search_service") as mock_get_search, \
             patch("src.agents.evidence_mapper.Config") as mock_config:

            mock_store = MagicMock()
            mock_store.load.return_value = mock_standards_library
            mock_get_store.return_value = mock_store

            # No search results = gaps
            mock_service = MagicMock()
            mock_service.search.return_value = []
            mock_get_search.return_value = mock_service

            mock_config.WORKSPACE_DIR = tmp_path
            mock_config.AGENT_CONFIDENCE_THRESHOLD = 0.7

            agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

            result = agent.run_workflow("gap_analysis", {
                "institution_id": "inst_test123",
                "standards_id": "std_accsc"
            })

            assert result.status == "success"
            assert "total_gaps" in result.data
            assert "recommendations" in result.data

    @patch("src.agents.base_agent.Anthropic")
    def test_workflow_unknown_action(self, mock_anthropic, mock_session, mock_workspace_manager):
        """Test workflow with unknown action."""
        agent = EvidenceMapperAgent(mock_session, mock_workspace_manager)

        result = agent.run_workflow("unknown_action", {})

        assert result.status == "error"
        assert "Unknown workflow action" in result.error


class TestDataModels:
    """Tests for evidence mapping data models."""

    def test_crosswalk_entry_serialization(self):
        """Test CrosswalkEntry serialization."""
        entry = CrosswalkEntry(
            standard_ref="I.A.1",
            section_reference="I.A",
            category="Mission",
            requirement="School has a written mission statement",
            evidence_found=True,
            quality="strong",
            document_id="doc_001",
            page=5,
            snippet="The mission of the institution...",
            confidence=0.92,
            exhibit_label="Exhibit I.A.1"
        )

        data = entry.to_dict()
        assert data["standard_ref"] == "I.A.1"
        assert data["quality"] == "strong"

        restored = CrosswalkEntry.from_dict(data)
        assert restored.standard_ref == entry.standard_ref
        assert restored.confidence == entry.confidence

    def test_evidence_mapping_serialization(self):
        """Test EvidenceMapping serialization."""
        mapping = EvidenceMapping(
            standard_id="I.A.1",
            standard_number="I.A.1",
            standard_text="School has a written mission statement",
            status="satisfied",
            confidence=0.9,
            evidence=[{"document_id": "doc_001", "page": 5}],
            suggested_exhibit="Exhibit I.A.1"
        )

        data = mapping.to_dict()
        assert data["status"] == "satisfied"

        restored = EvidenceMapping.from_dict(data)
        assert restored.status == mapping.status

    def test_evidence_map_serialization(self):
        """Test EvidenceMap serialization."""
        mapping = EvidenceMapping(
            standard_id="I.A.1",
            standard_number="I.A.1",
            standard_text="Test requirement",
            status="satisfied",
            confidence=0.9
        )

        evidence_map = EvidenceMap(
            institution_id="inst_test123",
            standards_library_id="std_accsc",
            mappings=[mapping],
            coverage_stats={"total": 1, "satisfied": 1}
        )

        data = evidence_map.to_dict()
        assert data["institution_id"] == "inst_test123"
        assert len(data["mappings"]) == 1

        restored = EvidenceMap.from_dict(data)
        assert restored.institution_id == evidence_map.institution_id
        assert len(restored.mappings) == 1

    def test_evidence_gap_serialization(self):
        """Test EvidenceGap serialization."""
        gap = EvidenceGap(
            standard_id="I.C.2",
            standard_number="I.C.2",
            standard_text="Refund policy requirement",
            severity="critical",
            current_coverage="missing",
            confidence=0.0,
            suggestions=["Upload refund policy document"],
            related_doc_types=["catalog", "enrollment_agreement"]
        )

        data = gap.to_dict()
        assert data["severity"] == "critical"
        assert len(data["suggestions"]) == 1

        restored = EvidenceGap.from_dict(data)
        assert restored.severity == gap.severity
        assert restored.suggestions == gap.suggestions
