"""Batch Schedule Service for cron-based batch automation.

Integrates with APScheduler for automatic batch execution.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from croniter import croniter

from src.core.models import generate_id, now_iso
from src.core.models.batch_schedules import BatchSchedule
from src.db.connection import get_conn
from src.services.batch_template_service import BatchTemplateService


class BatchScheduleService:
    """Service for batch schedule management."""

    def __init__(self, workspace_manager, scheduler=None):
        """Initialize schedule service.

        Args:
            workspace_manager: WorkspaceManager instance.
            scheduler: APScheduler instance (optional, for job management).
        """
        self.workspace_manager = workspace_manager
        self.scheduler = scheduler
        self.conn = get_conn()

    def _calculate_next_run(self, cron_expression: str) -> str:
        """Calculate next run time from cron expression.

        Args:
            cron_expression: Cron expression string.

        Returns:
            ISO timestamp of next run.
        """
        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        next_time = cron.get_next(datetime)
        return next_time.isoformat().replace("+00:00", "Z")

    def create_schedule(
        self,
        institution_id: str,
        template_id: str,
        name: str,
        cron_expression: str,
    ) -> BatchSchedule:
        """Create a new batch schedule.

        Args:
            institution_id: Institution ID.
            template_id: Template to execute.
            name: Schedule name.
            cron_expression: Cron expression for timing.

        Returns:
            Created BatchSchedule.

        Raises:
            ValueError: If cron expression is invalid.
        """
        # Validate cron expression
        try:
            croniter(cron_expression)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid cron expression: {e}")

        # Verify template exists
        template_service = BatchTemplateService(self.workspace_manager)
        template = template_service.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        schedule = BatchSchedule(
            id=generate_id("bsched"),
            institution_id=institution_id,
            template_id=template_id,
            name=name,
            cron_expression=cron_expression,
            next_run=self._calculate_next_run(cron_expression),
            status="active",
            created_at=now_iso(),
            updated_at=now_iso(),
        )

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO batch_schedules
            (id, institution_id, template_id, name, cron_expression, next_run, last_run, last_batch_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            schedule.id,
            schedule.institution_id,
            schedule.template_id,
            schedule.name,
            schedule.cron_expression,
            schedule.next_run,
            schedule.last_run,
            schedule.last_batch_id,
            schedule.status,
            schedule.created_at,
            schedule.updated_at,
        ))
        self.conn.commit()

        # Register with scheduler if available
        if self.scheduler:
            self._register_job(schedule)

        return schedule

    def get_schedule(self, schedule_id: str) -> Optional[BatchSchedule]:
        """Get a schedule by ID.

        Args:
            schedule_id: Schedule ID.

        Returns:
            BatchSchedule if found, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM batch_schedules WHERE id = ?",
            (schedule_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return BatchSchedule.from_dict(dict(row))

    def list_schedules(
        self,
        institution_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BatchSchedule]:
        """List schedules for an institution.

        Args:
            institution_id: Institution ID.
            status: Optional status filter.
            limit: Maximum schedules to return.
            offset: Pagination offset.

        Returns:
            List of BatchSchedule objects.
        """
        cursor = self.conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM batch_schedules
                WHERE institution_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (institution_id, status, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM batch_schedules
                WHERE institution_id = ? AND status != 'deleted'
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (institution_id, limit, offset))

        return [BatchSchedule.from_dict(dict(row)) for row in cursor.fetchall()]

    def update_schedule(
        self,
        schedule_id: str,
        **updates
    ) -> Optional[BatchSchedule]:
        """Update a schedule.

        Args:
            schedule_id: Schedule ID.
            **updates: Fields to update (name, cron_expression).

        Returns:
            Updated BatchSchedule if found, None otherwise.
        """
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None

        allowed_fields = {"name", "cron_expression"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return schedule

        # Recalculate next_run if cron changed
        if "cron_expression" in filtered_updates:
            try:
                croniter(filtered_updates["cron_expression"])
            except (KeyError, ValueError) as e:
                raise ValueError(f"Invalid cron expression: {e}")
            filtered_updates["next_run"] = self._calculate_next_run(
                filtered_updates["cron_expression"]
            )

        filtered_updates["updated_at"] = now_iso()

        set_clause = ", ".join([f"{k} = ?" for k in filtered_updates.keys()])
        values = list(filtered_updates.values()) + [schedule_id]

        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE batch_schedules SET {set_clause} WHERE id = ?",
            values
        )
        self.conn.commit()

        # Update scheduler job if cron changed
        updated = self.get_schedule(schedule_id)
        if self.scheduler and "cron_expression" in filtered_updates:
            self._unregister_job(schedule_id)
            if updated.status == "active":
                self._register_job(updated)

        return updated

    def delete_schedule(self, schedule_id: str) -> bool:
        """Soft-delete a schedule.

        Args:
            schedule_id: Schedule ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE batch_schedules SET status = 'deleted', updated_at = ? WHERE id = ?",
            (now_iso(), schedule_id)
        )
        self.conn.commit()

        # Remove from scheduler
        if self.scheduler:
            self._unregister_job(schedule_id)

        return cursor.rowcount > 0

    def pause_schedule(self, schedule_id: str) -> Optional[BatchSchedule]:
        """Pause a schedule.

        Args:
            schedule_id: Schedule ID.

        Returns:
            Updated BatchSchedule if found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE batch_schedules SET status = 'paused', updated_at = ? WHERE id = ?",
            (now_iso(), schedule_id)
        )
        self.conn.commit()

        # Pause scheduler job
        if self.scheduler:
            try:
                self.scheduler.pause_job(f"batch_schedule_{schedule_id}")
            except Exception:
                pass  # Job may not exist

        return self.get_schedule(schedule_id)

    def resume_schedule(self, schedule_id: str) -> Optional[BatchSchedule]:
        """Resume a paused schedule.

        Args:
            schedule_id: Schedule ID.

        Returns:
            Updated BatchSchedule if found.
        """
        schedule = self.get_schedule(schedule_id)
        if not schedule or schedule.status != "paused":
            return None

        # Recalculate next run
        next_run = self._calculate_next_run(schedule.cron_expression)

        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE batch_schedules SET status = 'active', next_run = ?, updated_at = ? WHERE id = ?",
            (next_run, now_iso(), schedule_id)
        )
        self.conn.commit()

        # Resume scheduler job
        if self.scheduler:
            try:
                self.scheduler.resume_job(f"batch_schedule_{schedule_id}")
            except Exception:
                # Re-register if job was removed
                updated = self.get_schedule(schedule_id)
                self._register_job(updated)

        return self.get_schedule(schedule_id)

    def trigger_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Manually trigger a scheduled batch.

        Args:
            schedule_id: Schedule ID.

        Returns:
            Dict with batch_id or error.
        """
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return {"error": "Schedule not found"}

        return self._execute_schedule(schedule_id)

    def _execute_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Execute a schedule (create batch from template).

        Args:
            schedule_id: Schedule ID.

        Returns:
            Dict with batch_id or error.
        """
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return {"error": "Schedule not found"}

        # Execute template
        template_service = BatchTemplateService(self.workspace_manager)
        result = template_service.execute_template(schedule.template_id)

        if "error" in result:
            return result

        # Update schedule with execution info
        next_run = self._calculate_next_run(schedule.cron_expression)
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE batch_schedules
            SET last_run = ?, last_batch_id = ?, next_run = ?, updated_at = ?
            WHERE id = ?
        """, (now_iso(), result["batch_id"], next_run, now_iso(), schedule_id))
        self.conn.commit()

        return {
            "schedule_id": schedule_id,
            "batch_id": result["batch_id"],
            "template_id": schedule.template_id,
            "next_run": next_run,
        }

    def _register_job(self, schedule: BatchSchedule) -> None:
        """Register a schedule with APScheduler.

        Args:
            schedule: BatchSchedule to register.
        """
        if not self.scheduler:
            return

        job_id = f"batch_schedule_{schedule.id}"

        # Parse cron expression into APScheduler trigger kwargs
        # Format: minute hour day_of_month month day_of_week
        parts = schedule.cron_expression.split()
        if len(parts) != 5:
            return  # Invalid cron format

        cron_kwargs = {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4],
        }

        try:
            self.scheduler.add_job(
                self._execute_schedule,
                trigger="cron",
                id=job_id,
                args=[schedule.id],
                replace_existing=True,
                **cron_kwargs
            )
        except Exception as e:
            print(f"Failed to register schedule job {job_id}: {e}")

    def _unregister_job(self, schedule_id: str) -> None:
        """Remove a schedule from APScheduler.

        Args:
            schedule_id: Schedule ID.
        """
        if not self.scheduler:
            return

        job_id = f"batch_schedule_{schedule_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass  # Job may not exist

    def register_all_active_schedules(self) -> int:
        """Register all active schedules with APScheduler on startup.

        Returns:
            Number of schedules registered.
        """
        if not self.scheduler:
            return 0

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM batch_schedules WHERE status = 'active'"
        )

        count = 0
        for row in cursor.fetchall():
            schedule = BatchSchedule.from_dict(dict(row))
            self._register_job(schedule)
            count += 1

        return count
