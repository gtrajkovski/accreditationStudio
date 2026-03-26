---
phase: 25-context-model-service-layer
plan: 01
subsystem: search
tags: [context-model, fts5, search-scoping, database]
dependency_graph:
  requires: [phase-13-global-search]
  provides: [search-context-model, fts5-scope-indexes]
  affects: [search-service, search-api, all-pages]
tech_stack:
  added: [SearchScope-enum, SearchContext-dataclass, FTS5-scope-columns]
  patterns: [context-factory, sql-generation, chromadb-filtering]
key_files:
  created:
    - src/db/migrations/0033_contextual_search.sql
    - tests/test_search_context.py
  modified:
    - src/core/models.py
decisions:
  - "SearchScope has 6 levels: GLOBAL, INSTITUTION, PROGRAM, DOCUMENT, STANDARDS, COMPLIANCE"
  - "SearchContext.from_page() uses Flask endpoint naming patterns to infer scope"
  - "FTS5 UNINDEXED columns enable scope filtering without affecting full-text ranking"
  - "site_visit_searches extended with scope tracking columns for contextual search history"
metrics:
  duration_minutes: 7
  tasks_completed: 2
  tests_added: 22
  files_created: 2
  files_modified: 1
  commits: 2
  completed_at: "2026-03-26T17:48:41Z"
---

# Phase 25 Plan 01: Context Model & Service Layer Summary

Context-aware search foundation with 6 scope levels, FTS5 indexes, and automatic scope detection from page endpoints

## One-Line Summary

SearchContext model with 6 scope levels (GLOBAL→INSTITUTION→PROGRAM→DOCUMENT→STANDARDS→COMPLIANCE) and FTS5 migration with UNINDEXED scope columns for context-aware search filtering

## What Was Built

### SearchScope Enum (6 levels)

Added to `src/core/models.py` after existing enums:

```python
class SearchScope(str, Enum):
    """6 scope levels for contextual search."""
    GLOBAL = "global"           # All institutions
    INSTITUTION = "institution" # Single institution, all content
    PROGRAM = "program"         # Single program within institution
    DOCUMENT = "document"       # Single document context
    STANDARDS = "standards"     # Standards library (accreditor-scoped)
    COMPLIANCE = "compliance"   # Compliance findings/audits
```

### SearchContext Dataclass

Full-featured context model with factory method and output methods:

**Factory Method:** `SearchContext.from_page(page_type, context)` maps Flask endpoint names to scope levels
- `dashboard`, `portfolios_*` → GLOBAL
- `institution_program_*` → PROGRAM (with institution_id, program_id)
- `institution_compliance_*`, `institution_audit_*` → COMPLIANCE
- `institution_document_*` → DOCUMENT (with document_id)
- `standards*` → STANDARDS (with accreditor_id)
- Other `institution_*` → INSTITUTION
- Fallback → GLOBAL

**SQL Generation:** `to_sql_conditions()` returns `(sql_string, params_list)` tuple
- GLOBAL → `("", [])`
- INSTITUTION → `("institution_id = ?", ["inst_123"])`
- PROGRAM → `("institution_id = ? AND program_id = ?", ["inst_123", "prog_456"])`

**ChromaDB Filtering:** `to_chromadb_where()` returns metadata dict or None
- GLOBAL → `None`
- INSTITUTION → `{"institution_id": "inst_123"}`
- PROGRAM → `{"institution_id": "inst_123", "program_id": "prog_456"}`

### FTS5 Migration (0033_contextual_search.sql)

**document_text_fts** — Full-text search on document chunks with scope columns:
- Indexed columns: `content`, `section_header`
- UNINDEXED scope columns: `document_id`, `institution_id`, `program_id`
- Populated from `document_chunks` JOIN `documents`
- Uses `porter unicode61` tokenizer

**evidence_fts** — Full-text search on evidence references with scope:
- Indexed columns: `snippet_text`
- UNINDEXED scope columns: `document_id`, `finding_id`, `institution_id`
- Populated from `evidence_refs` JOIN `audit_findings` JOIN `audit_runs`
- 3 triggers (insert/update/delete) keep FTS in sync

**Scope-aware indexes:**
- `idx_standards_accreditor` on `standards(accreditor_id)`
- `idx_findings_institution` on `audit_findings(audit_run_id)`

**Extended site_visit_searches:**
- Added `scope TEXT DEFAULT 'global'`
- Added `program_id TEXT`
- Added `document_id TEXT`
- Added `idx_site_visit_scope` index

### Test Coverage

Created `tests/test_search_context.py` with 22 tests:
- 1 test for SearchScope enum (6 values)
- 10 tests for SearchContext.from_page() factory (all page types)
- 5 tests for to_sql_conditions() (all scope levels)
- 5 tests for to_chromadb_where() (all scope levels)
- 1 test for to_dict() serialization

All tests pass ✓

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

**Why UNINDEXED columns in FTS5?**
- UNINDEXED columns are stored with the row but not tokenized or ranked
- Enables WHERE clause filtering by scope without affecting full-text ranking
- Much faster than JOINing back to source tables after FTS search

**Why extend site_visit_searches?**
- Contextual search history enables analytics: "What are users searching for in PROGRAM scope?"
- Supports future features: scope-specific saved searches, common queries per scope

**Why 6 scope levels?**
- GLOBAL: Portfolio dashboards, cross-institution queries
- INSTITUTION: Single institution's content (most common)
- PROGRAM: Program-specific documents, audits
- DOCUMENT: Document viewer inline search
- STANDARDS: Standards library browsing
- COMPLIANCE: Audit findings, gap analysis

## Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | SearchScope enum + SearchContext dataclass | b9f7604 | src/core/models.py, tests/test_search_context.py |
| 2 | FTS5 migration with scope columns | 485a24b | src/db/migrations/0033_contextual_search.sql |

## Self-Check: PASSED

**Files created:**
- ✓ src/db/migrations/0033_contextual_search.sql (111 lines)
- ✓ tests/test_search_context.py (213 lines)

**Files modified:**
- ✓ src/core/models.py (SearchScope enum at line 198, SearchContext dataclass at line 2606)

**Commits verified:**
- ✓ b9f7604: feat(25-01): add SearchScope enum and SearchContext dataclass
- ✓ 485a24b: feat(25-01): add FTS5 migration for contextual search

**Tests verified:**
- ✓ pytest tests/test_search_context.py: 22 passed in 0.69s

**Migration verified:**
- ✓ Migration 0033 applied successfully
- ✓ document_text_fts table exists with institution_id, program_id UNINDEXED
- ✓ evidence_fts table exists with institution_id UNINDEXED
- ✓ 3 triggers for evidence_fts (insert/update/delete)

## Known Stubs

None — this plan provides foundation models and database schema. No UI components or service layer implementation included.

## Next Steps

Plan 25-02 will implement:
1. ContextualSearchService wrapping existing search infrastructure
2. Service integration with ChromaDB and FTS5 using SearchContext filters
3. Search source registry with 8 sources
4. Result aggregation and ranking across sources

## Notes

**TDD Success:** Task 1 followed full RED-GREEN-REFACTOR cycle. Tests written first, failed correctly, then passed after implementation.

**Performance Consideration:** FTS5 UNINDEXED columns add ~4 bytes per column per row. With document_text_fts populated from document_chunks (typically 10-50 chunks per document), overhead is minimal (<1KB per document).

**Backward Compatibility:** Migration adds new tables and extends existing table. No breaking changes. Existing search functionality continues to work.
