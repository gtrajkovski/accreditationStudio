# Phase 23: Audit Reproducibility - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Every audit can be explained and reproduced. Users can view exactly what inputs, model, and standards produced each audit result, and optionally re-run audits to compare against original findings.

</domain>

<decisions>
## Implementation Decisions

### Bundle Contents
- **D-01:** Full snapshot approach — capture model ID, standards library snapshot, document content hash, system prompts, tool definitions, all API parameters
- **D-02:** Include both inputs AND outputs — full round-trip (prompts sent + responses received) for complete audit trail
- **D-03:** Store in structured JSON format for easy parsing and display

### Explainer UI
- **D-04:** Dedicated page at `/audits/{id}/reproducibility` with full breakdown
- **D-05:** Two-tier view: executive summary by default, "Show technical details" toggle for deep dive
- **D-06:** Executive summary shows: model, date, standards count, document hash, key parameters
- **D-07:** Technical detail shows: all prompts, tool calls, response tokens, timing

### Storage Approach
- **D-08:** Database table (`audit_reproducibility`) with JSON blob column
- **D-09:** Hybrid compression: raw JSON in database, ZIP export includes compressed bundle
- **D-10:** Link to audit_runs table via audit_id foreign key

### Replay Capability
- **D-11:** Compare mode: re-run audit with stored inputs AND diff results against original
- **D-12:** Show side-by-side comparison of findings (added, removed, changed)
- **D-13:** Warn and proceed when model version has changed — show warning banner but allow comparison

### Claude's Discretion
- Exact JSON schema for reproducibility bundle
- Diff algorithm for comparing findings
- UI styling for comparison view
- How to handle very large bundles (truncation, pagination)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Audit Infrastructure
- `src/agents/compliance_audit.py` — ComplianceAuditAgent with 7-pass audit workflow
- `src/services/audit_trail_service.py` — Existing session log export service
- `src/core/models.py` — Audit, AuditFinding, AgentSession models

### Session Storage
- `workspace/{institution_id}/agent_sessions/*.json` — Current session storage pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AuditTrailService`: Already queries/exports session logs — pattern for bundle retrieval
- `ComplianceAuditAgent`: Has tool definitions, prompts — these become bundle content
- Existing audit detail page: Can link to new reproducibility page

### Established Patterns
- JSON blob storage in SQLite (used by several tables)
- ZIP export with manifest (audit trail export does this)
- Modal/page patterns for detail views

### Integration Points
- Audit runs table — add reproducibility_id foreign key or embed
- Audit detail UI — add "View Reproducibility" link
- Agent session creation — capture bundle at audit completion

</code_context>

<specifics>
## Specific Ideas

- Link from audit findings page: "How was this audit produced?"
- Compare view should highlight changed findings clearly (green/red diff style)
- Model version warning should be prominent but not blocking

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-audit-reproducibility*
*Context gathered: 2026-03-22*
