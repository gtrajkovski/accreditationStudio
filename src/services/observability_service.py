"""Observability Service for system metrics aggregation.

Provides unified access to system health, AI costs, agent activity,
and performance metrics for the observability dashboard.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import os
import time
from src.db.connection import get_conn

# Track server start time for uptime calculation
_start_time = time.time()


class ObservabilityService:
    """Service for aggregating system observability metrics."""

    def __init__(self):
        """Initialize the observability service."""
        self.conn = get_conn()

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics.

        Returns:
            Dict containing:
                - database_size_mb: Database file size in MB
                - uptime_seconds: Server uptime in seconds
                - table_counts: Row counts for key tables
        """
        cursor = self.conn.cursor()

        # Database size
        cursor.execute(
            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        )
        row = cursor.fetchone()
        db_size_bytes = row["size"] if row else 0
        db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

        # Uptime
        uptime_seconds = int(time.time() - _start_time)

        # Table counts - handle missing tables gracefully
        table_counts = {}
        tables_to_count = ["institutions", "documents", "ai_cost_log", "batch_operations"]

        for table in tables_to_count:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                table_counts[table] = result["cnt"] if result else 0
            except Exception:
                table_counts[table] = 0

        return {
            "database_size_mb": db_size_mb,
            "uptime_seconds": uptime_seconds,
            "table_counts": table_counts,
        }

    def get_ai_costs(self, days: int = 30) -> Dict[str, Any]:
        """Get AI API cost metrics.

        Args:
            days: Number of days to look back (default 30)

        Returns:
            Dict containing:
                - total_cost: Total cost in USD
                - input_tokens: Total input tokens
                - output_tokens: Total output tokens
                - call_count: Number of API calls
                - by_model: Cost breakdown by model
                - daily_trend: Daily cost trend
        """
        cursor = self.conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Check if ai_cost_log table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_cost_log'"
        )
        if not cursor.fetchone():
            return {
                "total_cost": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "call_count": 0,
                "by_model": [],
                "daily_trend": [],
            }

        # Total metrics
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COUNT(*) as call_count
            FROM ai_cost_log
            WHERE created_at > ?
            """,
            (cutoff,),
        )
        totals = cursor.fetchone()

        # By model
        cursor.execute(
            """
            SELECT
                model,
                COALESCE(SUM(cost_usd), 0) as cost,
                COUNT(*) as calls
            FROM ai_cost_log
            WHERE created_at > ?
            GROUP BY model
            ORDER BY cost DESC
            """,
            (cutoff,),
        )
        by_model = [dict(row) for row in cursor.fetchall()]

        # Daily trend
        cursor.execute(
            """
            SELECT
                DATE(created_at) as date,
                COALESCE(SUM(cost_usd), 0) as cost
            FROM ai_cost_log
            WHERE created_at > ?
            GROUP BY DATE(created_at)
            ORDER BY date
            """,
            (cutoff,),
        )
        daily_trend = [dict(row) for row in cursor.fetchall()]

        return {
            "total_cost": round(totals["total_cost"], 4),
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "call_count": totals["call_count"],
            "by_model": by_model,
            "daily_trend": daily_trend,
        }

    def get_agent_activity(self) -> Dict[str, Any]:
        """Get agent/batch activity metrics.

        Returns:
            Dict containing:
                - active_count: Currently active batches
                - completed_24h: Batches completed in last 24 hours
                - failed_24h: Batches failed in last 24 hours
                - recent_batches: List of 5 most recent batches
        """
        cursor = self.conn.cursor()

        # Check if batch_operations table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batch_operations'"
        )
        if not cursor.fetchone():
            return {
                "active_count": 0,
                "completed_24h": 0,
                "failed_24h": 0,
                "recent_batches": [],
            }

        # Active count (pending + running)
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM batch_operations
            WHERE status IN ('pending', 'running')
            """
        )
        active_count = cursor.fetchone()["cnt"]

        # Completed in last 24 hours
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM batch_operations
            WHERE status = 'completed'
              AND completed_at > datetime('now', '-1 day')
            """
        )
        completed_24h = cursor.fetchone()["cnt"]

        # Failed in last 24 hours
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM batch_operations
            WHERE status = 'failed'
              AND completed_at > datetime('now', '-1 day')
            """
        )
        failed_24h = cursor.fetchone()["cnt"]

        # Recent batches
        cursor.execute(
            """
            SELECT
                id,
                operation_type,
                status,
                document_count,
                completed_count,
                failed_count,
                created_at
            FROM batch_operations
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        recent_batches = [dict(row) for row in cursor.fetchall()]

        return {
            "active_count": active_count,
            "completed_24h": completed_24h,
            "failed_24h": failed_24h,
            "recent_batches": recent_batches,
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.

        Returns:
            Dict containing:
                - queue_depth: Total pending items across active batches
                - avg_batch_duration_ms: Average batch duration in ms
                - throughput_per_hour: Batches completed in last hour
        """
        cursor = self.conn.cursor()

        # Check if batch_operations table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batch_operations'"
        )
        if not cursor.fetchone():
            return {
                "queue_depth": 0,
                "avg_batch_duration_ms": None,
                "throughput_per_hour": 0,
            }

        # Queue depth: pending items in active batches
        cursor.execute(
            """
            SELECT COALESCE(SUM(document_count - completed_count - failed_count), 0) as depth
            FROM batch_operations
            WHERE status IN ('pending', 'running')
            """
        )
        queue_depth = cursor.fetchone()["depth"]

        # Average batch duration (completed batches with timestamps)
        cursor.execute(
            """
            SELECT AVG(
                (julianday(completed_at) - julianday(started_at)) * 86400000
            ) as avg_ms
            FROM batch_operations
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND started_at IS NOT NULL
            LIMIT 100
            """
        )
        result = cursor.fetchone()
        avg_duration = round(result["avg_ms"], 2) if result and result["avg_ms"] else None

        # Throughput: completed in last hour
        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM batch_operations
            WHERE status = 'completed'
              AND completed_at > datetime('now', '-1 hour')
            """
        )
        throughput = cursor.fetchone()["cnt"]

        return {
            "queue_depth": queue_depth,
            "avg_batch_duration_ms": avg_duration,
            "throughput_per_hour": throughput,
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all observability metrics combined.

        Returns:
            Dict with system_health, ai_costs, agent_activity,
            performance, and timestamp keys.
        """
        return {
            "system_health": self.get_system_health(),
            "ai_costs": self.get_ai_costs(),
            "agent_activity": self.get_agent_activity(),
            "performance": self.get_performance_metrics(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def get_observability_service() -> ObservabilityService:
    """Factory function to create ObservabilityService instance.

    Returns:
        New ObservabilityService instance.
    """
    return ObservabilityService()
