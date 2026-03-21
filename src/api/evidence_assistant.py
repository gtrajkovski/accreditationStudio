"""Evidence Assistant API Blueprint."""

from flask import Blueprint, request, jsonify
from typing import Optional

from src.services.evidence_assistant_service import EvidenceAssistantService
from src.services.standard_explainer_service import StandardExplainerService
from src.search.search_service import get_search_service
from src.ai.client import AIClient
from src.core.standards_store import StandardsStore

evidence_assistant_bp = Blueprint(
    "evidence_assistant",
    __name__,
    url_prefix="/api/evidence"
)

# Global dependencies (injected via init function)
_ai_client: Optional[AIClient] = None
_standards_store: Optional[StandardsStore] = None


def init_evidence_assistant_bp(ai_client: AIClient, standards_store: StandardsStore):
    """
    Initialize evidence assistant blueprint with dependencies.

    Args:
        ai_client: AI client for generating suggestions
        standards_store: Standards store for standard lookups
    """
    global _ai_client, _standards_store
    _ai_client = ai_client
    _standards_store = standards_store


@evidence_assistant_bp.route("/search", methods=["POST"])
def search_evidence():
    """
    Search for evidence to satisfy a specific standard.

    Request body:
        {
            "standard_id": "std_001",
            "institution_id": "inst_001",
            "query": "optional custom query",
            "context": {}
        }

    Returns:
        {
            "results": [EvidenceResult.to_dict()],
            "standard": {"id": "std_001", "title": "Standard Title"},
            "query": "search query used"
        }
    """
    try:
        data = request.get_json()

        # Validate required fields
        standard_id = data.get("standard_id")
        institution_id = data.get("institution_id")

        if not standard_id:
            return jsonify({"error": "standard_id is required"}), 400

        if not institution_id:
            return jsonify({"error": "institution_id is required"}), 400

        # Get optional fields
        query = data.get("query")
        context = data.get("context", {})

        # Get standard info
        standard = _standards_store.get_standard(standard_id)
        if not standard:
            return jsonify({"error": f"Standard not found: {standard_id}"}), 404

        # Create services
        search_service = get_search_service(institution_id)
        explainer_service = StandardExplainerService(_ai_client, _standards_store)
        evidence_service = EvidenceAssistantService(
            search_service=search_service,
            explainer_service=explainer_service,
            ai_client=_ai_client
        )

        # Find evidence
        results = evidence_service.find_evidence_for_standard(
            institution_id=institution_id,
            standard_id=standard_id,
            query=query,
            context=context
        )

        # Build response
        return jsonify({
            "results": [r.to_dict() for r in results],
            "standard": {
                "id": standard.id,
                "title": standard.title,
                "code": standard.code
            },
            "query": query if query else "Auto-generated from standard"
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@evidence_assistant_bp.route("/suggestions", methods=["POST"])
def get_suggestions():
    """
    Generate suggested follow-up prompts based on conversation context.

    Request body:
        {
            "conversation_history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ],
            "context": {
                "current_page": "compliance",
                "active_standard_id": "std_001",
                "recent_findings": ["finding1", "finding2"]
            }
        }

    Returns:
        {
            "suggestions": ["Question 1?", "Question 2?", ...]
        }
    """
    try:
        data = request.get_json()

        # Get fields (both optional)
        conversation_history = data.get("conversation_history", [])
        context = data.get("context", {})

        # Need at least institution_id for search service
        institution_id = context.get("institution_id", "default")

        # Create services
        search_service = get_search_service(institution_id)
        explainer_service = StandardExplainerService(_ai_client, _standards_store)
        evidence_service = EvidenceAssistantService(
            search_service=search_service,
            explainer_service=explainer_service,
            ai_client=_ai_client
        )

        # Generate suggestions
        suggestions = evidence_service.generate_suggested_prompts(
            conversation_history=conversation_history,
            context=context
        )

        return jsonify({"suggestions": suggestions})

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
