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
]
