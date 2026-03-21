# Codebase Concerns

**Analysis Date:** 2026-03-21

## Tech Debt

**Incomplete Orchestrator Delegation:**
- Issue: Five critical orchestrator agent tools delegate to agents that don't exist: DocumentAnalyzer, GapAnalyzer, EvidenceMapper (separate from registry agent), ComplianceChecker, SelfStudyWriter
- Files: `src/agents/orchestrator_agent.py` (lines 326, 341, 377, 392, 429)
- Impact: Orchestrator workflow cannot execute end-to-end; all delegation stages return stub responses instead of real results
- Fix approach: Either (1) remove placeholder delegations and have orchestrator implement analysis directly, or (2) create the missing agents with proper registry entries and tool implementations

**Incomplete Evidence Guardian Implementation:**
- Issue: Two critical Evidence Guardian tools are stubs returning hardcoded responses
- Files: `src/agents/evidence_guardian.py` (lines 227, 246)
- Impact: Cannot validate audit findings or calculate evidence coverage from indexed documents; evidence scoring is non-functional
- Fix approach: Implement audit finding loading from workspace and actual coverage calculation from indexed documents; currently blocks evidence validation workflows

**Models File Size & Maintainability:**
- Issue: Single monolithic models.py file is 2,584 lines containing 40+ dataclasses, 10+ enums, serialization logic, helper functions, and tests
- Files: `src/core/models.py`
- Impact: Difficult to navigate, changes affect entire domain layer, testing individual models requires full import chain
- Fix approach: Split by domain: `models/audit.py`, `models/document.py`, `models/agent.py`, `models/compliance.py`; consolidate imports in `__init__.py`

**AgentType Enum Sprawl:**
- Issue: AgentType enum contains 30+ entries with multiple legacy aliases and naming inconsistencies (INGESTION, STANDARDS_LIBRARIAN, POLICY_CONSISTENCY, CROSSWALK_BUILDER, PACKET_ASSEMBLER, SITE_VISIT_PREP, CALENDAR_DEADLINE, EVIDENCE_MAPPER)
- Files: `src/agents/base_agent.py` (lines 29-112)
- Impact: Confusing agent registry; hard to know canonical names; potential agent dispatch bugs if legacy names are used
- Fix approach: Remove all legacy aliases; map each agent registration to single canonical name; update registry lookup to fail on unknown types instead of silently supporting aliases

**Exception Handling Pattern Issues:**
- Issue: Multiple files use broad exception catching with silent failures (empty `pass` statements), particularly in service files
- Files: `src/services/autopilot_service.py` (line 631), `src/services/audit_reproducibility_service.py` (lines 150, 163, 322), `src/services/evidence_highlighting_service.py` (lines 130, 144, 222), `src/api/audits.py` (lines 500-501, 556-559, 622-623)
- Impact: Errors are swallowed silently; hard to debug failures; silent data loss or inconsistency possible
- Fix approach: Replace bare `pass` with explicit error logging or re-raise with context; implement structured error responses in APIs

**Global Variable Mutation in Blueprint Modules:**
- Issue: Every API blueprint uses module-level `_workspace_manager = None` and global function `init_*_bp()` to inject dependencies (32 blueprints affected)
- Files: All files in `src/api/` (e.g., `audits_bp.py` line 24, `checklists_bp` line 26, etc.)
- Impact: Hard to test in isolation; state leaks across test runs; initialization order-dependent behavior
- Fix approach: Implement proper Flask app context or request-scoped dependency container instead of global mutation

---

## Known Bugs

**Autopilot Service Stub Implementation:**
- Symptoms: Autopilot tasks are created but don't actually run audits; line 532 in `autopilot_service.py` notes "TODO: Implement agent-based audit"
- Files: `src/services/autopilot_service.py` (line 532)
- Trigger: Enable `run_audit=True` in AutopilotConfig
- Workaround: Manually trigger audits via ComplianceAuditAgent instead of relying on scheduled autopilot

**Workspace Aggregation Incomplete:**
- Symptoms: Truth index aggregation in `compute_readiness()` doesn't include actual audit findings; returns placeholder scores
- Files: `src/core/workspace.py` (line 376)
- Trigger: Call readiness score with compliance sub-score
- Workaround: Audit findings are stored in database but not aggregated into truth index; use database queries directly instead of workspace API

**Evidence Highlighting Edge Cases:**
- Issue: Fuzzy matching in evidence highlighting may produce false positives when document text contains multiple similar phrases
- Files: `src/services/evidence_highlighting_service.py` (lines 130, 144, 222 contain error suppression)
- Impact: Evidence highlights may point to wrong locations; users may verify against incorrect text
- Safe modification: Add strict matching mode requiring minimum sequence match length before fuzzy fallback

---

## Security Considerations

**PII Redaction Coverage:**
- Risk: PII detection pattern-based and may miss institutional-specific identifiers (student IDs, employee numbers); no explicit opt-in for scope
- Files: `src/importers/pii_detector.py` (patterns-based detection)
- Current mitigation: Redacts common patterns (SSN, email, phone); user can review before storage
- Recommendations: (1) Add regex pattern customization per institution, (2) implement manual review queue for uncertain matches, (3) add audit log of all redactions, (4) support re-redaction if new patterns found

**API Authentication Absent:**
- Risk: No API key validation or user authentication on endpoints; direct HTTP access to any institution
- Files: All `src/api/*.py` files
- Current mitigation: Single-user localhost tool only; not exposed to internet
- Recommendations: (1) Add Flask-Login integration for session management, (2) implement API key rotation, (3) add request signing for external API integrations

**Evidence Storage & Retention:**
- Risk: Indexed documents stored in ChromaDB with embeddings; if database leaked, could extract original text via embedding inversion
- Files: `src/search/` integration
- Current mitigation: ChromaDB persisted locally; no backup to cloud storage
- Recommendations: (1) implement document retention policies (auto-purge old audits), (2) add encryption at rest, (3) add data masking in search results for non-privileged roles

**Configuration Secrets:**
- Risk: `.env` file could contain API keys; no validation that required secrets are present before app starts
- Files: `app.py` initialization
- Current mitigation: `.env` in `.gitignore`; ANTHROPIC_API_KEY required for operation
- Recommendations: (1) fail fast if critical env vars missing, (2) implement secret rotation mechanism, (3) add audit logging for all API calls using credentials

---

## Performance Bottlenecks

**Compliance Audit Multi-Pass Design:**
- Problem: ComplianceAuditAgent runs 5-7 sequential passes over document (completeness, standards, consistency, severity, remediation); each requires Claude API call
- Files: `src/agents/compliance_audit.py` (lines 32-39, tool structure)
- Cause: Each pass is independent tool invocation; no batching or streaming
- Improvement path: (1) combine passes into single parameterized tool, (2) use streaming completions for partial results, (3) implement caching of document embeddings between passes

**Model File Size and Import Time:**
- Problem: 2,584-line models.py file means importing any single model requires loading entire domain
- Files: `src/core/models.py`
- Cause: Monolithic design; all enums, dataclasses, helpers in one file
- Improvement path: Modularize into 5-6 files; test import performance before/after split

**Workspace File I/O:**
- Problem: No caching of workspace JSON files (institution.json, truth_index.json); each load is full disk read
- Files: `src/core/workspace.py` (load methods)
- Cause: Simple file-based storage; no in-memory cache
- Improvement path: (1) implement lru_cache decorator on load methods, (2) add TTL-based invalidation, (3) watch filesystem for changes

**Search Embedding Computation:**
- Problem: Document chunking + embedding happens inline during ingestion; blocks audit start while waiting for vectors
- Files: `src/importers/document_parser.py` integration with `src/search/`
- Cause: Synchronous embedding pipeline
- Improvement path: (1) defer embedding to background job, (2) allow partial audit without embeddings, (3) cache embeddings per chunk

---

## Fragile Areas

**Evidence Guardian Implementation Fragility:**
- Files: `src/agents/evidence_guardian.py`
- Why fragile: Tool implementations are stubs (lines 227-239, 246-251); any code path calling `validate_audit_findings()` or `get_evidence_score()` receives placeholder response. Production use will fail silently.
- Safe modification: Before calling evidence guardian tools, check response for `"status": "stub"` and handle separately
- Test coverage: No unit tests for evidence validation logic; only stub returns tested

**Orchestrator Workflow State Management:**
- Files: `src/agents/orchestrator_agent.py` (lines 317, 359, 411, etc.)
- Why fragile: Workflow stage tracking uses `self._current_stage` string field (line 317) with no validation against STAGES list; if stage name misspelled, workflow may get stuck. No recovery path if network fails mid-turn.
- Safe modification: Validate stage against enum before setting; checkpoint resumption must match exact stage name
- Test coverage: Mock Claude client tests only; no integration tests for full workflow with pauses/resumes

**Readiness Score Computation Gaps:**
- Files: `src/services/readiness_service.py` (lines 376 in workspace.py)
- Why fragile: Sub-scores (documents, compliance, evidence, consistency) are calculated independently; no cross-check that they aggregate sensibly. Compliance score may be 100% while actual audit findings show failures.
- Safe modification: Add validation that compliance sub-score ≤ severity-weighted actual findings
- Test coverage: Unit tests for individual sub-score calculations; no integration test comparing computed score to actual state

**Agent Session Persistence:**
- Files: `src/core/models.py` (AgentSession class); `src/api/agents.py` (session save/load)
- Why fragile: Sessions saved as JSON with nested arrays (messages, tool_calls, checkpoints); no migration path if schema changes. Large sessions (1000+ turns) become huge JSON blobs.
- Safe modification: (1) implement schema versioning in JSON, (2) paginate large sessions, (3) compress message history after completion
- Test coverage: No tests for session round-trip serialization with all fields populated

---

## Scaling Limits

**Single SQLite Database:**
- Current capacity: ~100MB default SQLite file size before performance degrades; vector indexes can be 50-200MB each
- Limit: Breaks at ~50-100 institutions with years of document history; concurrent writes limited to single writer
- Scaling path: (1) migrate to PostgreSQL + pgvector for vector storage, (2) implement connection pooling, (3) add read replicas for search queries

**In-Memory Agent Sessions:**
- Current capacity: `_active_audits` dict in `audits.py` (line 25) stores all running audits in process memory; no limit check
- Limit: Memory exhaustion if 100+ concurrent audits; server crash on OOM
- Scaling path: (1) implement audit persistence to database, (2) load sessions on-demand from disk, (3) implement audit cleanup after 24 hours

**Workspace File System:**
- Current capacity: One folder per institution with up to 50+ subdirectories and files; no archival or cleanup
- Limit: Filesystem scalability at ~1000 institutions; slow recursive traversals for portfolio operations
- Scaling path: (1) implement document archival after 1 year, (2) move old audits to archive storage, (3) database-backed folder index instead of recursive filesystem walks

**Vector Store Capacity:**
- Current capacity: ChromaDB embedded SQLite; no explicit limit but grows with every indexed document
- Limit: Search latency increases 10-100x with >10M vectors; no pruning strategy
- Scaling path: (1) implement vector deduplication (don't index near-duplicate chunks), (2) tier storage (hot vectors in memory, cold on disk), (3) implement vector cleanup on document deletion

---

## Dependencies at Risk

**Anthropic SDK Version Pinning:**
- Risk: No explicit version constraint in requirements.txt; could break on major API changes
- Impact: Model parameter changes, tool schema format changes could crash agents
- Migration plan: (1) pin to specific minor version (e.g., `anthropic>=1.0,<2.0`), (2) implement API adapter layer to handle version differences, (3) add integration tests against latest SDK

**ChromaDB Persistence:**
- Risk: ChromaDB's on-disk format not guaranteed stable between versions; migrations not supported
- Impact: Major version upgrade could corrupt vector database
- Migration plan: (1) export vectors to JSON before upgrade, (2) implement backup/restore tooling, (3) test upgrade path on copy before production

**Flask Dependency Chain:**
- Risk: Flask + Jinja2 templates; no explicit version locking for Jinja2; could introduce breaking changes in template rendering
- Impact: Template syntax changes could break all Jinja2 pages
- Migration plan: (1) lock Jinja2 to stable version, (2) add template unit tests, (3) validate all templates on startup

---

## Missing Critical Features

**Multi-Tenancy Support:**
- Problem: Code assumes single institution per workspace; portfolio API (Phase 8) adds institution switching but doesn't enforce isolation
- Blocks: Cannot safely run AccreditAI for multiple customers on shared server; no data isolation between institutions
- Why missing: Architecture designed for single-user localhost tool; would require database schema changes and API auth

**Audit Reproducibility:**
- Problem: No way to replay exact same audit configuration; Claude non-determinism means same document + standards produces different findings
- Blocks: Cannot generate consistent evidence for accreditor appeals; audits not reproducible for quality assurance
- Why missing: Would require audit snapshot (document + standards + prompt + model version) and deterministic seed control

**Change Tracking & Diffs:**
- Problem: Documents stored in originals/finals folders but no explicit version control; truth index doesn't track who changed what when
- Blocks: Cannot audit trail changes to policies; difficult to identify what changed between audit passes
- Why missing: Would require git integration or custom VCS layer in workspace

**Offline Mode:**
- Problem: Every significant operation requires Claude API call; no offline-first capability or fallback
- Blocks: Cannot use AccreditAI if Anthropic API is down; no local-only mode
- Why missing: Would require implementing fallback rules engines and local LLM capability

---

## Test Coverage Gaps

**Untested Agent Delegation Failures:**
- What's not tested: What happens when orchestrator tries to delegate to non-existent agents; error propagation from stub implementations
- Files: `src/agents/orchestrator_agent.py` (all delegation methods); `src/tests/` (if any integration tests exist)
- Risk: Silent failures in workflow; user doesn't know delegation failed; audit proceeds with incomplete data
- Priority: **High** - Blocks production readiness

**Evidence Validation No-Op:**
- What's not tested: Evidence guardian tools that are stubs; calling validate_audit_findings() or get_evidence_score() with real data
- Files: `src/agents/evidence_guardian.py` (lines 222-251 tool implementations)
- Risk: Evidence validation produces fake results; system appears to validate when it doesn't; compliance claims go unchecked
- Priority: **Critical** - Blocks evidence integrity guarantee

**Session Persistence Round-Trip:**
- What's not tested: Agent sessions serialized to JSON and loaded back; whether all nested structures survive round-trip
- Files: `src/core/models.py` (AgentSession, ToolCall, HumanCheckpoint); `src/api/agents.py` (session save/load endpoints)
- Risk: Sessions loaded from disk missing fields; UI displays incomplete audit results
- Priority: **High** - Affects audit history/resume features

**Workspace Migration:**
- What's not tested: Running `flask db upgrade` against existing workspace; whether old institution.json files load with new code
- Files: `src/db/migrations/` (25 migrations); `src/core/workspace.py` (load methods)
- Risk: Database upgrade breaks workspace loading; users cannot access institutions after upgrade
- Priority: **High** - Blocks deployment

**Concurrent Audit Handling:**
- What's not tested: Two audits running simultaneously on same institution; whether `_active_audits` dict gets corrupted
- Files: `src/api/audits.py` (line 25); audit streaming endpoints
- Risk: Race conditions; tool results mixed between audits; data corruption
- Priority: **Medium** - Single-user tool but worth testing for future

---

## Known Limitations

**Single-User Localhost Architecture:**
- Limitation: Entire system assumes one user at a time; no role-based access control (admin, reviewer, viewer)
- Impact: Cannot delegate review tasks; all users see all data
- Workaround: Manual communication outside system; print reports and email

**Non-Deterministic Compliance Findings:**
- Limitation: Claude API produces different findings each time for same document + standards (temperature >0)
- Impact: Two audits of identical document produce slightly different findings; cannot compare audit quality across models
- Workaround: Set temperature=0 for determinism but then reduced reasoning quality

**Embedded Vector Store Only:**
- Limitation: ChromaDB embedded (no client-server); cannot scale to multiple processes or machines
- Impact: Cannot run background workers; search performance tied to Flask process performance
- Workaround: Single process only; background jobs must be quick or defer to future Flask instance

---

*Concerns audit: 2026-03-21*
