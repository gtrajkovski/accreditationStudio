"""Batch Service for bulk operations.

Handles batch processing of documents for audit and remediation operations.
Provides cost estimation, batch creation, progress tracking, and result aggregation.
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from src.core.models import (
    BatchOperation,
    BatchItem,
    DocumentType,
    generate_id,
    now_iso,
)
from src.db.connection import get_conn


# Anthropic API pricing (as of 2024, per 1M tokens)
# Source: https://www.anthropic.com/pricing
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    # Phase 29: Fast model for simple tasks
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0},
}

# Average token usage per operation (empirical estimates)
# Format: {operation_type: {doc_type: (avg_input_tokens, avg_output_tokens)}}
AVG_TOKENS_PER_OPERATION = {
    "audit": {
        DocumentType.CATALOG.value: (12000, 3000),
        DocumentType.POLICY_MANUAL.value: (8000, 2500),
        DocumentType.STUDENT_HANDBOOK.value: (6000, 2000),
        DocumentType.FACULTY_HANDBOOK.value: (5500, 1800),
        DocumentType.ENROLLMENT_AGREEMENT.value: (4000, 1200),
        "default": (5000, 1500),
    },
    "remediation": {
        DocumentType.CATALOG.value: (8000, 2000),
        DocumentType.POLICY_MANUAL.value: (6000, 1800),
        DocumentType.STUDENT_HANDBOOK.value: (5000, 1500),
        DocumentType.FACULTY_HANDBOOK.value: (4500, 1400),
        DocumentType.ENROLLMENT_AGREEMENT.value: (3000, 1000),
        "default": (4000, 1200),
    },
}


def estimate_batch_cost(
    operation_type: str,
    documents: List[Dict[str, Any]],
    model: str = "claude-sonnet-4-20250514"
) -> Dict[str, Any]:
    """Estimate the cost of a batch operation.

    Args:
        operation_type: "audit" or "remediation"
        documents: List of document dicts with 'id', 'name', 'doc_type'
        model: Model name to use for pricing

    Returns:
        Dict with:
            - total_cost: Estimated total cost in dollars
            - per_document: List of per-document cost breakdowns
            - breakdown: Aggregated token and cost breakdown
            - document_count: Number of documents
            - warning: Optional warning for large batches
    """
    if model not in MODEL_PRICING:
        model = "claude-sonnet-4-20250514"  # Default fallback

    pricing = MODEL_PRICING[model]
    token_estimates = AVG_TOKENS_PER_OPERATION.get(operation_type, AVG_TOKENS_PER_OPERATION["audit"])

    per_document = []
    total_input_tokens = 0
    total_output_tokens = 0

    for doc in documents:
        doc_type = doc.get("doc_type", "default")
        if doc_type not in token_estimates:
            doc_type = "default"

        input_tokens, output_tokens = token_estimates[doc_type]

        # Add 1.2x safety margin
        input_tokens = int(input_tokens * 1.2)
        output_tokens = int(output_tokens * 1.2)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost_for_doc = input_cost + output_cost

        per_document.append({
            "document_id": doc["id"],
            "document_name": doc.get("name", "Unknown"),
            "doc_type": doc_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": round(input_cost, 4),
            "output_cost": round(output_cost, 4),
            "total_cost": round(total_cost_for_doc, 4),
        })

        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

    total_input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
    total_output_cost = (total_output_tokens / 1_000_000) * pricing["output"]
    total_cost = total_input_cost + total_output_cost

    result = {
        "total_cost": round(total_cost, 2),
        "per_document": per_document,
        "breakdown": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "input_cost": round(total_input_cost, 2),
            "output_cost": round(total_output_cost, 2),
            "model": model,
        },
        "document_count": len(documents),
    }

    # Add warning for large batches
    if len(documents) > 20:
        result["warning"] = f"Large batch ({len(documents)} documents). This operation may take a while. Continue?"

    return result


class BatchService:
    """Service for managing batch operations."""

    def __init__(self, workspace_manager):
        """Initialize batch service.

        Args:
            workspace_manager: WorkspaceManager instance for document access
        """
        self.workspace_manager = workspace_manager
        self.conn = get_conn()

    def create_batch(
        self,
        institution_id: str,
        operation_type: str,
        document_ids: List[str],
        concurrency: int = 3,
        parent_batch_id: Optional[str] = None,
    ) -> BatchOperation:
        """Create a new batch operation.

        Args:
            institution_id: Institution ID
            operation_type: "audit" or "remediation"
            document_ids: List of document IDs to process
            concurrency: Number of concurrent operations (1-5)
            parent_batch_id: Optional parent batch ID for chained operations

        Returns:
            Created BatchOperation with items
        """
        # Load institution to get document details
        institution = self.workspace_manager.load_institution(institution_id)
        if not institution:
            raise ValueError(f"Institution not found: {institution_id}")

        # Create batch operation
        batch = BatchOperation(
            id=generate_id("batch"),
            institution_id=institution_id,
            operation_type=operation_type,
            document_count=len(document_ids),
            concurrency=min(max(concurrency, 1), 5),  # Clamp to 1-5
            status="pending",
            parent_batch_id=parent_batch_id,
        )

        # Create batch items
        for doc_id in document_ids:
            doc = None
            for d in institution.documents:
                if d.id == doc_id:
                    doc = d
                    break

            if not doc:
                continue  # Skip missing documents

            item = BatchItem(
                id=generate_id("bitem"),
                batch_id=batch.id,
                document_id=doc.id,
                document_name=doc.name,
                status="pending",
            )
            batch.items.append(item)

        # Update document count to match actual items created
        batch.document_count = len(batch.items)

        # Persist to database
        self._save_batch_to_db(batch)

        return batch

    def get_batch(self, batch_id: str) -> Optional[BatchOperation]:
        """Get a batch operation by ID.

        Args:
            batch_id: Batch ID

        Returns:
            BatchOperation if found, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM batch_operations WHERE id = ?",
            (batch_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Load batch items
        cursor.execute(
            "SELECT * FROM batch_items WHERE batch_id = ? ORDER BY created_at",
            (batch_id,)
        )
        item_rows = cursor.fetchall()

        # Convert to BatchOperation
        batch_data = dict(row)
        batch_data["metadata"] = json.loads(batch_data.get("metadata", "{}"))
        batch_data["items"] = [dict(item_row) for item_row in item_rows]

        return BatchOperation.from_dict(batch_data)

    def get_progress(self, batch_id: str) -> Dict[str, Any]:
        """Get progress for a batch operation.

        Args:
            batch_id: Batch ID

        Returns:
            Dict with progress information
        """
        batch = self.get_batch(batch_id)
        if not batch:
            return {"error": "Batch not found"}

        total = batch.document_count
        completed = batch.completed_count
        failed = batch.failed_count
        pending = total - completed - failed

        progress_pct = 0.0
        if total > 0:
            progress_pct = round((completed + failed) / total * 100, 1)

        return {
            "batch_id": batch_id,
            "status": batch.status,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_pct": progress_pct,
            "operation_type": batch.operation_type,
            "estimated_cost": batch.estimated_cost,
            "actual_cost": batch.actual_cost,
        }

    def update_item_status(
        self,
        item_id: str,
        status: str,
        **kwargs
    ) -> None:
        """Update the status of a batch item.

        Args:
            item_id: Batch item ID
            status: New status (pending, running, completed, failed)
            **kwargs: Additional fields to update (error, result_path, tokens, etc.)
        """
        cursor = self.conn.cursor()

        # Build update fields
        updates = {"status": status}
        if status == "running" and "started_at" not in kwargs:
            updates["started_at"] = now_iso()
        if status in ("completed", "failed") and "completed_at" not in kwargs:
            updates["completed_at"] = now_iso()

        updates.update(kwargs)

        # Update item
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [item_id]

        cursor.execute(
            f"UPDATE batch_items SET {set_clause} WHERE id = ?",
            values
        )

        # Get batch_id
        cursor.execute("SELECT batch_id FROM batch_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            self.conn.commit()
            return

        batch_id = row["batch_id"]

        # Recalculate batch completed/failed counts
        cursor.execute(
            "SELECT COUNT(*) as count FROM batch_items WHERE batch_id = ? AND status = 'completed'",
            (batch_id,)
        )
        completed_count = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM batch_items WHERE batch_id = ? AND status = 'failed'",
            (batch_id,)
        )
        failed_count = cursor.fetchone()["count"]

        # Update batch
        cursor.execute(
            """
            UPDATE batch_operations
            SET completed_count = ?, failed_count = ?
            WHERE id = ?
            """,
            (completed_count, failed_count, batch_id)
        )

        # Check if batch is complete
        cursor.execute(
            "SELECT document_count FROM batch_operations WHERE id = ?",
            (batch_id,)
        )
        row = cursor.fetchone()
        document_count = row["document_count"]

        if completed_count + failed_count >= document_count:
            cursor.execute(
                """
                UPDATE batch_operations
                SET status = 'completed', completed_at = ?
                WHERE id = ?
                """,
                (now_iso(), batch_id)
            )

        self.conn.commit()

    def cancel_batch(self, batch_id: str) -> Dict[str, Any]:
        """Cancel a batch operation.

        Args:
            batch_id: Batch ID

        Returns:
            Dict with cancellation summary
        """
        batch = self.get_batch(batch_id)
        if not batch:
            return {"error": "Batch not found"}

        cursor = self.conn.cursor()

        # Cancel pending items
        cursor.execute(
            """
            UPDATE batch_items
            SET status = 'failed', error = 'Cancelled by user', completed_at = ?
            WHERE batch_id = ? AND status = 'pending'
            """,
            (now_iso(), batch_id)
        )
        cancelled_count = cursor.rowcount

        # Update batch status
        cursor.execute(
            """
            UPDATE batch_operations
            SET status = 'cancelled', completed_at = ?
            WHERE id = ?
            """,
            (now_iso(), batch_id)
        )

        self.conn.commit()

        # Refresh batch
        batch = self.get_batch(batch_id)

        return {
            "status": "cancelled",
            "completed_items": batch.completed_count,
            "cancelled_items": cancelled_count,
            "batch_id": batch_id,
        }

    def list_batches(
        self,
        institution_id: str,
        limit: int = 20,
        offset: int = 0,
        operation_type: Optional[str] = None
    ) -> List[BatchOperation]:
        """List batch operations for an institution.

        Args:
            institution_id: Institution ID
            limit: Maximum number of batches to return
            offset: Offset for pagination
            operation_type: Optional filter by operation type

        Returns:
            List of BatchOperation objects
        """
        cursor = self.conn.cursor()

        if operation_type:
            cursor.execute(
                """
                SELECT * FROM batch_operations
                WHERE institution_id = ? AND operation_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (institution_id, operation_type, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM batch_operations
                WHERE institution_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (institution_id, limit, offset)
            )

        rows = cursor.fetchall()
        batches = []

        for row in rows:
            batch_data = dict(row)
            batch_data["metadata"] = json.loads(batch_data.get("metadata", "{}"))
            batch_data["items"] = []  # Don't load items for list view
            batches.append(BatchOperation.from_dict(batch_data))

        return batches

    def _save_batch_to_db(self, batch: BatchOperation) -> None:
        """Save batch and items to database.

        Args:
            batch: BatchOperation to save
        """
        cursor = self.conn.cursor()

        # Insert batch operation
        cursor.execute(
            """
            INSERT INTO batch_operations (
                id, institution_id, operation_type, document_count,
                completed_count, failed_count, estimated_cost, actual_cost,
                concurrency, status, created_at, started_at, completed_at,
                parent_batch_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.id,
                batch.institution_id,
                batch.operation_type,
                batch.document_count,
                batch.completed_count,
                batch.failed_count,
                batch.estimated_cost,
                batch.actual_cost,
                batch.concurrency,
                batch.status,
                batch.created_at,
                batch.started_at,
                batch.completed_at,
                batch.parent_batch_id,
                json.dumps(batch.metadata),
            )
        )

        # Insert batch items
        for item in batch.items:
            cursor.execute(
                """
                INSERT INTO batch_items (
                    id, batch_id, document_id, document_name, status,
                    task_id, result_path, error, input_tokens, output_tokens,
                    duration_ms, findings_count, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.batch_id,
                    item.document_id,
                    item.document_name,
                    item.status,
                    item.task_id,
                    item.result_path,
                    item.error,
                    item.input_tokens,
                    item.output_tokens,
                    item.duration_ms,
                    item.findings_count,
                    item.created_at,
                    item.started_at,
                    item.completed_at,
                )
            )

        self.conn.commit()
