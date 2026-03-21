"""Institution and Program schemas for API documentation.

These schemas document the request/response formats for:
- POST /api/institutions (create institution)
- GET /api/institutions (list institutions)
- GET /api/institutions/{id} (get institution)
- PUT /api/institutions/{id} (update institution)
- POST /api/institutions/{id}/programs (create program)
- GET /api/institutions/{id}/programs (list programs)
"""

from marshmallow import Schema, fields, validate


class InstitutionCreateSchema(Schema):
    """Schema for creating a new institution (POST request body)."""

    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        metadata={
            "description": "Institution name",
            "example": "Tech University of Florida"
        }
    )
    accrediting_body = fields.Str(
        required=True,
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "WASC", "ABHES", "COE", "DEAC", "CUSTOM"]),
        metadata={
            "description": "Accrediting body code",
            "example": "ACCSC"
        }
    )
    opeid = fields.Str(
        validate=validate.Regexp(r"^\d{8}$", error="Must be 8 digits"),
        load_default="",
        metadata={
            "description": "8-digit OPE ID (optional)",
            "example": "12345678"
        }
    )
    website = fields.Url(
        load_default="",
        metadata={
            "description": "Institution website URL (optional)",
            "example": "https://techuniversity.edu"
        }
    )


class InstitutionSchema(InstitutionCreateSchema):
    """Full institution schema (includes server-generated fields)."""

    id = fields.Str(
        dump_only=True,
        metadata={
            "description": "Server-generated institution ID",
            "example": "inst_abc123def456"
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


class InstitutionUpdateSchema(Schema):
    """Schema for updating an institution (PUT request body, all fields optional)."""

    name = fields.Str(
        validate=validate.Length(min=1, max=200),
        metadata={
            "description": "Institution name",
            "example": "Tech University of Florida"
        }
    )
    accrediting_body = fields.Str(
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "WASC", "ABHES", "COE", "DEAC", "CUSTOM"]),
        metadata={
            "description": "Accrediting body code",
            "example": "SACSCOC"
        }
    )
    opeid = fields.Str(
        validate=validate.Regexp(r"^\d{8}$", error="Must be 8 digits"),
        metadata={
            "description": "8-digit OPE ID",
            "example": "87654321"
        }
    )
    website = fields.Url(
        metadata={
            "description": "Institution website URL",
            "example": "https://newwebsite.edu"
        }
    )


class InstitutionListSchema(Schema):
    """Response schema for listing institutions."""

    class Meta:
        # Allow additional fields from workspace_manager.list_institutions()
        strict = False

    id = fields.Str(metadata={"description": "Institution ID", "example": "inst_abc123"})
    name = fields.Str(metadata={"description": "Institution name", "example": "Tech University"})
    accrediting_body = fields.Str(metadata={"description": "Accrediting body", "example": "ACCSC"})
    document_count = fields.Int(metadata={"description": "Number of documents", "example": 15})
    program_count = fields.Int(metadata={"description": "Number of programs", "example": 3})
    compliance_status = fields.Str(metadata={"description": "Compliance status", "example": "partial"})


class ProgramCreateSchema(Schema):
    """Schema for creating a new program (POST request body)."""

    name_en = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        metadata={
            "description": "Program name in English",
            "example": "Medical Assisting Certificate"
        }
    )
    name_es = fields.Str(
        metadata={
            "description": "Program name in Spanish (optional)",
            "example": "Certificado de Asistente Medico"
        }
    )
    credential_level = fields.Str(
        required=True,
        validate=validate.OneOf(["diploma", "certificate", "associate", "bachelor", "master", "doctoral"]),
        metadata={
            "description": "Credential level awarded",
            "example": "certificate"
        }
    )
    modality = fields.Str(
        load_default="on_ground",
        validate=validate.OneOf(["on_ground", "online", "hybrid", "mixed"]),
        metadata={
            "description": "Delivery modality",
            "example": "on_ground"
        }
    )
    duration_months = fields.Int(
        load_default=0,
        validate=validate.Range(min=0, max=120),
        metadata={
            "description": "Program duration in months",
            "example": 12
        }
    )
    total_credits = fields.Int(
        load_default=0,
        validate=validate.Range(min=0, max=500),
        metadata={
            "description": "Total credit hours",
            "example": 45
        }
    )
    total_cost = fields.Float(
        load_default=0.0,
        validate=validate.Range(min=0),
        metadata={
            "description": "Total program cost in USD",
            "example": 15000.00
        }
    )
    licensure_required = fields.Bool(
        load_default=False,
        metadata={
            "description": "Whether professional licensure is required",
            "example": True
        }
    )
    licensure_exam = fields.Str(
        metadata={
            "description": "Licensure exam name (if licensure_required)",
            "example": "CMA (AAMA) Exam"
        }
    )
    professional_body = fields.Str(
        metadata={
            "description": "Professional licensing body",
            "example": "AAMA"
        }
    )


class ProgramSchema(ProgramCreateSchema):
    """Full program schema (includes server-generated fields)."""

    id = fields.Str(
        dump_only=True,
        metadata={
            "description": "Server-generated program ID",
            "example": "prog_xyz789abc123"
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
