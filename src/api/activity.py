"""
Activity Log API Blueprint.

Endpoints for viewing and exporting user activity logs.
Requires authentication and compliance_officer or admin role.
"""

from flask import Blueprint, jsonify, request, g
from src.services import activity_service
from src.auth.decorators import require_role

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activity")


@activity_bp.route("/", methods=["GET"])
@require_role("compliance_officer")
def get_activity():
    """
    Get paginated activity log with filters.

    Query params:
        - institution_id: Institution to filter (required)
        - user_id: Filter by user
        - action: Filter by action type
        - start_date: Filter by start date (ISO format)
        - end_date: Filter by end date (ISO format)
        - page: Page number (default 1)
        - per_page: Items per page (default 50)

    Returns:
        200: Activity log with pagination
        400: Missing institution_id
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    filters = {}
    if request.args.get("user_id"):
        filters["user_id"] = request.args.get("user_id")
    if request.args.get("action"):
        filters["action"] = request.args.get("action")
    if request.args.get("start_date"):
        filters["start_date"] = request.args.get("start_date")
    if request.args.get("end_date"):
        filters["end_date"] = request.args.get("end_date")

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    result = activity_service.get_activity(
        institution_id=institution_id,
        filters=filters,
        page=page,
        per_page=per_page
    )

    return jsonify(result), 200


@activity_bp.route("/summary", methods=["GET"])
@require_role("admin")
def get_summary():
    """
    Get activity summary statistics.

    Query params:
        - institution_id: Institution to summarize (required)
        - days: Number of days to look back (default 30)

    Returns:
        200: Summary statistics by action type
        400: Missing institution_id
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    days = int(request.args.get("days", 30))

    summary = activity_service.get_activity_summary(
        institution_id=institution_id,
        days=days
    )

    return jsonify({
        "institution_id": institution_id,
        "days": days,
        "summary": summary
    }), 200


@activity_bp.route("/export", methods=["GET"])
@require_role("admin")
def export_activity():
    """
    Export activity log as CSV.

    Query params:
        - institution_id: Institution to export (required)
        - start_date: Optional start date (ISO format)
        - end_date: Optional end date (ISO format)

    Returns:
        200: CSV file
        400: Missing institution_id
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    csv_data = activity_service.export_activity(
        institution_id=institution_id,
        start_date=start_date,
        end_date=end_date
    )

    from flask import Response
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=activity_log.csv"}
    )


@activity_bp.route("/entity/<entity_type>/<entity_id>", methods=["GET"])
@require_role("compliance_officer")
def get_entity_activity(entity_type: str, entity_id: str):
    """
    Get activity history for a specific entity.

    Path params:
        - entity_type: Type of entity (e.g., 'document', 'audit')
        - entity_id: ID of entity

    Returns:
        200: List of activity records
    """
    activities = activity_service.get_activity_for_entity(
        entity_type=entity_type,
        entity_id=entity_id
    )

    return jsonify({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "activities": activities
    }), 200


@activity_bp.route("/users", methods=["GET"])
@require_role("compliance_officer")
def get_users():
    """
    Get all users who have logged activity for an institution.

    Query params:
        - institution_id: Institution to query (required)

    Returns:
        200: List of user records
        400: Missing institution_id
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    users = activity_service.get_all_users_for_institution(institution_id)

    return jsonify({"users": users}), 200


@activity_bp.route("/actions", methods=["GET"])
@require_role("compliance_officer")
def get_actions():
    """
    Get all unique action types in the system.

    Returns:
        200: List of action type strings
    """
    actions = activity_service.get_all_actions()

    return jsonify({"actions": actions}), 200
