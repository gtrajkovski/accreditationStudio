# AccreditAI State

## Current Phase
Phase 3: Readiness Score + Command Center

## Session Date
2026-03-02

## What's Complete This Session

### Work Queue Screen (Full Implementation)
- **Work Queue Service** (`src/services/work_queue_service.py`):
  - `get_work_queue()` - Aggregates blockers, tasks, and approvals
  - `get_work_queue_summary()` - Summary counts by type/priority
  - `WorkItem` dataclass with type, priority, metadata
  - Sources: readiness blockers, human checkpoints, waiting sessions, task queue
- **API Blueprint** (`src/api/work_queue.py`):
  - `GET /api/work-queue` - List all work items with filters
  - `GET /api/work-queue/summary` - Summary counts
  - `GET /api/work-queue/institutions/<id>` - Institution-specific queue
- **UI** (`templates/work_queue.html`):
  - Summary cards (total, critical, blockers, approvals, tasks)
  - Filter tabs by type
  - Priority-sorted work items with action buttons
  - Auto-refresh every 30 seconds
  - Inline approve/reject for checkpoints
- **Navigation** - Added Work Queue link in sidebar
- **Tests** - `tests/test_work_queue_service.py` (8 tests)

### Readiness Score Computation (Full Implementation)
- **Migration 0009**: `consistency_issues` table
- **Migration 0010**: `institution_readiness_snapshots` + `institution_required_doc_types` tables
- **Readiness Service** (`src/services/readiness_service.py`):
  - `compute_readiness()` - Computes score with 4 sub-scores
  - `persist_snapshot()` - Stores historical snapshots
  - `get_next_actions()` - Rule-based action recommendations
  - `get_blockers()` - Prioritized blockers list
  - Cache management with 10-minute window

### Scoring Model
| Component | Weight | Penalties |
|-----------|--------|-----------|
| Compliance | 40% | Critical: -12, Significant: -7, Moderate: -5, Advisory: -3 |
| Evidence | 25% | Missing evidence: -8/-5/-2 by severity, Weak: -2 |
| Documents | 20% | Missing required: -15, Not indexed: -8 |
| Consistency | 15% | High: -10, Medium: -6, Low: -2 |

### API Endpoints
```
GET  /api/institutions/<id>/status        # Full readiness + breakdown
GET  /api/institutions/<id>/alerts        # Blockers + warnings
GET  /api/institutions/<id>/next-actions  # Prioritized recommendations
GET  /api/institutions/<id>/readiness/history  # Trend data
POST /api/institutions/<id>/readiness/invalidate  # Mark stale
```

### UI Updates
- Institution overview has Readiness Dashboard widget
- Animated circular score indicator
- Color-coded breakdown bars
- Blockers panel with Fix buttons
- Next Best Actions list with priorities

### Tests
- `tests/test_readiness_service.py` - Full test coverage

## Files Added/Modified
```
# Work Queue (this session)
src/services/work_queue_service.py (new)
src/api/work_queue.py (new)
templates/work_queue.html (new)
tests/test_work_queue_service.py (new)
src/services/__init__.py (updated exports)
src/api/__init__.py (updated exports)
app.py (registered blueprint + route)
templates/base.html (navigation link)

# Readiness Score (previous session)
src/db/migrations/0009_consistency.sql
src/db/migrations/0010_readiness.sql
src/services/readiness_service.py
src/api/readiness.py (rewritten)
src/agents/evidence_guardian.py
src/agents/base_agent.py (24 agents)
templates/institutions/overview.html (Command Center widgets)
tests/test_readiness_service.py
```

## Next Priorities (User Requested Features)

### High Impact Features for Daily Use
1. **Autopilot Nightly Run** - Scheduled re-index, audit, consistency check
2. ~~**Work Queue Screen**~~ - ✅ Complete
3. **Change Detection** - Diff on doc upload, targeted re-audit
4. **Evidence Coverage Contract** - Block packet export without evidence
5. **Audit Reproducibility** - Record prompt/version/hashes for defensibility

### Already Planned
- Task Rail Component (SSE streaming)
- Full Command Center Page
- Evidence Explorer
- Compliance Heatmap

## Key Commands
```bash
flask db upgrade          # Apply migrations (now includes 0009, 0010)
flask db status           # Check migration status
python app.py             # Run dev server on port 5003
pytest tests/test_readiness_service.py  # Run readiness tests
```

## Database
- Location: `workspace/_system/accreditai.db`
- New tables: `readiness_consistency_issues`, `institution_readiness_snapshots`, `institution_required_doc_types`
- Note: Renamed from `consistency_issues` to `readiness_consistency_issues` to avoid conflict with 0006 migration
- Seeded required doc types for ACCSC and COE
