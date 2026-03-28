"""Batch template domain models."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import json

from src.core.models.helpers import generate_id, now_iso


@dataclass
class BatchTemplate:
    """Reusable batch operation configuration."""
    id: str = field(default_factory=lambda: generate_id("btpl"))
    institution_id: str = ""
    name: str = ""
    description: str = ""
    operation_type: str = ""  # audit or remediation
    document_ids: List[str] = field(default_factory=list)
    concurrency: int = 1
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "name": self.name,
            "description": self.description,
            "operation_type": self.operation_type,
            "document_ids": self.document_ids,
            "concurrency": self.concurrency,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchTemplate":
        doc_ids = data.get("document_ids", [])
        if isinstance(doc_ids, str):
            doc_ids = json.loads(doc_ids)
        return cls(
            id=data.get("id", generate_id("btpl")),
            institution_id=data.get("institution_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            operation_type=data.get("operation_type", ""),
            document_ids=doc_ids,
            concurrency=data.get("concurrency", 1),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
