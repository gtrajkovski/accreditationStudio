# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**See [SPEC.md](./SPEC.md) for the complete technical specification** including detailed agent descriptions, data models, all application pages, workflow examples, and the full MVP build order.

**See [.planning/STATE.md](.planning/STATE.md)** for current session state, backlog progress, and urgent TODOs.

> **Reference Architecture:** The `_reference/` folder contains Course Builder Studio, which shares the same Flask + Jinja2 + vanilla JS + Anthropic SDK architecture. Study its patterns (especially `src/core/`, `src/generators/base_generator.py`, `src/api/`, `src/exporters/`, `src/validators/`, `app.py`, and `static/css/`) and reuse or adapt components wherever possible.

---

## Project Overview

**AccreditAI** is an AI-powered platform for managing the **entire accreditation lifecycle** of post-secondary educational institutions — from self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. It audits against the **full regulatory stack**: accreditor standards + federal regulations + state requirements + professional licensure expectations.

Standalone Flask app, single-user localhost tool (same deployment model as Course Builder Studio).

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
- **`src/agents/`** — 24-agent tiered architecture with registry pattern
- **`src/api/`** — Flask Blueprints with `init_*_bp(dependencies...)` DI pattern
- **`src/ai/`** — AIClient wrapper for Anthropic SDK
- **`src/db/`** — SQLite database with migration system (`src/db/migrations/`)
- **`src/services/`** — Business logic services (e.g., `readiness_service.py`)
- **`src/i18n/`** — Internationalization (en-US, es-PR) with JSON string files
- **`src/importers/`** — Document parsing (`document_parser.py`), PII detection (`pii_detector.py`), OCR, chunking
- **`src/search/`** — Semantic search with embeddings + ChromaDB vector store

**Entry point:** `app.py` — initializes `WorkspaceManager`, `AIClient`, `StandardsStore`; registers blueprints; injects i18n context.

**Frontend:** Jinja2 templates + vanilla JS, dark theme (#1a1a2e), theme switching.

### 24-Agent Tier Architecture

Agents are organized into tiers (defined in `src/agents/base_agent.py`):

| Tier | Purpose | Agents |
|------|---------|--------|
| 0 | Runtime & Governance | `ORCHESTRATOR`, `POLICY_SAFETY`, `EVIDENCE_GUARDIAN` |
| 1 | Intake & Retrieval | `DOCUMENT_INTAKE`, `PARSING_STRUCTURE`, `PII_REDACTION`, `RETRIEVAL_TUNING` |
| 2 | Standards & Regulatory | `STANDARDS_CURATOR`, `REGULATORY_STACK`, `STANDARDS_TRANSLATOR` |
| 3 | Compliance & Quality | `COMPLIANCE_AUDIT`, `CONSISTENCY`, `RISK_SCORER`, `GAP_FINDER` |
| 4 | Remediation & Authoring | `REMEDIATION`, `POLICY_AUTHOR`, `EXHIBIT_BUILDER`, `CHANGE_IMPACT` |
| 5 | Submission & Defense | `NARRATIVE`, `CROSSWALK`, `PACKET`, `SITE_VISIT_COACH` |
| 6 | Product Experience | `WORKFLOW_COACH`, `LOCALIZATION_QA` |

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

**Phase 1 (Foundation):** ✅ Complete

**Phase 2 (Ingestion + Standards):** ✅ Complete
- Document parser, PII detector, chunking pipeline
- Ingestion Agent with 7 tools
- Standards Library with ACCSC/SACSCOC/HLC/ABHES/COE presets
- Semantic search (embeddings + ChromaDB)
- i18n system (en-US, es-PR)
- Theme switching

**Phase 3 (Audit Engine + Readiness):** ✅ Complete
- ✅ 24-agent tiered architecture
- ✅ Agent registry with dynamic dispatch
- ✅ Evidence Guardian (Tier 0 governance)
- ✅ Readiness Score service with sub-scores
- ✅ Database migrations (20 migrations)
- ✅ Compliance Audit Agent (5-pass multi-tool audit engine)
- ✅ Audit API with SSE streaming
- ✅ Document upload and audit trigger UI
- ✅ Compliance findings display with filters

**Phase 4 (Remediation):** ✅ Complete
- ✅ Remediation Agent (7 tools, redlines, finals, truth index)
- ✅ Document Workbench UI (remediation review, diff view, approvals)
- ✅ Consistency Agent (8 policy categories, cross-doc checking)
- ✅ Checklist Auto-Fill Agent (12 tools, evidence search, validation, DOCX export)

**Phase 5 (Findings + Packets):** ✅ Complete
- ✅ Findings Agent (aggregation, prioritization, action items)
- ✅ Narrative Agent (issue responses, self-study sections)
- ✅ Packet Agent (10 tools, validation, DOCX/ZIP export)
- ✅ Submission Organizer UI (packet builder, validation, export)
- ✅ Action Plan Tracking (items, deadlines, progress)

**Phase 6 (Catalog + Exhibits + Faculty):** ✅ Complete
- ✅ Faculty Agent (8 tools: credential tracking, license verification, qualification audits)
- ✅ Catalog Agent (8 tools: section generation, audit, validation, export)
- ✅ Evidence Agent (8 tools: exhibit validation, gap analysis, index building)
- ✅ Achievement Agent (7 tools: outcome tracking, benchmark validation, trend analysis)

**Phase 7 (Visit Prep + Interview + Checklists):** ✅ Complete
- ✅ Interview Prep Agent (7 tools: 9 roles, questions, talking points, red flags)
- ✅ SER Drafting Agent (8 tools: section drafting, draft/submission modes)
- ✅ UI Redesign ("Certified Authority" - gold accent, collapsible nav, readiness ring)
- ✅ Enhanced Checklist Agent (4 new tools: document validation, page references, linked export, completion status)
- ✅ Visit readiness page with mock evaluation support
- ✅ Database migration (0015_phase7.sql)

**Post-Phase 7 Improvements:**
- ✅ Dashboard session controls (pause/resume/cancel buttons)
- ✅ PAUSED session status added to SessionStatus enum
- ✅ New API endpoints: POST `/api/agents/sessions/<id>/pause`, `/resume`
- ✅ Session cards UI with real-time status updates

**Phase 8 (Post-Visit + Ongoing):** ✅ Complete
- ✅ Team Report Response Agent (8 tools: report parsing, finding categorization, response drafting, evidence gathering, action plan creation, validation, packet export)
- ✅ Database migration (0016_team_reports.sql)
- ✅ Team Reports API blueprint with CRUD, AI parsing, response drafting
- ✅ Team Reports UI page (upload, parse, view findings, draft responses)
- ✅ Compliance Calendar Agent (8 tools: events, deadlines, timeline generation, reminders, action plan sync, export)
- ✅ Compliance Calendar API blueprint with CRUD, stats, reminders
- ✅ Compliance Calendar UI page (events, reminders, timeline generator)
- ✅ Document Review Agent (8 tools: scheduling, pending reviews, completion, cycles, reports, bulk schedule, history, priorities)
- ✅ Document Reviews API blueprint with CRUD, stats, bulk operations
- ✅ Document Reviews UI page (pending, overdue, scheduling, completion)

**Post-MVP: Impact Analysis** ✅ Complete
- ✅ Impact Analysis Service (fact scanning, change simulation, auto-remediation)
- ✅ Impact Analysis API blueprint (8 endpoints: facts, references, simulations, graph)
- ✅ Impact Analysis UI page (fact explorer, D3.js graph, simulation modal)
- ✅ Database migrations (0017_impact_analysis.sql, 0018_knowledge_graph.sql)

**Post-MVP: Knowledge Graph** ✅ Complete
- ✅ Knowledge Graph Service (entity extraction, relationship inference, graph traversal, impact analysis)
- ✅ Knowledge Graph Agent (8 tools: build_graph, add_entity, add_relationship, query_graph, get_neighbors, find_path, analyze_impact, export_graph)
- ✅ Knowledge Graph API blueprint (8 endpoints: graph data, entities, neighbors, paths, impact, export)
- ✅ Knowledge Graph UI page (entity explorer, D3.js force-directed graph, entity details, path finder)
- ✅ Database migration (0019_knowledge_graph_entities.sql)

**Post-MVP: Timeline Planner** ✅ Complete
- ✅ Timeline Planner API (15+ endpoints: phases, milestones, templates, Gantt data)
- ✅ Timeline Planner UI page (D3.js Gantt chart, 4 templates, drag-and-drop)
- ✅ Database migration (0020_timeline_planner.sql)

**Post-MVP: Site Visit Mode** ✅ Complete
- ✅ Site Visit Service (unified search across 6 data sources)
- ✅ Site Visit API (6 endpoints: search, fact lookup, history, saved searches)
- ✅ Site Visit UI (overlay with F2 shortcut, filter tabs, citations)
- ✅ Database migration (0021_site_visit.sql with FTS5 indexes)

**Post-MVP: Evidence Coverage Map** ✅ Complete
- ✅ Coverage Map Service (standards hierarchy, coverage metrics, gaps detection)
- ✅ Coverage Map API (4 endpoints: tree, summary, evidence, gaps)
- ✅ Coverage Map UI (D3.js treemap, drill-down, color-coded coverage)

**Post-MVP: Accreditation Simulation** ✅ Complete
- ✅ Simulation Service (mock audit orchestration, pass/fail prediction, risk assessment)
- ✅ Simulation API (8 endpoints: runs, findings, risk, comparisons, SSE streaming)
- ✅ Simulation UI (Quick Scan/Deep Audit modes, pass/fail badge, trend charts)
- ✅ Database migration (0022_simulation.sql)

**Post-MVP: Multi-Institution Mode** ✅ Complete
- ✅ Portfolio Service (CRUD, aggregate readiness, comparison data)
- ✅ Portfolio API (13 endpoints: portfolios, membership, readiness, comparison, bulk ops)
- ✅ Portfolio UI (list with readiness rings, dashboard with metrics, Chart.js radar comparison)
- ✅ Institution Quick-Switcher (sidebar dropdown, Ctrl+K shortcut, recent tracking)
- ✅ Database migration (0023_portfolios.sql)

**Post-MVP: Evidence Highlighting** ✅ Complete
- ✅ Evidence Highlighting Service (document text, evidence aggregation, fuzzy matching)
- ✅ Evidence Highlighting API (4 endpoints: text, evidence, standards, position)
- ✅ Document Viewer UI (page navigation, inline highlights, standards sidebar)
- ✅ Database migration (0024_evidence_highlighting.sql)

**Post-MVP: Compliance Heatmap** ✅ Complete
- ✅ Compliance Heatmap Service (document × standard matrix aggregation)
- ✅ Compliance Heatmap API (3 endpoints: matrix, cell details, document summary)
- ✅ Compliance Heatmap UI (CSS Grid matrix, sticky headers, filters, detail panel)

**Registered Blueprints** (33 total):
`chat_bp`, `agents_bp`, `institutions_bp`, `standards_bp`, `settings_bp`, `readiness_bp`, `work_queue_bp`, `autopilot_bp`, `audits_bp`, `remediation_bp`, `checklists_bp`, `packets_bp`, `action_plans_bp`, `faculty_bp`, `catalog_bp`, `exhibits_bp`, `achievements_bp`, `interview_prep_bp`, `ser_bp`, `team_reports_bp`, `compliance_calendar_bp`, `document_reviews_bp`, `documents_bp`, `impact_analysis_bp`, `knowledge_graph_bp`, `timeline_planner_bp`, `site_visit_bp`, `coverage_map_bp`, `simulation_bp`, `portfolios_bp`, `evidence_highlighting_bp`, `compliance_heatmap_bp`
