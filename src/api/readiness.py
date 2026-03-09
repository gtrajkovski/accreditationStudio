"""Readiness Score API.

Provides endpoints for the Accreditation Readiness Score -
the single number institutions can track.

Endpoints:
- GET /api/institutions/<id>/status - Full readiness status
- GET /api/institutions/<id>/alerts - Blockers list
- GET /api/institutions/<id>/next-actions - Recommended actions
- GET /api/institutions/<id>/readiness/history - Historical snapshots
"""

from flask import Blueprint, jsonify, request
from typing import Optional

from src.services.readiness_service import (
    get_or_compute_readiness,
    get_blockers,
    get_next_actions,
    get_readiness_history,
    compute_readiness,
    mark_readiness_stale,
    ensure_daily_snapshot,
)

readiness_bp = Blueprint('readiness', __name__, url_prefix='/api')

_workspace_manager = None


def init_readiness_bp(workspace_manager):
    """Initialize the readiness blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _get_accreditor_code(institution_id: str) -> str:
    """Get accreditor code for an institution."""
    if _workspace_manager:
        inst = _workspace_manager.load_institution(institution_id)
        if inst and hasattr(inst, 'accrediting_body'):
            return inst.accrediting_body.value
    return "ACCSC"  # Default


def _get_readiness_level(score: int) -> dict:
    """Convert score to level and label."""
    if score >= 90:
        return {"level": "excellent", "label": "Site Visit Ready"}
    elif score >= 75:
        return {"level": "good", "label": "Minor Gaps"}
    elif score >= 60:
        return {"level": "moderate", "label": "Needs Attention"}
    elif score >= 40:
        return {"level": "low", "label": "Significant Gaps"}
    else:
        return {"level": "critical", "label": "Not Ready"}


# =============================================================================
# API Endpoints
# =============================================================================

@readiness_bp.route('/institutions/<institution_id>/status', methods=['GET'])
def get_institution_status(institution_id: str):
    """Get full readiness status for an institution.

    Returns cached snapshot if fresh, otherwise computes new.

    Query params:
        force: Set to "true" to force recomputation

    Returns:
        {
            "success": true,
            "institution_id": "inst_xxx",
            "readiness_score": 82,
            "readiness_level": "good",
            "readiness_label": "Minor Gaps",
            "breakdown": {
                "documents": {"score": 90, "weight": 0.20, ...},
                "compliance": {"score": 74, "weight": 0.40, ...},
                "evidence": {"score": 81, "weight": 0.25, ...},
                "consistency": {"score": 88, "weight": 0.15, ...}
            },
            "blockers": [...],
            "computed_at": "2026-03-02T..."
        }
    """
    force = request.args.get('force', 'false').lower() == 'true'
    accreditor = _get_accreditor_code(institution_id)

    try:
        readiness = get_or_compute_readiness(
            institution_id,
            accreditor_code=accreditor,
            force_recompute=force
        )

        level_info = _get_readiness_level(readiness["total"])

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "readiness_score": readiness["total"],
            "readiness_level": level_info["level"],
            "readiness_label": level_info["label"],
            "breakdown": {
                "documents": {
                    "score": readiness["documents"],
                    "weight": 0.20,
                    "label": "Documents",
                    **readiness.get("breakdown", {}).get("documents", {})
                },
                "compliance": {
                    "score": readiness["compliance"],
                    "weight": 0.40,
                    "label": "Compliance",
                    **readiness.get("breakdown", {}).get("compliance", {})
                },
                "evidence": {
                    "score": readiness["evidence"],
                    "weight": 0.25,
                    "label": "Evidence Coverage",
                    **readiness.get("breakdown", {}).get("evidence", {})
                },
                "consistency": {
                    "score": readiness["consistency"],
                    "weight": 0.15,
                    "label": "Consistency",
                    **readiness.get("breakdown", {}).get("consistency", {})
                }
            },
            "blockers": readiness.get("blockers", []),
            "computed_at": readiness.get("computed_at")
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "readiness_score": 0
        }), 500


@readiness_bp.route('/institutions/<institution_id>/alerts', methods=['GET'])
def get_institution_alerts(institution_id: str):
    """Get blockers and warnings for alerts panel.

    Returns:
        {
            "success": true,
            "blockers": [
                {
                    "type": "missing_doc",
                    "severity": "critical",
                    "message": "Missing required document: Catalog",
                    "action": "Upload Catalog",
                    "link": "/institutions/.../documents?upload=catalog"
                },
                ...
            ],
            "warnings": [...]
        }
    """
    accreditor = _get_accreditor_code(institution_id)

    try:
        readiness = get_or_compute_readiness(institution_id, accreditor)
        blockers = readiness.get("blockers", [])

        # Separate into critical blockers and warnings
        critical_blockers = [b for b in blockers if b.get("severity") in ("critical", "high")]
        warnings = [b for b in blockers if b.get("severity") not in ("critical", "high")]

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "blockers": critical_blockers,
            "warnings": warnings,
            "total_blockers": len(critical_blockers),
            "total_warnings": len(warnings)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "blockers": [],
            "warnings": []
        }), 500


@readiness_bp.route('/institutions/<institution_id>/next-actions', methods=['GET'])
def get_institution_next_actions(institution_id: str):
    """Get recommended next actions to improve readiness.

    Query params:
        limit: Maximum actions to return (default 5)

    Returns:
        {
            "success": true,
            "actions": [
                {
                    "title": "Upload Institutional Catalog",
                    "reason": "Required document missing (-15 points)",
                    "action_type": "upload",
                    "priority": 1,
                    "link": "/institutions/.../documents?upload=catalog"
                },
                ...
            ]
        }
    """
    limit = request.args.get('limit', 5, type=int)
    accreditor = _get_accreditor_code(institution_id)

    try:
        readiness = get_or_compute_readiness(institution_id, accreditor)

        # Reconstruct ReadinessScore for get_next_actions
        from src.services.readiness_service import ReadinessScore, Blocker
        score = ReadinessScore(
            total=readiness["total"],
            documents=readiness["documents"],
            compliance=readiness["compliance"],
            evidence=readiness["evidence"],
            consistency=readiness["consistency"],
            blockers=[Blocker(**b) for b in readiness.get("blockers", [])],
            breakdown=readiness.get("breakdown", {})
        )

        actions = get_next_actions(institution_id, score, accreditor, limit)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "actions": [a.to_dict() for a in actions],
            "readiness_score": readiness["total"]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "actions": []
        }), 500


@readiness_bp.route('/institutions/<institution_id>/readiness/history', methods=['GET'])
def get_readiness_trend(institution_id: str):
    """Get historical readiness scores for trend chart.

    Query params:
        days: Number of days to look back (default 90)

    Returns:
        {
            "success": true,
            "history": [
                {"total": 65, "documents": 80, ..., "created_at": "2026-01-15T..."},
                {"total": 72, "documents": 85, ..., "created_at": "2026-02-01T..."},
                ...
            ]
        }
    """
    days = request.args.get('days', 90, type=int)

    try:
        history = get_readiness_history(institution_id, days)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "history": history,
            "days": days,
            "total_snapshots": len(history)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "history": []
        }), 500


# =============================================================================
# Legacy Endpoint (for backward compatibility)
# =============================================================================

@readiness_bp.route('/institutions/<institution_id>/readiness', methods=['GET'])
def get_readiness_score(institution_id: str):
    """Legacy endpoint - redirects to /status format.

    Returns same format as /status for backward compatibility.
    """
    return get_institution_status(institution_id)


@readiness_bp.route('/institutions/<institution_id>/readiness/breakdown', methods=['GET'])
def get_readiness_breakdown(institution_id: str):
    """Get detailed readiness breakdown with component scores."""
    return get_institution_status(institution_id)


# =============================================================================
# Invalidation Hook
# =============================================================================

@readiness_bp.route('/institutions/<institution_id>/readiness/invalidate', methods=['POST'])
def invalidate_readiness(institution_id: str):
    """Mark readiness as stale (for use by audit/remediation completions)."""
    try:
        mark_readiness_stale(institution_id)
        return jsonify({
            "success": True,
            "message": "Readiness marked as stale"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@readiness_bp.route('/institutions/<institution_id>/readiness/snapshot', methods=['POST'])
def create_readiness_snapshot(institution_id: str):
    """Manually trigger a readiness snapshot.

    Creates a new snapshot only if one doesn't exist for today.
    Use this to ensure historical data is captured regularly.

    Returns:
        {
            "success": true,
            "snapshot_id": "snap_xxx" | null,
            "created": true | false,
            "message": "..."
        }
    """
    accreditor = _get_accreditor_code(institution_id)

    try:
        snapshot_id = ensure_daily_snapshot(institution_id, accreditor)

        if snapshot_id:
            return jsonify({
                "success": True,
                "snapshot_id": snapshot_id,
                "created": True,
                "message": "New snapshot created"
            })
        else:
            return jsonify({
                "success": True,
                "snapshot_id": None,
                "created": False,
                "message": "Snapshot already exists for today"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "created": False
        }), 500
