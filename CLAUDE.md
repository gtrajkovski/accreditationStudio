# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**See [SPEC.md](./SPEC.md) for the complete technical specification** including detailed agent descriptions, data models, all application pages, workflow examples, and the full MVP build order.

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
```

---

## Architecture

### Directory Structure

- **`src/core/`** — Domain layer: models, workspace manager, task queue
- **`src/agents/`** — Agent implementations (`BaseAgent`, `OrchestratorAgent`) + session management
- **`src/api/`** — Flask Blueprints with `init_*_bp(dependencies...)` DI pattern
- **`src/ai/`** — AIClient wrapper for Anthropic SDK
- **`src/generators/`** — Document generation (planned: `BaseGenerator[T]` pattern from reference)
- **`src/validators/`** — Validation logic
- **`src/regulatory/`** — Federal/state/professional regulation definitions
- **`src/exporters/`** — .docx/.pdf generation, submission packaging
- **`src/importers/`** — Document parsing (`document_parser.py`), PII detection (`pii_detector.py`), OCR, chunking
- **`src/tasks/`** — Background task queue (SQLite-backed)

**Entry point:** `app.py` — initializes `WorkspaceManager`, `AIClient`, task queue; registers blueprints; serves templates.

**Frontend:** Jinja2 templates + vanilla JS, dark theme (#1a1a2e).

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

Current blueprints: `chat_bp`, `agents_bp`, `institutions_bp`, `documents_bp`

### Document Import Pipeline

Documents flow through: **upload → parse → PII detect → store**

```python
from src.importers import parse_document, detect_pii, redact_pii

# Parse extracts text from PDF/DOCX/text/images
parsed = parse_document(file_path)  # Returns ParsedDocument

# Detect PII returns list of PIIMatch objects
matches = detect_pii(parsed.text)

# Redact replaces PII with [REDACTED:type] markers
safe_text = redact_pii(parsed.text)
```

`ParsedDocument` contains: `text`, `page_count`, `word_count`, `sections`, `metadata`, `parse_errors`

### Model Serialization

All dataclasses in `src/core/models.py` implement `to_dict()` and `from_dict()` with unknown field filtering for schema evolution:

```python
@dataclass
class Institution:
    id: str = field(default_factory=lambda: generate_id("inst"))
    name: str = ""
    # ...

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, ...}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Institution":
        return cls(
            id=data.get("id", generate_id("inst")),
            name=data.get("name", ""),
            # ...
        )
```

Use `generate_id(prefix)` for IDs and `now_iso()` for timestamps.

### Agent Implementation

Extend `BaseAgent` in `src/agents/base_agent.py`:

```python
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

Key session management: `AgentSession` tracks tasks, checkpoints, tool calls, token usage, and messages. Agents yield progress updates via generators (`run_turn()`, `run_task()`, `run_all_tasks()`).

### Confidence Threshold

Agents check confidence against `Config.AGENT_CONFIDENCE_THRESHOLD` (default 0.7). Below threshold → flagged for human review via `HumanCheckpoint`.

---

## Core Models

**`src/core/models.py`** defines:

- **Enums:** `AccreditingBody`, `DocumentType`, `ComplianceStatus`, `FindingSeverity`, `RegulatorySource`, `AuditStatus`, `ExhibitStatus`, `SessionStatus`, `TaskPriority`, etc.
- **Domain Models:** `Institution`, `Program`, `Document`, `Audit`, `AuditFinding`
- **Importer Models:** `ParsedDocument` (in `document_parser.py`), `PIIMatch` (in `pii_detector.py`)
- **Agent Models:** `AgentSession`, `AgentTask`, `ToolCall`, `HumanCheckpoint`, `ChatMessage`

---

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-20250514
PORT=5003
WORKSPACE_DIR=./workspace
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

**Phase 1 (Foundation):** Complete
- ✅ Project scaffolding
- ✅ WorkspaceManager with file locking and version tracking
- ✅ Core models (Institution, Program, Document, Audit, Agent models)
- ✅ BaseAgent framework with tool execution and session management
- ✅ OrchestratorAgent shell
- ✅ Task queue infrastructure
- ✅ Chat API blueprint
- ✅ Institution CRUD API
- ✅ Basic dashboard and institution pages

**Phase 2 (Document Ingestion):** Complete
- ✅ Document upload API with file type validation
- ✅ Document parser (`src/importers/document_parser.py`) — PDF, DOCX, text, images (OCR)
- ✅ PII detection (`src/importers/pii_detector.py`) with redaction
- ✅ Chunking pipeline (`src/importers/document_chunker.py`) — section-aware, PII handling, overlap
- ✅ Ingestion Agent (`src/agents/ingestion_agent.py`) — orchestrates full pipeline

Next: Phase 3 — Compliance Audit Engine (Standards Agent, audit workflow).
