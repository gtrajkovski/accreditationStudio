"""Batch Template Service for managing reusable batch configurations.

Provides CRUD operations and execution for batch templates.
"""

import json
from typing import Dict, Any, List, Optional

from src.core.models import generate_id, now_iso
from src.core.models.batch_templates import BatchTemplate
from src.db.connection import get_conn
from src.services.batch_service import BatchService


class BatchTemplateService:
    """Service for batch template management."""

    def __init__(self, workspace_manager):
        """Initialize template service.

        Args:
            workspace_manager: WorkspaceManager instance for batch execution.
        """
        self.workspace_manager = workspace_manager
        self.conn = get_conn()

    def create_template(
        self,
        institution_id: str,
        name: str,
        operation_type: str,
        document_ids: List[str],
        description: str = "",
        concurrency: int = 1,
    ) -> BatchTemplate:
        """Create a new batch template.

        Args:
            institution_id: Institution ID.
            name: Template name.
            operation_type: "audit" or "remediation".
            document_ids: List of document IDs to include.
            description: Optional description.
            concurrency: Concurrency level (1-5).

        Returns:
            Created BatchTemplate.
        """
        template = BatchTemplate(
            id=generate_id("btpl"),
            institution_id=institution_id,
            name=name,
            description=description,
            operation_type=operation_type,
            document_ids=document_ids,
            concurrency=min(max(concurrency, 1), 5),
            created_at=now_iso(),
            updated_at=now_iso(),
        )

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO batch_templates
            (id, institution_id, name, description, operation_type, document_ids, concurrency, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template.id,
            template.institution_id,
            template.name,
            template.description,
            template.operation_type,
            json.dumps(template.document_ids),
            template.concurrency,
            template.created_at,
            template.updated_at,
        ))
        self.conn.commit()

        return template

    def get_template(self, template_id: str) -> Optional[BatchTemplate]:
        """Get a template by ID.

        Args:
            template_id: Template ID.

        Returns:
            BatchTemplate if found, None otherwise.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM batch_templates WHERE id = ?",
            (template_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return BatchTemplate.from_dict(dict(row))

    def list_templates(
        self,
        institution_id: str,
        operation_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BatchTemplate]:
        """List templates for an institution.

        Args:
            institution_id: Institution ID.
            operation_type: Optional filter by operation type.
            limit: Maximum templates to return.
            offset: Pagination offset.

        Returns:
            List of BatchTemplate objects.
        """
        cursor = self.conn.cursor()

        if operation_type:
            cursor.execute("""
                SELECT * FROM batch_templates
                WHERE institution_id = ? AND operation_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (institution_id, operation_type, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM batch_templates
                WHERE institution_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (institution_id, limit, offset))

        return [BatchTemplate.from_dict(dict(row)) for row in cursor.fetchall()]

    def update_template(
        self,
        template_id: str,
        **updates
    ) -> Optional[BatchTemplate]:
        """Update a template.

        Args:
            template_id: Template ID.
            **updates: Fields to update (name, description, document_ids, concurrency).

        Returns:
            Updated BatchTemplate if found, None otherwise.
        """
        template = self.get_template(template_id)
        if not template:
            return None

        allowed_fields = {"name", "description", "document_ids", "concurrency"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return template

        # Handle document_ids serialization
        if "document_ids" in filtered_updates:
            filtered_updates["document_ids"] = json.dumps(filtered_updates["document_ids"])

        filtered_updates["updated_at"] = now_iso()

        set_clause = ", ".join([f"{k} = ?" for k in filtered_updates.keys()])
        values = list(filtered_updates.values()) + [template_id]

        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE batch_templates SET {set_clause} WHERE id = ?",
            values
        )
        self.conn.commit()

        return self.get_template(template_id)

    def delete_template(self, template_id: str) -> bool:
        """Delete a template.

        Args:
            template_id: Template ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM batch_templates WHERE id = ?",
            (template_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def execute_template(self, template_id: str) -> Dict[str, Any]:
        """Execute a template to create a new batch operation.

        Args:
            template_id: Template ID to execute.

        Returns:
            Dict with batch_id and status, or error.
        """
        template = self.get_template(template_id)
        if not template:
            return {"error": "Template not found"}

        if not template.document_ids:
            return {"error": "Template has no documents configured"}

        # Create batch using existing BatchService
        batch_service = BatchService(self.workspace_manager)
        try:
            batch = batch_service.create_batch(
                institution_id=template.institution_id,
                operation_type=template.operation_type,
                document_ids=template.document_ids,
                concurrency=template.concurrency,
            )
            return {
                "batch_id": batch.id,
                "template_id": template_id,
                "template_name": template.name,
                "document_count": batch.document_count,
                "status": batch.status,
            }
        except Exception as e:
            return {"error": str(e)}
