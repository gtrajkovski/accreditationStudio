# Architecture

**Analysis Date:** 2026-03-21

## Pattern Overview

**Overall:** Tiered Agent-Based Microservices with Layered Workspace Persistence

**Key Characteristics:**
- **24-agent tiered architecture** (Tier 0-6) with registry-based dynamic dispatch
- **Separation of concerns** across domain (core), agents (AI), services (business logic), and API (HTTP) layers
- **Workspace-as-truth**: Local filesystem persistence per institution with SQLite metadata store
- **Streaming-first design**: SSE (Server-Sent Events) for real-time agent progress updates
- **Session-based state management**: AgentSession tracks tasks, checkpoints, tool calls, and token usage

## Layers

**Domain (Core):**
- Purpose: Immutable data models, enums, workspace structure
- Location: `src/core/`
- Contains: `models.py` (dataclasses), `workspace.py` (WorkspaceManager), `standards_store.py`, `task_queue.py`
- Depends on: Python stdlib, config
- Used by: All other layers

**AI & Agents:**
- Purpose: Autonomous task execution via Claude API with tool use
- Location: `src/agents/`
- Contains: `base_agent.py` (abstract), 30+ specialized agents (compliance_audit, remediation, packet_agent, etc.)
- Depends on: Anthropic SDK, core models, services
- Used by: API layer (via registry), orchestrator

**Services:**
- Purpose: Business logic, computation, analysis (non-AI)
- Location: `src/services/`
- Contains: readiness_service (scoring), impact_analysis_service, knowledge_graph_service, site_visit_service, portfolio_service, etc.
- Depends on: Core models, database, workspace manager
- Used by: API endpoints, agents

**API (REST):**
- Purpose: HTTP endpoints with dependency injection pattern
- Location: `src/api/`
- Contains: 40+ blueprints (chat, agents, audits, remediation, packets, etc.), each with `init_*_bp(dependencies)` DI function
- Depends on: Agents, services, core
- Used by: Flask app (app.py)

**Importers & Processing:**
- Purpose: Document ingestion pipeline (parse, PII detect, chunk)
- Location: `src/importers/`, `src/exporters/`, `src/generators/`
- Contains: `document_parser.py` (PDF/DOCX/TXT), `pii_detector.py`, `document_chunker.py`, DOCX/ZIP exporters
- Depends on: pdfplumber, python-docx, pytesseract
- Used by: Ingestion agent, audit flows

**Search & Retrieval:**
- Purpose: Semantic search with embeddings (ChromaDB vector store)
- Location: `src/search/`
- Contains: Embedding generation, vector store interface
- Depends on: ChromaDB, Anthropic embeddings
- Used by: Retrieval agents, evidence search

**Database:**
- Purpose: SQLite persistence with versioned schema
- Location: `src/db/`
- Contains: `connection.py` (connection pooling), `migrate.py` (28 migrations), raw SQL in `migrations/`
- Depends on: sqlite3
- Used by: All layers that need durable state (sessions, findings, audit results)

**Internationalization:**
- Purpose: Multi-locale UI text (en-US, es-PR)
- Location: `src/i18n/`
- Contains: `en-US.json`, `es-PR.json` with dot-notation keys
- Depends on: None
- Used by: Templates (via context processor), Python code

## Data Flow

**Document Audit Flow:**

1. User uploads document → `POST /api/institutions/{id}/audits`
2. API creates audit session (`AgentSession`) with `ComplianceAuditAgent`
3. Audit agent spawns **5-pass strategy**:
   - Pass 1: Extract standards requirements
   - Pass 2: Extract policy/procedure text
   - Pass 3: Map evidence to standards
   - Pass 4: Score compliance
   - Pass 5: Aggregate findings
4. Each tool call recorded with input, output, duration, success
5. Findings persisted to database (`audit_findings` table)
6. Results streamed to UI via SSE (`/api/agents/sessions/{id}/stream`)

**Remediation Flow:**

1. User selects audit findings to remediate
2. `RemediationAgent` generates:
   - **Redlines**: Document with tracked changes
   - **Finals**: Remediated version
   - **Truth index**: Single source of truth mapping
3. WorkspaceManager persists to: `workspace/{institution_id}/programs/{program_id}/redlines/` and `finals/`
4. User approves via `/api/remediation/approve` → updates truth index
5. Consistency agent cross-checks against other documents

**Compliance Calendar Flow:**

1. `ComplianceCalendarAgent` parses accreditor standards for deadlines
2. Generates events (e.g., "SER due 6 months before visit")
3. Syncs to database (`compliance_events` table)
4. Scheduler service (`src/services/scheduler_service.py`) triggers reminders
5. Email service (`src/services/email_service.py`) sends notifications

**Readiness Score Computation:**

1. `compute_readiness(institution_id)` called
2. Queries 4 sub-scores (documents, compliance, evidence, consistency)
3. Weights: compliance 40%, evidence 25%, documents 20%, consistency 15%
4. Returns `ReadinessScore` with blockers and next actions
5. Cached 10 minutes (`CACHE_WINDOW_MINUTES = 10`)

**Knowledge Graph Construction:**

1. `KnowledgeGraphAgent` scans institution documents
2. Extracts entities (policies, requirements, outcomes, faculty qualifications)
3. Infers relationships (e.g., "Policy X implements Requirement Y")
4. Builds directed graph (`knowledge_graph_relations` table)
5. Enables impact analysis: change to Policy → affected requirements → related documents

## State Management

**Workspace Structure:**
```
workspace/{institution_id}/
├── institution.json                  # Institution metadata
├── truth_index.json                  # Single source of truth mapping
├── programs/{program_id}/
│   ├── originals/                    # Original uploaded documents (read-only)
│   ├── audits/                       # Audit reports
│   ├── redlines/                     # Documents with tracked changes
│   ├── finals/                       # Remediated versions (working truth)
│   ├── crossrefs/                    # Cross-reference docs
│   └── checklists/                   # Generated checklists
├── catalog/                          # Institutional catalog
├── policies/                         # Policy documents
├── exhibits/                         # Evidence exhibits
├── faculty/                          # Faculty records
├── achievements/                     # Learning outcomes
├── visit_prep/                       # Site visit prep materials
├── responses/                        # Team report responses
├── submissions/                      # Submission packets
└── agent_sessions/                   # Full audit trail (JSON per session)
```

**Database Schema:**
- `institutions` - Institution records
- `documents` - Document metadata
- `audit_findings` - Compliance findings
- `remediation_jobs` - Remediation state
- `agent_sessions` - Session history with tool calls
- `knowledge_graph_relations` - Entity relationships
- `compliance_events` - Calendar deadlines
- Plus 20+ other tables for all features

**Session State (In-Memory):**
- `AgentSession`: messages, tasks, checkpoints, tool_calls, status, tokens_used
- Callbacks notify UI of progress
- Persisted to workspace after each turn

## Key Abstractions

**BaseAgent:**
- Purpose: Abstract base for all 30+ agents
- Examples: `src/agents/compliance_audit.py`, `src/agents/remediation_agent.py`, `src/agents/knowledge_graph_agent.py`
- Pattern: Subclasses implement `agent_type`, `system_prompt`, `tools`, `_execute_tool()`
- Tool lifecycle: User invokes tool → Claude API generates tool_use block → `_execute_tool()` → record outcome

**WorkspaceManager:**
- Purpose: Abstraction over filesystem workspace
- Examples:
  - `create_institution()` → initializes institution folder
  - `save_remediation_document()` → persists to finals/
  - `save_agent_session()` → JSON to agent_sessions/
- Pattern: All file I/O flows through this class for safety and consistency

**AgentRegistry:**
- Purpose: Dynamic agent lookup and instantiation
- Pattern: `@register_agent(AgentType.MY_AGENT)` decorator registers class
  - `AgentRegistry.create(agent_type, session, workspace_manager)` → agent instance
  - Enables orchestrator to dispatch by type without hardcoded imports

**Blueprint DI Pattern:**
- Purpose: Centralized dependency injection for all API endpoints
- Pattern: Each blueprint has `init_*_bp(dependencies...)` called in `app.py`
  - Module-level variables store dependencies
  - All routes access via module globals
  - Example: `src/api/audits.py` stores `_workspace_manager` globally

**Confidence Threshold:**
- Purpose: Quality gate for AI outputs
- Pattern: Agents check `Config.AGENT_CONFIDENCE_THRESHOLD` (default 0.7)
- Action: Below threshold → create HumanCheckpoint (flags for user review)

## Entry Points

**Web Application:**
- Location: `app.py`
- Triggers: Flask development server on port 5003
- Responsibilities: Initialize core services, register blueprints, inject i18n context

**Main Routes:**
- `GET /` → Redirects to dashboard
- `GET /dashboard` → Institution metrics, readiness overview
- `GET /institutions/{id}` → Institution detail page
- `POST /api/audits` → Start audit workflow (SSE streaming)
- `POST /api/remediation/` → Apply remediation
- `POST /api/agents/sessions/{id}/approve` → Approve human checkpoint

**Background Tasks:**
- Location: `src/core/task_queue.py`
- Triggers: Enqueued from API endpoints via `get_task_queue().submit()`
- Workers: 3 threads process work queue asynchronously

**Database Initialization:**
- Location: `src/db/migrate.py`
- Triggers: On app startup or CLI `flask db upgrade`
- Applies: All pending migrations in sequence

## Error Handling

**Strategy:** Layered with AI safety guardrails

**Agent Layer:**
- Token budget exceeded → suspend session with error
- Tool execution fails → log error, include in context for retry
- Confidence < 0.7 → create HumanCheckpoint instead of auto-applying
- PII detected in output → redaction filter masks before persistence

**API Layer:**
- Invalid request → 400 Bad Request with error message
- Institution not found → 404
- Missing dependency → 500 with diagnostic
- SSE stream errors → client reconnects

**Database Layer:**
- Connection failures → retry with exponential backoff
- Constraint violation → rollback and raise IntegrityError
- Migration failures → halt and report schema version mismatch

**Workspace Layer:**
- Path traversal attempts → sanitize via `_sanitize_path()`
- Missing institution folder → create with defaults
- Corrupted JSON → log error and fallback to empty state

## Cross-Cutting Concerns

**Logging:**
- Agent execution logged to `agent_sessions/{id}/log.json`
- Each tool call records duration, tokens, success/failure
- API requests logged via Flask (development mode)

**Validation:**
- All domain objects implement `to_dict()` / `from_dict()` with field filtering (unknown fields ignored)
- Document type enums enforce valid types
- Dates stored as ISO 8601 strings (UTC)

**Authentication:**
- Localhost single-user (same model as Course Builder Studio)
- No session management; trusted environment
- Environment-based API key for Anthropic

**Compliance:**
- PII detection pipeline flags student names, SSNs, emails
- `PII_REDACTION` agent replaces with `[REDACTED:pii_type]`
- Original documents preserved in `originals/` (read-only)
- Audit trail in `agent_sessions/` for every agent invocation

---

*Architecture analysis: 2026-03-21*
