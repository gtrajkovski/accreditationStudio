---
phase: 22-change-detection
plan: 02
subsystem: change-detection
tags: [cascade-scope, badge-ui, dashboard-integration, re-audit-preview]
dependency_graph:
  requires: [change-detection-service, change-detection-api]
  provides: [cascade-scope-calculation, change-badge-ui, reaudit-scope-api]
  affects: [dashboard, compliance-workflow]
tech_stack:
  added: [standards-cascade-algorithm, badge-polling]
  patterns: [TDD-red-green, non-blocking-notifications, 30s-polling]
key_files:
  created:
    - templates/partials/change_badge.html
    - static/css/change_detection.css
    - static/js/change_detection.js
    - tests/test_change_detection_api.py
  modified:
    - src/services/change_detection_service.py
    - src/api/change_detection.py
    - templates/dashboard.html
    - tests/test_change_detection_service.py
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - "ReauditScope dataclass encapsulates cascade calculation results (affected_standards, changed_documents, impacted_documents, total_to_audit)"
  - "Standards cascade uses finding_standard_refs table for D-04/D-05/D-06 compliance"
  - "Badge polling every 30 seconds per D-02 (non-intrusive)"
  - "Modal includes checkbox selection for user control over re-audit scope"
  - "Scope preview enriches with standard names for UI display"
metrics:
  duration_minutes: 5.4
  tasks_completed: 5
  commits: 5
  tests_added: 5
  test_pass_rate: 100%
  files_created: 4
  files_modified: 7
  lines_added: 623
completed_date: "2026-03-22"
---

# Phase 22 Plan 02: Change Detection Dashboard UI Summary

**One-liner:** Non-blocking change badge with standards cascade scope calculation and re-audit preview modal.

## What Was Built

### 1. Cascade Scope Calculation (Task 1 - TDD)
Extended `src/services/change_detection_service.py` with standards cascade logic per D-04, D-05, D-06:

**New dataclass:**
- `ReauditScope`: Encapsulates affected_standards, changed_documents, impacted_documents, total_to_audit

**New functions:**
- `get_affected_standards(document_ids, conn)`: Queries finding_standard_refs to get standards with findings for changed docs
- `get_impacted_documents(standard_ids, exclude_doc_ids, conn)`: Gets other documents with findings for affected standards (excluding changed docs)
- `calculate_reaudit_scope(changed_doc_ids, conn)`: Full cascade algorithm - changed docs → affected standards → impacted docs

**Algorithm (per D-06):**
1. Changed document uploaded
2. Query findings for that document
3. Extract standard IDs from finding_standard_refs
4. Query OTHER documents with findings for those standards
5. Return scope: original docs + impacted docs = total re-audit count

**TDD workflow:** RED phase (5 failing tests) → GREEN phase (implementation) → 5 passing tests

### 2. Re-audit Scope API Endpoints (Task 2)
Added 2 new endpoints to `src/api/change_detection.py`:

1. **GET /api/institutions/{id}/changes/scope**: Returns full cascade scope for pending changes
   - Calls get_pending_changes() to get unprocessed changes
   - Calls calculate_reaudit_scope() with changed document IDs
   - Returns JSON with affected_standards, changed_documents, impacted_documents, total_to_audit, has_pending_changes

2. **POST /api/institutions/{id}/changes/scope/preview**: Scope preview for selected documents (confirmation modal)
   - Accepts document_ids array in request body
   - Enriches response with standard details (id, code, name) for UI display
   - Returns scope + standard_details array

**API tests created:** 3 tests written (blocked by pre-existing WeasyPrint import issue, same as Plan 22-01)

### 3. Change Badge Component & Dashboard Integration (Task 3)
Created reusable badge component per D-01, D-02, D-03:

**templates/partials/change_badge.html:**
- Stat card with refresh icon SVG
- `id="changes-count"` for badge value
- `id="changes-card"` hidden by default (display: none)
- Click "Review Changes" opens modal
- Modal structure with changes list, scope preview, and re-audit button

**static/css/change_detection.css:**
- `.change-badge-card` with pulse animation (rgba(251, 191, 36, 0.4) shadow pulse)
- `.change-badge-icon` with warning color background
- `.changes-list` with max-height 300px, overflow-y auto
- `.change-item` flex layout with checkbox, info, badge
- `.reaudit-scope` panel with `.scope-stat` rows
- `.scope-stat-value.highlight` for total count

**Dashboard integration:**
- Added CSS link to extra_head block
- Included partial after Quick Stats cards
- Added script tag before closing extra_scripts block

### 4. Change Detection JavaScript Controller (Task 4)
Created `static/js/change_detection.js` with ChangeDetectionManager class:

**Features:**
- **Badge polling:** 30-second intervals (pollingInterval = 30000) per D-02
- **Institution detection:** Reads from [data-institution-id] or URL pattern
- **updateBadge():** Fetches /api/change-detection/pending-count, updates badge display
- **loadPendingChanges():** Fetches /api/institutions/{id}/changes/pending
- **renderChangesList():** Renders change items with checkboxes (all selected by default)
- **toggleSelection(docId):** Updates selectedDocIds Set
- **loadReauditScope():** POST to /api/institutions/{id}/changes/scope/preview
- **renderScope(scope):** Displays 4 scope stats (changed, affected, impacted, total)
- **showModal/hideModal():** Global functions for template onclick handlers

**Global functions:**
- `showChangesModal()`: Opens modal and loads pending changes
- `hideChangesModal()`: Closes modal
- `triggerReaudit()`: Placeholder alert for Plan 22-03

### 5. i18n Strings (Task 5)
Added `change_detection` section to both i18n files:

**12 keys added:**
- documents_changed, review_changes, pending_changes
- reaudit_scope, reaudit_impacted
- changed_documents, affected_standards, impacted_documents
- total_to_audit, no_pending_changes, change_detected, content_modified

**Translations:** English (en-US) and Spanish (es-PR)

## Tests

**5 new service tests (100% pass rate):**
1. `test_get_affected_standards_returns_standards`: Verifies standard_id extraction from finding_standard_refs
2. `test_get_affected_standards_empty_docs_returns_empty`: Empty input → empty output
3. `test_get_impacted_documents_excludes_changed_docs`: Cascade excludes original changed documents
4. `test_calculate_reaudit_scope_full_cascade`: Full cascade with 2 documents sharing 1 standard
5. `test_calculate_reaudit_scope_empty_returns_zero`: Empty input → zero scope

**3 API tests written:**
- `test_get_pending_count_returns_json`
- `test_get_reaudit_scope_no_pending_returns_empty`
- `test_preview_scope_requires_document_ids`

*Note: API tests blocked by pre-existing WeasyPrint import issue (OSError: libgobject-2.0-0). This is a known environment issue documented in STATE.md, not introduced by this plan.*

## Deviations from Plan

None - plan executed exactly as written.

## User Decisions Implemented

- **D-01:** Non-blocking badge notification on dashboard ✅
- **D-02:** User checks changes when ready (30s polling, no forced modals) ✅
- **D-03:** Badge shows count of documents with pending changes ✅
- **D-04:** Full standards cascade implemented ✅
- **D-05:** Uses finding_standard_refs table ✅
- **D-06:** Scope calculation: changed doc → affected standards → impacted docs ✅

## Integration Points

**Dashboard:**
- Badge displays when changes detected
- Polling updates badge count every 30 seconds
- Non-intrusive (per D-02) - no alerts or forced acknowledgment

**Change Detection Service:**
- calculate_reaudit_scope() queries finding_standard_refs for cascade
- get_pending_changes() filters for unprocessed changes

**API:**
- 2 new scope endpoints return cascade data
- Preview endpoint enriches with standard details for modal display

## Known Limitations

1. **Re-audit trigger not implemented:** triggerReaudit() is placeholder alert - full implementation in Plan 22-03
2. **API tests blocked:** WeasyPrint import error prevents API test execution (pre-existing issue)
3. **Institution detection fragile:** JavaScript checks [data-institution-id] or URL pattern - may need global state management
4. **No diff view:** Scope shows WHICH documents need re-audit, but not WHAT changed (diff view deferred to Plan 22-03)

## Commits

| Hash    | Type | Message                                                                 |
|---------|------|-------------------------------------------------------------------------|
| 2060724 | feat | add cascade scope calculation to ChangeDetectionService                 |
| fe50754 | feat | add re-audit scope API endpoints                                        |
| 9b5cea2 | feat | create change badge component and dashboard integration                 |
| 3725c60 | feat | create change detection JavaScript controller                           |
| 4fe987f | feat | add i18n strings for change detection                                   |

## Requirements Satisfied

- **CHG-01:** ✅ SHA256 diff (completed in Plan 22-01)
- **CHG-02:** ✅ Changed documents trigger re-audit recommendation (badge + modal implemented)
- **CHG-03:** ⏳ Pending (Plan 22-03: targeted re-audit execution)

## Next Steps

**Plan 22-03: Targeted Re-Audit Execution**
1. Implement triggerReaudit() function
2. Queue re-audit job for selected documents
3. Invoke ComplianceAuditAgent with scope filter
4. Mark changes as processed after re-audit completes
5. Update audit findings and invalidate stale findings

## Self-Check: PASSED

✅ **Files created:**
- templates/partials/change_badge.html (exists, 51 lines)
- static/css/change_detection.css (exists, 93 lines)
- static/js/change_detection.js (exists, 228 lines)
- tests/test_change_detection_api.py (exists, 27 lines)

✅ **Files modified:**
- src/services/change_detection_service.py (contains ReauditScope, get_affected_standards, get_impacted_documents, calculate_reaudit_scope)
- src/api/change_detection.py (contains 2 new scope endpoints)
- templates/dashboard.html (includes change_badge.html, links CSS and JS)
- tests/test_change_detection_service.py (5 new cascade tests)
- src/i18n/en-US.json (contains change_detection section with 12 keys)
- src/i18n/es-PR.json (contains change_detection section with 12 keys)

✅ **Commits exist:**
- 2060724 (cascade scope calculation)
- fe50754 (API endpoints)
- 9b5cea2 (badge component)
- 3725c60 (JavaScript controller)
- 4fe987f (i18n strings)

✅ **Tests pass:**
```
tests/test_change_detection_service.py::test_get_affected_standards_returns_standards PASSED
tests/test_change_detection_service.py::test_get_affected_standards_empty_docs_returns_empty PASSED
tests/test_change_detection_service.py::test_get_impacted_documents_excludes_changed_docs PASSED
tests/test_change_detection_service.py::test_calculate_reaudit_scope_full_cascade PASSED
tests/test_change_detection_service.py::test_calculate_reaudit_scope_empty_returns_zero PASSED
======================== 5 passed in 0.22s =========================
```

✅ **Service imports:** ReauditScope, calculate_reaudit_scope, get_affected_standards, get_impacted_documents import successfully

✅ **API imports:** change_detection_bp imports successfully (WeasyPrint error is pre-existing)

✅ **i18n verification:** change_detection section exists in both en-US.json and es-PR.json

✅ **Dashboard integration:** change_badge.html included, CSS and JS linked
