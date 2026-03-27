"""State Regulatory API Blueprint.

Provides endpoints for:
- State authorization management (CRUD)
- Catalog compliance tracking
- Program approval management
- State readiness scoring
- Preset loading from JSON files
"""

import json
import os
from flask import Blueprint, request, jsonify

from src.services.state_regulatory_service import StateRegulatoryService


# Create Blueprint
state_regulatory_bp = Blueprint("state_regulatory", __name__, url_prefix="/api/state-regulations")

# Module-level reference (set during initialization)
_service: StateRegulatoryService = None


def init_state_regulatory_bp(workspace_manager):
    """Initialize blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance (unused but matches pattern).
    """
    global _service
    _service = StateRegulatoryService()
    return state_regulatory_bp


# =============================================================================
# Authorization Endpoints
# =============================================================================

@state_regulatory_bp.route("", methods=["GET"])
def list_authorizations():
    """List all state authorizations for an institution.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with authorizations list and count.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        authorizations = _service.get_authorizations(institution_id)
        return jsonify({
            "authorizations": [a.to_dict() for a in authorizations],
            "count": len(authorizations),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("", methods=["POST"])
def add_authorization():
    """Add a new state authorization.

    Request Body:
        institution_id: Institution ID (required)
        state_code: State code (required)
        authorization_status: Status (required)
        sara_member: SARA reciprocity (optional)
        effective_date: Effective date (optional)
        renewal_date: Renewal date (optional)
        contact_agency: Contact agency (optional)
        contact_url: Contact URL (optional)
        notes: Notes (optional)

    Returns:
        JSON with created authorization.
    """
    data = request.get_json() or {}

    institution_id = data.get("institution_id")
    state_code = data.get("state_code")
    authorization_status = data.get("authorization_status")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400
    if not state_code:
        return jsonify({"error": "state_code is required"}), 400
    if not authorization_status:
        return jsonify({"error": "authorization_status is required"}), 400

    try:
        auth = _service.add_authorization(
            institution_id=institution_id,
            state_code=state_code.upper(),
            authorization_status=authorization_status,
            sara_member=data.get("sara_member", False),
            effective_date=data.get("effective_date"),
            renewal_date=data.get("renewal_date"),
            contact_agency=data.get("contact_agency"),
            contact_url=data.get("contact_url"),
            notes=data.get("notes"),
        )
        return jsonify({"authorization": auth.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>", methods=["GET"])
def get_authorization(state_code: str):
    """Get authorization details for a specific state.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with authorization data or 404.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        auth = _service.get_authorization(institution_id, state_code.upper())
        if not auth:
            return jsonify({"error": f"No authorization found for state {state_code}"}), 404
        return jsonify({"authorization": auth.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>", methods=["PUT"])
def update_authorization(state_code: str):
    """Update a state authorization.

    Query Parameters:
        institution_id: Institution ID (required)

    Request Body:
        authorization_status: Status (optional)
        sara_member: SARA reciprocity (optional)
        effective_date: Effective date (optional)
        renewal_date: Renewal date (optional)
        contact_agency: Contact agency (optional)
        contact_url: Contact URL (optional)
        notes: Notes (optional)

    Returns:
        JSON with updated authorization.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    data = request.get_json() or {}

    try:
        # Get existing authorization to find its ID
        auth = _service.get_authorization(institution_id, state_code.upper())
        if not auth:
            return jsonify({"error": f"No authorization found for state {state_code}"}), 404

        # Update with provided fields
        updated = _service.update_authorization(
            auth.id,
            **{k: v for k, v in data.items() if k in [
                "authorization_status", "sara_member", "effective_date",
                "renewal_date", "contact_agency", "contact_url", "notes"
            ]}
        )
        return jsonify({"authorization": updated.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>", methods=["DELETE"])
def delete_authorization(state_code: str):
    """Delete a state authorization.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with success status.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        # Get existing authorization to find its ID
        auth = _service.get_authorization(institution_id, state_code.upper())
        if not auth:
            return jsonify({"error": f"No authorization found for state {state_code}"}), 404

        _service.delete_authorization(auth.id)
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Catalog Requirements Endpoints
# =============================================================================

@state_regulatory_bp.route("/<state_code>/requirements", methods=["GET"])
def list_requirements(state_code: str):
    """List catalog requirements for a state.

    Returns:
        JSON with requirements list and count.
    """
    try:
        requirements = _service.get_requirements_for_state(state_code.upper())
        return jsonify({
            "requirements": [r.to_dict() for r in requirements],
            "count": len(requirements),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>/compliance", methods=["GET"])
def get_compliance(state_code: str):
    """Get compliance status for all requirements in a state.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with compliance status and counts.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        compliance = _service.get_compliance_status(institution_id, state_code.upper())

        # Count by status
        satisfied = len([c for c in compliance if c.get("status") == "satisfied"])
        partial = len([c for c in compliance if c.get("status") == "partial"])
        missing = len([c for c in compliance if c.get("status") == "missing"])

        return jsonify({
            "compliance": compliance,
            "satisfied": satisfied,
            "partial": partial,
            "missing": missing,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>/compliance/<requirement_id>", methods=["PUT"])
def update_compliance(state_code: str, requirement_id: str):
    """Update compliance status for a requirement.

    Query Parameters:
        institution_id: Institution ID (required)

    Request Body:
        status: Compliance status (required)
        evidence_doc_id: Evidence document ID (optional)
        page_reference: Page reference (optional)
        notes: Notes (optional)

    Returns:
        JSON with updated compliance.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    data = request.get_json() or {}
    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400

    try:
        compliance = _service.update_compliance(
            institution_id=institution_id,
            requirement_id=requirement_id,
            status=status,
            evidence_doc_id=data.get("evidence_doc_id"),
            page_reference=data.get("page_reference"),
            notes=data.get("notes"),
        )
        return jsonify({"compliance": compliance.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Program Approval Endpoints
# =============================================================================

@state_regulatory_bp.route("/<state_code>/programs", methods=["GET"])
def list_program_approvals(state_code: str):
    """List program approvals for a state.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with approvals list and count.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        approvals = _service.get_program_approvals(institution_id, state_code.upper())
        return jsonify({
            "approvals": [a.to_dict() for a in approvals],
            "count": len(approvals),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>/programs", methods=["POST"])
def add_program_approval(state_code: str):
    """Add a program approval.

    Request Body:
        institution_id: Institution ID (required)
        program_id: Program ID (required)
        board_name: Board name (required)
        approved: Approved status (optional)
        approval_date: Approval date (optional)
        expiration_date: Expiration date (optional)
        license_exam: License exam name (optional)
        min_pass_rate: Minimum pass rate (optional)
        current_pass_rate: Current pass rate (optional)
        board_url: Board URL (optional)
        notes: Notes (optional)

    Returns:
        JSON with created approval.
    """
    data = request.get_json() or {}

    institution_id = data.get("institution_id")
    program_id = data.get("program_id")
    board_name = data.get("board_name")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400
    if not program_id:
        return jsonify({"error": "program_id is required"}), 400
    if not board_name:
        return jsonify({"error": "board_name is required"}), 400

    try:
        approval = _service.add_program_approval(
            institution_id=institution_id,
            program_id=program_id,
            state_code=state_code.upper(),
            board_name=board_name,
            approved=data.get("approved", False),
            approval_date=data.get("approval_date"),
            expiration_date=data.get("expiration_date"),
            license_exam=data.get("license_exam"),
            min_pass_rate=data.get("min_pass_rate"),
            current_pass_rate=data.get("current_pass_rate"),
            board_url=data.get("board_url"),
            notes=data.get("notes"),
        )
        return jsonify({"approval": approval.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>/programs/<approval_id>", methods=["PUT"])
def update_program_approval(state_code: str, approval_id: str):
    """Update a program approval.

    Request Body:
        board_name: Board name (optional)
        approved: Approved status (optional)
        approval_date: Approval date (optional)
        expiration_date: Expiration date (optional)
        license_exam: License exam name (optional)
        min_pass_rate: Minimum pass rate (optional)
        current_pass_rate: Current pass rate (optional)
        board_url: Board URL (optional)
        notes: Notes (optional)

    Returns:
        JSON with updated approval.
    """
    data = request.get_json() or {}

    try:
        approval = _service.update_program_approval(
            approval_id,
            **{k: v for k, v in data.items() if k in [
                "board_name", "board_url", "approved", "approval_date",
                "expiration_date", "license_exam", "min_pass_rate",
                "current_pass_rate", "notes"
            ]}
        )
        if not approval:
            return jsonify({"error": f"Program approval {approval_id} not found"}), 404
        return jsonify({"approval": approval.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/<state_code>/programs/<approval_id>", methods=["DELETE"])
def delete_program_approval(state_code: str, approval_id: str):
    """Delete a program approval.

    Returns:
        JSON with success status.
    """
    try:
        deleted = _service.delete_program_approval(approval_id)
        if not deleted:
            return jsonify({"error": f"Program approval {approval_id} not found"}), 404
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Summary and Scoring Endpoints
# =============================================================================

@state_regulatory_bp.route("/<state_code>/readiness", methods=["GET"])
def get_state_readiness(state_code: str):
    """Get state readiness score.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with readiness score breakdown.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        readiness = _service.compute_state_readiness(institution_id, state_code.upper())
        return jsonify({"readiness": readiness.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/summary", methods=["GET"])
def get_all_states_summary():
    """Get summary for all states with authorizations.

    Query Parameters:
        institution_id: Institution ID (required)

    Returns:
        JSON with states summary list and count.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        summaries = _service.get_all_states_summary(institution_id)
        return jsonify({
            "states": [s.to_dict() for s in summaries],
            "count": len(summaries),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@state_regulatory_bp.route("/renewals", methods=["GET"])
def get_upcoming_renewals():
    """Get upcoming authorization renewals and approval expirations.

    Query Parameters:
        institution_id: Institution ID (required)
        days_ahead: Days to look ahead (default 90)

    Returns:
        JSON with renewals list and count.
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    days_ahead = request.args.get("days_ahead", 90, type=int)

    try:
        renewals = _service.get_upcoming_renewals(institution_id, days_ahead)
        return jsonify({
            "renewals": renewals,
            "count": len(renewals),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Preset Loading Endpoint
# =============================================================================

@state_regulatory_bp.route("/<state_code>/load-preset", methods=["POST"])
def load_state_preset(state_code: str):
    """Load state requirements from preset JSON file.

    Reads data/state_requirements/{state_code}.json and inserts
    requirements into the database.

    Returns:
        JSON with count of loaded requirements.
    """
    state_code_upper = state_code.upper()

    # Build path to preset file
    preset_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "state_requirements",
        f"{state_code.lower()}.json"
    )

    if not os.path.exists(preset_path):
        return jsonify({
            "error": f"No preset file found for state {state_code_upper}"
        }), 404

    try:
        with open(preset_path, "r", encoding="utf-8") as f:
            preset_data = json.load(f)

        requirements = preset_data.get("requirements", [])
        loaded_count = 0

        for req in requirements:
            _service.add_requirement(
                state_code=state_code_upper,
                requirement_key=req.get("requirement_key", ""),
                requirement_name=req.get("requirement_name", ""),
                requirement_text=req.get("requirement_text"),
                category=req.get("category", "disclosure"),
                required=req.get("required", True),
            )
            loaded_count += 1

        return jsonify({
            "loaded": loaded_count,
            "state_code": state_code_upper,
            "state_name": preset_data.get("state_name", ""),
            "regulatory_agency": preset_data.get("regulatory_agency", ""),
        }), 201

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON in preset file: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
