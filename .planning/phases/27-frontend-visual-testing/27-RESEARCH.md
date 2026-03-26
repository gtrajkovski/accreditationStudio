# Phase 27: Frontend & Visual Testing - Research

**Researched:** 2026-03-26
**Domain:** Frontend UI implementation, keyboard navigation, visual testing
**Confidence:** HIGH

## Summary

Phase 27 focuses on implementing the user-facing components for context-sensitive search. The backend API (Phase 26) and service layer (Phase 25) are complete, providing a solid foundation. This phase requires building: (1) command palette enhancements with scope badges and cycling, (2) inline search bar in page header with dynamic placeholders, (3) results panel with source tabs and counts, (4) comprehensive keyboard navigation, and (5) visual regression testing to prevent UI breakage.

The project uses **vanilla JavaScript** (no React/Vue), Flask + Jinja2 templates, and an existing command palette infrastructure (`static/js/command_palette.js`) that already handles dual-mode search (search vs. commands), filter chips, result tabs, and debouncing. The Phase 27 implementation will **extend** this existing component, not rewrite it.

**Primary recommendation:** Enhance the existing command palette with contextual scope detection from `data-*` attributes in `base.html`, add a scope badge UI element with Tab-cycling, create a separate inline search bar component for page headers, and use BackstopJS or Playwright for visual regression testing.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS (ES6+) | Native | State management, DOM manipulation | Project constraint - no frameworks allowed |
| Flask + Jinja2 | 3.x | Server-side templating | Existing architecture |
| CSS Grid/Flexbox | Native | Layout for results panel, tabs | Modern standard, no dependency |
| localStorage | Native | Recent searches, scope preference | Browser standard for client state |
| sessionStorage | Native | Active filters (per-session) | Browser standard for ephemeral state |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| BackstopJS | 6.x+ | Visual regression testing | Open-source, Node-based, headless Chrome |
| Playwright | 1.40+ | Visual testing + E2E | If BackstopJS insufficient |
| jest-image-snapshot | 6.x | Alternative to BackstopJS | If Jest already in use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BackstopJS | Percy (BrowserStack) | Percy is enterprise ($), BackstopJS is free but requires more setup |
| Vanilla JS | Alpine.js | Alpine adds reactivity but introduces dependency (violates CLAUDE.md) |
| localStorage | IndexedDB | IndexedDB is overkill for simple key-value pairs |

**Installation:**
```bash
# For visual testing (dev dependency)
npm install --save-dev backstopjs
# OR
npm install --save-dev playwright @playwright/test
```

**Version verification:** None required - vanilla JS uses native browser APIs. For testing tools, verify after install:
```bash
npx backstopjs --version
# or
npx playwright --version
```

## Architecture Patterns

### Recommended Project Structure
```
static/js/
├── command_palette.js        # Existing - enhance with scope badge
├── contextual_search.js      # NEW - inline search bar component
├── scope_badge.js            # NEW - scope indicator + cycling logic
└── i18n.js                   # Existing - translation helper

templates/
├── base.html                 # Existing - add inline search bar
└── components/
    └── search_bar.html       # NEW - Jinja2 macro for inline search

tests/backstop/
├── backstop.json             # Config for visual tests
├── scenarios/
│   ├── command_palette.json
│   └── inline_search.json
└── reference/                # Baseline screenshots
```

### Pattern 1: Scope Badge with Tab Cycling
**What:** A visual indicator showing the current search scope (e.g., "This Institution") that cycles to the next scope when user presses Tab (while focused on search input).
**When to use:** In both command palette and inline search bar.
**Example:**
```javascript
// Source: Vanilla JS state management pattern (2026)
class ScopeBadge {
  constructor(container, initialScope) {
    this.scopes = ['global', 'institution', 'program', 'document', 'standards', 'compliance'];
    this.currentIndex = this.scopes.indexOf(initialScope);
    this.container = container;
    this.render();
  }

  cycle() {
    this.currentIndex = (this.currentIndex + 1) % this.scopes.length;
    this.render();
    this.emit('scope-changed', this.scopes[this.currentIndex]);
  }

  render() {
    const scope = this.scopes[this.currentIndex];
    const label = window.AccreditAI.i18n.t(`search.scope.${scope}`);
    this.container.innerHTML = `
      <span class="scope-badge scope-badge-${scope}">
        ${label}
      </span>
    `;
  }

  emit(event, data) {
    this.container.dispatchEvent(new CustomEvent(event, { detail: data }));
  }
}
```

### Pattern 2: Context Detection from Data Attributes
**What:** Read `data-page`, `data-institution-id`, `data-program-id`, etc. from `<body>` or a context element to determine initial scope.
**When to use:** On page load, before initializing search components.
**Example:**
```javascript
// Source: AccreditAI existing pattern (templates/base.html)
function detectSearchContext() {
  const body = document.body;
  const context = {
    page: body.dataset.page || 'global',
    institution_id: body.dataset.institutionId || null,
    program_id: body.dataset.programId || null,
    document_id: body.dataset.documentId || null,
    accreditor_code: body.dataset.accreditorCode || null
  };

  // Determine scope from context
  if (context.document_id) return 'document';
  if (context.program_id) return 'program';
  if (context.institution_id && context.page === 'compliance') return 'compliance';
  if (context.institution_id && context.page === 'standards') return 'standards';
  if (context.institution_id) return 'institution';
  return 'global';
}
```

### Pattern 3: Debounced Search with Race Condition Prevention
**What:** Wait 250-300ms after user stops typing, then execute search. Cancel previous in-flight requests to prevent stale results.
**When to use:** Both command palette and inline search bar.
**Example:**
```javascript
// Source: https://www.freecodecamp.org/news/optimize-search-in-javascript-with-debouncing/
let searchTimeout = null;
let currentSearchId = 0;

async function debouncedSearch(query) {
  if (searchTimeout) clearTimeout(searchTimeout);

  searchTimeout = setTimeout(async () => {
    const searchId = ++currentSearchId;

    try {
      const response = await fetch('/api/search/contextual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, scope: currentScope, ... })
      });

      if (searchId !== currentSearchId) return; // Stale result

      const data = await response.json();
      renderResults(data);
    } catch (error) {
      if (searchId !== currentSearchId) return;
      renderError();
    }
  }, 250);
}
```

### Pattern 4: Focus Trap for Modal Keyboard Navigation
**What:** When command palette is open, Tab/Shift+Tab cycle through palette elements only, not page content.
**When to use:** All modal dialogs, including command palette.
**Example:**
```javascript
// Source: https://www.bennadel.com/blog/4096-trapping-focus-within-an-element-using-tab-key-navigation-in-javascript.htm
function trapFocus(containerEl) {
  const focusableEls = containerEl.querySelectorAll(
    'a[href], button:not([disabled]), textarea, input, select'
  );
  const firstFocusable = focusableEls[0];
  const lastFocusable = focusableEls[focusableEls.length - 1];

  containerEl.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;

    if (e.shiftKey) { // Shift+Tab
      if (document.activeElement === firstFocusable) {
        e.preventDefault();
        lastFocusable.focus();
      }
    } else { // Tab
      if (document.activeElement === lastFocusable) {
        e.preventDefault();
        firstFocusable.focus();
      }
    }
  });
}
```

### Anti-Patterns to Avoid
- **Don't reinvent command_palette.js:** The existing file already handles search, results, tabs, filters. Extend it, don't replace it.
- **Don't use frameworks:** React/Vue/Alpine.js violate CLAUDE.md's vanilla JS requirement.
- **Don't skip debouncing:** Every keystroke triggering an API call will hammer the server and degrade UX.
- **Don't ignore accessibility:** Missing aria-keyshortcuts, focus traps, or screen reader labels will fail WCAG compliance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visual regression testing | Custom screenshot comparison | BackstopJS, Playwright | Pixel-diff algorithms, cross-browser support, baseline management |
| Debounce/throttle utilities | Manual setTimeout logic | Standard debounce pattern | Edge cases (clearTimeout leaks, rapid rerenders) |
| Focus trap logic | Custom Tab key interception | W3C ARIA APG pattern | Accessibility edge cases (screen readers, mobile) |
| Keyboard shortcut registry | Global event listeners | aria-keyshortcuts attribute | Screen reader announces shortcuts |

**Key insight:** Visual regression testing has complex gotchas (dynamic content, timestamps, async loads). BackstopJS handles these with region-based ignores, responsive viewports, and CI integration. Rolling custom solutions risks false positives and brittle tests.

## Common Pitfalls

### Pitfall 1: Tab Key Conflicts with Default Browser Behavior
**What goes wrong:** Browser's default Tab behavior moves focus to next DOM element. If scope cycling also uses Tab, focus jumps to wrong element.
**Why it happens:** Tab key has dual purpose - standard focus navigation AND custom scope cycling.
**How to avoid:** Only cycle scope when search input has focus AND user presses Tab without Shift. Prevent default behavior and manually handle focus.
**Warning signs:** Focus jumps to next element instead of cycling scope; Shift+Tab breaks navigation.

### Pitfall 2: Stale Search Results from Race Conditions
**What goes wrong:** User types "com", request fires. User types "compliance", second request fires. Second request completes first, but first request overwrites results with stale "com" results.
**Why it happens:** Network requests complete out of order due to varying latency.
**How to avoid:** Assign sequential IDs to each search request. Ignore responses from outdated IDs. (See Pattern 3 above.)
**Warning signs:** Search results "flicker" or show wrong results after fast typing.

### Pitfall 3: Dynamic Content Breaking Visual Tests
**What goes wrong:** Visual regression tests fail due to timestamps, usernames, or async-loaded content that differs between runs.
**Why it happens:** BackstopJS captures everything on screen, including dynamic content.
**How to avoid:** Use `removeSelectors` or `hideSelectors` in BackstopJS config to ignore dynamic regions. Alternatively, use `onReadyScript` to inject fixed values for testing.
**Warning signs:** Tests fail with "minor differences" that are actually expected (e.g., "Last updated: 2026-03-26 10:00 AM" vs. "2026-03-26 10:05 AM").

### Pitfall 4: Scope Badge Not Syncing with Results
**What goes wrong:** Scope badge shows "This Program" but results include institution-wide documents.
**Why it happens:** Badge state updates locally but API request uses stale scope value.
**How to avoid:** Single source of truth for scope state. Badge and search both read from same variable. Update API payload at same time as badge render.
**Warning signs:** Badge label doesn't match result breadcrumbs or counts.

### Pitfall 5: Missing ARIA Attributes for Screen Readers
**What goes wrong:** Screen reader users can't discover keyboard shortcuts or understand scope badge purpose.
**Why it happens:** Vanilla JS developers forget to add `aria-label`, `aria-keyshortcuts`, `role`, etc.
**How to avoid:** Add `aria-keyshortcuts="Control+K"` to search input, `aria-live="polite"` to results container, `role="search"` to search landmark.
**Warning signs:** Automated accessibility tests (Axe, Lighthouse) report missing labels; manual screen reader testing reveals confusion.

## Code Examples

Verified patterns from official sources:

### Inline Search Bar Component
```javascript
// Source: Vanilla JS state management + debounce patterns (2026)
class InlineSearchBar {
  constructor(containerEl, options = {}) {
    this.container = containerEl;
    this.options = {
      debounceMs: 250,
      minQueryLength: 2,
      ...options
    };
    this.searchInput = null;
    this.scopeBadge = null;
    this.resultsPanel = null;
    this.currentScope = detectSearchContext();
    this.searchTimeout = null;
    this.currentSearchId = 0;

    this.init();
  }

  init() {
    this.render();
    this.attachEventListeners();
  }

  render() {
    const placeholderKey = `search.placeholder.${this.currentScope}`;
    const placeholder = window.AccreditAI.i18n.t(placeholderKey);

    this.container.innerHTML = `
      <div class="inline-search-bar" role="search">
        <div class="search-input-wrapper">
          <svg class="search-icon" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="search"
            class="search-input"
            placeholder="${placeholder}"
            aria-label="Contextual search"
            aria-keyshortcuts="Slash Control+K Tab"
          />
          <div class="scope-badge-container"></div>
        </div>
        <div class="search-results-panel" hidden></div>
      </div>
    `;

    this.searchInput = this.container.querySelector('.search-input');
    this.resultsPanel = this.container.querySelector('.search-results-panel');

    const badgeContainer = this.container.querySelector('.scope-badge-container');
    this.scopeBadge = new ScopeBadge(badgeContainer, this.currentScope);
  }

  attachEventListeners() {
    // Input event - debounced search
    this.searchInput.addEventListener('input', (e) => {
      this.handleInput(e.target.value);
    });

    // Keydown event - handle Tab for scope cycling
    this.searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault();
        this.scopeBadge.cycle();
        this.currentScope = this.scopeBadge.getCurrentScope();
        this.updatePlaceholder();
      }
    });

    // Escape - clear search
    this.searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.clearSearch();
      }
    });

    // Scope change event from badge
    this.scopeBadge.container.addEventListener('scope-changed', (e) => {
      this.currentScope = e.detail;
      this.updatePlaceholder();
      if (this.searchInput.value.length >= this.options.minQueryLength) {
        this.handleInput(this.searchInput.value);
      }
    });
  }

  handleInput(query) {
    if (query.length === 0) {
      this.hideResults();
      return;
    }

    if (query.length < this.options.minQueryLength) {
      this.showMinLengthHint();
      return;
    }

    // Debounce
    if (this.searchTimeout) clearTimeout(this.searchTimeout);
    this.searchTimeout = setTimeout(() => {
      this.executeSearch(query);
    }, this.options.debounceMs);
  }

  async executeSearch(query) {
    const searchId = ++this.currentSearchId;
    this.showLoading();

    try {
      const response = await fetch('/api/search/contextual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          scope: this.currentScope,
          institution_id: document.body.dataset.institutionId,
          program_id: document.body.dataset.programId,
          document_id: document.body.dataset.documentId
        })
      });

      if (searchId !== this.currentSearchId) return; // Stale

      const data = await response.json();
      this.renderResults(data);
    } catch (error) {
      if (searchId !== this.currentSearchId) return;
      this.showError();
    }
  }

  renderResults(data) {
    // Implementation similar to command_palette.js renderSearchResultsWithTabs
  }

  updatePlaceholder() {
    const placeholderKey = `search.placeholder.${this.currentScope}`;
    this.searchInput.placeholder = window.AccreditAI.i18n.t(placeholderKey);
  }

  clearSearch() {
    this.searchInput.value = '';
    this.hideResults();
  }

  // ... other methods
}
```

### BackstopJS Configuration
```json
// Source: BackstopJS documentation (2026)
{
  "id": "accreditai_contextual_search",
  "viewports": [
    {
      "label": "desktop",
      "width": 1920,
      "height": 1080
    },
    {
      "label": "tablet",
      "width": 768,
      "height": 1024
    }
  ],
  "scenarios": [
    {
      "label": "Command Palette - Global Scope",
      "url": "http://localhost:5003/",
      "onReadyScript": "simulate_command_palette_open.js",
      "selectors": ["#command-palette"],
      "removeSelectors": [".timestamp", ".user-name"],
      "hideSelectors": [".sidebar-badge"],
      "misMatchThreshold": 0.1,
      "requireSameDimensions": true
    },
    {
      "label": "Command Palette - Scope Badge Cycling",
      "url": "http://localhost:5003/institutions/inst_123",
      "onReadyScript": "simulate_scope_cycle.js",
      "selectors": [".scope-badge"],
      "misMatchThreshold": 0.05
    },
    {
      "label": "Inline Search Bar - Program Scope",
      "url": "http://localhost:5003/institutions/inst_123/programs/prog_456",
      "selectors": [".inline-search-bar"],
      "misMatchThreshold": 0.1
    },
    {
      "label": "Results Panel - Source Tabs",
      "url": "http://localhost:5003/",
      "onReadyScript": "simulate_search_results.js",
      "selectors": ["#search-result-tabs", ".command-palette-results"],
      "misMatchThreshold": 0.15
    }
  ],
  "paths": {
    "bitmaps_reference": "tests/backstop/reference",
    "bitmaps_test": "tests/backstop/test",
    "html_report": "tests/backstop/report",
    "ci_report": "tests/backstop/ci_report"
  },
  "report": ["browser", "CI"],
  "engine": "puppeteer",
  "engineOptions": {
    "args": ["--no-sandbox"]
  },
  "asyncCaptureLimit": 5,
  "asyncCompareLimit": 50,
  "debug": false,
  "debugWindow": false
}
```

### OnReady Script Example
```javascript
// tests/backstop/scripts/simulate_command_palette_open.js
// Source: BackstopJS patterns
module.exports = async (page, scenario, vp) => {
  console.log('Opening command palette...');

  // Wait for page to load
  await page.waitForSelector('body');

  // Trigger Ctrl+K to open palette
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyK');
  await page.keyboard.up('Control');

  // Wait for palette animation
  await page.waitForSelector('#command-palette[style*="display: flex"]', {
    timeout: 1000
  });

  // Inject fixed timestamp for consistent screenshots
  await page.evaluate(() => {
    const timestampEls = document.querySelectorAll('.timestamp');
    timestampEls.forEach(el => {
      el.textContent = '2026-03-26 10:00 AM';
    });
  });

  // Wait for any animations to complete
  await page.waitForTimeout(300);
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| jQuery-based search | Vanilla JS with Proxy reactivity | 2024-2025 | Reduced bundle size, native performance |
| Manual screenshot comparison | BackstopJS/Percy automation | 2023-2024 | CI/CD integration, baseline management |
| Global keyboard listener | ARIA keyboard patterns + focus traps | 2024-2025 | Accessibility compliance (WCAG 2.1) |
| Framework state (React/Vue) | localStorage + sessionStorage | 2025-2026 | No build step, simpler debugging |
| Fixed search scope | Context-aware scoping | 2026 (this phase) | Reduces user cognitive load |

**Deprecated/outdated:**
- jQuery `.live()` for event delegation: Replaced by native `addEventListener` with bubbling.
- `keyCode` property: Deprecated in favor of `key` property for keyboard events.
- BackstopJS v3 syntax: v6+ uses async/await patterns and Puppeteer instead of PhantomJS.

## Validation Architecture

**Note:** nyquist_validation is not explicitly set in `.planning/config.json`, so this section is included per default behavior.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | BackstopJS 6.x + Playwright (optional) |
| Config file | `tests/backstop/backstop.json` (Wave 0 task) |
| Quick run command | `npx backstopjs test --config=tests/backstop/backstop.json` |
| Full suite command | `npx backstopjs test && npx backstopjs approve` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTX-02 | User can manually widen/narrow scope via UI controls | visual | `npx backstopjs test --filter="Scope Badge"` | ❌ Wave 0 |
| CTX-03 | Search scope visually indicated with badge | visual | `npx backstopjs test --filter="Scope Badge"` | ❌ Wave 0 |
| SRCHUI-01 | Command palette shows scope badge + allows cycling | visual + E2E | `npx backstopjs test --filter="Command Palette"` | ❌ Wave 0 |
| SRCHUI-02 | Inline search bar shows scope as placeholder | visual | `npx backstopjs test --filter="Inline Search"` | ❌ Wave 0 |
| SRCHUI-03 | Results panel has tabs for each source | visual | `npx backstopjs test --filter="Results Panel"` | ❌ Wave 0 |
| SRCHUI-04 | Keyboard shortcuts work (/, Ctrl+K, Tab, Shift+Up/Down) | E2E | `npx playwright test keyboard-nav.spec.js` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Quick visual test on changed component only (`--filter` flag)
- **Per wave merge:** Full suite (`npx backstopjs test`)
- **Phase gate:** Full suite green + manual accessibility review before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/backstop/backstop.json` — config for all scenarios (REQ-CTX-02, CTX-03, SRCHUI-01, SRCHUI-02, SRCHUI-03)
- [ ] `tests/backstop/scripts/simulate_command_palette_open.js` — onReady script for palette scenarios
- [ ] `tests/backstop/scripts/simulate_scope_cycle.js` — Tab key cycling simulation
- [ ] `tests/backstop/scripts/simulate_search_results.js` — Results panel with tabs
- [ ] `tests/e2e/keyboard-nav.spec.js` — Playwright test for keyboard shortcuts (REQ-SRCHUI-04)
- [ ] Framework install: `npm install --save-dev backstopjs playwright` — if not detected

## Environment Availability

**Step 2.6: SKIPPED (no external dependencies identified)** — Phase 27 uses vanilla JavaScript browser APIs and BackstopJS (installed via npm as dev dependency). No external services, runtimes, or databases required.

## Sources

### Primary (HIGH confidence)
- [Mobbin Command Palette UI Patterns](https://mobbin.com/glossary/command-palette) - Command palette best practices
- [Destiner: Designing a Command Palette](https://destiner.io/blog/post/designing-a-command-palette/) - Keyboard-first design
- [MDN: Keyboard-navigable JavaScript widgets](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Keyboard-navigable_JavaScript_widgets) - ARIA keyboard patterns
- [W3C ARIA APG: Developing a Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) - Official ARIA guidelines
- [MDN: aria-keyshortcuts attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-keyshortcuts) - Screen reader support
- [FreeCodeCamp: Optimize Search with Debouncing](https://www.freecodecamp.org/news/optimize-search-in-javascript-with-debouncing/) - Debounce pattern
- [Medium: State Management in Vanilla JS 2026 Trends](https://medium.com/@chirag.dave/state-management-in-vanilla-js-2026-trends-f9baed7599de) - Modern vanilla JS patterns
- [VibidSoft: State Management in Vanilla JS 2026](https://www.vibidsoft.com/blog/state-management-in-vanilla-js-2026-trends/) - Reactive Proxies, async streams
- [JavaScript.info: LocalStorage, sessionStorage](https://javascript.info/localstorage) - Storage API reference
- [Ben Nadel: Trapping Focus with Tab Navigation](https://www.bennadel.com/blog/4096-trapping-focus-within-an-element-using-tab-key-navigation-in-javascript.htm) - Focus trap pattern
- [Sauce Labs: 20 Best Visual Testing Tools 2026](https://saucelabs.com/resources/blog/comparing-the-20-best-visual-testing-tools-of-2026) - Tool comparison
- [Percy: Open Source Visual Regression Tools 2026](https://percy.io/blog/open-source-visual-regression-testing-tools/) - BackstopJS, Playwright recommendations
- [Bug0: Best Visual Regression Testing Tools 2026](https://bug0.com/knowledge-base/visual-regression-testing-tools) - Tool reviews

### Secondary (MEDIUM confidence)
- [Medium: Command Palette UX Patterns](https://medium.com/design-bootcamp/command-palette-ux-patterns-1-d6b6e68f30c1) - Scoped palettes
- [Philip C Davis: Command Palette Interfaces](https://philipcdavis.com/writing/command-palette-interfaces) - Best practices
- [Algolia: Animated Placeholders](https://www.algolia.com/doc/guides/solutions/ecommerce/search/autocomplete/animated-placeholder) - Dynamic placeholder patterns
- [CSS Script: Best Autocomplete Libraries 2026](https://www.cssscript.com/best-autocomplete/) - Vanilla JS autocomplete
- [Smart Interface Design Patterns: Breadcrumbs UX](https://smart-interface-design-patterns.com/articles/breadcrumbs-ux/) - Scope narrowing/widening
- [NN/G: Breadcrumbs Design Guidelines](https://www.nngroup.com/articles/breadcrumbs/) - Hierarchy patterns
- [Tailwind CSS Badges](https://tailwindcss.com/plus/ui-blocks/application-ui/elements/badges) - Badge component patterns
- [Smart Interface Design: Badges vs Pills vs Chips](https://smart-interface-design-patterns.com/articles/badges-chips-tags-pills/) - UI element distinctions

### Tertiary (LOW confidence)
- None - all findings verified with official docs or established design pattern libraries.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Vanilla JS is project requirement, BackstopJS is proven industry standard
- Architecture: HIGH - Patterns verified with MDN/W3C, existing codebase provides reference
- Pitfalls: HIGH - Based on known gotchas from debounce/focus trap/visual testing domains
- Visual testing: MEDIUM - BackstopJS chosen based on open-source preference, but Playwright is equally valid alternative

**Research date:** 2026-03-26
**Valid until:** 60 days (stable domain - vanilla JS APIs don't change rapidly, visual testing tools mature)
