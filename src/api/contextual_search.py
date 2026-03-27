"""Contextual Search API Blueprint.

Provides context-aware search endpoints that automatically scope queries
based on the user's current location in the application hierarchy.

Endpoints:
- POST /api/search/contextual - Execute scoped search
- GET /api/search/contextual/sources - Get available sources for scope
- GET /api/search/contextual/suggest - Get query suggestions
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

from src.core.models import SearchContext, SearchScope
from src.services.contextual_search_service import (
    get_contextual_search_service,
    ALL_SOURCES,
)
from src.db.connection import get_conn


# Create Blueprint
contextual_search_bp = Blueprint('contextual_search', __name__, url_prefix='/api/search/contextual')

# Module-level references (set during initialization)
_workspace_manager = None
_standards_store = None


def init_contextual_search_bp(workspace_manager, standards_store):
    """Initialize the contextual search blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for workspace access.
        standards_store: StandardsStore instance for accreditor lookups.

    Returns:
        Blueprint instance.
    """
    global _workspace_manager, _standards_store
    _workspace_manager = workspace_manager
    _standards_store = standards_store
    return contextual_search_bp


@contextual_search_bp.route('', methods=['POST'])
def search():
    """Execute context-aware search across configured sources.

    Request body:
        {
            "query": str (required),
            "scope": str (required, one of: global|institution|program|document|standards|compliance),
            "institution_id": str (optional, required for some scopes),
            "program_id": str (optional),
            "document_id": str (optional),
            "accreditor_code": str (optional, for STANDARDS scope),
            "sources": list[str] (optional, defaults to all 8 sources),
            "page": int (optional, default 1),
            "per_page": int (optional, default 20),
            "semantic": bool (optional, default true)
        }

    Returns:
        {
            "query": str,
            "scope": str,
            "total": int,
            "items": list[dict],
            "facets": dict[str, int],
            "page": int,
            "per_page": int,
            "context": dict
        }
    """
    data = request.get_json()

    # Validate required fields
    query = data.get('query')
    if not query:
        return jsonify({"error": "Missing required field: query"}), 400

    scope_str = data.get('scope')
    if not scope_str:
        return jsonify({"error": "Missing required field: scope"}), 400

    # Validate scope
    try:
        scope = SearchScope(scope_str)
    except ValueError:
        return jsonify({"error": f"Invalid scope: {scope_str}. Must be one of: global, institution, program, document, standards, compliance"}), 400

    # Extract context parameters
    institution_id = data.get('institution_id')
    program_id = data.get('program_id')
    document_id = data.get('document_id')
    accreditor_code = data.get('accreditor_code')

    # Validate scope requirements
    if scope == SearchScope.INSTITUTION and not institution_id:
        return jsonify({"error": "institution_id required for INSTITUTION scope"}), 400

    if scope == SearchScope.PROGRAM:
        if not institution_id:
            return jsonify({"error": "institution_id required for PROGRAM scope"}), 400
        if not program_id:
            return jsonify({"error": "program_id required for PROGRAM scope"}), 400

    if scope == SearchScope.DOCUMENT:
        if not institution_id:
            return jsonify({"error": "institution_id required for DOCUMENT scope"}), 400
        if not document_id:
            return jsonify({"error": "document_id required for DOCUMENT scope"}), 400

    if scope == SearchScope.COMPLIANCE and not institution_id:
        return jsonify({"error": "institution_id required for COMPLIANCE scope"}), 400

    # Map accreditor_code to accreditor_id if provided
    accreditor_id = None
    if accreditor_code and _standards_store:
        try:
            accreditor = _standards_store.get_accreditor(accreditor_code)
            if accreditor:
                accreditor_id = accreditor.id
        except Exception as e:
            logger.debug("Failed to lookup accreditor %s: %s", accreditor_code, e)

    # Create SearchContext
    context = SearchContext(
        scope=scope,
        institution_id=institution_id,
        program_id=program_id,
        document_id=document_id,
        accreditor_id=accreditor_id,
    )

    # Extract search parameters
    sources = data.get('sources', ALL_SOURCES)
    page = max(1, data.get('page', 1))
    per_page = max(1, min(100, data.get('per_page', 20)))  # Cap at 100
    offset = (page - 1) * per_page

    # Get service and execute search
    service = get_contextual_search_service(context, _workspace_manager)
    search_response = service.search(
        query=query,
        sources=sources,
        limit=per_page,
        offset=offset,
    )

    # Build facets by counting source_type
    facets = {}
    for result in search_response.results:
        source_type = result.source_type
        facets[source_type] = facets.get(source_type, 0) + 1

    # Serialize results
    items = []
    for result in search_response.results:
        items.append({
            "id": result.id,
            "source_type": result.source_type,
            "source_id": result.source_id,
            "title": result.title,
            "snippet": result.snippet,
            "score": result.score,
            "citation": result.citation.to_dict(),
            "metadata": result.metadata,
        })

    return jsonify({
        "query": query,
        "scope": scope.value,
        "total": search_response.total,
        "items": items,
        "facets": facets,
        "page": page,
        "per_page": per_page,
        "context": context.to_dict(),
    })


@contextual_search_bp.route('/sources', methods=['GET'])
def get_sources():
    """Get available search sources for a given scope.

    Query params:
        scope: str (required) - One of: global|institution|program|document|standards|compliance

    Returns:
        {
            "scope": str,
            "sources": list[str]
        }
    """
    scope_str = request.args.get('scope')
    if not scope_str:
        return jsonify({"error": "Missing required parameter: scope"}), 400

    # Validate scope
    try:
        scope = SearchScope(scope_str)
    except ValueError:
        return jsonify({"error": f"Invalid scope: {scope_str}"}), 400

    # Determine available sources based on scope
    if scope == SearchScope.STANDARDS:
        # Standards scope only searches standards
        sources = ["standards"]
    else:
        # All other scopes have access to all 8 sources
        sources = ALL_SOURCES

    return jsonify({
        "scope": scope.value,
        "sources": sources,
    })


@contextual_search_bp.route('/suggest', methods=['GET'])
def get_suggestions():
    """Get query suggestions based on search history and context.

    Query params:
        scope: str (required) - Search scope for filtering suggestions
        institution_id: str (optional) - Filter by institution
        prefix: str (optional) - Filter suggestions by prefix

    Returns:
        {
            "suggestions": [
                {
                    "query": str,
                    "count": int
                },
                ...
            ]
        }
    """
    scope_str = request.args.get('scope', 'global')
    institution_id = request.args.get('institution_id')
    prefix = request.args.get('prefix', '').lower()

    # Query site_visit_searches table for recent searches
    conn = get_conn()
    query = """
        SELECT query, COUNT(*) as count
        FROM site_visit_searches
        WHERE 1=1
    """
    params = []

    # Add scope filter if not global
    if scope_str != 'global' and institution_id:
        query += " AND institution_id = ?"
        params.append(institution_id)

    # Add prefix filter if provided
    if prefix:
        query += " AND LOWER(query) LIKE ?"
        params.append(f"{prefix}%")

    query += """
        GROUP BY query
        ORDER BY count DESC, query
        LIMIT 10
    """

    cursor = conn.execute(query, params)
    suggestions = []
    for row in cursor.fetchall():
        suggestions.append({
            "query": row["query"],
            "count": row["count"],
        })

    return jsonify({"suggestions": suggestions})
