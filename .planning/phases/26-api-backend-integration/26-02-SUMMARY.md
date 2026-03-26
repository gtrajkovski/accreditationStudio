---
phase: 26-api-backend-integration
plan: 02
subsystem: frontend-integration
tags: [templates, data-attributes, context-detection]
dependency_graph:
  requires: []
  provides: [template-data-attributes]
  affects: [contextual-search-frontend]
tech_stack:
  added: []
  patterns: [jinja2-blocks, data-attributes]
key_files:
  created: []
  modified:
    - templates/base.html
    - templates/institutions/overview.html
    - templates/institutions/documents.html
    - templates/institutions/compliance.html
    - templates/pages/standards_harvester.html
decisions: []
metrics:
  duration_minutes: 4
  completed_date: "2026-03-26"
  tasks_completed: 3
  files_modified: 5
  commits: 3
---

# Phase 26 Plan 02: Template Data Attributes Summary

**One-liner:** Added data-scope attributes to 5 templates using Jinja2 blocks for automatic frontend context detection.

## What Was Built

Added data attributes to template hierarchy to enable automatic context detection by frontend JavaScript without additional API calls:

1. **Base Template (templates/base.html):**
   - Added 5 data attributes to `.main-wrapper` div
   - Implemented as Jinja2 blocks for child template override
   - Default values: `data-page` from endpoint, `data-institution-id` from context processor
   - Empty defaults for program, document, accreditor attributes

2. **Institution Templates:**
   - `overview.html`: Set `data-page="institution"` + institution ID
   - `documents.html`: Set `data-page="institution-documents"` + institution ID
   - `compliance.html`: Set `data-page="institution-compliance"` + institution ID

3. **Standards Template:**
   - `standards_harvester.html`: Set `data-page="standards"` + accreditor code

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| f9f7a45 | feat(26-02): add data attributes to base template | templates/base.html |
| 9a3ae91 | feat(26-02): add data attributes to institution templates | overview.html, documents.html, compliance.html |
| f3b031a | feat(26-02): add data attributes to standards template | standards_harvester.html |

## Technical Implementation

### Data Attribute Schema

```html
<div class="main-wrapper"
     data-page="{{ page_type }}"
     data-institution-id="{{ institution_id }}"
     data-program-id="{{ program_id }}"
     data-document-id="{{ document_id }}"
     data-accreditor="{{ accreditor_code }}">
```

### Jinja2 Block Pattern

Base template defines blocks with sensible defaults:
```jinja2
data-page="{% block data_page %}{{ request.endpoint|replace('_', '-') }}{% endblock %}"
```

Child templates override specific values:
```jinja2
{% block data_page %}institution{% endblock %}
{% block data_institution_id %}{{ institution.id }}{% endblock %}
```

### Page Type Mapping

| Template | data-page Value | Additional Attributes |
|----------|----------------|----------------------|
| overview.html | `institution` | `data-institution-id` |
| documents.html | `institution-documents` | `data-institution-id` |
| compliance.html | `institution-compliance` | `data-institution-id` |
| standards_harvester.html | `standards` | `data-accreditor` |

## Frontend Integration Points

JavaScript can now read context via:
```javascript
const mainWrapper = document.querySelector('.main-wrapper');
const pageType = mainWrapper.dataset.page;
const institutionId = mainWrapper.dataset.institutionId;
const accreditor = mainWrapper.dataset.accreditor;
```

This enables the contextual search component (Phase 27) to automatically scope search results without querying the backend for current context.

## Verification

Manual verification steps:
1. Start server: `python app.py`
2. Visit institution overview: `/institution/{id}`
3. Inspect `.main-wrapper` element
4. Verify `data-page="institution"` and `data-institution-id="{id}"`
5. Browser console: `document.querySelector('.main-wrapper').dataset`

## Requirements Satisfied

- **INT-01:** Template data attributes for automatic context detection ✓

## Known Stubs

None - all data attributes render from existing template variables.

## Self-Check: PASSED

### Files Created
- None (modification-only plan)

### Files Modified
```bash
$ ls -la templates/base.html templates/institutions/overview.html templates/institutions/documents.html templates/institutions/compliance.html templates/pages/standards_harvester.html
# All files exist ✓
```

### Commits Exist
```bash
$ git log --oneline | grep "26-02"
f3b031a feat(26-02): add data attributes to standards template
9a3ae91 feat(26-02): add data attributes to institution templates
f9f7a45 feat(26-02): add data attributes to base template
# All commits found ✓
```

### Data Attributes Present
```bash
$ grep -c "data-page=" templates/base.html
1  # ✓

$ grep -c "block data_page" templates/institutions/overview.html
1  # ✓

$ grep -c "block data_accreditor" templates/pages/standards_harvester.html
1  # ✓
```

All verification checks passed.

## Next Steps

Phase 27 can now:
1. Read data attributes from `.main-wrapper` on page load
2. Automatically determine current scope (Global/Institution/Program/Document/Standards)
3. Filter search results based on detected context
4. Display scope badge in search UI
