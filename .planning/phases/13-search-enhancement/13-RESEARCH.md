# Phase 13: Search Enhancement - Research

**Researched:** 2026-03-16
**Domain:** Global search UI, autocomplete, advanced filters
**Confidence:** HIGH

## Summary

Phase 13 extends the existing Site Visit Mode search infrastructure (built in Phase 10) to provide application-wide search capabilities through a unified command palette interface. The existing infrastructure already provides robust unified search across 6 data sources (documents, standards, findings, faculty, truth_index, knowledge_graph) with semantic search via ChromaDB, FTS5 indexes, and citation tracking.

The core challenge is merging two existing keyboard-driven overlays (Command Palette on Ctrl+K and Site Visit Mode on F2) into a single unified interface that supports both quick actions and comprehensive search with live results, recent searches, and saveable filter presets.

**Primary recommendation:** Extend the existing command palette to support search mode with live results preview, reusing Site Visit Service backend and existing filter infrastructure. Use localStorage for recent searches (5 max) and database for saved filter presets.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Unified command palette accessible via Ctrl+K
- Combines search + quick actions (like VS Code)
- Replaces current institution switcher shortcut - merge into command palette
- Default scope: current institution (option to search all)
- Live results appear after 2+ characters typed
- Support command prefix ">" for quick actions:
  - Switch institution
  - Navigate to page
  - Run audit, etc.
- Available filters: document type, compliance status, date range
- Filters persist until user clears them
- Active filters shown as removable chips
- Save filter combinations as named presets (e.g., "Recent Non-Compliant Policies")
- Large overlay panel for full results (similar to Site Visit Mode)
- Results grouped by source type with tabs: All, Documents, Standards, Findings, etc.
- Tab shows count per source type
- Each result shows: title, highlighted snippet, source badge, date, compliance status
- Click result navigates to item page, overlay closes

### Claude's Discretion
- Search bar visual design (header bar vs spotlight overlay - lean toward hybrid)
- Filter UI presentation (inline chips + dropdown vs sidebar)
- Debounce timing for live search (200-300ms range)
- Result card layout details
- Command palette command list and icons

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS | ES6+ | UI logic, event handling | Existing project pattern - no framework |
| localStorage API | Native | Recent searches persistence | Fast, simple, 5-item limit fits well |
| SQLite FTS5 | 3.x | Full-text search | Already in place (0021_site_visit.sql) |
| ChromaDB | Latest | Semantic document search | Already integrated via SearchService |
| Flask + Jinja2 | Latest | Backend API + templates | Existing architecture |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| CSS Grid | Native | Filter chip layout | Responsive filter UI |
| Fetch API | Native | AJAX search requests | Live results without page reload |
| JSON | Native | Filter preset storage | Database storage format |
| D3.js | 7.x | Result count sparklines (optional) | If adding visual trends |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla JS | autoComplete.js library | Library adds 23KB + overhead, existing code pattern works |
| localStorage | IndexedDB | Overkill for 5 recent searches, localStorage simpler |
| Filter chips | Multiselect dropdown | Chips provide better visibility, easier removal |
| Unified palette | Separate search page | Palette keeps user in context, faster workflow |

**Installation:**
```bash
# No new dependencies - using existing infrastructure
# Existing: ChromaDB, Flask, SQLite
```

## Architecture Patterns

### Recommended Project Structure
```
src/api/
├── global_search.py          # NEW: Unified search API (extends site_visit.py)
src/services/
├── site_visit_service.py     # EXISTING: Reuse for search logic
static/js/
├── command_palette.js        # EXTEND: Add search mode
├── site_visit_mode.js        # DEPRECATE: Merge into command_palette.js
templates/partials/
├── command_palette.html      # EXTEND: Add results area, filter chips
├── site_visit_overlay.html   # DEPRECATE: Merge into command_palette
src/db/migrations/
├── 0026_global_search.sql    # NEW: Filter presets table
```

### Pattern 1: Unified Command Palette with Dual Modes

**What:** Single overlay with two modes - command mode (prefix ">") and search mode (default)

**When to use:** When user wants quick actions OR comprehensive search without switching interfaces

**Example:**
```javascript
// Command Palette modes
const MODES = {
  SEARCH: 'search',     // Default: live search with results
  COMMAND: 'command'    // Prefix ">": quick actions only
};

function detectMode(query) {
  if (query.startsWith('>')) {
    return { mode: MODES.COMMAND, cleanQuery: query.slice(1).trim() };
  }
  return { mode: MODES.SEARCH, cleanQuery: query };
}

function handleInput(e) {
  const query = e.target.value;
  const { mode, cleanQuery } = detectMode(query);

  if (mode === MODES.COMMAND) {
    renderCommands(cleanQuery);  // Existing logic
  } else if (cleanQuery.length >= 2) {
    debouncedSearch(cleanQuery);  // NEW: Live search
  }
}
```

**Why this works:** VS Code pattern - familiar to developers, single keyboard shortcut, smooth mode switching.

### Pattern 2: Recent Searches with localStorage

**What:** Store last 5 searches per institution in localStorage, display at top of results before live search

**When to use:** When query is empty or < 2 chars - show recent searches as quick access

**Example:**
```javascript
// Recent searches storage (max 5)
const RECENT_SEARCHES_KEY = 'accreditai_recent_searches';
const MAX_RECENT = 5;

function saveRecentSearch(institutionId, query) {
  const key = `${RECENT_SEARCHES_KEY}_${institutionId}`;
  let recent = JSON.parse(localStorage.getItem(key) || '[]');

  // Remove if exists (move to front)
  recent = recent.filter(r => r !== query);

  // Add to front
  recent.unshift(query);

  // Keep only max
  recent = recent.slice(0, MAX_RECENT);

  localStorage.setItem(key, JSON.stringify(recent));
}

function getRecentSearches(institutionId) {
  const key = `${RECENT_SEARCHES_KEY}_${institutionId}`;
  return JSON.parse(localStorage.getItem(key) || '[]');
}
```

### Pattern 3: Filter Chips with Persistence

**What:** Active filters shown as removable chips, persist in session, saveable as named presets

**Example:**
```javascript
// Filter chip management
class FilterChipManager {
  constructor() {
    this.activeFilters = {
      doc_types: [],
      compliance_status: [],
      date_range: null
    };
  }

  addFilter(type, value) {
    if (type === 'date_range') {
      this.activeFilters.date_range = value;
    } else {
      if (!this.activeFilters[type].includes(value)) {
        this.activeFilters[type].push(value);
      }
    }
    this.render();
    this.persistToSession();
  }

  removeFilter(type, value) {
    if (type === 'date_range') {
      this.activeFilters.date_range = null;
    } else {
      this.activeFilters[type] = this.activeFilters[type].filter(v => v !== value);
    }
    this.render();
    this.persistToSession();
  }

  render() {
    const container = document.getElementById('filter-chips');
    container.innerHTML = '';

    // Render each active filter as a chip
    for (const [type, values] of Object.entries(this.activeFilters)) {
      if (type === 'date_range' && values) {
        container.appendChild(createChip(type, values));
      } else if (Array.isArray(values)) {
        values.forEach(v => container.appendChild(createChip(type, v)));
      }
    }
  }
}

function createChip(type, value) {
  const chip = document.createElement('div');
  chip.className = 'filter-chip';
  chip.innerHTML = `
    <span class="chip-label">${formatFilterLabel(type, value)}</span>
    <button class="chip-remove" onclick="filterManager.removeFilter('${type}', '${value}')">
      <svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor">
        <path d="M18 6L6 18M6 6l12 12"/>
      </svg>
    </button>
  `;
  return chip;
}
```

### Pattern 4: Tabbed Result Sources with Counts

**What:** Results grouped by source type (All, Documents, Standards, Findings, Faculty, Truth Index, Knowledge Graph) with count badges

**Example:**
```javascript
// Result grouping by source
function groupResultsBySource(results) {
  const grouped = {
    all: results,
    documents: [],
    standards: [],
    findings: [],
    faculty: [],
    truth_index: [],
    knowledge_graph: []
  };

  results.forEach(r => {
    if (grouped[r.source_type]) {
      grouped[r.source_type].push(r);
    }
  });

  return grouped;
}

function renderResultTabs(groupedResults) {
  const tabs = document.getElementById('result-tabs');
  tabs.innerHTML = '';

  const sources = [
    { key: 'all', label: 'All' },
    { key: 'documents', label: 'Documents' },
    { key: 'standards', label: 'Standards' },
    { key: 'findings', label: 'Findings' },
    { key: 'faculty', label: 'Faculty' },
    { key: 'truth_index', label: 'Truth Index' },
    { key: 'knowledge_graph', label: 'Knowledge Graph' }
  ];

  sources.forEach(source => {
    const count = groupedResults[source.key].length;
    if (count > 0 || source.key === 'all') {
      const tab = document.createElement('button');
      tab.className = 'result-tab';
      tab.dataset.source = source.key;
      tab.innerHTML = `${source.label} <span class="tab-count">${count}</span>`;
      tab.onclick = () => switchResultTab(source.key);
      tabs.appendChild(tab);
    }
  });
}
```

### Anti-Patterns to Avoid

- **Separate search page:** Breaks user flow, requires navigation - use overlay instead
- **No debouncing:** Hammers API on every keystroke - debounce 200-300ms
- **Heavy autocomplete library:** Existing code pattern handles it well, avoid 23KB+ dependency
- **IndexedDB for 5 items:** Overkill - localStorage is simpler and faster
- **Separate endpoints:** Reuse existing SiteVisitService.search() - already optimized
- **Inline filters everywhere:** Use chips to show active state, dropdown to add new

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic document search | Custom text matching algorithm | ChromaDB (existing) | Handles embeddings, vector similarity, metadata filtering |
| Full-text search | LIKE queries on large text | SQLite FTS5 (existing) | Optimized indexes, ranking, snippet extraction |
| Unified search orchestration | Multiple API calls from frontend | SiteVisitService (existing) | Parallel source search, deduplication, scoring |
| Search history persistence | Custom database table | localStorage for recent + DB for saved | Recent searches are ephemeral, localStorage is faster |
| Filter state management | URL query params | Session state + named presets in DB | Filters persist across searches, presets are reusable |
| Result highlighting | Regex text replacement | Server-side snippet extraction | SiteVisitService._extract_snippet() already handles it |

**Key insight:** Site Visit Mode (Phase 10) already solved the hard problems - unified search, result ranking, citation tracking, FTS5 indexes. This phase is primarily a UI/UX enhancement to make that infrastructure globally accessible.

## Common Pitfalls

### Pitfall 1: Modal Z-Index Conflicts
**What goes wrong:** Command palette opens below other modals, tooltips, or dropdowns
**Why it happens:** CSS z-index values not coordinated across components
**How to avoid:**
- Command palette: `z-index: 9999` (highest)
- Other modals: `z-index: 9998` or lower
- Site visit overlay (deprecated): Remove after merge
**Warning signs:** Palette appears behind institution switcher dropdown, user can't see results

### Pitfall 2: Search Debounce Race Conditions
**What goes wrong:** Fast typing causes results from old queries to overwrite newer results
**Why it happens:** API responses arrive out of order
**How to avoid:**
```javascript
let currentSearchId = 0;

function search(query) {
  const searchId = ++currentSearchId;

  fetch(`/api/search?q=${query}`)
    .then(r => r.json())
    .then(data => {
      // Only render if this is still the latest search
      if (searchId === currentSearchId) {
        renderResults(data.results);
      }
    });
}
```
**Warning signs:** Flickering results, old results briefly appearing after typing

### Pitfall 3: Filter Preset Name Collisions
**What goes wrong:** User saves "Recent Non-Compliant" preset, institution switcher resets it
**Why it happens:** Presets stored globally instead of per-institution
**How to avoid:** Always scope presets to institution_id in database:
```sql
CREATE TABLE filter_presets (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,  -- KEY: Scope to institution
  name TEXT NOT NULL,
  filters_json TEXT NOT NULL,
  UNIQUE(institution_id, name),  -- Prevent duplicates per institution
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);
```
**Warning signs:** User switches institutions, saved preset shows wrong results

### Pitfall 4: Recent Searches Leaking Between Users
**What goes wrong:** Multi-user localhost setup shows Alice's searches to Bob
**Why it happens:** localStorage is browser-wide, not user-scoped
**How to avoid:** Key by institution ID (not user):
```javascript
// GOOD: Scoped to institution (workspace is single-user)
const key = `accreditai_recent_${institutionId}`;

// BAD: Global recent searches across all institutions
const key = 'accreditai_recent_searches';
```
**Warning signs:** Switching institutions shows searches from other institutions

### Pitfall 5: Empty State Confusion
**What goes wrong:** User types 1 character, sees "No results" instead of "Type 2+ characters to search"
**Why it happens:** Showing search results empty state before minimum query length
**How to avoid:**
```javascript
if (query.length === 0) {
  renderRecentSearches();  // Show recent searches
} else if (query.length === 1) {
  renderMinLengthHint();   // "Type at least 2 characters..."
} else {
  renderLiveResults();      // Show live search results
}
```
**Warning signs:** User confused why no results appear after typing "a"

## Code Examples

Verified patterns from existing codebase:

### Existing Site Visit Search Backend (Reuse)
```python
# src/services/site_visit_service.py (EXISTING - lines 127-196)
def search(
    self,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    """Execute parallel search across all sources."""
    start_time = time.time()
    filters = filters or {}
    sources = filters.get("sources", ALL_SOURCES)
    results: List[SiteVisitResult] = []

    # Search each source
    if "documents" in sources:
        results.extend(self._search_documents(query, filters))
    if "standards" in sources:
        results.extend(self._search_standards(query, filters))
    # ... (5 more sources)

    # Calculate final scores, deduplicate, sort
    for result in results:
        result.score = self._calculate_final_score(result, query)
    results = self._deduplicate_results(results)
    results.sort(key=lambda r: -r.score)

    # Save to history
    self._save_search_history(query, filters, total, query_time_ms, sources)

    return SearchResponse(results, total, query_time_ms, sources)
```

### Existing Command Palette Structure (Extend)
```javascript
// static/js/command_palette.js (EXISTING - lines 18-39)
window.CommandPalette = (function() {
  let isOpen = false;
  let selectedIndex = 0;
  let filteredCommands = [];

  function open() {
    isOpen = true;
    const palette = document.getElementById('command-palette');
    palette.style.display = 'flex';
    const input = document.getElementById('command-palette-input');
    input.focus();
  }

  function handleInput(e) {
    const query = e.target.value;
    // EXTEND HERE: Detect mode, trigger search if not command mode
  }

  return { open, close, handleInput };
})();
```

### NEW: Filter Preset Storage
```python
# NEW: src/api/global_search.py
@global_search_bp.route("/api/institutions/<institution_id>/search/presets", methods=["POST"])
def save_filter_preset(institution_id: str):
    """Save a named filter preset."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    filters = data.get("filters", {})

    if not name:
        return jsonify({"error": "name is required"}), 400

    conn = get_conn()
    preset_id = generate_id("sfp")

    try:
        conn.execute(
            """
            INSERT INTO filter_presets (id, institution_id, name, filters_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(institution_id, name) DO UPDATE SET filters_json = excluded.filters_json
            """,
            (preset_id, institution_id, name, json.dumps(filters)),
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"id": preset_id, "name": name, "filters": filters}), 201
```

### NEW: Recent Searches Rendering
```javascript
// NEW: Add to command_palette.js
function renderRecentSearches(institutionId) {
  const recent = getRecentSearches(institutionId);
  const container = document.getElementById('command-palette-results');

  if (recent.length === 0) {
    container.innerHTML = '<div class="command-empty">Start typing to search...</div>';
    return;
  }

  let html = '<div class="command-group"><div class="command-group-title">Recent Searches</div>';
  recent.forEach((query, idx) => {
    html += `
      <div class="command-item" data-index="${idx}" onclick="CommandPalette.executeRecentSearch('${query}')">
        <svg class="command-item-icon" viewBox="0 0 24 24" stroke="currentColor">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <div class="command-item-content">
          <div class="command-item-title">${escapeHtml(query)}</div>
        </div>
        <span class="command-item-shortcut"><kbd>${idx + 1}</kbd></span>
      </div>
    `;
  });
  html += '</div>';
  container.innerHTML = html;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate search page | Command palette overlay | ~2020 (VS Code popularized) | Faster workflow, no context switch |
| Single-purpose search | Dual-mode (search + commands) | VS Code 1.43+ (2020) | One shortcut for all needs |
| Manual filter management | Saveable filter presets | Algolia autocomplete 2021+ | Reusable complex filters |
| String matching only | Semantic + FTS5 hybrid | ChromaDB/vector DBs 2022+ | Better relevance for natural language |
| Results list only | Grouped tabs with counts | Modern autocomplete libs 2023+ | Easier navigation, quick filtering |

**Deprecated/outdated:**
- F2 shortcut for Site Visit Mode: Replaced by unified Ctrl+K palette
- Separate institution switcher (Ctrl+K): Merged into command palette with ">" prefix
- site_visit_overlay.html partial: Merged into command_palette.html
- site_visit_mode.js: Logic merged into command_palette.js

## Open Questions

1. **Command palette merge strategy**
   - What we know: Two existing overlays (command palette, site visit mode) both use similar UI patterns
   - What's unclear: Best migration path to avoid breaking existing muscle memory (F2 shortcut)
   - Recommendation: Keep F2 as alias for 6 months post-release, show deprecation toast encouraging Ctrl+K

2. **Filter dropdown vs sidebar**
   - What we know: User wants filter chips for active state, needs UI to add filters
   - What's unclear: Best placement - inline dropdown (compact) vs sidebar panel (more space)
   - Recommendation: Inline dropdown next to search input - keeps focus near typing area, similar to VS Code

3. **Search across all institutions**
   - What we know: Default scope is current institution, but portfolios feature exists (Phase 11)
   - What's unclear: How to expose "Search All" toggle without cluttering UI
   - Recommendation: Add filter chip "Scope: Current Institution" - click to toggle to "All Portfolios"

4. **Live result preview vs navigate on click**
   - What we know: User decision says "click result navigates to item page, overlay closes"
   - What's unclear: Should Tab key show inline preview pane (like Site Visit Mode) or just navigate?
   - Recommendation: Keep Tab preview pane for power users - doesn't conflict with click navigation

## Sources

### Primary (HIGH confidence)
- Existing codebase: src/services/site_visit_service.py - unified search implementation
- Existing codebase: static/js/command_palette.js - command palette UI patterns
- Existing codebase: src/db/migrations/0021_site_visit.sql - FTS5 indexes, search history tables
- Existing codebase: templates/partials/command_palette.html - keyboard navigation, modal overlay
- Existing codebase: templates/partials/site_visit_overlay.html - result tabs, filter buttons, preview pane

### Secondary (MEDIUM confidence)
- [GitHub: light-cmd-palette](https://github.com/julianmateu/light-cmd-palette) - Vanilla JS command palette patterns
- [Algolia: Recent Searches](https://www.algolia.com/doc/ui-libraries/autocomplete/guides/adding-recent-searches) - localStorage + limit 5 pattern
- [Vanilla Framework: Search and Filter](https://vanillaframework.io/docs/patterns/search-and-filter) - Filter chip design pattern
- [CodePen: Vanilla JS Tag Filter](https://codepen.io/stephd/pen/MWaGbYO) - Removable chip implementation

### Tertiary (LOW confidence)
- [autoComplete.js](https://tarekraafat.github.io/autoComplete.js/) - Feature reference (not using library, but validates patterns)
- [VS Code Command Palette](https://code.visualstudio.com/docs/getstarted/userinterface#_command-palette) - UX inspiration (industry standard)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Reusing existing infrastructure (SiteVisitService, ChromaDB, FTS5, command palette)
- Architecture: HIGH - Existing patterns proven in Site Visit Mode, just extending to global access
- Pitfalls: MEDIUM - Known issues from existing search features, z-index conflicts are common

**Research date:** 2026-03-16
**Valid until:** 2026-04-15 (30 days - stable domain, minimal churn expected)
