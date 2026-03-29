"""Packet Wizard API blueprint.

Provides REST endpoints for the 5-step packet creation wizard:
- Session management (create, get, list, abandon)
- Step data updates
- Submission types and standards tree
- Narrative generation
- Preview rendering
- Wizard completion

URL prefix: /api/institutions/<institution_id>/packet-wizard
"""

import logging
from flask import Blueprint, jsonify, request

from src.services.packet_wizard_service import PacketWizardService, get_packet_wizard_service

logger = logging.getLogger(__name__)

packet_wizard_bp = Blueprint(
    "packet_wizard",
    __name__,
    url_prefix="/api/institutions/<institution_id>/packet-wizard"
)

# Module-level dependencies (injected by init function)
_service: PacketWizardService = None


def init_packet_wizard_bp(workspace_manager=None, standards_store=None):
    """Initialize blueprint with dependencies."""
    global _service
    _service = get_packet_wizard_service(workspace_manager, standards_store)


# =============================================================================
# Session Endpoints
# =============================================================================

@packet_wizard_bp.route("/sessions", methods=["POST"])
def create_session(institution_id: str):
    """Create new wizard session.

    Request body (optional):
        created_by: User identifier

    Returns:
        201: Created session object
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    data = request.get_json() or {}

    try:
        session = _service.create_session(institution_id, data.get("created_by"))
        return jsonify(session.to_dict()), 201
    except Exception as e:
        logger.exception("Failed to create wizard session")
        return jsonify({"error": str(e)}), 500


@packet_wizard_bp.route("/sessions", methods=["GET"])
def list_sessions(institution_id: str):
    """List wizard sessions for institution.

    Query params:
        status: Filter by status (draft, complete, abandoned)

    Returns:
        200: List of session objects
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    status = request.args.get("status")

    try:
        sessions = _service.list_sessions(institution_id, status)
        return jsonify({
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })
    except Exception as e:
        logger.exception("Failed to list wizard sessions")
        return jsonify({"error": str(e)}), 500


@packet_wizard_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(institution_id: str, session_id: str):
    """Get session state.

    Returns:
        200: Session object with step_data and validation info
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    session = _service.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Verify session belongs to institution
    if session.institution_id != institution_id:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict())


@packet_wizard_bp.route("/sessions/<session_id>", methods=["DELETE"])
def abandon_session(institution_id: str, session_id: str):
    """Abandon (soft-delete) a session.

    Returns:
        200: Updated session with status=abandoned
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        session = _service.abandon_session(session_id)
        return jsonify(session.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Failed to abandon session")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Step Endpoints
# =============================================================================

@packet_wizard_bp.route("/sessions/<session_id>/step/<int:step>", methods=["PUT"])
def update_step(institution_id: str, session_id: str, step: int):
    """Update step data.

    Request body:
        Any step-specific data to merge into step_data

    Step 1 (Submission Type):
        submission_type: "self_study" | "response" | "teach_out" | "annual" | "substantive_change"
        accreditor_code: Accreditor code (e.g., "ACCSC")
        packet_name: Optional packet title

    Step 2 (Standards):
        selected_standards: List of standard IDs

    Step 3 (Evidence):
        evidence_mappings: {standard_id: [{document_id, title, ...}]}

    Step 4 (Narrative):
        narratives: {standard_id: "narrative text"}

    Returns:
        200: Updated session object
        400: Validation error
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    if step < 1 or step > 5:
        return jsonify({"error": "Step must be between 1 and 5"}), 400

    data = request.get_json() or {}

    try:
        session = _service.update_step(session_id, step, data)
        return jsonify(session.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Failed to update step")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Reference Data Endpoints
# =============================================================================

@packet_wizard_bp.route("/submission-types", methods=["GET"])
def get_submission_types(institution_id: str):
    """Get available submission types.

    Returns:
        200: List of submission type objects with id, name, description
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    types = _service.get_submission_types()
    return jsonify({"types": types})


@packet_wizard_bp.route("/standards-tree", methods=["GET"])
def get_standards_tree(institution_id: str):
    """Get standards tree for selection.

    Query params:
        accreditor: Accreditor code (defaults to institution's primary accreditor)

    Returns:
        200: List of standards with hierarchy info
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    accreditor = request.args.get("accreditor")

    try:
        tree = _service.get_standards_tree(institution_id, accreditor)
        return jsonify({"tree": tree, "count": len(tree)})
    except Exception as e:
        logger.exception("Failed to get standards tree")
        return jsonify({"error": str(e)}), 500


@packet_wizard_bp.route("/standards/<standard_id>/evidence", methods=["GET"])
def get_evidence_for_standard(institution_id: str, standard_id: str):
    """Get available evidence for a standard.

    Returns:
        200: List of evidence items (documents, excerpts)
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        evidence = _service.get_evidence_for_standard(institution_id, standard_id)
        return jsonify({"evidence": evidence, "count": len(evidence)})
    except Exception as e:
        logger.exception("Failed to get evidence for standard")
        return jsonify({"error": str(e)}), 500


@packet_wizard_bp.route("/standards/<standard_id>/suggest", methods=["GET"])
def suggest_evidence(institution_id: str, standard_id: str):
    """AI-suggest evidence for a standard.

    Uses semantic search to find relevant documents.

    Returns:
        200: List of suggested evidence items
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        suggestions = _service.suggest_evidence(institution_id, standard_id)
        return jsonify({"suggestions": suggestions, "count": len(suggestions)})
    except Exception as e:
        logger.exception("Failed to suggest evidence")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Generation Endpoints
# =============================================================================

@packet_wizard_bp.route("/sessions/<session_id>/generate-narrative", methods=["POST"])
def generate_narrative(institution_id: str, session_id: str):
    """Generate narrative for section.

    Request body:
        section_id: Standard ID to generate narrative for

    Returns:
        200: Generated narrative text
        400: Missing section_id
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    data = request.get_json() or {}
    section_id = data.get("section_id")

    if not section_id:
        return jsonify({"error": "section_id is required"}), 400

    try:
        narrative = _service.generate_narrative(session_id, section_id)
        return jsonify({
            "narrative": narrative,
            "section_id": section_id,
            "generated": True,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Failed to generate narrative")
        return jsonify({"error": str(e)}), 500


@packet_wizard_bp.route("/sessions/<session_id>/preview", methods=["GET"])
def get_preview(institution_id: str, session_id: str):
    """Get HTML preview of packet.

    Returns:
        200: HTML preview string
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        html = _service.render_preview(session_id)
        return jsonify({"html": html})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("Failed to render preview")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Completion Endpoint
# =============================================================================

@packet_wizard_bp.route("/sessions/<session_id>/complete", methods=["POST"])
def complete_wizard(institution_id: str, session_id: str):
    """Complete wizard and create packet.

    Validates evidence coverage (80% required) and creates the packet record.

    Returns:
        200: {session_id, packet_id, status, message}
        400: Validation failed (coverage too low)
        404: Session not found
    """
    if not _service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        result = _service.complete_wizard(session_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to complete wizard")
        return jsonify({"error": str(e)}), 500
