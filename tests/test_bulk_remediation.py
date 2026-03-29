"""Tests for bulk remediation service.

Tests cover:
- Scope preview returning correct counts
- Job creation storing items
- Job lifecycle (pause, resume, cancel)
- Approval workflow (individual and batch)
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.services.bulk_remediation_service import (
    BulkRemediationService,
    BulkRemediationScope,
    BulkRemediationJob,
    BulkRemediationItem,
    BulkJobStatus,
    ItemApprovalStatus,
)


@pytest.fixture
def mock_db():
    """Create mock database with tables."""
    with patch("src.services.bulk_remediation_service.get_conn") as mock_conn:
        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.commit = MagicMock()

        # Configure cursor.fetchone() and fetchall() defaults
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.rowcount = 0

        yield mock_cursor


@pytest.fixture
def service():
    """Create bulk remediation service."""
    return BulkRemediationService(None, None)


class TestBulkRemediationScope:
    """Tests for BulkRemediationScope dataclass."""

    def test_scope_to_dict(self):
        """Verify scope serializes to dict correctly."""
        scope = BulkRemediationScope(
            scope_type="doc_type",
            doc_types=["policy", "catalog"],
            severities=["critical"],
        )

        result = scope.to_dict()

        assert result["scope_type"] == "doc_type"
        assert result["doc_types"] == ["policy", "catalog"]
        assert result["severities"] == ["critical"]
        assert result["program_ids"] == []
        assert result["include_resolved"] is False

    def test_scope_from_dict(self):
        """Verify scope deserializes from dict correctly."""
        data = {
            "scope_type": "program",
            "program_ids": ["prog_1", "prog_2"],
        }

        scope = BulkRemediationScope.from_dict(data)

        assert scope.scope_type == "program"
        assert scope.program_ids == ["prog_1", "prog_2"]
        assert scope.doc_types == []

    def test_scope_defaults(self):
        """Verify scope has correct defaults."""
        scope = BulkRemediationScope(scope_type="all")

        assert scope.doc_types == []
        assert scope.program_ids == []
        assert scope.severities == []
        assert scope.include_resolved is False


class TestBulkRemediationJob:
    """Tests for BulkRemediationJob dataclass."""

    def test_job_to_dict(self):
        """Verify job serializes to dict correctly."""
        job = BulkRemediationJob(
            id="bulk_test123",
            institution_id="inst_abc",
            scope_type="all",
            scope_value='{"scope_type": "all"}',
            total_documents=10,
            processed_documents=5,
        )

        result = job.to_dict()

        assert result["id"] == "bulk_test123"
        assert result["institution_id"] == "inst_abc"
        assert result["total_documents"] == 10
        assert result["processed_documents"] == 5
        assert result["progress_percent"] == 50.0
        assert result["scope"]["scope_type"] == "all"

    def test_job_progress_percent_zero_total(self):
        """Verify progress calculation handles zero total."""
        job = BulkRemediationJob(
            total_documents=0,
            processed_documents=0,
        )

        result = job.to_dict()

        assert result["progress_percent"] == 0.0


class TestBulkRemediationItem:
    """Tests for BulkRemediationItem dataclass."""

    def test_item_to_dict(self):
        """Verify item serializes to dict correctly."""
        item = BulkRemediationItem(
            id="britem_test",
            job_id="bulk_job",
            document_id="doc_123",
            document_name="test.pdf",
            finding_count=5,
            status="complete",
            confidence=0.85,
        )

        result = item.to_dict()

        assert result["id"] == "britem_test"
        assert result["document_id"] == "doc_123"
        assert result["finding_count"] == 5
        assert result["confidence"] == 0.85


class TestPreviewScope:
    """Tests for scope preview functionality."""

    def test_preview_scope_counts_documents(self, mock_db, service):
        """Verify preview returns correct counts."""
        # Configure mock to return sample documents
        mock_db.fetchall.return_value = [
            {"id": "doc_1", "filename": "policy1.pdf", "doc_type": "policy", "finding_count": 5},
            {"id": "doc_2", "filename": "catalog.pdf", "doc_type": "catalog", "finding_count": 3},
        ]

        scope = BulkRemediationScope(scope_type="all")
        preview = service.preview_scope("inst_test", scope)

        assert preview["document_count"] == 2
        assert preview["total_findings"] == 8
        assert len(preview["documents"]) == 2
        assert preview["has_more"] is False

    def test_preview_scope_with_doc_type_filter(self, mock_db, service):
        """Verify preview filters by doc type."""
        mock_db.fetchall.return_value = [
            {"id": "doc_1", "filename": "policy1.pdf", "doc_type": "policy", "finding_count": 5},
        ]

        scope = BulkRemediationScope(
            scope_type="doc_type",
            doc_types=["policy"],
        )
        preview = service.preview_scope("inst_test", scope)

        assert preview["document_count"] == 1

    def test_preview_scope_limits_to_20(self, mock_db, service):
        """Verify preview limits document list to 20."""
        # Create 25 documents
        docs = [
            {"id": f"doc_{i}", "filename": f"doc{i}.pdf", "doc_type": "policy", "finding_count": 1}
            for i in range(25)
        ]
        mock_db.fetchall.return_value = docs

        scope = BulkRemediationScope(scope_type="all")
        preview = service.preview_scope("inst_test", scope)

        assert preview["document_count"] == 25
        assert len(preview["documents"]) == 20
        assert preview["has_more"] is True


class TestCreateJob:
    """Tests for job creation."""

    def test_create_job_stores_items(self, mock_db, service):
        """Verify job creates items for each document."""
        mock_db.fetchall.return_value = [
            {"id": "doc_1", "filename": "policy1.pdf", "doc_type": "policy", "finding_count": 5},
            {"id": "doc_2", "filename": "catalog.pdf", "doc_type": "catalog", "finding_count": 3},
        ]

        scope = BulkRemediationScope(scope_type="all")
        job = service.create_job("inst_test", scope, created_by="user_123")

        assert job.id is not None
        assert job.status == "pending"
        assert job.institution_id == "inst_test"
        assert job.total_documents == 2
        assert job.created_by == "user_123"

    def test_create_job_with_empty_scope(self, mock_db, service):
        """Verify job handles empty scope gracefully."""
        mock_db.fetchall.return_value = []

        scope = BulkRemediationScope(scope_type="all")
        job = service.create_job("inst_test", scope)

        assert job.id is not None
        assert job.total_documents == 0


class TestJobLifecycle:
    """Tests for job pause/resume/cancel."""

    def test_pause_job(self, mock_db, service):
        """Verify pause updates job status."""
        mock_db.rowcount = 1

        result = service.pause_job("bulk_test")

        assert result is True
        mock_db.execute.assert_called()

    def test_pause_job_not_running(self, mock_db, service):
        """Verify pause fails if not running."""
        mock_db.rowcount = 0

        result = service.pause_job("bulk_test")

        assert result is False

    def test_resume_job(self, mock_db, service):
        """Verify resume updates job status."""
        mock_db.rowcount = 1

        result = service.resume_job("bulk_test")

        assert result is True

    def test_cancel_job(self, mock_db, service):
        """Verify cancel marks job as failed."""
        mock_db.rowcount = 1

        result = service.cancel_job("bulk_test")

        assert result is True


class TestApproval:
    """Tests for approval workflow."""

    def test_approve_item(self, mock_db, service):
        """Verify single item approval."""
        mock_db.rowcount = 1

        result = service.approve_item("britem_test", "user_123")

        assert result is True

    def test_reject_item(self, mock_db, service):
        """Verify single item rejection."""
        mock_db.rowcount = 1

        result = service.reject_item("britem_test", "user_123")

        assert result is True

    def test_approve_all(self, mock_db, service):
        """Verify batch approval updates all items."""
        mock_db.rowcount = 5

        count = service.approve_all("bulk_test", "user_123")

        assert count == 5

    def test_reject_all(self, mock_db, service):
        """Verify batch rejection updates all items."""
        mock_db.rowcount = 3

        count = service.reject_all("bulk_test", "user_123")

        assert count == 3


class TestGetJob:
    """Tests for job retrieval."""

    def test_get_job_with_items(self, mock_db, service):
        """Verify get job returns job with items."""
        # Configure mock for job query
        mock_db.fetchone.return_value = {
            "id": "bulk_test",
            "institution_id": "inst_test",
            "scope_type": "all",
            "scope_value": "{}",
            "status": "complete",
            "total_documents": 2,
            "processed_documents": 2,
            "successful_remediations": 2,
            "failed_remediations": 0,
            "skipped_documents": 0,
            "approval_status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
            "started_at": "2024-01-01T00:01:00Z",
            "completed_at": "2024-01-01T00:05:00Z",
            "created_by": "user_123",
            "error_message": None,
        }
        mock_db.fetchall.return_value = [
            {
                "id": "britem_1",
                "job_id": "bulk_test",
                "document_id": "doc_1",
                "document_name": "test.pdf",
                "finding_count": 5,
                "status": "complete",
                "remediation_job_id": "rem_1",
                "changes_count": 3,
                "confidence": 0.9,
                "approval_status": "pending",
                "approved_by": None,
                "approved_at": None,
                "error_message": None,
                "processed_at": "2024-01-01T00:02:00Z",
            }
        ]

        job = service.get_job("bulk_test")

        assert job is not None
        assert job["id"] == "bulk_test"
        assert job["status"] == "complete"
        assert len(job["items"]) == 1
        assert job["items"][0]["document_id"] == "doc_1"

    def test_get_job_not_found(self, mock_db, service):
        """Verify get job returns None if not found."""
        mock_db.fetchone.return_value = None

        job = service.get_job("nonexistent")

        assert job is None


class TestListJobs:
    """Tests for job listing."""

    def test_list_jobs_pagination(self, mock_db, service):
        """Verify list jobs supports pagination."""
        mock_db.fetchone.return_value = {"cnt": 25}
        mock_db.fetchall.return_value = [
            {
                "id": f"bulk_{i}",
                "institution_id": "inst_test",
                "scope_type": "all",
                "scope_value": "{}",
                "status": "pending",
                "total_documents": 5,
                "processed_documents": 0,
                "successful_remediations": 0,
                "failed_remediations": 0,
                "skipped_documents": 0,
                "approval_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "created_by": None,
                "error_message": None,
            }
            for i in range(10)
        ]

        result = service.list_jobs("inst_test", limit=10, offset=0)

        assert result["total"] == 25
        assert len(result["jobs"]) == 10
        assert result["limit"] == 10
        assert result["offset"] == 0

    def test_list_jobs_with_status_filter(self, mock_db, service):
        """Verify list jobs filters by status."""
        mock_db.fetchone.return_value = {"cnt": 5}
        mock_db.fetchall.return_value = []

        result = service.list_jobs("inst_test", status="running")

        assert result["total"] == 5


class TestJobStats:
    """Tests for job statistics."""

    def test_get_job_stats(self, mock_db, service):
        """Verify stats calculation."""
        mock_db.fetchone.return_value = {
            "total": 10,
            "completed": 8,
            "failed": 2,
            "pending": 0,
            "approved": 5,
            "rejected": 1,
            "total_changes": 45,
            "avg_confidence": 0.875,
        }

        stats = service.get_job_stats("bulk_test")

        assert stats["total_items"] == 10
        assert stats["completed"] == 8
        assert stats["failed"] == 2
        assert stats["approved"] == 5
        assert stats["total_changes"] == 45
        assert stats["avg_confidence"] == 0.88  # Rounded to 2 decimal


class TestEnums:
    """Tests for status enums."""

    def test_bulk_job_status_values(self):
        """Verify job status enum values."""
        assert BulkJobStatus.PENDING.value == "pending"
        assert BulkJobStatus.RUNNING.value == "running"
        assert BulkJobStatus.PAUSED.value == "paused"
        assert BulkJobStatus.COMPLETE.value == "complete"
        assert BulkJobStatus.FAILED.value == "failed"

    def test_item_approval_status_values(self):
        """Verify approval status enum values."""
        assert ItemApprovalStatus.PENDING.value == "pending"
        assert ItemApprovalStatus.APPROVED.value == "approved"
        assert ItemApprovalStatus.REJECTED.value == "rejected"
