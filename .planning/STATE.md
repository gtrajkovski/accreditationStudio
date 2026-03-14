# AccreditAI State

## Next Session: Start Here

**Evidence Coverage Map planned, ready to implement.** Plan file at:
`.claude/plans/sorted-plotting-trinket.md`

To continue:
```bash
# Review the plan, then implement:
# 1. src/services/coverage_map_service.py
# 2. src/api/coverage_map.py
# 3. templates/institutions/coverage_map.html
# 4. static/js/coverage_map.js
# 5. Register in app.py + add nav link
```

---

## Current Phase
**Phase 10: Planning & Search** - Evidence Coverage Map planned

## Session Date
2026-03-14

## Backlog Progress

### Ready to Implement
- **Evidence Coverage Map** (D3.js treemap visualization)
  - Plan complete in `.claude/plans/sorted-plotting-trinket.md`
  - Shows standards hierarchy with coverage %
  - Color-coded: green (strong) → red (missing)
  - Click to drill-down, see linked evidence
  - No new DB tables needed

### Just Completed (This Session)
- ✅ **Site Visit Mode** (Fast unified search during auditor visits)
  - Migration: `0021_site_visit.sql`
  - Service: `src/services/site_visit_service.py`
  - API: `src/api/site_visit.py` (6 endpoints)
  - UI: `templates/partials/site_visit_overlay.html`
  - JS: `static/js/site_visit_mode.js`
  - Shortcut: F2 or Ctrl+Shift+S

### Remaining Backlog
| Priority | Feature | Description |
|----------|---------|-------------|
| 1 | **Evidence Coverage Map** | ← NEXT (planned) |
| 2 | **Accreditation Simulation** | Mock audit with predicted findings |
| 3 | **Multi-Institution Mode** | Consultant dashboard for 20-50 schools |
| 4 | **Evidence Highlighting** | Highlight exact sentences in documents |
| 5 | **Compliance Heatmap** | Matrix: documents × requirements |

## Current Blueprints (28 total)
```
chat_bp, agents_bp, institutions_bp, standards_bp, settings_bp
readiness_bp, work_queue_bp, autopilot_bp, audits_bp, remediation_bp
checklists_bp, packets_bp, action_plans_bp, faculty_bp, catalog_bp
exhibits_bp, achievements_bp, interview_prep_bp, ser_bp, team_reports_bp
compliance_calendar_bp, document_reviews_bp, documents_bp
impact_analysis_bp, knowledge_graph_bp, timeline_planner_bp, site_visit_bp
```

## Recently Completed Features

### Phase 10: Analytics & Visualization ✅
- Compliance History (line chart, 7d/30d/90d)
- Keyboard Shortcuts (G+D, G+C sequences)
- Quick Actions FAB
- Risk Alerts Banner
- Impact Analysis (fact scanning, change simulation)
- Knowledge Graph (D3.js visualization, path finder)
- Timeline Planner (Gantt chart, templates)
- Site Visit Mode (fast unified search, F2 shortcut)

## Repository
- Remote: https://github.com/gtrajkovski/accreditationStudio
- Branch: master
- Latest commit: Site Visit Mode feature
