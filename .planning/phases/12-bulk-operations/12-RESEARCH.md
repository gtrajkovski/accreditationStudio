# Phase 12: Bulk Operations - Research

**Researched:** 2026-03-15
**Domain:** Multi-document batch processing with AI cost estimation
**Confidence:** HIGH

## Summary

Phase 12 implements bulk operations for audit and remediation workflows, allowing users to select multiple documents, estimate AI costs before execution, run batch operations with configurable concurrency, track progress in real-time, and handle failures gracefully. The phase leverages existing infrastructure (TaskQueue, SSE streaming, WorkspaceManager) and extends the current audit/remediation APIs with batch endpoints.

The architecture builds on proven patterns already in the codebase: TaskQueue for background processing, SSE for real-time progress updates, and agent session tracking for token usage. Cost estimation is a new feature requiring per-model token pricing data and average token consumption heuristics based on document types.

**Primary recommendation:** Extend existing TaskQueue and SSE streaming patterns with batch orchestration layer. Add cost estimation service using Anthropic's public pricing and empirical token averages from AgentSession history.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Selection UI:**
- Checkbox list for document selection (each row has checkbox)
- Select all/none toggle at top of list
- Floating action bar appears at bottom when items selected
  - Shows selection count + "Batch Audit" / "Batch Remediate" buttons
  - Disappears when deselected (Gmail-style selection bar)

**Cost Estimation:**
- Confirmation modal before any AI operation starts
- Shows estimated cost: "~$X.XX for Y documents"
- User must confirm or cancel before proceeding
- Appears after clicking "Batch Audit" or "Batch Remediate"

**Operation Scope:**
- Both Audit and Remediation support batch processing
- Concurrency is user-configurable (1-5 parallel operations)
- Soft limit with warning at 20+ documents: "Large batch may take a while. Continue?"
- After batch audit completes, offer to chain remediation: "X documents have issues. Remediate all?"

**Failure Handling:**
- Continue processing remaining documents when one fails
- Mark failed item with error status, don't halt batch
- After completion, show summary: "8/10 completed. 2 failed."
- Provide "View failures" and "Retry failed" buttons
- Cancel button visible during processing with confirmation prompt
- Partial results kept if cancelled (completed documents retain results)

**Progress Tracking:**
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

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.0+ | Web framework | Already in use, handles blueprints, SSE |
| SQLite | 3.x | Database | Already in use, simple persistence |
| Anthropic SDK | 0.40+ | AI API | Already in use, tracks token usage |
| threading | stdlib | Concurrency | TaskQueue already uses threads |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| queue.Queue | stdlib | Thread-safe task queue | TaskQueue already implements |
| json | stdlib | Serialization | Session/batch state persistence |
| datetime | stdlib | Timestamps | Already used via now_iso() |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| threading | asyncio | TaskQueue is already thread-based; no benefit to rewrite |
| SQLite | PostgreSQL | Over-engineered for single-user localhost tool |
| Manual token counting | tiktoken | Anthropic SDK already provides usage.input_tokens/output_tokens |

**Installation:**
```bash
# No new dependencies required - all capabilities exist in current stack
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── services/
│   └── batch_service.py              # Batch orchestration, cost estimation
├── api/
│   ├── audits.py                      # Extend with batch endpoints
│   ├── remediation.py                 # Extend with batch endpoints
│   └── batch_history.py               # NEW: Batch history API
├── core/
│   └── models.py                      # Add BatchOperation, BatchItem models
templates/institutions/
├── compliance.html                    # Add batch UI (checkboxes, action bar)
├── workbench.html                     # Add batch UI for remediation
└── batch_history.html                 # NEW: Batch history page
static/js/
└── batch_operations.js                # NEW: Batch selection and progress
```

### Pattern 1: Batch Orchestration with TaskQueue

**What:** Submit N document operations as N background tasks, track batch progress by polling task statuses.

**When to use:** Batch audit, batch remediation — any multi-document AI operation.

**Example:**

```python
# src/services/batch_service.py
from src.core.task_queue import get_task_queue, BackgroundTask
from src.core.models import generate_id, now_iso
from typing import List, Dict, Any

class BatchOperation:
    """Orchestrates batch operations across multiple documents."""

    def __init__(self, batch_id: str, operation_type: str, document_ids: List[str]):
        self.batch_id = batch_id
        self.operation_type = operation_type  # "audit" or "remediation"
        self.document_ids = document_ids
        self.task_ids: List[str] = []
        self.created_at = now_iso()

    def submit_tasks(self, task_func, **kwargs) -> List[str]:
        """Submit all document tasks to queue."""
        queue = get_task_queue()

        for doc_id in self.document_ids:
            task_id = queue.submit(
                task_func,
                document_id=doc_id,
                name=f"{self.operation_type}_{doc_id[:8]}",
                institution_id=kwargs.get("institution_id"),
                **kwargs
            )
            self.task_ids.append(task_id)

        return self.task_ids

    def get_progress(self) -> Dict[str, Any]:
        """Get batch progress summary."""
        queue = get_task_queue()
        statuses = [queue.get_status(tid) for tid in self.task_ids]

        completed = sum(1 for s in statuses if s and s["status"] == "completed")
        failed = sum(1 for s in statuses if s and s["status"] == "failed")
        running = sum(1 for s in statuses if s and s["status"] == "running")

        return {
            "batch_id": self.batch_id,
            "total": len(self.task_ids),
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": len(self.task_ids) - completed - failed - running,
            "progress_pct": (completed / len(self.task_ids) * 100) if self.task_ids else 0,
            "items": statuses,
        }
```

### Pattern 2: Cost Estimation via Token Averages

**What:** Estimate batch operation cost using per-model token pricing and average tokens per document type.

**When to use:** Before starting any batch operation requiring AI calls.

**Example:**

```python
# src/services/batch_service.py

# Anthropic pricing as of 2026-03-15 (verify at https://www.anthropic.com/pricing)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {
        "input": 3.00 / 1_000_000,   # $3 per 1M input tokens
        "output": 15.00 / 1_000_000, # $15 per 1M output tokens
    },
    "claude-opus-4-5-20251101": {
        "input": 15.00 / 1_000_000,
        "output": 75.00 / 1_000_000,
    },
}

# Empirical averages (update based on AgentSession history)
AVG_TOKENS_PER_OPERATION = {
    "audit": {
        "catalog": {"input": 12000, "output": 3000},
        "policy_manual": {"input": 8000, "output": 2500},
        "student_handbook": {"input": 6000, "output": 2000},
        "other": {"input": 5000, "output": 1500},
    },
    "remediation": {
        "catalog": {"input": 8000, "output": 2000},
        "policy_manual": {"input": 6000, "output": 1800},
        "student_handbook": {"input": 5000, "output": 1500},
        "other": {"input": 4000, "output": 1200},
    },
}

def estimate_batch_cost(
    operation_type: str,
    documents: List[Dict[str, Any]],
    model: str = "claude-sonnet-4-20250514"
) -> Dict[str, Any]:
    """Estimate cost for batch operation.

    Returns:
        {
            "total_cost": 12.45,
            "per_document": [
                {"doc_id": "...", "doc_name": "...", "estimated_cost": 1.24},
                ...
            ],
            "breakdown": {
                "input_tokens": 120000,
                "output_tokens": 30000,
                "input_cost": 0.36,
                "output_cost": 0.45,
            }
        }
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])

    total_input = 0
    total_output = 0
    per_doc = []

    for doc in documents:
        doc_type = doc.get("doc_type", "other")
        avg = AVG_TOKENS_PER_OPERATION.get(operation_type, {}).get(doc_type, AVG_TOKENS_PER_OPERATION[operation_type]["other"])

        input_tokens = avg["input"]
        output_tokens = avg["output"]

        cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])

        total_input += input_tokens
        total_output += output_tokens

        per_doc.append({
            "doc_id": doc["id"],
            "doc_name": doc.get("name", "Untitled"),
            "estimated_cost": round(cost, 2),
        })

    input_cost = total_input * pricing["input"]
    output_cost = total_output * pricing["output"]
    total_cost = input_cost + output_cost

    return {
        "total_cost": round(total_cost, 2),
        "per_document": per_doc,
        "breakdown": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "input_cost": round(input_cost, 2),
            "output_cost": round(output_cost, 2),
        },
    }
```

### Pattern 3: Batch Progress Modal with SSE

**What:** Open modal on batch start, stream progress via SSE, update document status in real-time.

**When to use:** All batch operations requiring user feedback.

**Example:**

```javascript
// static/js/batch_operations.js

class BatchProgressModal {
    constructor(batchId, operationType, documentCount) {
        this.batchId = batchId;
        this.operationType = operationType;
        this.documentCount = documentCount;
        this.eventSource = null;
        this.minimized = false;
    }

    show() {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.className = 'batch-progress-modal';
        modal.innerHTML = `
            <div class="modal-header">
                <h3>Batch ${this.operationType} - ${this.documentCount} documents</h3>
                <button class="minimize-btn" onclick="batchModal.minimize()">_</button>
                <button class="close-btn" onclick="batchModal.cancel()">×</button>
            </div>
            <div class="progress-summary">
                <div class="progress-bar">
                    <div class="progress-fill" id="batch-progress-fill" style="width: 0%"></div>
                </div>
                <div class="progress-stats">
                    <span id="progress-text">0 / ${this.documentCount} completed</span>
                </div>
            </div>
            <div class="documents-list" id="batch-documents-list">
                <!-- Populated via SSE -->
            </div>
            <div class="modal-footer">
                <button class="btn btn-danger" onclick="batchModal.cancel()">Cancel Batch</button>
            </div>
        `;
        document.body.appendChild(modal);

        // Start SSE stream
        this.startStreaming();
    }

    startStreaming() {
        this.eventSource = new EventSource(`/api/institutions/${institutionId}/batches/${this.batchId}/stream`);

        this.eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            this.updateProgress(data);
        });

        this.eventSource.addEventListener('item_completed', (e) => {
            const data = JSON.parse(e.data);
            this.updateItem(data.doc_id, 'completed', data.result);
        });

        this.eventSource.addEventListener('item_failed', (e) => {
            const data = JSON.parse(e.data);
            this.updateItem(data.doc_id, 'failed', data.error);
        });

        this.eventSource.addEventListener('batch_completed', (e) => {
            const data = JSON.parse(e.data);
            this.onComplete(data);
            this.eventSource.close();
        });

        this.eventSource.onerror = () => {
            this.eventSource.close();
            this.showError("Connection lost. Batch may still be running.");
        };
    }

    updateProgress(data) {
        const pct = (data.completed / data.total) * 100;
        document.getElementById('batch-progress-fill').style.width = `${pct}%`;
        document.getElementById('progress-text').textContent =
            `${data.completed} / ${data.total} completed (${data.failed} failed)`;
    }

    minimize() {
        this.minimized = true;
        // Convert to toast notification
        showToast(`Batch ${this.operationType} running in background...`, 'info');
        document.querySelector('.batch-progress-modal').style.display = 'none';
    }

    async cancel() {
        if (confirm('Cancel batch operation? Completed items will be kept.')) {
            await fetch(`/api/institutions/${institutionId}/batches/${this.batchId}/cancel`, {
                method: 'POST'
            });
            this.eventSource.close();
            this.close();
        }
    }
}
```

### Pattern 4: Database Schema for Batch History

**What:** Persist batch operations for history/audit trail.

**When to use:** All batch operations.

**Example:**

```sql
-- Migration: 0025_bulk_operations.sql

CREATE TABLE IF NOT EXISTS batch_operations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'audit' or 'remediation'
    document_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    estimated_cost REAL,
    actual_cost REAL,
    concurrency INTEGER DEFAULT 3,
    status TEXT DEFAULT 'pending', -- pending, running, completed, cancelled, failed
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE TABLE IF NOT EXISTS batch_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, running, completed, failed
    task_id TEXT,
    result_path TEXT, -- Path to audit/remediation result
    error TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (batch_id) REFERENCES batch_operations(id)
);

CREATE INDEX IF NOT EXISTS idx_batch_operations_institution ON batch_operations(institution_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_batch ON batch_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_status ON batch_items(status);
```

### Anti-Patterns to Avoid

- **Sequential Processing:** Don't wait for each document to finish before starting the next. Use TaskQueue's concurrency.
- **Blocking API Calls:** Don't make batch endpoints synchronous. Always use SSE or polling for progress.
- **Hardcoded Concurrency:** Don't force 3 workers. Make it user-configurable (1-5 range).
- **Ignoring Partial Results:** Don't delete results if batch is cancelled. Keep completed items.
- **Missing Cost Transparency:** Never start AI operations without showing estimated cost first.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background tasks | Custom process manager | TaskQueue (already exists) | Thread-safe, progress tracking, callbacks |
| Token counting | Manual regex/splitting | Anthropic SDK usage field | Accurate, maintained by vendor |
| Real-time updates | WebSocket server | SSE (Server-Sent Events) | Simpler, already used in audit/remediation |
| Concurrent execution | Custom semaphore | TaskQueue num_workers | Already configurable via Config.AGENT_MAX_CONCURRENT_TASKS |
| Batch state | In-memory dict | SQLite tables | Survives restarts, queryable history |

**Key insight:** TaskQueue already handles concurrency, progress tracking, and error handling. Extend it, don't replace it.

## Common Pitfalls

### Pitfall 1: Inaccurate Cost Estimates

**What goes wrong:** Cost estimates are wildly off, user loses trust.

**Why it happens:** Using fixed token counts without accounting for document size variance.

**How to avoid:**
- Store actual token usage in AgentSession after each operation
- Build empirical averages from real usage data (median, p90)
- Add safety margin (1.2x multiplier) to estimates
- Update averages quarterly based on AgentSession history query

**Warning signs:** User feedback "costs are always higher than shown"

### Pitfall 2: Memory Exhaustion from Large Batches

**What goes wrong:** Server crashes when user selects 100+ documents.

**Why it happens:** Loading all document contents into memory simultaneously.

**How to avoid:**
- Enforce soft limit (20 documents) with warning
- Hard limit (50 documents) with error
- TaskQueue already streams; don't preload all docs
- Each worker loads only the document it's processing

**Warning signs:** OOM errors, slow response times with large batches

### Pitfall 3: Orphaned Tasks After Cancel

**What goes wrong:** Tasks keep running after user cancels batch.

**Why it happens:** TaskQueue cancel() only works on pending tasks, not running ones.

**How to avoid:**
- Track batch_id in task metadata
- Add cancelled_batch_ids set
- Check at start of each tool function: if batch cancelled, return early
- Document limitation: "Running tasks will complete; pending tasks cancelled"

**Warning signs:** Tasks complete after cancellation, token usage continues

### Pitfall 4: No Retry for Network Failures

**What goes wrong:** Transient API errors fail entire batch.

**Why it happens:** No retry logic in batch orchestration.

**How to avoid:**
- BaseAgent already has retry logic for API calls
- Add batch-level retry: "Retry Failed" button in summary
- Store failed item IDs in batch_operations.metadata
- Retry creates new batch_items rows, preserves history

**Warning signs:** Batches fail with "Connection timeout" errors

### Pitfall 5: Progress Modal Blocks Navigation

**What goes wrong:** User can't navigate away without cancelling batch.

**Why it happens:** Modal is blocking overlay.

**How to avoid:**
- Add minimize button (converts to toast)
- Store modal state in sessionStorage
- Restore modal on page revisit if batch still running
- Allow multiple batches running (track by batch_id)

**Warning signs:** User complaints about being "stuck" on page

## Code Examples

Verified patterns from existing codebase:

### TaskQueue Progress Tracking

```python
# From: src/core/task_queue.py (lines 200-222)
def update_progress(
    self,
    task_id: str,
    progress: float,
    message: str = "",
) -> None:
    """Update progress of a running task.

    Called from within task functions to report progress.
    """
    with self._lock:
        task = self._tasks.get(task_id)
        if task:
            task.progress = progress
            task.progress_message = message

    # Notify callbacks
    self._notify_callbacks(task_id, "progress")
```

**Usage in batch context:**
```python
def audit_document_batch_worker(document_id: str, batch_id: str, task_id: str):
    """Worker function for batch audit."""
    queue = get_task_queue()

    # Report progress to batch orchestrator
    queue.update_progress(task_id, 10, f"Loading document {document_id[:8]}...")

    # ... perform audit ...

    queue.update_progress(task_id, 50, "Running compliance checks...")

    # ... finalize ...

    queue.update_progress(task_id, 100, "Audit complete")
```

### SSE Streaming (Existing Pattern)

```python
# From: src/api/audits.py (lines 144-194)
@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/stream', methods=['GET'])
def stream_audit(institution_id: str, audit_id: str):
    """Run audit and stream progress via Server-Sent Events."""

    def generate():
        """Generate SSE events for audit progress."""
        try:
            yield f"data: {json.dumps({'type': 'audit_started', 'audit_id': audit_id})}\n\n"

            # ... run operations ...

            yield f"data: {json.dumps({'type': 'audit_completed', 'result': final_result})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )
```

**Adapt for batch progress:**
```python
@batch_bp.route('/api/institutions/<institution_id>/batches/<batch_id>/stream', methods=['GET'])
def stream_batch_progress(institution_id: str, batch_id: str):
    """Stream batch operation progress."""

    def generate():
        batch_op = load_batch_operation(batch_id)
        yield f"data: {json.dumps({'type': 'batch_started', 'batch_id': batch_id})}\n\n"

        # Poll task statuses every 1 second
        while not is_batch_complete(batch_id):
            progress = batch_op.get_progress()
            yield f"data: {json.dumps({'type': 'progress', **progress})}\n\n"
            time.sleep(1)

        final = batch_op.get_final_summary()
        yield f"data: {json.dumps({'type': 'batch_completed', **final})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream', ...)
```

### AgentSession Token Tracking

```python
# From: src/core/models.py (lines 686-762)
@dataclass
class AgentSession:
    """A session tracking agent workflow execution."""
    # ...
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_api_calls: int = 0
    # ...
```

**Usage for cost calculation:**
```python
def calculate_actual_cost(session: AgentSession, model: str) -> float:
    """Calculate actual cost from session token usage."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])

    input_cost = session.total_input_tokens * pricing["input"]
    output_cost = session.total_output_tokens * pricing["output"]

    return round(input_cost + output_cost, 2)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential processing | Concurrent with TaskQueue | Already implemented | Much faster batch operations |
| WebSocket for updates | Server-Sent Events (SSE) | Already in use | Simpler, less overhead |
| Manual token counting | Anthropic SDK usage field | SDK v0.18+ (2024) | Accurate, no maintenance |
| In-memory batch tracking | SQLite persistence | Recommended | Survives restarts, audit trail |

**Deprecated/outdated:**
- **queue.SimpleQueue:** Use queue.Queue (thread-safe with locks) — TaskQueue already uses this
- **Manual retry logic:** BaseAgent includes exponential backoff — leverage it
- **Fixed worker count:** Config.AGENT_MAX_CONCURRENT_TASKS is configurable — respect it

## Open Questions

1. **Token Average Update Frequency**
   - What we know: AgentSession stores token usage per operation
   - What's unclear: How often to recalculate averages from historical data
   - Recommendation: Add monthly cron job OR manual "Recalibrate Estimates" button in settings

2. **Batch Size Hard Limit**
   - What we know: User wants soft limit at 20 documents
   - What's unclear: Should there be a hard limit (e.g., 50)?
   - Recommendation: Yes, 50 hard limit to prevent server overload. Suggest splitting into multiple batches.

3. **Chained Operations State**
   - What we know: After batch audit, offer "Remediate all non-compliant"
   - What's unclear: Does this create a new batch or extend the current one?
   - Recommendation: Create new batch (separate history entry) but reference parent_batch_id for UX flow

4. **Cost Estimate Disclaimer**
   - What we know: Estimates won't be perfect
   - What's unclear: Should we show confidence interval (e.g., "$5-$8")?
   - Recommendation: Show single estimate with "~" prefix and footnote: "Estimated based on averages. Actual cost may vary ±20%."

## Validation Architecture

> Validation section omitted — no .planning/config.json found, defaulting to workflow.nyquist_validation: false

## Sources

### Primary (HIGH confidence)

- **Codebase Analysis:**
  - `src/core/task_queue.py` - TaskQueue implementation with progress tracking, concurrency
  - `src/api/audits.py` - SSE streaming pattern for audit progress
  - `src/api/remediation.py` - SSE streaming pattern for remediation progress
  - `src/core/models.py` - AgentSession with token tracking fields
  - `src/config.py` - AGENT_MAX_CONCURRENT_TASKS configuration

- **User Context:**
  - `.planning/phases/12-bulk-operations/12-CONTEXT.md` - User decisions and requirements
  - `CLAUDE.md` - Project architecture and patterns

### Secondary (MEDIUM confidence)

- **Anthropic Pricing (as of 2026-03-15):**
  - https://www.anthropic.com/pricing
  - Claude Sonnet 4: $3/$15 per 1M tokens (input/output)
  - Claude Opus 4.5: $15/$75 per 1M tokens (input/output)
  - **Note:** Verify pricing before implementation as rates may change

### Tertiary (LOW confidence)

- **Batch Processing Best Practices:**
  - General web search results on Flask SSE patterns (multiple sources agree)
  - TaskQueue pattern is standard producer-consumer (well-established pattern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All components already in use
- Architecture: HIGH - Extends proven patterns, minimal new code
- Pitfalls: MEDIUM - Based on analysis, not empirical testing
- Cost estimation: MEDIUM - Pricing verified, averages need calibration

**Research date:** 2026-03-15
**Valid until:** 2026-06-15 (3 months - pricing may change, Anthropic SDK updates)
