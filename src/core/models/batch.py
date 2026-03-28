"""Batch operation domain models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from src.core.models.helpers import generate_id, now_iso


@dataclass
class BatchItem:
    """Individual item in a batch operation."""
    id: str = field(default_factory=lambda: generate_id("bitem"))
    batch_id: str = ""
    document_id: str = ""
    document_name: str = ""
    status: str = "pending"  # pending, running, completed, failed
    task_id: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    findings_count: int = 0
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "status": self.status,
            "task_id": self.task_id,
            "result_path": self.result_path,
            "error": self.error,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration_ms": self.duration_ms,
            "findings_count": self.findings_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchItem":
        return cls(
            id=data.get("id", generate_id("bitem")),
            batch_id=data.get("batch_id", ""),
            document_id=data.get("document_id", ""),
            document_name=data.get("document_name", ""),
            status=data.get("status", "pending"),
            task_id=data.get("task_id"),
            result_path=data.get("result_path"),
            error=data.get("error"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            duration_ms=data.get("duration_ms", 0),
            findings_count=data.get("findings_count", 0),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class BatchOperation:
    """Batch operation for processing multiple documents."""
    id: str = field(default_factory=lambda: generate_id("batch"))
    institution_id: str = ""
    operation_type: str = ""  # audit or remediation
    document_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    concurrency: int = 3
    status: str = "pending"  # pending, running, completed, cancelled, failed
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    parent_batch_id: Optional[str] = None
    priority_level: int = 3  # 1=critical, 2=high, 3=normal, 4=low
    sla_deadline: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    items: List[BatchItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "operation_type": self.operation_type,
            "document_count": self.document_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "concurrency": self.concurrency,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parent_batch_id": self.parent_batch_id,
            "priority_level": self.priority_level,
            "sla_deadline": self.sla_deadline,
            "metadata": self.metadata,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchOperation":
        return cls(
            id=data.get("id", generate_id("batch")),
            institution_id=data.get("institution_id", ""),
            operation_type=data.get("operation_type", ""),
            document_count=data.get("document_count", 0),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            estimated_cost=data.get("estimated_cost"),
            actual_cost=data.get("actual_cost"),
            concurrency=data.get("concurrency", 3),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            parent_batch_id=data.get("parent_batch_id"),
            priority_level=data.get("priority_level", 3),
            sla_deadline=data.get("sla_deadline"),
            metadata=data.get("metadata", {}),
            items=[BatchItem.from_dict(item) for item in data.get("items", [])],
        )
