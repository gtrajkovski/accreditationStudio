# Phase 13: Search Enhancement - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Global search UI with unified command palette (Ctrl+K), autocomplete with recent searches and live results, advanced filters (type, status, date), and results overlay with source tabs. This phase enhances the existing Site Visit Mode search infrastructure to provide application-wide search access.

</domain>

<decisions>
## Implementation Decisions

### Search Bar Location
- Unified command palette accessible via Ctrl+K
- Combines search + quick actions (like VS Code)
- Replaces current institution switcher shortcut - merge into command palette
- Default scope: current institution (option to search all)

### Autocomplete Behavior
- Show recent searches (5 items) at top of dropdown
- Live results preview (5 items) below recent searches
- Live results appear after 2+ characters typed
- Support command prefix ">" for quick actions:
  - Switch institution
  - Navigate to page
  - Run audit, etc.

### Filter UX
- Available filters: document type, compliance status, date range
- Filters persist until user clears them
- Active filters shown as removable chips
- Save filter combinations as named presets (e.g., "Recent Non-Compliant Policies")

### Results Display
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

</decisions>

<specifics>
## Specific Ideas

- Ctrl+K opens unified command palette (search + commands)
- ">" prefix switches to command mode (like VS Code)
- Recent searches persist per institution
- Filter presets are user-saveable
- Results tabs show counts to help user find relevant content fast
- Overlay panel preserves user context (doesn't navigate away)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SiteVisitService` (src/services/site_visit_service.py): Unified search across 6 data sources with citations
- `SearchService` (src/search/search_service.py): Semantic search with ChromaDB
- FTS5 indexes in database for full-text search
- Site Visit API endpoints (search, history, saved searches)

### Established Patterns
- Overlay pattern from Site Visit Mode (F2 shortcut)
- Institution switcher uses Ctrl+K currently (will be merged)
- Filter pattern: sources, doc_types, min_confidence in site_visit_service
- Search history table exists in database (0021_site_visit.sql)

### Integration Points
- Extend site_visit_bp or create new global_search_bp
- Reuse SiteVisitResult model for result formatting
- Add keyboard shortcut handler to base.html
- Store filter presets in database (new table or JSON in settings)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-search-enhancement*
*Context gathered: 2026-03-16*
