"""Work Queue Service - Aggregates blockers, tasks, and approvals into unified queue."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import sqlite3

logger = logging.getLogger(__name__)

from src.core.task_queue import get_task_queue, TaskStatus
from src.db.connection import get_conn
from src.services.readiness_service import get_blockers, compute_readiness


class WorkItemType(str, Enum):
    """Types of work items in the queue."""
    BLOCKER = "blocker"
    TASK = "task"
    APPROVAL = "approval"


class WorkItemPriority(str, Enum):
    """Priority levels for work items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class WorkItem:
    """Unified work item for the queue."""
    id: str
    type: WorkItemType
    priority: WorkItemPriority
    title: str
    description: str
    source: str  # e.g., "readiness", "agent:compliance_audit", "task_queue"
    institution_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Type-specific fields
    action_label: str = "View"
    action_link: Optional[str] = None
    severity: Optional[str] = None  # For blockers
    session_id: Optional[str] = None  # For approvals
    checkpoint_id: Optional[str] = None  # For approvals
    task_id: Optional[str] = None  # For tasks
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "priority": self.priority.value if isinstance(self.priority, Enum) else self.priority,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "institution_id": self.institution_id,
            "created_at": self.created_at,
            "action_label": self.action_label,
            "action_link": self.action_link,
            "severity": self.severity,
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "metadata": self.metadata,
        }


def _severity_to_priority(severity: str) -> WorkItemPriority:
    """Map blocker severity to work item priority."""
    mapping = {
        "critical": WorkItemPriority.CRITICAL,
        "high": WorkItemPriority.HIGH,
        "medium": WorkItemPriority.MEDIUM,
        "low": WorkItemPriority.LOW,
    }
    return mapping.get(severity, WorkItemPriority.MEDIUM)


def _get_blockers_as_work_items(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    conn: Optional[sqlite3.Connection] = None
) -> List[WorkItem]:
    """Convert readiness blockers to work items."""
    items = []

    try:
        score = compute_readiness(institution_id, accreditor_code, conn)

        for i, blocker in enumerate(score.blockers):
            items.append(WorkItem(
                id=f"blocker_{institution_id}_{i}",
                type=WorkItemType.BLOCKER,
                priority=_severity_to_priority(blocker.severity),
                title=blocker.message,
                description=blocker.action,
                source="readiness",
                institution_id=institution_id,
                severity=blocker.severity,
                action_label="Fix",
                action_link=blocker.link,
            ))
    except Exception as e:
        logger.debug("Readiness computation failed, skipping blockers: %s", e)

    return items


def _get_pending_checkpoints(
    institution_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[WorkItem]:
    """Get pending human checkpoints as work items."""
    items = []
    conn = conn or get_conn()

    try:
        if institution_id:
            cursor = conn.execute("""
                SELECT id, institution_id, session_id, checkpoint_type,
                       reason, created_at, requested_by
                FROM human_checkpoints
                WHERE institution_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 50
            """, (institution_id,))
        else:
            cursor = conn.execute("""
                SELECT id, institution_id, session_id, checkpoint_type,
                       reason, created_at, requested_by
                FROM human_checkpoints
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT 50
            """)

        for row in cursor.fetchall():
            # Map checkpoint type to priority
            checkpoint_type = row["checkpoint_type"] or "review"
            priority = WorkItemPriority.HIGH
            if checkpoint_type in ("critical_decision", "compliance_determination"):
                priority = WorkItemPriority.CRITICAL
            elif checkpoint_type in ("evidence_validation", "policy_approval"):
                priority = WorkItemPriority.HIGH

            items.append(WorkItem(
                id=f"approval_{row['id']}",
                type=WorkItemType.APPROVAL,
                priority=priority,
                title=f"{checkpoint_type.replace('_', ' ').title()} Required",
                description=row["reason"] or f"Review requested by {row['requested_by']}",
                source=f"agent:{row['requested_by']}" if row["requested_by"] else "agent",
                institution_id=row["institution_id"],
                created_at=row["created_at"],
                session_id=row["session_id"],
                checkpoint_id=row["id"],
                action_label="Review",
                action_link=f"/agent-sessions?session={row['session_id']}&checkpoint={row['id']}",
            ))
    except sqlite3.OperationalError:
        # Table might not exist yet
        pass

    return items


def _get_pending_tasks(
    institution_id: Optional[str] = None
) -> List[WorkItem]:
    """Get pending background tasks as work items."""
    items = []
    queue = get_task_queue()

    # Get pending and running tasks
    for status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
        tasks = queue.list_tasks(institution_id=institution_id, status=status)

        for task in tasks:
            # Determine priority based on task name
            priority = WorkItemPriority.MEDIUM
            name_lower = task.get("name", "").lower()
            if "critical" in name_lower or "urgent" in name_lower:
                priority = WorkItemPriority.CRITICAL
            elif "audit" in name_lower or "compliance" in name_lower:
                priority = WorkItemPriority.HIGH

            items.append(WorkItem(
                id=f"task_{task['id']}",
                type=WorkItemType.TASK,
                priority=priority,
                title=task.get("name", "Background Task"),
                description=task.get("progress_message", "Processing..."),
                source="task_queue",
                institution_id=task.get("institution_id"),
                created_at=task.get("created_at", ""),
                task_id=task["id"],
                action_label="View" if status == TaskStatus.RUNNING else "Pending",
                action_link=f"/agent-sessions?task={task['id']}",
                metadata={
                    "status": status.value,
                    "progress": task.get("progress", 0),
                },
            ))

    return items


def _get_waiting_sessions(
    institution_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> List[WorkItem]:
    """Get agent sessions waiting for human input."""
    items = []
    conn = conn or get_conn()

    try:
        if institution_id:
            cursor = conn.execute("""
                SELECT id, institution_id, agent_type, status, created_at
                FROM agent_sessions
                WHERE institution_id = ? AND status = 'waiting_for_human'
                ORDER BY created_at DESC
                LIMIT 20
            """, (institution_id,))
        else:
            cursor = conn.execute("""
                SELECT id, institution_id, agent_type, status, created_at
                FROM agent_sessions
                WHERE status = 'waiting_for_human'
                ORDER BY created_at DESC
                LIMIT 20
            """)

        for row in cursor.fetchall():
            agent_name = (row["agent_type"] or "agent").replace("_", " ").title()
            items.append(WorkItem(
                id=f"session_{row['id']}",
                type=WorkItemType.APPROVAL,
                priority=WorkItemPriority.HIGH,
                title=f"{agent_name} Awaiting Input",
                description="Agent session paused waiting for human decision",
                source=f"agent:{row['agent_type']}",
                institution_id=row["institution_id"],
                created_at=row["created_at"],
                session_id=row["id"],
                action_label="Continue",
                action_link=f"/agent-sessions?session={row['id']}",
            ))
    except sqlite3.OperationalError:
        # Table might not exist
        pass

    return items


def get_work_queue(
    institution_id: Optional[str] = None,
    accreditor_code: str = "ACCSC",
    include_blockers: bool = True,
    include_tasks: bool = True,
    include_approvals: bool = True,
    limit: int = 50,
    conn: Optional[sqlite3.Connection] = None
) -> List[WorkItem]:
    """
    Get unified work queue combining blockers, tasks, and approvals.

    Args:
        institution_id: Filter to specific institution (None for all)
        accreditor_code: Accreditor for blockers computation
        include_blockers: Include readiness blockers
        include_tasks: Include background tasks
        include_approvals: Include pending approvals
        limit: Maximum items to return
        conn: Database connection (optional)

    Returns:
        List of WorkItem sorted by priority and date
    """
    items: List[WorkItem] = []

    if include_blockers and institution_id:
        items.extend(_get_blockers_as_work_items(institution_id, accreditor_code, conn))

    if include_approvals:
        items.extend(_get_pending_checkpoints(institution_id, conn))
        items.extend(_get_waiting_sessions(institution_id, conn))

    if include_tasks:
        items.extend(_get_pending_tasks(institution_id))

    # Sort by priority (critical first) then by created_at (newest first)
    priority_order = {
        WorkItemPriority.CRITICAL: 0,
        WorkItemPriority.HIGH: 1,
        WorkItemPriority.MEDIUM: 2,
        WorkItemPriority.LOW: 3,
    }

    items.sort(key=lambda x: (
        priority_order.get(x.priority, 2),
        x.created_at or "",
    ), reverse=False)

    # For created_at, we want newest first within same priority
    # So we need to sort differently
    items.sort(key=lambda x: (
        priority_order.get(x.priority, 2),
        -(datetime.fromisoformat(x.created_at.replace("Z", "+00:00")).timestamp()
          if x.created_at else 0),
    ))

    return items[:limit]


def get_work_queue_summary(
    institution_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Get summary counts for work queue.

    Returns:
        Dict with counts by type and priority
    """
    items = get_work_queue(institution_id, conn=conn, limit=200)

    by_type = {"blocker": 0, "task": 0, "approval": 0}
    by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for item in items:
        type_key = item.type.value if isinstance(item.type, Enum) else item.type
        priority_key = item.priority.value if isinstance(item.priority, Enum) else item.priority

        by_type[type_key] = by_type.get(type_key, 0) + 1
        by_priority[priority_key] = by_priority.get(priority_key, 0) + 1

    return {
        "total": len(items),
        "by_type": by_type,
        "by_priority": by_priority,
        "critical_count": by_priority["critical"],
        "needs_attention": by_priority["critical"] + by_priority["high"],
    }
