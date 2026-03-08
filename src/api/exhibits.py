"""Exhibits API blueprint.

Provides REST endpoints for exhibit/evidence management.
"""

from flask import Blueprint, request, jsonify

from src.agents.evidence_agent import EvidenceAgent
from src.core.models import AgentSession

exhibits_bp = Blueprint("exhibits", __name__, url_prefix="/api/institutions/<institution_id>/exhibits")

_workspace_manager = None


def init_exhibits_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> EvidenceAgent:
    """Create an evidence agent instance."""
    session = AgentSession(agent_type="evidence", institution_id=institution_id)
    return EvidenceAgent(session, workspace_manager=_workspace_manager)


@exhibits_bp.route("", methods=["GET"])
def list_exhibits(institution_id: str):
    """List all exhibits."""
    category = request.args.get("category")
    status = request.args.get("status")

    agent = _create_agent(institution_id)
    result = agent._tool_list_exhibits({
        "institution_id": institution_id,
        "category": category,
        "status": status,
    })
    return jsonify(result)


@exhibits_bp.route("", methods=["POST"])
def add_exhibit(institution_id: str):
    """Add a new exhibit."""
    data = request.get_json() or {}

    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    agent = _create_agent(institution_id)
    result = agent._tool_add_exhibit({
        "institution_id": institution_id,
        **data,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@exhibits_bp.route("/<exhibit_id>/validate", methods=["POST"])
def validate_exhibit(institution_id: str, exhibit_id: str):
    """Validate an exhibit."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_validate_exhibit({
        "institution_id": institution_id,
        "exhibit_id": exhibit_id,
        **data,
    })
    return jsonify(result)


@exhibits_bp.route("/requirements", methods=["GET"])
def get_requirements(institution_id: str):
    """Get evidence requirements."""
    category = request.args.get("category")

    agent = _create_agent(institution_id)
    result = agent._tool_get_required({
        "institution_id": institution_id,
        "category": category,
    })
    return jsonify(result)


@exhibits_bp.route("/gaps", methods=["GET"])
def check_gaps(institution_id: str):
    """Check for evidence gaps."""
    categories = request.args.getlist("category")

    agent = _create_agent(institution_id)
    result = agent._tool_check_gaps({
        "institution_id": institution_id,
        "categories": categories if categories else None,
    })
    return jsonify(result)


@exhibits_bp.route("/index", methods=["POST"])
def build_index(institution_id: str):
    """Build exhibit index."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_build_index({
        "institution_id": institution_id,
        "submission_type": data.get("submission_type", "self_study"),
    })
    return jsonify(result)


@exhibits_bp.route("/suggest", methods=["POST"])
def suggest_evidence(institution_id: str):
    """Suggest additional evidence."""
    data = request.get_json() or {}

    agent = _create_agent(institution_id)
    result = agent._tool_suggest_evidence({
        "institution_id": institution_id,
        **data,
    })
    return jsonify(result)
