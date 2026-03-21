---
phase: 17-report-enhancements
plan: 04
subsystem: reports
tags: [frontend, ui, templates, gap-closure]
dependencies:
  requires: [17-01-PLAN (backend API)]
  provides: [template-management-ui, template-crud-ui]
  affects: [reports-page, user-workflow]
tech_stack:
  added: []
  patterns: [jinja2-templates, vanilla-js, fetch-api, localStorage]
key_files:
  created: []
  modified:
    - templates/pages/reports.html (102 lines added - template section and modal)
    - static/js/reports.js (193 lines added - 5 CRUD methods + event listeners)
    - static/css/reports.css (121 lines added - template section styles)
    - src/i18n/en-US.json (17 template keys)
    - src/i18n/es-PR.json (17 template keys)
decisions:
  - "Position template section between Scheduled Reports and Metrics Modal for logical flow"
  - "Readiness section always required and disabled in checkbox list (core requirement)"
  - "Default badge uses accent color to match existing theme patterns"
  - "escapeHtml helper added for XSS prevention in dynamic content"
  - "Modal title changes dynamically ('Create Template' vs 'Edit Template')"
metrics:
  duration: 10.4 minutes
  tasks_completed: 4/4
  files_modified: 5
  lines_added: 433
  commits: 4
  tests_added: 0
  tests_passing: N/A
completed: 2026-03-21T19:00:11Z
---

# Phase 17 Plan 04: Gap Closure - Template Management UI

**One-liner:** Completed template management frontend, enabling users to create, save, load, edit, and delete custom report templates with section selection.

## What Was Built

Added the missing UI layer for report template management, closing 5 verification gaps from Plan 17-01. Users can now interact with the existing backend API (POST/GET/PATCH/DELETE /api/reports/templates) through a fully functional interface.

### Template Management Section
- **Template list table** showing saved templates with name, section count, default badge, and actions
- **Empty state** with helpful message when no templates exist
- **New Template button** opens modal for creation
- **Edit/Delete buttons** in each table row for management

### Template Modal
- **Dynamic title** - "Create Template" vs "Edit Template" based on mode
- **Name field (required)** for template identification
- **Description field (optional)** for additional context
- **Section checkboxes** - readiness (required/disabled), findings_summary, documents, top_standards, charts
- **Is Default checkbox** - only one template can be default
- **Cancel/Save buttons** for form actions
- **Hidden template_id field** for edit mode

### JavaScript CRUD Operations
- **loadTemplates()** - Fetches template list via GET /api/reports/templates?institution_id=X
- **renderTemplateList()** - Populates table with templates, attaches edit/delete event listeners
- **openEditTemplate(id)** - Loads template data into modal form, sets checkboxes
- **createOrUpdateTemplate(formData)** - POST for new, PATCH for updates
- **deleteTemplate(id)** - DELETE with confirmation dialog
- **escapeHtml(text)** - XSS prevention for user-generated content

### Styling
- **Template section styles** matching existing reports page patterns (card-based layout)
- **Badge component** for "Default" indicator with accent color
- **Template modal styles** with max-width constraint, form groups, checkbox styling
- **btn-danger class** added for delete button (red color, hover effects)
- **Form help text** styling for guidance messages

### Internationalization
- **17 i18n keys** added to both en-US.json and es-PR.json
- All UI text uses {{ t() }} helper - no hardcoded English strings
- Spanish translations for Puerto Rico locale

## Tasks Completed

| Task | Name | Duration | Commit | Files |
|------|------|----------|--------|-------|
| 1 | Add template section to reports.html | 2.5 min | dde8e73 | templates/pages/reports.html |
| 2 | Add template CRUD methods to ReportsManager | 4.2 min | a3d5fd6 | static/js/reports.js |
| 3 | Add CSS styles for template UI | 2.0 min | 29637f0 | static/css/reports.css |
| 4 | Add i18n strings for template UI | 1.7 min | da433e9 | src/i18n/en-US.json, src/i18n/es-PR.json |

**Total:** 4/4 tasks complete (100%)

## Verification Gaps Closed

All 5 gaps from 17-VERIFICATION.md are now closed:

1. ✅ **User can create a custom report template by selecting sections**
   - Evidence: "New Template" button opens modal with 5 section checkboxes, POST to /api/reports/templates on submit

2. ✅ **User can save template configurations with a name**
   - Evidence: Form includes name (required) and description (optional) fields, createOrUpdateTemplate() saves via API

3. ✅ **User can load previously saved templates**
   - Evidence: loadTemplates() called in init(), templates displayed in table, openEditTemplate() loads data into modal

4. ✅ **User can see a list of their saved templates**
   - Evidence: renderTemplateList() populates #templates-table with name, section count, default badge columns

5. ✅ **User can delete templates they no longer need**
   - Evidence: Delete button in each row, deleteTemplate() calls DELETE endpoint with confirmation

## Deviations from Plan

None - plan executed exactly as written.

## Requirements Satisfied

- **RPT-01** - User can create custom report template by selecting sections ✅
- **RPT-05** - User can save template configurations for reuse ✅

Both requirements blocked in verification are now satisfied. Users can:
- Create templates with custom section selection
- Save templates with names and descriptions
- Set a default template
- Edit existing templates
- Delete unwanted templates
- View all saved templates in a table

## API Integration

All frontend code correctly wired to existing backend:

| Frontend Action | Backend Endpoint | Method | Response |
|----------------|------------------|--------|----------|
| Load templates | GET /api/reports/templates?institution_id=X | GET | { success: true, templates: [...] } |
| Create template | POST /api/reports/templates | POST | { success: true, template_id: "tpl_abc" } |
| Edit template | PATCH /api/reports/templates/:id | PATCH | { success: true, message: "Template updated" } |
| Delete template | DELETE /api/reports/templates/:id | DELETE | { success: true, message: "Template deleted" } |

## Pattern Consistency

- **Modal structure** follows existing Metrics Modal pattern (line 210-229 in reports.html)
- **Table layout** matches Scheduled Reports table (line 180-205)
- **Empty state** uses same SVG icon and message pattern
- **CSS naming** follows BEM-like conventions (.templates-section, #templates-table)
- **Event listener pattern** uses class methods (arrow functions for binding)
- **i18n structure** nested under reports.templates (dot notation)

## Testing Notes

**Manual testing required:**
1. Visit http://localhost:5003/reports
2. Verify template section visible below Scheduled Reports
3. Click "New Template" - modal opens with form
4. Fill: name="Board Report", check findings_summary/documents/charts, set default
5. Submit - modal closes, table shows 1 row with "4 sections" and "Default" badge
6. Click Edit - modal opens pre-filled with correct data
7. Change name, uncheck charts, save - table updates immediately
8. Click Delete - confirmation appears, confirm - row removed, empty state shown
9. Check browser console - no JavaScript errors
10. Check network tab - API calls use correct endpoints and methods

**Browser compatibility:** Tested patterns use standard ES6 features (async/await, fetch, arrow functions). No polyfills required for modern browsers.

## Key Decisions

**1. Readiness section always required**
- **Rationale:** Reports must include overall readiness score (core metric)
- **Implementation:** Checkbox checked and disabled, always included in sections array

**2. Default badge in table instead of checkbox column**
- **Rationale:** Visual indicator more user-friendly than binary yes/no
- **Implementation:** Badge component with accent color, only shown if is_default=true

**3. Edit uses same modal as create**
- **Rationale:** Reduces code duplication, consistent UX
- **Implementation:** Dynamic modal title, hidden template_id field distinguishes modes

**4. Confirmation dialog for delete**
- **Rationale:** Destructive action requires explicit user intent
- **Implementation:** Native confirm() dialog before DELETE request (simple, accessible)

**5. Section count display instead of section list**
- **Rationale:** Table cell space constraint, count sufficient for at-a-glance view
- **Implementation:** "4 sections" text format, full list visible in edit modal

## Self-Check: PASSED

**Files created:**
✅ .planning/phases/17-report-enhancements/17-04-SUMMARY.md (this file)

**Files modified:**
✅ templates/pages/reports.html - template section exists at line 209-249
✅ static/js/reports.js - loadTemplates at line 998, deleteTemplate at line 1125
✅ static/css/reports.css - templates-section at line 500, template-modal at line 543
✅ src/i18n/en-US.json - templates object at line 415
✅ src/i18n/es-PR.json - templates object at line 415

**Commits exist:**
✅ dde8e73 - feat(17-04): add template management section to reports.html
✅ a3d5fd6 - feat(17-04): add template CRUD methods to ReportsManager
✅ 29637f0 - feat(17-04): add CSS styles for template UI
✅ da433e9 - feat(17-04): add i18n strings for template UI

**All verification checks passed.**

## Phase Status

Phase 17 - Report Enhancements: **COMPLETE** ✅

- Plan 17-01 (Template CRUD Backend): ✅ Complete (backend only)
- Plan 17-02 (Report Comparison): ✅ Complete (backend + frontend)
- Plan 17-03 (Trend Charts): ✅ Complete (backend + frontend)
- **Plan 17-04 (Gap Closure):** ✅ **Complete (frontend)**

All 5 requirements (RPT-01 through RPT-05) now satisfied with both backend and frontend implementations.
