---
phase: 24
slug: standards-harvester
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.0+ |
| **Config file** | None — existing infrastructure |
| **Quick run command** | `pytest tests/test_standards_harvester.py -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_standards_harvester.py -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | HARV-01 | unit | `pytest tests/test_standards_harvester.py::test_web_harvester -x` | ❌ W0 | ⬜ pending |
| 24-01-02 | 01 | 1 | HARV-01 | unit | `pytest tests/test_standards_harvester.py::test_pdf_harvester -x` | ❌ W0 | ⬜ pending |
| 24-01-03 | 01 | 1 | HARV-02 | unit | `pytest tests/test_standards_harvester.py::test_store_version -x` | ❌ W0 | ⬜ pending |
| 24-01-04 | 01 | 1 | HARV-03 | unit | `pytest tests/test_standards_harvester.py::test_generate_diff -x` | ❌ W0 | ⬜ pending |
| 24-01-05 | 01 | 1 | HARV-01 | integration | `pytest tests/test_standards_harvester.py::test_manual_upload -x` | ❌ W0 | ⬜ pending |
| 24-02-01 | 02 | 2 | HARV-03 | integration | `pytest tests/test_standards_harvester.py::test_api_endpoints -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_standards_harvester.py` — stubs for HARV-01, HARV-02, HARV-03
- [ ] Fixtures for mock HTML responses, sample PDF content
- [ ] Framework install: Already installed (`pytest>=7.4.0` in requirements.txt)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Diff viewer renders correctly in browser | HARV-03 | Visual rendering | Navigate to harvester page, trigger fetch, verify side-by-side diff displays |
| Rate limiting delays web requests | HARV-01 | Timing-dependent | Monitor network requests during web scrape, verify 10+ second delays |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
