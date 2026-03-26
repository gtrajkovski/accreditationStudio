---
phase: 27
slug: frontend-visual-testing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | BackstopJS 6.x + Playwright 1.40+ |
| **Config file** | `tests/backstop/backstop.json` (Wave 0 installs) |
| **Quick run command** | `npx backstopjs test --filter="{scenario}"` |
| **Full suite command** | `npx backstopjs test && npx playwright test tests/e2e/` |
| **Estimated runtime** | ~30 seconds (visual) + ~15 seconds (E2E) |

---

## Sampling Rate

- **After every task commit:** Run `npx backstopjs test --filter="{changed component}"`
- **After every plan wave:** Run `npx backstopjs test && npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-00-01 | 00 | 0 | - | setup | `npm run test:visual:setup` | ❌ W0 | ⬜ pending |
| 27-01-01 | 01 | 1 | CTX-02, CTX-03 | visual | `npx backstopjs test --filter="Scope Badge"` | ❌ W0 | ⬜ pending |
| 27-01-02 | 01 | 1 | SRCHUI-01 | visual | `npx backstopjs test --filter="Command Palette"` | ❌ W0 | ⬜ pending |
| 27-02-01 | 02 | 2 | SRCHUI-02 | visual | `npx backstopjs test --filter="Inline Search"` | ❌ W0 | ⬜ pending |
| 27-03-01 | 03 | 3 | SRCHUI-03 | visual | `npx backstopjs test --filter="Results Panel"` | ❌ W0 | ⬜ pending |
| 27-04-01 | 04 | 4 | SRCHUI-04 | E2E | `npx playwright test keyboard-nav.spec.js` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/backstop/backstop.json` — BackstopJS config with all scenarios
- [ ] `tests/backstop/scripts/simulate_command_palette_open.js` — onReady script for palette
- [ ] `tests/backstop/scripts/simulate_scope_cycle.js` — Tab key cycling simulation
- [ ] `tests/backstop/scripts/simulate_search_results.js` — Results panel with tabs
- [ ] `tests/e2e/keyboard-nav.spec.js` — Playwright test for keyboard shortcuts (SRCHUI-04)
- [ ] `npm install --save-dev backstopjs @playwright/test` — framework install

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Screen reader announces scope changes | CTX-02 | NVDA/VoiceOver testing | 1. Enable screen reader 2. Open palette 3. Press Tab 4. Verify scope announced |
| Focus visible on keyboard navigation | SRCHUI-04 | Visual focus ring inspection | 1. Tab through results 2. Verify focus ring visible on each item |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
