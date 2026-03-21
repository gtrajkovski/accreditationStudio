"""Document schemas for API documentation.

These schemas document the request/response formats for:
- POST /api/documents/upload (upload document)
- GET /api/documents/{id} (get document)
- GET /api/institutions/{id}/documents (list institution documents)
"""

from marshmallow import Schema, fields, validate


class DocumentCreateSchema(Schema):
    """Schema for creating a document record (POST request body)."""

    title = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=500),
        metadata={
            "description": "Document title",
            "example": "Student Handbook 2026"
        }
    )
    doc_type = fields.Str(
        required=True,
        validate=validate.OneOf([
            "enrollment_agreement", "catalog", "student_handbook",
            "admissions_manual", "faculty_handbook", "policy_manual",
            "self_evaluation_report", "canvas_manual", "financial_aid_policy",
            "complaint_policy", "safety_plan", "drug_free_policy",
            "title_ix_policy", "ada_policy", "faculty_pd_protocol",
            "advisory_committee_minutes", "organizational_chart",
            "financial_statements", "other"
        ]),
        metadata={
            "description": "Document type for classification",
            "example": "policy_manual"
        }
    )
    description = fields.Str(
        load_default="",
        metadata={
            "description": "Optional document description",
            "example": "Official student handbook containing all institutional policies"
        }
    )


class DocumentSchema(DocumentCreateSchema):
    """Full document schema (includes server-generated fields)."""

    id = fields.Str(
        dump_only=True,
        metadata={
            "description": "Server-generated document ID",
            "example": "doc_abc123def456"
        }
    )
    institution_id = fields.Str(
        dump_only=True,
        metadata={
            "description": "Parent institution ID",
            "example": "inst_xyz789"
        }
    )
    file_path = fields.Str(
        dump_only=True,
        metadata={
            "description": "Path to document file in workspace",
            "example": "workspace/inst_xyz789/policies/handbook.pdf"
        }
    )
    file_size = fields.Int(
        dump_only=True,
        metadata={
            "description": "File size in bytes",
            "example": 1048576
        }
    )
    mime_type = fields.Str(
        dump_only=True,
        metadata={
            "description": "MIME type of document",
            "example": "application/pdf"
        }
    )
    page_count = fields.Int(
        dump_only=True,
        metadata={
            "description": "Number of pages (for PDFs)",
            "example": 45
        }
    )
    compliance_status = fields.Str(
        dump_only=True,
        validate=validate.OneOf(["not_assessed", "compliant", "partial", "non_compliant"]),
        metadata={
            "description": "Compliance status from audit",
            "example": "partial"
        }
    )
    created_at = fields.Str(
        dump_only=True,
        metadata={
            "description": "ISO 8601 creation timestamp",
            "example": "2026-03-21T10:30:00Z"
        }
    )
    updated_at = fields.Str(
        dump_only=True,
        metadata={
            "description": "ISO 8601 last update timestamp",
            "example": "2026-03-21T14:45:00Z"
        }
    )


class DocumentUploadResponseSchema(Schema):
    """Response schema for document upload endpoint."""

    success = fields.Bool(
        metadata={
            "description": "Upload success status",
            "example": True
        }
    )
    document = fields.Nested(
        DocumentSchema,
        metadata={
            "description": "Created document record"
        }
    )
    message = fields.Str(
        metadata={
            "description": "Success message",
            "example": "Document uploaded and queued for processing"
        }
    )


class DocumentListSchema(Schema):
    """Response schema for listing documents."""

    documents = fields.List(
        fields.Nested(DocumentSchema),
        metadata={
            "description": "List of document records"
        }
    )
    total = fields.Int(
        metadata={
            "description": "Total number of documents",
            "example": 25
        }
    )
