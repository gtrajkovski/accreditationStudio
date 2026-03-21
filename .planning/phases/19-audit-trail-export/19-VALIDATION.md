---
phase: 19
slug: audit-trail-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini |
| **Quick run command** | `pytest tests/test_audit_trail_service.py -x` |
| **Full suite command** | `pytest tests/test_audit_trail*.py -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_audit_trail_service.py -x`
- **After every plan wave:** Run `pytest tests/test_audit_trail*.py -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 0 | AUD-01 | unit | `pytest tests/test_audit_trail_service.py::test_query_sessions -v` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | AUD-01 | unit | `pytest tests/test_audit_trail_service.py::test_export_json -v` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | AUD-02 | unit | `pytest tests/test_audit_trail_service.py::test_date_range_filter -v` | ❌ W0 | ⬜ pending |
| 19-01-04 | 01 | 1 | AUD-05 | unit | `pytest tests/test_audit_trail_service.py::test_agent_type_filter -v` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 2 | AUD-01 | integration | `pytest tests/test_audit_trails_api.py::test_export_endpoint -v` | ❌ W0 | ⬜ pending |
| 19-02-02 | 02 | 2 | AUD-03 | integration | `pytest tests/test_audit_trails_api.py::test_package_with_report -v` | ❌ W0 | ⬜ pending |
| 19-02-03 | 02 | 2 | AUD-04 | integration | `pytest tests/test_audit_trails_api.py::test_export_includes_tool_calls -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_audit_trail_service.py` — stubs for AUD-01, AUD-02, AUD-04, AUD-05
- [ ] `tests/test_audit_trails_api.py` — stubs for AUD-01, AUD-03, AUD-04
- [ ] Fixtures: mock workspace with agent_sessions/*.json files

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ZIP file opens in OS | AUD-03 | OS integration | Download ZIP, extract with native tool |
| Date picker UI works | AUD-02 | Browser interaction | Select date range, verify filter applies |
| Filter chips respond | AUD-05 | Browser interaction | Click agent type chip, verify results update |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
