"""Tests for contextual search API blueprint.

Tests POST /api/search/contextual, GET /sources, and GET /suggest endpoints.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from src.core.models import SearchScope, SearchContext
from src.services.site_visit_service import SearchResponse, SiteVisitResult, Citation


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    from src.core.workspace import WorkspaceManager
    from src.core.standards_store import StandardsStore

    # Create a minimal Flask app for testing
    app = Flask(__name__)
    app.config['TESTING'] = True

    # Mock dependencies
    workspace_manager = Mock(spec=WorkspaceManager)
    standards_store = Mock(spec=StandardsStore)

    # Initialize and register blueprint
    from src.api.contextual_search import contextual_search_bp, init_contextual_search_bp
    init_contextual_search_bp(workspace_manager, standards_store)
    app.register_blueprint(contextual_search_bp)

    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_search_service():
    """Mock ContextualSearchService."""
    with patch('src.api.contextual_search.get_contextual_search_service') as mock:
        service = Mock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_db_conn():
    """Mock database connection."""
    with patch('src.api.contextual_search.get_conn') as mock:
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = []
        conn.execute.return_value = cursor
        mock.return_value = conn
        yield conn


class TestContextualSearchEndpoint:
    """Tests for POST /api/search/contextual"""

    def test_search_returns_200_with_valid_query(self, client, mock_search_service):
        """POST /api/search/contextual with valid body returns 200 with results."""
        # Setup mock response
        mock_search_service.search.return_value = SearchResponse(
            results=[
                SiteVisitResult(
                    id="res_1",
                    source_type="documents",
                    source_id="doc_1",
                    title="Test Document",
                    snippet="Test snippet",
                    citation=Citation(
                        document="Test Doc",
                        page=1,
                        section="Test"
                    ),
                    score=0.9,
                    metadata={}
                )
            ],
            total=1,
            query_time_ms=50,
            sources_searched=["documents"]
        )

        response = client.post(
            '/api/search/contextual',
            json={"query": "test query", "scope": "global"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["query"] == "test query"
        assert data["scope"] == "global"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert "facets" in data
        assert "page" in data
        assert "per_page" in data
        assert "context" in data

    def test_search_missing_query_returns_400(self, client):
        """POST /api/search/contextual with missing query returns 400."""
        response = client.post(
            '/api/search/contextual',
            json={"scope": "global"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "query" in data["error"].lower()

    def test_search_institution_scope_without_id_returns_400(self, client):
        """POST /api/search/contextual with INSTITUTION scope but no institution_id returns 400."""
        response = client.post(
            '/api/search/contextual',
            json={"query": "test", "scope": "institution"}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "institution_id" in data["error"].lower()

    def test_search_program_scope_requires_institution_and_program(self, client):
        """POST /api/search/contextual with PROGRAM scope requires both IDs."""
        # Missing program_id
        response = client.post(
            '/api/search/contextual',
            json={"query": "test", "scope": "program", "institution_id": "inst_1"}
        )
        assert response.status_code == 400

        # Missing institution_id
        response = client.post(
            '/api/search/contextual',
            json={"query": "test", "scope": "program", "program_id": "prog_1"}
        )
        assert response.status_code == 400

    def test_search_with_pagination(self, client, mock_search_service):
        """POST /api/search/contextual respects page and per_page parameters."""
        mock_search_service.search.return_value = SearchResponse(
            results=[],
            total=100,
            query_time_ms=50,
            sources_searched=["documents"]
        )

        response = client.post(
            '/api/search/contextual',
            json={"query": "test", "scope": "global", "page": 2, "per_page": 10}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["page"] == 2
        assert data["per_page"] == 10

        # Verify service was called with correct offset
        mock_search_service.search.assert_called_once()
        call_args = mock_search_service.search.call_args
        assert call_args[1]["limit"] == 10
        assert call_args[1]["offset"] == 10  # (page-1) * per_page


class TestSourcesEndpoint:
    """Tests for GET /api/search/contextual/sources"""

    def test_sources_returns_all_for_global_scope(self, client):
        """GET /api/search/contextual/sources?scope=global returns all 8 sources."""
        response = client.get('/api/search/contextual/sources?scope=global')

        assert response.status_code == 200
        data = response.get_json()
        assert data["scope"] == "global"
        assert len(data["sources"]) == 8
        assert "documents" in data["sources"]
        assert "standards" in data["sources"]

    def test_sources_returns_all_for_institution_scope(self, client):
        """GET /api/search/contextual/sources?scope=institution returns all 8 sources."""
        response = client.get('/api/search/contextual/sources?scope=institution')

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["sources"]) == 8

    def test_sources_returns_standards_only_for_standards_scope(self, client):
        """GET /api/search/contextual/sources?scope=standards returns only standards source."""
        response = client.get('/api/search/contextual/sources?scope=standards')

        assert response.status_code == 200
        data = response.get_json()
        assert data["sources"] == ["standards"]

    def test_sources_invalid_scope_returns_400(self, client):
        """GET /api/search/contextual/sources with invalid scope returns 400."""
        response = client.get('/api/search/contextual/sources?scope=invalid')

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_sources_missing_scope_returns_400(self, client):
        """GET /api/search/contextual/sources without scope returns 400."""
        response = client.get('/api/search/contextual/sources')

        assert response.status_code == 400


class TestSuggestEndpoint:
    """Tests for GET /api/search/contextual/suggest"""

    def test_suggest_returns_suggestions(self, client, mock_db_conn):
        """GET /api/search/contextual/suggest returns suggestions list."""
        response = client.get('/api/search/contextual/suggest?scope=global')

        assert response.status_code == 200
        data = response.get_json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    def test_suggest_accepts_prefix_filter(self, client, mock_db_conn):
        """GET /api/search/contextual/suggest accepts prefix parameter."""
        response = client.get('/api/search/contextual/suggest?scope=institution&prefix=pol')

        assert response.status_code == 200
        data = response.get_json()
        assert "suggestions" in data
