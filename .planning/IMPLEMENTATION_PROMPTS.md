# AccreditAI Implementation Prompts

5 sequenced prompts for shipping real value in weekly chunks.

---

## Prompt 1: Autopilot Nightly Run + Morning Brief

**Goal**: Convert from "run audit when I remember" to "always current"

```text
Implement "Autopilot" for AccreditAI: a scheduled background run that keeps an institution continuously audit-ready and generates a morning brief.

Requirements:
1) Add institution setting:
   - autopilot_enabled (bool)
   - autopilot_schedule_local (string like "06:30")
   - autopilot_days (json array, default weekdays)
   - autopilot_scope (json: {documents:true, consistency:true, audits:"targeted", translations:false})

2) Autopilot runner:
   - Runs in background worker (reuse existing task queue/worker).
   - For each institution with autopilot_enabled:
     a) detect new/changed documents (by sha256 or updated_at)
     b) if changed: parse/index as needed
     c) run consistency check
     d) run targeted audits only for impacted doc types or standards
     e) recompute readiness score snapshot
     f) generate "morning brief" artifact:
        workspace/{institution_id}/briefs/YYYY-MM-DD_<locale>.md

3) Morning brief contents:
   - readiness score + delta since last snapshot
   - top blockers (max 8)
   - what changed (docs updated, audits run)
   - next best actions (max 5)
   - links to findings and artifacts

4) API:
   - GET /api/institutions/<id>/briefs/latest
   - GET /api/institutions/<id>/briefs?days=30
   - POST /api/institutions/<id>/autopilot/run-now

5) UI:
   - Command Center shows "Last Autopilot Run" and a "Run now" button
   - Morning brief panel with download/open

6) Tests:
   - autopilot run produces a brief file and readiness snapshot
   - run-now endpoint triggers task and reports status

Start with run-now endpoint + runner that does: readiness recompute + brief generation, then add document-change detection and targeted audits.
```

---

## Prompt 2: Work Queue Screen

**Goal**: Single merged view of blockers + tasks + approvals + artifacts

```text
Implement a Work Queue screen that merges blockers, tasks, approvals, and artifacts awaiting review into one actionable view.

Requirements:
1) New page: /work-queue (scoped to current institution)
2) Data sources:
   - blockers from readiness status
   - pending checkpoints from human_checkpoints
   - remediation_jobs with status queued/running/complete needing approval
   - latest audit findings (critical/moderate) unresolved
   - recent artifacts created by agent sessions

3) Queue items unified schema:
   { type, severity, title, reason, created_at, primary_action, link }

4) Actions:
   - Approve/Reject checkpoint inline
   - "Generate fix" for a finding
   - "Run targeted audit" for a doc type
   - "Resolve mismatch" for a consistency issue
   - "Export packet" only if allowed by readiness gate

5) UI layout:
   - Filters: severity, type, doc_type, program
   - Sort: highest severity first
   - Right panel: details for selected item (evidence + standard + confidence)

6) i18n:
   - All labels translated (en-US, es-PR)

7) Tests:
   - work queue endpoint returns deterministic ordering
   - checkpoint approval updates status and disappears from queue

Implement /api/institutions/<id>/work-queue first (server aggregates), then build the UI.
```

---

## Prompt 3: Document Change Detection + Targeted Re-Audit

**Goal**: Avoid rerunning full audits when only specific docs change

```text
Implement document change detection and targeted re-audit to avoid rerunning full audits.

Requirements:
1) When a document version is added (upload or remediation output), compute:
   - file_sha256
   - diff summary vs previous version (text-level diff on parsed redacted text)
   - changed_sections (best effort using headings/section markers)
   Store in:
   - document_version_diffs table (version_id, prior_version_id, diff_summary, changed_sections_json, created_at)

2) Impact mapping:
   - Map changed doc_type + changed_sections to likely affected checklist items and standards.
   - Store impact set for an event in:
     re_audit_requests (institution_id, document_id, affected_checklist_item_ids, affected_standard_ids, reason, created_at)

3) Targeted re-audit runner:
   - Runs only impacted checklist items for the impacted doc type.
   - Produces a partial audit_run flagged as targeted:
     audit_runs.run_type = "targeted"
   - Updates readiness and blockers.

4) UI:
   - Document Workbench shows: "Changes since last version"
   - Button: "Run targeted re-audit"
   - Work Queue shows "Targeted re-audit recommended" items after changes.

5) Tests:
   - uploading a new version creates a diff record
   - targeted re-audit runs and produces findings for only affected items

Start with sha256-based change detection + a simple diff_summary, then add section-based mapping.
```

---

## Prompt 4: Evidence Coverage Contract for Packet Export

**Goal**: Prevent exporting packets without proper evidence coverage

```text
Implement an evidence coverage contract that prevents exporting submission packets unless coverage requirements are met.

Requirements:
1) Define coverage rules:
   - Every selected standard in a packet must have >=1 evidence ref linked to an audit finding OR explicitly attached evidence
   - Critical findings must be resolved or explicitly waived with a human checkpoint
   - Any low-confidence compliance claims must be approved

2) Add packet validation:
   - validate_packet(packet_id) returns:
     { ok, missing_standards[], missing_evidence[], blocking_findings[], required_checkpoints[] }

3) Enforce:
   - Export endpoints must refuse export if ok=false
   - Provide override only by creating a checkpoint:
     checkpoint_type = "finalize_submission"
     requires a reason and approver identity

4) UI:
   - Submission Packet Studio shows a "Coverage" step with:
     - standards list
     - evidence count per standard
     - missing items highlighted
   - Export buttons disabled until validation ok

5) Tests:
   - packet with missing evidence fails validation
   - approval checkpoint allows export

Start with validate_packet() and server-side export gating, then wire UI coverage step.
```

---

## Prompt 5: Audit Reproducibility Logs

**Goal**: Every audit can be explained and reproduced later

```text
Implement audit reproducibility records so every audit can be explained later.

Requirements:
1) For each audit_run, store a reproducibility bundle:
   - standards version ids and hashes used
   - document ids + version ids + file_sha256
   - chunk ids retrieved + retrieval query text
   - model identifier or "no-ai" mode flag
   - agent versions (code version string)
   - timestamps
   Store:
   - audit_run_repro table (audit_run_id, repro_json, created_at)
   And also write a workspace artifact:
   workspace/{institution_id}/audits/<audit_run_id>_REPRO.json

2) UI:
   - Audit Run detail page shows:
     - "How this audit was produced"
     - key elements + download repro bundle

3) Tests:
   - audit run creation persists repro bundle and workspace file
   - repro bundle includes required keys

Start by adding the DB table + workspace writer, then instrument the AuditAgent to write repro data.
```

---

## Prompt 6: Global Command Palette (Future)

**Goal**: Keyboard-driven quick actions for power users

```text
Implement a global command palette for keyboard-driven navigation and actions.

Requirements:
1) Keyboard shortcuts:
   - `/` or `Cmd+K` - Open command palette
   - `A` - Run audit
   - `F` - Fix finding (when finding selected)
   - `E` - Open evidence explorer
   - `U` - Upload document
   - `P` - Generate packet
   - `T` - Toggle language (en-US ↔ es-PR)
   - `Escape` - Close modals/palette

2) Command palette features:
   - Fuzzy search across: documents, standards, findings, institutions
   - Recent commands
   - Context-aware actions (different options on different pages)

3) UI:
   - Modal overlay with search input
   - Results grouped by type
   - Keyboard navigation (arrows + enter)

4) Persist:
   - Recent commands in localStorage
   - User shortcut preferences in settings

Start with basic palette + search, then add context-aware actions.
```

---

## Implementation Order

| Week | Prompt | Value |
|------|--------|-------|
| 1 | Autopilot | "Always current" daily value |
| 2 | Work Queue | UX consolidation, single action point |
| 3 | Change Detection | Efficiency, targeted re-audits |
| 4 | Evidence Contract | Safety gate, defensible submissions |
| 5 | Reproducibility | Trust/compliance, explains conclusions |
| 6 | Command Palette | Power user speed, polish |

---

## Dependencies

- **Autopilot** requires: task queue (exists), readiness service (done)
- **Work Queue** requires: readiness blockers (done), checkpoints (exists)
- **Change Detection** requires: document parser (exists), audit agent (exists)
- **Evidence Contract** requires: evidence_refs table (exists), packet agent (exists)
- **Reproducibility** requires: audit_runs table (exists)
- **Command Palette** requires: search infrastructure (exists)
