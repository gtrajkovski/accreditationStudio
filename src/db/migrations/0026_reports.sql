-- Migration: 0026_reports.sql
-- Description: Add reports table for tracking generated PDF reports

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'compliance',
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    file_path TEXT,
    file_size INTEGER,
    generated_at TEXT,
    generated_by TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_reports_institution ON reports(institution_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
