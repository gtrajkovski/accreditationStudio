"""Faculty API blueprint.

Provides REST endpoints for faculty management:
- CRUD for faculty members
- Credential and license management
- Compliance checking and reporting
"""

import json
from flask import Blueprint, request, jsonify

from src.agents.faculty_agent import FacultyAgent
from src.core.models import AgentSession, FacultyMember, generate_id, now_iso

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/institutions/<institution_id>/faculty")

# Module-level dependencies (injected by init function)
_workspace_manager = None


def init_faculty_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> FacultyAgent:
    """Create a faculty agent instance."""
    session = AgentSession(
        agent_type="faculty",
        institution_id=institution_id,
    )
    return FacultyAgent(session, workspace_manager=_workspace_manager)


def _load_faculty_registry(institution_id: str):
    """Load faculty registry from workspace."""
    data = _workspace_manager.load_file(institution_id, "faculty/faculty_registry.json")
    if not data:
        return []
    return [FacultyMember.from_dict(f) for f in data.get("members", [])]


def _save_faculty_registry(institution_id: str, members):
    """Save faculty registry to workspace."""
    data = {
        "members": [m.to_dict() for m in members],
        "updated_at": now_iso(),
    }
    _workspace_manager.save_file(institution_id, "faculty/faculty_registry.json", data)


@faculty_bp.route("", methods=["GET"])
def list_faculty(institution_id: str):
    """List faculty members with optional filters."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    status = request.args.get("status", "all")
    employment_type = request.args.get("employment_type", "all")
    department = request.args.get("department")
    active_only = request.args.get("active_only", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_list_faculty({
        "institution_id": institution_id,
        "status_filter": status,
        "employment_type": employment_type,
        "department": department,
        "active_only": active_only,
    })

    return jsonify(result)


@faculty_bp.route("", methods=["POST"])
def create_faculty(institution_id: str):
    """Create a new faculty member."""
    data = request.get_json() or {}

    if not data.get("first_name") or not data.get("last_name"):
        return jsonify({"error": "first_name and last_name are required"}), 400

    agent = _create_agent(institution_id)
    result = agent._tool_add_faculty_member({
        "institution_id": institution_id,
        **data,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@faculty_bp.route("/<faculty_id>", methods=["GET"])
def get_faculty(institution_id: str, faculty_id: str):
    """Get faculty member details."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    agent = _create_agent(institution_id)
    result = agent._tool_get_faculty_member({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
    })

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@faculty_bp.route("/<faculty_id>", methods=["PUT"])
def update_faculty(institution_id: str, faculty_id: str):
    """Update faculty member basic info."""
    data = request.get_json() or {}

    members = _load_faculty_registry(institution_id)
    member = next((m for m in members if m.id == faculty_id), None)

    if not member:
        return jsonify({"error": "Faculty member not found"}), 404

    # Update allowed fields
    for field in ["first_name", "last_name", "email", "phone", "title",
                  "department", "employment_type", "is_active"]:
        if field in data:
            setattr(member, field, data[field])

    member.updated_at = now_iso()
    _save_faculty_registry(institution_id, members)

    return jsonify({"success": True, "faculty": member.to_dict()})


@faculty_bp.route("/<faculty_id>", methods=["DELETE"])
def delete_faculty(institution_id: str, faculty_id: str):
    """Delete (deactivate) a faculty member."""
    members = _load_faculty_registry(institution_id)
    member = next((m for m in members if m.id == faculty_id), None)

    if not member:
        return jsonify({"error": "Faculty member not found"}), 404

    # Soft delete - mark inactive
    member.is_active = False
    member.updated_at = now_iso()
    _save_faculty_registry(institution_id, members)

    return jsonify({"success": True, "message": "Faculty member deactivated"})


@faculty_bp.route("/<faculty_id>/credentials", methods=["POST"])
def add_credential(institution_id: str, faculty_id: str):
    """Add academic credential to faculty member."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_update_credentials({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
        "action": "add_credential",
        "credential_data": data,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@faculty_bp.route("/<faculty_id>/licenses", methods=["POST"])
def add_license(institution_id: str, faculty_id: str):
    """Add professional license to faculty member."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_update_credentials({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
        "action": "add_license",
        "credential_data": data,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@faculty_bp.route("/<faculty_id>/verify-licenses", methods=["POST"])
def verify_licenses(institution_id: str, faculty_id: str):
    """Verify licenses for a faculty member."""
    data = request.get_json() or {}
    license_id = data.get("license_id")

    if not license_id:
        return jsonify({"error": "license_id is required"}), 400

    agent = _create_agent(institution_id)
    result = agent._tool_verify_license({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
        "license_id": license_id,
    })

    return jsonify(result)


@faculty_bp.route("/check-qualifications", methods=["POST"])
def check_qualifications(institution_id: str):
    """Check teaching qualifications for faculty."""
    data = request.get_json() or {}
    faculty_id = data.get("faculty_id", "all")

    agent = _create_agent(institution_id)
    result = agent._tool_check_qualifications({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
    })

    return jsonify(result)


@faculty_bp.route("/compliance-report", methods=["GET"])
def compliance_report(institution_id: str):
    """Generate faculty compliance report."""
    include_details = request.args.get("details", "true").lower() == "true"
    report_format = request.args.get("format", "detailed")

    agent = _create_agent(institution_id)
    result = agent._tool_generate_report({
        "institution_id": institution_id,
        "include_details": include_details,
        "format": report_format,
    })

    return jsonify(result)


@faculty_bp.route("/expiring-licenses", methods=["GET"])
def expiring_licenses(institution_id: str):
    """Get licenses expiring within N days."""
    days = int(request.args.get("days", 90))

    agent = _create_agent(institution_id)
    expiring = agent.get_expiring_licenses(institution_id, days)

    return jsonify({
        "days": days,
        "count": len(expiring),
        "licenses": expiring,
    })


@faculty_bp.route("/<faculty_id>/assignments", methods=["POST"])
def add_assignment(institution_id: str, faculty_id: str):
    """Add teaching assignment to faculty member."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_update_assignments({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
        "action": "add",
        "assignment_data": data,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@faculty_bp.route("/<faculty_id>/assignments/<assignment_id>", methods=["DELETE"])
def remove_assignment(institution_id: str, faculty_id: str, assignment_id: str):
    """Remove teaching assignment from faculty member."""
    agent = _create_agent(institution_id)
    result = agent._tool_update_assignments({
        "institution_id": institution_id,
        "faculty_id": faculty_id,
        "action": "remove",
        "assignment_data": {"id": assignment_id},
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
