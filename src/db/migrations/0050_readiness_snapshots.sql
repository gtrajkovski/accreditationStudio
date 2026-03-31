-- Migration: 0050_readiness_snapshots.sql
-- Phase: 45 (Executive Dashboard)
-- Purpose: Add readiness_snapshots table for tracking readiness score trends

CREATE TABLE IF NOT EXISTS readiness_snapshots (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    score REAL NOT NULL,
    documents_score REAL,
    compliance_score REAL,
    evidence_score REAL,
    consistency_score REAL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_readiness_snapshots_inst
    ON readiness_snapshots(institution_id, recorded_at);
