"""Onboarding API blueprint for AccreditAI.

Provides endpoints for managing the 4-step onboarding wizard.
"""

from flask import Blueprint, request, jsonify, g

from src.services import onboarding_service

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/api/onboarding")


def init_onboarding_bp():
    """Initialize onboarding blueprint (no dependencies required)."""
    pass


@onboarding_bp.route("/progress", methods=["GET"])
def get_progress():
    """Get onboarding progress for current user's institution.

    Returns:
        JSON with progress data or error
    """
    # Get institution from current user or query param
    institution_id = request.args.get("institution_id")

    # Try to get from current user if available
    if not institution_id:
        user = g.get("current_user")
        if user and user.get("institution_id"):
            institution_id = user["institution_id"]

    if not institution_id:
        return jsonify({"error": "No institution specified"}), 400

    progress = onboarding_service.get_progress(institution_id)

    if not progress:
        # Start onboarding if not started
        progress = onboarding_service.start_onboarding(institution_id)

    return jsonify(progress)


@onboarding_bp.route("/step/<int:step>", methods=["POST"])
def complete_step(step: int):
    """Mark onboarding step as complete.

    Args:
        step: Step number (1-4)

    Body (optional):
        {data: {...}} - Step-specific data

    Returns:
        JSON with updated progress
    """
    institution_id = request.args.get("institution_id")

    # Try to get from current user if available
    if not institution_id:
        user = g.get("current_user")
        if user and user.get("institution_id"):
            institution_id = user["institution_id"]

    if not institution_id:
        return jsonify({"error": "No institution specified"}), 400

    if step < 1 or step > 4:
        return jsonify({"error": "Step must be 1-4"}), 400

    data = request.get_json(silent=True) or {}
    step_data = data.get("data")

    try:
        progress = onboarding_service.update_step(institution_id, step, step_data)
        return jsonify(progress)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@onboarding_bp.route("/skip", methods=["POST"])
def skip_onboarding():
    """Skip remaining onboarding steps.

    Returns:
        JSON with updated progress (completed=true)
    """
    institution_id = request.args.get("institution_id")

    # Try to get from current user if available
    if not institution_id:
        user = g.get("current_user")
        if user and user.get("institution_id"):
            institution_id = user["institution_id"]

    if not institution_id:
        return jsonify({"error": "No institution specified"}), 400

    progress = onboarding_service.skip_onboarding(institution_id)
    return jsonify(progress)


@onboarding_bp.route("/check", methods=["GET"])
def check_onboarding():
    """Check if current user should see onboarding.

    Returns:
        JSON with {should_show: bool}
    """
    user = g.get("current_user")
    if not user:
        return jsonify({"should_show": False})

    should_show = onboarding_service.should_show_onboarding(user["id"])
    return jsonify({"should_show": should_show})
