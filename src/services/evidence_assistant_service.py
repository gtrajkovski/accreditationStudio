"""
Evidence Assistant Service
Context-aware evidence finding for accreditation standards with prioritization.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from src.search.search_service import SearchService, get_search_service
from src.services.standard_explainer_service import StandardExplainerService
from src.ai.client import AIClient
from src.core.models import generate_id


@dataclass
class EvidenceResult:
    """Evidence search result with relevance indicators."""

    document_id: str = ""
    doc_type: str = ""
    snippet: str = ""
    page: Optional[int] = None
    score: float = 0.0
    is_required_type: bool = False
    relevance_label: str = "Related"  # "Required", "Relevant", "Related"
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_id": self.document_id,
            "doc_type": self.doc_type,
            "snippet": self.snippet,
            "page": self.page,
            "score": self.score,
            "is_required_type": self.is_required_type,
            "relevance_label": self.relevance_label,
            "confidence": self.confidence
        }


class EvidenceAssistantService:
    """Service for context-aware evidence finding with standard prioritization."""

    def __init__(
        self,
        search_service: SearchService,
        explainer_service: StandardExplainerService,
        ai_client: AIClient
    ):
        """
        Initialize evidence assistant service.

        Args:
            search_service: Search service for semantic search
            explainer_service: Standard explainer service for evidence types
            ai_client: AI client for generating suggestions
        """
        self._search_service = search_service
        self._explainer_service = explainer_service
        self._ai_client = ai_client

    def find_evidence_for_standard(
        self,
        institution_id: str,
        standard_id: str,
        query: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceResult]:
        """
        Find evidence to satisfy a specific standard with context-aware weighting.

        Args:
            institution_id: Institution ID for search scope
            standard_id: Standard to find evidence for
            query: Optional custom search query (uses standard body if not provided)
            context: Optional context dict with conversation history, active page, etc.

        Returns:
            List of EvidenceResult objects, sorted by weighted score (top 10)

        Raises:
            ValueError: If standard not found
        """
        # Get standard explanation to identify required evidence types
        explanation = self._explainer_service.explain_standard(standard_id)
        required_evidence = explanation.get("required_evidence", [])

        # Build search query
        if query is None:
            # Use first 500 characters of plain English explanation as query
            plain_english = explanation.get("plain_english", "")
            query = plain_english[:500] if plain_english else standard_id

        # Get search service for this institution
        search_svc = get_search_service(institution_id)

        # Execute search
        raw_results = search_svc.search(query, n_results=20)

        # Apply weighting and build evidence results
        evidence_results = []

        for result in raw_results:
            # Extract metadata
            metadata = result.chunk.metadata
            doc_type = metadata.get("doc_type", "")
            doc_id = result.chunk.document_id
            snippet = result.chunk.text_original[:300] + "..." if len(result.chunk.text_original) > 300 else result.chunk.text_original
            page = result.chunk.page_number

            # Check if document type matches required evidence
            is_required = self._is_required_evidence_type(doc_type, required_evidence)

            # Apply weighting: boost score by 1.5x for required types
            weighted_score = result.score * 1.5 if is_required else result.score

            # Determine relevance label
            if is_required:
                relevance_label = "Required"
            elif result.score > 0.7:
                relevance_label = "Relevant"
            else:
                relevance_label = "Related"

            evidence_results.append(
                EvidenceResult(
                    document_id=doc_id,
                    doc_type=doc_type,
                    snippet=snippet,
                    page=page,
                    score=weighted_score,
                    is_required_type=is_required,
                    relevance_label=relevance_label,
                    confidence=result.score  # Confidence is the original score (0-1)
                )
            )

        # Sort by weighted score descending and take top 10
        evidence_results.sort(key=lambda x: x.score, reverse=True)
        return evidence_results[:10]

    def generate_suggested_prompts(
        self,
        conversation_history: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[str]:
        """
        Generate context-aware follow-up prompts based on conversation history.

        Args:
            conversation_history: List of conversation messages
            context: Context dict with current_page, active_standard_id, recent_findings

        Returns:
            List of 3-5 suggested prompt strings

        Raises:
            None (returns empty list on error)
        """
        # Build context string
        context_parts = []

        if context.get("current_page"):
            context_parts.append(f"User is on page: {context['current_page']}")

        if context.get("active_standard_id"):
            context_parts.append(f"Active standard: {context['active_standard_id']}")

        if context.get("recent_findings"):
            findings = context["recent_findings"][:3]  # Limit to 3
            context_parts.append(f"Recent findings: {', '.join(findings)}")

        context_str = "\n".join(context_parts) if context_parts else "No specific context available"

        # Build conversation summary
        if conversation_history:
            last_messages = conversation_history[-3:]  # Last 3 messages
            convo_summary = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')[:200]}"
                for msg in last_messages
            ])
        else:
            convo_summary = "No conversation history"

        # System prompt for suggestion generation
        system_prompt = """You are an expert assistant helping users navigate accreditation evidence.
Generate 3-5 specific follow-up questions the user might want to ask next.

Guidelines:
- Questions should be specific and actionable
- Relate to the current context and conversation
- Focus on evidence gathering, compliance checking, or documentation gaps
- Keep questions concise (under 80 characters each)

Respond with ONLY a JSON array of strings, like:
["Question 1?", "Question 2?", "Question 3?"]
"""

        user_prompt = f"""Context:
{context_str}

Recent conversation:
{convo_summary}

Generate 3-5 relevant follow-up questions the user might ask."""

        try:
            # Generate suggestions
            response = self._ai_client.generate(
                system=system_prompt,
                user=user_prompt,
                temperature=0.7
            )

            # Parse JSON response
            suggestions = json.loads(response)

            # Validate it's a list of strings
            if isinstance(suggestions, list) and all(isinstance(s, str) for s in suggestions):
                return suggestions[:5]  # Cap at 5
            else:
                return []

        except (json.JSONDecodeError, ValueError, Exception) as e:
            # Graceful failure: return empty list
            print(f"Error generating suggestions: {e}")
            return []

    def _is_required_evidence_type(self, doc_type: str, required_evidence: List[str]) -> bool:
        """
        Check if document type matches any required evidence types.

        Args:
            doc_type: Document type from metadata
            required_evidence: List of required evidence type strings

        Returns:
            True if doc_type matches any required evidence
        """
        if not doc_type or not required_evidence:
            return False

        doc_type_lower = doc_type.lower()

        # Check for partial matches (e.g., "policy" in "Student Policy Manual")
        for required in required_evidence:
            required_lower = required.lower()
            if required_lower in doc_type_lower or doc_type_lower in required_lower:
                return True

        return False


# Convenience functions
def find_evidence_for_standard(
    institution_id: str,
    standard_id: str,
    query: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    ai_client: Optional[AIClient] = None,
    explainer_service: Optional[StandardExplainerService] = None
) -> List[EvidenceResult]:
    """
    Convenience function to find evidence for a standard.

    Args:
        institution_id: Institution ID
        standard_id: Standard ID
        query: Optional custom query
        context: Optional context dict
        ai_client: Optional AI client (required if not using default)
        explainer_service: Optional explainer service (required if not using default)

    Returns:
        List of EvidenceResult objects
    """
    if ai_client is None or explainer_service is None:
        raise ValueError("ai_client and explainer_service are required")

    search_service = get_search_service(institution_id)
    service = EvidenceAssistantService(search_service, explainer_service, ai_client)

    return service.find_evidence_for_standard(institution_id, standard_id, query, context)
