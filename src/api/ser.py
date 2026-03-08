"""SER (Self-Evaluation Report) API blueprint.

Provides REST endpoints for SER drafting:
- List sections by accreditor
- Draft individual sections
- Generate full SER
- Validate and export
"""

from flask import Blueprint, request, jsonify, Response
import json

from src.agents.ser_drafting_agent import SERDraftingAgent, SER_SECTIONS
from src.core.models import AgentSession, generate_id, now_iso

ser_bp = Blueprint(
    "ser",
    __name__,
    url_prefix="/api/institutions/<institution_id>/ser"
)

# Module-level dependencies
_workspace_manager = None


def init_ser_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> SERDraftingAgent:
    """Create an SER drafting agent instance."""
    session = AgentSession(
        agent_type="ser_drafting",
        institution_id=institution_id,
    )
    return SERDraftingAgent(session, workspace_manager=_workspace_manager)


@ser_bp.route("/sections", methods=["GET"])
def list_sections(institution_id: str):
    """List SER sections for an accreditor."""
    accreditor = request.args.get("accreditor_code", "ACCSC")

    agent = _create_agent(institution_id)
    result = agent._tool_list_sections({
        "accreditor_code": accreditor,
    })

    return jsonify(result)


@ser_bp.route("", methods=["POST"])
def create_ser(institution_id: str):
    """Generate a new SER draft."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}
    accreditor = data.get("accreditor_code", "ACCSC")
    mode = data.get("writing_mode", "draft")
    sections = data.get("sections_to_include", [])

    agent = _create_agent(institution_id)
    result = agent._tool_generate_full({
        "institution_id": institution_id,
        "accreditor_code": accreditor,
        "writing_mode": mode,
        "sections_to_include": sections,
    })

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 201


@ser_bp.route("/<ser_id>", methods=["GET"])
def get_ser(institution_id: str, ser_id: str):
    """Get an existing SER draft."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    agent = _create_agent(institution_id)
    result = agent._tool_get_draft({
        "institution_id": institution_id,
        "ser_id": ser_id,
    })

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@ser_bp.route("/<ser_id>/sections/<section_id>", methods=["POST"])
def draft_section(institution_id: str, ser_id: str, section_id: str):
    """Draft or regenerate a specific section."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}
    accreditor = data.get("accreditor_code", "ACCSC")
    mode = data.get("writing_mode", "draft")

    agent = _create_agent(institution_id)
    result = agent._tool_draft_section({
        "institution_id": institution_id,
        "section_id": section_id,
        "accreditor_code": accreditor,
        "writing_mode": mode,
    })

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@ser_bp.route("/<ser_id>/sections/<section_id>/validate", methods=["GET"])
def validate_section(institution_id: str, ser_id: str, section_id: str):
    """Validate a specific section."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    agent = _create_agent(institution_id)
    result = agent._tool_validate_section({
        "institution_id": institution_id,
        "ser_id": ser_id,
        "section_id": section_id,
    })

    return jsonify(result)


@ser_bp.route("/<ser_id>/export", methods=["GET"])
def export_ser(institution_id: str, ser_id: str):
    """Export SER to file."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    export_format = request.args.get("format", "json")

    agent = _create_agent(institution_id)
    result = agent._tool_export({
        "institution_id": institution_id,
        "ser_id": ser_id,
        "format": export_format,
    })

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


@ser_bp.route("/auto-fill", methods=["GET"])
def auto_fill_data(institution_id: str):
    """Get auto-fill data for SER sections."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    section_id = request.args.get("section_id")

    agent = _create_agent(institution_id)
    result = agent._tool_auto_fill({
        "institution_id": institution_id,
        "section_id": section_id,
    })

    return jsonify(result)


@ser_bp.route("/stream", methods=["POST"])
def generate_ser_stream(institution_id: str):
    """Generate SER with SSE streaming progress."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = request.get_json() or {}
    accreditor = data.get("accreditor_code", "ACCSC")
    mode = data.get("writing_mode", "draft")

    sections = SER_SECTIONS.get(accreditor.upper(), [])
    total_sections = len(sections)

    def generate():
        yield f"data: {json.dumps({'step': 0, 'total': total_sections + 2, 'message': 'Loading institution data...'})}\n\n"

        agent = _create_agent(institution_id)

        yield f"data: {json.dumps({'step': 1, 'total': total_sections + 2, 'message': 'Initializing SER structure...'})}\n\n"

        for i, section in enumerate(sections):
            section_name = section.get("name", f"Section {i+1}")
            msg = f"Drafting {section_name}..."
            yield f"data: {json.dumps({'step': i + 2, 'total': total_sections + 2, 'message': msg})}\n\n"

        result = agent._tool_generate_full({
            "institution_id": institution_id,
            "accreditor_code": accreditor,
            "writing_mode": mode,
        })

        yield f"data: {json.dumps({'step': total_sections + 2, 'total': total_sections + 2, 'message': 'Complete', 'result': result})}\n\n"

    return Response(generate(), mimetype="text/event-stream")
