---
phase: 22
slug: change-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini |
| **Quick run command** | `pytest tests/test_change_detection.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_change_detection.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | CHG-01 | unit | `pytest tests/test_change_detection.py::test_sha256_diff -x` | ❌ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | CHG-01 | unit | `pytest tests/test_change_detection.py::test_version_storage -x` | ❌ W0 | ⬜ pending |
| 22-02-01 | 02 | 2 | CHG-02 | unit | `pytest tests/test_change_detection.py::test_reaudit_recommendation -x` | ❌ W0 | ⬜ pending |
| 22-02-02 | 02 | 2 | CHG-02 | integration | `pytest tests/test_change_detection.py::test_badge_notification -x` | ❌ W0 | ⬜ pending |
| 22-03-01 | 03 | 2 | CHG-03 | integration | `pytest tests/test_change_detection.py::test_targeted_reaudit -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_change_detection.py` — stubs for CHG-01, CHG-02, CHG-03
- [ ] Database migration for change_events table

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Badge displays correct count | CHG-02 | Visual rendering | Navigate to dashboard, verify badge shows pending change count |
| Diff view highlights changes | CHG-02 | Visual rendering | Open diff modal, verify green/red highlighting correct |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
