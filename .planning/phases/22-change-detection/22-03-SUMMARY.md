---
phase: 22-change-detection
plan: 03
subsystem: change-detection
tags: [difflib, side-by-side-diff, targeted-reaudit, cascade-scope, ComplianceAuditAgent]

# Dependency graph
requires:
  - phase: 22-01
    provides: SHA256 change detection, change event recording, pending changes API
  - phase: 22-02
    provides: Cascade scope calculation, change badge UI, change modal component
provides:
  - Side-by-side diff viewer with difflib.HtmlDiff
  - Targeted re-audit execution with ComplianceAuditAgent invocation
  - API endpoints for diff viewing, re-audit triggering, and change dismissal
  - Dark theme diff styling (green additions, red removals)
  - Complete change detection flow integration
affects: [compliance-audit, agent-sessions, document-management]

# Tech tracking
tech-stack:
  added: [difflib.HtmlDiff]
  patterns: [diff-generation, agent-invocation-from-service, cascade-scope-filtering]

key-files:
  created:
    - templates/partials/diff_viewer.html
    - static/css/diff_viewer.css
  modified:
    - src/services/change_detection_service.py
    - src/api/change_detection.py
    - static/js/change_detection.js
    - templates/partials/change_badge.html
    - templates/dashboard.html
    - tests/test_change_detection_service.py

key-decisions:
  - "Used Python stdlib difflib.HtmlDiff instead of external diff library (zero dependencies)"
  - "Context mode with 3 lines of context per D-13 (user decision)"
  - "trigger_targeted_reaudit invokes ComplianceAuditAgent directly via AgentRegistry"
  - "Change dismissal allows users to skip re-audit after reviewing diff"
  - "Dark theme CSS overrides difflib HTML table styles for consistency"

patterns-established:
  - "Diff generation: difflib.HtmlDiff with context=True, numlines=3"
  - "Service-to-agent invocation: AgentRegistry.create(COMPLIANCE_AUDIT, session, workspace_manager)"
  - "Cascade scope filtering: calculate_reaudit_scope → trigger_targeted_reaudit → ONLY scope documents audited"

requirements-completed: [CHG-03]

# Metrics
duration: 18min
completed: 2026-03-22
---

# Phase 22 Plan 03: Targeted Re-Audit Execution Summary

**Side-by-side diff viewer with difflib and targeted re-audit via ComplianceAuditAgent with cascade scope filtering**

## Performance

- **Duration:** 18 minutes
- **Started:** 2026-03-22T18:56:45Z
- **Completed:** 2026-03-22T19:15:23Z
- **Tasks:** 6 (5 auto, 1 human-verify)
- **Files modified:** 8
- **Tests added:** 8 (all passing)

## Accomplishments
- Side-by-side diff generation using Python's difflib.HtmlDiff with context mode (3 lines)
- Targeted re-audit execution that invokes ComplianceAuditAgent for cascade scope documents only
- API endpoints for diff viewing (`/diff`), re-audit triggering (`/reaudit`), and change dismissal (`/dismiss`)
- Diff viewer modal component with dark theme CSS (green additions, red removals per D-11)
- JavaScript controller integration with `showDiff()`, `triggerReaudit()`, and `dismissChange()` functions
- CHG-03 requirement verified: targeted re-audit runs ONLY documents in cascade scope (test_cascade_scope_filtering passes)

## Task Commits

Each task was committed atomically with TDD approach:

1. **Task 1: Add diff generation to ChangeDetectionService (TDD)** - `0432638` (test), Implementation in first commit (feat)
2. **Task 2: Add targeted re-audit execution to ChangeDetectionService (TDD)** - `1851613` (test), `88c5e84` (feat)
3. **Task 3: Add diff and re-audit API endpoints** - `d90aa84` (feat)
4. **Task 4: Create diff viewer component and CSS** - `24f26a0` (feat)
5. **Task 5: Add diff and re-audit functions to JavaScript controller** - `62aee52` (feat)
6. **Task 6: Verify complete change detection flow** - Human verification approved

_Note: TDD tasks have test and feat commits (RED → GREEN phases)_

## Files Created/Modified

### Created
- `templates/partials/diff_viewer.html` - Side-by-side diff modal with metadata section and dismiss button
- `static/css/diff_viewer.css` - Dark theme styles with green/red highlighting (150 lines)

### Modified
- `src/services/change_detection_service.py` - Added `generate_diff()`, `get_change_diff()`, `trigger_targeted_reaudit()`, `mark_changes_processed()`, `get_pending_change_ids()`
- `src/api/change_detection.py` - Added 3 endpoints: GET `/diff`, POST `/reaudit`, PATCH `/dismiss`
- `static/js/change_detection.js` - Added `showDiff()`, `hideDiff()`, `dismissChange()`, `triggerReaudit()` methods
- `templates/partials/change_badge.html` - Included diff_viewer.html partial
- `templates/dashboard.html` - Added diff_viewer.css stylesheet
- `tests/test_change_detection_service.py` - Added 8 tests (4 for diff generation, 4 for re-audit execution)

## Decisions Made

1. **difflib.HtmlDiff instead of external library**: Chose Python stdlib for zero dependencies. HtmlDiff provides standard side-by-side diff with context mode built-in.

2. **Context mode with 3 lines**: Per D-13 requirement, show only changed sections plus 3 lines of surrounding context to avoid overwhelming users with large documents.

3. **Service-to-agent invocation pattern**: `trigger_targeted_reaudit()` creates AgentSession and invokes ComplianceAuditAgent via `AgentRegistry.create()` following autopilot_service.py pattern.

4. **Change dismissal option**: Added `/dismiss` endpoint allowing users to mark changes as reviewed without re-auditing (per D-02 non-blocking UX).

5. **Dark theme CSS overrides**: difflib generates HTML with default light theme. Added CSS overrides for dark theme consistency with AccreditAI design.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without blocking issues.

## User Setup Required

None - no external service configuration required.

## Test Results

All 20 tests pass (12 from Plans 01-02, 8 new in Plan 03):

**Diff generation tests (4):**
- `test_generate_diff_returns_html_table` ✅
- `test_generate_diff_empty_old_returns_info_message` ✅
- `test_generate_diff_shows_changes` ✅
- `test_get_change_diff_not_found_returns_error` ✅

**Targeted re-audit tests (4):**
- `test_mark_changes_processed_updates_rows` ✅
- `test_mark_changes_processed_links_session` ✅
- `test_get_pending_change_ids_returns_unprocessed` ✅
- `test_cascade_scope_filtering` ✅ **(CHG-03 critical test)**

**CHG-03 Verification:**
The `test_cascade_scope_filtering` test verifies the core requirement:
- 3 documents exist: doc_test, doc_02, doc_03
- doc_test is changed
- doc_test and doc_02 share standard std_01 (both in cascade scope)
- doc_03 has NO findings for std_01 (OUT OF SCOPE)
- **Result:** Re-audit targets ONLY doc_test and doc_02. doc_03 is NOT audited. ✅

## Next Phase Readiness

Complete change detection feature ready for production:
- ✅ Document upload detects changes via SHA256 (Plan 01)
- ✅ Dashboard badge shows pending change count with 30s polling (Plan 02)
- ✅ User can view side-by-side diff with green/red highlighting (Plan 03)
- ✅ Targeted re-audit runs only cascade scope documents (Plan 03)
- ✅ Changes marked as processed after re-audit (Plan 03)

**Blockers:** None

**Next:** Phase 23 (Audit Reproducibility) can proceed. Change detection provides foundation for tracking which audits were triggered by document changes.

---
*Phase: 22-change-detection*
*Completed: 2026-03-22*
