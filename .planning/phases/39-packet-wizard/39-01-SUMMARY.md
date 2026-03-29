---
phase: "39"
plan: "01"
name: "Packet Studio Wizard Backend"
subsystem: "packet-wizard"
tags: ["wizard", "packets", "submission", "state-machine"]
dependency_graph:
  requires: ["packets", "standards", "evidence"]
  provides: ["packet-wizard-api", "wizard-sessions"]
  affects: ["submissions", "narratives"]
tech_stack:
  added: []
  patterns: ["5-step-wizard", "session-persistence", "step-validation"]
key_files:
  created:
    - src/db/migrations/0045_packet_wizard.sql
    - src/services/packet_wizard_service.py
    - src/api/packet_wizard.py
  modified:
    - app.py
decisions:
  - "80% evidence coverage threshold for wizard completion"
  - "WizardStep IntEnum for type-safe step navigation"
  - "Session state persists as JSON in step_data column"
metrics:
  duration: "~10 minutes"
  tasks_completed: 4
  files_changed: 4
  lines_added: 900
  completed_at: "2026-03-29"
---

# Phase 39 Plan 01: Packet Studio Wizard Backend Summary

5-step wizard state machine for submission packet creation with step persistence, validation, and preview rendering.

## One-Liner

Packet wizard service with 5-step state machine (type/standards/evidence/narrative/preview), 80% coverage validation, and 12-endpoint REST API.

## Completed Tasks

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Database migration 0045_packet_wizard.sql | 8add10b |
| 2 | Packet wizard service implementation | b6c5415 |
| 3 | Packet wizard API blueprint | 61e602b |
| 4 | Register blueprint in app.py | d8d4d6e |

## Implementation Details

### Database Schema

Created `packet_wizard_sessions` table:
- `id` - Session identifier (wiz_xxxx)
- `institution_id` - Parent institution
- `packet_id` - Links to packets table when complete
- `current_step` - Current wizard step (1-5)
- `step_data` - JSON blob with all step data
- `status` - draft/complete/abandoned
- `created_at`, `updated_at`, `completed_at` timestamps

### Service (packet_wizard_service.py)

**WizardStep Enum:**
1. SUBMISSION_TYPE - Choose packet type
2. STANDARDS - Select applicable standards
3. EVIDENCE - Map evidence to standards (80% coverage required)
4. NARRATIVE - Generate/edit narratives
5. PREVIEW - Review and finalize

**Key Methods:**
- `create_session()` - Start new wizard session
- `get_session()` / `list_sessions()` - Retrieve sessions
- `update_step()` - Save step data and advance
- `abandon_session()` - Soft-delete draft session
- `get_submission_types()` - List available types
- `get_standards_tree()` - Hierarchical standards
- `get_evidence_for_standard()` - Evidence lookup
- `suggest_evidence()` - AI-suggest relevant documents
- `generate_narrative()` - AI narrative generation (placeholder)
- `render_preview()` - HTML preview rendering
- `complete_wizard()` - Validate and create packet

### API Blueprint (packet_wizard.py)

**Session Endpoints:**
- `POST /sessions` - Create new session
- `GET /sessions` - List with status filter
- `GET /sessions/<id>` - Get session state
- `DELETE /sessions/<id>` - Abandon session
- `PUT /sessions/<id>/step/<n>` - Update step data

**Reference Data:**
- `GET /submission-types` - Available packet types
- `GET /standards-tree` - Standards hierarchy
- `GET /standards/<id>/evidence` - Evidence for standard
- `GET /standards/<id>/suggest` - AI suggestions

**Generation:**
- `POST /sessions/<id>/generate-narrative` - AI narrative
- `GET /sessions/<id>/preview` - HTML preview
- `POST /sessions/<id>/complete` - Finalize packet

### Step Validation Logic

Each step has specific validation before proceeding:

| Step | Validation |
|------|------------|
| 1. Type | submission_type must be set |
| 2. Standards | At least 1 standard selected |
| 3. Evidence | 80% of standards have evidence mapped |
| 4. Narrative | At least 1 narrative exists |
| 5. Preview | Always complete (final review) |

## Key Decisions

1. **80% Evidence Coverage** - Requiring 80% coverage before completion balances thoroughness with flexibility
2. **JSON Step Data** - Single column for all step data enables flexible schema evolution
3. **Soft Delete** - Abandoned sessions are marked, not deleted, for audit trail
4. **Placeholder AI** - Narrative generation ready for AI integration

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- Service imports: PASSED
- API blueprint imports: PASSED
- App loads with blueprint: PASSED

## Self-Check: PASSED

All files created:
- [x] src/db/migrations/0045_packet_wizard.sql
- [x] src/services/packet_wizard_service.py
- [x] src/api/packet_wizard.py

All commits exist:
- [x] 8add10b - Migration
- [x] b6c5415 - Service
- [x] 61e602b - API
- [x] d8d4d6e - Registration
