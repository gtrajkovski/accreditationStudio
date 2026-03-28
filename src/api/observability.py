"""Observability API Blueprint.

Provides endpoints for the system observability dashboard showing
system health, AI costs, agent activity, and performance metrics.
"""

from flask import Blueprint, jsonify, request
from src.services.observability_service import get_observability_service


# Create Blueprint
observability_bp = Blueprint("observability", __name__, url_prefix="/api/observability")


@observability_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Get all observability metrics.

    Query params:
        days (int): Days for AI cost lookback (default 30)

    Returns:
        JSON with system_health, ai_costs, agent_activity, performance, timestamp
    """
    days = request.args.get("days", 30, type=int)
    svc = get_observability_service()
    metrics = svc.get_all_metrics()

    # Override ai_costs with custom days if provided
    if days != 30:
        metrics["ai_costs"] = svc.get_ai_costs(days=days)

    return jsonify(metrics)


@observability_bp.route("/health", methods=["GET"])
def get_health():
    """Get system health only (lightweight endpoint).

    Returns:
        JSON with database_size_mb, uptime_seconds, table_counts
    """
    svc = get_observability_service()
    return jsonify(svc.get_system_health())


@observability_bp.route("/costs", methods=["GET"])
def get_costs():
    """Get AI costs breakdown.

    Query params:
        days (int): Days to look back (default 30)

    Returns:
        JSON with total_cost, input_tokens, output_tokens, call_count,
        by_model, daily_trend
    """
    days = request.args.get("days", 30, type=int)
    svc = get_observability_service()
    return jsonify(svc.get_ai_costs(days=days))


def init_observability_bp():
    """Initialize the observability blueprint.

    Returns:
        The observability blueprint instance.
    """
    return observability_bp
