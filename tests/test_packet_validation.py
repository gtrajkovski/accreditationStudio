"""Tests for packet validation service (evidence contract enforcement).

Tests the validate_packet() function and export gating logic.
"""

import json
import pytest
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.services.packet_service import (
    ValidationResult,
    validate_packet,
    check_force_export_override,
    create_finalize_checkpoint,
)


@pytest.fixture
def mock_db():
    """Create an in-memory database with required schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create minimal schema for testing
    conn.executescript("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT
        );

        CREATE TABLE submission_packets (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            packet_type TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft'
        );

        CREATE TABLE packet_items (
            id TEXT PRIMARY KEY,
            packet_id TEXT NOT NULL,
            ref TEXT DEFAULT '{}'
        );

        CREATE TABLE audit_runs (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            status TEXT DEFAULT 'completed'
        );

        CREATE TABLE audit_findings (
            id TEXT PRIMARY KEY,
            audit_run_id TEXT NOT NULL,
            summary TEXT,
            severity TEXT,
            status TEXT
        );

        CREATE TABLE evidence_refs (
            id TEXT PRIMARY KEY,
            finding_id TEXT NOT NULL,
            document_id TEXT
        );

        CREATE TABLE finding_standard_refs (
            id TEXT PRIMARY KEY,
            finding_id TEXT NOT NULL,
            standard_id TEXT NOT NULL
        );

        CREATE TABLE human_checkpoints (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            checkpoint_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_by TEXT,
            reason TEXT,
            notes TEXT,
            created_at TEXT,
            resolved_at TEXT
        );
    """)

    return conn


@pytest.fixture
def setup_institution(mock_db):
    """Set up an institution for testing."""
    mock_db.execute(
        "INSERT INTO institutions (id, name) VALUES (?, ?)",
        ("inst_test", "Test University")
    )
    mock_db.commit()
    return "inst_test"


@pytest.fixture
def setup_packet(mock_db, setup_institution):
    """Set up a packet for testing."""
    mock_db.execute(
        "INSERT INTO submission_packets (id, institution_id, packet_type, title) VALUES (?, ?, ?, ?)",
        ("pkt_test", setup_institution, "response", "Test Packet")
    )
    mock_db.commit()
    return "pkt_test"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = ValidationResult()
        assert result.ok is True
        assert result.missing_standards == []
        assert result.missing_evidence == []
        assert result.blocking_findings == []
        assert result.required_checkpoints == []

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = ValidationResult(
            ok=False,
            missing_standards=["STD-001", "STD-002"],
            blocking_findings=["find_001"],
        )
        data = result.to_dict()

        assert data["ok"] is False
        assert len(data["missing_standards"]) == 2
        assert len(data["blocking_findings"]) == 1


class TestValidatePacket:
    """Tests for validate_packet function."""

    def test_packet_not_found(self, mock_db):
        """Test validation fails if packet doesn't exist."""
        result = validate_packet("nonexistent", conn=mock_db)

        assert result.ok is False
        assert "packet_not_found" in result.required_checkpoints

    def test_packet_with_full_evidence(self, mock_db, setup_packet):
        """Test packet with full evidence coverage passes validation."""
        # Add packet item with standard reference
        mock_db.execute(
            "INSERT INTO packet_items (id, packet_id, ref) VALUES (?, ?, ?)",
            ("item_1", setup_packet, json.dumps({"standard_refs": ["STD-001"]}))
        )

        # Add audit run and finding with evidence
        mock_db.execute(
            "INSERT INTO audit_runs (id, institution_id, status) VALUES (?, ?, ?)",
            ("audit_1", "inst_test", "completed")
        )
        mock_db.execute(
            "INSERT INTO audit_findings (id, audit_run_id, summary, severity, status) VALUES (?, ?, ?, ?, ?)",
            ("find_1", "audit_1", "Test finding", "advisory", "compliant")
        )
        mock_db.execute(
            "INSERT INTO evidence_refs (id, finding_id, document_id) VALUES (?, ?, ?)",
            ("ev_1", "find_1", "doc_1")
        )
        mock_db.execute(
            "INSERT INTO finding_standard_refs (id, finding_id, standard_id) VALUES (?, ?, ?)",
            ("fsr_1", "find_1", "STD-001")
        )
        mock_db.commit()

        result = validate_packet(setup_packet, conn=mock_db)

        assert result.ok is True
        assert len(result.missing_standards) == 0
        assert len(result.blocking_findings) == 0

    def test_packet_missing_evidence(self, mock_db, setup_packet):
        """Test packet missing evidence coverage fails validation."""
        # Add packet item with standard reference but no evidence
        mock_db.execute(
            "INSERT INTO packet_items (id, packet_id, ref) VALUES (?, ?, ?)",
            ("item_1", setup_packet, json.dumps({"standard_refs": ["STD-001"]}))
        )
        mock_db.commit()

        result = validate_packet(setup_packet, conn=mock_db)

        assert result.ok is False
        assert "STD-001" in result.missing_standards

    def test_packet_with_critical_findings(self, mock_db, setup_packet):
        """Test packet with critical unresolved findings fails validation."""
        # Add audit run with critical non-compliant finding
        mock_db.execute(
            "INSERT INTO audit_runs (id, institution_id, status) VALUES (?, ?, ?)",
            ("audit_1", "inst_test", "completed")
        )
        mock_db.execute(
            "INSERT INTO audit_findings (id, audit_run_id, summary, severity, status) VALUES (?, ?, ?, ?, ?)",
            ("find_crit", "audit_1", "Critical issue", "critical", "non_compliant")
        )
        mock_db.commit()

        result = validate_packet(setup_packet, conn=mock_db)

        assert result.ok is False
        assert "find_crit" in result.blocking_findings

    def test_packet_with_resolved_critical(self, mock_db, setup_packet):
        """Test packet with resolved critical findings passes validation."""
        # Add audit run with resolved critical finding
        mock_db.execute(
            "INSERT INTO audit_runs (id, institution_id, status) VALUES (?, ?, ?)",
            ("audit_1", "inst_test", "completed")
        )
        mock_db.execute(
            "INSERT INTO audit_findings (id, audit_run_id, summary, severity, status) VALUES (?, ?, ?, ?, ?)",
            ("find_crit", "audit_1", "Critical issue", "critical", "compliant")
        )
        mock_db.execute(
            "INSERT INTO evidence_refs (id, finding_id, document_id) VALUES (?, ?, ?)",
            ("ev_1", "find_crit", "doc_1")
        )
        mock_db.commit()

        result = validate_packet(setup_packet, conn=mock_db)

        assert result.ok is True
        assert len(result.blocking_findings) == 0


class TestForceExportOverride:
    """Tests for check_force_export_override function."""

    def test_checkpoint_not_found(self, mock_db):
        """Test override fails if checkpoint doesn't exist."""
        result = check_force_export_override("pkt_test", "nonexistent", conn=mock_db)

        assert result["valid"] is False
        assert "not found" in result["reason"]

    def test_wrong_checkpoint_type(self, mock_db, setup_institution):
        """Test override fails with wrong checkpoint type."""
        # Create packet first
        mock_db.execute(
            "INSERT INTO submission_packets (id, institution_id, packet_type, title) VALUES (?, ?, ?, ?)",
            ("pkt_test", setup_institution, "response", "Test Packet")
        )
        # Create checkpoint with wrong type
        mock_db.execute(
            "INSERT INTO human_checkpoints (id, institution_id, checkpoint_type, status) VALUES (?, ?, ?, ?)",
            ("cp_wrong", setup_institution, "approval", "resolved")
        )
        mock_db.commit()

        result = check_force_export_override("pkt_test", "cp_wrong", conn=mock_db)

        assert result["valid"] is False
        assert "Invalid checkpoint type" in result["reason"]

    def test_checkpoint_not_resolved(self, mock_db, setup_institution):
        """Test override fails if checkpoint not resolved."""
        mock_db.execute(
            "INSERT INTO submission_packets (id, institution_id, packet_type, title) VALUES (?, ?, ?, ?)",
            ("pkt_test", setup_institution, "response", "Test Packet")
        )
        mock_db.execute(
            "INSERT INTO human_checkpoints (id, institution_id, checkpoint_type, status) VALUES (?, ?, ?, ?)",
            ("cp_pending", setup_institution, "finalize_submission", "pending")
        )
        mock_db.commit()

        result = check_force_export_override("pkt_test", "cp_pending", conn=mock_db)

        assert result["valid"] is False
        assert "not resolved" in result["reason"]

    def test_valid_override(self, mock_db, setup_institution):
        """Test valid override with resolved finalize_submission checkpoint."""
        mock_db.execute(
            "INSERT INTO submission_packets (id, institution_id, packet_type, title) VALUES (?, ?, ?, ?)",
            ("pkt_test", setup_institution, "response", "Test Packet")
        )
        mock_db.execute(
            "INSERT INTO human_checkpoints (id, institution_id, checkpoint_type, status) VALUES (?, ?, ?, ?)",
            ("cp_valid", setup_institution, "finalize_submission", "resolved")
        )
        mock_db.commit()

        result = check_force_export_override("pkt_test", "cp_valid", conn=mock_db)

        assert result["valid"] is True
        assert "accepted" in result["reason"]


class TestCreateFinalizeCheckpoint:
    """Tests for create_finalize_checkpoint function."""

    def test_creates_checkpoint(self, mock_db, setup_institution):
        """Test checkpoint creation with validation result."""
        validation = ValidationResult(
            ok=False,
            missing_standards=["STD-001", "STD-002"],
            blocking_findings=["find_001"],
        )

        result = create_finalize_checkpoint(
            "pkt_test", setup_institution, validation, conn=mock_db
        )

        assert "checkpoint_id" in result
        assert result["checkpoint_type"] == "finalize_submission"
        assert result["status"] == "pending"
        assert "standards lack evidence" in result["reason"]

        # Verify checkpoint was stored
        cursor = mock_db.execute(
            "SELECT * FROM human_checkpoints WHERE id = ?",
            (result["checkpoint_id"],)
        )
        checkpoint = cursor.fetchone()
        assert checkpoint is not None
        assert checkpoint["checkpoint_type"] == "finalize_submission"

    def test_checkpoint_includes_validation_in_notes(self, mock_db, setup_institution):
        """Test checkpoint notes contain validation details."""
        validation = ValidationResult(
            ok=False,
            blocking_findings=["find_001", "find_002"],
        )

        result = create_finalize_checkpoint(
            "pkt_test", setup_institution, validation, conn=mock_db
        )

        cursor = mock_db.execute(
            "SELECT notes FROM human_checkpoints WHERE id = ?",
            (result["checkpoint_id"],)
        )
        checkpoint = cursor.fetchone()
        notes = json.loads(checkpoint["notes"])

        assert notes["packet_id"] == "pkt_test"
        assert len(notes["validation"]["blocking_findings"]) == 2
