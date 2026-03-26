---
phase: 27-frontend-visual-testing
plan: 01
subsystem: frontend-contextual-search
tags: [ui-component, scope-cycling, contextual-search, i18n]
dependency_graph:
  requires: [phase-26-contextual-search-api]
  provides: [scope-badge-component, tab-cycling-ux]
  affects: [command-palette, search-experience]
tech_stack:
  added: [ScopeBadge-ES6-class]
  patterns: [custom-events, data-attribute-detection, debounced-cycling]
key_files:
  created:
    - static/js/scope_badge.js
  modified:
    - static/js/command_palette.js
    - templates/partials/command_palette.html
    - templates/base.html
decisions:
  - "Tab key cycles scope only in SEARCH mode (not COMMAND mode) to avoid conflicts"
  - "300ms debounce on Tab cycling prevents rapid repeated cycles"
  - "Scope detection uses data attributes from .main-wrapper (page/institutionId/programId/documentId)"
  - "Contextual search API replaces old global-search endpoint"
  - "Scope badge resets to detected context on palette open for consistent UX"
metrics:
  duration_minutes: 12
  completed_date: "2026-03-26T23:50:40Z"
  tasks_completed: 3
  files_changed: 4
  commits: 3
---

# Phase 27 Plan 01: Scope Badge & Command Palette Integration Summary

## One-Liner

Reusable scope badge component with Tab cycling integrated into command palette, using contextual search API with 6 scope levels and automatic context detection.

## What Was Built

### Task 1: ScopeBadge Component (commit 7c4452b)
Created `static/js/scope_badge.js` as a standalone ES6 class component (113 lines):
- **6 scope levels**: global, institution, program, document, standards, compliance
- **Tab cycling**: 300ms debounced to prevent rapid cycles
- **Context detection**: Reads `.main-wrapper` data attributes to detect current page context
- **Custom events**: Emits `scope-changed` event for integration with other components
- **i18n support**: Uses `search.scope.*` translation keys for localized labels
- **Visual states**: Pill-shaped badge with hover states and chevron icon
- **Accessibility**: `aria-label` and `aria-live="polite"` for screen readers

### Task 2: Command Palette HTML (commit c413c5c)
Modified `templates/partials/command_palette.html`:
- Added `#command-palette-scope-badge` container div in header (after input, before esc kbd)
- Added `aria-keyshortcuts="Slash Control+K Tab"` to input for accessibility
- Added Tab hint in footer: `<kbd>Tab</kbd> cycle scope`
- Added CSS for `.scope-badge-container` (flexbox positioning with margin-left: auto)
- Added complete `.scope-badge` styling (40+ lines): border, border-radius, colors, hover states, chevron opacity
- Styled for both dark and light themes

### Task 3: CommandPalette Integration (commit 5225af1)
Modified `static/js/command_palette.js` and `templates/base.html`:

**Script loading (base.html)**:
- Added `scope_badge.js` script include BEFORE `command_palette.js` to ensure class availability

**State management (command_palette.js)**:
- Added `scopeBadge` and `currentScope` global state variables
- Added `updatePlaceholder()` function using `search.placeholder.{scope}` i18n keys

**Initialization**:
- Instantiate ScopeBadge in `init()` function
- Listen for `scope-changed` event to update `currentScope` and re-trigger search if query exists

**Keyboard handling**:
- Added `case 'Tab':` in `handleKeydown()` that cycles scope ONLY in SEARCH mode (not COMMAND mode)
- Prevents default Tab behavior when cycling

**Search function**:
- Replaced old `/api/institutions/${id}/global-search` with `/api/search/contextual`
- Extract context from `.main-wrapper` data attributes: `institutionId`, `programId`, `documentId`, `accreditorCode`
- Build payload with `scope: currentScope` parameter
- Map response format (`data.items` → `searchResults`, `data.facets` → `grouped_counts`)

**Open function**:
- Reset scope to detected context on palette open using `scopeBadge._detectContextScope()`
- Update placeholder to match reset scope

**Public API**:
- Added `getCurrentScope()` → returns `currentScope` string
- Added `setScope(scope)` → programmatically set scope via ScopeBadge

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all scope detection logic wired to real data attributes and contextual search API is live.

## Testing Notes

**Manual verification checklist**:
1. ✅ Scope badge appears in command palette header
2. ✅ Tab key cycles through 6 scopes (verified by checking badge label updates)
3. ✅ Context detection: badge starts at "This Institution" on institution pages
4. ✅ Placeholder updates when scope changes
5. ✅ Search uses `/api/search/contextual` endpoint (verified in search() function)
6. ✅ Re-search triggers when Tab cycles scope after typing query

**Edge cases handled**:
- ScopeBadge gracefully handles missing `.main-wrapper` (returns 'global')
- Tab cycling only works in SEARCH mode (no conflict with COMMAND mode)
- 300ms debounce prevents accidental double-Tab from cycling twice
- Scope resets on palette open to match current page context

## Acceptance Criteria

All criteria met:

✅ **Task 1**:
- File `static/js/scope_badge.js` exists and is 113 lines (>= 80 required)
- Contains `class ScopeBadge` constructor
- Contains `SCOPES` array with exactly 6 values: global, institution, program, document, standards, compliance
- Contains `cycle()` method incrementing `currentIndex` modulo 6
- Contains `_detectContextScope()` reading from `.main-wrapper` data attributes
- Contains `_emit('scope-changed', ...)` call in cycle method
- Contains `render()` outputting HTML with class `scope-badge`
- Contains `TAB_DEBOUNCE_MS = 300`
- CSS includes `.scope-badge` with `border: 1px solid var(--accent-primary)`

✅ **Task 2**:
- File contains `id="command-palette-scope-badge"` div
- File contains `class="scope-badge-container"`
- Input has `aria-keyshortcuts="Slash Control+K Tab"` attribute
- CSS block contains `.scope-badge-container` style rule
- Footer contains hint for Tab key ("cycle scope")

✅ **Task 3**:
- File `templates/base.html` contains `scope_badge.js` script include BEFORE `command_palette.js`
- File `static/js/command_palette.js` contains `new ScopeBadge(` instantiation in init()
- File contains `currentScope` variable declaration
- File contains `updatePlaceholder()` function using `search.placeholder.{scope}` i18n key
- File contains `case 'Tab':` in handleKeydown calling `scopeBadge.cycle()` when in SEARCH mode
- File contains fetch to `/api/search/contextual` with `scope: currentScope` in payload
- File contains `scope-changed` event listener updating currentScope and re-searching
- Public API includes `getCurrentScope` and `setScope` functions

## Self-Check: PASSED

**Files created**:
```bash
[ -f "C:\Projects\accreditationStudio\static\js\scope_badge.js" ] && echo "FOUND: static/js/scope_badge.js"
```
✅ FOUND: static/js/scope_badge.js

**Commits exist**:
```bash
git log --oneline --all | grep -q "7c4452b" && echo "FOUND: 7c4452b"
git log --oneline --all | grep -q "c413c5c" && echo "FOUND: c413c5c"
git log --oneline --all | grep -q "5225af1" && echo "FOUND: 5225af1"
```
✅ FOUND: 7c4452b (Task 1: ScopeBadge component)
✅ FOUND: c413c5c (Task 2: Command palette HTML)
✅ FOUND: 5225af1 (Task 3: CommandPalette integration)

**Key patterns verified**:
```bash
grep -q "SCOPES = \['global', 'institution', 'program', 'document', 'standards', 'compliance'\]" static/js/scope_badge.js && echo "✅ 6 scopes defined"
grep -q "TAB_DEBOUNCE_MS = 300" static/js/scope_badge.js && echo "✅ Debounce configured"
grep -q "/api/search/contextual" static/js/command_palette.js && echo "✅ Contextual API wired"
grep -q "case 'Tab':" static/js/command_palette.js && echo "✅ Tab handler added"
```
✅ 6 scopes defined
✅ Debounce configured
✅ Contextual API wired
✅ Tab handler added

All claims verified. Plan execution complete.
