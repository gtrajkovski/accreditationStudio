---
phase: 17-report-enhancements
plan: 03
subsystem: reporting
tags: [trend-chart, metric-customization, chart-js, localStorage]
dependency_graph:
  requires: [reports-api, readiness-service]
  provides: [trend-visualization, metric-preferences]
  affects: [reports-dashboard]
tech_stack:
  added: []
  patterns: [Chart.js line chart, localStorage persistence, time-range filtering]
key_files:
  created: []
  modified:
    - src/services/report_service.py
    - src/api/reports.py
    - templates/pages/reports.html
    - static/css/reports.css
    - static/js/reports.js
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - Use Chart.js line chart with area fill for trend visualization
  - Store metric preferences per-institution in localStorage (metric-prefs-{institution_id})
  - Readiness metric always visible (disabled checkbox)
  - Trend data returns date + readiness pairs from reports table metadata
metrics:
  duration: 14.4
  completed_date: "2026-03-21T17:38:39Z"
  tasks_completed: 3
  files_modified: 7
  commits: 3
---

# Phase 17 Plan 03: Trend Charts & Metric Customization Summary

**One-liner:** Readiness trend visualization with Chart.js line charts (30/60/90-day time ranges) and localStorage-persisted metric customization for executive summary

## Objective

Users can view readiness trend charts over time and customize which metrics appear in the executive summary.

## What Was Built

### 1. Readiness Trend Service & API (Task 1)

**Service Method (`src/services/report_service.py`):**
- Added `ReportService.get_readiness_trend(institution_id, days=30)` method
- Calculates cutoff date using `timedelta(days=days)`
- Queries reports table: `WHERE institution_id = ? AND generated_at >= ? ORDER BY generated_at ASC`
- Extracts `readiness_total` from metadata JSON field
- Returns list of `{date, readiness}` dicts sorted chronologically
- Handles JSON parsing errors gracefully (skips malformed records)

**API Endpoint (`src/api/reports.py`):**
- Added `GET /api/reports/institutions/:id/trend` endpoint
- Query parameter: `days` (default 30, max 365)
- Validates days parameter range (1-365)
- Returns `{success, trend, count}` JSON structure
- Error handling: 400 for validation, 500 for exceptions

**Commit:** `94612eb`

### 2. Trend Chart UI with Chart.js (Task 2)

**HTML (`templates/pages/reports.html`):**
- Added trend section after charts-grid with 30/60/90 day buttons
- Canvas element with `id="trend-chart"`
- Buttons have `data-days` attribute and `active` class for selected state

**CSS (`static/css/reports.css`):**
- Trend section styles (margin-top: 2rem)
- Trend button styles with hover and active states
- Active button uses accent color with white text

**JavaScript (`static/js/reports.js`):**
- `loadTrend(days=30)` method fetches from API and stores in `this.trendData`
- `renderTrendChart()` creates Chart.js line chart:
  - Line with area fill (rgba 0.1 opacity)
  - Accent color (#e94560)
  - Y-axis: 0-100 scale
  - X-axis: rotated labels (45°)
  - Custom tooltip with formatted date
- Destroys previous chart instance before creating new one (prevents memory leaks)
- Button click handlers toggle active class and reload chart
- Chart initialized in `init()` with 30-day default

**Commit:** `a38067a`

### 3. Metric Customization with localStorage (Task 3)

**HTML (`templates/pages/reports.html`):**
- Added section-header wrapper to hero-metrics with Customize button
- Added `data-metric` attributes to all metric cards (readiness, compliance, evidence, documents, consistency)
- Added metrics modal with checkbox form
- Readiness checkbox disabled (always visible)

**CSS (`static/css/reports.css`):**
- Section-header flex layout (justify-between)
- Checkbox group vertical layout (flex-direction: column)
- Checkbox styling (18px size)
- Disabled checkbox opacity (0.5, not-allowed cursor)
- `metric-card.hidden` class (display: none)
- Modal description styles

**JavaScript (`static/js/reports.js`):**
- `loadMetricPreferences()` - loads from localStorage on init
  - Key: `metric-prefs-{institution_id}`
  - Default: all metrics visible
- `applyMetricVisibility()` - shows/hides cards based on preferences
- `saveMetricPreferences(selectedMetrics)` - persists to localStorage
- `openMetricsModal()` - opens modal, sets checkboxes based on current preferences
- `closeMetricsModal()` - closes modal
- `handleMetricsSubmit(e)` - saves preferences, shows toast
- Event listeners for customize button, cancel button, form submit
- Called in `init()` before loading data

**i18n (`en-US.json`, `es-PR.json`):**
- Added 9 new keys:
  - `readiness_trend` / `Tendencia de Preparación`
  - `days` / `días`
  - `key_metrics` / `Métricas Clave`
  - `customize` / `Personalizar`
  - `customize_metrics` / `Personalizar Métricas`
  - `customize_metrics_help` / help text
  - `compare_reports`, `select_report`, `compare` (added by parallel plan)

**Commit:** `40e3779`

## Deviations from Plan

None - plan executed exactly as written.

## Technical Decisions

1. **localStorage key format:** `metric-prefs-{institution_id}` ensures preferences are institution-specific
2. **Chart.js configuration:** Used `maintainAspectRatio: false` for responsive height control
3. **Trend data structure:** Simple `{date, readiness}` pairs extracted from reports metadata
4. **Readiness always visible:** Disabled checkbox prevents users from hiding the primary metric
5. **Chart destruction:** Explicitly destroy previous chart instance before creating new one to prevent memory leaks

## Integration Points

- **Reports API:** New `/trend` endpoint provides time-series data
- **ReportService:** Extended with trend aggregation method
- **Reports Dashboard:** Integrated trend chart and customization UI
- **localStorage:** Client-side persistence for user preferences

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `src/services/report_service.py` | Added `get_readiness_trend` method | +30 |
| `src/api/reports.py` | Added trend endpoint with validation | +25 |
| `templates/pages/reports.html` | Trend section + metrics modal | +40 |
| `static/css/reports.css` | Trend + checkbox styles | +45 |
| `static/js/reports.js` | Trend loading/rendering + customization | +95 |
| `src/i18n/en-US.json` | 9 new translation keys | +9 |
| `src/i18n/es-PR.json` | 9 new translation keys | +9 |

## Verification

✅ `ReportService.get_readiness_trend` method exists and returns time-series data
✅ `GET /api/reports/institutions/:id/trend` endpoint returns trend data
✅ Reports page has trend chart with 30/60/90 day buttons
✅ Chart.js line chart renders with readiness data over time
✅ Metric customization button opens modal
✅ User can select which metrics to display
✅ Preferences persist in localStorage per institution
✅ i18n strings support English and Spanish

## Success Criteria Met

✅ User can click 30/60/90 day buttons to view different time ranges
✅ Trend chart renders with data points from reports in selected range
✅ Chart shows line with area fill and interactive tooltips
✅ User can click Customize button to open metrics modal
✅ User can check/uncheck metrics (except readiness which is always visible)
✅ Saving preferences hides/shows metric cards immediately
✅ Preferences persist across page reloads for each institution

## What's Next

Plan 17-03 complete. Ready for Phase 17 next plans (custom templates, report comparison).

## Self-Check: PASSED

✅ Files exist:
- `src/services/report_service.py` contains `get_readiness_trend`
- `src/api/reports.py` contains `get_institution_trend` endpoint
- `templates/pages/reports.html` contains `trend-chart` and `metrics-modal`
- `static/css/reports.css` contains `.trend-section` and `.checkbox-group`
- `static/js/reports.js` contains `loadTrend` and `loadMetricPreferences`

✅ Commits exist:
- `94612eb`: feat(17-03): add readiness trend service method and API endpoint
- `a38067a`: feat(17-03): add trend chart UI with Chart.js line chart
- `40e3779`: feat(17-03): add metric customization UI with localStorage persistence
