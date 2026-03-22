"""Change Detection API Blueprint.

Provides endpoints for querying pending document changes and change events.
"""

from flask import Blueprint, jsonify, request

from src.services.change_detection_service import (
    get_pending_changes,
    get_change_count,
    ChangeEvent,
    calculate_reaudit_scope,
    ReauditScope,
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


@change_detection_bp.route('/api/institutions/<institution_id>/changes/scope', methods=['GET'])
def get_reaudit_scope(institution_id: str):
    """Get the scope of a potential re-audit for pending changes (per D-04, D-05, D-06).

    Returns:
        JSON with affected standards, changed documents, impacted documents, and total count.
    """
    from src.db.connection import get_conn

    try:
        conn = get_conn()

        # Get pending changes
        pending = get_pending_changes(institution_id, conn)
        if not pending:
            return jsonify({
                "affected_standards": [],
                "changed_documents": [],
                "impacted_documents": [],
                "total_to_audit": 0,
                "has_pending_changes": False,
            }), 200

        # Calculate cascade scope
        changed_doc_ids = [change.document_id for change in pending]
        scope = calculate_reaudit_scope(changed_doc_ids, conn)

        response = scope.to_dict()
        response["has_pending_changes"] = True

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@change_detection_bp.route('/api/institutions/<institution_id>/changes/scope/preview', methods=['POST'])
def preview_reaudit_scope(institution_id: str):
    """Preview re-audit scope for specific document IDs (for confirmation modal).

    Request Body:
        document_ids: List of document IDs to include in re-audit

    Returns:
        JSON with scope details and standard names for display.
    """
    from src.db.connection import get_conn

    try:
        conn = get_conn()

        data = request.get_json() or {}
        document_ids = data.get('document_ids', [])

        if not document_ids:
            return jsonify({"error": "document_ids required"}), 400

        scope = calculate_reaudit_scope(document_ids, conn)
        response = scope.to_dict()

        # Enrich with standard names for UI display
        if scope.affected_standards:
            placeholders = ','.join(['?' for _ in scope.affected_standards])
            cursor = conn.execute(f"""
                SELECT id, code, name FROM standards WHERE id IN ({placeholders})
            """, scope.affected_standards)
            response["standard_details"] = [
                {"id": row["id"], "code": row["code"], "name": row["name"]}
                for row in cursor.fetchall()
            ]
        else:
            response["standard_details"] = []

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
