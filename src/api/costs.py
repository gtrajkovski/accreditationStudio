"""Cost Tracking API Blueprint.

Provides endpoints for viewing AI API cost summaries and managing budgets.
"""

from flask import Blueprint, jsonify, request
from src.services.cost_tracking_service import (
    get_cost_summary,
    check_budget,
    set_budget
)

costs_bp = Blueprint("costs", __name__, url_prefix="/api/costs")


@costs_bp.route("/summary")
def summary():
    """Get overall cost summary.

    Query params:
        days (int): Number of days to look back (default 30)

    Returns:
        JSON with total_cost, input_tokens, output_tokens, call_count,
        by_agent, by_model, daily_trend
    """
    days = request.args.get("days", 30, type=int)
    return jsonify(get_cost_summary(days=days))


@costs_bp.route("/summary/<institution_id>")
def institution_summary(institution_id):
    """Get cost summary for a specific institution.

    Args:
        institution_id: Institution ID

    Query params:
        days (int): Number of days to look back (default 30)

    Returns:
        JSON with cost summary filtered to institution
    """
    days = request.args.get("days", 30, type=int)
    return jsonify(get_cost_summary(institution_id=institution_id, days=days))


@costs_bp.route("/budget/<institution_id>", methods=["GET"])
def budget_status(institution_id):
    """Get budget status for an institution.

    Args:
        institution_id: Institution ID

    Returns:
        JSON with has_budget, monthly_budget, used, remaining, percent_used, alert
    """
    return jsonify(check_budget(institution_id))


@costs_bp.route("/budget/<institution_id>", methods=["POST"])
def update_budget(institution_id):
    """Set or update budget for an institution.

    Args:
        institution_id: Institution ID

    Request body:
        {
            "monthly_budget_usd": 100.0,
            "alert_threshold": 0.8  // Optional, default 0.8
        }

    Returns:
        JSON with success status
    """
    data = request.get_json()

    if not data or "monthly_budget_usd" not in data:
        return jsonify({"error": "monthly_budget_usd is required"}), 400

    monthly_budget = data["monthly_budget_usd"]
    alert_threshold = data.get("alert_threshold", 0.8)

    if monthly_budget <= 0:
        return jsonify({"error": "monthly_budget_usd must be positive"}), 400

    if not 0 < alert_threshold <= 1:
        return jsonify({"error": "alert_threshold must be between 0 and 1"}), 400

    set_budget(institution_id, monthly_budget, alert_threshold)

    return jsonify({
        "success": True,
        "institution_id": institution_id,
        "monthly_budget_usd": monthly_budget,
        "alert_threshold": alert_threshold
    })
