# CLAUDE_CODE_REMAINING.md — AccreditAI Remaining Work

**Generated:** 2026-03-27 (Updated)
**Scope:** Remaining implementation after v1.7 completion

> **This file is a Claude Code execution prompt.** Feed it to Claude Code along with the codebase. It contains every remaining task, organized for sequential execution.

---

## Current State Summary

**Completed Milestones:**
- v1.0 MVP (Phases 1-8) ✅
- v1.1 Post-MVP Enhancements (Phases 9-11) ✅
- v1.2 Productivity & Polish (Phases 12-14) ✅
- v1.3 AI & Reporting (Phases 15-16) ✅
- v1.4 Enterprise & Polish (Phases 17-19) ✅
- v1.5 Operational Intelligence (Phases 20-24) ✅
- v1.6 Context-Sensitive Search (Phases 25-27) ✅
- v1.7 Performance & Efficiency (Phases 28-30) ✅

**What's Left:**
- **Tech Debt** (4 tasks) — foundational cleanup
- **Phase 9 Advanced** (6 tasks) — advertising scanner, cross-program matrix, standards importer, state modules
- **v1.8+ Future** — multi-tenancy, PostgreSQL, CI pipeline, offline mode

---

## Project Context

**AccreditAI** is an AI-powered accreditation management platform for post-secondary institutions. Standalone Flask app, single-user localhost tool.

**Current state:** 30 phases complete. 35+ registered blueprints, 24-agent tiered architecture, SQLite with 32+ migrations, ChromaDB for semantic search.

---

## Architecture & Patterns (Reference)

### Directory Structure
```
src/
├── core/           # Domain models, workspace, standards, task queue
├── agents/         # 30+ agents, base_agent.py, registry.py
├── api/            # 35+ Flask blueprints with init_*_bp() DI pattern
├── ai/             # AIClient wrapper for Anthropic SDK
├── db/             # SQLite + migrations/ (32+ SQL files)
├── services/       # Business logic (non-AI)
├── importers/      # Document parsing, PII detection, chunking
├── exporters/      # DOCX/ZIP generation
├── search/         # ChromaDB vector store, embeddings
├── i18n/           # en-US.json, es-PR.json
├── accreditors/    # ACCSC, COE parsers
├── regulatory/     # Federal/state regs (stubbed)
├── validators/     # Input validation
├── generators/     # Code/schema generation
└── config.py       # Config class
```

### Key Patterns to Follow

**New Agent:**
```python
# src/agents/{name}_agent.py
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

**New Blueprint:**
```python
# src/api/{feature}.py
from flask import Blueprint, jsonify, request

{feature}_bp = Blueprint('{feature}', __name__)
_workspace_manager = None

def init_{feature}_bp(workspace_manager):
    global _workspace_manager
    _workspace_manager = workspace_manager
    return {feature}_bp

@{feature}_bp.route('/api/{feature}', methods=['GET'])
def list_{feature}():
    return jsonify({"data": []}), 200
```

**New Migration:**
```sql
-- src/db/migrations/NNNN_{feature}.sql
-- Migration: {feature}
-- Date: 2026-03-27

CREATE TABLE IF NOT EXISTS {table_name} (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);
```

### Naming Conventions
- Files: `snake_case.py`, agents: `{name}_agent.py`, tests: `test_{module}.py`
- Functions: `snake_case()`, private: `_leading_underscore()`
- Classes: `PascalCase`, enums: `AgentType`, dataclasses: `Institution`
- DB columns: `snake_case`, dates: ISO 8601 UTC
- i18n keys: `dot.notation` (add to both `en-US.json` and `es-PR.json`)

### Frontend Style
```css
--bg-primary: #1a1a2e;    --bg-secondary: #16213e;    --bg-card: #0f3460;
--accent: #c9a84c;        /* gold (post Phase 7 redesign) */
--success: #4ade80;       --warning: #fbbf24;          --danger: #ef4444;
--accreditor: #a78bfa;    --federal: #f472b6;
--state: #fb923c;         --professional: #34d399;
```

### AI Safety Guardrails
1. NEVER fabricate evidence, policy text, or compliance claims
2. ALWAYS cite sources for every claim
3. ALWAYS label uncertainty (confidence < 0.7 → requires human review)
4. REQUIRE human confirmation for compliance determinations
5. NEVER store student PII in embeddings or AI context
6. ALWAYS preserve original documents (originals/ folder is read-only)

---

## TECH DEBT (4 Tasks) — Do First

### TD-1: Split models.py into Domain Modules

**Problem:** `src/core/models.py` is 2,500+ lines with 40+ dataclasses.

**Action:**
1. Create `src/core/models/` package directory
2. Create domain-specific files:
   - `src/core/models/__init__.py` — re-exports everything
   - `src/core/models/institution.py` — Institution, Program, Campus
   - `src/core/models/document.py` — Document, DocumentChunk, ParsedDocument
   - `src/core/models/audit.py` — Audit, AuditFinding, ComplianceStatus
   - `src/core/models/agent.py` — AgentSession, AgentTask, HumanCheckpoint
   - `src/core/models/compliance.py` — ReadinessScore, Blocker, NextAction
   - `src/core/models/enums.py` — All shared enums
   - `src/core/models/helpers.py` — generate_id(), now_iso()
3. Update `__init__.py` to re-export all classes
4. Run `pytest` — all tests must pass with zero import changes

**Acceptance:** `from src.core.models import Institution` still works.

### TD-2: Silent Exception Handler Sweep

**Problem:** Bare `except: pass` handlers swallow errors silently.

**Action:**
1. Search: `grep -rn "except.*:$\|except.*pass" src/`
2. For each handler:
   - **Graceful degradation** → add `logger.debug()`
   - **Bug-hiding** → add `logger.error()` and re-raise if appropriate
   - **Missing error response** → return proper error JSON
3. Priority files:
   - `src/services/autopilot_service.py`
   - `src/services/audit_reproducibility_service.py`
   - `src/api/audits.py`

**Acceptance:** Zero bare `pass` in exception handlers. All exceptions logged.

### TD-3: AgentType Enum Cleanup

**Problem:** AgentType has 30+ entries with legacy aliases.

**Action:**
1. Review all AgentType entries in `src/agents/base_agent.py`
2. Keep ONE canonical name per agent, remove aliases
3. Update all `@register_agent()` decorators
4. Update all `AgentRegistry.create()` calls

**Acceptance:** Each agent has exactly one AgentType entry.

### TD-4: Workspace File I/O Caching

**Problem:** No caching — every load is a full disk read.

**Action:**
1. Add `functools.lru_cache` to `load_institution()` and `load_truth_index()`
2. Add cache invalidation on write operations
3. Add `CACHE_TTL_SECONDS` config (default: 30)

**Acceptance:** Repeated reads within TTL don't hit disk.

---

## PHASE 9: Advanced Features (6 Tasks)

### 9-01: Advertising/Marketing Compliance Scanner

**Context:** Review website/brochures against accreditor + FTC + state advertising requirements.

**Action:**
1. Create `src/agents/advertising_agent.py`:
   - AgentType: `ADVERTISING_SCANNER`
   - Tools: `scan_url`, `scan_document`, `check_claims`, `generate_report`
2. Create `src/api/advertising.py` blueprint
3. Create `templates/pages/advertising.html`
4. Key rules: FTC Act §5, accreditor-specific, state regulations, claims vs. achievement data

**Tests:** Test claim verification against mock achievement data.

### 9-02: Cross-Program Comparison Matrix

**Action:**
1. Create `src/services/program_comparison_service.py`:
   - `build_comparison_matrix(institution_id)` → programs × metrics
   - Metrics: readiness score, finding count, evidence coverage, faculty compliance
2. Add API endpoint: `GET /api/institutions/<id>/programs/comparison`
3. Add UI: table/heatmap + Chart.js radar chart

### 9-03: Universal Standards Importer

**Context:** Currently only ACCSC and COE have parsers. Need generic importer.

**Action:**
1. Enhance `src/accreditors/registry.py` with generic parser
2. Create `src/agents/standards_importer_agent.py`:
   - Tool: `parse_standards_document` → AI-powered parsing
   - Tool: `validate_parsed_standards`
   - Tool: `map_to_existing`
3. Add UI to Standards Library page

### 9-04: State Regulatory Modules

**Action:**
1. Create modules in `src/regulatory/states/`:
   - `puerto_rico.py` — CEPR (Ley 212-2018)
   - `florida.py` — CIE (Florida Statutes §1005)
   - `california.py` — BPPE (Ed. Code §94800-94950)
   - `new_york.py` — BPSS
   - `texas.py` — TWC
2. Each exports: `get_requirements()`, `get_document_requirements()`, `get_disclosure_requirements()`
3. Create `src/regulatory/federal.py` with Title IV, FERPA, Title IX, Clery, ADA, etc.

### 9-05: Enhanced Batch Processing

**Action:**
1. Enhance `src/core/task_queue.py`:
   - Priority levels (critical, normal, background)
   - Task dependencies
   - Rate limiting, retry with backoff
2. Add batch operations: consistency check, checklist generation, evidence validation
3. Add progress tracking: `GET /api/work-queue/progress` + SSE

### 9-06: Full Observability Dashboard

**Action:**
1. Implement append-only audit log: `workspace/{institution_id}/audit_log.jsonl`
2. Create `/admin/audit-log` page with search, filters, CSV export
3. Add token cost tracking with budget alerts

---

## FUTURE MILESTONES (v1.8+)

### Multi-Tenancy & Authentication
- Flask-Login integration
- User model with roles (admin, compliance_officer, reviewer, viewer)
- Data isolation via institution_id filters
- Role-based access control

### PostgreSQL + pgvector Migration
- `src/db/postgres_connection.py` with connection pooling
- Dialect-aware SQL (SQLite vs. PostgreSQL)
- pgvector for embeddings instead of ChromaDB
- `DATABASE_URL` env var support

### CI Pipeline
- `.github/workflows/ci.yml` with pytest + ruff
- Pre-commit hooks
- Coverage reporting

### Offline Mode / Local LLM Fallback
- `src/ai/fallback_client.py` with same interface
- Graceful degradation when API unavailable
- Optional ollama integration

---

## EXECUTION ORDER

```
1. TD-1: Split models.py          ← foundational
2. TD-2: Exception handler sweep  ← safety
3. TD-3: AgentType cleanup        ← clarity
4. TD-4: Workspace caching        ← performance

5. Phase 9-01: Advertising scanner
6. Phase 9-02: Cross-program matrix
7. Phase 9-03: Standards importer
8. Phase 9-04: State regulatory modules
9. Phase 9-05: Enhanced batch processing
10. Phase 9-06: Full observability dashboard

[Future milestones as needed]
```

---

## QUICK REFERENCE

### Registered Blueprints (35+)
```
chat_bp, agents_bp, institutions_bp, standards_bp, settings_bp,
readiness_bp, work_queue_bp, autopilot_bp, audits_bp, remediation_bp,
checklists_bp, packets_bp, action_plans_bp, faculty_bp, catalog_bp,
exhibits_bp, achievements_bp, interview_prep_bp, ser_bp, team_reports_bp,
compliance_calendar_bp, document_reviews_bp, documents_bp,
impact_analysis_bp, knowledge_graph_bp, timeline_planner_bp,
site_visit_bp, coverage_map_bp, simulation_bp, portfolios_bp,
evidence_highlighting_bp, compliance_heatmap_bp, contextual_search_bp,
cost_tracking_bp, batch_api_bp
```

### Agent Tiers (24 agents)
```
Tier 0: ORCHESTRATOR, POLICY_SAFETY, EVIDENCE_GUARDIAN
Tier 1: DOCUMENT_INTAKE, PARSING_STRUCTURE, PII_REDACTION, RETRIEVAL_TUNING
Tier 2: STANDARDS_CURATOR, REGULATORY_STACK, STANDARDS_TRANSLATOR
Tier 3: COMPLIANCE_AUDIT, CONSISTENCY, RISK_SCORER, GAP_FINDER
Tier 4: REMEDIATION, POLICY_AUTHOR, EXHIBIT_BUILDER, CHANGE_IMPACT
Tier 5: NARRATIVE, CROSSWALK, PACKET, SITE_VISIT_COACH
Tier 6: WORKFLOW_COACH, LOCALIZATION_QA
```

### Database Migrations
Use sequential numbering starting from the next available number after existing migrations.

---

*Updated 2026-03-27 after v1.7 milestone completion*
