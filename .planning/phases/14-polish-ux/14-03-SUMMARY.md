---
phase: 14-polish-ux
plan: 03
subsystem: frontend-ux
tags: [onboarding, tooltips, first-time-user-experience, localStorage]
completed_date: "2026-03-16T20:24:53Z"
duration_minutes: 10.5

dependencies:
  requires: []
  provides: [onboarding-system, contextual-tooltips, per-institution-state]
  affects: [dashboard, base-template, user-onboarding]

tech_stack:
  added: [OnboardingManager, tooltip-positioning, localStorage-state]
  patterns: [per-institution-persistence, auto-dismiss, interaction-tracking]

key_files:
  created:
    - static/js/onboarding.js (274 lines)
    - static/css/onboarding.css (184 lines)
  modified:
    - templates/base.html (onboarding initialization, command palette trigger button)
    - src/i18n/en-US.json (onboarding strings)
    - src/i18n/es-PR.json (onboarding strings)

decisions:
  - localStorage key format: accreditai_onboarding_{institutionId}
  - Auto-dismiss timeout: 15 seconds
  - Maximum tooltips per page: 2 (avoid overwhelming users)
  - Added visible command palette trigger button (search icon with Ctrl+K hint)
  - 500ms initialization delay to ensure DOM elements are visible
  - Tooltip positioning: viewport-aware with 20px boundaries

metrics:
  lines_of_code: 458
  files_created: 2
  files_modified: 3
  commits: 3
---

# Phase 14 Plan 03: Contextual Onboarding Tooltips Summary

**One-liner:** Lightweight onboarding system with per-institution localStorage state, auto-dismissing tooltips for work queue badge and command palette.

## What Was Built

Created a complete onboarding system for first-time users with contextual tooltips that guide them through key features:

1. **OnboardingManager JavaScript Class** (274 lines)
   - Per-institution state management via localStorage
   - Tracks completed vs dismissed tooltips separately
   - Auto-dismiss on timeout (15s) or interaction
   - Position-aware tooltips (top/bottom/left/right)
   - Viewport bounds checking
   - Resize handler for responsive positioning
   - Global access via `window.onboarding`

2. **Tooltip CSS** (184 lines)
   - Theme-compatible using CSS variables
   - Arrow indicators for 4 positions via `data-position` attribute
   - Fade-in animation with cubic-bezier easing
   - Gold accent border (--border-accent) matching "Certified Authority" theme
   - High z-index (--z-tooltip: 1500)
   - Responsive adjustments for mobile
   - Accessibility: reduced motion, high contrast support

3. **Base Template Integration**
   - Added command palette trigger button (search icon) in header
   - Linked onboarding.css and onboarding.js
   - OnboardingManager initialization for current institution
   - 2 dashboard tooltips: work queue badge, command palette trigger
   - 500ms delay ensures DOM readiness

4. **i18n Support**
   - en-US: work_queue_intro, command_palette_intro, dismiss, skip_tour
   - es-PR: Full Spanish translations

## Implementation Decisions

### State Management
- **localStorage key format:** `accreditai_onboarding_{institutionId}`
- **State structure:** `{ completed: [], dismissed: [], version: '1.0' }`
- **Separation of concerns:** "completed" = user interacted with feature; "dismissed" = user explicitly closed tooltip
- **Per-institution isolation:** Users see tooltips again when switching institutions

### Tooltip Behavior
- **Auto-dismiss timeout:** 15 seconds (long enough to read, short enough to not annoy)
- **Interaction-based dismissal:** Click on target element marks tooltip as "completed"
- **Explicit dismissal:** X button marks tooltip as "dismissed"
- **Maximum per page:** 2 tooltips (work queue + command palette on dashboard)
- **Positioning:** Viewport-aware with 20px minimum margins

### Command Palette UX Improvement
**Problem:** Command palette was keyboard-only (Ctrl+K) with no visual trigger.
**Solution:** Added search icon button in header with `data-command-palette-trigger` attribute.
**Benefits:**
- Visible affordance for new users
- Tooltip attachment point
- Still emphasizes keyboard shortcut in tooltip text

### Timing
- **500ms initialization delay:** Ensures DOM elements are fully rendered and visible before tooltip attachment
- **15-second timeout:** Balances user attention span with information retention

## Testing Guide

### First-Time User Flow
1. Start Flask app: `python app.py`
2. Clear localStorage: DevTools > Application > Local Storage > delete `accreditai_onboarding_*` keys
3. Visit dashboard (http://localhost:5003/)
4. **Expected:** 2 tooltips appear after 500ms
   - Work queue badge: "Your work queue shows pending tasks. Click to view details." with ⚡ icon
   - Command palette trigger: "Press Ctrl+K to quickly search and navigate anywhere." with ⌘ icon
5. Click work queue badge → tooltip dismisses immediately
6. Wait 15 seconds → command palette tooltip auto-dismisses
7. Refresh page → no tooltips (state persisted)

### State Verification
1. Open DevTools > Application > Local Storage
2. Key: `accreditai_onboarding_{institution_id}`
3. Value: `{"completed":["work_queue_intro"],"dismissed":["command_palette_intro"],"version":"1.0"}`

### Multi-Institution
1. Switch institutions via sidebar dropdown
2. Visit dashboard → tooltips reappear (new institution ID)
3. Verify separate localStorage keys for each institution

### Command Palette Trigger
1. Click search icon in header → command palette opens
2. Press Ctrl+K → command palette opens (existing behavior preserved)
3. Tooltip attached to button (visible on first visit)

### Accessibility
1. Toggle theme (light/dark) → tooltip colors adapt
2. Test keyboard navigation → dismiss button focusable
3. Reduce motion preference → no transform animation
4. High contrast mode → increased border width

## Deviations from Plan

**None** - Plan executed exactly as specified.

## Files Modified

### Created
- `static/js/onboarding.js` (274 lines)
  - OnboardingManager class
  - Methods: loadState, saveState, shouldShow, markCompleted, dismiss, reset, attachTooltip, createTooltip, positionTooltip, removeTooltip, dismissAll
  - Exported to window.OnboardingManager

- `static/css/onboarding.css` (184 lines)
  - Tooltip base styles
  - Arrow indicators for 4 positions
  - Fade-in animation
  - Responsive adjustments
  - Accessibility enhancements

### Modified
- `templates/base.html`
  - Added onboarding.css link in head
  - Added command palette trigger button in header-actions
  - Added onboarding.js script link
  - Added OnboardingManager initialization
  - Added dashboard tooltip attachments
  - Added command palette button click handler

- `src/i18n/en-US.json`
  - Added "onboarding" section with 4 strings

- `src/i18n/es-PR.json`
  - Added "onboarding" section with 4 Spanish translations

## Commits

| Hash | Message |
|------|---------|
| 66dd8e6 | feat(14-03): create OnboardingManager with localStorage state management |
| 1b32d30 | feat(14-03): create onboarding tooltip CSS with arrow indicators |
| 41a79c7 | feat(14-03): integrate onboarding system with dashboard tooltips |

## Self-Check: PASSED

### Files Exist
```bash
✓ static/js/onboarding.js (274 lines)
✓ static/css/onboarding.css (184 lines)
✓ templates/base.html (modified)
✓ src/i18n/en-US.json (modified)
✓ src/i18n/es-PR.json (modified)
```

### Commits Exist
```bash
✓ 66dd8e6 - feat(14-03): create OnboardingManager with localStorage state management
✓ 1b32d30 - feat(14-03): create onboarding tooltip CSS with arrow indicators
✓ 41a79c7 - feat(14-03): integrate onboarding system with dashboard tooltips
```

### Functionality Verified
- OnboardingManager exports to window ✓
- localStorage state management ✓
- CSS variables used (27 references) ✓
- Arrow indicators for 4 positions ✓
- i18n strings in both languages ✓
- Command palette trigger button added ✓
- Tooltips attached on dashboard ✓

## Next Steps

Phase 14 onboarding complete. This system can be extended to other pages:
- Compliance page: "Batch operations" tooltip
- Documents page: "Upload drag-and-drop" tooltip
- Standards page: "Filter by accreditor" tooltip

Pattern established:
```javascript
onboarding.attachTooltip(
  '#element-selector',
  'tooltip_id',
  {
    text: 'Tooltip text',
    icon: '🎯',
    position: 'bottom',
    timeout: 15000,
    dismissLabel: 'Dismiss'
  }
);
```
