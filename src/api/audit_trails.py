"""Audit Trails API Blueprint.

Endpoints for querying and exporting agent session logs.
"""

import json
from datetime import datetime, timezone
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file

from src.services.audit_trail_service import AuditTrailService


audit_trails_bp = Blueprint("audit_trails", __name__, url_prefix="/api/audit-trails")
_workspace_manager = None


def init_audit_trails_bp(workspace_manager):
    """Initialize audit trails blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance
    """
    global _workspace_manager
    _workspace_manager = workspace_manager


@audit_trails_bp.route("/institutions/<institution_id>/sessions", methods=["GET"])
def list_sessions(institution_id: str):
    """List agent sessions with optional filters.

    Query params:
        start_date: ISO8601 start date (optional)
        end_date: ISO8601 end date (optional)
        agent_type: Filter by agent type (optional)
        operation: Filter by operation (optional)
        limit: Maximum number of sessions (default 100)

    Returns:
        JSON with sessions array and count
    """
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        agent_type = request.args.get("agent_type")
        operation = request.args.get("operation")
        limit = int(request.args.get("limit", 100))

        sessions = AuditTrailService.query_sessions(
            institution_id=institution_id,
            start_date=start_date,
            end_date=end_date,
            agent_type=agent_type,
            operation=operation,
        )

        # Apply limit
        sessions = sessions[:limit]

        return jsonify({
            "success": True,
            "sessions": sessions,
            "count": len(sessions),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@audit_trails_bp.route("/institutions/<institution_id>/sessions/<session_id>", methods=["GET"])
def get_session(institution_id: str, session_id: str):
    """Get a single session by ID.

    Args:
        institution_id: Institution ID
        session_id: Session ID

    Returns:
        JSON with session data
    """
    try:
        session = AuditTrailService.get_session(
            institution_id=institution_id,
            session_id=session_id
        )

        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        return jsonify({
            "success": True,
            "session": session,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@audit_trails_bp.route("/institutions/<institution_id>/agent-types", methods=["GET"])
def get_agent_types(institution_id: str):
    """Get unique agent types for filter dropdown.

    Args:
        institution_id: Institution ID

    Returns:
        JSON with agent_types array
    """
    try:
        agent_types = AuditTrailService.get_agent_types(institution_id)

        return jsonify({
            "success": True,
            "agent_types": agent_types,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@audit_trails_bp.route("/institutions/<institution_id>/export", methods=["POST"])
def export_audit_trail(institution_id: str):
    """Export audit trail as JSON file.

    Request Body:
        start_date: ISO8601 start date (optional)
        end_date: ISO8601 end date (optional)
        agent_type: Filter by agent type (optional)
        operation: Filter by operation (optional)

    Returns:
        JSON file download
    """
    try:
        data = request.get_json() or {}

        # Query sessions with filters
        sessions = AuditTrailService.query_sessions(
            institution_id=institution_id,
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            agent_type=data.get("agent_type"),
            operation=data.get("operation"),
        )

        # Build export payload
        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "institution_id": institution_id,
            "filters": {
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "agent_type": data.get("agent_type"),
                "operation": data.get("operation"),
            },
            "session_count": len(sessions),
            "sessions": sessions,
            "export_version": "1.0",
        }

        # Create JSON file in memory
        json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
        buffer = BytesIO(json_bytes)
        buffer.seek(0)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_trail_{institution_id}_{timestamp}.json"

        return send_file(
            buffer,
            mimetype="application/json",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
