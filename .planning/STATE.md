# AccreditAI State

## URGENT TODO (Next Session)

**Document Upload Not Working** - The `documents_bp` blueprint exists in `src/api/documents.py` but is NOT registered in `app.py`.

Fix needed in `app.py`:
```python
# Add import
from src.api.documents import documents_bp, init_documents_bp

# Add initialization (after other init_*_bp calls)
init_documents_bp(workspace_manager)

# Add registration (after other register_blueprint calls)
app.register_blueprint(documents_bp)
```

Then test: `curl -X POST http://127.0.0.1:5006/api/institutions/inst_b2b4c7533e20/documents/upload -F "file=@test.txt" -F "doc_type=policy"`

---

## Current Phase
**Post-MVP Backlog** - Implementing feature enhancements

## Session Date
2026-03-08

## Backlog Progress

### Completed This Session
- ✅ Compliance History (line chart with 7d/30d/90d range, sub-scores toggle)
- ✅ Keyboard Shortcuts (G+D dashboard, G+C compliance sequences)
- ✅ Quick Actions FAB (floating button: Upload/Audit/Packet)
- ✅ Risk Alerts Banner (critical blockers on dashboard)
- ✅ Impact Analysis (fact-to-document dependencies, change simulation, auto-remediation)

### Remaining Backlog
- 🔲 Institutional Knowledge Graph - Facts as nodes
- 🔲 Accreditation Timeline Planner - Project management
- 🔲 Site Visit Mode - Fast search during visits
- 🔲 Multi-Institution Mode - Consultant dashboard
- 🔲 Evidence Highlighting - Highlight exact sentences
- 🔲 Global Search - Unified search across all content

## Milestone Summary

### Phase 8: Post-Visit + Ongoing ✅ COMPLETE
- ✅ Team Report Response Agent (8 tools: report parsing, finding categorization, response drafting)
- ✅ Compliance Calendar Agent (8 tools: events, deadlines, timeline generation, reminders)
- ✅ Document Review Agent (8 tools: scheduling, pending reviews, completion, bulk operations)
- ✅ Database migration (0016_team_reports.sql)
- ✅ Team Reports UI page
- ✅ Compliance Calendar UI page
- ✅ Document Reviews UI page

### Phase 7: Visit Prep ✅ COMPLETE
- ✅ Interview Prep Agent (7 tools: 9 roles, questions, talking points, red flags)
- ✅ SER Drafting Agent (8 tools: section drafting, draft/submission modes)
- ✅ UI Redesign ("Certified Authority" - gold accent, collapsible nav, readiness ring)
- ✅ Enhanced Checklist Agent (4 new tools: document validation, page references, linked export)
- ✅ Visit readiness page with mock evaluation support
- ✅ Database migration (0015_phase7.sql)

### Post-Phase 7 Improvements ✅ COMPLETE
- ✅ Dashboard session controls (pause/resume/cancel buttons)
- ✅ PAUSED session status added to SessionStatus enum
- ✅ New API endpoints: POST `/api/agents/sessions/<id>/pause`, `/resume`
- ✅ Session cards UI with real-time status updates

## Current Blueprints
- chat_bp, agents_bp, institutions_bp, standards_bp
- settings_bp, readiness_bp, work_queue_bp, autopilot_bp
- audits_bp, remediation_bp, checklists_bp
- packets_bp, action_plans_bp
- faculty_bp, catalog_bp, exhibits_bp, achievements_bp
- interview_prep_bp, ser_bp
- team_reports_bp, compliance_calendar_bp, document_reviews_bp

## Post-MVP Backlog
See FEATURE_PRIORITIES.md for potential future features:
- Compliance History (readiness over time graph)
- Risk Alerts Banner
- Impact Analysis
- Institutional Knowledge Graph
- Accreditation Timeline Planner
- Site Visit Mode (fast search)
- Multi-Institution Mode (consultant scale)
- Evidence Highlighting
- Global Search
- Quick Actions FAB
- Keyboard Shortcuts

## Repository
- Remote: https://github.com/gtrajkovski/accreditationStudio
- Branch: master
