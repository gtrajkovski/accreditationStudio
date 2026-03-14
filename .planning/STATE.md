# AccreditAI State

## Next Session: Start Here

**Site Visit Mode just completed.** To test it:
```bash
flask db upgrade              # Apply 0021_site_visit.sql
python app.py                 # Start server on port 5003
# Navigate to any institution page, press F2
```

**Pick next feature from backlog below.**

---

## Current Phase
**Phase 10: Planning & Search** - Site Visit Mode complete, continuing with remaining items

## Session Date
2026-03-14

## Backlog Progress

### Just Completed
- ✅ **Site Visit Mode** (Fast unified search during auditor visits)
  - Migration: `0021_site_visit.sql`
  - Service: `src/services/site_visit_service.py`
  - API: `src/api/site_visit.py` (6 endpoints)
  - UI: `templates/partials/site_visit_overlay.html`
  - JS: `static/js/site_visit_mode.js`
  - Shortcut: F2 or Ctrl+Shift+S
  - Searches: documents, standards, findings, faculty, truth index, knowledge graph

### Remaining Backlog (pick one)
| Priority | Feature | Description |
|----------|---------|-------------|
| 1 | **Global Search** | Unified search across standards, documents, findings |
| 2 | **Evidence Coverage Map** | Standard coverage percentages visualization |
| 3 | **Accreditation Simulation** | Mock audit with predicted findings |
| 4 | **Multi-Institution Mode** | Consultant dashboard for 20-50 schools |
| 5 | **Evidence Highlighting** | Highlight exact sentences in documents |
| 6 | **Compliance Heatmap** | Matrix: documents × requirements |

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

### Phase 8-9: Post-Visit + Ongoing ✅
- Team Report Response Agent
- Compliance Calendar Agent
- Document Review Agent

## Repository
- Remote: https://github.com/gtrajkovski/accreditationStudio
- Branch: master
- Latest commit: Site Visit Mode feature
