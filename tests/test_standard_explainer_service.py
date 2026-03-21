"""
Tests for Standard Explainer Service
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from src.services.standard_explainer_service import (
    StandardExplainerService,
    StandardExplanation,
    explain_standard,
    get_cached_explanation
)
from src.db.connection import get_conn


@dataclass
class MockStandard:
    """Mock standard for testing."""
    id: str
    code: str
    title: str
    body: str
    accrediting_body: str


@pytest.fixture
def mock_ai_client():
    """Mock AI client."""
    client = MagicMock()
    # Return valid JSON response
    client.generate.return_value = json.dumps({
        "plain_english": "This standard requires institutions to maintain accurate student records.",
        "required_evidence": [
            "Student record retention policy",
            "Database backup procedures",
            "Access control documentation"
        ],
        "common_mistakes": [
            "Not documenting retention periods",
            "Inadequate backup procedures"
        ],
        "regulatory_context": "Accurate records are essential for student verification and regulatory compliance."
    })
    return client


@pytest.fixture
def mock_standards_store():
    """Mock standards store."""
    store = MagicMock()
    store.get_standard.return_value = MockStandard(
        id="std-001",
        code="1.A.1",
        title="Student Records",
        body="Institutions must maintain accurate and secure student records for a minimum of 5 years.",
        accrediting_body="ACCSC"
    )
    return store


@pytest.fixture
def service(mock_ai_client, mock_standards_store):
    """Create service instance."""
    return StandardExplainerService(mock_ai_client, mock_standards_store)


@pytest.fixture(autouse=True)
def clean_db():
    """Clean test data before each test."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM standard_explanations")
    conn.commit()
    yield
    cursor.execute("DELETE FROM standard_explanations")
    conn.commit()


def test_explain_standard_generates_explanation(service, mock_ai_client):
    """Test that explain_standard generates explanation with required fields."""
    result = service.explain_standard("std-001")

    # Verify required fields
    assert "plain_english" in result
    assert "required_evidence" in result
    assert "common_mistakes" in result
    assert "regulatory_context" in result
    assert "confidence" in result

    # Verify content
    assert result["plain_english"] == "This standard requires institutions to maintain accurate student records."
    assert len(result["required_evidence"]) == 3
    assert "Student record retention policy" in result["required_evidence"]
    assert len(result["common_mistakes"]) == 2

    # Verify AI was called
    mock_ai_client.generate.assert_called_once()


def test_explain_standard_caches_result(service, mock_ai_client):
    """Test that second call uses cache and doesn't invoke AI."""
    # First call
    result1 = service.explain_standard("std-001")

    # Second call
    result2 = service.explain_standard("std-001")

    # AI should only be called once
    assert mock_ai_client.generate.call_count == 1

    # Results should match
    assert result1["plain_english"] == result2["plain_english"]
    assert result1["required_evidence"] == result2["required_evidence"]


def test_invalidate_cache_forces_regeneration(service, mock_ai_client):
    """Test that cache invalidation causes AI to be called again."""
    # First call
    service.explain_standard("std-001")
    assert mock_ai_client.generate.call_count == 1

    # Invalidate cache
    service.invalidate_cache("std-001")

    # Second call should invoke AI again
    service.explain_standard("std-001")
    assert mock_ai_client.generate.call_count == 2


def test_get_cached_explanation_returns_none_when_empty(service):
    """Test that get_cached_explanation returns None when no cache exists."""
    result = service.get_cached_explanation("std-999")
    assert result is None


def test_get_cached_explanation_returns_data_when_cached(service):
    """Test that get_cached_explanation returns cached data."""
    # Generate explanation to populate cache
    service.explain_standard("std-001")

    # Retrieve from cache
    cached = service.get_cached_explanation("std-001")

    assert cached is not None
    assert cached["standard_id"] == "std-001"
    assert cached["plain_english"] == "This standard requires institutions to maintain accurate student records."


def test_explain_standard_raises_on_missing_standard(service, mock_standards_store):
    """Test that explain_standard raises ValueError for missing standard."""
    mock_standards_store.get_standard.return_value = None

    with pytest.raises(ValueError, match="Standard not found"):
        service.explain_standard("std-999")


def test_explain_standard_handles_json_in_markdown(service, mock_ai_client, mock_standards_store):
    """Test that service extracts JSON from markdown code blocks."""
    # AI returns JSON wrapped in markdown
    mock_ai_client.generate.return_value = """```json
{
  "plain_english": "Test explanation",
  "required_evidence": ["Evidence 1"],
  "common_mistakes": ["Mistake 1"],
  "regulatory_context": "Context"
}
```"""

    result = service.explain_standard("std-001")

    assert result["plain_english"] == "Test explanation"
    assert result["required_evidence"] == ["Evidence 1"]


def test_standard_explanation_to_dict():
    """Test StandardExplanation to_dict conversion."""
    explanation = StandardExplanation(
        id="expl-001",
        standard_id="std-001",
        accreditor="ACCSC",
        plain_english="Test",
        required_evidence=["Evidence 1", "Evidence 2"],
        common_mistakes=["Mistake 1"],
        regulatory_context="Context",
        confidence=0.9,
        version="abc123"
    )

    result = explanation.to_dict()

    assert result["id"] == "expl-001"
    assert result["standard_id"] == "std-001"
    assert result["accreditor"] == "ACCSC"
    assert result["confidence"] == 0.9
    assert len(result["required_evidence"]) == 2


def test_standard_explanation_from_dict():
    """Test StandardExplanation from_dict conversion with unknown field filtering."""
    data = {
        "id": "expl-001",
        "standard_id": "std-001",
        "accreditor": "ACCSC",
        "plain_english": "Test",
        "required_evidence": ["Evidence 1"],
        "common_mistakes": ["Mistake 1"],
        "regulatory_context": "Context",
        "confidence": 0.85,
        "version": "abc123",
        "unknown_field": "should be filtered"
    }

    explanation = StandardExplanation.from_dict(data)

    assert explanation.id == "expl-001"
    assert explanation.standard_id == "std-001"
    assert not hasattr(explanation, "unknown_field")


def test_convenience_function_explain_standard(mock_ai_client, mock_standards_store):
    """Test convenience function explain_standard."""
    result = explain_standard("std-001", mock_ai_client, mock_standards_store)

    assert "plain_english" in result
    assert "required_evidence" in result
    mock_ai_client.generate.assert_called_once()


def test_convenience_function_get_cached_explanation(service):
    """Test convenience function get_cached_explanation."""
    # Generate to populate cache
    service.explain_standard("std-001")

    # Use convenience function
    cached = get_cached_explanation("std-001")

    assert cached is not None
    assert cached["standard_id"] == "std-001"
