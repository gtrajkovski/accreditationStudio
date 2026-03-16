---
phase: 13-search-enhancement
plan: 01
subsystem: global-search-api
tags: [backend, api, database, search]
dependency_graph:
  requires: [site_visit_service, workspace_manager]
  provides: [global_search_bp, filter_presets_table]
  affects: [app.py, database_schema]
tech_stack:
  added: [filter_presets_table]
  patterns: [blueprint_di, preset_management, search_grouping]
key_files:
  created:
    - src/db/migrations/0026_global_search.sql
    - src/api/global_search.py
  modified:
    - app.py
decisions:
  - Recent searches stored in localStorage (no table needed - see 13-RESEARCH.md)
  - Filter presets use ON CONFLICT pattern for create/update idempotency
  - Search grouping adds grouped_counts to response for enhanced UI
  - Usage tracking increments usage_count and updates last_used_at
metrics:
  duration_minutes: 3
  tasks_completed: 3
  commits: 3
  files_created: 2
  files_modified: 1
  completed_at: "2026-03-16T17:37:49Z"
---

# Phase 13 Plan 01: Global Search API Foundation

**One-liner:** Database schema for filter presets and 6-endpoint global search API extending SiteVisitService

## Overview

Created the backend foundation for enhanced command palette search functionality. Added database migration for filter presets with institution scoping, built a comprehensive API blueprint with 6 endpoints (search, recent, presets CRUD, usage tracking), and registered it in the Flask app. The API extends SiteVisitService for unified multi-source search with grouped result counts.

## Tasks Completed

### Task 1: Create filter presets database migration
**Duration:** ~1 minute
**Commit:** `57d45f0`

Created migration `0026_global_search.sql` with:
- `filter_presets` table with institution FK
- Fields: id, institution_id, name, filters_json, created_at, last_used_at, usage_count
- UNIQUE constraint on (institution_id, name) to prevent duplicates
- CASCADE delete on institution removal
- Index on institution_id for fast lookup

**Files created:**
- `src/db/migrations/0026_global_search.sql`

### Task 2: Create global search API blueprint
**Duration:** ~1 minute
**Commit:** `5ebd368`

Built `global_search_bp` Blueprint with 6 endpoints:
1. `POST /api/institutions/<id>/global-search` - Enhanced search with grouped counts
2. `GET /api/institutions/<id>/global-search/recent` - Last 5 searches for empty state
3. `GET /api/institutions/<id>/global-search/presets` - List presets (ordered by usage, then name)
4. `POST /api/institutions/<id>/global-search/presets` - Create/update preset (idempotent)
5. `DELETE /api/institutions/<id>/global-search/presets/<preset_id>` - Delete preset
6. `POST /api/institutions/<id>/global-search/presets/<preset_id>/use` - Track usage

**Key features:**
- Uses `SiteVisitService.search()` for backend search execution
- Returns `grouped_counts` by source_type for UI display
- ON CONFLICT pattern for idempotent preset creation
- Usage analytics (usage_count, last_used_at)
- Follows blueprint DI pattern with `init_global_search_bp(workspace_manager)`

**Files created:**
- `src/api/global_search.py` (321 lines)

### Task 3: Register blueprint in app.py
**Duration:** ~1 minute
**Commit:** `81bc46b`

Integrated global_search_bp into Flask app:
- Added import: `from src.api.global_search import global_search_bp, init_global_search_bp`
- Initialized with workspace_manager: `init_global_search_bp(workspace_manager)`
- Registered blueprint: `app.register_blueprint(global_search_bp)`

**Verification:** Confirmed routes accessible via `app.url_map`:
- `/api/institutions/<institution_id>/global-search`
- `/api/institutions/<institution_id>/global-search/recent`
- `/api/institutions/<institution_id>/global-search/presets`

**Files modified:**
- `app.py` (3 lines added)

## Deviations from Plan

None - plan executed exactly as written.

## Technical Notes

### Filter Preset JSON Schema
```json
{
  "doc_types": ["policy", "catalog"],
  "compliance_status": ["non_compliant"],
  "date_range": {
    "start": "2025-01-01",
    "end": "2025-12-31"
  }
}
```

### Search Response Enhancement
Standard SiteVisitService response extended with `grouped_counts`:
```json
{
  "results": [...],
  "total": 42,
  "query_time_ms": 123,
  "sources_searched": ["documents", "standards", "findings"],
  "grouped_counts": {
    "document": 25,
    "standard": 12,
    "finding": 5
  }
}
```

### Blueprint Count
Total registered blueprints: 33 (was 32, added global_search_bp)

## Next Steps

This plan provides the backend foundation. Future plans will build:
- **13-02:** Command palette UI with keyboard shortcut (Ctrl+K / Cmd+K)
- **13-03:** Search autocomplete, recent searches display, filter preset UI

## Self-Check: PASSED

**Created files exist:**
```
FOUND: src/db/migrations/0026_global_search.sql
FOUND: src/api/global_search.py
```

**Modified files exist:**
```
FOUND: app.py
```

**Commits exist:**
```
FOUND: 57d45f0
FOUND: 5ebd368
FOUND: 81bc46b
```

**Blueprint registration verified:**
```
Routes accessible: /api/institutions/<institution_id>/global-search (and 5 more)
```
