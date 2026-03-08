"""Interview Prep API blueprint.

Provides REST endpoints for interview preparation:
- List available roles
- Generate role-specific prep documents
- Generate questions and talking points
- Identify red flags
- Export prep documents
"""

from flask import Blueprint, request, jsonify, Response
import json

from src.agents.interview_prep_agent import InterviewPrepAgent, INTERVIEW_ROLES
from src.core.models import AgentSession, generate_id, now_iso

interview_prep_bp = Blueprint(
    "interview_prep",
    __name__,
    url_prefix="/api/institutions/<institution_id>/interview-prep"
)

# Module-level dependencies (injected by init function)
_workspace_manager = None


def init_interview_prep_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> InterviewPrepAgent:
    """Create an interview prep agent instance."""
    session = AgentSession(
        agent_type="interview_prep",
        institution_id=institution_id,
    )
    return InterviewPrepAgent(session, workspace_manager=_workspace_manager)


@interview_prep_bp.route("/roles", methods=["GET"])
def list_roles(institution_id: str):
    """List available interview roles."""
    include_focus = request.args.get("include_focus_areas", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_list_roles({
        "include_focus_areas": include_focus,
    })

    return jsonify(result)


@interview_prep_bp.route("", methods=["POST"])
def generate_prep(institution_id: str):
    """Generate interview prep document for a role."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}

    role = data.get("role")
    if not role:
        return jsonify({"error": "role is required"}), 400

    if role not in INTERVIEW_ROLES:
        return jsonify({
            "error": f"Invalid role: {role}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    agent = _create_agent(institution_id)
    result = agent._tool_generate_role_prep({
        "institution_id": institution_id,
        "role": role,
        "program_id": data.get("program_id"),
        "accreditor_code": data.get("accreditor_code", "ACCSC"),
        "include_red_flags": data.get("include_red_flags", True),
    })

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 201


@interview_prep_bp.route("/batch", methods=["POST"])
def generate_batch(institution_id: str):
    """Generate prep documents for multiple roles."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}
    roles = data.get("roles", [])

    if not roles:
        return jsonify({"error": "roles array is required"}), 400

    # Validate all roles
    invalid_roles = [r for r in roles if r not in INTERVIEW_ROLES]
    if invalid_roles:
        return jsonify({
            "error": f"Invalid roles: {invalid_roles}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    agent = _create_agent(institution_id)
    results = []

    for role in roles:
        result = agent._tool_generate_role_prep({
            "institution_id": institution_id,
            "role": role,
            "accreditor_code": data.get("accreditor_code", "ACCSC"),
            "include_red_flags": data.get("include_red_flags", True),
        })
        results.append({
            "role": role,
            "result": result,
        })

    return jsonify({
        "success": True,
        "total": len(results),
        "results": results,
    }), 201


@interview_prep_bp.route("/<prep_id>", methods=["GET"])
def get_prep(institution_id: str, prep_id: str):
    """Get a generated prep document."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    # Search for the prep document
    for role in INTERVIEW_ROLES.keys():
        path = f"visit_prep/interview_prep_{role}.json"
        doc = _workspace_manager.load_file(institution_id, path)
        if doc and doc.get("id") == prep_id:
            return jsonify(doc)

    return jsonify({"error": f"Prep document not found: {prep_id}"}), 404


@interview_prep_bp.route("/<role>/questions", methods=["GET"])
def get_questions(institution_id: str, role: str):
    """Generate questions for a specific role."""
    if role not in INTERVIEW_ROLES:
        return jsonify({
            "error": f"Invalid role: {role}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    focus_area = request.args.get("focus_area")
    include_audit = request.args.get("include_audit_based", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_generate_questions({
        "institution_id": institution_id,
        "role": role,
        "focus_area": focus_area,
        "include_audit_based": include_audit,
    })

    return jsonify(result)


@interview_prep_bp.route("/<role>/talking-points", methods=["POST"])
def get_talking_points(institution_id: str, role: str):
    """Generate talking points for a topic."""
    if role not in INTERVIEW_ROLES:
        return jsonify({
            "error": f"Invalid role: {role}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    data = request.get_json() or {}
    topic = data.get("topic")

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    agent = _create_agent(institution_id)
    result = agent._tool_generate_talking_points({
        "institution_id": institution_id,
        "role": role,
        "topic": topic,
    })

    return jsonify(result)


@interview_prep_bp.route("/<role>/red-flags", methods=["GET"])
def get_red_flags(institution_id: str, role: str):
    """Identify red flag areas for a role."""
    if role not in INTERVIEW_ROLES:
        return jsonify({
            "error": f"Invalid role: {role}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    include_guidance = request.args.get("include_guidance", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_identify_red_flags({
        "institution_id": institution_id,
        "role": role,
        "include_guidance": include_guidance,
    })

    return jsonify(result)


@interview_prep_bp.route("/<role>/do-not-list", methods=["GET"])
def get_do_not_list(institution_id: str, role: str):
    """Get do-not-say list for a role."""
    if role not in INTERVIEW_ROLES:
        return jsonify({
            "error": f"Invalid role: {role}",
            "valid_roles": list(INTERVIEW_ROLES.keys())
        }), 400

    agent = _create_agent(institution_id)
    result = agent._tool_generate_do_not_list({
        "institution_id": institution_id,
        "role": role,
    })

    return jsonify(result)


@interview_prep_bp.route("/<prep_id>/export", methods=["GET"])
def export_prep(institution_id: str, prep_id: str):
    """Export prep document to file."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    export_format = request.args.get("format", "json")

    agent = _create_agent(institution_id)
    result = agent._tool_export_prep({
        "institution_id": institution_id,
        "prep_id": prep_id,
        "format": export_format,
    })

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@interview_prep_bp.route("/stream", methods=["POST"])
def generate_prep_stream(institution_id: str):
    """Generate prep document with SSE streaming progress."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}
    role = data.get("role")

    if not role or role not in INTERVIEW_ROLES:
        return jsonify({"error": f"Invalid role: {role}"}), 400

    def generate():
        yield f"data: {json.dumps({'step': 1, 'total': 4, 'message': 'Loading institution context...'})}\n\n"

        agent = _create_agent(institution_id)

        yield f"data: {json.dumps({'step': 2, 'total': 4, 'message': 'Analyzing audit findings...'})}\n\n"

        yield f"data: {json.dumps({'step': 3, 'total': 4, 'message': 'Generating questions and talking points...'})}\n\n"

        result = agent._tool_generate_role_prep({
            "institution_id": institution_id,
            "role": role,
            "accreditor_code": data.get("accreditor_code", "ACCSC"),
            "include_red_flags": True,
        })

        yield f"data: {json.dumps({'step': 4, 'total': 4, 'message': 'Complete', 'result': result})}\n\n"

    return Response(generate(), mimetype="text/event-stream")
