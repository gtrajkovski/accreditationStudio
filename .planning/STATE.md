# AccreditAI State

## Next Session: Start Here

**Accreditation Simulation feature complete!**

Files created:
- `src/db/migrations/0022_simulation.sql` - Tables for simulation runs, findings, risk
- `src/services/simulation_service.py` - Core orchestration and prediction logic
- `src/api/simulation.py` - 8 API endpoints with SSE streaming
- `templates/institutions/simulation.html` - UI with pass/fail badge, scores, findings

To verify:
```bash
python app.py  # Start server
# Navigate to institution → Simulation
# Run Quick Scan or Deep Audit
```

---

## Current Phase
**Phase 10: Analytics & Visualization** - Simulation complete

## Session Date
2026-03-14

## Just Completed (This Session)
1. **Evidence Coverage Map** - D3.js treemap, drill-down, gaps view
2. **Accreditation Simulation** - Mock audit with pass/fail prediction
   - Quick Scan (fast) and Deep Audit (thorough) modes
   - Aggregates findings across all documents
   - Predicts pass/conditional/fail with confidence
   - Risk assessment by category
   - Comparison between simulation runs
   - Historical trend chart

## Current Blueprints (30 total)
```
chat_bp, agents_bp, institutions_bp, standards_bp, settings_bp
readiness_bp, work_queue_bp, autopilot_bp, audits_bp, remediation_bp
checklists_bp, packets_bp, action_plans_bp, faculty_bp, catalog_bp
exhibits_bp, achievements_bp, interview_prep_bp, ser_bp, team_reports_bp
compliance_calendar_bp, document_reviews_bp, documents_bp
impact_analysis_bp, knowledge_graph_bp, timeline_planner_bp, site_visit_bp
coverage_map_bp, simulation_bp
```

## Remaining Backlog
| Priority | Feature | Description |
|----------|---------|-------------|
| 1 | **Multi-Institution Mode** | Consultant dashboard for 20-50 schools |
| 2 | **Evidence Highlighting** | Highlight exact sentences in documents |
| 3 | **Compliance Heatmap** | Matrix: documents × requirements |

## Repository
- Remote: https://github.com/gtrajkovski/accreditationStudio
- Branch: master
