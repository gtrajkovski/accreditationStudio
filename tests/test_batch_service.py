"""Tests for BatchService cost estimation and orchestration."""

import pytest
from unittest.mock import MagicMock
from src.services.batch_service import estimate_batch_cost, BatchService
from src.core.models import BatchOperation, BatchItem


class TestCostEstimation:
    """Test cost estimation for batch operations."""

    def test_estimate_audit_cost_catalog(self):
        """Should estimate audit cost for catalog documents."""
        documents = [
            {"id": "doc1", "doc_type": "catalog", "name": "Catalog 2024.pdf"}
        ]
        result = estimate_batch_cost("audit", documents, model="claude-sonnet-4-20250514")

        assert "total_cost" in result
        assert "per_document" in result
        assert "breakdown" in result
        assert result["total_cost"] > 0
        assert len(result["per_document"]) == 1
        # Catalog audits are expensive (12k input, 3k output)
        # $3/1M input + $15/1M output = ~$0.08 per doc with safety margin
        assert 0.05 < result["total_cost"] < 0.15

    def test_estimate_audit_cost_policy_manual(self):
        """Should estimate audit cost for policy manuals."""
        documents = [
            {"id": "doc1", "doc_type": "policy_manual", "name": "Policy Manual.pdf"}
        ]
        result = estimate_batch_cost("audit", documents)

        assert result["total_cost"] > 0
        # Policy manual: 8k input, 2.5k output
        assert 0.03 < result["total_cost"] < 0.10

    def test_estimate_remediation_cost(self):
        """Should estimate remediation cost (lower than audit)."""
        documents = [
            {"id": "doc1", "doc_type": "catalog", "name": "Catalog.pdf"}
        ]
        audit_cost = estimate_batch_cost("audit", documents)["total_cost"]
        remediation_cost = estimate_batch_cost("remediation", documents)["total_cost"]

        # Remediation should be cheaper than audit
        assert remediation_cost < audit_cost

    def test_estimate_multiple_documents(self):
        """Should calculate total cost for multiple documents."""
        documents = [
            {"id": "doc1", "doc_type": "catalog", "name": "Catalog.pdf"},
            {"id": "doc2", "doc_type": "student_handbook", "name": "Handbook.pdf"},
            {"id": "doc3", "doc_type": "other", "name": "Other.pdf"},
        ]
        result = estimate_batch_cost("audit", documents)

        assert len(result["per_document"]) == 3
        # Total should be sum of individual estimates
        per_doc_total = sum(d["total_cost"] for d in result["per_document"])
        assert abs(result["total_cost"] - per_doc_total) < 0.01

    def test_estimate_opus_model_more_expensive(self):
        """Should estimate higher cost for Opus model."""
        documents = [{"id": "doc1", "doc_type": "catalog", "name": "Catalog.pdf"}]

        sonnet_cost = estimate_batch_cost("audit", documents, model="claude-sonnet-4-20250514")["total_cost"]
        opus_cost = estimate_batch_cost("audit", documents, model="claude-opus-4-5-20251101")["total_cost"]

        # Opus is 5x more expensive
        assert opus_cost > sonnet_cost * 3


class TestBatchService:
    """Test BatchService CRUD and orchestration."""

    @pytest.fixture
    def workspace_manager(self):
        """Mock workspace manager with proper institution structure."""
        from src.core.models import Institution, Document, generate_id

        # Create mock documents
        doc1 = MagicMock()
        doc1.id = "doc1"
        doc1.name = "Catalog.pdf"
        doc1.doc_type = "catalog"

        doc2 = MagicMock()
        doc2.id = "doc2"
        doc2.name = "Handbook.pdf"
        doc2.doc_type = "student_handbook"

        doc3 = MagicMock()
        doc3.id = "doc3"
        doc3.name = "Policy.pdf"
        doc3.doc_type = "policy_manual"

        doc4 = MagicMock()
        doc4.id = "doc4"
        doc4.name = "Other.pdf"
        doc4.doc_type = "other"

        # Create mock institutions
        institution1 = MagicMock()
        institution1.id = "inst_277a77bc5d8d"  # Use existing institution from database
        institution1.name = "Test University"
        institution1.documents = [doc1, doc2, doc3, doc4]

        institution2 = MagicMock()
        institution2.id = "inst_798fb35f75d0"
        institution2.name = "Another University"
        institution2.documents = [doc3]

        # Mock workspace manager that returns appropriate institution
        def load_institution(inst_id):
            if inst_id == "inst_277a77bc5d8d":
                return institution1
            elif inst_id == "inst_798fb35f75d0":
                return institution2
            return None

        mock = MagicMock()
        mock.load_institution.side_effect = load_institution
        return mock

    @pytest.fixture
    def batch_service(self, workspace_manager):
        """Create BatchService instance."""
        return BatchService(workspace_manager)

    def test_create_batch_persists_to_database(self, batch_service):
        """Should create batch operation and persist to database."""
        batch = batch_service.create_batch(
            institution_id="inst_277a77bc5d8d",
            operation_type="audit",
            document_ids=["doc1", "doc2", "doc3"],
            concurrency=3
        )

        assert batch.id.startswith("batch_")
        assert batch.institution_id == "inst_277a77bc5d8d"
        assert batch.operation_type == "audit"
        assert batch.document_count == 3
        assert batch.status == "pending"
        assert len(batch.items) == 3

    def test_get_batch_loads_from_database(self, batch_service):
        """Should retrieve batch with items from database."""
        # Create batch first
        created = batch_service.create_batch(
            institution_id="inst_277a77bc5d8d",
            operation_type="remediation",
            document_ids=["doc1", "doc2"]
        )

        # Retrieve it
        retrieved = batch_service.get_batch(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert len(retrieved.items) == 2

    def test_get_progress_returns_metrics(self, batch_service):
        """Should calculate batch progress from item statuses."""
        batch = batch_service.create_batch(
            institution_id="inst_277a77bc5d8d",
            operation_type="audit",
            document_ids=["doc1", "doc2", "doc3", "doc4"]
        )

        # Simulate some items completing
        batch_service.update_item_status(batch.items[0].id, "completed")
        batch_service.update_item_status(batch.items[1].id, "completed")
        batch_service.update_item_status(batch.items[2].id, "failed")

        progress = batch_service.get_progress(batch.id)

        assert progress["total"] == 4
        assert progress["completed"] == 2
        assert progress["failed"] == 1
        assert progress["progress_pct"] == 75.0  # 3 out of 4 done (completed + failed)

    def test_update_item_status_updates_batch_counts(self, batch_service):
        """Should update batch completed/failed counts when item status changes."""
        batch = batch_service.create_batch(
            institution_id="inst_277a77bc5d8d",
            operation_type="audit",
            document_ids=["doc1", "doc2"]
        )

        # Complete one item
        batch_service.update_item_status(batch.items[0].id, "completed", input_tokens=1000, output_tokens=500)

        # Reload batch
        updated_batch = batch_service.get_batch(batch.id)
        assert updated_batch.completed_count == 1
        assert updated_batch.failed_count == 0

    def test_cancel_batch_cancels_pending_items(self, batch_service):
        """Should cancel pending items when batch is cancelled."""
        batch = batch_service.create_batch(
            institution_id="inst_277a77bc5d8d",
            operation_type="audit",
            document_ids=["doc1", "doc2", "doc3"]
        )

        # Start one item
        batch_service.update_item_status(batch.items[0].id, "running")

        # Cancel batch
        batch_service.cancel_batch(batch.id)

        cancelled_batch = batch_service.get_batch(batch.id)
        assert cancelled_batch.status == "cancelled"

    def test_list_batches_returns_history(self, batch_service):
        """Should list batches for an institution."""
        # Get initial count
        initial_batches = batch_service.list_batches("inst_277a77bc5d8d")
        initial_count = len(initial_batches)

        # Create multiple batches
        batch_service.create_batch("inst_277a77bc5d8d", "audit", ["doc1"])
        batch_service.create_batch("inst_277a77bc5d8d", "remediation", ["doc2"])
        batch_service.create_batch("inst_798fb35f75d0", "audit", ["doc3"])

        # List batches for inst_277a77bc5d8d
        batches = batch_service.list_batches("inst_277a77bc5d8d")

        # Should have 2 more batches than before
        assert len(batches) == initial_count + 2
        assert all(b.institution_id == "inst_277a77bc5d8d" for b in batches)
