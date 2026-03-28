---
phase: 9-05
type: research
created: 2026-03-27
---

# Phase 9-05: Enhanced Batch Processing - Research

## Current State

### Existing Infrastructure
- **BatchService** (801 lines): Cost estimation, batch creation, Anthropic API integration
- **Database**: `batch_operations` (19 cols), `batch_items` (16 cols)
- **API**: 7 endpoints for CRUD, stats, Anthropic submission
- **UI**: batch_history.html with stats, table, detail modal

### Gaps Identified
| Feature | Current | Needed |
|---------|---------|--------|
| Queue visibility | API-only | Real-time dashboard |
| Scheduling | Manual only | Cron-based automation |
| Priority | None | 4-level priority system |
| Templates | None | Save/reuse configurations |

## Technical Approach

### Plan 9-05-01: Queue Monitoring & Batch Templates

**New Files:**
- `src/services/batch_queue_service.py` — Queue inspection, depth metrics
- `src/services/batch_template_service.py` — Template CRUD, execute
- `src/core/models/batch_templates.py` — BatchTemplate dataclass
- `src/api/batch_queue_bp.py` — Queue status, template endpoints
- `src/db/migrations/0040_batch_templates.sql`
- Update `templates/institutions/batch_history.html` — Add queue monitor card

**Database:**
```sql
CREATE TABLE batch_templates (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  operation_type TEXT NOT NULL,
  document_ids TEXT NOT NULL,  -- JSON array
  concurrency INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

**API Endpoints:**
```
GET  /api/batches/queue/status    # Active/pending/completed counts
GET  /api/batch-templates         # List templates
POST /api/batch-templates         # Create template
GET  /api/batch-templates/<id>    # Get template
PUT  /api/batch-templates/<id>    # Update template
DELETE /api/batch-templates/<id>  # Delete template
POST /api/batch-templates/<id>/execute  # Execute template as new batch
```

### Plan 9-05-02: Batch Scheduling

**New Files:**
- `src/services/batch_schedule_service.py` — Schedule CRUD, APScheduler integration
- `src/core/models/batch_schedules.py` — BatchSchedule dataclass
- `src/api/batch_schedule_bp.py` — Schedule endpoints
- `src/db/migrations/0041_batch_schedules.sql`
- `templates/batch_scheduling.html` — Schedule manager UI

**Database:**
```sql
CREATE TABLE batch_schedules (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  template_id TEXT REFERENCES batch_templates(id),
  name TEXT NOT NULL,
  cron_expression TEXT NOT NULL,
  next_run TEXT,
  last_run TEXT,
  status TEXT DEFAULT 'active',  -- active, paused, deleted
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

**API Endpoints:**
```
GET  /api/batch-schedules         # List schedules
POST /api/batch-schedules         # Create schedule
PUT  /api/batch-schedules/<id>    # Update schedule
DELETE /api/batch-schedules/<id>  # Delete schedule
POST /api/batch-schedules/<id>/pause    # Pause schedule
POST /api/batch-schedules/<id>/resume   # Resume schedule
POST /api/batch-schedules/<id>/trigger  # Manual trigger
```

### Plan 9-05-03: Priority Queue

**Model Updates:**
- Add `priority_level` (1=critical, 2=high, 3=normal, 4=low) to batch_operations
- Add `sla_deadline` (optional) for critical batches

**Service Updates:**
- `BatchQueueService.reorder_queue()` — Re-sort by priority
- `BatchService.create_batch()` — Accept priority parameter

**API Updates:**
```
PATCH /api/batches/<id>/priority  # Change priority
```

**UI Updates:**
- Priority badge in batch table
- Priority selector in batch creation modal

## Estimated Scope

| Plan | Component | Lines |
|------|-----------|-------|
| 9-05-01 | Queue Service | 150 |
| 9-05-01 | Template Service | 200 |
| 9-05-01 | Template Model | 80 |
| 9-05-01 | API Blueprint | 200 |
| 9-05-01 | Migration | 30 |
| 9-05-01 | UI Updates | 150 |
| 9-05-02 | Schedule Service | 250 |
| 9-05-02 | Schedule Model | 80 |
| 9-05-02 | API Blueprint | 200 |
| 9-05-02 | Migration | 30 |
| 9-05-02 | UI Template | 300 |
| 9-05-03 | Priority Service | 150 |
| 9-05-03 | Model Updates | 50 |
| 9-05-03 | API Updates | 50 |
| 9-05-03 | UI Updates | 100 |
| **Total** | | **~2,000** |
