"""Global Search API endpoints.

Enhanced search API that extends SiteVisitService for the command palette.
Provides unified search with filter presets, recent searches, and advanced filtering.

Endpoints:
- POST /api/institutions/<id>/global-search - Enhanced unified search
- GET /api/institutions/<id>/global-search/recent - Recent searches
- GET /api/institutions/<id>/global-search/presets - List filter presets
- POST /api/institutions/<id>/global-search/presets - Create/update preset
- DELETE /api/institutions/<id>/global-search/presets/<preset_id> - Delete preset
- POST /api/institutions/<id>/global-search/presets/<preset_id>/use - Track preset usage
"""

import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from src.services.site_visit_service import get_site_visit_service
from src.core.models import generate_id
from src.db.connection import get_conn


# Create Blueprint
global_search_bp = Blueprint("global_search", __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_global_search_bp(workspace_manager):
    """Initialize the global search blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return global_search_bp


@global_search_bp.route("/api/institutions/<institution_id>/global-search", methods=["POST"])
def search(institution_id: str):
    """Execute unified search with enhanced filters and grouping.

    Request Body:
        query: Search query text (required)
        filters: Optional filters
            - sources: List of sources to search
            - doc_types: List of document types to filter
            - compliance_status: List of compliance statuses (compliant, partial, non_compliant)
            - date_range: {start: ISO date, end: ISO date}
            - min_confidence: Minimum confidence score (0-1)
        limit: Maximum results (default 20)
        offset: Pagination offset (default 0)

    Returns:
        JSON with search results, grouped counts by source type.
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

    # Execute search via SiteVisitService
    service = get_site_visit_service(institution_id, _workspace_manager)
    response = service.search(query, filters, limit, offset)

    # Group results by source_type for enhanced UI
    grouped_counts = {}
    for result in response.results:
        source = result.source_type
        grouped_counts[source] = grouped_counts.get(source, 0) + 1

    # Return enhanced response
    return jsonify({
        "results": [r.to_dict() for r in response.results],
        "total": response.total,
        "query_time_ms": response.query_time_ms,
        "sources_searched": response.sources_searched,
        "grouped_counts": grouped_counts,
    })


@global_search_bp.route("/api/institutions/<institution_id>/global-search/recent", methods=["GET"])
def get_recent_searches(institution_id: str):
    """Get recent search history for empty state display.

    Returns:
        JSON with last 5 searches.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    service = get_site_visit_service(institution_id, _workspace_manager)
    history = service.get_search_history(limit=5)

    return jsonify({"recent_searches": history})


@global_search_bp.route("/api/institutions/<institution_id>/global-search/presets", methods=["GET"])
def list_presets(institution_id: str):
    """List all filter presets for institution.

    Returns:
        JSON with presets ordered by usage count (desc), then name (asc).
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()
    cursor = conn.execute(
        """
        SELECT id, institution_id, name, filters_json, created_at, last_used_at, usage_count
        FROM filter_presets
        WHERE institution_id = ?
        ORDER BY usage_count DESC, name ASC
        """,
        (institution_id,),
    )

    presets = []
    for row in cursor.fetchall():
        presets.append({
            "id": row["id"],
            "institution_id": row["institution_id"],
            "name": row["name"],
            "filters": json.loads(row["filters_json"]),
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "usage_count": row["usage_count"],
        })

    return jsonify({"presets": presets})


@global_search_bp.route("/api/institutions/<institution_id>/global-search/presets", methods=["POST"])
def create_or_update_preset(institution_id: str):
    """Create or update a filter preset.

    Request Body:
        name: Preset name (required)
        filters: Filter configuration (required)
            - doc_types: List of document types
            - compliance_status: List of compliance statuses
            - date_range: {start: ISO date, end: ISO date}

    Returns:
        JSON with created/updated preset.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    filters = data.get("filters")
    if not filters or not isinstance(filters, dict):
        return jsonify({"error": "filters is required and must be an object"}), 400

    # Check if preset with this name exists
    conn = get_conn()
    cursor = conn.execute(
        """
        SELECT id FROM filter_presets
        WHERE institution_id = ? AND name = ?
        """,
        (institution_id, name),
    )
    existing = cursor.fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        # Update existing preset
        preset_id = existing["id"]
        conn.execute(
            """
            UPDATE filter_presets
            SET filters_json = ?, last_used_at = ?
            WHERE id = ?
            """,
            (json.dumps(filters), now, preset_id),
        )
        conn.commit()
    else:
        # Create new preset
        preset_id = generate_id("sfp")
        conn.execute(
            """
            INSERT INTO filter_presets (id, institution_id, name, filters_json, created_at, usage_count)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (preset_id, institution_id, name, json.dumps(filters), now),
        )
        conn.commit()

    # Return created/updated preset
    cursor = conn.execute(
        """
        SELECT id, institution_id, name, filters_json, created_at, last_used_at, usage_count
        FROM filter_presets
        WHERE id = ?
        """,
        (preset_id,),
    )
    row = cursor.fetchone()

    return jsonify({
        "preset": {
            "id": row["id"],
            "institution_id": row["institution_id"],
            "name": row["name"],
            "filters": json.loads(row["filters_json"]),
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "usage_count": row["usage_count"],
        }
    }), 200 if existing else 201


@global_search_bp.route("/api/institutions/<institution_id>/global-search/presets/<preset_id>", methods=["DELETE"])
def delete_preset(institution_id: str, preset_id: str):
    """Delete a filter preset.

    Returns:
        204 No Content on success.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()
    cursor = conn.execute(
        """
        DELETE FROM filter_presets
        WHERE id = ? AND institution_id = ?
        """,
        (preset_id, institution_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Preset not found"}), 404

    return "", 204


@global_search_bp.route("/api/institutions/<institution_id>/global-search/presets/<preset_id>/use", methods=["POST"])
def track_preset_usage(institution_id: str, preset_id: str):
    """Increment usage count and update last_used_at for a preset.

    Returns:
        JSON with updated preset.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """
        UPDATE filter_presets
        SET usage_count = usage_count + 1, last_used_at = ?
        WHERE id = ? AND institution_id = ?
        """,
        (now, preset_id, institution_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Preset not found"}), 404

    # Return updated preset
    cursor = conn.execute(
        """
        SELECT id, institution_id, name, filters_json, created_at, last_used_at, usage_count
        FROM filter_presets
        WHERE id = ?
        """,
        (preset_id,),
    )
    row = cursor.fetchone()

    return jsonify({
        "preset": {
            "id": row["id"],
            "institution_id": row["institution_id"],
            "name": row["name"],
            "filters": json.loads(row["filters_json"]),
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "usage_count": row["usage_count"],
        }
    })
