---
phase: 12-bulk-operations
plan: 01
subsystem: batch-operations
tags: [batch, cost-estimation, orchestration, foundation]

dependency_graph:
  requires: []
  provides:
    - batch_operations_schema
    - batch_domain_models
    - batch_service_with_cost_estimation
  affects:
    - src/db/migrations/
    - src/core/models.py
    - src/services/

tech_stack:
  added:
    - SQLite tables for batch tracking
    - BatchOperation/BatchItem dataclasses
    - Anthropic pricing calculations
  patterns:
    - Database migration with foreign keys and constraints
    - Cost estimation with safety margin (1.2x)
    - Batch orchestration service pattern

key_files:
  created:
    - src/db/migrations/0025_bulk_operations.sql
    - tests/test_batch_service.py
  modified:
    - src/core/models.py

decisions:
  - title: "Safety margin for cost estimates"
    choice: "Applied 1.2x multiplier to token estimates"
    rationale: "Accounts for variability in document complexity and agent behavior"
    alternatives: ["No safety margin", "2x margin (too conservative)"]
  - title: "Concurrency limits"
    choice: "1-5 range with default of 3"
    rationale: "Prevents API rate limits while allowing flexible throughput"
    alternatives: ["Fixed concurrency", "Unlimited concurrency"]
  - title: "Batch item status tracking"
    choice: "Separate batch_items table with individual statuses"
    rationale: "Enables granular progress tracking and retry logic"
    alternatives: ["Store items as JSON in batch_operations", "No item-level tracking"]

metrics:
  duration_minutes: 8
  tasks_completed: 3
  files_created: 2
  files_modified: 1
  commits: 3
  tests_added: 11
  test_pass_rate: 100%
  lines_added: 425
  completed_at: "2026-03-16T15:48:51Z"
---

# Phase 12 Plan 01: Batch Operations Foundation Summary

**One-liner:** Database schema, domain models, and cost estimation service for tracking bulk audit/remediation operations with Anthropic API pricing.

## What Was Built

Created the foundational layer for batch operations that enables:

1. **Database persistence** - `batch_operations` and `batch_items` tables with foreign keys, indexes, and constraints
2. **Domain models** - `BatchOperation` and `BatchItem` dataclasses with serialization
3. **Cost estimation** - Pre-operation cost calculation based on Anthropic pricing and empirical token usage
4. **Batch orchestration** - `BatchService` with CRUD, progress tracking, and cancellation

## Key Components

### Database Schema (0025_bulk_operations.sql)

**batch_operations table:**
- Tracks overall batch metadata (institution, operation type, counts, costs)
- Status lifecycle: pending → running → completed/cancelled/failed
- Concurrency control (1-5 range)
- Parent batch support for chained operations

**batch_items table:**
- Per-document progress tracking
- Links to TaskQueue via `task_id`
- Captures token usage and findings count
- Stores result paths and error messages

**Indexes:**
- `idx_batch_operations_institution` - Fast institution queries
- `idx_batch_operations_status` - Status filtering
- `idx_batch_items_batch` - Batch item lookups
- `idx_batch_items_status` - Item status filtering

### Domain Models (models.py)

**BatchStatus enum:**
```python
PENDING, RUNNING, COMPLETED, CANCELLED, FAILED
```

**BatchOperation:**
- Aggregates batch metadata and items
- Tracks estimated vs actual costs
- Supports metadata JSON for retry info and failed item tracking

**BatchItem:**
- Individual document processing record
- Captures input/output tokens and duration
- Links to document and task queue

### Cost Estimation Service (batch_service.py)

**MODEL_PRICING:**
- Sonnet 4: $3/$15 per 1M tokens (input/output)
- Opus 4.5: $15/$75 per 1M tokens

**AVG_TOKENS_PER_OPERATION:**
- Audit: catalog (12k/3k), policy_manual (8k/2.5k), student_handbook (6k/2k), other (5k/1.5k)
- Remediation: catalog (8k/2k), policy_manual (6k/1.8k), student_handbook (5k/1.5k), other (4k/1.2k)

**estimate_batch_cost():**
- Returns total cost, per-document breakdown, and token estimates
- Applies 1.2x safety margin to account for variability
- Warns for batches > 20 documents

**BatchService methods:**
- `create_batch()` - Persist batch with items
- `get_batch()` - Load batch with items
- `get_progress()` - Calculate completion percentage
- `update_item_status()` - Update item and recalculate batch counts
- `cancel_batch()` - Cancel pending items
- `list_batches()` - Institution batch history

## Testing

Created 11 comprehensive tests:

**Cost Estimation (5 tests):**
- Catalog audit cost (~$0.08)
- Policy manual audit cost (~$0.05)
- Remediation cheaper than audit
- Multiple document totals
- Opus model 5x more expensive

**Batch Service (6 tests):**
- Batch creation and persistence
- Batch retrieval with items
- Progress calculation (completed + failed / total)
- Item status updates affect batch counts
- Batch cancellation
- Institution batch history

**Result:** 11/11 tests pass (100%)

## Deviations from Plan

None - plan executed exactly as written. The batch_service.py implementation was already present from prior work (commit 275b18c in phase 12-02), so Task 3 focused on writing comprehensive tests to verify the existing implementation against the spec.

## Impact

**Requirements fulfilled:**
- REQ-55: Batch Remediation (foundation complete)
- REQ-56: Bulk Audit Trigger (foundation complete)
- REQ-57: Progress Tracking Dashboard (database schema ready)

**Next steps enabled:**
- Plan 02: Batch Audit API with SSE streaming
- Plan 03: Batch Remediation API
- Plan 04: Progress Tracking Dashboard UI

**Cost transparency:**
- Users can see estimated costs before starting operations
- Per-document cost breakdown for budget planning
- Actual cost tracking for post-operation analysis

## Files Changed

### Created
- `src/db/migrations/0025_bulk_operations.sql` (58 lines)
- `tests/test_batch_service.py` (233 lines)

### Modified
- `src/core/models.py` (+134 lines)
  - Added `BatchStatus` enum
  - Added `BatchItem` dataclass
  - Added `BatchOperation` dataclass

### Commits
1. `b79fdf9` - feat(12-01): add batch operations database schema
2. `b1c3c3a` - feat(12-01): add BatchOperation and BatchItem domain models
3. `0c335c0` - test(12-01): add BatchService tests with cost estimation

## Verification

```bash
# Migration applies cleanly
python -c "from src.db.migrate import apply_migrations; print(apply_migrations())"
# Output: ['0025_bulk_operations.sql']

# Models importable
python -c "from src.core.models import BatchOperation, BatchItem, BatchStatus; print('OK')"
# Output: OK

# Cost estimation works
python -c "from src.services.batch_service import estimate_batch_cost; docs = [{'id': 'd1', 'doc_type': 'catalog', 'name': 'Catalog.pdf'}]; print(estimate_batch_cost('audit', docs)['total_cost'])"
# Output: 0.1

# All tests pass
pytest tests/test_batch_service.py -v
# Output: 11 passed in 0.23s
```

## Self-Check: PASSED

**Files created:**
- [x] `src/db/migrations/0025_bulk_operations.sql` exists
- [x] `tests/test_batch_service.py` exists

**Commits exist:**
- [x] `b79fdf9` (migration)
- [x] `b1c3c3a` (models)
- [x] `0c335c0` (tests)

**Functionality verified:**
- [x] Tables exist in database
- [x] Models serialize/deserialize correctly
- [x] Cost estimation returns dollar amounts
- [x] BatchService creates and retrieves batches
- [x] All 11 tests pass
