---
phase: 9-05-enhanced-batch-processing
plan: 03
subsystem: batch-processing
tags: [priority-queue, queue-monitor, templates, ui-enhancement]
dependency_graph:
  requires:
    - 9-05-01 (BatchQueueService, BatchTemplateService)
    - 9-05-02 (Scheduled batches infrastructure)
  provides:
    - Priority queue support for batch operations
    - Queue monitoring UI with real-time updates
    - Template management UI
    - Priority change API endpoint
  affects:
    - BatchOperation model
    - BatchService
    - BatchQueueService
    - batch_queue_bp API
    - batch_history.html UI
tech_stack:
  added:
    - priority_level column in batch_operations table
    - Priority-based queue ordering
  patterns:
    - Real-time queue monitoring with 10s refresh interval
    - Priority badges with color coding (critical/high/normal/low)
    - Template CRUD with quick-launch buttons
key_files:
  created:
    - src/db/migrations/0042_batch_priority.sql
  modified:
    - src/core/models/batch.py
    - src/services/batch_service.py
    - src/services/batch_queue_service.py
    - src/api/batch_queue_bp.py
    - templates/institutions/batch_history.html
decisions:
  - Priority levels use integers 1-4 (critical, high, normal, low) for efficient sorting
  - Default priority is 3 (normal) to maintain backward compatibility
  - Only pending/running batches can have priority changed
  - Queue status refreshes every 10 seconds for real-time monitoring
metrics:
  duration_minutes: 6
  completed: 2026-03-28
  tasks_completed: 4
  files_modified: 6
---

# Phase 9-05 Plan 03: Priority Queue & UI Enhancements Summary

Priority queue support with real-time queue monitoring UI and template management for batch operations.

## One-Liner

Added batch priority levels (critical/high/normal/low) with migration, API endpoint, and enhanced batch history UI featuring queue monitor, templates section, and priority badges.

## Completed Tasks

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create migration for priority support | 8aa6111 | 0042_batch_priority.sql |
| 2 | Update BatchService with priority methods | 6705a7f | batch.py, batch_service.py |
| 3 | Add priority endpoint to batch_queue_bp | 9ef49bf | batch_queue_bp.py, batch_queue_service.py |
| 4 | Enhance batch_history.html with queue monitor | 6b26882 | batch_history.html |

## Implementation Details

### Migration (0042_batch_priority.sql)
- Added `priority_level` column (INTEGER DEFAULT 3)
- Added `sla_deadline` column (TEXT, optional)
- Created index on (status, priority_level, created_at) for efficient queue ordering
- Backfills existing records with priority_level = 3

### BatchOperation Model
- New field: `priority_level: int = 3`
- New field: `sla_deadline: Optional[str] = None`
- Updated to_dict() and from_dict() methods

### BatchService Updates
- `create_batch()` now accepts `priority_level` parameter
- New method: `update_priority(batch_id, priority_level)` for changing batch priority
- `list_batches()` now orders by priority_level ASC, created_at DESC
- Helper method: `_priority_name(level)` converts level to name

### API Endpoint
- `PATCH /api/institutions/{id}/batches/{batch_id}/priority`
- Validates priority_level is 1-4
- Verifies batch belongs to institution
- Only allows changes for pending/running batches

### BatchQueueService
- Active batches query now includes priority_level
- Orders active batches by priority_level ASC, created_at ASC

### UI Enhancements (batch_history.html)
1. **Queue Monitor Card**
   - Real-time counts: Pending, Running, Completed, Failed, Queue Depth
   - Active batches with progress bars and priority badges
   - Auto-refresh every 10 seconds

2. **Templates Section**
   - Grid layout with template cards
   - Quick-launch "Run" button for each template
   - Create/Delete template actions
   - Template modal with document multi-select

3. **Batch Table**
   - New Priority column with color-coded badges
   - Priority badges: critical (red), high (yellow), normal (gray), low (dark gray)

4. **Batch Detail Modal**
   - Shows current priority with badge
   - Priority change buttons for pending/running batches
   - Buttons highlight current selection

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- [x] Migration file created and SQL syntax validated
- [x] BatchService imports without errors
- [x] batch_queue_bp imports without errors
- [x] Template contains "Queue Monitor" section
- [x] App imports successfully

## Self-Check: PASSED

- FOUND: src/db/migrations/0042_batch_priority.sql
- FOUND: Commit 8aa6111 (migration)
- FOUND: Commit 6705a7f (batch service)
- FOUND: Commit 9ef49bf (API endpoint)
- FOUND: Commit 6b26882 (UI enhancement)
