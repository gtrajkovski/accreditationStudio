"""Tests for Work Queue Service."""

import pytest
import sqlite3
from uuid import uuid4

from src.services.work_queue_service import (
    get_work_queue,
    get_work_queue_summary,
    WorkItem,
    WorkItemType,
    WorkItemPriority,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

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
            confidence REAL DEFAULT 0.85
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
            weight INTEGER DEFAULT 15
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

        CREATE TABLE human_checkpoints (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            session_id TEXT,
            finding_id TEXT,
            checkpoint_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_by TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE agent_sessions (
            id TEXT PRIMARY KEY,
            institution_id TEXT,
            agent_type TEXT,
            status TEXT DEFAULT 'running',
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Seed required doc types
        INSERT INTO institution_required_doc_types VALUES
            ('req1', 'ACCSC', 'catalog', 'Catalog', 1, 15);
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


class TestWorkQueue:
    """Test work queue aggregation."""

    def test_empty_queue_returns_blockers_only(self, test_db, institution_id):
        """Empty queue still returns blockers from readiness."""
        items = get_work_queue(
            institution_id=institution_id,
            include_tasks=False,
            include_approvals=False,
            conn=test_db
        )

        # Should have blockers for missing docs
        blocker_items = [i for i in items if i.type == WorkItemType.BLOCKER]
        assert len(blocker_items) > 0

    def test_pending_checkpoints_appear_in_queue(self, test_db, institution_id):
        """Pending checkpoints should appear as approval items."""
        # Add pending checkpoint
        checkpoint_id = f"chk_{uuid4().hex[:8]}"
        test_db.execute("""
            INSERT INTO human_checkpoints
            (id, institution_id, checkpoint_type, status, requested_by, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (checkpoint_id, institution_id, "compliance_determination", "pending",
              "compliance_audit", "Review finding"))
        test_db.commit()

        items = get_work_queue(
            institution_id=institution_id,
            include_blockers=False,
            include_tasks=False,
            conn=test_db
        )

        approval_items = [i for i in items if i.type == WorkItemType.APPROVAL]
        assert len(approval_items) >= 1
        assert any(checkpoint_id in i.id for i in approval_items)

    def test_waiting_sessions_appear_in_queue(self, test_db, institution_id):
        """Sessions waiting for human should appear as approval items."""
        session_id = f"sess_{uuid4().hex[:8]}"
        test_db.execute("""
            INSERT INTO agent_sessions
            (id, institution_id, agent_type, status)
            VALUES (?, ?, ?, ?)
        """, (session_id, institution_id, "compliance_audit", "waiting_for_human"))
        test_db.commit()

        items = get_work_queue(
            institution_id=institution_id,
            include_blockers=False,
            include_tasks=False,
            conn=test_db
        )

        session_items = [i for i in items if session_id in (i.session_id or "")]
        assert len(session_items) >= 1

    def test_items_sorted_by_priority(self, test_db, institution_id):
        """Work items should be sorted by priority."""
        # Add checkpoints with different priorities
        for i, (cp_type, reason) in enumerate([
            ("compliance_determination", "Critical check"),
            ("evidence_validation", "Review evidence"),
        ]):
            test_db.execute("""
                INSERT INTO human_checkpoints
                (id, institution_id, checkpoint_type, status, requested_by, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f"chk_{i}", institution_id, cp_type, "pending", "agent", reason))
        test_db.commit()

        items = get_work_queue(
            institution_id=institution_id,
            conn=test_db
        )

        if len(items) > 1:
            priority_order = {
                WorkItemPriority.CRITICAL: 0,
                WorkItemPriority.HIGH: 1,
                WorkItemPriority.MEDIUM: 2,
                WorkItemPriority.LOW: 3,
            }
            for i in range(len(items) - 1):
                current = priority_order.get(items[i].priority, 2)
                next_p = priority_order.get(items[i + 1].priority, 2)
                assert current <= next_p


class TestWorkQueueSummary:
    """Test work queue summary."""

    def test_summary_has_counts(self, test_db, institution_id):
        """Summary should have counts by type and priority."""
        summary = get_work_queue_summary(institution_id, conn=test_db)

        assert "total" in summary
        assert "by_type" in summary
        assert "by_priority" in summary
        assert "critical_count" in summary
        assert "needs_attention" in summary

    def test_summary_counts_are_accurate(self, test_db, institution_id):
        """Summary counts should match actual items."""
        # Add a checkpoint
        test_db.execute("""
            INSERT INTO human_checkpoints
            (id, institution_id, checkpoint_type, status, requested_by)
            VALUES (?, ?, ?, ?, ?)
        """, ("chk_1", institution_id, "review", "pending", "agent"))
        test_db.commit()

        summary = get_work_queue_summary(institution_id, conn=test_db)
        items = get_work_queue(institution_id, conn=test_db)

        assert summary["total"] == len(items)


class TestWorkItem:
    """Test WorkItem model."""

    def test_to_dict(self):
        """WorkItem should serialize to dict."""
        item = WorkItem(
            id="test_1",
            type=WorkItemType.BLOCKER,
            priority=WorkItemPriority.HIGH,
            title="Test Item",
            description="Test description",
            source="test",
        )

        d = item.to_dict()

        assert d["id"] == "test_1"
        assert d["type"] == "blocker"
        assert d["priority"] == "high"
        assert d["title"] == "Test Item"

    def test_optional_fields(self):
        """WorkItem should handle optional fields."""
        item = WorkItem(
            id="test_2",
            type=WorkItemType.APPROVAL,
            priority=WorkItemPriority.CRITICAL,
            title="Approval Needed",
            description="Please review",
            source="agent:compliance",
            session_id="sess_123",
            checkpoint_id="chk_456",
        )

        d = item.to_dict()

        assert d["session_id"] == "sess_123"
        assert d["checkpoint_id"] == "chk_456"
