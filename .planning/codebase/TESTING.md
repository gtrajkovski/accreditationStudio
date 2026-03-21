# Testing Patterns

**Analysis Date:** 2026-03-21

## Framework

**Test runner:** pytest 7.4.0+
**Coverage:** pytest-cov 4.1.0+
**Location:** `tests/` directory
**Config file:** `pytest.ini`

## Configuration

**pytest.ini:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
addopts = --ignore=_reference -v
```

**Key settings:**
- Test discovery in `tests/` directory
- Files matching `test_*.py` pattern
- Ignores `_reference/` (Course Builder Studio reference implementation)
- Verbose output by default

## Test File Structure

**Naming:**
- Test files: `test_{module}.py`
- Test functions: `test_{behavior}_when_{condition}()` or `test_{function_name}()`

**Current test files:**
```
tests/
├── conftest.py                    # Shared fixtures
├── test_batch_service.py          # BatchService tests
├── test_chat_context_service.py   # ChatContextService tests
├── test_checklist_agent.py        # Checklist agent tests
├── test_consistency_agent.py      # Consistency agent tests
├── test_db_migrations.py          # Database migration tests
├── test_document_chunker.py       # Document chunker tests
├── test_evidence_assistant_service.py  # Evidence assistant tests
├── test_evidence_mapper.py        # Evidence mapper tests
├── test_findings_agent.py         # Findings agent tests
├── test_narrative_agent.py        # Narrative agent tests
├── test_packet_agent.py           # Packet agent tests
├── test_readiness_service.py      # Readiness scoring tests
├── test_remediation_agent.py      # Remediation agent tests
├── test_standards_store.py        # Standards store tests
├── test_standard_explainer_service.py  # Standard explainer tests
└── test_work_queue_service.py     # Work queue tests
```

## Fixtures

**Location:** `tests/conftest.py`

**Common fixtures:**

**`temp_db`** - Temporary SQLite database:
```python
@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
    Path(db_path).unlink(missing_ok=True)
```

**`temp_workspace`** - Temporary workspace directory:
```python
@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace
```

**`mock_anthropic`** - Mock Anthropic client for agent tests:
```python
@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client for agent tests."""
    with patch("src.agents.base_agent.Anthropic") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(type="text", text="Test response")],
            usage=MagicMock(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )
        yield mock_client
```

**`sample_institution`** - Test institution data:
```python
@pytest.fixture
def sample_institution():
    """Return a sample institution dict for testing."""
    return {
        "id": "inst_test123",
        "name": "Test University",
        "accreditor_code": "ACCSC",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
```

**`sample_document`** - Test document data:
```python
@pytest.fixture
def sample_document():
    """Return a sample document dict for testing."""
    return {
        "id": "doc_test123",
        "institution_id": "inst_test123",
        "filename": "test_policy.pdf",
        "doc_type": "policy",
        "status": "indexed",
        "created_at": "2024-01-01T00:00:00Z"
    }
```

## Mocking Patterns

**Anthropic API mocking:**
```python
from unittest.mock import patch, MagicMock

@patch("src.agents.base_agent.Anthropic")
def test_agent_executes_task(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    # Mock successful text response
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="Result")],
        usage=MagicMock(input_tokens=10, output_tokens=20),
        stop_reason="end_turn"
    )

    # Test agent behavior
    agent = MyAgent(session, workspace_manager)
    result = list(agent.run_task("Do something"))

    assert mock_client.messages.create.called
```

**Tool use response mocking:**
```python
mock_client.messages.create.return_value = MagicMock(
    content=[
        MagicMock(
            type="tool_use",
            id="call_123",
            name="my_tool",
            input={"param": "value"}
        )
    ],
    usage=MagicMock(input_tokens=10, output_tokens=20),
    stop_reason="tool_use"
)
```

**Database fixture pattern:**
```python
@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create minimal schema for tests
    conn.executescript("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT,
            accrediting_body TEXT DEFAULT 'ACCSC'
        );
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            doc_type TEXT,
            status TEXT DEFAULT 'uploaded'
        );
    """)

    yield conn
    conn.close()
```

## Test Categories

**Unit tests:**
- Test individual functions/methods in isolation
- Mock external dependencies (database, API, filesystem)
- Fast execution (< 100ms per test)

**Service tests:**
- Test service layer functions
- Use temp database fixtures
- Verify business logic correctness

**Agent tests:**
- Mock Anthropic client
- Test tool execution logic
- Verify session state management

**Integration tests (limited):**
- Test end-to-end workflows
- Use real database (temp file)
- Verify component interaction

## Running Tests

**All tests:**
```bash
pytest
```

**Single file:**
```bash
pytest tests/test_readiness_service.py
```

**Single test function:**
```bash
pytest tests/test_readiness_service.py::test_compute_readiness_basic
```

**Stop on first failure:**
```bash
pytest -x
```

**With coverage:**
```bash
pytest --cov=src --cov-report=html
```

**Verbose output:**
```bash
pytest -v
```

## Test Examples

**Service test (readiness_service):**
```python
def test_compute_readiness_basic(test_db):
    """Test basic readiness computation."""
    # Setup
    institution_id = "inst_123"
    test_db.execute(
        "INSERT INTO institutions (id, name) VALUES (?, ?)",
        (institution_id, "Test Inst")
    )
    test_db.commit()

    # Execute
    with patch("src.services.readiness_service.get_conn", return_value=test_db):
        score = compute_readiness(institution_id)

    # Verify
    assert isinstance(score, ReadinessScore)
    assert 0 <= score.total <= 100
    assert 0 <= score.documents <= 100
    assert 0 <= score.compliance <= 100
```

**Agent test with tool execution:**
```python
@patch("src.agents.base_agent.Anthropic")
def test_checklist_agent_validates_document(mock_anthropic, temp_workspace):
    """Test checklist agent validates documents correctly."""
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    # Mock tool use response
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(
            type="tool_use",
            id="call_1",
            name="validate_document",
            input={"document_id": "doc_123"}
        )],
        stop_reason="tool_use"
    )

    session = AgentSession(institution_id="inst_123")
    agent = ChecklistAgent(session, workspace_manager=None)

    # Tool should execute
    result = agent._execute_tool("validate_document", {"document_id": "doc_123"})
    assert "success" in result or "error" in result
```

## Coverage Targets

**Current coverage:** Not formally tracked (no CI pipeline)

**Recommended targets:**
- Services: 80%+
- Agents: 70%+ (tool execution logic)
- API endpoints: 60%+ (happy paths)
- Models: 90%+ (serialization round-trips)

**Gap areas (no tests):**
- Integration tests for full workflows
- Concurrent access / race conditions
- Session persistence round-trip
- Workspace migration scenarios

## Test Data

**Inline fixtures:**
- Small, self-contained test data defined in test file
- Use for simple cases

**File fixtures:**
- Store in `tests/fixtures/` if needed
- Use for large test documents or complex JSON

**Database seeding:**
- Use fixture functions that insert minimal required data
- Clean up in fixture teardown

---

*Testing analysis: 2026-03-21*
