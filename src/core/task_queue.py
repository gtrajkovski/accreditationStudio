"""Background task queue for async agent operations.

Simple in-memory task queue using threading for single-user localhost tool.
For production, consider Celery or similar distributed task queue.
"""

import logging
import threading
import queue
import uuid
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """A task to be executed in the background."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    func: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
    progress_message: str = ""
    institution_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "result": self.result if not callable(self.result) else str(self.result),
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "institution_id": self.institution_id,
            "session_id": self.session_id,
        }


class TaskQueue:
    """Simple in-memory task queue with worker threads.

    Usage:
        queue = TaskQueue(num_workers=3)
        queue.start()

        task_id = queue.submit(my_function, arg1, kwarg1=value)
        status = queue.get_status(task_id)

        queue.stop()
    """

    def __init__(self, num_workers: int = 3):
        """Initialize task queue.

        Args:
            num_workers: Number of concurrent worker threads.
        """
        self.num_workers = num_workers
        self._queue: queue.Queue = queue.Queue()
        self._tasks: Dict[str, BackgroundTask] = {}
        self._workers: List[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable]] = {}

    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            return

        self._running = True
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskWorker-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self, wait: bool = True) -> None:
        """Stop worker threads.

        Args:
            wait: If True, wait for current tasks to complete.
        """
        self._running = False
        if wait:
            for worker in self._workers:
                worker.join(timeout=5.0)
        self._workers.clear()

    def submit(
        self,
        func: Callable,
        *args,
        name: str = "",
        institution_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Submit a task to the queue.

        Args:
            func: Function to execute.
            *args: Positional arguments for the function.
            name: Human-readable task name.
            institution_id: Associated institution ID.
            session_id: Associated agent session ID.
            **kwargs: Keyword arguments for the function.

        Returns:
            Task ID for tracking.
        """
        task = BackgroundTask(
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            institution_id=institution_id,
            session_id=session_id,
        )

        with self._lock:
            self._tasks[task.id] = task

        self._queue.put(task.id)
        return task.id

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task.

        Args:
            task_id: Task ID to check.

        Returns:
            Task status dictionary or None if not found.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return task.to_dict()
        return None

    def get_result(self, task_id: str) -> Any:
        """Get result of a completed task.

        Args:
            task_id: Task ID.

        Returns:
            Task result or None.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.COMPLETED:
                return task.result
        return None

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.

        Args:
            task_id: Task ID to cancel.

        Returns:
            True if cancelled, False if task was already running/completed.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def update_progress(
        self,
        task_id: str,
        progress: float,
        message: str = "",
    ) -> None:
        """Update progress of a running task.

        Called from within task functions to report progress.

        Args:
            task_id: Task ID.
            progress: Progress percentage (0.0-100.0).
            message: Progress message.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.progress = progress
                task.progress_message = message

        # Notify callbacks
        self._notify_callbacks(task_id, "progress")

    def on_complete(self, task_id: str, callback: Callable) -> None:
        """Register a callback for task completion.

        Args:
            task_id: Task ID to watch.
            callback: Function to call when task completes.
        """
        with self._lock:
            if task_id not in self._callbacks:
                self._callbacks[task_id] = []
            self._callbacks[task_id].append(callback)

    def list_tasks(
        self,
        institution_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered.

        Args:
            institution_id: Filter by institution.
            status: Filter by status.

        Returns:
            List of task status dictionaries.
        """
        with self._lock:
            tasks = list(self._tasks.values())

        if institution_id:
            tasks = [t for t in tasks if t.institution_id == institution_id]
        if status:
            tasks = [t for t in tasks if t.status == status]

        return [t.to_dict() for t in tasks]

    def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """Remove old completed tasks.

        Args:
            max_age_seconds: Remove tasks older than this.

        Returns:
            Number of tasks removed.
        """
        cutoff = datetime.now().timestamp() - max_age_seconds
        removed = 0

        with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    if task.completed_at:
                        completed_ts = datetime.fromisoformat(task.completed_at).timestamp()
                        if completed_ts < cutoff:
                            to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]
                if task_id in self._callbacks:
                    del self._callbacks[task_id]
                removed += 1

        return removed

    def _worker_loop(self) -> None:
        """Main loop for worker threads."""
        while self._running:
            try:
                task_id = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            with self._lock:
                task = self._tasks.get(task_id)
                if not task or task.status != TaskStatus.PENDING:
                    continue
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()

            self._notify_callbacks(task_id, "started")

            try:
                # Execute the task
                result = task.func(*task.args, **task.kwargs)

                with self._lock:
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now().isoformat()
                    task.progress = 100.0

                self._notify_callbacks(task_id, "completed")

            except Exception as e:
                with self._lock:
                    task.error = str(e)
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now().isoformat()

                self._notify_callbacks(task_id, "failed")

    def _notify_callbacks(self, task_id: str, event: str) -> None:
        """Notify registered callbacks."""
        callbacks = []
        with self._lock:
            callbacks = self._callbacks.get(task_id, []).copy()

        task_status = self.get_status(task_id)
        for callback in callbacks:
            try:
                callback(task_id, event, task_status)
            except Exception as e:
                logger.warning("Task callback error for %s: %s", task_id, e)


# Global task queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue.

    Returns:
        The global TaskQueue instance.
    """
    global _task_queue
    if _task_queue is None:
        from src.config import Config
        _task_queue = TaskQueue(num_workers=Config.AGENT_MAX_CONCURRENT_TASKS)
        _task_queue.start()
    return _task_queue


def shutdown_task_queue() -> None:
    """Shutdown the global task queue."""
    global _task_queue
    if _task_queue:
        _task_queue.stop()
        _task_queue = None
