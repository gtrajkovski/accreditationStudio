# AccreditAI State

## Current Phase
Phase 3: Readiness Score + Command Center - **COMPLETE**

## Session Date
2026-03-02

## What's Complete This Session

### 1. Work Queue Screen
- **Service** (`src/services/work_queue_service.py`): Aggregates blockers, tasks, approvals
- **API** (`src/api/work_queue.py`): `/api/work-queue` endpoints
- **UI** (`templates/work_queue.html`): Summary cards, filter tabs, auto-refresh
- **Tests**: 8 tests passing

### 2. Autopilot Nightly Run
- **Service** (`src/services/autopilot_service.py`): APScheduler-based scheduler
- **Jobs**: Re-index, consistency checks, audit (optional), readiness
- **API** (`src/api/autopilot.py`): Config, manual trigger, history
- **UI** (`templates/institutions/autopilot.html`): Schedule picker, run history
- **Migration** (`0011_autopilot.sql`): `autopilot_config`, `autopilot_runs` tables

### 3. Change Detection
- **Service** (`src/services/change_detection_service.py`):
  - `detect_change()` - SHA-256 hash comparison
  - `record_change()` - Persist change events
  - `invalidate_findings()` - Mark findings for re-validation
- **Migration** (`0012_change_detection.sql`): `document_changes`, `audit_invalidations`

### 4. Evidence Coverage Contract
- **Service** (`src/services/evidence_contract_service.py`):
  - `check_evidence_coverage()` - Calculate % standards with evidence
  - `validate_packet_export()` - Block export if coverage < 80%
  - Reports gaps by severity with suggestions

### 5. Audit Reproducibility
- **Service** (`src/services/audit_reproducibility_service.py`):
  - `capture_audit_snapshot()` - Record model, prompts, doc hashes
  - `record_finding_provenance()` - Link findings to exact AI interactions
  - `verify_audit_reproducibility()` - Check if audit can be reproduced
- **Migration** (`0013_audit_reproducibility.sql`): `audit_snapshots`, `finding_provenance`

### 6. Readiness Score (Previous)
- **Service** (`src/services/readiness_service.py`): 4 weighted sub-scores
- **API** (`src/api/readiness.py`): Status, alerts, next-actions, history
- **UI**: Institution overview dashboard widget

## Files Added This Session
```
# Services
src/services/work_queue_service.py
src/services/autopilot_service.py
src/services/change_detection_service.py
src/services/evidence_contract_service.py
src/services/audit_reproducibility_service.py

# API
src/api/work_queue.py
src/api/autopilot.py

# Templates
templates/work_queue.html
templates/institutions/autopilot.html

# Migrations
src/db/migrations/0011_autopilot.sql
src/db/migrations/0012_change_detection.sql
src/db/migrations/0013_audit_reproducibility.sql

# Tests
tests/test_work_queue_service.py
tests/test_readiness_service.py
```

## Commits This Session
```
8c7f880 Add Audit Reproducibility service
39b6090 Add Evidence Coverage Contract service
9fe041b Add Change Detection service
9fc3cf8 Add Autopilot Nightly Run feature
7171567 Add Work Queue screen and Readiness Score service
```

## Tests
- **92 tests passing**
- 701 warnings (mostly datetime deprecation)

## High Impact Features - Status
| Feature | Status |
|---------|--------|
| Work Queue Screen | ✅ Complete |
| Autopilot Nightly Run | ✅ Complete |
| Change Detection | ✅ Complete |
| Evidence Coverage Contract | ✅ Complete |
| Audit Reproducibility | ✅ Complete |

## Key Commands
```bash
flask db upgrade          # Apply migrations (0001-0013)
flask db status           # Check migration status
python app.py             # Run dev server on port 5003
pytest                    # Run all tests (92 passing)
pip install APScheduler   # Required for autopilot
```

## Database
- Location: `workspace/_system/accreditai.db`
- Migrations: 13 total (0001-0013)
- New tables this session:
  - `autopilot_config`, `autopilot_runs`, `autopilot_run_tasks`
  - `document_changes`, `audit_invalidations`
  - `audit_snapshots`, `finding_provenance`
