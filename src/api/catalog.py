"""Catalog API blueprint.

Provides REST endpoints for catalog management:
- List, create, update catalogs
- Audit catalogs against requirements
- Generate and export catalogs
"""

from flask import Blueprint, request, jsonify

from src.agents.catalog_agent import CatalogAgent
from src.core.models import AgentSession, generate_id, now_iso

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/institutions/<institution_id>/catalog")

# Module-level dependencies (injected by init function)
_workspace_manager = None


def init_catalog_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> CatalogAgent:
    """Create a catalog agent instance."""
    session = AgentSession(
        agent_type="catalog",
        institution_id=institution_id,
    )
    return CatalogAgent(session, workspace_manager=_workspace_manager)


@catalog_bp.route("", methods=["GET"])
def list_catalogs(institution_id: str):
    """List all catalogs for an institution."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    include_drafts = request.args.get("include_drafts", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_list_catalogs({
        "institution_id": institution_id,
        "include_drafts": include_drafts,
    })

    return jsonify(result)


@catalog_bp.route("", methods=["POST"])
def create_catalog(institution_id: str):
    """Create a new catalog (build from scratch)."""
    data = request.get_json() or {}

    language = data.get("language", "en")
    sections = data.get("sections")
    draft_mode = data.get("draft_mode", True)

    agent = _create_agent(institution_id)
    result = agent._tool_build_catalog({
        "institution_id": institution_id,
        "language": language,
        "sections": sections,
        "draft_mode": draft_mode,
    })

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@catalog_bp.route("/<catalog_id>", methods=["GET"])
def get_catalog(institution_id: str, catalog_id: str):
    """Get catalog details."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    agent = _create_agent(institution_id)
    catalog = agent._load_catalog(institution_id, catalog_id)

    if not catalog:
        return jsonify({"error": "Catalog not found"}), 404

    return jsonify({
        "success": True,
        "catalog": catalog,
    })


@catalog_bp.route("/<catalog_id>/sections/<section_id>", methods=["PUT"])
def update_section(institution_id: str, catalog_id: str, section_id: str):
    """Update or regenerate a catalog section."""
    data = request.get_json() or {}

    # If content provided, update directly
    if "content" in data:
        agent = _create_agent(institution_id)
        catalog = agent._load_catalog(institution_id, catalog_id)

        if not catalog:
            return jsonify({"error": "Catalog not found"}), 404

        if section_id not in catalog.get("sections", {}):
            catalog["sections"][section_id] = {}

        catalog["sections"][section_id]["content"] = data["content"]
        catalog["sections"][section_id]["updated_at"] = now_iso()
        catalog["updated_at"] = now_iso()

        agent._save_catalog(institution_id, catalog)

        return jsonify({
            "success": True,
            "section_id": section_id,
            "updated_at": catalog["updated_at"],
        })

    # Otherwise regenerate section
    language = data.get("language", "en")
    draft_mode = data.get("draft_mode", False)

    agent = _create_agent(institution_id)
    result = agent._tool_generate_section({
        "institution_id": institution_id,
        "section_id": section_id,
        "language": language,
        "draft_mode": draft_mode,
    })

    if result.get("success"):
        # Update catalog with new content
        catalog = agent._load_catalog(institution_id, catalog_id)
        if catalog:
            if section_id not in catalog.get("sections", {}):
                catalog["sections"][section_id] = {}

            catalog["sections"][section_id]["content"] = result["content"]
            catalog["sections"][section_id]["generated_at"] = result["generated_at"]
            catalog["updated_at"] = now_iso()

            agent._save_catalog(institution_id, catalog)

    return jsonify(result)


@catalog_bp.route("/<catalog_id>/audit", methods=["POST"])
def audit_catalog(institution_id: str, catalog_id: str):
    """Audit catalog against regulatory requirements."""
    data = request.get_json() or {}

    accreditor_code = data.get("accreditor_code", "ACCSC")
    check_consistency = data.get("check_consistency", True)

    agent = _create_agent(institution_id)
    result = agent._tool_audit_catalog({
        "institution_id": institution_id,
        "catalog_id": catalog_id,
        "accreditor_code": accreditor_code,
        "check_consistency": check_consistency,
    })

    return jsonify(result)


@catalog_bp.route("/<catalog_id>/validate", methods=["POST"])
def validate_catalog(institution_id: str, catalog_id: str):
    """Validate catalog completeness."""
    data = request.get_json() or {}

    validation_level = data.get("validation_level", "standard")

    agent = _create_agent(institution_id)
    result = agent._tool_validate_catalog({
        "institution_id": institution_id,
        "catalog_id": catalog_id,
        "validation_level": validation_level,
    })

    return jsonify(result)


@catalog_bp.route("/<catalog_id>/export", methods=["POST"])
def export_catalog(institution_id: str, catalog_id: str):
    """Export catalog to file format."""
    data = request.get_json() or {}

    export_format = data.get("format", "docx")
    include_toc = data.get("include_toc", True)

    agent = _create_agent(institution_id)
    result = agent._tool_export_catalog({
        "institution_id": institution_id,
        "catalog_id": catalog_id,
        "format": export_format,
        "include_toc": include_toc,
    })

    return jsonify(result)


@catalog_bp.route("/<catalog_id>/update-from-truth", methods=["POST"])
def update_from_truth(institution_id: str, catalog_id: str):
    """Update catalog sections from truth index."""
    data = request.get_json() or {}

    sections_to_update = data.get("sections")

    agent = _create_agent(institution_id)
    result = agent._tool_update_from_truth({
        "institution_id": institution_id,
        "catalog_id": catalog_id,
        "sections_to_update": sections_to_update,
    })

    return jsonify(result)


@catalog_bp.route("/requirements", methods=["GET"])
def get_requirements(institution_id: str):
    """Get catalog requirements for accreditor."""
    accreditor_code = request.args.get("accreditor", "ACCSC")
    state_code = request.args.get("state")
    include_federal = request.args.get("include_federal", "true").lower() == "true"

    agent = _create_agent(institution_id)
    result = agent._tool_get_requirements({
        "accreditor_code": accreditor_code,
        "include_federal": include_federal,
        "state_code": state_code,
    })

    return jsonify(result)


@catalog_bp.route("/generate-section", methods=["POST"])
def generate_section(institution_id: str):
    """Generate a catalog section (standalone, not attached to catalog)."""
    data = request.get_json() or {}

    section_id = data.get("section_id")
    if not section_id:
        return jsonify({"error": "section_id is required"}), 400

    language = data.get("language", "en")
    draft_mode = data.get("draft_mode", True)
    program_id = data.get("program_id")

    agent = _create_agent(institution_id)
    result = agent._tool_generate_section({
        "institution_id": institution_id,
        "section_id": section_id,
        "language": language,
        "draft_mode": draft_mode,
        "program_id": program_id,
    })

    return jsonify(result)
