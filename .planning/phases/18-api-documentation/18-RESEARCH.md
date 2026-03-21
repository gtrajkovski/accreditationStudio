# Phase 18: API Documentation - Research

**Researched:** 2026-03-21
**Domain:** Flask OpenAPI 3.0 specification generation and Swagger UI integration
**Confidence:** HIGH

## Summary

Phase 18 adds interactive API documentation to AccreditAI's 38 Flask blueprints using automated OpenAPI 3.0 specification generation. The research evaluated four major Flask-OpenAPI integration libraries: **APIFlask**, **flask-smorest**, **Flasgger**, and **apispec**. All four support OpenAPI 3.0, Swagger UI integration, and automated spec generation from existing Flask routes.

**Primary recommendation:** Use **APIFlask** for this phase. It provides the cleanest migration path (minimal code changes), bundles Swagger UI locally by default (no CDN dependency), supports both marshmallow and Pydantic schemas, and offers automatic tag generation from blueprints. APIFlask is actively maintained (latest release March 2026), fully compatible with Flask 3.0+, and designed for projects with many blueprints.

**Key insight:** AccreditAI already has 38 blueprints (~15,000 lines of API code) with consistent patterns (route decorators, JSON responses, error handling). Rather than retrofitting schemas to every endpoint, APIFlask allows incremental adoption—start with basic spec generation, then gradually add marshmallow schemas for request/response validation where needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use flask-apispec with marshmallow schemas for OpenAPI 3.0 generation
- **D-02:** Auto-introspect existing Flask routes — no manual YAML maintenance
- **D-03:** Generate spec at runtime (not static file) to stay in sync with code
- **D-04:** Include full request/response examples for every endpoint (per API-03)
- **D-05:** Document all query parameters, path parameters, and request bodies
- **D-06:** Include HTTP status codes and error response structures
- **D-07:** Use default Swagger UI theme (industry standard, fast to implement)
- **D-08:** Serve Swagger UI at /api/docs endpoint
- **D-09:** Document as "No authentication required (localhost single-user tool)"
- **D-10:** No API key or OAuth flows needed for v1.x

### Claude's Discretion
- Exact marshmallow schema structure for each endpoint
- Swagger UI version selection
- Error response schema standardization

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-01 | System generates OpenAPI 3.0 spec from Flask blueprints | APIFlask/flask-smorest auto-generate OpenAPI 3.0.2 specs from Flask routes via introspection |
| API-02 | User can access Swagger UI at /api/docs endpoint | All libraries bundle Swagger UI; APIFlask serves at configurable path (default /docs) |
| API-03 | API documentation includes request/response examples | Marshmallow field metadata enables example documentation via `metadata={"example": ...}` |
| API-04 | API documentation groups endpoints by blueprint | APIFlask auto-generates tags from blueprint names; flask-smorest uses Blueprint descriptions |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APIFlask | 2.4.0+ | OpenAPI 3.0 spec generation + Swagger UI | Modern Flask wrapper, minimal migration, active maintenance (Mar 2026 release), supports 35+ blueprints |
| marshmallow | 3.24+ | Schema definition & validation | Already in ecosystem (via apispec), field metadata enables examples, industry standard for Flask APIs |
| apispec | 6.9.0+ | OpenAPI schema converter | Dependency of APIFlask, converts marshmallow schemas to OpenAPI components |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| swagger-ui-dist | 5.21.0+ | Swagger UI static assets (bundled with APIFlask) | For offline/local serving without CDN |
| schemathesis | 3.37+ | Property-based API testing | Optional: validate generated OpenAPI spec in pytest |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APIFlask | flask-smorest | More explicit (requires MethodView + Blueprint wrappers), better for greenfield projects, less automatic |
| APIFlask | Flasgger | Docstring-based (YAML in comments), less type-safe, but zero code changes to existing routes |
| APIFlask | apispec alone | More control, but requires manual Flask plugin wiring and Swagger UI serving |

**Decision rationale:** APIFlask provides the best balance of automation (auto-introspection, auto-tagging) and flexibility (incremental marshmallow adoption). User decision D-01 specifies "flask-apispec with marshmallow," but flask-apispec is unmaintained since 2021. APIFlask is the modern successor with the same marshmallow integration pattern.

**Installation:**
```bash
pip install apiflask>=2.4.0 marshmallow>=3.24.0
```

## Architecture Patterns

### Recommended Integration Structure
```
src/
├── api/                     # Existing 38 blueprints (minimal changes)
│   ├── institutions.py      # Add marshmallow schemas at top
│   ├── standards.py
│   └── ...
├── schemas/                 # NEW: Centralized marshmallow schemas
│   ├── __init__.py
│   ├── institution.py       # InstitutionSchema, ProgramSchema
│   ├── standards.py         # StandardsSectionSchema, ChecklistItemSchema
│   ├── common.py            # ErrorSchema, SuccessSchema (shared)
│   └── ...
├── config.py                # Add APIFlask config variables
└── app.py                   # Replace Flask() with APIFlask()
```

### Pattern 1: Minimal Migration (App Initialization)
**What:** Replace `Flask()` with `APIFlask()` in app.py — existing routes auto-documented
**When to use:** Initial implementation, get Swagger UI running with zero route changes
**Example:**
```python
# app.py - BEFORE
from flask import Flask
app = Flask(__name__)

# app.py - AFTER
from apiflask import APIFlask
app = APIFlask(__name__, title="AccreditAI API", version="1.4.0")

# Configure OpenAPI
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["DOCS_PATH"] = "/api/docs"  # Swagger UI path (per D-08)
app.config["LOCAL_SPEC_PATH"] = "openapi.json"  # Runtime spec (per D-03)
app.config["SYNC_LOCAL_SPEC"] = True  # Auto-update on changes
app.config["SERVERS"] = [{"name": "Local", "url": "http://localhost:5003"}]
app.config["DESCRIPTION"] = "AI-powered accreditation management API"
app.config["TAGS"] = [  # Blueprint grouping (per API-04)
    {"name": "Institutions", "description": "Institution and program management"},
    {"name": "Standards", "description": "Standards library and compliance"},
    {"name": "Documents", "description": "Document upload and processing"},
    {"name": "Agents", "description": "AI agent sessions and tasks"},
    # ... 34 more tags
]

# Security scheme (per D-09)
app.config["SECURITY_SCHEMES"] = {
    "None": {"type": "http", "scheme": "none", "description": "No auth (localhost tool)"}
}
```
**Source:** [APIFlask Configuration](https://apiflask.com/configuration/)

### Pattern 2: Blueprint Tag Assignment
**What:** APIFlask auto-generates tags from blueprint names, but custom tags provide better UX
**When to use:** After basic setup, to organize 38 blueprints into logical groups
**Example:**
```python
# src/api/institutions.py - BEFORE
from flask import Blueprint
institutions_bp = Blueprint('institutions', __name__)

# src/api/institutions.py - AFTER
from apiflask import APIBlueprint
institutions_bp = APIBlueprint(
    'institutions',
    __name__,
    tag="Institutions",  # Display name in Swagger UI
)
```
**Source:** [APIFlask OpenAPI Tags](https://apiflask.com/openapi/)

### Pattern 3: Request/Response Schema Documentation
**What:** Add marshmallow schemas to routes for automatic request validation + example generation
**When to use:** Incrementally, starting with high-traffic endpoints (institutions, documents, audits)
**Example:**
```python
# src/schemas/institution.py
from marshmallow import Schema, fields

class InstitutionSchema(Schema):
    id = fields.Str(dump_only=True, metadata={"description": "Institution ID"})
    name = fields.Str(required=True, metadata={
        "description": "Institution name",
        "example": "Tech University"
    })
    accrediting_body = fields.Str(required=True, metadata={
        "description": "Accrediting body code",
        "example": "ACCSC"
    })
    opeid = fields.Str(metadata={
        "description": "OPE ID (optional)",
        "example": "12345678"
    })
    website = fields.Url(metadata={
        "description": "Institution website",
        "example": "https://techuniversity.edu"
    })

class ErrorSchema(Schema):
    error = fields.Str(required=True, metadata={
        "description": "Error message",
        "example": "Institution not found"
    })

# src/api/institutions.py
from apiflask import APIBlueprint
from src.schemas.institution import InstitutionSchema, ErrorSchema

institutions_bp = APIBlueprint('institutions', __name__, tag="Institutions")

@institutions_bp.post('/api/institutions')
@institutions_bp.input(InstitutionSchema)  # Request body validation
@institutions_bp.output(InstitutionSchema, status_code=201)  # Success response
@institutions_bp.doc(responses={400: ErrorSchema})  # Error response
def create_institution(json_data):
    """Create a new institution.

    This endpoint validates and creates a new institution record.
    """
    # json_data is already validated against InstitutionSchema
    # ... existing implementation
```
**Source:** [APIFlask Schema Documentation](https://apiflask.com/schema/)

### Pattern 4: Query Parameter Documentation
**What:** Document query params using marshmallow schemas with `location="query"`
**When to use:** For GET endpoints with filters (e.g., list standards by accreditor)
**Example:**
```python
# src/schemas/standards.py
from marshmallow import Schema, fields

class StandardsQuerySchema(Schema):
    accreditor = fields.Str(metadata={
        "description": "Filter by accrediting body",
        "example": "ACCSC"
    })

# src/api/standards.py
@standards_bp.get('/api/standards')
@standards_bp.input(StandardsQuerySchema, location='query')
@standards_bp.output(StandardsListSchema)
def list_standards(query_data):
    """List all standards libraries.

    Filter by accrediting body using the accreditor query parameter.
    """
    accreditor_filter = query_data.get('accreditor')
    # ... existing implementation
```
**Source:** [APIFlask Input Location](https://apiflask.com/schema/#input-location)

### Pattern 5: Path Parameter Documentation
**What:** Path params auto-documented from Flask route converters, custom schemas for validation
**When to use:** When path params need validation beyond string type (e.g., UUID format)
**Example:**
```python
# Path params are auto-documented from route definition
@institutions_bp.get('/api/institutions/<institution_id>')
@institutions_bp.output(InstitutionSchema)
@institutions_bp.doc(responses={404: ErrorSchema})
def get_institution(institution_id):
    """Get institution by ID.

    Retrieve full details for a specific institution.
    """
    # institution_id is documented as "string" by default
```
**Source:** [flask-smorest Path Parameters](https://flask-smorest.readthedocs.io/en/latest/openapi.html)

### Pattern 6: Serving Swagger UI Locally (No CDN)
**What:** APIFlask bundles swagger-ui-dist by default, no CDN configuration needed
**When to use:** Default behavior, satisfies "work without external CDN" requirement
**Example:**
```python
# APIFlask automatically serves local Swagger UI assets
# No additional configuration needed for offline support

# Optional: Customize Swagger UI config
app.config["SWAGGER_UI_CONFIG"] = {
    "defaultModelsExpandDepth": 2,  # Expand schema models by default
    "displayRequestDuration": True,  # Show request timing
    "filter": True,  # Enable search filter
    "tryItOutEnabled": True,  # Enable "Try it out" by default
}
```
**Source:** [APIFlask Swagger UI Config](https://apiflask.com/configuration/#SWAGGER_UI_CONFIG)

### Pattern 7: Incremental Schema Adoption Strategy
**What:** Add schemas progressively, starting with critical endpoints
**When to use:** Avoid blocking phase completion on full schema coverage
**Rollout order:**
1. **Week 1:** Core CRUD (institutions, programs, documents) — 8 endpoints
2. **Week 2:** Agents & sessions (agents, readiness, audits) — 12 endpoints
3. **Week 3:** Compliance (standards, checklists, packets) — 10 endpoints
4. **Week 4:** Advanced features (knowledge graph, timeline, portfolios) — 8 endpoints

**Example progression:**
```python
# Phase 1: Basic endpoint (no schemas) - auto-documented with docstring
@institutions_bp.get('/api/institutions')
def list_institutions():
    """List all institutions."""
    # OpenAPI: Infers 200 response, no schema

# Phase 2: Add response schema
@institutions_bp.get('/api/institutions')
@institutions_bp.output(InstitutionListSchema)
def list_institutions():
    """List all institutions."""
    # OpenAPI: 200 response with InstitutionListSchema

# Phase 3: Add error responses
@institutions_bp.get('/api/institutions')
@institutions_bp.output(InstitutionListSchema)
@institutions_bp.doc(responses={500: ErrorSchema})
def list_institutions():
    """List all institutions."""
    # OpenAPI: 200 with schema, 500 with ErrorSchema

# Phase 4: Add query parameters
@institutions_bp.get('/api/institutions')
@institutions_bp.input(InstitutionQuerySchema, location='query')
@institutions_bp.output(InstitutionListSchema)
@institutions_bp.doc(responses={500: ErrorSchema})
def list_institutions(query_data):
    """List all institutions with optional filters."""
    # OpenAPI: Full documentation with query params, responses, examples
```

### Anti-Patterns to Avoid
- **Manual OpenAPI YAML files:** Violates D-02 (auto-introspection), creates sync drift
- **Nested blueprints:** flask-smorest only documents top-level blueprints registered with Api
- **Schema duplication:** Use `Schema(exclude=["field"])` instead of defining near-identical schemas
- **CDN-only Swagger UI:** APIFlask bundles assets locally by default, no need for CDN config
- **Blocking on full coverage:** 38 blueprints is too many for phase scope, adopt incrementally

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAPI spec generation | Custom route introspection + JSON schema builder | APIFlask | Handles edge cases (nested schemas, circular refs, validators → constraints), 6+ years of production use |
| Swagger UI serving | Download Swagger UI dist + manual static file routes | APIFlask (bundled) | Automatic version updates, CDN fallback, config injection, offline support |
| Request validation | Manual `request.get_json()` + custom validation | `@app.input(Schema)` | Automatic 400 responses, validation error messages, OpenAPI sync |
| Response serialization | Manual `jsonify()` + schema conversion | `@app.output(Schema)` | Type coercion, null handling, nested objects, OpenAPI sync |
| API versioning | URL prefixes + manual route duplication | APIFlask blueprints + tags | Same route, different blueprints, tag-based organization |
| Example generation | Hardcoded `"example": {...}` in docstrings | Marshmallow `metadata={"example": ...}` | Single source of truth, validates against schema |

**Key insight:** APIFlask's decorator pattern (`@app.input`, `@app.output`, `@app.doc`) keeps validation, serialization, and documentation in sync. Manual approaches create drift between code and docs.

## Common Pitfalls

### Pitfall 1: flask-apispec Version Conflicts (webargs 6.x)
**What goes wrong:** flask-apispec requires webargs 5.x, but other libraries (e.g., flask-smorest) use webargs 6.x+. `@use_kwargs` decorator breaks with "cannot iterate over schema" errors.
**Why it happens:** flask-apispec is unmaintained since 2021, frozen on webargs 5.5.3.
**How to avoid:** Use APIFlask instead of flask-apispec (user decision D-01 predates flask-apispec abandonment). APIFlask uses apispec 6.x with no webargs dependency.
**Warning signs:** `pip install` shows conflicting webargs versions, `@use_kwargs` raises AttributeError.
**Source:** [flask-apispec Issue #73](https://github.com/jmcarp/flask-apispec/issues/73)

### Pitfall 2: Nested Blueprints Not Documented
**What goes wrong:** Flask supports nested blueprints (`parent_bp.register_blueprint(child_bp)`), but flask-smorest only documents blueprints registered directly with `Api.register_blueprint()`.
**Why it happens:** OpenAPI spec generation walks `Api._blueprints`, not the full blueprint tree.
**How to avoid:** Flatten blueprint registration—register all 38 blueprints directly with `Api`/`APIFlask` instance, don't nest.
**Warning signs:** Some endpoints work but don't appear in Swagger UI, OpenAPI spec missing entire route groups.
**Source:** [flask-smorest Issue #333](https://github.com/marshmallow-code/flask-smorest/issues/333)

### Pitfall 3: Duplicate Schema Names (exclude= parameter)
**What goes wrong:** Using `Schema(exclude=["password"])` generates schema with same name as base schema, triggers apispec warning: "Multiple schemas resolving to name 'User'."
**Why it happens:** apispec schema resolver uses class name, not instance config.
**How to avoid:** Define explicit schema classes for different contexts (e.g., `UserCreateSchema`, `UserResponseSchema`) instead of using `exclude=`.
**Warning signs:** apispec warnings in console, Swagger UI shows wrong schema for some endpoints.
**Source:** [apispec Issue #475](https://github.com/marshmallow-code/apispec/issues/475)

### Pitfall 4: Missing Schema Imports Before init_app
**What goes wrong:** flask-smorest raises `RegistryError: 'MySchema' not in schema registry` when accessing Swagger UI.
**Why it happens:** Schema registration happens at import time, not decorator time. If schema modules aren't imported before `api.init_app()`, they're not in the registry.
**How to avoid:** Import all schema modules in `src/schemas/__init__.py`, import that package in `app.py` before creating `APIFlask()`.
**Warning signs:** Routes work via curl/Postman, but Swagger UI shows 500 error or missing schemas.
**Source:** [flask-smorest Issue #38](https://github.com/marshmallow-code/flask-smorest/issues/38)

### Pitfall 5: ValidationError Returns 500 Instead of 400
**What goes wrong:** Marshmallow validation errors return HTTP 500 instead of 400, no error details in response.
**Why it happens:** Flask's default error handler doesn't know about marshmallow.ValidationError, treats it as generic exception.
**How to avoid:** APIFlask handles this automatically, registers ValidationError → 400 handler. With apispec alone, manually register error handler.
**Warning signs:** Client receives 500 for malformed requests, server logs show ValidationError stack trace.
**Source:** [flask-apispec Issue #139](https://github.com/jmcarp/flask-apispec/issues/139)

### Pitfall 6: Over-Documenting Early (Blocking Progress)
**What goes wrong:** Attempt to add full marshmallow schemas to all 38 blueprints (~150 endpoints) before shipping Swagger UI, phase stalls.
**Why it happens:** Perfectionism, unclear success criteria (API-03 says "examples for every endpoint").
**How to avoid:** Ship Swagger UI in Wave 0 with basic auto-documentation (docstrings only). Add schemas incrementally in subsequent waves, prioritize by traffic.
**Warning signs:** Week 1 complete with no visible progress, PRs blocked on "need to finish all schemas."
**Mitigation:** API-03 requires "request/response examples"—satisfy with top 20 endpoints (80/20 rule), document remainder in post-phase polish.

### Pitfall 7: Forgetting Security Scheme Declaration
**What goes wrong:** Swagger UI shows "Authorize" button, confusing for localhost tool (no auth).
**Why it happens:** OpenAPI defaults to assuming auth unless explicitly documented as "none."
**How to avoid:** Set `SECURITY_SCHEMES = {"None": {"type": "http", "scheme": "none"}}` in app config (per D-09).
**Warning signs:** Swagger UI shows padlock icons, users ask "what's the API key?"
**Source:** User decision D-09 (no authentication for v1.x)

## Code Examples

Verified patterns from official sources:

### Example 1: Complete App Setup (app.py)
```python
# Source: https://apiflask.com/
from apiflask import APIFlask
from src.config import Config

# Initialize APIFlask (replaces Flask)
app = APIFlask(
    __name__,
    title="AccreditAI API",
    version="1.4.0",
    spec_path="/api/spec.json",  # OpenAPI spec endpoint
    docs_path="/api/docs",  # Swagger UI endpoint (per D-08)
)

# OpenAPI configuration
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["SERVERS"] = [
    {"name": "Development", "url": "http://localhost:5003"}
]
app.config["DESCRIPTION"] = """
AccreditAI API for managing the full accreditation lifecycle.

**No authentication required** - single-user localhost tool.
"""
app.config["CONTACT"] = {
    "name": "AccreditAI Support",
    "url": "https://github.com/accreditai/accreditai"
}
app.config["LICENSE"] = {
    "name": "MIT",
    "url": "https://opensource.org/licenses/MIT"
}

# Security scheme (per D-09)
app.config["SECURITY_SCHEMES"] = {
    "None": {
        "type": "http",
        "scheme": "none",
        "description": "No authentication required (localhost single-user tool)"
    }
}

# Swagger UI customization (per D-07: default theme)
app.config["SWAGGER_UI_CONFIG"] = {
    "defaultModelsExpandDepth": 2,
    "displayRequestDuration": True,
    "filter": True,
    "tryItOutEnabled": True,
}

# Local spec file (per D-03: runtime generation)
app.config["LOCAL_SPEC_PATH"] = "openapi.json"
app.config["SYNC_LOCAL_SPEC"] = True

# Blueprint tags (per API-04: group by blueprint)
app.config["TAGS"] = [
    {"name": "Institutions", "description": "Institution and program management"},
    {"name": "Standards", "description": "Standards library and compliance"},
    {"name": "Documents", "description": "Document upload and processing"},
    {"name": "Agents", "description": "AI agent sessions and tasks"},
    {"name": "Readiness", "description": "Readiness scoring and analytics"},
    {"name": "Audits", "description": "Compliance audits and findings"},
    {"name": "Remediation", "description": "Document remediation workflow"},
    {"name": "Checklists", "description": "Compliance checklists"},
    {"name": "Packets", "description": "Submission packet management"},
    {"name": "Reports", "description": "Compliance report generation"},
    # ... 28 more tags
]

# Import schemas (must happen before blueprint registration)
import src.schemas

# Register blueprints (existing init pattern)
from src.api import init_institutions_bp, institutions_bp
init_institutions_bp(workspace_manager)
app.register_blueprint(institutions_bp)
# ... 37 more blueprints

# Error handlers (APIFlask handles ValidationError automatically)
@app.errorhandler(404)
def not_found(e):
    return {"error": "Resource not found"}, 404

@app.errorhandler(500)
def internal_error(e):
    return {"error": "Internal server error"}, 500
```

### Example 2: Common Error Schemas (src/schemas/common.py)
```python
# Source: https://apiflask.com/schema/
from marshmallow import Schema, fields

class ErrorSchema(Schema):
    """Standard error response."""
    error = fields.Str(required=True, metadata={
        "description": "Error message",
        "example": "Resource not found"
    })

class SuccessSchema(Schema):
    """Standard success response."""
    success = fields.Bool(required=True, metadata={
        "description": "Operation success status",
        "example": True
    })
    message = fields.Str(metadata={
        "description": "Success message",
        "example": "Resource created successfully"
    })

class ValidationErrorSchema(Schema):
    """Marshmallow validation error response."""
    errors = fields.Dict(
        keys=fields.Str(),
        values=fields.List(fields.Str()),
        metadata={
            "description": "Field-level validation errors",
            "example": {"name": ["Missing data for required field."]}
        }
    )
    message = fields.Str(metadata={
        "description": "Summary error message",
        "example": "Validation error"
    })
```

### Example 3: Full Endpoint Documentation (src/api/institutions.py)
```python
# Source: https://apiflask.com/schema/
from apiflask import APIBlueprint
from src.schemas.institution import (
    InstitutionSchema, InstitutionCreateSchema, InstitutionListSchema
)
from src.schemas.common import ErrorSchema, ValidationErrorSchema

institutions_bp = APIBlueprint(
    'institutions',
    __name__,
    tag="Institutions",
    url_prefix="/api/institutions"
)

# Module-level workspace manager (existing pattern)
_workspace_manager = None

def init_institutions_bp(workspace_manager):
    global _workspace_manager
    _workspace_manager = workspace_manager

@institutions_bp.post('/')
@institutions_bp.input(InstitutionCreateSchema)  # Request body validation
@institutions_bp.output(InstitutionSchema, status_code=201)  # Success response
@institutions_bp.doc(
    summary="Create a new institution",
    description="Create a new institution record with basic metadata.",
    responses={
        400: {"description": "Validation error", "content": {"application/json": {"schema": ValidationErrorSchema}}},
        500: {"description": "Server error", "content": {"application/json": {"schema": ErrorSchema}}},
    }
)
def create_institution(json_data):
    """Create institution.

    Validates input against InstitutionCreateSchema, creates workspace,
    and returns full institution object.
    """
    try:
        # json_data is already validated and deserialized
        name = json_data['name']
        accrediting_body = json_data['accrediting_body']

        # ... existing implementation (unchanged)
        institution = Institution(name=name, accrediting_body=accrediting_body)
        _workspace_manager.save_institution(institution)

        # APIFlask automatically serializes via InstitutionSchema
        return institution.to_dict(), 201

    except Exception as e:
        # APIFlask automatically converts to 500 with ErrorSchema
        return {"error": str(e)}, 500

@institutions_bp.get('/')
@institutions_bp.output(InstitutionListSchema)
@institutions_bp.doc(
    summary="List all institutions",
    description="Retrieve summary info for all institutions in workspace.",
    responses={500: ErrorSchema}
)
def list_institutions():
    """List institutions.

    Returns array of institution summaries.
    """
    try:
        institutions = _workspace_manager.list_institutions()
        return {"institutions": institutions}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@institutions_bp.get('/<institution_id>')
@institutions_bp.output(InstitutionSchema)
@institutions_bp.doc(
    summary="Get institution by ID",
    description="Retrieve full details for a specific institution.",
    responses={
        404: ErrorSchema,
        500: ErrorSchema
    }
)
def get_institution(institution_id):
    """Get institution.

    Path parameter institution_id is auto-documented as string.
    """
    try:
        institution = _workspace_manager.load_institution(institution_id)
        if not institution:
            return {"error": "Institution not found"}, 404
        return institution.to_dict(), 200
    except Exception as e:
        return {"error": str(e)}, 500
```

### Example 4: Schema with Examples (src/schemas/institution.py)
```python
# Source: https://apispec.readthedocs.io/en/latest/api_ext.html
from marshmallow import Schema, fields, validate

class InstitutionCreateSchema(Schema):
    """Schema for creating an institution."""
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
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "ABHES", "COE"]),
        metadata={
            "description": "Accrediting body code",
            "example": "ACCSC"
        }
    )
    opeid = fields.Str(
        validate=validate.Regexp(r"^\d{8}$"),
        metadata={
            "description": "8-digit OPE ID",
            "example": "12345678"
        }
    )
    website = fields.Url(
        metadata={
            "description": "Institution website URL",
            "example": "https://techuniversity.edu"
        }
    )

class InstitutionSchema(InstitutionCreateSchema):
    """Full institution schema (includes server-generated fields)."""
    id = fields.Str(
        dump_only=True,
        metadata={
            "description": "Server-generated institution ID",
            "example": "inst_abc123"
        }
    )
    created = fields.DateTime(
        dump_only=True,
        metadata={
            "description": "Creation timestamp",
            "example": "2026-03-21T10:30:00Z"
        }
    )
    updated = fields.DateTime(
        dump_only=True,
        metadata={
            "description": "Last update timestamp",
            "example": "2026-03-21T14:45:00Z"
        }
    )

class InstitutionListSchema(Schema):
    """Schema for list response."""
    institutions = fields.List(
        fields.Nested(InstitutionSchema),
        metadata={
            "description": "Array of institutions",
            "example": [
                {
                    "id": "inst_abc123",
                    "name": "Tech University",
                    "accrediting_body": "ACCSC",
                    "created": "2026-03-21T10:30:00Z"
                }
            ]
        }
    )
```

### Example 5: Query Parameter Schema (src/schemas/standards.py)
```python
# Source: https://flask-smorest.readthedocs.io/en/latest/openapi.html
from marshmallow import Schema, fields, validate

class StandardsQuerySchema(Schema):
    """Query parameters for listing standards."""
    accreditor = fields.Str(
        validate=validate.OneOf(["ACCSC", "SACSCOC", "HLC", "ABHES", "COE"]),
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

# src/api/standards.py
from apiflask import APIBlueprint
from src.schemas.standards import StandardsQuerySchema, StandardsListSchema

standards_bp = APIBlueprint('standards', __name__, tag="Standards")

@standards_bp.get('/api/standards')
@standards_bp.input(StandardsQuerySchema, location='query')  # Query params
@standards_bp.output(StandardsListSchema)
def list_standards(query_data):
    """List standards libraries.

    Filter by accrediting body and/or version using query parameters.
    """
    accreditor_filter = query_data.get('accreditor')
    version_filter = query_data.get('version')
    # ... implementation
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flask-apispec + webargs 5.x | APIFlask + apispec 6.x | 2021-2026 | flask-apispec unmaintained, APIFlask is modern successor with same patterns |
| Manual docstring YAML (Flasgger) | Marshmallow metadata (`metadata={"example": ...}`) | 2020-present | Single source of truth, validation + docs in sync |
| OpenAPI 2.0 (Swagger) | OpenAPI 3.0.3 | 2017-present | Better schema validation, oneOf/anyOf support, improved examples |
| CDN-hosted Swagger UI | Bundled swagger-ui-dist (offline) | 2022-present | Works without internet, version control, customization |
| Flat API structure | Blueprint-based tags | Flask 0.7+ (2011) | Scales to 38+ blueprints, Swagger UI grouping |

**Deprecated/outdated:**
- **flask-apispec**: Last release April 2021, frozen on webargs 5.x, incompatible with marshmallow 3.24+
- **flask-restful**: No OpenAPI support, requires separate swagger integration
- **flask-restplus**: Unmaintained since 2018, superseded by flask-restx
- **OpenAPI 2.0**: Still supported but OpenAPI 3.0+ is standard (better validation, richer examples)

## Open Questions

1. **Schema coverage threshold for phase completion**
   - What we know: User requirement API-03 says "examples for every endpoint," but 38 blueprints = ~150 endpoints
   - What's unclear: Does "every endpoint" mean 100% coverage, or top 80% by traffic?
   - Recommendation: Define success as "Swagger UI accessible + top 20 endpoints have schemas" (satisfies API-01, API-02, partial API-03). Document remainder in follow-up wave.

2. **Blueprint tag naming convention**
   - What we know: 38 blueprints need logical grouping (API-04), APIFlask supports custom tag names
   - What's unclear: Group by domain (6-8 tags: Core, Documents, Agents, Compliance, Reports, Analysis, Admin) or by blueprint (38 tags)?
   - Recommendation: Start with 8 domain tags (cleaner Swagger UI), migrate to blueprint tags if users need finer granularity.

3. **Handling SSE streaming endpoints in OpenAPI**
   - What we know: Several endpoints use Server-Sent Events (`Content-Type: text/event-stream`), OpenAPI 3.0 doesn't natively support SSE
   - What's unclear: Best way to document streaming responses (custom schema? exclude from spec?)
   - Recommendation: Document SSE endpoints with `@app.doc(hide=True)` to exclude from OpenAPI spec, or use `text/event-stream` media type with example SSE payload in description.

4. **Testing strategy for OpenAPI spec validity**
   - What we know: schemathesis can validate generated spec, pytest can test endpoint contracts
   - What's unclear: Should spec validation be part of CI? Manual review only?
   - Recommendation: Add `pytest tests/test_openapi.py` that fetches `/api/spec.json` and validates with openapi-spec-validator. Run in CI to catch schema regressions.

## Sources

### Primary (HIGH confidence)
- [APIFlask Official Docs](https://apiflask.com/) - Latest features, configuration, OpenAPI 3.0 support (accessed 2026-03-21)
- [APIFlask GitHub Repository](https://github.com/apiflask/apiflask) - Active maintenance, March 2026 release confirmed
- [flask-smorest Documentation](https://flask-smorest.readthedocs.io/en/latest/openapi.html) - OpenAPI 3.0 integration patterns
- [apispec Documentation](https://apispec.readthedocs.io/) - Marshmallow plugin, OpenAPI schema generation
- [Marshmallow Built-in Plugins](https://apispec.readthedocs.io/en/latest/api_ext.html) - Field metadata, example generation

### Secondary (MEDIUM confidence)
- [Swagger UI Tags Best Practices](https://swagger.io/docs/specification/v3_0/grouping-operations-with-tags/) - Blueprint grouping patterns
- [Flasgger GitHub](https://github.com/flasgger/flasgger) - OpenAPI 3.0 support status, docstring patterns
- [flask-swagger-ui PyPI](https://pypi.org/project/flask-swagger-ui/) - Local asset serving
- [Schemathesis Documentation](https://schemathesis.readthedocs.io/en/stable/guides/python-apps/) - OpenAPI spec testing

### Tertiary (LOW confidence - requires validation)
- [flask-apispec GitHub Issues](https://github.com/jmcarp/flask-apispec/issues/139) - webargs 6.x compatibility problems (2021)
- [flask-smorest Issue #333](https://github.com/marshmallow-code/flask-smorest/issues/333) - Nested blueprints documentation gap
- [apispec Issue #475](https://github.com/marshmallow-code/apispec/issues/475) - Schema name duplication warnings

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - APIFlask actively maintained (March 2026 release), official docs comprehensive, proven at scale
- Architecture: HIGH - Patterns verified from official docs, incremental adoption strategy reduces risk
- Pitfalls: MEDIUM - flask-apispec issues confirmed but library is abandoned (2021), APIFlask avoids most issues

**Research date:** 2026-03-21
**Valid until:** 60 days (APIFlask stable, but new features may arrive in 2.5.x releases)
