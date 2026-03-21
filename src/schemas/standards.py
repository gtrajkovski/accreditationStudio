"""Standards library schemas for API documentation.

These schemas document the request/response formats for:
- GET /api/standards (list standards)
- GET /api/standards/{code} (get standard library)
- GET /api/standards/{code}/sections (get sections)
"""

from marshmallow import Schema, fields, validate


class ChecklistItemSchema(Schema):
    """Schema for a checklist item within a standard."""

    id = fields.Str(
        metadata={
            "description": "Checklist item ID",
            "example": "ACCSC-III-A-1"
        }
    )
    text = fields.Str(
        metadata={
            "description": "Checklist item text",
            "example": "Institution has a published mission statement"
        }
    )
    evidence_required = fields.List(
        fields.Str(),
        metadata={
            "description": "Types of evidence required",
            "example": ["Mission statement document", "Board meeting minutes approving mission"]
        }
    )
    compliance_notes = fields.Str(
        metadata={
            "description": "Notes for compliance evaluation",
            "example": "Mission must be prominently displayed in catalog and on website"
        }
    )


class StandardSectionSchema(Schema):
    """Schema for a section within a standards library."""

    id = fields.Str(
        metadata={
            "description": "Section ID",
            "example": "III"
        }
    )
    title = fields.Str(
        metadata={
            "description": "Section title",
            "example": "Institutional Mission and Objectives"
        }
    )
    description = fields.Str(
        metadata={
            "description": "Section description",
            "example": "Standards related to the institution's stated mission and objectives"
        }
    )
    checklist_items = fields.List(
        fields.Nested(ChecklistItemSchema),
        metadata={
            "description": "Checklist items in this section"
        }
    )
    subsections = fields.List(
        fields.Nested(lambda: StandardSectionSchema()),
        metadata={
            "description": "Nested subsections"
        }
    )


class StandardsLibrarySchema(Schema):
    """Full standards library schema."""

    id = fields.Str(
        metadata={
            "description": "Library ID",
            "example": "lib_accsc_2024"
        }
    )
    code = fields.Str(
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "WASC", "ABHES", "COE", "DEAC", "CUSTOM"]),
        metadata={
            "description": "Accrediting body code",
            "example": "ACCSC"
        }
    )
    name = fields.Str(
        metadata={
            "description": "Full accreditor name",
            "example": "Accrediting Commission of Career Schools and Colleges"
        }
    )
    version = fields.Str(
        metadata={
            "description": "Standards version",
            "example": "2024"
        }
    )
    sections = fields.List(
        fields.Nested(StandardSectionSchema),
        metadata={
            "description": "Top-level sections"
        }
    )
    total_items = fields.Int(
        metadata={
            "description": "Total checklist items",
            "example": 156
        }
    )
    created_at = fields.Str(
        metadata={
            "description": "ISO 8601 creation timestamp",
            "example": "2026-03-21T10:30:00Z"
        }
    )


class StandardsListSchema(Schema):
    """Response schema for listing standards libraries."""

    libraries = fields.List(
        fields.Nested(StandardsLibrarySchema),
        metadata={
            "description": "List of standards libraries"
        }
    )


class StandardsQuerySchema(Schema):
    """Query parameters for listing standards."""

    accreditor = fields.Str(
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "WASC", "ABHES", "COE", "DEAC", "CUSTOM"]),
        metadata={
            "description": "Filter by accrediting body",
            "example": "ACCSC"
        }
    )
    version = fields.Str(
        metadata={
            "description": "Filter by version",
            "example": "2024"
        }
    )
