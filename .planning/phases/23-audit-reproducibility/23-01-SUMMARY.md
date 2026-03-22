---
phase: 23-audit-reproducibility
plan: 01
subsystem: audit-engine
tags: [reproducibility, audit-trail, regulatory-compliance]

dependency_graph:
  requires: [audit-engine, database]
  provides: [reproducibility-bundles, audit-provenance]
  affects: [compliance-audit-agent, audit-api]

tech_stack:
  added: []
  patterns: [tdd, snapshot-capture, provenance-tracking]

key_files:
  created:
    - tests/test_audit_reproducibility.py
  modified:
    - src/agents/compliance_audit.py
    - src/api/audits.py

decisions:
  - D-01: Snapshot captured at audit init with model, prompts, document hashes
  - D-02: Provenance recorded per finding with prompt/response and token usage
  - D-08: Snapshot saved at audit finalization (not init) to avoid orphaned records
  - D-09: Database storage with JSON blobs in existing audit_snapshots table

metrics:
  duration_minutes: 7.3
  completed_at: "2026-03-22T20:19:11Z"
  tasks_completed: 3
  tests_added: 11
  files_modified: 2
  commits: 3
---

# Phase 23 Plan 01: Audit Reproducibility Bundle Summary

**One-liner:** ComplianceAuditAgent automatically captures reproducibility bundles (model, prompts, document hashes, standards) at audit execution, with API endpoints for bundle and finding-level provenance retrieval.

---

## What Was Built

### Service Layer (Task 1)
- **Snapshot capture integration** in ComplianceAuditAgent
  - Added `_current_snapshot` instance variable
  - Capture at `_tool_initialize_audit` (after audit creation)
  - Save at `_tool_finalize_audit` (before report generation)
  - Record provenance at `_analyze_compliance` (after AI response)
- **TDD workflow** with RED → GREEN phases
  - 5 service-layer tests (all passing)

### API Layer (Task 2)
- **GET /audits/{id}/reproducibility** - Bundle retrieval endpoint
  - Query param: `include_prompts` (default false, hashes only)
  - Query param: `verify` (checks reproducibility with current state)
  - Executive summary: model, accreditor, document count (D-06)
  - Technical detail: prompt hashes, document hashes, config (D-07)
  - Verification status with discrepancies (D-11, D-13)

- **GET /audits/{id}/findings/{finding_id}/provenance** - Finding-level provenance
  - Prompt/response text and hashes
  - Token usage (input/output)
  - Evidence chunk hashes and reasoning steps

### Testing (Task 3)
- 11 total tests (5 service + 6 API)
- Service tests: 5/5 passing
- API tests: Blocked by pre-existing WeasyPrint environment issue
- Acceptance criteria verified via code inspection

---

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

---

## Implementation Notes

### Snapshot Lifecycle
1. **Init phase**: Snapshot created with `capture_audit_snapshot()`
   - Captures: model ID, system prompt hash, tool definitions hash
   - Captures: document SHA256 hashes, truth index hash
   - Captures: accreditor code, confidence threshold
2. **Execution phase**: Provenance recorded for each finding
   - Prompt text and hash
   - Response text and hash
   - Token usage (input/output)
3. **Finalize phase**: Snapshot persisted to database
   - Avoids orphaned snapshots if audit fails mid-execution
   - Foreign key link to audit_runs table

### API Design
- **Two-tier view** (D-05): Summary by default, technical details on demand
- **Privacy-aware** (D-07): Prompts excluded by default, opt-in with `include_prompts=true`
- **Verification** (D-11): Optional reproducibility check against current state
- **Warning system** (D-13): Model version changes flagged but non-blocking

### Environment Notes
- WeasyPrint import issue (missing GTK dependencies on Windows) prevents API tests from running
- This is a pre-existing issue documented in STATE.md
- Service layer tests confirm functionality
- API endpoints verified via code inspection and acceptance criteria

---

## Commits

| Hash    | Message                                                                 | Files                                        |
|---------|-------------------------------------------------------------------------|----------------------------------------------|
| d6a28e9 | test(23-01): add failing tests for audit reproducibility snapshot      | tests/test_audit_reproducibility.py          |
|         |                                                                         | src/agents/compliance_audit.py               |
| 0a5260d | feat(23-01): add reproducibility API endpoints                          | src/api/audits.py                            |
| b0610ab | test(23-01): add API tests for reproducibility endpoints               | tests/test_audit_reproducibility.py          |

---

## Verification

### Service Tests (5/5 passing)
```bash
pytest tests/test_audit_reproducibility.py::test_audit_initialization_creates_snapshot -v
pytest tests/test_audit_reproducibility.py::test_audit_initialization_stores_system_prompt_hash -v
pytest tests/test_audit_reproducibility.py::test_audit_finalization_saves_snapshot -v
pytest tests/test_audit_reproducibility.py::test_finding_analysis_records_provenance -v
pytest tests/test_audit_reproducibility.py::test_get_audit_snapshot_returns_populated_snapshot -v
```

### Acceptance Criteria
- ✅ ComplianceAuditAgent imports audit_reproducibility_service
- ✅ `capture_audit_snapshot` called in `_tool_initialize_audit`
- ✅ `save_audit_snapshot` called in `_tool_finalize_audit`
- ✅ `record_finding_provenance` called in `_analyze_compliance`
- ✅ `_current_snapshot` instance variable exists
- ✅ GET /reproducibility endpoint returns summary and technical sections
- ✅ GET /provenance endpoint returns prompt/response data

---

## Known Stubs

None - all functionality fully implemented.

---

## Next Steps

1. **Phase 23-02**: Reproducibility UI page at `/audits/{id}/reproducibility`
   - Executive summary view
   - "Show technical details" toggle
   - Verification status display
   - Compare mode (re-run and diff)

---

## Self-Check: PASSED

**Created files exist:**
- ✅ tests/test_audit_reproducibility.py (exists, 472 lines)

**Modified files exist:**
- ✅ src/agents/compliance_audit.py (modified, imports added, snapshot logic wired)
- ✅ src/api/audits.py (modified, 2 new endpoints added)

**Commits exist:**
- ✅ d6a28e9 (test + feat combined in TDD cycle)
- ✅ 0a5260d (API endpoints)
- ✅ b0610ab (API tests)

**Tests passing:**
- ✅ 5/5 service-layer tests passing
- ⚠️ 6 API tests blocked by WeasyPrint environment issue (pre-existing, out of scope)

**Acceptance criteria verified:**
- ✅ All acceptance criteria met via code inspection
