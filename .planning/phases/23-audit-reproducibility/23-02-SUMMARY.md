---
phase: 23-audit-reproducibility
plan: 02
subsystem: compliance-ui
tags: [reproducibility, ui, verification]
dependency_graph:
  requires:
    - 23-01 (API endpoints)
  provides:
    - Reproducibility viewer UI
  affects:
    - User trust in audit results
    - Regulatory defensibility
tech_stack:
  added:
    - Vanilla JavaScript class-based manager pattern
    - Dark theme CSS with verification states
  patterns:
    - Two-tier display (summary/technical toggle)
    - Modal-based finding provenance
    - Client-side JSON export
key_files:
  created:
    - templates/audit_reproducibility.html (183 lines)
    - static/js/audit_reproducibility.js (280 lines)
    - static/css/audit_reproducibility.css (368 lines)
  modified:
    - app.py (added reproducibility route)
    - src/i18n/en-US.json (added 30 reproducibility keys)
    - src/i18n/es-PR.json (added 30 Spanish translations)
decisions:
  - D-01: Two-tier display (summary default, technical toggle) per plan requirements
  - D-02: Client-side JSON export (no server round-trip needed)
  - D-03: Modal for finding provenance to avoid page clutter
  - D-04: Verification banner only shown when verification run (not default)
  - D-05: Theme-aware CSS using existing variable system
metrics:
  duration_minutes: 8.9
  commits: 4
  tasks_completed: 4/4
  test_coverage: Manual verification approved
  lines_added: ~900
  completed_at: "2026-03-22T20:25:26Z"
---

# Phase 23 Plan 02: Reproducibility UI Summary

**One-liner:** Interactive viewer for audit reproducibility bundles with summary/technical toggle and verification status

## What Was Built

Created a dedicated reproducibility viewer page that consumes the API from Plan 01, presenting audit provenance data in a two-tier format:

**Executive Summary (D-06):**
- 5-card grid showing: AI Model, Audit Date, Accreditor, Document Count, Confidence Threshold
- Clean, scannable format for non-technical stakeholders
- Visible by default without scrolling

**Technical Details (D-07):**
- Collapsible section (hidden by default)
- System prompt with SHA-256 hash
- Document hashes table (document ID → hash mapping)
- Tool definitions hash
- Truth index hash
- All data presented in copy-pasteable format

**Verification Banner (D-13):**
- Green "Reproducible" status when current state matches snapshot
- Yellow warning with discrepancy list when mismatches detected
- Only appears after user clicks "Verify" button

**Export Functionality:**
- Download complete bundle as JSON file
- Filename pattern: `audit_{audit_id}_reproducibility.json`
- No server round-trip (client-side blob generation)

**Finding Provenance (future hook):**
- Modal ready for per-finding prompt/response display
- Endpoint exists from Plan 01 but UI binding deferred (no findings list available yet)

## How It Works

1. **Page Load:**
   - JavaScript extracts `institutionId` and `auditId` from template variables
   - Fetches `/api/institutions/{id}/audits/{id}/reproducibility?include_prompts=true`
   - Populates summary cards and technical sections

2. **Technical Toggle:**
   - Button click expands/collapses technical details
   - Icon changes (▶ to ▼)
   - localStorage could be added for persistence (not implemented)

3. **Verification Flow:**
   - User clicks "Verify" button
   - Fetches same endpoint with `?verify=true` flag
   - Backend compares snapshot hashes against current state
   - Frontend displays banner with pass/fail result

4. **Export:**
   - User clicks "Export Bundle"
   - JavaScript creates Blob from `this.data` (full API response)
   - Triggers browser download
   - No server interaction needed

## Key Decisions

**D-01: Summary-First Design**
- Executive summary visible by default
- Technical details collapsed (requires explicit user action)
- Rationale: 80% of users just need to confirm "this audit is defendable" — technical details for the 20% debugging or auditing the system

**D-02: Client-Side Export**
- JSON export handled entirely in browser
- No `/export` endpoint needed
- Rationale: Data already loaded, no server processing required, faster UX

**D-03: Modal for Finding Provenance**
- Per-finding prompts shown in modal overlay
- Not inline (would clutter page)
- Rationale: Findings could number 50+, inline expansion would create massive scroll

**D-04: On-Demand Verification**
- Verification banner hidden until user clicks "Verify"
- Not run automatically on page load
- Rationale: Verification requires backend computation; most users don't need it every time

**D-05: CSS Variable Reuse**
- All colors use existing theme variables (`--bg-card`, `--accent`, `--success`, `--warning`)
- No hardcoded colors
- Rationale: Automatic theme support (dark/light/system preference)

## Deviations from Plan

None. Plan executed exactly as written.

All 4 tasks completed:
1. ✅ Template and route created
2. ✅ JavaScript controller and CSS implemented
3. ✅ i18n strings added (en-US and es-PR)
4. ✅ Human verification approved

## Verification Results

**Human verification performed** (Task 4 checkpoint):

✅ Executive summary displays 5 metrics correctly
✅ Technical details toggle works (expand/collapse)
✅ System prompt and hashes populate from API
✅ Document hashes table renders correctly
✅ Verify button triggers verification check
✅ Verification banner shows pass/fail status
✅ Export button downloads JSON bundle
✅ Spanish localization works (30 keys translated)
✅ Theme-aware styling (dark theme tested)
✅ Responsive design (cards wrap on small screens)

**All verification criteria passed.**

## Requirements Satisfied

**REPRO-02:** ✅ User can view "How this audit was produced"
- Route exists at `/institutions/{id}/audits/{id}/reproducibility`
- Page displays model, date, standards, document versions
- Technical details available via toggle
- Verification status shown on demand

## Known Stubs

None. All UI elements are fully wired to the API from Plan 01.

**Note:** Finding provenance modal is ready but not populated because the findings list UI integration point doesn't exist yet. This is expected — the modal handler (`loadFindingProvenance()`) is complete and will work when a findings list is added in a future plan.

## Integration Points

**Inbound:**
- Consumes `GET /api/institutions/{id}/audits/{id}/reproducibility` (Plan 01)
- Consumes `GET /api/institutions/{id}/audits/{id}/findings/{id}/provenance` (Plan 01, deferred)

**Outbound:**
- None (terminal UI, no downstream dependencies)

**UI Links:**
- Expected to be linked from audit detail views (e.g., compliance page audit cards)
- Link pattern: `<a href="/institutions/{id}/audits/{id}/reproducibility">View Reproducibility</a>`

## Files Changed

**Created:**
- `templates/audit_reproducibility.html` (183 lines)
- `static/js/audit_reproducibility.js` (280 lines)
- `static/css/audit_reproducibility.css` (368 lines)

**Modified:**
- `app.py` (+8 lines: route definition)
- `src/i18n/en-US.json` (+32 lines: reproducibility section)
- `src/i18n/es-PR.json` (+32 lines: Spanish translations)

**Total:** ~900 lines added across 6 files

## Self-Check

✅ **Files exist:**
```bash
[ -f "templates/audit_reproducibility.html" ] && echo "FOUND"
[ -f "static/js/audit_reproducibility.js" ] && echo "FOUND"
[ -f "static/css/audit_reproducibility.css" ] && echo "FOUND"
```

✅ **Commits exist:**
- 60d6977: Template and route
- 6f02e7d: JavaScript and CSS
- 37d2571: i18n strings
- 11fc5b7: Checkpoint approval

✅ **Key links verified:**
- `grep -q 'fetch.*reproducibility' static/js/audit_reproducibility.js` ✅
- `grep -q 'audit_reproducibility.html' app.py` ✅
- `grep -q 'class ReproducibilityManager' static/js/audit_reproducibility.js` ✅

## Self-Check: PASSED

All files created, all commits recorded, all links verified.

## Next Steps

**Immediate (Phase 23 completion):**
- Plan 23 now complete (2/2 plans done)
- Phase 23 verification can proceed

**Future enhancements (post-Phase 23):**
1. Add "View Reproducibility" link to compliance page audit cards
2. Wire finding provenance modal to actual findings list (when available)
3. Add "Compare Snapshots" feature (diff two reproducibility bundles)
4. Add permalink/share capability (copy URL with audit ID)

**Dependency for other work:**
- Standards Harvester (Phase 24) can reference this UI pattern for diff views
- Any future "audit debugging" tools can link here for provenance
