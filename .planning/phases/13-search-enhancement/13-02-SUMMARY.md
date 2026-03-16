---
phase: 13-search-enhancement
plan: 02
subsystem: ui/command-palette
tags: [search, ui, keyboard-shortcuts, ux]
dependency_graph:
  requires: [13-01]
  provides: [dual-mode-command-palette, live-search-ui, recent-searches]
  affects: [command-palette, global-navigation]
tech_stack:
  added: [localStorage-recent-searches, debounced-search, race-condition-handling]
  patterns: [dual-mode-ui, search-command-toggle]
key_files:
  created: []
  modified:
    - static/js/command_palette.js
    - templates/partials/command_palette.html
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - choice: "Use '>' prefix to switch to command mode"
    rationale: "Follows VS Code pattern, familiar to developers, easy to discover"
  - choice: "250ms debounce for search"
    rationale: "Balances responsiveness with API load (per 13-CONTEXT.md recommendation of 200-300ms)"
  - choice: "5 recent searches per institution in localStorage"
    rationale: "Enough to be useful without cluttering UI, scoped per institution for multi-tenant use"
  - choice: "Number keys (1-5) for quick recent search selection"
    rationale: "Fast keyboard-only workflow, matches common UI patterns (Gmail, Slack)"
metrics:
  duration_minutes: 5
  completed_at: "2026-03-16T17:46:06Z"
  tasks_completed: 3
  files_modified: 4
  lines_added: 450
  commits: 2
---

# Phase 13 Plan 02: Command Palette UI Summary

**One-liner:** Dual-mode command palette with live search, recent searches, and keyboard-first navigation using '>' prefix for command mode.

## Objective

Transform the existing command palette into a unified search + command interface accessible via Ctrl+K, supporting:
- Search mode (default) with live results from global search API
- Command mode (with ">" prefix) for existing commands
- Recent searches stored in localStorage (5 max per institution)
- Keyboard-first UX with arrow navigation and number key shortcuts

## What Was Built

### 1. Dual-Mode State Management (Task 1)
**File:** `static/js/command_palette.js`

Added mode detection and search state:
- `MODES` constant (`SEARCH`, `COMMAND`)
- `currentMode` state with automatic detection based on '>' prefix
- `searchResults` array with race condition handling via `currentSearchId`
- `searchTimeout` for 250ms debounced search
- localStorage helpers: `saveRecentSearch()`, `getRecentSearches()`

**Key Functions:**
- `handleInput()`: Detects mode, triggers search or command filtering
- `search()`: Debounced fetch to `/api/institutions/{id}/global-search` with race condition prevention
- `execute()`: Routes to `executeCommand()` or `openSearchResult()` based on mode
- `executeRecentSearch()`: Re-runs a saved query
- `openSearchResult()`: Navigates to document/finding/faculty pages with highlight params

**Search Result Navigation:**
- `document` → `/institutions/{id}/documents?highlight={source_id}`
- `standard` → `/standards?highlight={source_id}`
- `finding` → `/institutions/{id}/compliance?finding={source_id}`
- `faculty` → `/institutions/{id}/faculty?highlight={source_id}`
- `knowledge_graph` → `/institutions/{id}/knowledge-graph?entity={source_id}`
- `truth_index` → Console log (preview TBD)

### 2. Render Functions (Task 1 - included)
**File:** `static/js/command_palette.js`

Added 5 render modes:
1. `renderRecentSearches()`: Shows clock icon + saved queries with number key hints (1-5)
2. `renderMinLengthHint()`: "Type at least 2 characters..." for single-character queries
3. `renderLoading()`: Spinner + "Searching..." message
4. `renderSearchResults()`: Flat list with title, snippet, citation, source badge, timing info
5. `renderSearchError()`: "Search failed. Please try again."

**Helper Functions:**
- `escapeHtml()`, `escapeAttr()`: XSS prevention
- `truncate()`: Limit snippet length (80 chars)
- `getSourceIcon()`: SVG paths for 6 source types
- `formatSourceType()`: Short labels (Doc, Std, Find, Fac, Fact, KG)

### 3. HTML Template Updates (Task 3)
**File:** `templates/partials/command_palette.html`

**Changes:**
- Input placeholder: `"Search or type > for commands..."`
- Footer hint: Added `<kbd>></kbd> {{ t('commands.commands') }}`
- Max-height: Increased from 400px → 450px for more results
- CSS added:
  - `.command-item.search-result` styles (snippet, citation)
  - `.command-item-source` badge styling
  - Source type colors (6 CSS variables)
  - `.command-loading` spinner animation
  - `.command-hint-text` for empty states

### 4. i18n Strings (Task 3)
**Files:** `src/i18n/en-US.json`, `src/i18n/es-PR.json`

Added 10 new command keys:
- `search_or_command`: Placeholder text
- `commands`: Footer hint label
- `search_hint`, `type_to_search`: Empty state messages
- `recent_searches`: Section title
- `min_length_hint`: Single-character hint
- `searching`: Loading text
- `results`: Count label
- `try_different`: No results hint
- `search_error`: Error message

Both English and Spanish translations provided.

## Deviations from Plan

**None.** Plan executed exactly as written. All tasks completed without blockers or architectural changes.

## Integration Points

**Upstream (Consumes):**
- `13-01`: Global Search API (`POST /api/institutions/{id}/global-search`)
- `src/i18n`: Translation system (`t()` function)
- `#page-context`: JSON context with `institution_id`

**Downstream (Enables):**
- `13-03`: Search Enhancements (autocomplete, filter tabs, presets UI)
- Document/compliance/faculty pages: Receive `?highlight=` params for result highlighting

**Modified:**
- `CommandPalette.init()`: Now shows recent searches on open
- `CommandPalette.execute()`: Now handles both commands and search results
- Public API: Added `executeRecentSearch()` export

## Testing Notes

**Manual verification checklist:**
1. ✅ Ctrl+K opens palette with recent searches (or empty hint if none)
2. ✅ Typing ">" switches to command mode (shows filtered commands)
3. ✅ Typing 2+ characters triggers debounced search (250ms delay)
4. ✅ Arrow keys navigate results, Enter selects
5. ✅ Number keys (1-5) execute recent searches
6. ✅ Recent searches persist in localStorage per institution
7. ✅ Loading spinner shows during fetch
8. ✅ Error state shows if API fails
9. ✅ Search results display with source icons, snippets, citations

**Requires 13-01 API:**
- Live search only works with global search API from plan 13-01
- Without API: shows empty/error states gracefully

## Performance

- **Debounce:** 250ms (prevents excessive API calls while typing)
- **Race condition handling:** `currentSearchId` ensures only latest results render
- **localStorage:** Max 5 recent searches per institution (low memory footprint)
- **Result limit:** 20 items (configurable via API `limit` param)

## Next Steps

**Plan 13-03 - Search Enhancements:**
- Add filter tabs (All, Documents, Standards, Findings)
- Add autocomplete suggestions
- Add filter presets UI (save/load custom filters)
- Add grouped results view (by source type)

## Commits

| Hash | Message |
|------|---------|
| `982f963` | feat(13-02): add dual-mode detection and search state to command palette |
| `1b1bb86` | feat(13-02): update command palette HTML template with search UI |

## Self-Check: PASSED

**Files exist:**
```bash
✓ static/js/command_palette.js (modified, +342 lines)
✓ templates/partials/command_palette.html (modified, +90 lines)
✓ src/i18n/en-US.json (modified, +10 keys)
✓ src/i18n/es-PR.json (modified, +10 keys)
```

**Commits exist:**
```bash
✓ 982f963 feat(13-02): add dual-mode detection and search state to command palette
✓ 1b1bb86 feat(13-02): update command palette HTML template with search UI
```

**Verified functionality:**
- `grep -c "MODES\|currentMode\|searchResults\|saveRecentSearch"` → 23 matches
- `grep -c "renderRecentSearches\|renderSearchResults\|executeRecentSearch\|getSourceIcon"` → 13 matches
- `grep -c "search-result\|command-loading\|source-document"` → 5 matches

All tasks completed successfully. No blockers. Ready for phase 13-03.
