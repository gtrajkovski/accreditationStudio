# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**See [SPEC.md](./SPEC.md) for the complete technical specification** including detailed agent descriptions, data models, all application pages, workflow examples, and the full MVP build order.

**See [.planning/STATE.md](.planning/STATE.md)** for current session state, backlog progress, and urgent TODOs.

> **Reference Architecture:** The `_reference/` folder contains Course Builder Studio, which shares the same Flask + Jinja2 + vanilla JS + Anthropic SDK architecture. Study its patterns (especially `src/core/`, `src/generators/base_generator.py`, `src/api/`, `src/exporters/`, `src/validators/`, `app.py`, and `static/css/`) and reuse or adapt components wherever possible.

---

## Project Overview

**AccreditAI** is an AI-powered platform for managing the **entire accreditation lifecycle** of post-secondary educational institutions — from self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. It audits against the **full regulatory stack**: accreditor standards + federal regulations + state requirements + professional licensure expectations.

Standalone Flask app with optional multi-user support (AUTH_ENABLED flag). Default deployment is single-user localhost tool.

**The application is agentic to the highest degree possible.** Autonomous AI agents chain tasks, invoke each other, and complete multi-step workflows with minimal human intervention.

---

## Commands

```bash
python app.py                      # Flask dev server on port 5003
pytest                             # Run all tests
pytest tests/test_file.py          # Run single test file
pytest tests/test_file.py::test_fn # Run single test function
pytest -x                          # Stop on first failure
pip install -r requirements.txt    # Install dependencies

# Database migrations
flask db status                    # Show migration status
flask db upgrade                   # Apply pending migrations
flask init-db                      # Initialize fresh database
```

---

## Architecture

### Directory Structure

- **`src/core/`** — Domain layer: models, workspace manager, task queue, standards store
- **`src/agents/`** — 34-agent tiered architecture with registry pattern
- **`src/api/`** — Flask Blueprints (61+) with `init_*_bp(dependencies...)` DI pattern
- **`src/ai/`** — AIClient wrapper for Anthropic SDK
- **`src/db/`** — SQLite database with migration system (`src/db/migrations/`, 51 migrations)
- **`src/services/`** — Business logic services (43 services)
- **`src/i18n/`** — Internationalization (en-US, es-PR) with JSON string files
- **`src/importers/`** — Document parsing (`document_parser.py`), PII detection (`pii_detector.py`), OCR, chunking
- **`src/search/`** — Semantic search with embeddings + ChromaDB vector store

**Entry point:** `app.py` — initializes `WorkspaceManager`, `AIClient`, `StandardsStore`; registers blueprints; injects i18n context; handles auth middleware.

**Frontend:** Jinja2 templates + vanilla JS, dark theme (#1a1a2e), theme switching.

### Agent Tier Architecture

Agents are organized into tiers (defined in `src/agents/base_agent.py`). Currently 34 agents across 7 tiers:

| Tier | Purpose | Example Agents |
|------|---------|----------------|
| 0 | Runtime & Governance | `ORCHESTRATOR`, `EVIDENCE_GUARDIAN` |
| 1 | Intake & Retrieval | `INGESTION`, `PII_REDACTION` |
| 2 | Standards & Regulatory | `STANDARDS_LIBRARIAN`, `STANDARDS_IMPORTER` |
| 3 | Compliance & Quality | `COMPLIANCE_AUDIT`, `CONSISTENCY`, `RISK_SCORER` |
| 4 | Remediation & Authoring | `REMEDIATION`, `CATALOG`, `EXHIBIT_BUILDER` |
| 5 | Submission & Defense | `NARRATIVE`, `PACKET`, `SITE_VISIT_PREP`, `TEAM_REPORT` |
| 6 | Product Experience | `KNOWLEDGE_GRAPH`, `INTERVIEW_PREP` |

Register agents with the decorator: `@register_agent(AgentType.MY_AGENT)`. The registry enables dynamic dispatch via `AgentRegistry.create(agent_type, session, ...)`.

### Local Workspace Structure

Each institution gets a persistent folder:

```
workspace/{institution_id}/
├── institution.json
├── truth_index.json              # Single Source of Truth
├── programs/{program_id}/
│   ├── originals/                # Never modified
│   ├── audits/
│   ├── redlines/
│   ├── finals/                   # The working truth
│   ├── crossrefs/
│   └── checklists/
├── catalog/
├── policies/
├── exhibits/
├── faculty/
├── achievements/
├── visit_prep/
├── responses/
├── submissions/
└── agent_sessions/               # Full audit trail
```

---

## Key Patterns

### Blueprint Dependency Injection

Each API blueprint uses `init_*_bp(dependencies...)` to inject dependencies. Blueprints are registered in `app.py`:

```python
# src/api/institutions.py
institutions_bp = Blueprint("institutions", __name__, url_prefix="/api/institutions")
_workspace_manager = None

def init_institutions_bp(workspace_manager):
    global _workspace_manager
    _workspace_manager = workspace_manager
```

### Database & Migrations

SQLite database with versioned migrations in `src/db/migrations/`. Migrations are numbered sequentially (`0001_core.sql`, `0002_docs.sql`, etc.).

```python
from src.db.connection import get_conn
from src.db.migrate import apply_migrations

# Get database connection (row_factory = sqlite3.Row)
conn = get_conn()

# Apply migrations programmatically
applied = apply_migrations()
```

### i18n System

Translation files in `src/i18n/{locale}.json`. Access via template helper `t()` or Python:

```python
from src.i18n import t, get_all_strings

# Python
label = t("nav.dashboard", "es-PR")

# Jinja2 (injected via context processor)
{{ t('nav.dashboard') }}
```

Add new strings to both `en-US.json` and `es-PR.json`. Keys use dot notation (e.g., `nav.dashboard`, `compliance.status.compliant`).

### Document Import Pipeline

Documents flow through: **upload → parse → PII detect → store**

```python
from src.importers import parse_document, detect_pii, redact_pii

parsed = parse_document(file_path)  # Returns ParsedDocument
matches = detect_pii(parsed.text)   # Returns list of PIIMatch
safe_text = redact_pii(parsed.text) # Replaces with [REDACTED:type]
```

### Model Serialization

All dataclasses implement `to_dict()` and `from_dict()` with unknown field filtering:

```python
@dataclass
class Institution:
    id: str = field(default_factory=lambda: generate_id("inst"))
    name: str = ""

    def to_dict(self) -> Dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Institution": ...
```

Use `generate_id(prefix)` for IDs and `now_iso()` for timestamps.

### Agent Implementation

Extend `BaseAgent` and register with decorator:

```python
from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent

@register_agent(AgentType.MY_AGENT)
class MyAgent(BaseAgent):
    @property
    def agent_type(self) -> AgentType:
        return AgentType.MY_AGENT

    @property
    def system_prompt(self) -> str:
        return "You are a specialized agent for..."

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [{"name": "my_tool", "description": "...", "input_schema": {...}}]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "my_tool":
            return self._do_my_tool(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}
```

Session management: `AgentSession` tracks tasks, checkpoints, tool calls, token usage. Agents yield progress via generators (`run_turn()`, `run_task()`, `run_all_tasks()`).

### Readiness Score Service

`src/services/readiness_service.py` computes institution readiness (0-100) with weighted sub-scores:

```python
from src.services.readiness_service import compute_readiness, get_next_actions

readiness = compute_readiness(institution_id, accreditor_code="ACCSC")
# Returns: total, documents, compliance, evidence, consistency scores + blockers

actions = get_next_actions(institution_id, readiness)
# Returns prioritized list of NextAction objects
```

### Confidence Threshold

Agents check confidence against `Config.AGENT_CONFIDENCE_THRESHOLD` (default 0.7). Below threshold → flagged for human review via `HumanCheckpoint`.

### Authentication & RBAC (v2.1+)

When `AUTH_ENABLED=true`, the app requires login. Role hierarchy (lowest to highest):

```python
ROLE_HIERARCHY = ['viewer', 'department_head', 'compliance_officer', 'admin', 'owner']
```

Decorators in `app.py`:
- `@login_required` — requires any authenticated user
- `@require_role('admin', 'owner')` — requires specific role(s)
- `@require_minimum_role('compliance_officer')` — requires role level or higher

Services: `auth_service.py` (JWT, sessions), `rbac_service.py` (permissions), `activity_service.py` (audit log)

---

## Planning Directory

The `.planning/` directory contains project planning artifacts:

| File | Purpose |
|------|---------|
| `STATE.md` | **Current session state** - urgent TODOs, backlog progress, what's complete |
| `IMPLEMENTATION_PROMPTS.md` | Sequenced prompts for weekly feature shipping |
| `FEATURE_PRIORITIES.md` | Post-MVP backlog items ranked by value |
| `ROADMAP.md` | High-level milestone timeline |
| `ARCHITECTURE.md` | System architecture decisions |
| `DATABASE_SCHEMA.md` | Database table documentation |

**Always check `.planning/STATE.md`** at session start for urgent TODOs and current context.

---

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-20250514
PORT=5003
WORKSPACE_DIR=./workspace
DATABASE=./accreditai.db
AGENT_CONFIDENCE_THRESHOLD=0.7
VECTOR_STORE=sqlite-vss
CHUNK_SIZE=500
CHUNK_OVERLAP=50
AUTH_ENABLED=false              # Set true to require login (v2.1+)
SECRET_KEY=your-secret-key      # Required when AUTH_ENABLED=true
```

---

## Testing

Mock `src.agents.base_agent.Anthropic` for agent tests:

```python
from unittest.mock import patch, MagicMock

@patch("src.agents.base_agent.Anthropic")
def test_agent_executes_task(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="Result")],
        usage=MagicMock(input_tokens=10, output_tokens=20),
        stop_reason="end_turn"
    )
    # ... test agent behavior
```

---

## AI Safety Guardrails

1. NEVER fabricate evidence, policy text, or compliance claims
2. ALWAYS cite sources for every claim
3. ALWAYS label uncertainty (confidence < 0.7 → requires human review)
4. REQUIRE human confirmation for compliance determinations
5. NEVER store student PII in embeddings or AI context
6. ALWAYS preserve original documents (originals/ folder is read-only)

---

## Frontend Style

```css
--bg-primary: #1a1a2e;
--bg-secondary: #16213e;
--bg-card: #0f3460;
--accent: #e94560;
--success: #4ade80;        /* compliant */
--warning: #fbbf24;        /* partial */
--danger: #ef4444;         /* non-compliant */
--accreditor: #a78bfa;     /* purple */
--federal: #f472b6;        /* pink */
--state: #fb923c;          /* orange */
--professional: #34d399;   /* teal */
```

---

## Current Status

See [.planning/STATE.md](.planning/STATE.md) for detailed milestone progress.

**Milestone History:**
| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v1.0-v1.7 | Core through Performance | 1-35 | ✅ Complete |
| v1.8 | Operational Intelligence | (retroactive) | ✅ Complete |
| v1.9 | Regulatory Intelligence | 36-37 | ✅ Complete |
| v2.0 | Productivity Tools | 38-40 | ✅ Complete |
| v2.1 | Commercial Readiness | 41-47 | 🔄 In Progress (91%) |

**v2.1 Phases (Commercial Readiness):**
- ✅ Phase 41: Authentication System (JWT, sessions, password reset)
- ✅ Phase 42: Role-Based Access Control (5-role hierarchy, decorators)
- ✅ Phase 43: Activity Audit Trail (logging, filtering, export)
- ✅ Phase 44: Task Management (assignments, status tracking)
- ✅ Phase 45: Executive Dashboard (AI insights, summaries)
- ✅ Phase 46: Onboarding Wizard (guided setup)
- ✅ Phase 47: Consulting Mode (multi-institution templates)

---

## Codebase Metrics

| Metric | Count |
|--------|-------|
| Lines of Code | ~145,000 |
| Database Migrations | 51 |
| Agents | 34 |
| Services | 43 |
| API Blueprints | 61 |
| i18n Locales | 2 (en-US, es-PR) |
