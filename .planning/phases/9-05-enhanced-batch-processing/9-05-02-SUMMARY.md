---
phase: 9-05-enhanced-batch-processing
plan: 02
subsystem: batch-scheduling
tags: [batch, scheduling, cron, apscheduler, automation]
dependency_graph:
  requires:
    - 9-05-01  # BatchTemplate service
  provides:
    - batch_schedule_service
    - batch_schedule_bp
    - batch_schedules table
  affects:
    - batch_template_service (execution triggers)
    - scheduler_service (get_scheduler export)
tech_stack:
  added:
    - croniter>=1.3.0  # Cron expression parsing
  patterns:
    - APScheduler job registration
    - Cron-based scheduling
key_files:
  created:
    - src/core/models/batch_schedules.py
    - src/services/batch_schedule_service.py
    - src/api/batch_schedule_bp.py
    - src/db/migrations/0041_batch_schedules.sql
    - templates/institutions/batch_scheduling.html
  modified:
    - src/core/models/__init__.py
    - src/services/scheduler_service.py
    - requirements.txt
    - app.py
decisions:
  - Soft-delete for schedules (status='deleted') to preserve history
  - Cron expression validation using croniter library
  - APScheduler job IDs prefixed with batch_schedule_ for namespacing
metrics:
  duration: ~8 minutes
  completed: 2026-03-28T16:28:20Z
---

# Phase 9-05 Plan 02: Batch Scheduling with APScheduler Summary

Cron-based batch scheduling with APScheduler for automated recurring batch operations.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 8d27d02 | feat | Add batch schedule model and migration |
| 3582f85 | feat | Add batch schedule service with APScheduler |
| 4c920bc | feat | Add batch schedule API and UI |

## What Was Built

### 1. BatchSchedule Model (`src/core/models/batch_schedules.py`)

Dataclass for scheduled batch configurations:

```python
@dataclass
class BatchSchedule:
    id: str                    # bsched_ prefix
    institution_id: str
    template_id: str           # References batch_templates
    name: str
    cron_expression: str       # e.g., "0 9 * * MON"
    next_run: Optional[str]    # Calculated from cron
    last_run: Optional[str]
    last_batch_id: Optional[str]
    status: str                # active, paused, deleted
    created_at: str
    updated_at: str
```

### 2. Database Migration (`0041_batch_schedules.sql`)

- `batch_schedules` table with FK to `institutions` and `batch_templates`
- Index on `(institution_id, status)` for listing
- Index on `(status, next_run)` for finding active schedules

### 3. BatchScheduleService (`src/services/batch_schedule_service.py`)

Full CRUD with APScheduler integration:

- `create_schedule()` - validates cron, calculates next_run, registers job
- `get_schedule()` / `list_schedules()` - standard retrieval
- `update_schedule()` - recalculates next_run if cron changes
- `delete_schedule()` - soft delete, removes scheduler job
- `pause_schedule()` / `resume_schedule()` - toggle job state
- `trigger_schedule()` - manual execution
- `register_all_active_schedules()` - startup hook

### 4. API Blueprint (`src/api/batch_schedule_bp.py`)

8 endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/institutions/{id}/batch-schedules` | List schedules |
| POST | `/api/institutions/{id}/batch-schedules` | Create schedule |
| GET | `/api/institutions/{id}/batch-schedules/{sid}` | Get schedule |
| PUT | `/api/institutions/{id}/batch-schedules/{sid}` | Update schedule |
| DELETE | `/api/institutions/{id}/batch-schedules/{sid}` | Delete schedule |
| POST | `/api/institutions/{id}/batch-schedules/{sid}/pause` | Pause |
| POST | `/api/institutions/{id}/batch-schedules/{sid}/resume` | Resume |
| POST | `/api/institutions/{id}/batch-schedules/{sid}/trigger` | Manual trigger |

### 5. Scheduling UI (`templates/institutions/batch_scheduling.html`)

- Schedule list table with status badges
- Cron expression reference panel with common presets
- Create/edit modal with template selector
- Pause/Resume/Run Now/Delete actions

### 6. Scheduler Service Enhancement

Added `get_scheduler()` export for external access to APScheduler instance.

## Integration Points

- **BatchTemplateService**: Schedules execute templates via `execute_template()`
- **APScheduler**: Jobs registered/removed on CRUD operations
- **Startup hook**: `init_batch_schedule_bp()` registers all active schedules

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verifications passed:
- BatchSchedule model imports and serializes correctly
- Migration SQL syntax valid
- BatchScheduleService imports without error
- Blueprint registers successfully
- Template file exists

## Self-Check: PASSED

- [x] `src/core/models/batch_schedules.py` exists
- [x] `src/services/batch_schedule_service.py` exists
- [x] `src/api/batch_schedule_bp.py` exists
- [x] `src/db/migrations/0041_batch_schedules.sql` exists
- [x] `templates/institutions/batch_scheduling.html` exists
- [x] Commits 8d27d02, 3582f85, 4c920bc exist
