"""Tests for audit reproducibility bundle capture and retrieval."""

import pytest
import sqlite3
from unittest.mock import MagicMock, patch

from src.agents.compliance_audit import ComplianceAuditAgent, SYSTEM_PROMPT
from src.agents.base_agent import AgentType
from src.core.models import AgentSession, DocumentType
from src.services.audit_reproducibility_service import (
    capture_audit_snapshot,
    save_audit_snapshot,
    record_finding_provenance,
    get_audit_snapshot,
)
from src.config import Config


@pytest.fixture
def mock_db_connection():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create necessary tables
    conn.executescript("""
        CREATE TABLE audit_snapshots (
            id TEXT PRIMARY KEY,
            audit_run_id TEXT NOT NULL UNIQUE,
            institution_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_version TEXT,
            api_version TEXT,
            system_prompt_hash TEXT,
            system_prompt TEXT,
            tool_definitions_hash TEXT,
            document_hashes TEXT NOT NULL DEFAULT '{}',
            truth_index_hash TEXT,
            accreditor_code TEXT,
            standards_version TEXT,
            standards_hash TEXT,
            confidence_threshold REAL,
            agent_config TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE finding_provenance (
            id TEXT PRIMARY KEY,
            finding_id TEXT NOT NULL UNIQUE,
            audit_snapshot_id TEXT NOT NULL,
            prompt_hash TEXT,
            prompt_text TEXT,
            response_hash TEXT,
            response_text TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            evidence_chunk_hashes TEXT DEFAULT '[]',
            reasoning_steps TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            file_sha256 TEXT,
            status TEXT
        );

        CREATE TABLE truth_index (
            institution_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT
        );
    """)

    yield conn
    conn.close()


# === RED PHASE TESTS (Should fail initially) ===

def test_audit_initialization_creates_snapshot(mock_db_connection):
    """Test 1: Audit initialization creates snapshot with model_id matching Config.MODEL."""
    session = AgentSession(agent_type=AgentType.COMPLIANCE_AUDIT)

    # Mock workspace manager
    mock_workspace = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc_test"
    mock_doc.doc_type = DocumentType.CATALOG
    mock_workspace.load_institution.return_value.documents = [mock_doc]

    agent = ComplianceAuditAgent(session, workspace_manager=mock_workspace)

    # Initialize audit
    result = agent._tool_initialize_audit({
        "institution_id": "inst_test",
        "document_id": "doc_test",
        "standards_library_id": "std_accsc",
    })

    assert result["success"] is True
    # After fix: snapshot should be created
    assert hasattr(agent, '_current_snapshot')
    assert agent._current_snapshot is not None
    assert agent._current_snapshot.model_id == Config.MODEL


def test_audit_initialization_stores_system_prompt_hash(mock_db_connection):
    """Test 2: Audit initialization stores system_prompt_hash (non-empty string, 16 chars)."""
    session = AgentSession(agent_type=AgentType.COMPLIANCE_AUDIT)

    mock_workspace = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc_test"
    mock_doc.doc_type = DocumentType.CATALOG
    mock_workspace.load_institution.return_value.documents = [mock_doc]

    agent = ComplianceAuditAgent(session, workspace_manager=mock_workspace)

    result = agent._tool_initialize_audit({
        "institution_id": "inst_test",
        "document_id": "doc_test",
        "standards_library_id": "std_accsc",
    })

    assert result["success"] is True
    # After fix: snapshot should have system_prompt_hash
    assert agent._current_snapshot.system_prompt_hash is not None
    assert isinstance(agent._current_snapshot.system_prompt_hash, str)
    assert len(agent._current_snapshot.system_prompt_hash) == 16


def test_audit_finalization_saves_snapshot(mock_db_connection):
    """Test 3: Audit finalization saves snapshot to database (row exists in audit_snapshots)."""
    session = AgentSession(agent_type=AgentType.COMPLIANCE_AUDIT)

    mock_workspace = MagicMock()
    agent = ComplianceAuditAgent(session, workspace_manager=mock_workspace)

    # Create a snapshot manually
    from src.services.audit_reproducibility_service import AuditSnapshot
    snapshot = AuditSnapshot(
        audit_run_id="audit_test123",
        institution_id="inst_test",
        model_id=Config.MODEL,
        system_prompt=SYSTEM_PROMPT,
        system_prompt_hash="abc123def456",
        tool_definitions_hash="tool123",
        accreditor_code="ACCSC",
    )

    agent._current_snapshot = snapshot

    # Mock audit cache
    from src.core.models import Audit, AuditStatus
    audit = Audit(
        id="audit_test123",
        document_id="doc_test",
        standards_library_id="std_accsc",
        status=AuditStatus.IN_PROGRESS,
    )
    agent._audit_cache["audit_test123"] = audit

    # Mock _save_audit
    agent._save_audit = MagicMock()

    # Finalize audit (should save snapshot)
    with patch('src.services.audit_reproducibility_service.get_conn', return_value=mock_db_connection):
        result = agent._tool_finalize_audit({"audit_id": "audit_test123"})

    assert result["success"] is True

    # Verify snapshot was saved to database
    cursor = mock_db_connection.execute(
        "SELECT * FROM audit_snapshots WHERE audit_run_id = ?",
        ("audit_test123",)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["model_id"] == Config.MODEL


def test_finding_analysis_records_provenance(mock_db_connection):
    """Test 4: Finding analysis records provenance with prompt/response hashes."""
    session = AgentSession(agent_type=AgentType.COMPLIANCE_AUDIT)

    agent = ComplianceAuditAgent(session)

    # Create snapshot
    from src.services.audit_reproducibility_service import AuditSnapshot
    snapshot = AuditSnapshot(
        id="snap_test123",
        audit_run_id="audit_test",
        institution_id="inst_test",
        model_id=Config.MODEL,
    )
    agent._current_snapshot = snapshot

    # Mock AI response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text='{"status": "compliant", "confidence": 0.9, "reasoning": "test", "evidence_used": "test", "gaps": []}')]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    with patch('src.services.audit_reproducibility_service.get_conn', return_value=mock_db_connection):
        with patch.object(agent.client.messages, 'create', return_value=mock_response):
            # Call _analyze_compliance which should record provenance
            result = agent._analyze_compliance(
                item_number="1.A.1",
                item_description="Test requirement",
                evidence_texts=["Test evidence"]
            )

    # Verify provenance was recorded
    cursor = mock_db_connection.execute(
        "SELECT * FROM finding_provenance WHERE finding_id LIKE ?",
        ("%1.A.1%",)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["prompt_hash"] is not None
    assert row["response_hash"] is not None
    assert row["input_tokens"] == 100
    assert row["output_tokens"] == 50


def test_get_audit_snapshot_returns_populated_snapshot(mock_db_connection):
    """Test 5: get_audit_snapshot returns populated snapshot for completed audit."""
    # Save a snapshot first
    from src.services.audit_reproducibility_service import AuditSnapshot
    snapshot = AuditSnapshot(
        audit_run_id="audit_complete",
        institution_id="inst_test",
        model_id=Config.MODEL,
        system_prompt=SYSTEM_PROMPT,
        system_prompt_hash="abc123def456",
        accreditor_code="ACCSC",
    )

    with patch('src.services.audit_reproducibility_service.get_conn', return_value=mock_db_connection):
        save_audit_snapshot(snapshot, conn=mock_db_connection)

        # Retrieve it
        retrieved = get_audit_snapshot("audit_complete", conn=mock_db_connection)

    assert retrieved is not None
    assert retrieved.audit_run_id == "audit_complete"
    assert retrieved.model_id == Config.MODEL
    assert retrieved.system_prompt_hash == "abc123def456"
    assert retrieved.accreditor_code == "ACCSC"
