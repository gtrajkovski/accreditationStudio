---
phase: 9-03
plan: 9-03-03
subsystem: standards-importer
tags: [api, ui, blueprint, standards]
dependency-graph:
  requires: [9-03-01, 9-03-02]
  provides: [standards-importer-api, standards-importer-ui]
  affects: [standards-library, navigation]
tech-stack:
  added: []
  patterns: [blueprint-di, sse-streaming, tab-ui]
key-files:
  created:
    - src/api/standards_importer_bp.py
    - templates/standards_importer.html
    - static/js/standards-importer.js
    - static/css/standards-importer.css
  modified:
    - app.py
    - templates/base.html
decisions:
  - Use SSE for AI parsing progress streaming
  - 4-tab workflow: Upload -> Preview -> Mapping -> History
  - Gold accent theme consistent with app design
metrics:
  duration: 10m
  completed: 2026-03-27T19:29:35Z
---

# Phase 9-03 Plan 03: API and UI Summary

REST API blueprint and full-featured UI for the Universal Standards Importer with file upload, preview, mapping adjustments, and import history.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 2c89090 | feat | Add standards importer API blueprint |
| 37a62d2 | feat | Wire standards importer blueprint in app.py |
| b0ef5d0 | feat | Add standards importer UI template |
| 200dd73 | feat | Add standards importer JavaScript |
| dfd6faf | feat | Add standards importer CSS |
| bfc80db | feat | Add standards importer nav link |

## Task Completion

### Task 1: Create Standards Importer API Blueprint
**File:** `src/api/standards_importer_bp.py`

REST endpoints for the import workflow:
- `POST /upload` - File upload with validation (PDF, Excel, CSV, text)
- `POST /parse` - Standard parsing without AI
- `POST /parse-ai` - AI-enhanced parsing with SSE streaming
- `POST /validate` - Structure validation without saving
- `POST /import` - Finalize and create StandardsLibrary
- `POST /preview` - Quick preview without database save
- `GET /imports` - List import history with filters
- `GET /imports/<id>` - Get specific import record
- `DELETE /imports/<id>` - Delete import record
- `GET /accreditors` - List available accrediting body codes

Uses `init_standards_importer_bp()` pattern for dependency injection.

### Task 2: Wire Blueprint in app.py
- Imported `standards_importer_bp` and `init_standards_importer_bp`
- Imported `get_import_service` from services
- Initialized import service with workspace_manager and standards_store
- Registered blueprint with app
- Added `/standards-importer` page route

### Task 3: Create Standards Importer UI Template
**File:** `templates/standards_importer.html`

4-tab layout:
1. **Upload** - Drag-drop zone, text input, options (accreditor, name, version, AI toggle)
2. **Preview** - Summary cards, section tree, checklist items, validation issues
3. **Mapping** - Section adjustments table, category mapping table
4. **History** - Import history with status filters

Includes edit modal and success modal.

### Task 4: Create Standards Importer JavaScript
**File:** `static/js/standards-importer.js`

Features:
- File drag-drop and selection handling
- API communication for upload, parse, import
- SSE streaming for AI-enhanced parsing progress
- Tab navigation with state management
- Section tree and checklist preview rendering
- Mapping table with inline editing
- Import history display with filters
- Edit modals for sections and items

### Task 5: Create Standards Importer CSS
**File:** `static/css/standards-importer.css`

Styling:
- Dark theme with gold accent (--accent-primary)
- Drop zone with hover/drag states
- Tab navigation
- Summary cards with success/error states
- Section tree hierarchy display
- Mapping tables with inline inputs
- Status badges for history
- Modal dialogs
- Responsive design for mobile

## Deviations from Plan

### Auto-added (Rule 2)
**Navigation link in base.html**
- Added Standards Importer link in the AI Assistant navigation section
- Ensures discoverability of the new feature
- Uses consistent icon styling

## Verification

All tasks completed:
- [x] POST /upload accepts files and saves to upload directory
- [x] POST /parse returns structured preview with validation
- [x] POST /parse-ai streams SSE progress updates
- [x] POST /validate checks structure without saving
- [x] POST /import creates and saves StandardsLibrary
- [x] GET /imports lists import history
- [x] DELETE /imports/<id> removes records
- [x] Template extends base.html correctly
- [x] All tabs render with proper structure
- [x] JavaScript handles all interactions
- [x] CSS provides consistent styling

## Self-Check: PASSED

Files verified:
- FOUND: src/api/standards_importer_bp.py
- FOUND: templates/standards_importer.html
- FOUND: static/js/standards-importer.js
- FOUND: static/css/standards-importer.css
- FOUND: Commits 2c89090, 37a62d2, b0ef5d0, 200dd73, dfd6faf, bfc80db
