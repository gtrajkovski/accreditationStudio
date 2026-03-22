# Phase 22: Change Detection + Targeted Re-Audit - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Incremental re-audits for changed documents only. Detects document modifications via SHA256 comparison (infrastructure from Phase 20), notifies users, and enables targeted re-audit of impacted items rather than full re-audit.

</domain>

<decisions>
## Implementation Decisions

### Change Notification UX
- **D-01:** Non-blocking badge notification on dashboard and document list
- **D-02:** User checks changes when ready — no interruptive modals or forced acknowledgment
- **D-03:** Badge shows count of documents with pending changes

### Re-audit Scope Rules
- **D-04:** Full standards cascade — re-audit all documents mapped to standards affected by the changed document
- **D-05:** Use existing finding_standard_refs table to determine which standards are affected
- **D-06:** Scope calculation: changed doc → affected standards → all docs with findings for those standards

### Recommendation Behavior
- **D-07:** Manual trigger only — user explicitly requests re-audit
- **D-08:** No auto-queuing of re-audits
- **D-09:** "Re-audit Impacted" button visible when changes detected
- **D-10:** Batch multiple changed documents into single re-audit request

### Change History Tracking
- **D-11:** Full diff view — side-by-side comparison of old vs new content
- **D-12:** Store previous document version for comparison
- **D-13:** Diff shows section-level changes (added, modified, removed)

### Claude's Discretion
- Diff algorithm implementation (character-level vs line-level vs section-level)
- Badge styling and animation
- How long to retain previous versions (recommend: until next audit completes)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Change Detection Infrastructure
- `src/services/autopilot_service.py` — SHA256 change detection already implemented (Phase 20)
- `src/db/migrations/0030_autopilot.sql` — document_hashes table schema

### Audit System
- `src/agents/compliance_audit_agent.py` — Existing audit agent to invoke for re-audit
- `src/api/audits.py` — Audit API endpoints pattern

### Standards Mapping
- `src/db/migrations/0005_audits.sql` — finding_standard_refs table for cascade scope

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AutopilotService.detect_document_changes()` — SHA256 comparison already implemented
- `document_hashes` table — stores SHA256 per document
- `ComplianceAuditAgent` — existing audit execution

### Established Patterns
- Badge notifications used in work queue (pending items count)
- SSE streaming for long-running operations (audit progress)
- Modal confirmations for batch operations

### Integration Points
- Document upload endpoint (`src/api/documents.py`) — trigger change detection
- Dashboard page — display change notification badge
- Compliance page — show diff view and re-audit button

</code_context>

<specifics>
## Specific Ideas

- Diff view should highlight changes clearly (green for additions, red for removals)
- Re-audit should show which standards will be checked before user confirms
- Badge should clear after user views changes or triggers re-audit

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-change-detection*
*Context gathered: 2026-03-22*
