# Phase 12: Bulk Operations - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Multi-document batch processing for audit and remediation workflows. Users can select multiple documents, estimate AI costs, run batch operations with configurable concurrency, track progress, handle failures gracefully, and view batch history. This phase focuses on bulk audit and bulk remediation — other bulk operations (checklist, export) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Selection UI
- Checkbox list for document selection (each row has checkbox)
- Select all/none toggle at top of list
- Floating action bar appears at bottom when items selected
  - Shows selection count + "Batch Audit" / "Batch Remediate" buttons
  - Disappears when deselected (like Gmail's selection bar)

### Cost Estimation
- Confirmation modal before any AI operation starts
- Shows estimated cost: "~$X.XX for Y documents"
- User must confirm or cancel before proceeding
- Appears after clicking "Batch Audit" or "Batch Remediate"

### Operation Scope
- Both Audit and Remediation support batch processing
- Concurrency is user-configurable (1-5 parallel operations)
- Soft limit with warning at 20+ documents: "Large batch may take a while. Continue?"
- After batch audit completes, offer to chain remediation: "X documents have issues. Remediate all?"

### Failure Handling
- Continue processing remaining documents when one fails
- Mark failed item with error status, don't halt batch
- After completion, show summary: "8/10 completed. 2 failed."
- Provide "View failures" and "Retry failed" buttons
- Cancel button visible during processing with confirmation prompt
- Partial results kept if cancelled (completed documents retain results)

### Progress Tracking
- Modal with overall progress bar + scrollable document list
- Each document shows status: pending (gray), running (spinner), done (checkmark), failed (X)
- Cancel button in modal footer with confirmation
- Dedicated "Batch History" page listing past operations
  - Shows: date, operation type, document count, success rate
  - Click to view details of a past batch

### Claude's Discretion
- Whether to save selection sets (lean toward smart filters only if needed)
- Status badges/quick filters in document list (show audit status to help selection)
- Cost estimate breakdown (total vs per-document detail)
- Whether progress modal is minimizable (lean toward yes, to toast)
- Detail level per document in progress list (name + status + optional findings count)

</decisions>

<specifics>
## Specific Ideas

- Cost estimation popup is mandatory before any AI call — transparency for the user
- Chaining flow: batch audit -> offer remediation -> user confirms -> batch remediate
- Gmail-style floating action bar for batch actions
- Progress modal should feel like a task manager (clear status per item)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TaskQueue` (src/core/task_queue.py): Background task queue with worker threads, progress tracking (0-100% + message), status states
- `work_queue_bp` (src/api/work_queue.py): Unified work item management, can extend for batch tracking
- SSE streaming pattern: Used in audits_bp and remediation_bp for real-time progress

### Established Patterns
- Agent session tracking: `AgentSession` with progress field, used by all agents
- Document listing: institutions have `.documents` list with status
- API pattern: `init_*_bp(workspace_manager)` dependency injection

### Integration Points
- Audits API: Extend with `POST /api/institutions/<id>/audits/batch`
- Remediation API: Extend with `POST /api/institutions/<id>/remediations/batch`
- New Batch History API: `GET /api/institutions/<id>/batches`
- Dashboard: Add batch status widget or link to batch history

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-bulk-operations*
*Context gathered: 2026-03-15*
