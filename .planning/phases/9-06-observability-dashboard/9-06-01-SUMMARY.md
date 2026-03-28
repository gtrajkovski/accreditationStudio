---
phase: 9-06
plan: 01
title: "Observability Dashboard"
subsystem: observability
tags: [monitoring, metrics, dashboard, ai-costs, performance]
dependency_graph:
  requires: []
  provides: [observability-service, observability-api, observability-ui]
  affects: [app-config]
tech_stack:
  added: [Chart.js]
  patterns: [service-aggregation, polling-refresh, dark-theme-panels]
key_files:
  created:
    - src/services/observability_service.py
    - src/api/observability.py
    - templates/observability.html
    - static/css/observability.css
    - static/js/observability.js
  modified:
    - app.py
decisions:
  - Use module-level _start_time for uptime tracking (simple, no external deps)
  - 30-second auto-refresh interval (balance freshness vs load)
  - Chart.js CDN for cost trend chart (already used elsewhere in app)
metrics:
  duration_minutes: 7
  completed_date: "2026-03-28"
---

# Phase 9-06 Plan 01: Observability Dashboard Summary

ObservabilityService aggregating system health, AI costs, agent activity, and performance metrics with REST API and dashboard UI featuring Chart.js cost trends.

## Completed Tasks

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | ObservabilityService with metric aggregation | e6a18d5 | Service class with 4 metric methods + factory |
| 2 | Observability API blueprint | 64856fa | 3 endpoints: /metrics, /health, /costs |
| 3 | Register blueprint in app.py | 637c9f8 | Import, init, register, page route |
| 4 | Dashboard HTML template | 5f5b24c | 4 panels with Chart.js integration |
| 5 | Dashboard CSS styles | a385bb7 | Dark theme with metric cards |
| 6 | Dashboard JavaScript | a788bd9 | Auto-refresh, formatters, Chart.js |

## Files Created

1. **src/services/observability_service.py** (319 lines)
   - `ObservabilityService` class with `get_conn()` DB connection
   - `get_system_health()`: database size, uptime, table counts
   - `get_ai_costs(days)`: total cost, tokens, by-model, daily trend
   - `get_agent_activity()`: active/completed/failed counts, recent batches
   - `get_performance_metrics()`: queue depth, avg duration, throughput
   - `get_all_metrics()`: combined metrics with timestamp
   - `get_observability_service()` factory function

2. **src/api/observability.py** (69 lines)
   - Blueprint at `/api/observability`
   - `GET /metrics` - all metrics with optional days param
   - `GET /health` - lightweight health check
   - `GET /costs` - AI cost breakdown with days param
   - `init_observability_bp()` function

3. **templates/observability.html** (169 lines)
   - Extends base.html with gold accent theme
   - Header bar with status dot and time range selector
   - 4 metric panels in 2-column grid
   - Chart.js CDN for cost trend visualization

4. **static/css/observability.css** (366 lines)
   - `.obs-header` with status indicator
   - `.metric-panel` card styling
   - `.cost-summary` and `.model-breakdown`
   - `.activity-stats` with status colors
   - `.perf-metrics` with units
   - Responsive breakpoints at 1024px and 768px

5. **static/js/observability.js** (273 lines)
   - `loadMetrics()` with fetch to API
   - `updateHealthPanel()`, `updateCostsPanel()`, etc.
   - `formatSize()`, `formatUptime()`, `formatNumber()`, `formatCurrency()`
   - Chart.js line chart for daily cost trend
   - 30-second auto-refresh with `setInterval`
   - Time range selector event handling

## Files Modified

1. **app.py** (+10 lines)
   - Added import: `from src.api.observability import observability_bp, init_observability_bp`
   - Added tag: `{"name": "Observability", "description": "System metrics and monitoring"}`
   - Added init call: `init_observability_bp()`
   - Added registration: `app.register_blueprint(observability_bp)`
   - Added page route: `@app.route('/observability')` -> `observability_dashboard()`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/observability/metrics | All metrics (system_health, ai_costs, agent_activity, performance) |
| GET | /api/observability/health | Lightweight health check |
| GET | /api/observability/costs | AI cost breakdown with by_model and daily_trend |

Query parameters:
- `days` (int, default 30): Lookback period for AI costs

## Dashboard Panels

1. **System Health**: Database size, uptime, institution/document counts
2. **AI Costs**: Total cost, tokens, API calls, model breakdown, daily trend chart
3. **Agent Activity**: Active/completed/failed counts, recent batches list
4. **Performance**: Queue depth, avg batch duration, throughput per hour

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

Files verified:
- FOUND: src/services/observability_service.py
- FOUND: src/api/observability.py
- FOUND: templates/observability.html
- FOUND: static/css/observability.css
- FOUND: static/js/observability.js

Commits verified:
- FOUND: e6a18d5
- FOUND: 64856fa
- FOUND: 637c9f8
- FOUND: 5f5b24c
- FOUND: a385bb7
- FOUND: a788bd9
