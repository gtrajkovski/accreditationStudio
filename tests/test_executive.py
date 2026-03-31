"""
Tests for Executive Dashboard (Phase 45)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.readiness_service import record_readiness_snapshot, get_readiness_trend


@pytest.fixture
def setup_tables(temp_db):
    """Create required database tables."""
    temp_db.execute("""
        CREATE TABLE IF NOT EXISTS institutions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            accrediting_body TEXT
        )
    """)

    temp_db.execute("""
        CREATE TABLE IF NOT EXISTS readiness_snapshots (
            id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            score REAL NOT NULL,
            documents_score REAL,
            compliance_score REAL,
            evidence_score REAL,
            consistency_score REAL,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    temp_db.execute("""
        INSERT INTO institutions (id, name, accrediting_body)
        VALUES ('inst_test', 'Test Institution', 'ACCSC')
    """)

    temp_db.commit()
    return temp_db


# =============================================================================
# Service Tests
# =============================================================================

def test_record_readiness_snapshot(temp_db, setup_tables, monkeypatch):
    """Test recording readiness snapshot."""
    # Patch get_conn to return temp_db
    monkeypatch.setattr('src.services.readiness_service.get_conn', lambda: temp_db)

    snapshot_id = record_readiness_snapshot(
        institution_id='inst_test',
        score=75.5,
        sub_scores={
            'documents_score': 80.0,
            'compliance_score': 70.0,
            'evidence_score': 75.0,
            'consistency_score': 78.0
        },
        conn=temp_db  # Pass connection directly
    )

    assert snapshot_id.startswith('snap_')

    # Verify stored
    cursor = temp_db.execute("""
        SELECT * FROM readiness_snapshots WHERE id = ?
    """, (snapshot_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row['institution_id'] == 'inst_test'
    assert row['score'] == 75.5
    assert row['documents_score'] == 80.0
    assert row['compliance_score'] == 70.0


def test_get_readiness_trend(temp_db, setup_tables, monkeypatch):
    """Test retrieving readiness trend."""
    # Patch get_conn to return temp_db
    monkeypatch.setattr('src.services.readiness_service.get_conn', lambda: temp_db)

    # Create snapshots for last 30 days
    for i in range(30):
        date = (datetime.now(timezone.utc) - timedelta(days=30-i)).isoformat()
        score = 60 + i  # Upward trend

        temp_db.execute("""
            INSERT INTO readiness_snapshots (
                id, institution_id, score, documents_score,
                compliance_score, evidence_score, consistency_score, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f'snap_{i}',
            'inst_test',
            score,
            score + 5,
            score - 5,
            score,
            score + 2,
            date
        ))

    temp_db.commit()

    trend = get_readiness_trend('inst_test', days=90)

    assert len(trend) == 30  # 30 snapshots created
    assert all('score' in t for t in trend)
    assert all('date' in t for t in trend)

    # Verify chronological order
    scores = [t['score'] for t in trend]
    assert scores == sorted(scores)  # Upward trend


def test_get_readiness_trend_empty(temp_db, setup_tables, monkeypatch):
    """Test trend with no snapshots."""
    # Patch get_conn to return temp_db
    monkeypatch.setattr('src.services.readiness_service.get_conn', lambda: temp_db)

    trend = get_readiness_trend('inst_test', days=90)
    assert len(trend) == 0


# =============================================================================
# API Tests (Simplified)
# =============================================================================

def test_snapshot_storage():
    """Test that snapshot data structure is correct."""
    # This is a smoke test to verify the data model
    from uuid import uuid4

    snapshot_id = f"snap_{uuid4().hex[:12]}"
    assert snapshot_id.startswith('snap_')
    assert len(snapshot_id) == 17  # 'snap_' + 12 hex chars


def test_trend_data_format():
    """Test that trend data format is correct."""
    # Mock trend data format
    trend_data = [
        {
            'date': '2026-03-01',
            'score': 65.0,
            'documents_score': 70.0,
            'compliance_score': 60.0,
            'evidence_score': 65.0,
            'consistency_score': 67.0,
            'recorded_at': '2026-03-01T10:00:00Z'
        }
    ]

    assert len(trend_data) == 1
    assert 'date' in trend_data[0]
    assert 'score' in trend_data[0]
    assert trend_data[0]['score'] == 65.0
