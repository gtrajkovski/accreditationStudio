"""Batch schedule domain models."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from src.core.models.helpers import generate_id, now_iso


@dataclass
class BatchSchedule:
    """Scheduled batch operation configuration."""
    id: str = field(default_factory=lambda: generate_id("bsched"))
    institution_id: str = ""
    template_id: str = ""  # References batch_templates
    name: str = ""
    cron_expression: str = ""  # e.g., "0 9 * * MON" for 9am Mondays
    next_run: Optional[str] = None  # ISO timestamp of next scheduled run
    last_run: Optional[str] = None  # ISO timestamp of last execution
    last_batch_id: Optional[str] = None  # ID of last batch created
    status: str = "active"  # active, paused, deleted
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "template_id": self.template_id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "last_batch_id": self.last_batch_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchSchedule":
        return cls(
            id=data.get("id", generate_id("bsched")),
            institution_id=data.get("institution_id", ""),
            template_id=data.get("template_id", ""),
            name=data.get("name", ""),
            cron_expression=data.get("cron_expression", ""),
            next_run=data.get("next_run"),
            last_run=data.get("last_run"),
            last_batch_id=data.get("last_batch_id"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
