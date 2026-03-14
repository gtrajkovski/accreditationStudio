"""Portfolios API for Multi-Institution Mode.

Provides endpoints for managing portfolios, aggregate readiness,
institution comparison, and bulk operations.

Endpoints:
- GET    /api/portfolios                        - List all portfolios
- POST   /api/portfolios                        - Create portfolio
- GET    /api/portfolios/<id>                   - Get portfolio details
- PUT    /api/portfolios/<id>                   - Update portfolio
- DELETE /api/portfolios/<id>                   - Delete portfolio
- POST   /api/portfolios/<id>/institutions      - Add institutions
- DELETE /api/portfolios/<id>/institutions/<iid> - Remove institution
- PUT    /api/portfolios/<id>/institutions/reorder - Reorder institutions
- GET    /api/portfolios/<id>/readiness         - Aggregate readiness
- GET    /api/portfolios/<id>/comparison        - Comparison data
- GET    /api/portfolios/<id>/history           - Historical snapshots
- GET    /api/institutions/recent               - Recent institutions
- POST   /api/institutions/<id>/access          - Record access
"""

from flask import Blueprint, jsonify, request

from src.services.portfolio_service import (
    create_portfolio,
    update_portfolio,
    delete_portfolio,
    get_portfolio,
    list_portfolios,
    add_institutions_to_portfolio,
    remove_institution_from_portfolio,
    get_portfolio_institutions,
    reorder_portfolio_institutions,
    compute_portfolio_readiness,
    persist_portfolio_snapshot,
    get_portfolio_history,
    get_portfolio_comparison,
    record_institution_access,
    get_recent_institutions,
)

portfolios_bp = Blueprint('portfolios', __name__, url_prefix='/api')

_workspace_manager = None


def init_portfolios_bp(workspace_manager):
    """Initialize the portfolios blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


# =============================================================================
# Portfolio CRUD
# =============================================================================

@portfolios_bp.route('/portfolios', methods=['GET'])
def api_list_portfolios():
    """List all portfolios with institution counts.

    Returns:
        {
            "success": true,
            "portfolios": [
                {
                    "id": "portfolio_xxx",
                    "name": "Regional Schools",
                    "description": "...",
                    "color": "#C9A84C",
                    "institution_count": 12,
                    ...
                }
            ]
        }
    """
    portfolios = list_portfolios()
    return jsonify({
        "success": True,
        "portfolios": [p.to_dict() for p in portfolios],
    })


@portfolios_bp.route('/portfolios', methods=['POST'])
def api_create_portfolio():
    """Create a new portfolio.

    Request body:
        {
            "name": "Regional Schools",
            "description": "Western region institutions",
            "color": "#C9A84C",
            "icon": "folder"
        }

    Returns:
        { "success": true, "portfolio": {...} }
    """
    data = request.get_json() or {}

    name = data.get("name")
    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    portfolio = create_portfolio(
        name=name,
        description=data.get("description"),
        color=data.get("color", "#C9A84C"),
        icon=data.get("icon", "folder"),
    )

    return jsonify({
        "success": True,
        "portfolio": portfolio.to_dict(),
    }), 201


@portfolios_bp.route('/portfolios/<portfolio_id>', methods=['GET'])
def api_get_portfolio(portfolio_id: str):
    """Get portfolio details with institution list.

    Returns:
        {
            "success": true,
            "portfolio": {...},
            "institutions": [
                {"id": "inst_xxx", "name": "School A", ...}
            ]
        }
    """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"success": False, "error": "Portfolio not found"}), 404

    # Get institution details
    institution_ids = get_portfolio_institutions(portfolio_id)
    institutions = []

    if _workspace_manager and institution_ids:
        all_insts = _workspace_manager.list_institutions()
        inst_map = {i["id"]: i for i in all_insts}
        for inst_id in institution_ids:
            if inst_id in inst_map:
                institutions.append(inst_map[inst_id])

    return jsonify({
        "success": True,
        "portfolio": portfolio.to_dict(),
        "institutions": institutions,
    })


@portfolios_bp.route('/portfolios/<portfolio_id>', methods=['PUT'])
def api_update_portfolio(portfolio_id: str):
    """Update portfolio metadata.

    Request body (all fields optional):
        {
            "name": "New Name",
            "description": "...",
            "color": "#ff0000",
            "icon": "star",
            "sort_order": 1
        }

    Returns:
        { "success": true, "portfolio": {...} }
    """
    if portfolio_id == "portfolio_all":
        return jsonify({"success": False, "error": "Cannot modify default portfolio"}), 400

    data = request.get_json() or {}

    portfolio = update_portfolio(
        portfolio_id=portfolio_id,
        name=data.get("name"),
        description=data.get("description"),
        color=data.get("color"),
        icon=data.get("icon"),
        sort_order=data.get("sort_order"),
    )

    if not portfolio:
        return jsonify({"success": False, "error": "Portfolio not found"}), 404

    return jsonify({
        "success": True,
        "portfolio": portfolio.to_dict(),
    })


@portfolios_bp.route('/portfolios/<portfolio_id>', methods=['DELETE'])
def api_delete_portfolio(portfolio_id: str):
    """Delete a portfolio (not its institutions).

    Returns:
        { "success": true }
    """
    if portfolio_id == "portfolio_all":
        return jsonify({"success": False, "error": "Cannot delete default portfolio"}), 400

    success = delete_portfolio(portfolio_id)
    if not success:
        return jsonify({"success": False, "error": "Portfolio not found"}), 404

    return jsonify({"success": True})


# =============================================================================
# Portfolio Membership
# =============================================================================

@portfolios_bp.route('/portfolios/<portfolio_id>/institutions', methods=['POST'])
def api_add_institutions(portfolio_id: str):
    """Add institutions to a portfolio.

    Request body:
        {
            "institution_ids": ["inst_xxx", "inst_yyy"]
        }

    Returns:
        { "success": true, "added": 2 }
    """
    data = request.get_json() or {}
    institution_ids = data.get("institution_ids", [])

    if not institution_ids:
        return jsonify({"success": False, "error": "No institution IDs provided"}), 400

    added = add_institutions_to_portfolio(portfolio_id, institution_ids)

    return jsonify({
        "success": True,
        "added": added,
    })


@portfolios_bp.route('/portfolios/<portfolio_id>/institutions/<institution_id>', methods=['DELETE'])
def api_remove_institution(portfolio_id: str, institution_id: str):
    """Remove an institution from a portfolio.

    Returns:
        { "success": true }
    """
    success = remove_institution_from_portfolio(portfolio_id, institution_id)
    if not success:
        return jsonify({"success": False, "error": "Institution not in portfolio"}), 404

    return jsonify({"success": True})


@portfolios_bp.route('/portfolios/<portfolio_id>/institutions/reorder', methods=['PUT'])
def api_reorder_institutions(portfolio_id: str):
    """Reorder institutions within a portfolio.

    Request body:
        {
            "institution_ids": ["inst_yyy", "inst_xxx", ...]
        }

    Returns:
        { "success": true }
    """
    data = request.get_json() or {}
    institution_ids = data.get("institution_ids", [])

    reorder_portfolio_institutions(portfolio_id, institution_ids)

    return jsonify({"success": True})


# =============================================================================
# Portfolio Readiness & Comparison
# =============================================================================

@portfolios_bp.route('/portfolios/<portfolio_id>/readiness', methods=['GET'])
def api_portfolio_readiness(portfolio_id: str):
    """Get aggregate readiness metrics for a portfolio.

    Query params:
        force: Set to "true" to force recomputation
        snapshot: Set to "true" to persist snapshot

    Returns:
        {
            "success": true,
            "readiness": {
                "portfolio_id": "portfolio_xxx",
                "avg_score": 72,
                "min_score": 45,
                "max_score": 95,
                "institution_count": 15,
                "at_risk_count": 3,
                "ready_count": 8,
                "breakdown": {...},
                "institutions": [...]
            }
        }
    """
    if not _workspace_manager:
        return jsonify({"success": False, "error": "Service not initialized"}), 500

    force = request.args.get("force", "").lower() == "true"
    snapshot = request.args.get("snapshot", "").lower() == "true"

    readiness = compute_portfolio_readiness(
        portfolio_id=portfolio_id,
        workspace_manager=_workspace_manager,
        force_recompute=force,
    )

    if snapshot:
        persist_portfolio_snapshot(portfolio_id, readiness)

    return jsonify({
        "success": True,
        "readiness": readiness.to_dict(),
    })


@portfolios_bp.route('/portfolios/<portfolio_id>/comparison', methods=['GET'])
def api_portfolio_comparison(portfolio_id: str):
    """Get comparison data for institutions in a portfolio.

    Query params:
        institutions: Comma-separated institution IDs (max 4)

    Returns:
        {
            "success": true,
            "comparison": {
                "portfolio_id": "...",
                "institutions": [...],
                "chart": {...},
                "metrics": [...]
            }
        }
    """
    if not _workspace_manager:
        return jsonify({"success": False, "error": "Service not initialized"}), 500

    # Parse institution filter
    inst_filter = request.args.get("institutions", "")
    institution_ids = [i.strip() for i in inst_filter.split(",") if i.strip()] or None

    comparison = get_portfolio_comparison(
        portfolio_id=portfolio_id,
        workspace_manager=_workspace_manager,
        institution_ids=institution_ids,
    )

    return jsonify({
        "success": True,
        "comparison": comparison,
    })


@portfolios_bp.route('/portfolios/<portfolio_id>/history', methods=['GET'])
def api_portfolio_history(portfolio_id: str):
    """Get historical portfolio snapshots.

    Query params:
        days: Number of days to look back (default 90)

    Returns:
        {
            "success": true,
            "history": [
                {"avg_score": 72, "created_at": "...", ...}
            ]
        }
    """
    days = int(request.args.get("days", 90))
    history = get_portfolio_history(portfolio_id, days)

    return jsonify({
        "success": True,
        "history": history,
    })


# =============================================================================
# Recent Institution Tracking
# =============================================================================

@portfolios_bp.route('/institutions/recent', methods=['GET'])
def api_recent_institutions():
    """Get recently accessed institutions.

    Query params:
        limit: Max institutions to return (default 5)

    Returns:
        {
            "success": true,
            "institution_ids": ["inst_xxx", ...],
            "institutions": [{...}, ...]
        }
    """
    limit = int(request.args.get("limit", 5))
    institution_ids = get_recent_institutions(limit)

    institutions = []
    if _workspace_manager and institution_ids:
        all_insts = _workspace_manager.list_institutions()
        inst_map = {i["id"]: i for i in all_insts}
        for inst_id in institution_ids:
            if inst_id in inst_map:
                institutions.append(inst_map[inst_id])

    return jsonify({
        "success": True,
        "institution_ids": institution_ids,
        "institutions": institutions,
    })


@portfolios_bp.route('/institutions/<institution_id>/access', methods=['POST'])
def api_record_access(institution_id: str):
    """Record that an institution was accessed.

    Returns:
        { "success": true }
    """
    record_institution_access(institution_id)
    return jsonify({"success": True})
