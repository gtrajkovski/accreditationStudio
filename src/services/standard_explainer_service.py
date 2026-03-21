"""
Standard Explainer Service
Generates plain-English explanations of accreditation standards with evidence checklists.
"""

import json
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from src.db.connection import get_conn
from src.core.models import generate_id, now_iso
from src.ai.client import AIClient
from src.core.standards_store import StandardsStore


@dataclass
class StandardExplanation:
    """Plain-English explanation of a standard with evidence requirements."""

    id: str = field(default_factory=lambda: generate_id("expl"))
    standard_id: str = ""
    accreditor: str = ""
    plain_english: str = ""
    required_evidence: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    regulatory_context: str = ""
    confidence: float = 0.85
    version: str = ""  # Hash of standard body
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "standard_id": self.standard_id,
            "accreditor": self.accreditor,
            "plain_english": self.plain_english,
            "required_evidence": self.required_evidence,
            "common_mistakes": self.common_mistakes,
            "regulatory_context": self.regulatory_context,
            "confidence": self.confidence,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardExplanation":
        """Create from dictionary, filtering unknown fields."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class StandardExplainerService:
    """Service for generating and caching standard explanations."""

    def __init__(self, ai_client: AIClient, standards_store: StandardsStore):
        self._ai_client = ai_client
        self._standards_store = standards_store

    def explain_standard(self, standard_id: str) -> Dict[str, Any]:
        """
        Generate or retrieve cached plain-English explanation of a standard.

        Args:
            standard_id: ID of the standard to explain

        Returns:
            Dictionary with explanation fields (plain_english, required_evidence, etc.)

        Raises:
            ValueError: If standard not found
        """
        # Get the standard
        standard = self._standards_store.get_standard(standard_id)
        if not standard:
            raise ValueError(f"Standard not found: {standard_id}")

        # Calculate version hash
        version = self._compute_version(standard.body)

        # Check cache first
        cached = self._get_cached(standard_id, version)
        if cached:
            return cached.to_dict()

        # Generate new explanation
        explanation = self._generate_explanation(standard)

        # Store in cache
        self._store_explanation(explanation)

        return explanation.to_dict()

    def get_cached_explanation(self, standard_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached explanation without regenerating if missing.

        Args:
            standard_id: ID of the standard

        Returns:
            Cached explanation dict or None
        """
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, standard_id, accreditor, plain_english, required_evidence,
                   common_mistakes, regulatory_context, confidence, version,
                   created_at, updated_at
            FROM standard_explanations
            WHERE standard_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (standard_id,)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "standard_id": row["standard_id"],
            "accreditor": row["accreditor"],
            "plain_english": row["plain_english"],
            "required_evidence": json.loads(row["required_evidence"]),
            "common_mistakes": json.loads(row["common_mistakes"]) if row["common_mistakes"] else [],
            "regulatory_context": row["regulatory_context"],
            "confidence": row["confidence"],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def invalidate_cache(self, standard_id: str) -> None:
        """
        Invalidate cached explanation for a standard.

        Args:
            standard_id: ID of the standard
        """
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM standard_explanations WHERE standard_id = ?",
            (standard_id,)
        )

        conn.commit()

    def _compute_version(self, standard_body: str) -> str:
        """Compute version hash from standard body."""
        return hashlib.sha256(standard_body.encode('utf-8')).hexdigest()[:16]

    def _get_cached(self, standard_id: str, version: str) -> Optional[StandardExplanation]:
        """Get cached explanation if version matches."""
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, standard_id, accreditor, plain_english, required_evidence,
                   common_mistakes, regulatory_context, confidence, version,
                   created_at, updated_at
            FROM standard_explanations
            WHERE standard_id = ? AND version = ?
            """,
            (standard_id, version)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return StandardExplanation(
            id=row["id"],
            standard_id=row["standard_id"],
            accreditor=row["accreditor"],
            plain_english=row["plain_english"],
            required_evidence=json.loads(row["required_evidence"]),
            common_mistakes=json.loads(row["common_mistakes"]) if row["common_mistakes"] else [],
            regulatory_context=row["regulatory_context"],
            confidence=row["confidence"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _generate_explanation(self, standard) -> StandardExplanation:
        """Generate new explanation using AI."""
        system_prompt = """You are an expert in accreditation standards interpretation.
Your task is to translate dense regulatory standards into plain English and identify required evidence.

Respond with valid JSON only, using this exact structure:
{
  "plain_english": "Clear, jargon-free explanation of what this standard requires",
  "required_evidence": ["Evidence type 1", "Evidence type 2", "Evidence type 3"],
  "common_mistakes": ["Common mistake 1", "Common mistake 2"],
  "regulatory_context": "Brief explanation of why this standard exists and its importance"
}

Guidelines:
- plain_english: Use simple language, avoid regulatory jargon, explain in 2-4 sentences
- required_evidence: List 3-5 specific document/data types needed to demonstrate compliance
- common_mistakes: List 2-4 common errors institutions make with this standard
- regulatory_context: Explain the "why" in 1-2 sentences
"""

        user_prompt = f"""Standard: {standard.code}
Title: {standard.title}
Accreditor: {standard.accrediting_body.value if hasattr(standard.accrediting_body, 'value') else standard.accrediting_body}

Full Text:
{standard.body}

Provide a plain-English explanation with evidence requirements."""

        # Generate explanation
        response = self._ai_client.generate(
            system=system_prompt,
            user=user_prompt,
            temperature=0.3
        )

        # Parse JSON response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON from markdown code blocks
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
                data = json.loads(response)
            else:
                raise ValueError(f"AI response is not valid JSON: {response[:200]}")

        # Create explanation object
        version = self._compute_version(standard.body)

        return StandardExplanation(
            standard_id=standard.id,
            accreditor=standard.accrediting_body.value if hasattr(standard.accrediting_body, 'value') else str(standard.accrediting_body),
            plain_english=data.get("plain_english", ""),
            required_evidence=data.get("required_evidence", []),
            common_mistakes=data.get("common_mistakes", []),
            regulatory_context=data.get("regulatory_context", ""),
            confidence=0.85,
            version=version
        )

    def _store_explanation(self, explanation: StandardExplanation) -> None:
        """Store explanation in database."""
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO standard_explanations
            (id, standard_id, accreditor, plain_english, required_evidence,
             common_mistakes, regulatory_context, confidence, version,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                explanation.id,
                explanation.standard_id,
                explanation.accreditor,
                explanation.plain_english,
                json.dumps(explanation.required_evidence),
                json.dumps(explanation.common_mistakes),
                explanation.regulatory_context,
                explanation.confidence,
                explanation.version,
                explanation.created_at,
                explanation.updated_at
            )
        )

        conn.commit()


# Convenience functions for direct use
def explain_standard(
    standard_id: str,
    ai_client: AIClient,
    standards_store: StandardsStore
) -> Dict[str, Any]:
    """Convenience function to explain a standard."""
    service = StandardExplainerService(ai_client, standards_store)
    return service.explain_standard(standard_id)


def get_cached_explanation(standard_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get cached explanation."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, standard_id, accreditor, plain_english, required_evidence,
               common_mistakes, regulatory_context, confidence, version,
               created_at, updated_at
        FROM standard_explanations
        WHERE standard_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (standard_id,)
    )

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row["id"],
        "standard_id": row["standard_id"],
        "accreditor": row["accreditor"],
        "plain_english": row["plain_english"],
        "required_evidence": json.loads(row["required_evidence"]),
        "common_mistakes": json.loads(row["common_mistakes"]) if row["common_mistakes"] else [],
        "regulatory_context": row["regulatory_context"],
        "confidence": row["confidence"],
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }
