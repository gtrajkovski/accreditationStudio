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
from src.config import Config


# Anthropic API pricing (as of 2024, per 1M tokens)
# Source: https://www.anthropic.com/pricing
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    # Phase 29: Fast model for simple tasks
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0},
}

# Anthropic Batch API pricing (50% of standard rates)
BATCH_PRICING = {
    "claude-sonnet-4-20250514": {"input": 1.5, "output": 7.5},
    "claude-opus-4-5-20251101": {"input": 7.5, "output": 37.5},
    "claude-3-5-sonnet-20241022": {"input": 1.5, "output": 7.5},
    "claude-3-5-haiku-20241022": {"input": 0.40, "output": 2.0},
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
    model: str = "claude-sonnet-4-20250514",
    batch_mode: str = "realtime"
) -> Dict[str, Any]:
    """Estimate the cost of a batch operation.

    Args:
        operation_type: "audit" or "remediation"
        documents: List of document dicts with 'id', 'name', 'doc_type'
        model: Model name to use for pricing
        batch_mode: "realtime" (standard pricing) or "async" (50% discount)

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

    # Select pricing based on batch mode
    if batch_mode == "async":
        pricing = BATCH_PRICING.get(model, BATCH_PRICING["claude-sonnet-4-20250514"])
    else:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
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
        priority_level: int = 3,
    ) -> BatchOperation:
        """Create a new batch operation.

        Args:
            institution_id: Institution ID
            operation_type: "audit" or "remediation"
            document_ids: List of document IDs to process
            concurrency: Number of concurrent operations (1-5)
            parent_batch_id: Optional parent batch ID for chained operations
            priority_level: Priority level 1-4 (1=critical, 2=high, 3=normal, 4=low)

        Returns:
            Created BatchOperation with items
        """
        # Load institution to get document details
        institution = self.workspace_manager.load_institution(institution_id)
        if not institution:
            raise ValueError(f"Institution not found: {institution_id}")

        # Validate priority level (1-4)
        priority_level = min(max(priority_level, 1), 4)

        # Create batch operation
        batch = BatchOperation(
            id=generate_id("batch"),
            institution_id=institution_id,
            operation_type=operation_type,
            document_count=len(document_ids),
            concurrency=min(max(concurrency, 1), 5),  # Clamp to 1-5
            status="pending",
            parent_batch_id=parent_batch_id,
            priority_level=priority_level,
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

    def update_priority(self, batch_id: str, priority_level: int) -> Dict[str, Any]:
        """Update priority of a pending or running batch.

        Args:
            batch_id: Batch ID.
            priority_level: New priority (1=critical, 2=high, 3=normal, 4=low).

        Returns:
            Dict with updated batch info or error.
        """
        batch = self.get_batch(batch_id)
        if not batch:
            return {"error": "Batch not found"}

        if batch.status not in ("pending", "running"):
            return {"error": "Can only change priority of pending or running batches"}

        # Validate priority level
        priority_level = min(max(priority_level, 1), 4)

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE batch_operations SET priority_level = ? WHERE id = ?",
            (priority_level, batch_id)
        )
        self.conn.commit()

        return {
            "batch_id": batch_id,
            "priority_level": priority_level,
            "priority_name": self._priority_name(priority_level),
        }

    def _priority_name(self, level: int) -> str:
        """Convert priority level to name."""
        names = {1: "critical", 2: "high", 3: "normal", 4: "low"}
        return names.get(level, "normal")

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
                ORDER BY priority_level ASC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (institution_id, operation_type, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM batch_operations
                WHERE institution_id = ?
                ORDER BY priority_level ASC, created_at DESC
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

    def submit_to_anthropic(
        self,
        batch_id: str,
        ai_client: "AIClient"
    ) -> Dict[str, Any]:
        """Submit a batch to Anthropic Batch API for async processing.

        Args:
            batch_id: Local batch operation ID
            ai_client: AIClient instance with API credentials

        Returns:
            Dict with anthropic_batch_id, processing_status, expires_at
        """
        batch = self.get_batch(batch_id)
        if not batch:
            return {"error": "Batch not found"}

        if batch.status != "pending":
            return {"error": f"Batch already {batch.status}"}

        # Load documents to build prompts
        institution = self.workspace_manager.load_institution(batch.institution_id)
        if not institution:
            return {"error": "Institution not found"}

        # Build Anthropic batch requests
        requests = []
        for item in batch.items:
            # Find document
            doc = next((d for d in institution.documents if d.id == item.document_id), None)
            if not doc:
                continue

            # Load document content
            doc_path = self.workspace_manager.get_document_path(
                batch.institution_id, item.document_id
            )
            content = ""
            if doc_path and doc_path.exists():
                content = doc_path.read_text(encoding='utf-8', errors='ignore')[:50000]  # Limit to 50k chars

            # Build request
            system_prompt = self._get_audit_system_prompt(batch.operation_type)
            user_prompt = self._get_audit_user_prompt(batch.operation_type, doc, content)

            requests.append({
                "custom_id": item.id,  # Use batch_item.id as custom_id
                "params": {
                    "model": Config.MODEL,
                    "max_tokens": Config.MAX_TOKENS,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
            })

        if not requests:
            return {"error": "No valid documents to process"}

        # Submit to Anthropic
        result = ai_client.submit_batch(requests)

        # Update local batch record
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE batch_operations
            SET anthropic_batch_id = ?,
                batch_mode = 'async',
                anthropic_status = ?,
                expires_at = ?,
                status = 'running',
                started_at = ?
            WHERE id = ?
        """, (
            result["batch_id"],
            result["processing_status"],
            result.get("expires_at"),
            now_iso(),
            batch_id
        ))

        # Update item custom_ids
        for req in requests:
            cursor.execute("""
                UPDATE batch_items
                SET anthropic_custom_id = ?
                WHERE id = ?
            """, (req["custom_id"], req["custom_id"]))

        self.conn.commit()

        return {
            "batch_id": batch_id,
            "anthropic_batch_id": result["batch_id"],
            "processing_status": result["processing_status"],
            "request_count": len(requests),
            "expires_at": result.get("expires_at"),
        }

    def poll_anthropic_batch(
        self,
        batch_id: str,
        ai_client: "AIClient"
    ) -> Dict[str, Any]:
        """Poll Anthropic batch status and update local record."""
        batch = self.get_batch(batch_id)
        anthropic_batch_id = None

        if not batch or not batch.metadata.get("anthropic_batch_id"):
            # Check if anthropic_batch_id is in the db directly
            cursor = self.conn.cursor()
            cursor.execute("SELECT anthropic_batch_id FROM batch_operations WHERE id = ?", (batch_id,))
            row = cursor.fetchone()
            if not row or not row["anthropic_batch_id"]:
                return {"error": "No Anthropic batch ID found"}
            anthropic_batch_id = row["anthropic_batch_id"]
        else:
            anthropic_batch_id = batch.metadata.get("anthropic_batch_id")

        # Poll Anthropic
        status = ai_client.get_batch_status(anthropic_batch_id)

        # Update local record
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE batch_operations
            SET anthropic_status = ?,
                results_url = ?
            WHERE id = ?
        """, (
            status["processing_status"],
            status.get("results_url"),
            batch_id
        ))
        self.conn.commit()

        return {
            "batch_id": batch_id,
            "anthropic_batch_id": anthropic_batch_id,
            "processing_status": status["processing_status"],
            "request_counts": status["request_counts"],
            "ended_at": status.get("ended_at"),
            "results_url": status.get("results_url"),
        }

    def process_anthropic_results(
        self,
        batch_id: str,
        ai_client: "AIClient"
    ) -> Dict[str, Any]:
        """Retrieve and process results from completed Anthropic batch."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT anthropic_batch_id, anthropic_status FROM batch_operations WHERE id = ?", (batch_id,))
        row = cursor.fetchone()

        if not row or not row["anthropic_batch_id"]:
            return {"error": "No Anthropic batch ID found"}

        if row["anthropic_status"] != "ended":
            return {"error": "Batch not yet completed", "status": row["anthropic_status"]}

        anthropic_batch_id = row["anthropic_batch_id"]

        # Process results
        succeeded = 0
        failed = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for result in ai_client.get_batch_results(anthropic_batch_id):
            custom_id = result["custom_id"]

            if result["result_type"] == "succeeded":
                message = result["message"]
                input_tokens = message.usage.input_tokens if message else 0
                output_tokens = message.usage.output_tokens if message else 0

                self.update_item_status(
                    custom_id,
                    "completed",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )
                succeeded += 1
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

            elif result["result_type"] in ("errored", "expired", "canceled"):
                error_msg = str(result.get("error", result["result_type"]))
                self.update_item_status(custom_id, "failed", error=error_msg)
                failed += 1

        # Calculate actual cost with batch pricing (50% discount)
        pricing = BATCH_PRICING.get(Config.MODEL, BATCH_PRICING["claude-sonnet-4-20250514"])
        actual_cost = (
            (total_input_tokens / 1_000_000) * pricing["input"] +
            (total_output_tokens / 1_000_000) * pricing["output"]
        )

        # Update batch record
        cursor.execute("""
            UPDATE batch_operations
            SET status = 'completed',
                completed_at = ?,
                actual_cost = ?,
                completed_count = ?,
                failed_count = ?
            WHERE id = ?
        """, (now_iso(), actual_cost, succeeded, failed, batch_id))
        self.conn.commit()

        return {
            "batch_id": batch_id,
            "succeeded": succeeded,
            "failed": failed,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "actual_cost": round(actual_cost, 4),
            "savings_vs_realtime": round(actual_cost, 4),  # 50% savings
        }

    def _get_audit_system_prompt(self, operation_type: str) -> str:
        """Get system prompt for audit/remediation."""
        if operation_type == "audit":
            return """You are an expert compliance auditor for post-secondary educational institutions.
Analyze the document against accreditation standards and identify compliance issues.
Return findings in JSON format with: standard_id, finding_type, severity, description, evidence, recommendation."""
        else:
            return """You are an expert compliance remediation specialist.
Review the document and suggest specific improvements to address compliance gaps.
Return recommendations in JSON format with: issue, current_text, suggested_text, rationale."""

    def _get_audit_user_prompt(self, operation_type: str, doc, content: str) -> str:
        """Get user prompt for audit/remediation."""
        if operation_type == "audit":
            return f"""Audit the following document for compliance issues:

Document: {doc.name}
Type: {doc.doc_type}

Content:
{content}

Identify any compliance gaps, missing information, or areas needing improvement."""
        else:
            return f"""Remediate the following document:

Document: {doc.name}
Type: {doc.doc_type}

Content:
{content}

Suggest specific text changes to improve compliance."""

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
                parent_batch_id, metadata, priority_level, sla_deadline
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                batch.priority_level,
                batch.sla_deadline,
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
