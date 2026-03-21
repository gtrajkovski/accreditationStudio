"""Marshmallow schemas for API documentation.

All schemas are imported here for apispec registration.
Import this package in app.py BEFORE registering blueprints.
"""

from src.schemas.common import (
    ErrorSchema,
    SuccessSchema,
    ValidationErrorSchema,
)

__all__ = [
    "ErrorSchema",
    "SuccessSchema",
    "ValidationErrorSchema",
]
