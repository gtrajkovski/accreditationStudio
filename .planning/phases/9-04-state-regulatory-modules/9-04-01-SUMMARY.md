---
phase: 9-04-state-regulatory-modules
plan: 01
subsystem: state-regulatory
tags: [backend, models, service, database, state-compliance]
dependency_graph:
  requires: []
  provides: [StateAuthorization, StateCatalogRequirement, StateCatalogCompliance, StateProgramApproval, StateReadinessScore, StateSummary, StateRegulatoryService]
  affects: [readiness_service, compliance_calendar, knowledge_graph]
tech_stack:
  added: []
  patterns: [dataclass, to_dict/from_dict, service-class, connection-management]
key_files:
  created:
    - src/core/models/state_regulations.py
    - src/db/migrations/0039_state_regulatory.sql
    - src/services/state_regulatory_service.py
  modified: []
decisions:
  - Used ON CONFLICT for upsert in compliance updates
  - Module-level convenience functions for common operations
  - Weighted scoring: authorization 30%, catalog 40%, program 30%
metrics:
  duration: "6 minutes"
  completed: "2026-03-27T20:07:33Z"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 9-04 Plan 01: Core Backend for State Regulatory Modules Summary

State regulatory compliance infrastructure with data models, database schema, and service layer for tracking state authorizations, catalog requirements, and program licensing approvals.

## What Was Built

### 1. State Regulations Data Models (`src/core/models/state_regulations.py`)

Six dataclasses following existing codebase patterns:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `StateAuthorization` | Track state authorization status | institution_id, state_code, authorization_status, sara_member, renewal_date |
| `StateCatalogRequirement` | State-specific catalog disclosures | state_code, requirement_key, category, required |
| `StateCatalogCompliance` | Institution compliance tracking | institution_id, requirement_id, status, evidence_doc_id |
| `StateProgramApproval` | Program licensing board approvals | program_id, board_name, approved, min_pass_rate, current_pass_rate |
| `StateReadinessScore` | Per-state compliance score | total, authorization_score, catalog_score, program_score |
| `StateSummary` | Compact state overview | state_name, authorization_status, catalog_compliance_pct, programs_approved |

All implement `to_dict()` and `from_dict()` with unknown field filtering.

### 2. Database Migration (`src/db/migrations/0039_state_regulatory.sql`)

Four tables with proper indexes:

```sql
state_authorizations
  - UNIQUE(institution_id, state_code)
  - Indexes: institution_id, state_code, status, renewal_date

state_catalog_requirements
  - UNIQUE(state_code, requirement_key)
  - Indexes: state_code, category

state_catalog_compliance
  - UNIQUE(institution_id, requirement_id)
  - Indexes: institution_id, state_code, status

state_program_approvals
  - UNIQUE(institution_id, program_id, state_code)
  - Indexes: institution_id, state_code, program_id, approved, expiration_date
```

### 3. State Regulatory Service (`src/services/state_regulatory_service.py`)

Service class with 15+ methods:

**Authorization Methods:**
- `add_authorization()` - Create new state authorization
- `get_authorizations()` - List all for institution
- `get_authorization()` - Get specific state
- `update_authorization()` - Update fields
- `delete_authorization()` - Remove record

**Catalog Requirements Methods:**
- `get_requirements_for_state()` - List state requirements
- `add_requirement()` - Add new requirement
- `get_compliance_status()` - JOIN view of requirements + compliance
- `update_compliance()` - Upsert compliance record

**Program Approval Methods:**
- `add_program_approval()` - Create approval record
- `get_program_approvals()` - List with filters
- `update_program_approval()` - Update fields
- `delete_program_approval()` - Remove record

**Scoring Methods:**
- `compute_state_readiness()` - Calculate 0-100 score with sub-scores
- `get_all_states_summary()` - Dashboard-ready state summaries

**Calendar Integration:**
- `get_upcoming_renewals()` - Authorization and approval expirations within N days

**Module-level Convenience Functions:**
- `add_authorization()`, `get_authorizations()`, `compute_state_readiness()`, `get_all_states_summary()`, `get_upcoming_renewals()`

## Scoring Algorithm

```
total = (authorization_score * 0.30) + (catalog_score * 0.40) + (program_score * 0.30)

authorization_score:
  - authorized: 100
  - pending: 50
  - restricted: 25
  - denied: 0

catalog_score:
  - (satisfied + partial*0.5) / total_required * 100

program_score:
  - approved_with_passing_rates / total_programs * 100
  - Partial credit (0.5) if approved but below min_pass_rate
```

## Commits

| Hash | Message |
|------|---------|
| abc0769 | feat(9-04): add state regulations data models |
| b1f587e | feat(9-04): add state regulatory database migration |
| 0572c72 | feat(9-04): add state regulatory service |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all functionality is fully implemented.

## Self-Check: PASSED

Files verified:
- [x] `src/core/models/state_regulations.py` exists
- [x] `src/db/migrations/0039_state_regulatory.sql` exists
- [x] `src/services/state_regulatory_service.py` exists
- [x] All 6 dataclasses import successfully
- [x] All 4 database tables created
- [x] Service instantiates with all 15 methods
- [x] Commits abc0769, b1f587e, 0572c72 verified
