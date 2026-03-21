"""Tests for Evidence Assistant Service."""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.services.evidence_assistant_service import (
    EvidenceAssistantService,
    EvidenceResult
)
from src.core.models import DocumentChunk


class TestEvidenceAssistantService:
    """Tests for EvidenceAssistantService."""

    def test_evidence_result_to_dict(self):
        """Test EvidenceResult serialization."""
        result = EvidenceResult(
            document_id="doc_001",
            doc_type="Policy Manual",
            snippet="This is a snippet...",
            page=5,
            score=0.85,
            is_required_type=True,
            relevance_label="Required",
            confidence=0.75
        )

        data = result.to_dict()

        assert data["document_id"] == "doc_001"
        assert data["doc_type"] == "Policy Manual"
        assert data["snippet"] == "This is a snippet..."
        assert data["page"] == 5
        assert data["score"] == 0.85
        assert data["is_required_type"] is True
        assert data["relevance_label"] == "Required"
        assert data["confidence"] == 0.75

    @patch("src.services.evidence_assistant_service.get_search_service")
    def test_find_evidence_for_standard_returns_results(self, mock_get_search):
        """Test find_evidence_for_standard returns weighted results."""
        # Mock search service
        mock_search_service = MagicMock()
        mock_get_search.return_value = mock_search_service

        # Mock search results
        mock_chunk1 = MagicMock(spec=DocumentChunk)
        mock_chunk1.document_id = "doc_001"
        mock_chunk1.text_original = "This document contains policy information about admissions."
        mock_chunk1.page_number = 1
        mock_chunk1.metadata = {"doc_type": "Admissions Policy"}

        mock_chunk2 = MagicMock(spec=DocumentChunk)
        mock_chunk2.document_id = "doc_002"
        mock_chunk2.text_original = "General information about the institution."
        mock_chunk2.page_number = 3
        mock_chunk2.metadata = {"doc_type": "Catalog"}

        mock_result1 = MagicMock()
        mock_result1.chunk = mock_chunk1
        mock_result1.score = 0.8

        mock_result2 = MagicMock()
        mock_result2.chunk = mock_chunk2
        mock_result2.score = 0.6

        mock_search_service.search.return_value = [mock_result1, mock_result2]

        # Mock explainer service
        mock_explainer = MagicMock()
        mock_explainer.explain_standard.return_value = {
            "plain_english": "Students must be admitted according to published policies.",
            "required_evidence": ["Admissions Policy", "Student Handbook"]
        }

        # Mock AI client
        mock_ai_client = MagicMock()

        # Create service
        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Execute
        results = service.find_evidence_for_standard(
            institution_id="inst_001",
            standard_id="std_001"
        )

        # Verify
        assert len(results) == 2
        assert all(isinstance(r, EvidenceResult) for r in results)
        assert results[0].document_id == "doc_001"
        assert results[0].doc_type == "Admissions Policy"
        assert results[0].is_required_type is True  # Matches "Admissions Policy"
        assert results[0].relevance_label == "Required"

    @patch("src.services.evidence_assistant_service.get_search_service")
    def test_find_evidence_applies_weighting(self, mock_get_search):
        """Test that required evidence types get boosted scores."""
        # Mock search service
        mock_search_service = MagicMock()
        mock_get_search.return_value = mock_search_service

        # Mock search results with equal scores
        mock_chunk1 = MagicMock(spec=DocumentChunk)
        mock_chunk1.document_id = "doc_001"
        mock_chunk1.text_original = "Policy document"
        mock_chunk1.page_number = 1
        mock_chunk1.metadata = {"doc_type": "Policy Manual"}

        mock_chunk2 = MagicMock(spec=DocumentChunk)
        mock_chunk2.document_id = "doc_002"
        mock_chunk2.text_original = "Other document"
        mock_chunk2.page_number = 2
        mock_chunk2.metadata = {"doc_type": "Other"}

        mock_result1 = MagicMock()
        mock_result1.chunk = mock_chunk1
        mock_result1.score = 0.7

        mock_result2 = MagicMock()
        mock_result2.chunk = mock_chunk2
        mock_result2.score = 0.7

        mock_search_service.search.return_value = [mock_result2, mock_result1]  # Order: Other, Policy

        # Mock explainer service
        mock_explainer = MagicMock()
        mock_explainer.explain_standard.return_value = {
            "plain_english": "Test standard",
            "required_evidence": ["Policy Manual", "Student Handbook"]
        }

        # Mock AI client
        mock_ai_client = MagicMock()

        # Create service
        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Execute
        results = service.find_evidence_for_standard(
            institution_id="inst_001",
            standard_id="std_001"
        )

        # Verify: Policy Manual should be first due to 1.5x boost
        assert results[0].doc_type == "Policy Manual"
        assert results[0].score == 0.7 * 1.5  # Boosted
        assert results[1].doc_type == "Other"
        assert results[1].score == 0.7  # Not boosted

    @patch("src.services.evidence_assistant_service.get_search_service")
    def test_find_evidence_sorts_by_score(self, mock_get_search):
        """Test that results are sorted by weighted score descending."""
        # Mock search service
        mock_search_service = MagicMock()
        mock_get_search.return_value = mock_search_service

        # Create multiple results with different scores
        results = []
        for i in range(5):
            mock_chunk = MagicMock(spec=DocumentChunk)
            mock_chunk.document_id = f"doc_{i}"
            mock_chunk.text_original = f"Document {i}"
            mock_chunk.page_number = i
            mock_chunk.metadata = {"doc_type": "General"}

            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_result.score = 0.5 + (i * 0.1)  # Scores: 0.5, 0.6, 0.7, 0.8, 0.9

            results.append(mock_result)

        mock_search_service.search.return_value = results

        # Mock explainer service
        mock_explainer = MagicMock()
        mock_explainer.explain_standard.return_value = {
            "plain_english": "Test standard",
            "required_evidence": []
        }

        # Mock AI client
        mock_ai_client = MagicMock()

        # Create service
        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Execute
        evidence_results = service.find_evidence_for_standard(
            institution_id="inst_001",
            standard_id="std_001"
        )

        # Verify sorted descending
        scores = [r.score for r in evidence_results]
        assert scores == sorted(scores, reverse=True)
        assert evidence_results[0].document_id == "doc_4"  # Highest score
        assert evidence_results[-1].document_id == "doc_0"  # Lowest score

    def test_generate_suggested_prompts_returns_list(self):
        """Test generate_suggested_prompts returns list of strings."""
        # Mock AI client
        mock_ai_client = MagicMock()
        mock_ai_client.generate.return_value = json.dumps([
            "What evidence supports Standard 1.2?",
            "Are there any gaps in faculty credentials?",
            "Show me enrollment data for the last 3 years"
        ])

        # Mock explainer service
        mock_explainer = MagicMock()

        # Mock search service
        mock_search_service = MagicMock()

        # Create service
        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Execute
        conversation_history = [
            {"role": "user", "content": "Show me admissions policies"},
            {"role": "assistant", "content": "Here are the admissions policies..."}
        ]
        context = {
            "current_page": "compliance",
            "active_standard_id": "std_001"
        }

        suggestions = service.generate_suggested_prompts(conversation_history, context)

        # Verify
        assert isinstance(suggestions, list)
        assert len(suggestions) == 3
        assert all(isinstance(s, str) for s in suggestions)
        assert "What evidence supports Standard 1.2?" in suggestions

    def test_generate_suggested_prompts_handles_parse_error(self):
        """Test graceful failure when AI returns invalid JSON."""
        # Mock AI client with invalid response
        mock_ai_client = MagicMock()
        mock_ai_client.generate.return_value = "This is not valid JSON"

        # Mock explainer service
        mock_explainer = MagicMock()

        # Mock search service
        mock_search_service = MagicMock()

        # Create service
        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Execute
        suggestions = service.generate_suggested_prompts([], {})

        # Verify: should return empty list, not raise exception
        assert suggestions == []

    def test_is_required_evidence_type_matches(self):
        """Test _is_required_evidence_type matching logic."""
        # Mock services
        mock_search_service = MagicMock()
        mock_explainer = MagicMock()
        mock_ai_client = MagicMock()

        service = EvidenceAssistantService(
            search_service=mock_search_service,
            explainer_service=mock_explainer,
            ai_client=mock_ai_client
        )

        # Test exact match
        assert service._is_required_evidence_type(
            "Policy Manual",
            ["Policy Manual", "Student Handbook"]
        ) is True

        # Test partial match (case insensitive)
        assert service._is_required_evidence_type(
            "Student Admissions Policy",
            ["Policy Manual", "Admissions Policy"]
        ) is True

        # Test no match
        assert service._is_required_evidence_type(
            "Catalog",
            ["Policy Manual", "Student Handbook"]
        ) is False

        # Test empty inputs
        assert service._is_required_evidence_type("", ["Policy"]) is False
        assert service._is_required_evidence_type("Policy", []) is False
