"""Batch Queue Service for real-time queue monitoring.

Provides queue depth metrics and status aggregation for batch operations.
"""

from typing import Dict, Any, List, Optional
from src.db.connection import get_conn


class BatchQueueService:
    """Service for monitoring batch queue status."""

    def __init__(self, institution_id: Optional[str] = None):
        """Initialize queue service.

        Args:
            institution_id: Optional institution filter. If None, returns global stats.
        """
        self.institution_id = institution_id
        self.conn = get_conn()

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status with counts by status.

        Returns:
            Dict with pending, running, completed, failed, cancelled counts
            and queue depth metrics.
        """
        cursor = self.conn.cursor()

        # Build WHERE clause
        where = ""
        params = []
        if self.institution_id:
            where = "WHERE institution_id = ?"
            params = [self.institution_id]

        # Get counts by status
        cursor.execute(f"""
            SELECT status, COUNT(*) as count
            FROM batch_operations
            {where}
            GROUP BY status
        """, params)

        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        # Get active batches (pending + running)
        active_statuses = ["pending", "running"]
        placeholders = ",".join(["?"] * len(active_statuses))
        active_where = f"WHERE status IN ({placeholders})"
        active_params = list(active_statuses)

        if self.institution_id:
            active_where += " AND institution_id = ?"
            active_params.append(self.institution_id)

        cursor.execute(f"""
            SELECT id, operation_type, document_count, completed_count, failed_count, status, created_at, priority_level
            FROM batch_operations
            {active_where}
            ORDER BY priority_level ASC, created_at ASC
        """, active_params)

        active_batches = [dict(row) for row in cursor.fetchall()]

        # Calculate queue depth (total pending items across batches)
        queue_depth = sum(
            b["document_count"] - b["completed_count"] - b["failed_count"]
            for b in active_batches
            if b["status"] == "pending"
        )

        return {
            "status_counts": {
                "pending": status_counts.get("pending", 0),
                "running": status_counts.get("running", 0),
                "completed": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "cancelled": status_counts.get("cancelled", 0),
            },
            "queue_depth": queue_depth,
            "active_batches": active_batches,
            "total_batches": sum(status_counts.values()),
        }

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent batch activity for monitoring.

        Args:
            limit: Maximum number of recent batches to return.

        Returns:
            List of recent batch summaries ordered by updated time.
        """
        cursor = self.conn.cursor()

        where = ""
        params = [limit]
        if self.institution_id:
            where = "WHERE institution_id = ?"
            params = [self.institution_id, limit]

        cursor.execute(f"""
            SELECT id, operation_type, document_count, completed_count, failed_count,
                   status, created_at, completed_at
            FROM batch_operations
            {where}
            ORDER BY COALESCE(completed_at, created_at) DESC
            LIMIT ?
        """, params)

        return [dict(row) for row in cursor.fetchall()]
