---
phase: 26-api-backend-integration
plan: 01
subsystem: api
tags: [api, search, contextual, i18n, integration]
dependency_graph:
  requires: [25-02]
  provides: [contextual-search-api]
  affects: [frontend-search, search-ui]
tech_stack:
  added: []
  patterns: [blueprint-di, rest-api, scope-validation, pagination]
key_files:
  created:
    - src/api/contextual_search.py
    - tests/test_contextual_search_api.py
  modified:
    - src/api/__init__.py
    - app.py
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - "Blueprint uses DI pattern with workspace_manager and standards_store dependencies"
  - "STANDARDS scope returns only standards source, all others return all 8 sources"
  - "Pagination defaults to page=1, per_page=20 with max cap of 100"
  - "SearchContext validates scope requirements (e.g., INSTITUTION requires institution_id)"
  - "Facets built by aggregating source_type counts from results"
  - "Spanish i18n avoids accented characters for JSON safety"
metrics:
  duration_minutes: 14
  tasks_completed: 2
  tests_added: 12
  api_endpoints_added: 3
  i18n_keys_added: 40
  completed_at: "2026-03-26T19:35:24Z"
---

# Phase 26 Plan 01: Contextual Search API Blueprint Summary

**One-liner:** REST API blueprint with POST search, GET sources, GET suggest endpoints plus i18n strings for 6 scopes and 8 sources.

## What Was Built

Created the contextual search API blueprint (`src/api/contextual_search.py`) with three endpoints that expose the ContextualSearchService from Phase 25 via REST API. Added comprehensive i18n support for search UI in both English and Spanish.

### API Endpoints (3 total)

**1. POST /api/search/contextual**
- Executes context-aware search across configured sources
- Validates scope requirements (INSTITUTION requires institution_id, PROGRAM requires both institution_id and program_id, etc.)
- Maps accreditor_code to accreditor_id via standards_store
- Returns JSON with query, scope, total, items, facets, page, per_page, context
- Supports pagination (default page=1, per_page=20, max 100)
- Builds facets by counting source_type occurrences

**2. GET /api/search/contextual/sources**
- Returns available search sources for a given scope
- STANDARDS scope: returns ["standards"] only
- All other scopes: returns all 8 sources
- Validates scope parameter (400 if invalid or missing)

**3. GET /api/search/contextual/suggest**
- Returns query suggestions based on search history
- Queries site_visit_searches table
- Supports optional prefix filtering
- Groups by query and orders by count DESC

### i18n Strings (40 keys total)

Added `search` section to both `src/i18n/en-US.json` and `src/i18n/es-PR.json`:

**search.scope (6 keys):**
- global, institution, program, document, standards, compliance

**search.source (8 keys):**
- documents, document_text, standards, findings, evidence, knowledge_graph, truth_index, agent_sessions

**search.results (4 keys):**
- showing, no_results, search_error, facet_count

**search.placeholder (6 keys):**
- Scope-specific search placeholders for each scope level

Spanish translations avoid accented characters (e.g., "Institucion" not "Institución") for JSON safety.

### Tests

Created `tests/test_contextual_search_api.py` with 12 tests (all passing):
- 5 tests for POST /api/search/contextual (validation, pagination, faceting)
- 5 tests for GET /sources (scope filtering, validation)
- 2 tests for GET /suggest (basic functionality, prefix filtering)

Uses isolated Flask app fixture to avoid full app.py initialization during testing.

### Integration

**Blueprint Registration:**
- Added import in `src/api/__init__.py`
- Registered in `app.py` with `init_contextual_search_bp(workspace_manager, standards_store)`
- Added "Contextual Search" tag to OpenAPI TAGS list

**Dependencies:**
- workspace_manager: for truth_index access
- standards_store: for accreditor_code → accreditor_id mapping

## Deviations from Plan

None - plan executed exactly as written.

## Requirements Completed

- **SRCH-01:** ✅ POST /api/search/contextual endpoint with scope validation
- **SRCH-02:** ✅ GET /api/search/contextual/sources endpoint with scope-specific filtering
- **SRCH-03:** ✅ GET /api/search/contextual/suggest endpoint with query history
- **INT-02:** ✅ i18n strings for 6 scopes and 8 sources in en-US and es-PR

## Known Stubs

None - all endpoints fully functional with real service integration.

## Self-Check: PASSED

**Created files exist:**
- ✅ FOUND: src/api/contextual_search.py (281 lines)
- ✅ FOUND: tests/test_contextual_search_api.py (224 lines)

**Modified files updated:**
- ✅ FOUND: src/api/__init__.py (export added)
- ✅ FOUND: app.py (import, init, register added)
- ✅ FOUND: src/i18n/en-US.json (search section added)
- ✅ FOUND: src/i18n/es-PR.json (search section added)

**Commits exist:**
- ✅ FOUND: 6c5ff0e (Task 1: API blueprint)
- ✅ FOUND: a63a72d (Task 2: i18n strings)

**Tests pass:**
- ✅ All 12 tests in test_contextual_search_api.py pass

**Blueprint registered:**
- ✅ FOUND: contextual_search_bp in app.py registered blueprints
- ✅ FOUND: init_contextual_search_bp call in app.py

## Next Steps

Phase 26 Plan 02 will create the frontend UI components that consume these API endpoints (search bar, scope badge, manual scope cycling, results display).
