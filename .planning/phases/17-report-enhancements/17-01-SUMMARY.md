---
phase: 17-report-enhancements
plan: 01
subsystem: reports
tags: [templates, customization, CRUD]
dependency_graph:
  requires: [RPT-01, RPT-05]
  provides: [template-crud-api, template-database]
  affects: [reports-api, report-service]
tech_stack:
  added: [report_templates-table]
  patterns: [template-crud, json-sections]
key_files:
  created:
    - src/db/migrations/0029_report_templates.sql
  modified:
    - src/services/report_service.py
    - src/api/reports.py
decisions:
  - Store sections as JSON array for flexibility
  - Enforce single default template per institution via is_default flag
  - Use template ID format "tmpl_XXXXXXXXXXXX" (12-char hex)
metrics:
  duration_minutes: 11.3
  completed_at: "2026-03-21T17:36:01Z"
  tasks_completed: 3
  commits: 2
---

# Phase 17 Plan 01: Report Templates Summary

**One-liner:** Report template CRUD system with JSON section storage and per-institution default enforcement

## What Was Built

### Database Schema (0029_report_templates.sql)
Created `report_templates` table with:
- **Fields:** id, institution_id, name, sections (JSON), description, is_default, timestamps
- **Foreign key:** institution_id → institutions(id)
- **Indexes:**
  - institution_id for fast lookups
  - (institution_id, is_default) composite for default template queries
- **Available sections:** readiness, findings_summary, documents, top_standards, charts

### Service Layer (report_service.py)
Added 5 static methods to `ReportService`:

1. **create_template** - Generates template ID, validates sections list, clears other defaults if is_default=True
2. **list_templates** - Returns templates ordered by is_default DESC, name ASC with JSON parsing
3. **get_template** - Fetches single template with sections deserialized from JSON
4. **update_template** - Dynamic UPDATE query, coordinates is_default flag across templates
5. **delete_template** - Removes template by ID, returns boolean success

All methods follow existing patterns: use `get_conn()`, `json.dumps/loads` for sections, graceful error handling.

### API Endpoints (reports.py)
Added 5 REST endpoints to `reports_bp`:

1. **POST /api/reports/templates** - Create template (validates required fields, returns 201)
2. **GET /api/reports/templates?institution_id=X** - List templates for institution
3. **GET /api/reports/templates/:id** - Get single template (404 if not found)
4. **PATCH /api/reports/templates/:id** - Update template (at least one field required)
5. **DELETE /api/reports/templates/:id** - Delete template (200 or 404)

Consistent error handling:
- 400 for validation errors (missing fields, empty sections)
- 404 for not found
- 500 for server exceptions

## How It Works

### Template Creation Flow
1. Client POSTs to `/api/reports/templates` with institution_id, name, sections array
2. Service validates sections is non-empty list
3. If is_default=True, service clears is_default flag on other templates for that institution
4. Template inserted with sections as JSON string
5. Returns template_id (format: `tmpl_abc123def456`)

### Default Template Enforcement
Only one template per institution can be default:
- On create: if is_default=True → UPDATE other templates SET is_default=0
- On update: if is_default=True → UPDATE other templates SET is_default=0 WHERE id != current

This ensures `ORDER BY is_default DESC` always puts the default first in list results.

### JSON Sections Storage
Sections stored as JSON array string in database:
```json
["readiness", "findings_summary", "charts"]
```

Parsed on retrieval:
- Service methods: `json.loads(row["sections"])`
- Graceful fallback to empty array on parse errors

## Technical Decisions

### Why JSON for sections?
- **Flexibility:** Easy to add new section types without schema migration
- **Ordering:** Array preserves section display order
- **Standard:** JSON widely supported, no custom serialization needed

### Why clear other defaults on update?
- **Data integrity:** Prevents multiple defaults (business rule violation)
- **UI simplicity:** Frontend can always show one "Default" badge
- **Atomic operation:** Happens in same transaction as update

### Why separate delete_template from delete_report?
- **Different lifecycles:** Templates are reusable configurations, reports are generated artifacts
- **No cascading:** Deleting template doesn't delete reports (they're independent)
- **Clean separation:** Templates = configuration, reports = output

## Deviations from Plan

None - plan executed exactly as written.

## Files Modified

### Created
- `src/db/migrations/0029_report_templates.sql` (23 lines) - Database schema

### Modified
- `src/services/report_service.py` (+220 lines) - 5 CRUD methods added
- `src/api/reports.py` (+226 lines) - 5 REST endpoints added

## Commits

1. `c49b529` - feat(17-01): create report templates database schema
2. `9e70cd2` - feat(17-01): add template API endpoints to reports blueprint

## Integration Points

### Consumed By (Future)
- Plan 17-02: Report customization UI will call template endpoints
- Plan 17-03: Report generation will use template sections to filter output

### Depends On
- `reports` table (migration 0026) - For report metadata storage
- `institutions` table - For foreign key relationship
- `ReportService` existing methods - For pattern consistency

## Next Steps

Plan 17-02 will build UI for:
1. Template manager modal (create, edit, delete)
2. Section checkboxes (readiness, findings_summary, etc.)
3. Default template toggle
4. Template selection dropdown on report generation page

## Self-Check: PASSED

Verification:
- ✅ Migration file exists: `src/db/migrations/0029_report_templates.sql`
- ✅ Service has 5 methods: create_template, list_templates, get_template, update_template, delete_template
- ✅ API has 5 endpoints: POST /templates, GET /templates, GET /templates/:id, PATCH /templates/:id, DELETE /templates/:id
- ✅ Commit c49b529 exists in git log
- ✅ Commit 9e70cd2 exists in git log
