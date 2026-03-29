---
phase: "39"
plan: "02"
title: "Packet Studio Wizard UI"
subsystem: "wizard-ui"
tags: ["wizard", "ui", "templates", "javascript", "css", "i18n"]
depends_on:
  requires: ["39-01"]
  provides: ["wizard-ui", "wizard-template", "wizard-styles"]
  affects: ["packets", "submissions"]
tech_stack:
  added: []
  patterns: ["wizard-pattern", "drag-drop", "step-navigation"]
key_files:
  created:
    - "static/css/packet_wizard.css"
    - "static/js/packet_wizard.js"
    - "templates/institutions/packet_wizard.html"
  modified:
    - "src/i18n/en-US.json"
    - "src/i18n/es-PR.json"
    - "app.py"
decisions:
  - "Used step-based wizard pattern matching bulk_remediation.html"
  - "CSS uses project design system variables"
  - "JavaScript controller manages all 5 steps client-side"
  - "Full i18n support for both English and Spanish"
metrics:
  duration: "~7 minutes"
  completed: "2026-03-29T15:02:13Z"
---

# Phase 39 Plan 02: Packet Studio Wizard UI Summary

5-step visual wizard for building submission packets with step indicators, drag-drop evidence mapping, narrative editor, and live preview.

## Completed Tasks

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create CSS for 5-step wizard | `08d023f` | `static/css/packet_wizard.css` |
| 2 | Create JavaScript controller | `702502b` | `static/js/packet_wizard.js` |
| 3 | Create HTML template | `04b67cf` | `templates/institutions/packet_wizard.html` |
| 4 | Add i18n strings and route | `eca40c8` | `src/i18n/en-US.json`, `src/i18n/es-PR.json`, `app.py` |

## Implementation Details

### CSS Styles (1081 lines)
- Step progress indicator with numbered circles and connecting line
- Submission type card grid with hover/selected states
- Standards tree with collapsible sections and checkboxes
- Evidence mapping with drag-drop zones and AI suggest button
- Narrative editor panel with sections list and rich textarea
- Live preview with TOC and document rendering
- Responsive layouts for tablets and mobile
- Uses CSS variables from design system (`--accent`, `--bg-panel`, etc.)

### JavaScript Controller (1130 lines)
- `PacketWizard` object managing:
  - State: `submissionType`, `accreditor`, `packetName`, `selectedStandards`, `evidenceMapping`, `narratives`
  - Navigation: `goToStep()`, `prevStep()`, `nextStep()`, `validateStep()`
  - Standards: `renderStandardsTree()`, `toggleSection()`, `toggleStandard()`
  - Evidence: `renderEvidenceMapping()`, `onDragStart()`, `onDrop()`, `aiSuggestEvidence()`
  - Narrative: `generateNarrative()`, `saveNarrativeContent()`
  - Preview: `renderPreview()`, `buildEvidenceIndex()`
  - Export: `exportPacket()` with validation

### HTML Template (313 lines)
- Extends `base.html` with `page_header` macro
- 5 wizard steps with visual indicators
- Step 1: Submission type cards (self-study, response, teach-out, annual, substantive change)
- Step 2: Standards tree with section toggles and selection shortcuts
- Step 3: Evidence pool with drag handles and mapping drop zones
- Step 4: Narrative editor with sections list and AI generate buttons
- Step 5: Live preview with TOC and document preview pane
- Navigation footer with back/next/export buttons

### i18n Support
- Added `wizard.*` namespace with 65 keys
- Full Spanish translations in es-PR.json
- Keys cover all steps, buttons, validation messages

### Page Route
- Added `/institutions/<id>/packet-wizard` route in `app.py`
- Renders `packet_wizard.html` with institution context

## Verification

- [x] App imports without errors (`python -c "import app"`)
- [x] All files created at correct paths
- [x] CSS uses design system variables
- [x] JavaScript integrates with API endpoints from 39-01
- [x] i18n keys added for both locales

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] `static/css/packet_wizard.css` exists (22564 bytes)
- [x] `static/js/packet_wizard.js` exists (41413 bytes)
- [x] `templates/institutions/packet_wizard.html` exists (15342 bytes)
- [x] Commit `08d023f` exists (CSS)
- [x] Commit `702502b` exists (JavaScript)
- [x] Commit `04b67cf` exists (HTML template)
- [x] Commit `eca40c8` exists (i18n + route)
