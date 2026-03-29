---
phase: 38
plan: 02
subsystem: ui
tags: [bulk-remediation, ui, wizard, i18n]
dependency_graph:
  requires: [38-01]
  provides: [bulk_remediation_ui]
  affects: [templates, static, i18n]
tech_stack:
  added: []
  patterns: [wizard-flow, sse-progress, batch-approval]
key_files:
  created:
    - templates/institutions/bulk_remediation.html
    - static/js/bulk_remediation.js
    - static/css/bulk_remediation.css
    - tests/test_bulk_remediation_page.py
  modified:
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - Using name_en field for program display (not name)
  - SSE progress streaming via EventSource API
  - Batch approve/reject pattern with checkboxes
metrics:
  duration: 9m
  completed: 2026-03-29T14:41:18Z
---

# Phase 38 Plan 02: Bulk Remediation UI Summary

Wizard-based UI for selecting scope, tracking SSE progress, and batch approving remediations.

## One-Liner

3-step bulk remediation wizard with scope selection, real-time progress tracking, and batch approval interface.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create template | 59a1804 | templates/institutions/bulk_remediation.html |
| 2 | Add JavaScript controller | bc04eb9 | static/js/bulk_remediation.js |
| 3 | Add CSS styles | de8a281 | static/css/bulk_remediation.css |
| 4 | Add i18n translations | 4e58306 | src/i18n/en-US.json, src/i18n/es-PR.json |
| 5 | Add page tests | b9b022e, bed1685 | tests/test_bulk_remediation_page.py |
| 6 | Fix template field | ec9cd40 | templates/institutions/bulk_remediation.html |

## Implementation Details

### Template (bulk_remediation.html)
- Three sections: scope selection, progress, approval
- Scope options: all, by doc_type, by program, by severity
- Preview panel shows document/finding counts before starting
- Progress section hidden until job starts
- Approval section shows completed items with diff view links

### JavaScript (bulk_remediation.js)
- `BulkRemediation` module with init, scope handling, preview updates
- SSE via `EventSource` for real-time progress tracking
- Progress events: start, processing, complete, failed, stopped, done
- Batch approval with approve/reject per item or all

### CSS (bulk_remediation.css)
- Scope option radio buttons with select dropdowns
- Preview panel with stat value/label display
- Progress bar and list with status indicators
- Approval list with approved/rejected visual states
- Responsive layout for mobile

### i18n Translations
- English (en-US): 28 keys in `bulk` namespace
- Spanish (es-PR): 28 keys in `bulk` namespace
- Covers scope options, progress labels, approval buttons

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed program name field**
- **Found during:** Task 5 (tests)
- **Issue:** Template used `prog.name` but model uses `name_en`
- **Fix:** Changed template to use `prog.name_en`
- **Files modified:** templates/institutions/bulk_remediation.html
- **Commit:** ec9cd40

**2. [Rule 1 - Bug] Fixed test patch path**
- **Found during:** Task 5 (tests)
- **Issue:** Tests patched `app.get_conn` but import is inside function
- **Fix:** Changed to patch `src.db.connection.get_conn`
- **Files modified:** tests/test_bulk_remediation_page.py
- **Commit:** bed1685

## Verification

- [x] Template renders with scope options
- [x] JavaScript module loads without errors
- [x] CSS styles applied correctly
- [x] i18n keys added to both locales
- [x] Page route returns 200 for valid institution
- [x] Page route returns 404 for invalid institution
- [x] All 4 tests pass

## Self-Check: PASSED

All created files exist and commits verified.
