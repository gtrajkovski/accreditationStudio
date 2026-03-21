# Coding Conventions

**Analysis Date:** 2026-03-21

## Naming Conventions

**Files:**
- Snake case: `document_parser.py`, `compliance_audit.py`, `readiness_service.py`
- Agents: `{name}_agent.py` (e.g., `remediation_agent.py`, `faculty_agent.py`)
- API blueprints: `{feature}.py` (e.g., `audits.py`, `packets.py`)
- Tests: `test_{module}.py` (e.g., `test_readiness_service.py`)

**Functions & Methods:**
- Snake case: `compute_readiness()`, `save_remediation_document()`, `_slugify()`
- Public: `no_leading_underscore()`
- Private: `_leading_underscore()`
- Tool handlers in agents: `_tool_{name}()` pattern (e.g., `_tool_validate_claim()`)

**Classes & Types:**
- PascalCase: `WorkspaceManager`, `ComplianceAuditAgent`, `AgentSession`
- Enums: `AgentType`, `ComplianceStatus`, `DocumentType`
- Dataclasses: `Institution`, `Program`, `Finding`, `ReadinessScore`
- Service classes: `{Name}Service` (e.g., `ReadinessService`, `BatchService`)

**Variables:**
- Snake case: `institution_id`, `document_count`, `compliance_status`
- Constants: `UPPERCASE_SNAKE` (e.g., `MAX_TOKENS`, `CACHE_WINDOW_MINUTES`)
- Module-level singletons: `_workspace_manager`, `_active_audits`

**Database & JSON:**
- Snake case for columns: `institution_id`, `created_at`, `compliance_status`
- Enums as strings: `"compliant"`, `"partial"`, `"non_compliant"`
- Dates: ISO 8601 with timezone: `"2026-03-21T12:30:45.123456+00:00"`

**i18n Keys:**
- Dot notation: `nav.dashboard`, `compliance.status.compliant`, `audit.findings.critical`

## Import Organization

**Standard order:**
1. Standard library imports
2. Third-party imports (Flask, Anthropic, etc.)
3. Local imports from `src/`
4. Blank line between groups

**Example from `src/services/readiness_service.py`:**
```python
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from src.db.connection import get_conn
```

**Import style:**
- Prefer explicit imports: `from src.db.connection import get_conn`
- Avoid wildcard imports: Never use `from module import *`
- Group related imports on same line when < 3 items

## Function Signatures

**Type annotations:**
- All public functions annotated with parameter and return types
- Use `Optional[T]` for nullable parameters
- Use `Dict[str, Any]` for flexible JSON-like structures
- Use `List[T]` for homogeneous collections

**Example pattern:**
```python
def compute_readiness(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    force_recompute: bool = False
) -> ReadinessScore:
    """Compute readiness score for institution.

    Args:
        institution_id: Institution to compute score for.
        accreditor_code: Accreditor standards to use.
        force_recompute: Skip cache if True.

    Returns:
        ReadinessScore with total and sub-scores.
    """
```

**Default parameters:**
- Use `None` as default for mutable types, then initialize in body
- Document defaults in docstring if not obvious

## Docstrings

**Style:** Google docstring format

**Required sections:**
- One-line summary (always)
- Extended description (if complex)
- Args: (if parameters beyond `self`)
- Returns: (if not `None`)
- Raises: (if explicitly raising exceptions)

**Example:**
```python
def validate_claim(self, claim_id: str, claim_text: str) -> EvidenceCheck:
    """Validate a single compliance claim has proper evidence.

    Checks that the claim has both a standard citation and
    document evidence reference with sufficient confidence.

    Args:
        claim_id: Unique identifier for the claim.
        claim_text: The text of the compliance claim.

    Returns:
        EvidenceCheck with validation results.

    Raises:
        ValueError: If claim_id is empty.
    """
```

## Error Handling

**Pattern:** Explicit error returns or exceptions, never silent failures

**API endpoints:**
- Return tuple of `(jsonify(data), status_code)`
- 400 for invalid input, 404 for not found, 500 for internal errors
- Include error message in JSON: `{"error": "description"}`

**Service functions:**
- Return `None` or empty result for "not found" cases
- Raise exceptions for invalid inputs or unrecoverable errors
- Log errors with context before raising

**Agent tool execution:**
- Return `{"error": "message"}` dict for tool failures
- Return `{"success": True, ...}` for successful execution
- Include diagnostic info in error responses

**Example API error handling:**
```python
@audits_bp.route('/api/institutions/<institution_id>/audits', methods=['POST'])
def start_audit(institution_id: str):
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    document_id = data.get('document_id')
    if not document_id:
        return jsonify({"error": "document_id is required"}), 400
```

## Class Structure

**Dataclasses:**
- Use `@dataclass` decorator for data containers
- Implement `to_dict()` and `from_dict()` for serialization
- Use `field(default_factory=...)` for mutable defaults

**Example:**
```python
@dataclass
class Blocker:
    """A blocking issue that reduces readiness."""
    type: str  # 'missing_doc', 'critical_finding', 'consistency', 'evidence'
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    action: str
    link: Optional[str] = None
    doc_type: Optional[str] = None
    finding_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}
```

**Agent classes:**
- Extend `BaseAgent` abstract class
- Implement required properties: `agent_type`, `system_prompt`, `tools`
- Implement `_execute_tool()` for tool dispatch
- Register with `@register_agent(AgentType.NAME)` decorator

**Blueprint modules:**
- Create blueprint at module level
- Define `init_{name}_bp(dependencies)` function for DI
- Store dependencies in module-level globals

## Code Patterns

**Dependency Injection (API blueprints):**
```python
# Module level
audits_bp = Blueprint('audits', __name__)
_workspace_manager = None

def init_audits_bp(workspace_manager):
    global _workspace_manager
    _workspace_manager = workspace_manager
    return audits_bp
```

**Optional Import (graceful degradation):**
```python
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
```

**Serialization round-trip:**
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        "id": self.id,
        "name": self.name,
        ...
    }

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "ClassName":
    # Filter unknown fields before construction
    known_fields = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return cls(**filtered)
```

**Generator-based streaming (agents):**
```python
def run_turn(self, prompt: str) -> Generator[Dict[str, Any], None, None]:
    """Execute one agent turn, yielding progress updates."""
    yield {"type": "turn_start", "prompt": prompt}
    # ... execute ...
    yield {"type": "turn_complete", "result": result}
```

## Comments

**When to comment:**
- Complex algorithms requiring explanation
- Non-obvious business logic
- Workarounds or temporary fixes (with TODO)
- Configuration constants with non-obvious values

**When NOT to comment:**
- Self-documenting code (good names explain intent)
- Obvious operations
- Redundant comments that repeat the code

**TODO format:**
```python
# TODO: Implement agent-based audit (placeholder for now)
# TODO(username): Fix race condition in concurrent audits
```

## Logging

**Pattern:**
- Use Python `logging` module
- Create module-level logger: `logger = logging.getLogger(__name__)`
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR

**What to log:**
- Agent execution start/complete
- Tool calls with inputs/outputs
- Errors with context
- Performance metrics (duration, token usage)

**Example:**
```python
import logging

logger = logging.getLogger(__name__)

def send_report_email(self, recipients, subject, body, pdf_bytes, filename):
    logger.info(f"Sending report email to {len(recipients)} recipients")
    try:
        # ... send email ...
        logger.info(f"Email sent successfully: {filename}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise
```

## Testing Conventions

See TESTING.md for detailed testing patterns.

---

*Conventions analysis: 2026-03-21*
