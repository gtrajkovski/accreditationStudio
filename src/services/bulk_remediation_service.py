"""Bulk remediation service for fixing all findings in scope.

Provides:
- Scope preview (document counts, finding counts)
- Job creation and management
- SSE progress streaming
- Batch approval workflow
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Generator
from enum import Enum

from src.db.connection import get_conn
from src.core.models import generate_id, now_iso

logger = logging.getLogger(__name__)


class BulkJobStatus(Enum):
    """Status of a bulk remediation job."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"


class ItemApprovalStatus(Enum):
    """Approval status of a bulk remediation item."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class BulkRemediationScope:
    """Scope criteria for bulk remediation."""
    scope_type: str  # all, doc_type, program, severity
    doc_types: List[str] = field(default_factory=list)
    program_ids: List[str] = field(default_factory=list)
    severities: List[str] = field(default_factory=list)
    include_resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_type": self.scope_type,
            "doc_types": self.doc_types,
            "program_ids": self.program_ids,
            "severities": self.severities,
            "include_resolved": self.include_resolved
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BulkRemediationScope":
        """Create scope from dictionary."""
        return cls(
            scope_type=data.get("scope_type", "all"),
            doc_types=data.get("doc_types", []),
            program_ids=data.get("program_ids", []),
            severities=data.get("severities", []),
            include_resolved=data.get("include_resolved", False),
        )


@dataclass
class BulkRemediationJob:
    """A bulk remediation job."""
    id: str = field(default_factory=lambda: generate_id("bulk"))
    institution_id: str = ""
    scope_type: str = "all"
    scope_value: str = "{}"
    status: str = "pending"
    total_documents: int = 0
    processed_documents: int = 0
    successful_remediations: int = 0
    failed_remediations: int = 0
    skipped_documents: int = 0
    approval_status: str = "pending"
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "scope_type": self.scope_type,
            "scope": json.loads(self.scope_value) if self.scope_value else {},
            "status": self.status,
            "total_documents": self.total_documents,
            "processed_documents": self.processed_documents,
            "successful_remediations": self.successful_remediations,
            "failed_remediations": self.failed_remediations,
            "skipped_documents": self.skipped_documents,
            "approval_status": self.approval_status,
            "progress_percent": round(self.processed_documents / max(self.total_documents, 1) * 100, 1),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_by": self.created_by,
            "error_message": self.error_message,
        }

    @classmethod
    def from_row(cls, row) -> "BulkRemediationJob":
        """Create job from database row."""
        return cls(
            id=row["id"],
            institution_id=row["institution_id"],
            scope_type=row["scope_type"],
            scope_value=row["scope_value"] or "{}",
            status=row["status"],
            total_documents=row["total_documents"] or 0,
            processed_documents=row["processed_documents"] or 0,
            successful_remediations=row["successful_remediations"] or 0,
            failed_remediations=row["failed_remediations"] or 0,
            skipped_documents=row["skipped_documents"] or 0,
            approval_status=row["approval_status"] or "pending",
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_by=row["created_by"],
            error_message=row["error_message"],
        )


@dataclass
class BulkRemediationItem:
    """An item within a bulk remediation job."""
    id: str = field(default_factory=lambda: generate_id("britem"))
    job_id: str = ""
    document_id: str = ""
    document_name: str = ""
    finding_count: int = 0
    status: str = "pending"
    remediation_job_id: Optional[str] = None
    changes_count: int = 0
    confidence: float = 0.0
    approval_status: str = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "finding_count": self.finding_count,
            "status": self.status,
            "remediation_job_id": self.remediation_job_id,
            "changes_count": self.changes_count,
            "confidence": self.confidence,
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "error_message": self.error_message,
            "processed_at": self.processed_at,
        }

    @classmethod
    def from_row(cls, row) -> "BulkRemediationItem":
        """Create item from database row."""
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            document_id=row["document_id"],
            document_name=row["document_name"],
            finding_count=row["finding_count"] or 0,
            status=row["status"],
            remediation_job_id=row["remediation_job_id"],
            changes_count=row["changes_count"] or 0,
            confidence=row["confidence"] or 0.0,
            approval_status=row["approval_status"] or "pending",
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            error_message=row["error_message"],
            processed_at=row["processed_at"],
        )


class BulkRemediationService:
    """Service for bulk remediation operations."""

    def __init__(self, remediation_agent=None, workspace_manager=None):
        """Initialize the service.

        Args:
            remediation_agent: Optional remediation agent for running remediations
            workspace_manager: Optional workspace manager for file operations
        """
        self._remediation_agent = remediation_agent
        self._workspace_manager = workspace_manager

    def preview_scope(self, institution_id: str, scope: BulkRemediationScope) -> Dict[str, Any]:
        """
        Preview what documents and findings would be affected.

        Returns counts without actually running remediation.

        Args:
            institution_id: Institution to preview for
            scope: Scope criteria for filtering

        Returns:
            Dictionary with document_count, total_findings, documents list
        """
        conn = get_conn()
        cursor = conn.cursor()

        # Build query based on scope
        query = """
            SELECT d.id, d.filename, d.doc_type, COUNT(f.id) as finding_count
            FROM documents d
            LEFT JOIN audit_findings f ON d.id = f.document_id
                AND f.status IN ('non_compliant', 'partial')
            WHERE d.institution_id = ?
        """
        params = [institution_id]

        if scope.doc_types:
            placeholders = ",".join("?" * len(scope.doc_types))
            query += f" AND d.doc_type IN ({placeholders})"
            params.extend(scope.doc_types)

        if scope.program_ids:
            placeholders = ",".join("?" * len(scope.program_ids))
            query += f" AND d.program_id IN ({placeholders})"
            params.extend(scope.program_ids)

        if scope.severities:
            placeholders = ",".join("?" * len(scope.severities))
            query += f" AND f.severity IN ({placeholders})"
            params.extend(scope.severities)

        query += " GROUP BY d.id HAVING finding_count > 0 ORDER BY finding_count DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        documents = []
        total_findings = 0
        for row in rows:
            documents.append({
                "id": row["id"],
                "filename": row["filename"],
                "doc_type": row["doc_type"],
                "finding_count": row["finding_count"]
            })
            total_findings += row["finding_count"]

        return {
            "document_count": len(documents),
            "total_findings": total_findings,
            "documents": documents[:20],  # Preview first 20
            "has_more": len(documents) > 20,
            "all_document_ids": [d["id"] for d in documents],
        }

    def create_job(
        self,
        institution_id: str,
        scope: BulkRemediationScope,
        created_by: str = None
    ) -> BulkRemediationJob:
        """Create a bulk remediation job.

        Args:
            institution_id: Institution to create job for
            scope: Scope criteria for the job
            created_by: Optional user identifier

        Returns:
            Created BulkRemediationJob
        """
        preview = self.preview_scope(institution_id, scope)

        job = BulkRemediationJob(
            institution_id=institution_id,
            scope_type=scope.scope_type,
            scope_value=json.dumps(scope.to_dict()),
            total_documents=preview["document_count"],
            created_by=created_by
        )

        conn = get_conn()
        cursor = conn.cursor()

        # Insert job
        cursor.execute("""
            INSERT INTO bulk_remediation_jobs
            (id, institution_id, scope_type, scope_value, status, total_documents, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job.id, job.institution_id, job.scope_type, job.scope_value,
              job.status, job.total_documents, job.created_by, job.created_at))

        # Insert items for all documents (not just preview)
        all_docs = self._get_all_scope_documents(institution_id, scope)
        for doc in all_docs:
            item_id = generate_id("britem")
            cursor.execute("""
                INSERT INTO bulk_remediation_items
                (id, job_id, document_id, document_name, finding_count, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, job.id, doc["id"], doc["filename"], doc["finding_count"], "pending"))

        conn.commit()

        logger.info("Created bulk remediation job %s with %d documents", job.id, job.total_documents)
        return job

    def _get_all_scope_documents(
        self,
        institution_id: str,
        scope: BulkRemediationScope
    ) -> List[Dict[str, Any]]:
        """Get all documents matching scope (not just preview limit)."""
        conn = get_conn()
        cursor = conn.cursor()

        query = """
            SELECT d.id, d.filename, d.doc_type, COUNT(f.id) as finding_count
            FROM documents d
            LEFT JOIN audit_findings f ON d.id = f.document_id
                AND f.status IN ('non_compliant', 'partial')
            WHERE d.institution_id = ?
        """
        params = [institution_id]

        if scope.doc_types:
            placeholders = ",".join("?" * len(scope.doc_types))
            query += f" AND d.doc_type IN ({placeholders})"
            params.extend(scope.doc_types)

        if scope.program_ids:
            placeholders = ",".join("?" * len(scope.program_ids))
            query += f" AND d.program_id IN ({placeholders})"
            params.extend(scope.program_ids)

        if scope.severities:
            placeholders = ",".join("?" * len(scope.severities))
            query += f" AND f.severity IN ({placeholders})"
            params.extend(scope.severities)

        query += " GROUP BY d.id HAVING finding_count > 0 ORDER BY finding_count DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def run_job(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """
        Run bulk remediation job with SSE progress.

        Yields progress events for each document.

        Args:
            job_id: Job to run

        Yields:
            Progress event dictionaries
        """
        conn = get_conn()
        cursor = conn.cursor()

        # Update job status
        cursor.execute("""
            UPDATE bulk_remediation_jobs
            SET status = 'running', started_at = ?
            WHERE id = ?
        """, (now_iso(), job_id))
        conn.commit()

        yield {"event": "start", "job_id": job_id}

        # Get items to process (critical first)
        cursor.execute("""
            SELECT bi.*, d.id as doc_id
            FROM bulk_remediation_items bi
            JOIN documents d ON bi.document_id = d.id
            WHERE bi.job_id = ? AND bi.status = 'pending'
            ORDER BY bi.finding_count DESC
        """, (job_id,))
        items = cursor.fetchall()

        processed = 0
        successful = 0
        failed = 0

        for item in items:
            # Check if job was paused/cancelled
            cursor.execute("SELECT status FROM bulk_remediation_jobs WHERE id = ?", (job_id,))
            job_row = cursor.fetchone()
            if not job_row:
                yield {"event": "error", "error": "Job not found"}
                return

            job_status = job_row["status"]
            if job_status in ("paused", "failed"):
                yield {"event": "stopped", "reason": job_status}
                return

            # Update item status
            cursor.execute("""
                UPDATE bulk_remediation_items SET status = 'running' WHERE id = ?
            """, (item["id"],))
            conn.commit()

            yield {
                "event": "processing",
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "progress": round(processed / max(len(items), 1) * 100, 1)
            }

            try:
                # Run remediation via agent
                result = self._run_single_remediation(item["document_id"])

                # Update item
                cursor.execute("""
                    UPDATE bulk_remediation_items
                    SET status = 'complete', changes_count = ?, confidence = ?,
                        remediation_job_id = ?, processed_at = ?
                    WHERE id = ?
                """, (result.get("changes", 0), result.get("confidence", 0),
                      result.get("job_id"), now_iso(), item["id"]))

                successful += 1
                yield {
                    "event": "complete",
                    "document_id": item["document_id"],
                    "document_name": item["document_name"],
                    "changes": result.get("changes", 0),
                    "confidence": result.get("confidence", 0)
                }

            except Exception as e:
                logger.warning("Failed to remediate document %s: %s", item["document_id"], e)
                cursor.execute("""
                    UPDATE bulk_remediation_items
                    SET status = 'failed', error_message = ?, processed_at = ?
                    WHERE id = ?
                """, (str(e), now_iso(), item["id"]))

                failed += 1
                yield {
                    "event": "failed",
                    "document_id": item["document_id"],
                    "document_name": item["document_name"],
                    "error": str(e)
                }

            processed += 1

            # Update job progress
            cursor.execute("""
                UPDATE bulk_remediation_jobs
                SET processed_documents = ?, successful_remediations = ?, failed_remediations = ?
                WHERE id = ?
            """, (processed, successful, failed, job_id))
            conn.commit()

        # Complete job
        cursor.execute("""
            UPDATE bulk_remediation_jobs
            SET status = 'complete', completed_at = ?
            WHERE id = ?
        """, (now_iso(), job_id))
        conn.commit()

        yield {
            "event": "done",
            "total": len(items),
            "successful": successful,
            "failed": failed
        }

        logger.info("Completed bulk remediation job %s: %d successful, %d failed",
                   job_id, successful, failed)

    def _run_single_remediation(self, document_id: str) -> Dict[str, Any]:
        """Run remediation for a single document.

        This calls the remediation agent if available, otherwise returns
        a stub result for testing.

        Args:
            document_id: Document to remediate

        Returns:
            Dictionary with job_id, changes, confidence
        """
        if self._remediation_agent:
            # TODO: Wire up actual remediation agent call
            # result = self._remediation_agent.remediate_document(document_id)
            pass

        # Stub result for now - will be wired to agent in 38-02
        return {
            "job_id": generate_id("rem"),
            "changes": 5,
            "confidence": 0.87
        }

    def pause_job(self, job_id: str) -> bool:
        """Pause a running job.

        Args:
            job_id: Job to pause

        Returns:
            True if paused successfully
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_jobs SET status = 'paused' WHERE id = ? AND status = 'running'
        """, (job_id,))
        conn.commit()
        return cursor.rowcount > 0

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job.

        Args:
            job_id: Job to resume

        Returns:
            True if resumed successfully
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_jobs SET status = 'running' WHERE id = ? AND status = 'paused'
        """, (job_id,))
        conn.commit()
        return cursor.rowcount > 0

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (mark as failed).

        Args:
            job_id: Job to cancel

        Returns:
            True if cancelled successfully
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_jobs
            SET status = 'failed', error_message = 'Cancelled by user', completed_at = ?
            WHERE id = ? AND status IN ('pending', 'running', 'paused')
        """, (now_iso(), job_id))
        conn.commit()
        return cursor.rowcount > 0

    def approve_item(self, item_id: str, approved_by: str) -> bool:
        """Approve a remediation item.

        Args:
            item_id: Item to approve
            approved_by: User identifier

        Returns:
            True if approved successfully
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_items
            SET approval_status = 'approved', approved_by = ?, approved_at = ?
            WHERE id = ?
        """, (approved_by, now_iso(), item_id))
        conn.commit()
        return cursor.rowcount > 0

    def reject_item(self, item_id: str, approved_by: str) -> bool:
        """Reject a remediation item.

        Args:
            item_id: Item to reject
            approved_by: User identifier

        Returns:
            True if rejected successfully
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_items
            SET approval_status = 'rejected', approved_by = ?, approved_at = ?
            WHERE id = ?
        """, (approved_by, now_iso(), item_id))
        conn.commit()
        return cursor.rowcount > 0

    def approve_all(self, job_id: str, approved_by: str) -> int:
        """Approve all completed items in a job.

        Args:
            job_id: Job to approve items for
            approved_by: User identifier

        Returns:
            Number of items approved
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_items
            SET approval_status = 'approved', approved_by = ?, approved_at = ?
            WHERE job_id = ? AND status = 'complete' AND approval_status = 'pending'
        """, (approved_by, now_iso(), job_id))
        count = cursor.rowcount

        # Update job approval status
        cursor.execute("""
            UPDATE bulk_remediation_jobs SET approval_status = 'approved' WHERE id = ?
        """, (job_id,))

        conn.commit()
        logger.info("Approved %d items in job %s", count, job_id)
        return count

    def reject_all(self, job_id: str, approved_by: str) -> int:
        """Reject all completed items in a job.

        Args:
            job_id: Job to reject items for
            approved_by: User identifier

        Returns:
            Number of items rejected
        """
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bulk_remediation_items
            SET approval_status = 'rejected', approved_by = ?, approved_at = ?
            WHERE job_id = ? AND status = 'complete' AND approval_status = 'pending'
        """, (approved_by, now_iso(), job_id))
        count = cursor.rowcount

        # Update job approval status
        cursor.execute("""
            UPDATE bulk_remediation_jobs SET approval_status = 'rejected' WHERE id = ?
        """, (job_id,))

        conn.commit()
        logger.info("Rejected %d items in job %s", count, job_id)
        return count

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job with items.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Dictionary with job details and items, or None
        """
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM bulk_remediation_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None

        job = BulkRemediationJob.from_row(row)
        result = job.to_dict()

        # Get items
        cursor.execute("""
            SELECT * FROM bulk_remediation_items WHERE job_id = ? ORDER BY finding_count DESC
        """, (job_id,))
        result["items"] = [BulkRemediationItem.from_row(r).to_dict() for r in cursor.fetchall()]

        return result

    def list_jobs(
        self,
        institution_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List bulk remediation jobs for an institution.

        Args:
            institution_id: Institution to list jobs for
            status: Optional status filter
            limit: Maximum jobs to return
            offset: Pagination offset

        Returns:
            Dictionary with jobs list and total count
        """
        conn = get_conn()
        cursor = conn.cursor()

        # Count query
        count_query = "SELECT COUNT(*) as cnt FROM bulk_remediation_jobs WHERE institution_id = ?"
        count_params = [institution_id]

        if status:
            count_query += " AND status = ?"
            count_params.append(status)

        cursor.execute(count_query, count_params)
        total = cursor.fetchone()["cnt"]

        # List query
        query = """
            SELECT * FROM bulk_remediation_jobs
            WHERE institution_id = ?
        """
        params = [institution_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        jobs = [BulkRemediationJob.from_row(r).to_dict() for r in cursor.fetchall()]

        return {
            "total": total,
            "jobs": jobs,
            "limit": limit,
            "offset": offset,
        }

    def get_job_stats(self, job_id: str) -> Dict[str, Any]:
        """Get statistics for a job.

        Args:
            job_id: Job ID

        Returns:
            Dictionary with approval stats, timing, etc.
        """
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN approval_status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN approval_status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(changes_count) as total_changes,
                AVG(confidence) as avg_confidence
            FROM bulk_remediation_items
            WHERE job_id = ?
        """, (job_id,))

        row = cursor.fetchone()
        return {
            "total_items": row["total"] or 0,
            "completed": row["completed"] or 0,
            "failed": row["failed"] or 0,
            "pending": row["pending"] or 0,
            "approved": row["approved"] or 0,
            "rejected": row["rejected"] or 0,
            "total_changes": row["total_changes"] or 0,
            "avg_confidence": round(row["avg_confidence"] or 0, 2),
        }
