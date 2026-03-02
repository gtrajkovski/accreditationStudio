"""Core domain layer for AccreditAI.

Contains models, workspace management, and task queue.
"""

from src.core.workspace import WorkspaceManager
from src.core.task_queue import (
    TaskQueue,
    BackgroundTask,
    TaskStatus,
    get_task_queue,
    shutdown_task_queue,
)

__all__ = [
    "WorkspaceManager",
    "TaskQueue",
    "BackgroundTask",
    "TaskStatus",
    "get_task_queue",
    "shutdown_task_queue",
]
