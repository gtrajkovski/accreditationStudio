"""Site Visit Mode API endpoints.

Provides fast unified search for use during accreditor site visits.
When auditors ask questions, staff need instant answers with citations.

Endpoints:
- POST /api/institutions/<id>/site-visit/search - Unified search
- GET /api/institutions/<id>/site-visit/fact/<path> - Quick fact lookup
- GET /api/institutions/<id>/site-visit/history - Search history
- POST /api/institutions/<id>/site-visit/saved - Save a search
- GET /api/institutions/<id>/site-visit/saved - Get saved searches
"""

import json
from flask import Blueprint, request, jsonify

from src.services.site_visit_service import get_site_visit_service
from src.core.models import generate_id
from src.db.connection import get_conn


# Create Blueprint
site_visit_bp = Blueprint("site_visit", __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_site_visit_bp(workspace_manager):
    """Initialize the site visit blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return site_visit_bp


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/search", methods=["POST"])
def search(institution_id: str):
    """Execute unified search across all data sources.

    Request Body:
        query: Search query text (required)
        filters: Optional filters
            - sources: List of sources to search (documents, standards, findings, faculty, truth_index, knowledge_graph)
            - doc_types: List of document types to filter
            - min_confidence: Minimum confidence score (0-1)
        limit: Maximum results (default 20)
        offset: Pagination offset (default 0)

    Returns:
        JSON with search results including citations.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    if len(query) < 2:
        return jsonify({"error": "query must be at least 2 characters"}), 400

    filters = data.get("filters", {})
    limit = min(data.get("limit", 20), 100)  # Cap at 100
    offset = max(data.get("offset", 0), 0)

    # Execute search
    service = get_site_visit_service(institution_id, _workspace_manager)
    response = service.search(query, filters, limit, offset)

    return jsonify(response.to_dict())


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/fact/<path:fact_path>", methods=["GET"])
def get_fact(institution_id: str, fact_path: str):
    """Get a specific fact from the truth index.

    Path parameter:
        fact_path: Dot-notation path to fact (e.g., programs/prog_001/total_cost)
            Note: Use / in URL, will be converted to dots internally.

    Returns:
        JSON with fact value and source information.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Convert URL path to dot notation
    fact_path_dots = fact_path.replace("/", ".")

    service = get_site_visit_service(institution_id, _workspace_manager)
    fact = service.get_fact(fact_path_dots)

    if not fact:
        return jsonify({"error": f"Fact not found: {fact_path_dots}"}), 404

    return jsonify(fact)


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/history", methods=["GET"])
def get_history(institution_id: str):
    """Get recent search history for auditor continuity.

    Query parameters:
        limit: Maximum entries to return (default 20)

    Returns:
        JSON with list of recent searches.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    limit = min(request.args.get("limit", 20, type=int), 100)

    service = get_site_visit_service(institution_id, _workspace_manager)
    history = service.get_search_history(limit)

    return jsonify({"searches": history})


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/saved", methods=["POST"])
def save_search(institution_id: str):
    """Save a search for quick access.

    Request Body:
        name: Name for the saved search (required)
        query: Search query text (required)
        filters: Optional filters to save

    Returns:
        JSON with saved search details.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    query = data.get("query", "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not query:
        return jsonify({"error": "query is required"}), 400

    filters = data.get("filters", {})

    conn = get_conn()
    search_id = generate_id("svss")

    conn.execute(
        """
        INSERT INTO site_visit_saved_searches
        (id, institution_id, name, query, filters_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (search_id, institution_id, name, query, json.dumps(filters)),
    )
    conn.commit()

    return jsonify({
        "id": search_id,
        "name": name,
        "query": query,
        "filters": filters,
    }), 201


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/saved", methods=["GET"])
def get_saved_searches(institution_id: str):
    """Get saved searches for quick access.

    Returns:
        JSON with list of saved searches ordered by usage.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()
    cursor = conn.execute(
        """
        SELECT id, name, query, filters_json, usage_count, created_at, last_used_at
        FROM site_visit_saved_searches
        WHERE institution_id = ?
        ORDER BY usage_count DESC, created_at DESC
        LIMIT 50
        """,
        (institution_id,),
    )

    saved = []
    for row in cursor.fetchall():
        saved.append({
            "id": row["id"],
            "name": row["name"],
            "query": row["query"],
            "filters": json.loads(row["filters_json"]) if row["filters_json"] else {},
            "usage_count": row["usage_count"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
        })

    return jsonify({"saved_searches": saved})


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/saved/<search_id>", methods=["DELETE"])
def delete_saved_search(institution_id: str, search_id: str):
    """Delete a saved search.

    Returns:
        JSON with success status.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()
    cursor = conn.execute(
        "DELETE FROM site_visit_saved_searches WHERE id = ? AND institution_id = ?",
        (search_id, institution_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Saved search not found"}), 404

    return jsonify({"success": True})


@site_visit_bp.route("/api/institutions/<institution_id>/site-visit/saved/<search_id>/use", methods=["POST"])
def use_saved_search(institution_id: str, search_id: str):
    """Execute a saved search and update usage stats.

    Returns:
        JSON with search results.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()

    # Get saved search
    cursor = conn.execute(
        "SELECT query, filters_json FROM site_visit_saved_searches WHERE id = ? AND institution_id = ?",
        (search_id, institution_id),
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Saved search not found"}), 404

    # Update usage stats
    conn.execute(
        """
        UPDATE site_visit_saved_searches
        SET usage_count = usage_count + 1, last_used_at = datetime('now')
        WHERE id = ?
        """,
        (search_id,),
    )
    conn.commit()

    # Execute search
    query = row["query"]
    filters = json.loads(row["filters_json"]) if row["filters_json"] else {}

    service = get_site_visit_service(institution_id, _workspace_manager)
    response = service.search(query, filters)

    return jsonify(response.to_dict())
