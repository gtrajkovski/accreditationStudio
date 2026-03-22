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


# === API Tests ===

@pytest.fixture
def client():
    """Create Flask test client."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_with_snapshot(mock_db_connection):
    """Create database with a saved snapshot."""
    from src.services.audit_reproducibility_service import AuditSnapshot
    from dataclasses import dataclass

    snapshot = AuditSnapshot(
        audit_run_id="audit_api_test",
        institution_id="inst_api_test",
        model_id=Config.MODEL,
        system_prompt=SYSTEM_PROMPT,
        system_prompt_hash="abc123def456",
        accreditor_code="ACCSC",
        document_hashes={"doc1": "hash1", "doc2": "hash2"},
    )

    with patch('src.services.audit_reproducibility_service.get_conn', return_value=mock_db_connection):
        save_audit_snapshot(snapshot, conn=mock_db_connection)

    @dataclass
    class SnapshotInfo:
        inst_id: str = "inst_api_test"
        audit_id: str = "audit_api_test"
        snapshot_id: str = snapshot.id

    return SnapshotInfo()


@pytest.fixture
def db_with_provenance(mock_db_connection):
    """Create database with snapshot and provenance."""
    from src.services.audit_reproducibility_service import AuditSnapshot
    from dataclasses import dataclass

    snapshot = AuditSnapshot(
        id="snap_prov_test",
        audit_run_id="audit_prov_test",
        institution_id="inst_prov_test",
        model_id=Config.MODEL,
    )

    with patch('src.services.audit_reproducibility_service.get_conn', return_value=mock_db_connection):
        save_audit_snapshot(snapshot, conn=mock_db_connection)
        record_finding_provenance(
            finding_id="finding_1",
            snapshot_id=snapshot.id,
            prompt="Test prompt",
            response="Test response",
            input_tokens=50,
            output_tokens=25,
            conn=mock_db_connection,
        )

    @dataclass
    class ProvenanceInfo:
        inst_id: str = "inst_prov_test"
        audit_id: str = "audit_prov_test"
        finding_id: str = "finding_1"

    return ProvenanceInfo()


def test_get_reproducibility_not_found(client):
    """GET /reproducibility returns 404 for unknown audit."""
    with patch('src.services.audit_reproducibility_service.get_audit_snapshot', return_value=None):
        response = client.get('/api/institutions/inst_test/audits/unknown/reproducibility')
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


def test_get_reproducibility_success(client, db_with_snapshot):
    """GET /reproducibility returns bundle with summary and technical sections."""
    from src.services.audit_reproducibility_service import AuditSnapshot

    snapshot = AuditSnapshot(
        audit_run_id=db_with_snapshot.audit_id,
        institution_id=db_with_snapshot.inst_id,
        model_id=Config.MODEL,
        system_prompt_hash="abc123def456",
        accreditor_code="ACCSC",
        document_hashes={"doc1": "hash1", "doc2": "hash2"},
    )

    with patch('src.services.audit_reproducibility_service.get_audit_snapshot', return_value=snapshot):
        response = client.get(f'/api/institutions/{db_with_snapshot.inst_id}/audits/{db_with_snapshot.audit_id}/reproducibility')
        assert response.status_code == 200
        data = response.get_json()

        # Check summary section (D-06)
        assert "summary" in data
        assert "model" in data["summary"]
        assert "accreditor" in data["summary"]
        assert "document_count" in data["summary"]
        assert data["summary"]["document_count"] == 2

        # Check technical section (D-07)
        assert "technical" in data
        assert "system_prompt_hash" in data["technical"]
        assert "document_hashes" in data["technical"]

        # Prompts should NOT be included by default
        assert "system_prompt" not in data["technical"]


def test_get_reproducibility_with_prompts(client, db_with_snapshot):
    """GET /reproducibility?include_prompts=true includes full prompt text."""
    from src.services.audit_reproducibility_service import AuditSnapshot

    snapshot = AuditSnapshot(
        audit_run_id=db_with_snapshot.audit_id,
        institution_id=db_with_snapshot.inst_id,
        model_id=Config.MODEL,
        system_prompt=SYSTEM_PROMPT,
        system_prompt_hash="abc123def456",
        accreditor_code="ACCSC",
        document_hashes={},
    )

    with patch('src.services.audit_reproducibility_service.get_audit_snapshot', return_value=snapshot):
        response = client.get(
            f'/api/institutions/{db_with_snapshot.inst_id}/audits/{db_with_snapshot.audit_id}/reproducibility?include_prompts=true'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "system_prompt" in data["technical"]
        assert len(data["technical"]["system_prompt"]) > 100


def test_get_reproducibility_with_verify(client, db_with_snapshot):
    """GET /reproducibility?verify=true includes verification status."""
    from src.services.audit_reproducibility_service import AuditSnapshot

    snapshot = AuditSnapshot(
        audit_run_id=db_with_snapshot.audit_id,
        institution_id=db_with_snapshot.inst_id,
        model_id=Config.MODEL,
        system_prompt_hash="abc123def456",
        accreditor_code="ACCSC",
        document_hashes={},
    )

    verification_result = {
        "verified": True,
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at,
        "discrepancies": [],
    }

    with patch('src.services.audit_reproducibility_service.get_audit_snapshot', return_value=snapshot):
        with patch('src.services.audit_reproducibility_service.verify_audit_reproducibility', return_value=verification_result):
            response = client.get(
                f'/api/institutions/{db_with_snapshot.inst_id}/audits/{db_with_snapshot.audit_id}/reproducibility?verify=true'
            )
            assert response.status_code == 200
            data = response.get_json()
            assert "verification" in data
            assert "verified" in data["verification"]


def test_get_finding_provenance_not_found(client, mock_db_connection):
    """GET /findings/{id}/provenance returns 404 for unknown finding."""
    with patch('src.db.connection.get_conn', return_value=mock_db_connection):
        response = client.get('/api/institutions/inst_test/audits/audit_test/findings/unknown/provenance')
        assert response.status_code == 404


def test_get_finding_provenance_success(client, db_with_provenance):
    """GET /findings/{id}/provenance returns prompt and response data."""
    from src.db.connection import get_conn

    # Create a mock connection with the provenance data
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_row = {
        "model_id": Config.MODEL,
        "prompt_hash": "abc123",
        "response_hash": "def456",
        "prompt_text": "Test prompt",
        "response_text": "Test response",
        "input_tokens": 50,
        "output_tokens": 25,
        "evidence_chunk_hashes": "[]",
        "reasoning_steps": "[]",
    }
    mock_cursor.fetchone.return_value = mock_row
    mock_conn.execute.return_value = mock_cursor

    with patch('src.db.connection.get_conn', return_value=mock_conn):
        response = client.get(
            f'/api/institutions/{db_with_provenance.inst_id}/audits/{db_with_provenance.audit_id}/findings/{db_with_provenance.finding_id}/provenance'
        )
        assert response.status_code == 200
        data = response.get_json()

        assert "prompt_hash" in data
        assert "response_hash" in data
        assert "prompt_text" in data
        assert "input_tokens" in data
        assert data["input_tokens"] == 50
