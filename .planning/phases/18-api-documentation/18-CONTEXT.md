# Phase 18: API Documentation - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning
**Source:** Auto-generated (--auto mode)

<domain>
## Phase Boundary

Generate interactive API documentation for all 38 Flask blueprints. Developers can explore endpoints, see request/response examples, and test API calls directly from Swagger UI at /api/docs.

</domain>

<decisions>
## Implementation Decisions

### Spec Generation
- **D-01:** Use APIFlask with marshmallow schemas for OpenAPI 3.0 generation (updated from flask-apispec per research — flask-apispec unmaintained since 2021)
- **D-02:** Auto-introspect existing Flask routes — no manual YAML maintenance
- **D-03:** Generate spec at runtime (not static file) to stay in sync with code

### Documentation Depth
- **D-04:** Include full request/response examples for every endpoint (per API-03)
- **D-05:** Document all query parameters, path parameters, and request bodies
- **D-06:** Include HTTP status codes and error response structures

### UI Customization
- **D-07:** Use default Swagger UI theme (industry standard, fast to implement)
- **D-08:** Serve Swagger UI at /api/docs endpoint

### Authentication Display
- **D-09:** Document as "No authentication required (localhost single-user tool)"
- **D-10:** No API key or OAuth flows needed for v1.x

### Claude's Discretion
- Exact marshmallow schema structure for each endpoint
- Swagger UI version selection
- Error response schema standardization

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Flask Blueprints (38 total)
- `src/api/*.py` — All API blueprint files to document
- `app.py` — Blueprint registration and initialization

### Existing Patterns
- `CLAUDE.md` — Project conventions and blueprint DI pattern

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 38 Flask blueprints with consistent `init_*_bp()` pattern
- Existing route decorators with type hints on some endpoints

### Established Patterns
- Blueprint registration in `app.py`
- Consistent JSON response format: `{success: bool, ...data}`
- Error handling with appropriate status codes (400, 404, 500)

### Integration Points
- `app.py` — Register Swagger UI blueprint
- Static assets for Swagger UI (if bundled)

</code_context>

<specifics>
## Specific Ideas

- Swagger UI should work without external CDN (bundle assets locally)
- Group endpoints by domain (Institutions, Documents, Agents, Compliance, etc.)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-api-documentation*
*Context gathered: 2026-03-21 via auto mode*
