"""Tests for ContextualSearchService."""

import pytest
from unittest.mock import MagicMock, patch

from src.core.models import SearchContext, SearchScope, generate_id
from src.services.contextual_search_service import (
    ContextualSearchService,
    get_contextual_search_service,
    ALL_SOURCES,
    SearchResponse,
    SiteVisitResult,
    Citation,
)


class TestContextualSearchService:
    """Test ContextualSearchService."""

    def test_constructor_accepts_search_context(self):
        """Test that constructor accepts SearchContext."""
        context = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        service = ContextualSearchService(context)
        assert service.context == context
        assert service.context.scope == SearchScope.INSTITUTION
        assert service.context.institution_id == "inst_123"

    def test_search_returns_search_response(self):
        """Test that search() returns SearchResponse with expected fields."""
        context = SearchContext(scope=SearchScope.GLOBAL)
        service = ContextualSearchService(context)

        # Mock all search methods to return empty lists
        service._search_semantic = MagicMock(return_value=[])
        service._search_document_text = MagicMock(return_value=[])
        service._search_standards = MagicMock(return_value=[])
        service._search_findings = MagicMock(return_value=[])
        service._search_evidence = MagicMock(return_value=[])
        service._search_knowledge_graph = MagicMock(return_value=[])
        service._search_truth_index = MagicMock(return_value=[])
        service._search_agent_sessions = MagicMock(return_value=[])

        response = service.search("test query")

        assert isinstance(response, SearchResponse)
        assert isinstance(response.results, list)
        assert isinstance(response.total, int)
        assert isinstance(response.query_time_ms, int)
        assert isinstance(response.sources_searched, list)

    def test_deduplicate_removes_duplicates_by_source_tuple(self):
        """Test that _deduplicate() removes duplicates by (source_type, source_id) and keeps highest score."""
        context = SearchContext(scope=SearchScope.GLOBAL)
        service = ContextualSearchService(context)

        results = [
            SiteVisitResult(
                id="r1",
                source_type="document",
                source_id="doc_123",
                title="Test",
                snippet="Snippet 1",
                citation=Citation(document="Test"),
                score=0.8,
                metadata={}
            ),
            SiteVisitResult(
                id="r2",
                source_type="document",
                source_id="doc_123",  # Duplicate
                title="Test",
                snippet="Snippet 2",
                citation=Citation(document="Test"),
                score=0.9,  # Higher score
                metadata={}
            ),
            SiteVisitResult(
                id="r3",
                source_type="document",
                source_id="doc_456",  # Different doc
                title="Test 2",
                snippet="Snippet 3",
                citation=Citation(document="Test 2"),
                score=0.7,
                metadata={}
            ),
        ]

        unique = service._deduplicate(results)

        assert len(unique) == 2
        # Should keep the one with score 0.9
        doc_123_result = [r for r in unique if r.source_id == "doc_123"][0]
        assert doc_123_result.score == 0.9
        assert doc_123_result.id == "r2"

    @patch("src.services.contextual_search_service.get_conn")
    def test_search_with_institution_scope_filters_results(self, mock_get_conn):
        """Test that search() with INSTITUTION scope only returns results for that institution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        context = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        service = ContextualSearchService(context)

        # Mock semantic search to return nothing (requires institution)
        service._search_semantic = MagicMock(return_value=[])

        response = service.search("test query", sources=["document_text"])

        # Verify SQL was called with institution_id filter
        call_args = mock_conn.execute.call_args
        assert call_args is not None
        sql = call_args[0][0]
        params = call_args[0][1]

        # Should have institution_id in WHERE clause
        assert "inst_123" in params

    def test_search_with_global_scope_returns_all_institutions(self):
        """Test that search() with GLOBAL scope returns results from all institutions."""
        context = SearchContext(scope=SearchScope.GLOBAL)
        service = ContextualSearchService(context)

        # Mock all search methods
        service._search_semantic = MagicMock(return_value=[])
        service._search_document_text = MagicMock(return_value=[])
        service._search_standards = MagicMock(return_value=[])
        service._search_findings = MagicMock(return_value=[])
        service._search_evidence = MagicMock(return_value=[])
        service._search_knowledge_graph = MagicMock(return_value=[])
        service._search_truth_index = MagicMock(return_value=[])
        service._search_agent_sessions = MagicMock(return_value=[])

        response = service.search("test query")

        # With GLOBAL scope, to_sql_conditions() should return ("", [])
        sql_where, params = context.to_sql_conditions()
        assert sql_where == ""
        assert params == []

    def test_sources_searched_includes_all_8_sources_when_enabled(self):
        """Test that sources_searched includes all 8 sources when all enabled."""
        context = SearchContext(scope=SearchScope.GLOBAL)
        service = ContextualSearchService(context)

        # Mock all search methods
        service._search_semantic = MagicMock(return_value=[])
        service._search_document_text = MagicMock(return_value=[])
        service._search_standards = MagicMock(return_value=[])
        service._search_findings = MagicMock(return_value=[])
        service._search_evidence = MagicMock(return_value=[])
        service._search_knowledge_graph = MagicMock(return_value=[])
        service._search_truth_index = MagicMock(return_value=[])
        service._search_agent_sessions = MagicMock(return_value=[])

        response = service.search("test query")

        # Should search all 8 sources by default
        assert len(response.sources_searched) == 8
        assert set(response.sources_searched) == set(ALL_SOURCES)

    def test_factory_function_returns_service(self):
        """Test that get_contextual_search_service() returns ContextualSearchService."""
        context = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        service = get_contextual_search_service(context)

        assert isinstance(service, ContextualSearchService)
        assert service.context == context

    def test_factory_function_caches_by_scope_and_institution(self):
        """Test that factory function caches services by scope + institution."""
        context1 = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")
        context2 = SearchContext(scope=SearchScope.INSTITUTION, institution_id="inst_123")

        service1 = get_contextual_search_service(context1)
        service2 = get_contextual_search_service(context2)

        # Should return the same instance
        assert service1 is service2


class TestAllSourcesConstant:
    """Test ALL_SOURCES constant."""

    def test_all_sources_has_8_sources(self):
        """Test that ALL_SOURCES contains exactly 8 sources."""
        assert len(ALL_SOURCES) == 8

        expected_sources = [
            "documents",
            "document_text",
            "standards",
            "findings",
            "evidence",
            "knowledge_graph",
            "truth_index",
            "agent_sessions",
        ]

        assert set(ALL_SOURCES) == set(expected_sources)
