"""
Standard Explainer API Blueprint
Provides endpoints for generating and refreshing standard explanations.
"""

from flask import Blueprint, jsonify, request
from src.services.standard_explainer_service import StandardExplainerService
from src.ai.client import AIClient
from src.core.standards_store import StandardsStore

standard_explainer_bp = Blueprint(
    "standard_explainer",
    __name__,
    url_prefix="/api/standards"
)

# Global dependencies (injected via init function)
_explainer_service: StandardExplainerService = None


def init_standard_explainer_bp(ai_client: AIClient, standards_store: StandardsStore):
    """
    Initialize the standard explainer blueprint with dependencies.

    Args:
        ai_client: AI client for generating explanations
        standards_store: Standards store for retrieving standards
    """
    global _explainer_service
    _explainer_service = StandardExplainerService(ai_client, standards_store)


@standard_explainer_bp.route("/<standard_id>/explain", methods=["GET"])
def get_explanation(standard_id: str):
    """
    Get or generate plain-English explanation for a standard.

    Args:
        standard_id: ID of the standard to explain

    Returns:
        JSON with explanation fields:
        - plain_english: Simple explanation
        - required_evidence: List of evidence types needed
        - common_mistakes: List of common errors
        - regulatory_context: Why this standard matters
        - confidence: AI confidence score
    """
    if not _explainer_service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        explanation = _explainer_service.explain_standard(standard_id)
        return jsonify(explanation), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to generate explanation: {str(e)}"}), 500


@standard_explainer_bp.route("/<standard_id>/explain/refresh", methods=["POST"])
def refresh_explanation(standard_id: str):
    """
    Invalidate cache and regenerate explanation for a standard.

    Args:
        standard_id: ID of the standard to refresh

    Returns:
        JSON with updated explanation
    """
    if not _explainer_service:
        return jsonify({"error": "Service not initialized"}), 500

    try:
        # Invalidate cache
        _explainer_service.invalidate_cache(standard_id)

        # Generate new explanation
        explanation = _explainer_service.explain_standard(standard_id)
        return jsonify(explanation), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    except Exception as e:
        return jsonify({"error": f"Failed to refresh explanation: {str(e)}"}), 500
