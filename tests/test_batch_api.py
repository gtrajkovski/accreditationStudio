"""Tests for Anthropic Batch API integration.

Tests batch submission, polling, and result processing with mocked Anthropic API.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass


@dataclass
class MockRequestCounts:
    processing: int = 0
    succeeded: int = 0
    errored: int = 0
    canceled: int = 0
    expired: int = 0


@dataclass
class MockBatch:
    id: str = "msgbatch_test123"
    processing_status: str = "in_progress"
    request_counts: MockRequestCounts = None
    created_at: str = "2024-01-01T00:00:00Z"
    expires_at: str = "2024-01-02T00:00:00Z"
    ended_at: str = None
    results_url: str = None

    def __post_init__(self):
        if self.request_counts is None:
            self.request_counts = MockRequestCounts(processing=2)


@dataclass
class MockUsage:
    input_tokens: int = 1000
    output_tokens: int = 500


@dataclass
class MockMessage:
    usage: MockUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = MockUsage()


@dataclass
class MockSucceededResult:
    type: str = "succeeded"
    message: MockMessage = None

    def __post_init__(self):
        if self.message is None:
            self.message = MockMessage()


@dataclass
class MockErroredResult:
    type: str = "errored"
    error: str = "Test error"


@dataclass
class MockBatchResult:
    custom_id: str
    result: object


class TestBatchPricing:
    """Test batch pricing is 50% of standard rates."""

    def test_batch_pricing_is_50_percent_discount(self):
        from src.services.batch_service import MODEL_PRICING, BATCH_PRICING

        for model, standard in MODEL_PRICING.items():
            if model in BATCH_PRICING:
                batch = BATCH_PRICING[model]
                assert batch["input"] == standard["input"] / 2, f"{model} input not 50%"
                assert batch["output"] == standard["output"] / 2, f"{model} output not 50%"

    def test_estimate_batch_cost_async_mode(self):
        from src.services.batch_service import estimate_batch_cost

        docs = [
            {"id": "doc1", "name": "Test Doc", "doc_type": "policy"}
        ]

        realtime_est = estimate_batch_cost("audit", docs, batch_mode="realtime")
        async_est = estimate_batch_cost("audit", docs, batch_mode="async")

        # Async should be ~50% of realtime
        assert async_est["total_cost"] < realtime_est["total_cost"]
        assert async_est["total_cost"] == pytest.approx(realtime_est["total_cost"] / 2, rel=0.01)


class TestAIClientBatchMethods:
    """Test AIClient batch API methods with mocked Anthropic client."""

    @patch("src.ai.client.anthropic.Anthropic")
    def test_submit_batch(self, mock_anthropic):
        """Test submit_batch creates batch and returns info."""
        from src.ai.client import AIClient

        # Setup mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.batches.create.return_value = MockBatch()

        client = AIClient()
        requests = [
            {
                "custom_id": "req-1",
                "params": {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Test"}]
                }
            }
        ]

        result = client.submit_batch(requests)

        assert result["batch_id"] == "msgbatch_test123"
        assert result["processing_status"] == "in_progress"
        assert "expires_at" in result
        mock_client.messages.batches.create.assert_called_once()

    @patch("src.ai.client.anthropic.Anthropic")
    def test_get_batch_status(self, mock_anthropic):
        """Test get_batch_status retrieves status."""
        from src.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.batches.retrieve.return_value = MockBatch(
            processing_status="ended",
            ended_at="2024-01-01T01:00:00Z",
            results_url="https://example.com/results"
        )

        client = AIClient()
        result = client.get_batch_status("msgbatch_test123")

        assert result["processing_status"] == "ended"
        assert result["ended_at"] == "2024-01-01T01:00:00Z"
        assert result["results_url"] == "https://example.com/results"

    @patch("src.ai.client.anthropic.Anthropic")
    def test_get_batch_results(self, mock_anthropic):
        """Test get_batch_results streams results."""
        from src.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock results iterator
        mock_results = [
            MockBatchResult(custom_id="req-1", result=MockSucceededResult()),
            MockBatchResult(custom_id="req-2", result=MockErroredResult()),
        ]
        mock_client.messages.batches.results.return_value = iter(mock_results)

        client = AIClient()
        results = list(client.get_batch_results("msgbatch_test123"))

        assert len(results) == 2
        assert results[0]["custom_id"] == "req-1"
        assert results[0]["result_type"] == "succeeded"
        assert results[1]["custom_id"] == "req-2"
        assert results[1]["result_type"] == "errored"


class TestBatchServiceIntegration:
    """Test BatchService Anthropic integration with mocked dependencies."""

    def test_batch_mode_column_exists(self):
        """Verify batch_mode column exists in database."""
        from src.db.connection import get_conn

        conn = get_conn()
        cursor = conn.execute("PRAGMA table_info(batch_operations)")
        columns = [row[1] for row in cursor.fetchall()]

        assert "anthropic_batch_id" in columns
        assert "batch_mode" in columns
        assert "anthropic_status" in columns
