"""Achievements API blueprint.

Provides REST endpoints for student achievement data management.
"""

from flask import Blueprint, request, jsonify

from src.agents.achievement_agent import AchievementAgent
from src.core.models import AgentSession

achievements_bp = Blueprint("achievements", __name__, url_prefix="/api/institutions/<institution_id>/achievements")

_workspace_manager = None


def init_achievements_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> AchievementAgent:
    """Create an achievement agent instance."""
    session = AgentSession(agent_type="achievement", institution_id=institution_id)
    return AchievementAgent(session, workspace_manager=_workspace_manager)


@achievements_bp.route("/programs", methods=["GET"])
def list_programs(institution_id: str):
    """List programs with achievement data."""
    year = request.args.get("year", type=int)
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_list_programs({"institution_id": institution_id, "year": year}))


@achievements_bp.route("/programs/<program_id>", methods=["GET"])
def get_program_data(institution_id: str, program_id: str):
    """Get achievement data for a program."""
    year = request.args.get("year", type=int)
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_get_data({"institution_id": institution_id, "program_id": program_id, "year": year}))


@achievements_bp.route("/programs/<program_id>", methods=["POST"])
def record_data(institution_id: str, program_id: str):
    """Record achievement data for a program year."""
    data = request.get_json() or {}
    if not data.get("year"):
        return jsonify({"error": "year is required"}), 400

    agent = _create_agent(institution_id)
    result = agent._tool_record_data({"institution_id": institution_id, "program_id": program_id, **data})
    return jsonify(result), 201 if result.get("success") else 400


@achievements_bp.route("/validate", methods=["GET"])
def validate_rates(institution_id: str):
    """Validate rates against benchmarks."""
    program_id = request.args.get("program_id")
    accreditor = request.args.get("accreditor", "ACCSC")
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_validate_rates({
        "institution_id": institution_id, "program_id": program_id, "accreditor": accreditor
    }))


@achievements_bp.route("/trends", methods=["GET"])
def analyze_trends(institution_id: str):
    """Analyze multi-year trends."""
    program_id = request.args.get("program_id")
    years = request.args.get("years", 5, type=int)
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_analyze_trends({
        "institution_id": institution_id, "program_id": program_id, "years": years
    }))


@achievements_bp.route("/programs/<program_id>/disclosure", methods=["GET"])
def generate_disclosure(institution_id: str, program_id: str):
    """Generate disclosure language."""
    format_type = request.args.get("format", "catalog")
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_generate_disclosure({
        "institution_id": institution_id, "program_id": program_id, "format": format_type
    }))


@achievements_bp.route("/report", methods=["GET"])
def generate_report(institution_id: str):
    """Generate achievement summary report."""
    year = request.args.get("year", type=int)
    include_trends = request.args.get("include_trends", "true").lower() == "true"
    agent = _create_agent(institution_id)
    return jsonify(agent._tool_generate_report({
        "institution_id": institution_id, "year": year, "include_trends": include_trends
    }))
