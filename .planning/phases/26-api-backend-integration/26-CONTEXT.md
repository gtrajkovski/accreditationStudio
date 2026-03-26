# Phase 26: API & Backend Integration - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the REST API endpoints for contextual search and integrates context detection into all page templates. It does NOT include frontend JavaScript components (that's Phase 27).

</domain>

<decisions>
## Implementation Decisions

### API Endpoint Design
- **D-01:** POST /api/search/contextual accepts body with query, scope, institution_id, program_id, document_id, accreditor_code, sources[], page, per_page, semantic flag
- **D-02:** Response shape: {query, scope, total, items[], facets{}, page, per_page, context{}}
- **D-03:** GET /api/search/contextual/sources?scope=X returns available sources for that scope
- **D-04:** GET /api/search/contextual/suggest returns query suggestions based on context
- **D-05:** Validation: scope requires matching IDs (INSTITUTION requires institution_id, etc.) - return 400 if missing
- **D-06:** Blueprint follows existing pattern: `init_contextual_search_bp(db_conn, vector_store, standards_store, workspace_manager)`

### Template Data Attributes
- **D-07:** Base template includes `data-page`, `data-institution-id`, `data-program-id`, `data-document-id`, `data-accreditor` attributes on main container
- **D-08:** Each page template sets appropriate context via Jinja2 block
- **D-09:** Page types: dashboard, institution, program, document, compliance, standards, evidence, work_queue, portfolio

### i18n Approach
- **D-10:** Add keys to existing src/i18n/en-US.json and es-PR.json
- **D-11:** Use dot notation: search.scope.*, search.source.*, search.results.*, search.placeholder.*
- **D-12:** Follow existing t() helper pattern in templates

### Claude's Discretion
- Error message wording
- Pagination defaults (suggested: page=1, per_page=20)
- Suggestion algorithm details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Search Infrastructure
- `src/services/global_search_service.py` — Existing global search patterns
- `src/api/global_search.py` — Existing search API blueprint
- `src/services/site_visit_service.py` — Unified search across 6 sources

### Blueprint Patterns
- `src/api/institutions.py` — Blueprint DI pattern example
- `src/api/audits.py` — Request validation patterns

### i18n
- `src/i18n/en-US.json` — English strings
- `src/i18n/es-PR.json` — Spanish strings

### Phase 25 Outputs (dependencies)
- `src/core/search_context.py` — SearchContext model (from Phase 25)
- `src/services/contextual_search_service.py` — Service layer (from Phase 25)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Blueprint DI pattern from all existing blueprints
- Request validation patterns from audits.py
- i18n t() helper already in templates

### Established Patterns
- Flask Blueprint with init_*_bp() for dependency injection
- JSON responses with consistent error shapes
- i18n keys use dot notation

### Integration Points
- Register blueprint in app.py
- Import ContextualSearchService from Phase 25
- Templates already have base.html inheritance

</code_context>

<specifics>
## Specific Ideas

User provided detailed implementation spec with exact endpoint signatures and response shapes. Follow the spec.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 26-api-backend-integration*
*Context gathered: 2026-03-26*
