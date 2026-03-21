"""Marshmallow schemas for API documentation.

All schemas are imported here for apispec registration.
Import this package in app.py BEFORE registering blueprints.
"""

from src.schemas.common import (
    ErrorSchema,
    SuccessSchema,
    ValidationErrorSchema,
)

from src.schemas.institution import (
    InstitutionSchema,
    InstitutionCreateSchema,
    InstitutionUpdateSchema,
    InstitutionListSchema,
    ProgramSchema,
    ProgramCreateSchema,
)

from src.schemas.documents import (
    DocumentSchema,
    DocumentCreateSchema,
    DocumentUploadResponseSchema,
    DocumentListSchema,
)

from src.schemas.agents import (
    AgentSessionSchema,
    AgentSessionListSchema,
    TaskSchema,
    TaskCreateSchema,
)

from src.schemas.standards import (
    StandardsLibrarySchema,
    StandardsListSchema,
    StandardSectionSchema,
    ChecklistItemSchema,
    StandardsQuerySchema,
)

__all__ = [
    # Common
    "ErrorSchema",
    "SuccessSchema",
    "ValidationErrorSchema",
    # Institution
    "InstitutionSchema",
    "InstitutionCreateSchema",
    "InstitutionUpdateSchema",
    "InstitutionListSchema",
    "ProgramSchema",
    "ProgramCreateSchema",
    # Documents
    "DocumentSchema",
    "DocumentCreateSchema",
    "DocumentUploadResponseSchema",
    "DocumentListSchema",
    # Agents
    "AgentSessionSchema",
    "AgentSessionListSchema",
    "TaskSchema",
    "TaskCreateSchema",
    # Standards
    "StandardsLibrarySchema",
    "StandardsListSchema",
    "StandardSectionSchema",
    "ChecklistItemSchema",
    "StandardsQuerySchema",
]
