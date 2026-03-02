"""Work Queue API - Unified work item management."""

from flask import Blueprint, jsonify, request

from src.services.work_queue_service import (
    get_work_queue,
    get_work_queue_summary,
)


work_queue_bp = Blueprint("work_queue", __name__, url_prefix="/api/work-queue")

_workspace_manager = None


def init_work_queue_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


@work_queue_bp.route("", methods=["GET"])
def list_work_items():
    """
    Get unified work queue.

    Query params:
        institution_id: Filter to specific institution
        type: Filter by type (blocker, task, approval)
        priority: Filter by priority (critical, high, medium, low)
        limit: Max items (default 50)
    """
    institution_id = request.args.get("institution_id")
    item_type = request.args.get("type")
    priority = request.args.get("priority")
    limit = request.args.get("limit", 50, type=int)

    # Get accreditor for institution
    accreditor_code = "ACCSC"
    if institution_id and _workspace_manager:
        inst = _workspace_manager.load_institution(institution_id)
        if inst and inst.accrediting_body:
            accreditor_code = inst.accrediting_body.value

    items = get_work_queue(
        institution_id=institution_id,
        accreditor_code=accreditor_code,
        limit=min(limit, 200),
    )

    # Apply filters
    if item_type:
        items = [i for i in items if i.type.value == item_type]

    if priority:
        items = [i for i in items if i.priority.value == priority]

    return jsonify({
        "items": [item.to_dict() for item in items],
        "total": len(items),
        "filters": {
            "institution_id": institution_id,
            "type": item_type,
            "priority": priority,
        },
    })


@work_queue_bp.route("/summary", methods=["GET"])
def get_summary():
    """
    Get work queue summary counts.

    Query params:
        institution_id: Filter to specific institution
    """
    institution_id = request.args.get("institution_id")

    summary = get_work_queue_summary(institution_id)

    return jsonify(summary)


@work_queue_bp.route("/institutions/<institution_id>", methods=["GET"])
def list_institution_work_items(institution_id: str):
    """
    Get work queue for specific institution.

    Path params:
        institution_id: Institution ID

    Query params:
        type: Filter by type
        limit: Max items (default 50)
    """
    item_type = request.args.get("type")
    limit = request.args.get("limit", 50, type=int)

    # Get accreditor for institution
    accreditor_code = "ACCSC"
    if _workspace_manager:
        inst = _workspace_manager.load_institution(institution_id)
        if inst and inst.accrediting_body:
            accreditor_code = inst.accrediting_body.value

    items = get_work_queue(
        institution_id=institution_id,
        accreditor_code=accreditor_code,
        limit=min(limit, 200),
    )

    if item_type:
        items = [i for i in items if i.type.value == item_type]

    return jsonify({
        "items": [item.to_dict() for item in items],
        "total": len(items),
        "institution_id": institution_id,
    })


@work_queue_bp.route("/institutions/<institution_id>/summary", methods=["GET"])
def get_institution_summary(institution_id: str):
    """Get work queue summary for specific institution."""
    summary = get_work_queue_summary(institution_id)

    return jsonify({
        **summary,
        "institution_id": institution_id,
    })
