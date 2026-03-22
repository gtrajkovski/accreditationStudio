"""Change Detection API Blueprint.

Provides endpoints for querying pending document changes and change events.
"""

from flask import Blueprint, jsonify, request

from src.services.change_detection_service import (
    get_pending_changes,
    get_change_count,
    ChangeEvent,
)


# Create Blueprint
change_detection_bp = Blueprint('change_detection', __name__)

# Module-level references
_workspace_manager = None


def init_change_detection_bp(workspace_manager):
    """Initialize the change detection blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return change_detection_bp


@change_detection_bp.route('/api/institutions/<institution_id>/changes/pending', methods=['GET'])
def get_institution_pending_changes(institution_id: str):
    """Get pending document changes for an institution.

    Returns:
        JSON list of change events with metadata.
    """
    try:
        changes = get_pending_changes(institution_id)

        return jsonify([change.to_dict() for change in changes]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@change_detection_bp.route('/api/institutions/<institution_id>/changes/count', methods=['GET'])
def get_institution_change_count(institution_id: str):
    """Get count of pending document changes for an institution.

    Returns:
        JSON with count of pending changes.
    """
    try:
        count = get_change_count(institution_id)

        return jsonify({"count": count}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@change_detection_bp.route('/api/change-detection/pending-count', methods=['GET'])
def get_pending_count():
    """Get count of pending changes (for dashboard badge polling).

    Query Parameters:
        institution_id: ID of the institution (required)

    Returns:
        JSON with count of pending changes.
    """
    institution_id = request.args.get('institution_id')

    if not institution_id:
        return jsonify({"error": "institution_id query parameter required"}), 400

    try:
        count = get_change_count(institution_id)

        return jsonify({"count": count}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
