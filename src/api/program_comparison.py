"""Program Comparison API Blueprint.

Provides endpoints for cross-program comparison metrics within an institution.
"""

from flask import Blueprint, jsonify
from src.services.program_comparison_service import (
    build_comparison_matrix,
    get_program_detail,
    get_comparison_radar_data,
)

program_comparison_bp = Blueprint("program_comparison", __name__, url_prefix="/api/institutions")


@program_comparison_bp.route("/<institution_id>/programs/comparison", methods=["GET"])
def get_comparison_matrix(institution_id: str):
    """Get comparison matrix for all programs in an institution."""
    try:
        matrix = build_comparison_matrix(institution_id)
        return jsonify({"success": True, **matrix.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@program_comparison_bp.route("/<institution_id>/programs/<program_id>/metrics", methods=["GET"])
def get_program_metrics(institution_id: str, program_id: str):
    """Get detailed metrics for a single program."""
    try:
        metrics = get_program_detail(institution_id, program_id)
        if not metrics:
            return jsonify({"success": False, "error": "Program not found"}), 404
        return jsonify({"success": True, "program": metrics.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@program_comparison_bp.route("/<institution_id>/programs/radar", methods=["GET"])
def get_radar_chart_data(institution_id: str):
    """Get radar chart data for program comparison."""
    try:
        data = get_comparison_radar_data(institution_id)
        return jsonify({"success": True, **data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
