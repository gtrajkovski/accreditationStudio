"""Action plan domain models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


class ActionItemPriority(str, Enum):
    """Priority levels for action items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemStatus(str, Enum):
    """Status of an action item."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ActionItem:
    """A single action item in a remediation plan."""
    id: str = field(default_factory=lambda: generate_id("act"))
    title: str = ""
    description: str = ""
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: ActionItemStatus = ActionItemStatus.NOT_STARTED

    # Links
    finding_id: str = ""
    standard_ref: str = ""
    document_id: str = ""

    # Assignment
    assigned_to: str = ""
    assigned_by: str = ""

    # Dates
    due_date: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Progress
    progress_notes: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "finding_id": self.finding_id,
            "standard_ref": self.standard_ref,
            "document_id": self.document_id,
            "assigned_to": self.assigned_to,
            "assigned_by": self.assigned_by,
            "due_date": self.due_date,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_notes": self.progress_notes,
            "blockers": self.blockers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionItem":
        return cls(
            id=data.get("id", generate_id("act")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=ActionItemPriority(data.get("priority", "medium")),
            status=ActionItemStatus(data.get("status", "not_started")),
            finding_id=data.get("finding_id", ""),
            standard_ref=data.get("standard_ref", ""),
            document_id=data.get("document_id", ""),
            assigned_to=data.get("assigned_to", ""),
            assigned_by=data.get("assigned_by", ""),
            due_date=data.get("due_date"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress_notes=data.get("progress_notes", []),
            blockers=data.get("blockers", []),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class ActionPlan:
    """A complete action plan for remediation tracking."""
    id: str = field(default_factory=lambda: generate_id("plan"))
    institution_id: str = ""
    name: str = ""
    description: str = ""

    # Links
    findings_report_id: str = ""
    packet_id: str = ""

    # Items
    items: List[ActionItem] = field(default_factory=list)

    # Statistics
    total_items: int = 0
    items_completed: int = 0
    items_in_progress: int = 0
    items_blocked: int = 0
    items_overdue: int = 0

    # Dates
    target_completion_date: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "name": self.name,
            "description": self.description,
            "findings_report_id": self.findings_report_id,
            "packet_id": self.packet_id,
            "items": [i.to_dict() for i in self.items],
            "total_items": self.total_items,
            "items_completed": self.items_completed,
            "items_in_progress": self.items_in_progress,
            "items_blocked": self.items_blocked,
            "items_overdue": self.items_overdue,
            "target_completion_date": self.target_completion_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionPlan":
        return cls(
            id=data.get("id", generate_id("plan")),
            institution_id=data.get("institution_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            findings_report_id=data.get("findings_report_id", ""),
            packet_id=data.get("packet_id", ""),
            items=[ActionItem.from_dict(i) for i in data.get("items", [])],
            total_items=data.get("total_items", 0),
            items_completed=data.get("items_completed", 0),
            items_in_progress=data.get("items_in_progress", 0),
            items_blocked=data.get("items_blocked", 0),
            items_overdue=data.get("items_overdue", 0),
            target_completion_date=data.get("target_completion_date"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )

    def update_stats(self) -> None:
        """Recalculate statistics."""
        self.total_items = len(self.items)
        self.items_completed = sum(1 for i in self.items if i.status == ActionItemStatus.COMPLETED)
        self.items_in_progress = sum(1 for i in self.items if i.status == ActionItemStatus.IN_PROGRESS)
        self.items_blocked = sum(1 for i in self.items if i.status == ActionItemStatus.BLOCKED)

        # Count overdue items
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.items_overdue = sum(
            1 for i in self.items
            if i.due_date and i.due_date < today and i.status not in [ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]
        )

        self.updated_at = now_iso()
