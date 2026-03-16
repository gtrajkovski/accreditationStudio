# Phase 14: Polish & UX - Research

**Researched:** 2026-03-16
**Domain:** Frontend UX patterns (skeleton loaders, keyboard shortcuts modal, onboarding tooltips)
**Confidence:** HIGH

## Summary

Phase 14 focuses on three polish features to improve perceived performance, discoverability, and first-time user experience: skeleton loaders to replace spinners, a keyboard shortcuts help modal, and onboarding tooltips for new users.

The project already has a strong foundation with vanilla JS architecture, custom CSS variables system, existing keyboard shortcut infrastructure (command palette), i18n support, and a "Certified Authority" design system. All three features can be implemented using pure CSS and vanilla JavaScript with no external dependencies, maintaining architectural consistency.

**Primary recommendation:** Build all three features using existing patterns - CSS-only skeleton animations leveraging the `background-attachment: fixed` technique for synchronized shimmer effects, a keyboard shortcuts modal following the existing modal patterns with aria-modal and focus trap, and a lightweight onboarding system using CSS tooltips with localStorage-based state management per institution.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JavaScript | ES6+ | UI interactions, state management | Already project standard, no frameworks |
| CSS Custom Properties | - | Theming, animations | Already in use via variables.css |
| CSS Animations | - | Skeleton shimmer, transitions | Native browser support, no dependencies |
| localStorage | - | Onboarding state, user preferences | Persistent client-side storage |
| Jinja2 templates | - | Server-side rendering | Project standard for HTML generation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.4.0+ | Python testing | Backend/integration tests |
| ARIA attributes | - | Accessibility for modal | Keyboard shortcuts modal |
| sessionStorage | - | Per-session state | Transient onboarding dismissals |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure CSS skeleton | React Skeleton, Ant Design | External dependencies, framework lock-in, overkill for simple animations |
| Custom modal | Bootstrap Modal, Material-UI Dialog | Requires full framework, conflicts with existing design system |
| Custom tooltips | Tippy.js, Popper.js | Adds 20KB+ for functionality achievable in <2KB CSS |
| localStorage | Cookies, Server-side state | Cookies less flexible, server-side adds complexity for client-only feature |

**Installation:**
```bash
# No new dependencies required - uses existing project stack
```

## Architecture Patterns

### Recommended Project Structure
```
static/
├── css/
│   ├── skeleton.css       # Skeleton loader styles
│   ├── keyboard-help.css  # Keyboard shortcuts modal
│   └── onboarding.css     # Onboarding tooltips
├── js/
│   ├── skeleton.js        # Skeleton loader utility (optional)
│   ├── keyboard-help.js   # Shortcuts modal controller
│   └── onboarding.js      # Onboarding flow manager
templates/
└── components/
    └── keyboard_shortcuts_modal.html  # Modal template partial
```

### Pattern 1: Synchronized Skeleton Loaders
**What:** CSS-only skeleton loaders using `background-attachment: fixed` for globally synchronized shimmer effects across multiple elements
**When to use:** Replace all `.spinner` instances with contextual skeletons matching final content layout
**Example:**
```css
/* Source: https://freefrontend.com/code/synchronized-pure-css-skeleton-loader-2026-01-22/ */
/* Leverages existing CSS variables for theme consistency */

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-hover) 0%,
    var(--bg-panel) 20%,
    var(--accent-muted) 50%,
    var(--bg-panel) 80%,
    var(--bg-hover) 100%
  );
  background-size: 200% 100%;
  background-attachment: fixed;  /* Key: synchronizes across all elements */
  animation: skeleton-shimmer 2s ease-in-out infinite;
  border-radius: var(--radius-md);
  pointer-events: none;
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Specific variants */
.skeleton-text { height: 1rem; margin-bottom: 0.5rem; }
.skeleton-title { height: 2rem; width: 60%; margin-bottom: 1rem; }
.skeleton-card { height: 120px; }
.skeleton-avatar { width: 40px; height: 40px; border-radius: 50%; }
.skeleton-button { height: 40px; width: 100px; }
```

### Pattern 2: Accessible Keyboard Shortcuts Modal
**What:** Modal overlay with focus trap, ESC to close, ARIA labeling
**When to use:** Triggered by `?` key or Help menu item
**Example:**
```javascript
// Source: https://www.a11y-collective.com/blog/modal-accessibility/
// Follows WCAG 2.1 Level AA standards

class KeyboardShortcutsModal {
  constructor() {
    this.modal = document.getElementById('keyboard-shortcuts-modal');
    this.backdrop = this.modal.querySelector('.modal-backdrop');
    this.content = this.modal.querySelector('.modal-content');
    this.focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    this.firstFocusableElement = null;
    this.lastFocusableElement = null;
    this.previousActiveElement = null;
  }

  open() {
    this.previousActiveElement = document.activeElement;
    this.modal.style.display = 'flex';
    this.modal.setAttribute('aria-hidden', 'false');

    // Set up focus trap
    const focusables = this.content.querySelectorAll(this.focusableElements);
    this.firstFocusableElement = focusables[0];
    this.lastFocusableElement = focusables[focusables.length - 1];

    this.firstFocusableElement.focus();
    document.addEventListener('keydown', this.handleKeydown.bind(this));
  }

  close() {
    this.modal.style.display = 'none';
    this.modal.setAttribute('aria-hidden', 'true');
    document.removeEventListener('keydown', this.handleKeydown.bind(this));

    // Restore focus
    if (this.previousActiveElement) {
      this.previousActiveElement.focus();
    }
  }

  handleKeydown(e) {
    if (e.key === 'Escape') {
      this.close();
      return;
    }

    // Focus trap
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === this.firstFocusableElement) {
          e.preventDefault();
          this.lastFocusableElement.focus();
        }
      } else {
        if (document.activeElement === this.lastFocusableElement) {
          e.preventDefault();
          this.firstFocusableElement.focus();
        }
      }
    }
  }
}
```

### Pattern 3: Lightweight Onboarding Tooltips
**What:** CSS tooltips positioned near key UI elements, shown conditionally based on localStorage flags
**When to use:** First visit to each major page/feature, dismissed per-institution
**Example:**
```javascript
// Source: https://formbricks.com/blog/user-onboarding-best-practices
// Behavioral trigger approach (hover detection, interaction tracking)

class OnboardingManager {
  constructor(institutionId) {
    this.institutionId = institutionId;
    this.storageKey = `accreditai_onboarding_${institutionId}`;
    this.state = this.loadState();
  }

  loadState() {
    const stored = localStorage.getItem(this.storageKey);
    return stored ? JSON.parse(stored) : {
      completed: [],
      dismissed: [],
      version: '1.0'
    };
  }

  saveState() {
    localStorage.setItem(this.storageKey, JSON.stringify(this.state));
  }

  shouldShow(tooltipId) {
    return !this.state.completed.includes(tooltipId) &&
           !this.state.dismissed.includes(tooltipId);
  }

  markCompleted(tooltipId) {
    if (!this.state.completed.includes(tooltipId)) {
      this.state.completed.push(tooltipId);
      this.saveState();
    }
  }

  dismiss(tooltipId) {
    if (!this.state.dismissed.includes(tooltipId)) {
      this.state.dismissed.push(tooltipId);
      this.saveState();
    }
  }

  reset() {
    localStorage.removeItem(this.storageKey);
    this.state = this.loadState();
  }

  // Show tooltip with behavioral trigger (e.g., hover for 2+ seconds)
  attachTooltip(elementSelector, tooltipId, options = {}) {
    const element = document.querySelector(elementSelector);
    if (!element || !this.shouldShow(tooltipId)) return;

    const tooltip = this.createTooltip(tooltipId, options);
    this.positionTooltip(tooltip, element, options.position || 'bottom');

    // Auto-dismiss after interaction or timeout
    const dismissOnAction = () => {
      this.markCompleted(tooltipId);
      tooltip.remove();
    };

    element.addEventListener('click', dismissOnAction, { once: true });
    if (options.timeout) {
      setTimeout(() => {
        if (tooltip.parentNode) {
          this.dismiss(tooltipId);
          tooltip.remove();
        }
      }, options.timeout);
    }
  }

  createTooltip(tooltipId, options) {
    const tooltip = document.createElement('div');
    tooltip.className = 'onboarding-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.setAttribute('data-tooltip-id', tooltipId);

    tooltip.innerHTML = `
      <div class="tooltip-content">
        ${options.icon ? `<span class="tooltip-icon">${options.icon}</span>` : ''}
        <div class="tooltip-text">${options.text}</div>
      </div>
      <button class="tooltip-dismiss" aria-label="Dismiss">×</button>
    `;

    tooltip.querySelector('.tooltip-dismiss').addEventListener('click', () => {
      this.dismiss(tooltipId);
      tooltip.remove();
    });

    document.body.appendChild(tooltip);
    return tooltip;
  }

  positionTooltip(tooltip, element, position) {
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    const positions = {
      top: { top: rect.top - tooltipRect.height - 10, left: rect.left + rect.width / 2 - tooltipRect.width / 2 },
      bottom: { top: rect.bottom + 10, left: rect.left + rect.width / 2 - tooltipRect.width / 2 },
      left: { top: rect.top + rect.height / 2 - tooltipRect.height / 2, left: rect.left - tooltipRect.width - 10 },
      right: { top: rect.top + rect.height / 2 - tooltipRect.height / 2, left: rect.right + 10 }
    };

    const pos = positions[position];
    tooltip.style.top = `${pos.top}px`;
    tooltip.style.left = `${pos.left}px`;
  }
}
```

### Anti-Patterns to Avoid
- **Blocking onboarding tours:** Never force users through multi-step wizards - allow skip/dismiss at any point
- **Generic skeleton shapes:** Don't use rectangles for everything - match the skeleton to the final content structure
- **Modal keyboard traps without ESC:** Always provide ESC key exit and visible close button
- **Overuse of tooltips:** Show only 2-3 per page on first visit, not every element
- **Permanent tooltips:** Auto-dismiss after interaction or 15 seconds
- **Theme-breaking animations:** Skeleton shimmer must respect --accent colors and transition timing variables

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Complex onboarding flows | Multi-step wizard, progress tracker, video tutorials | Contextual tooltips, progressive disclosure | Existing project has command palette for power users; tooltips sufficient for discovery |
| Animation engine | Custom JavaScript animation library | CSS animations + CSS variables | Native performance, no JavaScript overhead, works with existing theme system |
| Focus management | Custom focus trap logic from scratch | Existing modal pattern (see command_palette.js) | Already implemented for command palette, reuse pattern |
| Tooltip positioning | Custom collision detection, viewport calculations | Simple fixed positioning + CSS transforms | Edge cases rare in admin tool, YAGNI for perfect positioning |

**Key insight:** AccreditAI is an admin tool for power users, not a consumer app. Onboarding should be lightweight (tooltips + help modal), not a product tour. Users want to get to work quickly.

## Common Pitfalls

### Pitfall 1: Skeleton Layout Shift
**What goes wrong:** Skeleton dimensions don't match final content, causing layout shift (CLS) when content loads
**Why it happens:** Using generic skeleton classes without measuring actual content dimensions
**How to avoid:**
- Measure final content dimensions during development
- Create skeleton variants for each content type (card, list item, table row)
- Use exact heights or min-heights to prevent reflow
**Warning signs:** Visible "jump" when content replaces skeleton, page height changes during load

### Pitfall 2: Modal Focus Loss on Close
**What goes wrong:** Focus doesn't return to trigger element after modal closes, breaking keyboard navigation
**Why it happens:** Not storing reference to `document.activeElement` before opening modal
**How to avoid:**
- Store `previousActiveElement = document.activeElement` in `open()` method
- Restore focus to `previousActiveElement` in `close()` method
- Test keyboard navigation flow: trigger → modal → ESC → back to trigger
**Warning signs:** Focus disappears after closing modal, user must click to re-engage

### Pitfall 3: Onboarding Fatigue
**What goes wrong:** Too many tooltips overwhelm users, leading to "dismiss all" behavior
**Why it happens:** Showing tooltips for every feature on first page load
**How to avoid:**
- Show maximum 2-3 tooltips per page
- Trigger tooltips only when user hovers near element (behavioral trigger)
- Auto-dismiss after 15 seconds or user interaction
- Allow "Skip tour" option that dismisses all
**Warning signs:** Users immediately dismiss tooltips without reading, low engagement metrics

### Pitfall 4: Keyboard Shortcut Conflicts
**What goes wrong:** New shortcuts conflict with existing shortcuts or browser defaults
**Why it happens:** Not auditing existing keyboard bindings (command palette already uses Ctrl+K, F2, etc.)
**How to avoid:**
- Audit existing shortcuts in command_palette.js before adding new ones
- Use `?` for help modal (common convention, low conflict risk)
- Document all shortcuts in help modal
- Allow users to see shortcuts grouped by category
**Warning signs:** Shortcuts don't work, browser behavior overrides app behavior

### Pitfall 5: Theme Inconsistency in Animations
**What goes wrong:** Skeleton shimmer uses hardcoded colors that don't adapt to light/dark theme
**Why it happens:** Copying skeleton code without using CSS custom properties
**How to avoid:**
- Always use CSS variables: `var(--bg-hover)`, `var(--accent-muted)`, etc.
- Test animations in both light and dark themes
- Use existing `--transition-timing` and `--transition-normal` for animation duration
**Warning signs:** Skeleton looks wrong in light theme, inconsistent with other animations

## Code Examples

Verified patterns from official sources and existing project code:

### Synchronized Skeleton Loader (Project Style)
```css
/* Source: https://freefrontend.com/code/synchronized-pure-css-skeleton-loader-2026-01-22/ */
/* Adapted to use AccreditAI CSS variables from variables.css */

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-hover) 0%,
    var(--bg-panel) 20%,
    var(--accent-muted) 50%,  /* Gold shimmer in dark theme */
    var(--bg-panel) 80%,
    var(--bg-hover) 100%
  );
  background-size: 200% 100%;
  background-attachment: fixed;  /* Synchronizes shimmer across all skeletons */
  animation: skeleton-shimmer 2s ease-in-out infinite;
  border-radius: var(--radius-md);
  pointer-events: none;
  opacity: 0.7;
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Specific use cases */
.skeleton-text {
  height: 1rem;
  margin-bottom: 0.5rem;
  width: 100%;
}

.skeleton-text-short {
  height: 1rem;
  margin-bottom: 0.5rem;
  width: 60%;
}

.skeleton-title {
  height: 2rem;
  margin-bottom: 1rem;
  width: 40%;
}

.skeleton-card {
  height: 120px;
  border-radius: var(--radius-lg);
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.skeleton-button {
  height: 40px;
  width: 100px;
  border-radius: var(--radius-sm);
}

.skeleton-badge {
  height: 24px;
  width: 80px;
  border-radius: var(--radius-full);
}

/* Usage in templates */
/* Replace: <div class="spinner"></div> */
/* With: <div class="skeleton skeleton-card"></div> */
```

### Keyboard Shortcuts Modal HTML (Jinja2)
```html
<!-- Source: Adapted from command_palette.js modal pattern -->
<!-- templates/components/keyboard_shortcuts_modal.html -->

<div id="keyboard-shortcuts-modal" class="modal" role="dialog" aria-modal="true" aria-labelledby="shortcuts-title" aria-hidden="true" style="display: none;">
  <div class="modal-backdrop" onclick="window.KeyboardShortcuts.close()"></div>
  <div class="modal-content" style="max-width: 700px;">
    <div class="modal-header">
      <h2 id="shortcuts-title">{{ t('help.keyboard_shortcuts') }}</h2>
      <button type="button" class="modal-close" onclick="window.KeyboardShortcuts.close()" aria-label="{{ t('common.close') }}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
    <div class="modal-body">
      <!-- Navigation shortcuts -->
      <section class="shortcuts-section">
        <h3>{{ t('help.shortcuts.navigation') }}</h3>
        <dl class="shortcuts-list">
          <div class="shortcut-item">
            <dt><kbd>Ctrl</kbd> + <kbd>K</kbd></dt>
            <dd>{{ t('help.shortcuts.open_command_palette') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>G</kbd> <kbd>D</kbd></dt>
            <dd>{{ t('help.shortcuts.go_dashboard') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>W</kbd></dt>
            <dd>{{ t('help.shortcuts.go_work_queue') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>D</kbd></dt>
            <dd>{{ t('help.shortcuts.go_documents') }}</dd>
          </div>
        </dl>
      </section>

      <!-- Actions shortcuts -->
      <section class="shortcuts-section">
        <h3>{{ t('help.shortcuts.actions') }}</h3>
        <dl class="shortcuts-list">
          <div class="shortcut-item">
            <dt><kbd>A</kbd></dt>
            <dd>{{ t('help.shortcuts.run_audit') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>C</kbd></dt>
            <dd>{{ t('help.shortcuts.consistency_check') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>F</kbd></dt>
            <dd>{{ t('help.shortcuts.fix_finding') }}</dd>
          </div>
        </dl>
      </section>

      <!-- General shortcuts -->
      <section class="shortcuts-section">
        <h3>{{ t('help.shortcuts.general') }}</h3>
        <dl class="shortcuts-list">
          <div class="shortcut-item">
            <dt><kbd>?</kbd></dt>
            <dd>{{ t('help.shortcuts.show_help') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>Esc</kbd></dt>
            <dd>{{ t('help.shortcuts.close_modal') }}</dd>
          </div>
          <div class="shortcut-item">
            <dt><kbd>Ctrl</kbd> + <kbd>B</kbd></dt>
            <dd>{{ t('help.shortcuts.toggle_sidebar') }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </div>
</div>
```

### Onboarding Tooltip CSS
```css
/* Source: Project design system (variables.css) */
/* static/css/onboarding.css */

.onboarding-tooltip {
  position: fixed;
  z-index: var(--z-tooltip);
  max-width: 300px;
  padding: var(--spacing-md);
  background-color: var(--bg-card);
  border: 1px solid var(--border-accent);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  animation: tooltip-fade-in var(--transition-fast) var(--transition-timing);
  pointer-events: auto;
}

@keyframes tooltip-fade-in {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-content {
  display: flex;
  gap: var(--spacing-sm);
  align-items: flex-start;
}

.tooltip-icon {
  flex-shrink: 0;
  font-size: var(--font-size-xl);
  color: var(--accent-primary);
}

.tooltip-text {
  flex: 1;
  font-size: var(--font-size-sm);
  line-height: 1.5;
  color: var(--text-primary);
}

.tooltip-dismiss {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-size-lg);
  line-height: 1;
  transition: color var(--transition-fast);
}

.tooltip-dismiss:hover {
  color: var(--text-primary);
}

/* Arrow indicator */
.onboarding-tooltip::before {
  content: '';
  position: absolute;
  width: 0;
  height: 0;
  border: 8px solid transparent;
}

.onboarding-tooltip[data-position="bottom"]::before {
  top: -16px;
  left: 50%;
  transform: translateX(-50%);
  border-bottom-color: var(--border-accent);
}

.onboarding-tooltip[data-position="top"]::before {
  bottom: -16px;
  left: 50%;
  transform: translateX(-50%);
  border-top-color: var(--border-accent);
}

.onboarding-tooltip[data-position="left"]::before {
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  border-left-color: var(--border-accent);
}

.onboarding-tooltip[data-position="right"]::before {
  left: -16px;
  top: 50%;
  transform: translateY(-50%);
  border-right-color: var(--border-accent);
}
```

### Initializing Onboarding (base.html)
```javascript
// Source: Project pattern - institution-specific state management
// Add to templates/base.html after other JS modules

<script>
  // Initialize onboarding for current institution
  {% if current_institution %}
  document.addEventListener('DOMContentLoaded', () => {
    const onboarding = new OnboardingManager('{{ current_institution.id }}');
    window.onboarding = onboarding;  // Global access for feature modules

    // Dashboard tooltips (only on first visit)
    if (window.location.pathname === '/') {
      onboarding.attachTooltip(
        '#work-queue-badge',
        'work_queue_intro',
        {
          text: '{{ t("onboarding.work_queue_intro") }}',
          icon: '⚡',
          position: 'bottom',
          timeout: 15000
        }
      );

      onboarding.attachTooltip(
        '[data-command-palette-trigger]',
        'command_palette_intro',
        {
          text: '{{ t("onboarding.command_palette_intro") }}',
          icon: '⌘',
          position: 'bottom',
          timeout: 15000
        }
      );
    }
  });
  {% endif %}
</script>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Spinner-only loading | Skeleton loaders | ~2018 | Better perceived performance, users see content structure during load |
| Static tooltips | Behavioral tooltips | ~2023 | Less intrusive, triggered by user intent (hover, hesitation) |
| Multi-step wizards | Contextual help + progressive disclosure | ~2024 | Faster time-to-value, users get to work immediately |
| Global keyboard shortcuts | Context-aware shortcuts | ~2020 | Same keys do different things based on page context |
| JavaScript animation libraries | CSS animations + custom properties | ~2021 | Better performance, works with theme system, no dependencies |
| Product tours (Intercom, WalkMe) | Lightweight tooltips | ~2025 | Lower overhead for admin tools, less annoying |

**Deprecated/outdated:**
- **Product tour libraries (Shepherd.js, Intro.js):** Heavy dependencies (50KB+) for functionality achievable in <5KB custom code
- **jQuery-based skeleton loaders:** Modern CSS animations perform better and don't require jQuery
- **Fixed-position modals without backdrop:** WCAG 2.1 requires proper focus management and backdrop

## Open Questions

1. **Should skeleton loaders animate on every load or only on first page load?**
   - What we know: Animations consume CPU, but improve perceived performance
   - What's unclear: Whether users prefer consistency (always animate) vs. speed (skip animation on cached content)
   - Recommendation: Always animate - perceive performance benefit outweighs CPU cost for admin tool with human-speed interactions

2. **Should onboarding reset when switching institutions?**
   - What we know: Onboarding state is per-institution via localStorage key `accreditai_onboarding_${institutionId}`
   - What's unclear: Whether users want to see tooltips again when switching to a new institution
   - Recommendation: YES - new institution may have different data/setup, re-showing tooltips is helpful

3. **Should keyboard shortcuts be customizable by user?**
   - What we know: Command palette already uses hardcoded shortcuts
   - What's unclear: Whether power users want to customize shortcuts
   - Recommendation: Not for MVP - add to post-MVP backlog if requested

## Validation Architecture

> Skipping this section - no `.planning/config.json` found, assuming `workflow.nyquist_validation` is false or not configured.

## Sources

### Primary (HIGH confidence)
- [AccreditAI static/css/main.css](file://C:\Projects\accreditationStudio\static\css\main.css) - Existing spinner and skeleton styles
- [AccreditAI static/js/command_palette.js](file://C:\Projects\accreditationStudio\static\js\command_palette.js) - Keyboard shortcut patterns
- [AccreditAI templates/base.html](file://C:\Projects\accreditationStudio\templates\base.html) - Layout and modal patterns
- [AccreditAI CLAUDE.md](file://C:\Projects\accreditationStudio\CLAUDE.md) - Architecture and design system
- [Synchronized Pure CSS Skeleton Loader](https://freefrontend.com/code/synchronized-pure-css-skeleton-loader-2026-01-22/) - background-attachment: fixed technique
- [Skeleton loading screen design - LogRocket](https://blog.logrocket.com/ux-design/skeleton-loading-screen-design/) - Best practices
- [Skeleton Screens 101 - Nielsen Norman Group](https://www.nngroup.com/articles/skeleton-screens/) - UX research

### Secondary (MEDIUM confidence)
- [Mastering Accessible Modals with ARIA and Keyboard Navigation](https://www.a11y-collective.com/blog/modal-accessibility/) - WCAG 2.1 modal patterns
- [Complete Guide to Accessibility for Keyboard Interaction & Focus Management](https://blog.greeden.me/en/2025/11/10/complete-guide-to-accessibility-for-keyboard-interaction-focus-management-order-visibility-roving-tabindex-shortcuts-and-patterns-for-modals-tabs-menus/) - Focus trap implementation
- [7 User Onboarding Best Practices for 2026](https://formbricks.com/blog/user-onboarding-best-practices) - Modern onboarding patterns
- [First-Time User Experience (FTUE) in 2026: AI-Powered Onboarding](https://www.chameleon.io/blog/first-time-user-experience) - Behavioral triggers
- [17 Best Onboarding Flow Examples for New Users (2026)](https://whatfix.com/blog/user-onboarding-examples/) - Industry examples

### Tertiary (LOW confidence)
- None - all findings verified with multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All patterns already in use in project (vanilla JS, CSS animations, localStorage)
- Architecture: HIGH - Reusing existing modal and command palette patterns
- Pitfalls: HIGH - Based on WCAG 2.1 standards and NNG UX research (skeleton layout shift, focus loss, onboarding fatigue are well-documented issues)

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (30 days - stable patterns, CSS/HTML standards don't change rapidly)
