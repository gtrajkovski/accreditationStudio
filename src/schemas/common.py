"""Common response schemas used across all API endpoints.

These schemas document the standard response formats for:
- Error responses (400, 404, 500)
- Success responses (200, 201)
- Validation error responses (400 with field details)
"""

from marshmallow import Schema, fields


class ErrorSchema(Schema):
    """Standard error response returned by all endpoints."""

    error = fields.Str(
        required=True,
        metadata={
            "description": "Error message describing what went wrong",
            "example": "Institution not found"
        }
    )


class SuccessSchema(Schema):
    """Standard success response for operations without data."""

    success = fields.Bool(
        required=True,
        metadata={
            "description": "Operation success status",
            "example": True
        }
    )
    message = fields.Str(
        metadata={
            "description": "Human-readable success message",
            "example": "Resource created successfully"
        }
    )


class ValidationErrorSchema(Schema):
    """Validation error response with field-level details.

    Returned by APIFlask when request validation fails (HTTP 400).
    """

    detail = fields.Dict(
        keys=fields.Str(),
        values=fields.Dict(),
        metadata={
            "description": "Field-level validation errors",
            "example": {
                "json": {
                    "name": ["Missing data for required field."]
                }
            }
        }
    )
    message = fields.Str(
        metadata={
            "description": "Summary error message",
            "example": "Validation error"
        }
    )
