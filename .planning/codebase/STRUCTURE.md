# Codebase Structure

**Analysis Date:** 2026-03-21

## Directory Layout

```
accreditationStudio/
├── app.py                           # Flask app entry point, blueprint registration
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Pytest configuration
├── SPEC.md                          # Complete feature specification
├── CLAUDE.md                        # Development guidelines (this file)
├── DEPLOYMENT.md                    # Deployment instructions
├── PROJECT.md                       # Project overview
│
├── .env                             # Environment variables (secrets, never commit)
├── .env.example                     # Template for required vars
├── docker-compose.yml               # Docker local dev environment
├── Dockerfile                       # Container image definition
│
├── .planning/                       # Project planning artifacts
│   ├── STATE.md                     # Current session state, urgent TODOs
│   ├── IMPLEMENTATION_PROMPTS.md    # Weekly feature shipping prompts
│   ├── codebase/                    # Generated codebase analysis (this dir)
│   │   ├── ARCHITECTURE.md          # (generated)
│   │   └── STRUCTURE.md             # (generated)
│   └── phases/                      # Per-phase planning docs
│
├── src/                             # Main application source code
│   ├── config.py                    # Global configuration (Config class)
│   │
│   ├── core/                        # Domain models and workspace management
│   │   ├── __init__.py
│   │   ├── models.py                # All dataclasses (Institution, Program, Document, AgentSession, etc.)
│   │   ├── workspace.py             # WorkspaceManager - filesystem abstraction
│   │   ├── standards_store.py       # StandardsStore - accreditor standards loader
│   │   ├── task_queue.py            # Background task queue with worker threads
│   │   └── migrations/              # (Symlink to db/migrations)
│   │
│   ├── agents/                      # 30+ specialized AI agents
│   │   ├── __init__.py              # Agent imports and utilities
│   │   ├── base_agent.py            # BaseAgent abstract class, AgentType enum
│   │   ├── registry.py              # AgentRegistry for dynamic dispatch
│   │   │
│   │   ├── orchestrator_agent.py    # Tier 0 - Main workflow orchestrator
│   │   ├── evidence_guardian.py     # Tier 0 - Safety and governance
│   │   ├── policy_safety.py         # Tier 0 - Policy compliance
│   │   │
│   │   ├── ingestion_agent.py       # Tier 1 - Document intake and parsing
│   │   ├── pii_redaction.py         # Tier 1 - PII detection and masking
│   │   ├── parsing_structure.py     # Tier 1 - Section extraction
│   │   ├── retrieval_tuning.py      # Tier 1 - Semantic search optimization
│   │   │
│   │   ├── standards_librarian.py   # Tier 2 - Standards curation
│   │   ├── regulatory_stack.py      # Tier 2 - Federal/state regulations
│   │   ├── standards_translator.py  # Tier 2 - Standards mapping
│   │   │
│   │   ├── compliance_audit.py      # Tier 3 - 5-pass audit engine (main agent)
│   │   ├── policy_consistency.py    # Tier 3 - Cross-document consistency
│   │   ├── risk_scorer.py           # Tier 3 - Risk assessment
│   │   │
│   │   ├── remediation_agent.py     # Tier 4 - Document remediation (main agent)
│   │   ├── truth_index_curator.py   # Tier 4 - Single source of truth management
│   │   ├── exhibit_builder.py       # Tier 4 - Evidence exhibit generation
│   │   │
│   │   ├── narrative_agent.py       # Tier 5 - Issue response drafting
│   │   ├── packet_agent.py          # Tier 5 - Submission packet assembly
│   │   ├── site_visit_prep.py       # Tier 5 - Interview prep and coaching
│   │   │
│   │   ├── faculty_agent.py         # Faculty credential tracking and qualification audits
│   │   ├── catalog_agent.py         # Institutional catalog generation
│   │   ├── evidence_agent.py        # Evidence and exhibit validation
│   │   ├── achievement_agent.py     # Learning outcomes and benchmarks
│   │   │
│   │   ├── interview_prep_agent.py  # Interview question generation
│   │   ├── ser_drafting_agent.py    # Self-Evaluation Report drafting
│   │   ├── team_report_agent.py     # Post-visit team report responses
│   │   ├── compliance_calendar_agent.py  # Deadline and event management
│   │   ├── document_review_agent.py # Document review scheduling
│   │   ├── knowledge_graph_agent.py # Entity extraction and relationship mapping
│   │   │
│   │   └── prompts/                 # Agent system prompts (separate files)
│   │
│   ├── ai/                          # AI client wrapper
│   │   ├── __init__.py
│   │   └── client.py                # AIClient - Anthropic SDK wrapper with history
│   │
│   ├── api/                         # 40+ REST API blueprints
│   │   ├── __init__.py              # Blueprint exports
│   │   ├── chat.py                  # Chat conversational endpoints
│   │   ├── agents.py                # Workflow and session management
│   │   ├── institutions.py          # Institution CRUD and listing
│   │   ├── standards.py             # Standards library endpoints
│   │   ├── settings.py              # User preferences (theme, locale)
│   │   │
│   │   ├── readiness.py             # Readiness score calculation
│   │   ├── work_queue.py            # Background task status
│   │   ├── autopilot.py             # Automated workflow orchestration
│   │   │
│   │   ├── audits.py                # Compliance audit workflow (main endpoint)
│   │   ├── remediation.py           # Remediation and approval endpoints
│   │   ├── checklists.py            # Checklist generation and export
│   │   ├── packets.py               # Submission packet building
│   │   ├── action_plans.py          # Action item tracking
│   │   │
│   │   ├── faculty.py               # Faculty records and credentials
│   │   ├── catalog.py               # Catalog validation and generation
│   │   ├── exhibits.py              # Evidence exhibit management
│   │   ├── achievements.py          # Learning outcome tracking
│   │   │
│   │   ├── interview_prep.py        # Interview coaching endpoints
│   │   ├── ser.py                   # SER drafting endpoints
│   │   ├── team_reports.py          # Team report response workflow
│   │   ├── compliance_calendar.py   # Deadline management and reminders
│   │   ├── document_reviews.py      # Document review scheduling
│   │   ├── documents.py             # Document upload and management
│   │   │
│   │   ├── impact_analysis.py       # Change impact simulation
│   │   ├── knowledge_graph.py       # Entity explorer and graph queries
│   │   ├── timeline_planner.py      # Gantt chart and milestone planning
│   │   ├── site_visit.py            # Unified search and fact lookup
│   │   ├── coverage_map.py          # Standards coverage visualization
│   │   ├── simulation.py            # Accreditation scenario simulation
│   │   ├── portfolios.py            # Multi-institution portfolio management
│   │   ├── evidence_highlighting.py # Document text highlighting
│   │   ├── compliance_heatmap.py    # Standards × documents matrix
│   │   │
│   │   ├── batch_history.py         # Batch operation history and stats
│   │   ├── global_search.py         # Cross-institution full-text search
│   │   ├── standard_explainer.py    # Standards detail and clarification
│   │   ├── evidence_assistant.py    # Evidence discovery assistant
│   │   ├── reports.py               # Executive and compliance reporting
│   │   └── __init__.py              # Blueprint registration helper
│   │
│   ├── services/                    # Business logic and computation
│   │   ├── __init__.py
│   │   ├── readiness_service.py     # Readiness score (0-100) with sub-scores
│   │   ├── autopilot_service.py     # Automated workflow orchestration
│   │   ├── batch_service.py         # Batch operation management
│   │   ├── impact_analysis_service.py  # Change impact simulation
│   │   ├── knowledge_graph_service.py  # Entity extraction and graph operations
│   │   ├── portfolio_service.py     # Multi-institution aggregation
│   │   ├── site_visit_service.py    # Unified search across 6 sources
│   │   ├── coverage_map_service.py  # Standards coverage metrics
│   │   ├── compliance_heatmap_service.py  # Matrix aggregation
│   │   ├── evidence_highlighting_service.py  # Text and evidence mapping
│   │   ├── simulation_service.py    # Mock audit scenarios
│   │   ├── chat_context_service.py  # Chat history and context management
│   │   ├── evidence_assistant_service.py   # Evidence discovery
│   │   ├── standard_explainer_service.py   # Standards clarification
│   │   ├── report_service.py        # Report generation
│   │   ├── email_service.py         # Email notifications
│   │   ├── scheduler_service.py     # Task scheduling and reminders
│   │   └── [other services...]      # (13 total services)
│   │
│   ├── db/                          # Database management
│   │   ├── __init__.py
│   │   ├── connection.py            # SQLite connection and row factory
│   │   ├── migrate.py               # Migration runner
│   │   └── migrations/              # 28 versioned SQL schema files
│   │       ├── 0001_core.sql        # Institutions, documents
│   │       ├── 0002_docs.sql        # Document metadata
│   │       ├── 0005_audits.sql      # Audit findings
│   │       ├── 0010_readiness.sql   # Readiness scores
│   │       ├── 0016_team_reports.sql   # Team report responses
│   │       ├── 0018_knowledge_graph.sql # Entity relationships
│   │       ├── 0021_site_visit.sql  # FTS5 indexes
│   │       ├── 0023_portfolios.sql  # Multi-institution
│   │       └── [others...]          # (28 total)
│   │
│   ├── importers/                   # Document ingestion pipeline
│   │   ├── __init__.py
│   │   ├── document_parser.py       # PDF/DOCX/TXT parsing (pdfplumber, python-docx)
│   │   ├── pii_detector.py          # PII detection (names, SSNs, emails)
│   │   └── document_chunker.py      # Text chunking for embeddings
│   │
│   ├── exporters/                   # Document generation
│   │   ├── __init__.py
│   │   ├── docx_exporter.py         # DOCX generation
│   │   └── zip_exporter.py          # ZIP packaging for submissions
│   │
│   ├── generators/                  # Code and schema generation
│   │   ├── __init__.py
│   │   ├── base_generator.py        # Base generator class
│   │   └── schemas/                 # JSON schemas for various entities
│   │
│   ├── search/                      # Semantic search
│   │   ├── __init__.py
│   │   └── embeddings.py            # ChromaDB vector store wrapper
│   │
│   ├── validators/                  # Input and data validation
│   │   ├── __init__.py
│   │   └── document_validator.py    # Document structure validation
│   │
│   ├── accreditors/                 # Accreditor-specific implementations
│   │   ├── __init__.py
│   │   ├── registry.py              # Accreditor registry
│   │   ├── accsc/                   # ACCSC standards and parser
│   │   │   ├── __init__.py
│   │   │   ├── parser.py
│   │   │   └── sources.py
│   │   └── coe/                     # COE standards and parser
│   │       ├── __init__.py
│   │       ├── parser.py
│   │       └── sources.py
│   │
│   ├── regulatory/                  # Regulatory compliance
│   │   ├── __init__.py
│   │   └── states/                  # State-specific regulations
│   │
│   ├── i18n/                        # Internationalization
│   │   ├── __init__.py              # i18n functions (t(), get_all_strings())
│   │   ├── en-US.json               # English strings (dot-notation keys)
│   │   └── es-PR.json               # Spanish (Puerto Rico) strings
│   │
│   ├── auth/                        # Authentication (currently minimal)
│   │   └── __init__.py
│   │
│   └── tasks/                       # Scheduled tasks
│       └── __init__.py
│
├── templates/                       # Jinja2 HTML templates
│   ├── base.html                    # Base layout
│   ├── index.html                   # Home page
│   ├── auth/                        # Login/logout pages
│   ├── institutions/                # Institution pages
│   ├── pages/                       # Feature pages (audits, remediation, etc.)
│   ├── components/                  # Reusable UI components
│   ├── macros/                      # Jinja2 macros
│   ├── partials/                    # Template fragments
│   ├── portfolios/                  # Multi-institution portfolio pages
│   └── reports/                     # Report templates
│
├── static/                          # Frontend assets
│   ├── css/
│   │   ├── main.css                 # Global styles
│   │   ├── components/              # Component styles
│   │   └── pages/                   # Page-specific styles
│   ├── js/
│   │   ├── app.js                   # Main app entry point
│   │   ├── components/              # JavaScript components
│   │   └── utils/                   # Utilities (fetch, event handlers)
│   └── images/                      # Icons, logos
│
├── standards/                       # Accreditor standards data
│   ├── accsc.json                   # ACCSC standards hierarchy
│   ├── sacscoc.json                 # SACSCOC standards
│   └── [others...]                  # Other accreditors
│
├── workspace/                       # Institution workspace (generated at runtime)
│   └── {institution_id}/            # Per-institution folder
│       ├── institution.json
│       ├── truth_index.json
│       ├── programs/
│       ├── agent_sessions/
│       └── [other dirs...]
│
├── scripts/                         # Utility scripts
│   └── smoke_test.py                # Smoke tests for deployment
│
├── seed_data.py                     # Database seeding for development
├── projects/                        # Reference projects (internal)
└── _reference/                      # Course Builder Studio reference implementation
    ├── src/core/                    # Similar patterns to study
    ├── src/generators/              # Reuse-able generator patterns
    └── [others...]
```

## Directory Purposes

**`src/core/`:**
- Purpose: Core domain models, workspace abstraction, standards definitions
- Contains: Dataclasses (Institution, Program, Document, Finding, etc.), WorkspaceManager, StandardsStore, TaskQueue
- Key files: `models.py` (200+ lines), `workspace.py` (300+ lines)

**`src/agents/`:**
- Purpose: Specialized AI agents that orchestrate multi-step workflows
- Contains: 30 agent implementations, base class, registry
- Key files: `compliance_audit.py` (5-pass engine), `remediation_agent.py`, `packet_agent.py`
- Pattern: Each agent implements `system_prompt`, `tools`, `_execute_tool()`

**`src/api/`:**
- Purpose: HTTP REST endpoints that expose agent workflows and services
- Contains: 40+ Flask blueprints, each with DI initialization pattern
- Key files: `audits.py` (audit workflow), `remediation.py` (approval flow), `agents.py` (session management)
- Pattern: `init_*_bp(dependencies)` called in app.py, blueprint registers routes

**`src/services/`:**
- Purpose: Business logic, computation, analysis (non-AI)
- Contains: Score calculation, impact analysis, knowledge graph traversal, portfolio aggregation
- Key files: `readiness_service.py` (scoring), `impact_analysis_service.py` (change simulation)

**`src/db/`:**
- Purpose: SQLite persistence with versioned migrations
- Contains: Connection utilities, migration runner, 28 SQL schema files
- Key files: `connection.py` (connection pooling), `migrate.py` (application runner)

**`src/importers/`:**
- Purpose: Document ingestion pipeline (parse → PII detect → chunk → embed)
- Contains: PDF/DOCX/TXT parser, PII detector, chunker
- Key files: `document_parser.py`, `pii_detector.py`
- Pattern: Each parser returns `ParsedDocument` dataclass

**`src/i18n/`:**
- Purpose: Multi-locale UI text management
- Contains: JSON files with dot-notation keys, translation functions
- Key files: `en-US.json`, `es-PR.json`
- Usage: Template context processor injects `t()` function, Python calls `t(key, locale)`

**`templates/`:**
- Purpose: Jinja2 HTML templates with Jinja2 macros and includes
- Pattern: Base layout (`base.html`), page templates, reusable components
- Key pages: Dashboard, audit workflow, remediation workbench, site visit mode

**`static/`:**
- Purpose: Frontend CSS and vanilla JavaScript (no framework)
- Pattern: CSS files organized by component/page, JS utilities for API calls and DOM manipulation
- Dark theme: `--bg-primary: #1a1a2e`, accents by compliance status

## Key File Locations

**Entry Points:**
- `app.py`: Flask app initialization, blueprint registration, startup hooks
- `config.py`: Global configuration class with all constants
- `workspace/` (runtime): Institution data folders

**Configuration:**
- `.env`: Secrets (ANTHROPIC_API_KEY, DATABASE, PORT)
- `src/config.py`: Hardcoded config (Config class with defaults)
- `pytest.ini`: Pytest setup

**Core Logic:**
- `src/core/workspace.py`: FileSystem abstraction for institution folders
- `src/agents/base_agent.py`: Abstract base for all agents
- `src/db/migrate.py`: Schema versioning and application
- `src/services/readiness_service.py`: Readiness scoring (0-100)

**Testing:**
- `tests/` (not shown, but implied): Unit and integration tests
- `pytest.ini`: Pytest configuration

**Documentation:**
- `SPEC.md`: Full 90KB+ specification with all features
- `CLAUDE.md`: Development guidelines (this file)
- `.planning/STATE.md`: Current session state and urgent TODOs

## Naming Conventions

**Files:**
- Snake case: `document_parser.py`, `compliance_audit.py`, `readiness_service.py`
- Agents: `{name}_agent.py` (e.g., `remediation_agent.py`, `faculty_agent.py`)
- API blueprints: `{feature}.py` (e.g., `audits.py`, `packets.py`)
- Tests: `test_{module}.py` (e.g., `test_document_parser.py`)

**Directories:**
- Snake case: `importers/`, `validators/`, `generators/`, `accreditors/`
- Feature grouping: `agents/`, `api/`, `services/`, `db/`
- Asset organization: `templates/{feature}/`, `static/{css|js}/{feature}/`

**Functions & Methods:**
- Snake case: `compute_readiness()`, `save_remediation_document()`, `_slugify()`
- Public: `no_leading_underscore()`
- Private: `_leading_underscore()`
- Abstract: Prefixed in docstring: "@abstractmethod"

**Classes & Types:**
- PascalCase: `WorkspaceManager`, `ComplianceAuditAgent`, `AgentSession`
- Enums: `AgentType`, `ComplianceStatus`, `DocumentType`
- Dataclasses: `Institution`, `Program`, `Finding`, `ReadinessScore`

**Database & JSON:**
- Snake case: `institution_id`, `document_count`, `compliance_status`
- Enums as strings: `"compliant"`, `"partial"`, `"non_compliant"`
- Dates: ISO 8601 with timezone: `"2026-03-21T12:30:45.123456+00:00"`

**i18n Keys:**
- Dot notation: `nav.dashboard`, `compliance.status.compliant`, `audit.findings.critical`

## Where to Add New Code

**New Feature (e.g., "Budget Tracking"):**
- Agent: `src/agents/budget_agent.py` → register with `@register_agent(AgentType.BUDGET)`
- API: `src/api/budget.py` → blueprint with `init_budget_bp(workspace_manager)`
- Service: `src/services/budget_service.py` → scoring and aggregation
- DB: `src/db/migrations/NNNN_budget.sql` → schema for budget records
- Template: `templates/pages/budget.html` → UI
- Tests: `tests/test_budget_agent.py`, `tests/api/test_budget.py`

**New Agent Type:**
1. Add enum to `src/agents/base_agent.py` AgentType class
2. Create `src/agents/{name}_agent.py` extending BaseAgent
3. Implement: `agent_type`, `system_prompt`, `tools`, `_execute_tool()`
4. Register: Add `@register_agent(AgentType.NAME)` decorator
5. Wire: API blueprint can call `AgentRegistry.create(AgentType.NAME, session, ...)`

**New API Endpoint:**
1. Create `src/api/{feature}.py` or add to existing blueprint
2. Define DI function: `def init_{feature}_bp(dependencies): global _deps; _deps = dependencies`
3. Register blueprint in `app.py` by calling `init_{feature}_bp(...)` and `app.register_blueprint(..._bp)`
4. Use module-level globals to access dependencies

**New Service:**
1. Create `src/services/{name}_service.py`
2. Implement domain logic without AI (for AI, use agents)
3. Accept WorkspaceManager, database connection in constructor
4. Return typed dataclasses (e.g., `ReadinessScore`)
5. Called from API endpoints or agents

**New Database Table:**
1. Create `src/db/migrations/NNNN_{feature}.sql` (increment number)
2. Define schema with foreign keys to `institutions`
3. Run `flask db upgrade` to apply
4. Access via `from src.db.connection import get_conn`
5. Consider caching strategy if read-heavy

**New i18n String:**
1. Add to `src/i18n/en-US.json` with dot-notation key: `"feature.action": "Label"`
2. Add same key to `src/i18n/es-PR.json` with Spanish translation
3. Access in templates: `{{ t('feature.action') }}`
4. Access in Python: `from src.i18n import t; label = t('feature.action', locale)`

## Special Directories

**`workspace/`:**
- Purpose: Institution-specific persistent data
- Generated: Yes, created dynamically per institution
- Committed: No, git-ignored (contains user data)
- Structure: Institution folder per ID, with subfolder hierarchy
- Lifecycle: Created on first institution setup, grows with usage

**`agent_sessions/`:**
- Purpose: Full audit trail of agent execution
- Generated: Yes, one JSON per session
- Committed: No, kept locally (can be voluminous)
- Contents: All messages, tool calls, tokens, checkpoints
- Usage: Debugging, reproducibility, compliance audits

**`standards/`:**
- Purpose: Accreditor standards definitions (JSON hierarchies)
- Generated: No, hand-curated or fetched from accreditor sources
- Committed: Yes, version-controlled
- Format: JSON with standard ID, name, requirements, guidance

**`.planning/`:**
- Purpose: Project planning artifacts and codebase analysis
- Generated: Yes (by GSD mappers and planners)
- Committed: Yes (tracking project progress)
- Contents: STATE.md (current status), phase plans, codebase docs

---

*Structure analysis: 2026-03-21*
