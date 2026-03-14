# AccreditAI State

## Next Session: Start Here

**Timeline Planner just completed.** To test it:
```bash
flask db upgrade              # Apply 0020_timeline_planner.sql
python app.py                 # Start server on port 5003
# Navigate to: /institutions/<id>/timeline-planner
```

**Pick next feature from backlog below.**

---

## Current Phase
**Phase 10: Planning & Search** - Timeline Planner complete, continuing with remaining items

## Session Date
2026-03-14

## Backlog Progress

### Just Completed
- ✅ **Timeline Planner** (Gantt chart, phases, milestones, 4 templates)
  - Migration: `0020_timeline_planner.sql`
  - API: `src/api/timeline_planner.py` (15+ endpoints)
  - UI: `templates/institutions/timeline_planner.html` (D3.js Gantt)
  - Route: `/institutions/<id>/timeline-planner`

### Remaining Backlog (pick one)
| Priority | Feature | Description |
|----------|---------|-------------|
| 1 | **Site Visit Mode** | Fast search during auditor visits |
| 2 | **Global Search** | Unified search across standards, documents, findings |
| 3 | **Evidence Coverage Map** | Standard coverage percentages visualization |
| 4 | **Accreditation Simulation** | Mock audit with predicted findings |
| 5 | **Multi-Institution Mode** | Consultant dashboard for 20-50 schools |
| 6 | **Evidence Highlighting** | Highlight exact sentences in documents |
| 7 | **Compliance Heatmap** | Matrix: documents × requirements |

## Current Blueprints (27 total)
```
chat_bp, agents_bp, institutions_bp, standards_bp, settings_bp
readiness_bp, work_queue_bp, autopilot_bp, audits_bp, remediation_bp
checklists_bp, packets_bp, action_plans_bp, faculty_bp, catalog_bp
exhibits_bp, achievements_bp, interview_prep_bp, ser_bp, team_reports_bp
compliance_calendar_bp, document_reviews_bp, documents_bp
impact_analysis_bp, knowledge_graph_bp, timeline_planner_bp
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

### Phase 8-9: Post-Visit + Ongoing ✅
- Team Report Response Agent
- Compliance Calendar Agent
- Document Review Agent

## Repository
- Remote: https://github.com/gtrajkovski/accreditationStudio
- Branch: master
- Latest commit: Timeline Planner feature
