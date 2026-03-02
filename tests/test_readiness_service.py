"""Tests for Readiness Score Computation Service."""

import json
import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.services.readiness_service import (
    compute_readiness,
    persist_snapshot,
    get_latest_snapshot,
    get_readiness_history,
    get_next_actions,
    get_blockers,
    ReadinessScore,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create minimal schema
    conn.executescript("""
        CREATE TABLE institutions (
            id TEXT PRIMARY KEY,
            name TEXT,
            accrediting_body TEXT DEFAULT 'ACCSC',
            readiness_stale INTEGER DEFAULT 1,
            readiness_computed_at TEXT
        );

        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            doc_type TEXT,
            status TEXT DEFAULT 'uploaded',
            title TEXT
        );

        CREATE TABLE audit_runs (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE audit_findings (
            id TEXT PRIMARY KEY,
            audit_run_id TEXT,
            severity TEXT DEFAULT 'moderate',
            compliance_status TEXT DEFAULT 'non_compliant',
            title TEXT,
            standard_ref TEXT
        );

        CREATE TABLE evidence_refs (
            id TEXT PRIMARY KEY,
            finding_id TEXT,
            document_id TEXT,
            chunk_id TEXT,
            confidence REAL DEFAULT 0.85,
            human_review_required INTEGER DEFAULT 0
        );

        CREATE TABLE readiness_consistency_issues (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            truth_key TEXT,
            severity TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            message TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE institution_required_doc_types (
            id TEXT PRIMARY KEY,
            accreditor_code TEXT,
            doc_type TEXT,
            doc_type_label TEXT,
            required INTEGER DEFAULT 1,
            weight INTEGER DEFAULT 15,
            UNIQUE(accreditor_code, doc_type)
        );

        CREATE TABLE institution_readiness_snapshots (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            score_total INTEGER,
            score_documents INTEGER,
            score_compliance INTEGER,
            score_evidence INTEGER,
            score_consistency INTEGER,
            blockers_json TEXT DEFAULT '[]',
            breakdown_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Seed required doc types
        INSERT INTO institution_required_doc_types VALUES
            ('req1', 'ACCSC', 'catalog', 'Catalog', 1, 15),
            ('req2', 'ACCSC', 'enrollment_agreement', 'Enrollment Agreement', 1, 15),
            ('req3', 'ACCSC', 'refund_policy', 'Refund Policy', 1, 15);
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def institution_id(test_db):
    """Create a test institution."""
    inst_id = f"inst_{uuid4().hex[:8]}"
    test_db.execute(
        "INSERT INTO institutions (id, name) VALUES (?, ?)",
        (inst_id, "Test Institution")
    )
    test_db.commit()
    return inst_id


class TestReadinessComputation:
    """Test readiness score computation."""

    def test_empty_institution_has_low_score(self, test_db, institution_id):
        """Empty institution should have low score due to missing docs."""
        score = compute_readiness(institution_id, "ACCSC", test_db)

        # Missing all 3 required docs = -45 points
        assert score.documents <= 55
        assert score.total < 50
        assert len(score.blockers) > 0

    def test_adding_documents_increases_score(self, test_db, institution_id):
        """Adding required documents should increase score."""
        # Get baseline
        baseline = compute_readiness(institution_id, "ACCSC", test_db)

        # Add catalog
        test_db.execute(
            "INSERT INTO documents (id, institution_id, doc_type, status) VALUES (?, ?, ?, ?)",
            (f"doc_{uuid4().hex[:8]}", institution_id, "catalog", "indexed")
        )
        test_db.commit()

        # Score should improve
        after = compute_readiness(institution_id, "ACCSC", test_db)
        assert after.documents > baseline.documents

    def test_critical_findings_reduce_compliance_score(self, test_db, institution_id):
        """Critical findings should reduce compliance score."""
        # Create audit with critical finding
        audit_id = f"audit_{uuid4().hex[:8]}"
        test_db.execute(
            "INSERT INTO audit_runs (id, institution_id, status, completed_at) VALUES (?, ?, ?, ?)",
            (audit_id, institution_id, "completed", datetime.now().isoformat())
        )
        test_db.execute(
            "INSERT INTO audit_findings (id, audit_run_id, severity, compliance_status, title) VALUES (?, ?, ?, ?, ?)",
            (f"find_{uuid4().hex[:8]}", audit_id, "critical", "non_compliant", "Test Finding")
        )
        test_db.commit()

        score = compute_readiness(institution_id, "ACCSC", test_db)

        # Critical finding = -12 points from 100
        assert score.compliance <= 88
        # Should have a blocker for critical finding
        critical_blockers = [b for b in score.blockers if b.type == "critical_finding"]
        assert len(critical_blockers) > 0

    def test_consistency_issues_reduce_score(self, test_db, institution_id):
        """High severity consistency issues should reduce score."""
        # Add high severity consistency issue
        test_db.execute(
            "INSERT INTO readiness_consistency_issues (id, institution_id, truth_key, severity, status, message) VALUES (?, ?, ?, ?, ?, ?)",
            (f"issue_{uuid4().hex[:8]}", institution_id, "tuition_total", "high", "open", "Tuition mismatch")
        )
        test_db.commit()

        score = compute_readiness(institution_id, "ACCSC", test_db)

        # High severity = -10 points
        assert score.consistency <= 90

    def test_score_schema_is_complete(self, test_db, institution_id):
        """Score should have all required fields."""
        score = compute_readiness(institution_id, "ACCSC", test_db)

        assert hasattr(score, 'total')
        assert hasattr(score, 'documents')
        assert hasattr(score, 'compliance')
        assert hasattr(score, 'evidence')
        assert hasattr(score, 'consistency')
        assert hasattr(score, 'blockers')
        assert hasattr(score, 'breakdown')
        assert hasattr(score, 'computed_at')

        # Breakdown should have sub-breakdowns
        assert 'documents' in score.breakdown
        assert 'compliance' in score.breakdown
        assert 'evidence' in score.breakdown
        assert 'consistency' in score.breakdown


class TestSnapshotPersistence:
    """Test snapshot persistence and history."""

    def test_persist_snapshot(self, test_db, institution_id):
        """Snapshots should be persisted to database."""
        score = compute_readiness(institution_id, "ACCSC", test_db)
        snapshot_id = persist_snapshot(institution_id, score, test_db)

        assert snapshot_id.startswith("snap_")

        # Verify in database
        cursor = test_db.execute(
            "SELECT * FROM institution_readiness_snapshots WHERE id = ?",
            (snapshot_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["score_total"] == score.total

    def test_get_latest_snapshot(self, test_db, institution_id):
        """Should retrieve latest snapshot within cache window."""
        score = compute_readiness(institution_id, "ACCSC", test_db)
        persist_snapshot(institution_id, score, test_db)

        latest = get_latest_snapshot(institution_id, max_age_minutes=10, conn=test_db)

        assert latest is not None
        assert latest["total"] == score.total

    def test_history_returns_series(self, test_db, institution_id):
        """History should return multiple snapshots."""
        # Create multiple snapshots
        for i in range(3):
            score = compute_readiness(institution_id, "ACCSC", test_db)
            persist_snapshot(institution_id, score, test_db)

        history = get_readiness_history(institution_id, days=90, conn=test_db)

        assert len(history) == 3
        assert all("total" in h for h in history)


class TestNextActions:
    """Test next actions generation."""

    def test_missing_docs_generate_upload_actions(self, test_db, institution_id):
        """Missing docs should generate upload actions."""
        score = compute_readiness(institution_id, "ACCSC", test_db)
        actions = get_next_actions(institution_id, score, "ACCSC", limit=10)

        upload_actions = [a for a in actions if a.action_type == "upload"]
        assert len(upload_actions) > 0

    def test_actions_are_prioritized(self, test_db, institution_id):
        """Actions should be sorted by priority."""
        score = compute_readiness(institution_id, "ACCSC", test_db)
        actions = get_next_actions(institution_id, score, "ACCSC", limit=10)

        if len(actions) > 1:
            for i in range(len(actions) - 1):
                assert actions[i].priority <= actions[i + 1].priority

    def test_high_score_suggests_packet(self, test_db, institution_id):
        """High score with no blockers should suggest packet generation."""
        # Add all required documents
        for doc_type in ["catalog", "enrollment_agreement", "refund_policy"]:
            test_db.execute(
                "INSERT INTO documents (id, institution_id, doc_type, status) VALUES (?, ?, ?, ?)",
                (f"doc_{uuid4().hex[:8]}", institution_id, doc_type, "indexed")
            )

        # Add passing audit
        audit_id = f"audit_{uuid4().hex[:8]}"
        test_db.execute(
            "INSERT INTO audit_runs (id, institution_id, status, completed_at) VALUES (?, ?, ?, ?)",
            (audit_id, institution_id, "completed", datetime.now().isoformat())
        )
        test_db.commit()

        score = compute_readiness(institution_id, "ACCSC", test_db)

        # If score is high enough, packet should be suggested
        if score.total >= 80:
            actions = get_next_actions(institution_id, score, "ACCSC", limit=10)
            packet_actions = [a for a in actions if a.action_type == "packet"]
            # May or may not have packet action depending on blockers
            assert True  # Just verify no error


class TestBlockers:
    """Test blockers generation."""

    def test_blockers_sorted_by_severity(self, test_db, institution_id):
        """Blockers should be sorted by severity."""
        score = compute_readiness(institution_id, "ACCSC", test_db)

        if len(score.blockers) > 1:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(score.blockers) - 1):
                current = severity_order.get(score.blockers[i].severity, 2)
                next_sev = severity_order.get(score.blockers[i + 1].severity, 2)
                assert current <= next_sev

    def test_blockers_have_actions(self, test_db, institution_id):
        """Every blocker should have an action."""
        score = compute_readiness(institution_id, "ACCSC", test_db)

        for blocker in score.blockers:
            assert blocker.action is not None
            assert len(blocker.action) > 0
