-- Migration: 0044_bulk_remediation.sql
-- Description: Bulk remediation jobs and items tables
-- Date: 2026-03-29

CREATE TABLE IF NOT EXISTS bulk_remediation_jobs (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,  -- all, doc_type, program, severity
    scope_value TEXT,          -- JSON for scope criteria
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, paused, complete, failed
    total_documents INTEGER DEFAULT 0,
    processed_documents INTEGER DEFAULT 0,
    successful_remediations INTEGER DEFAULT 0,
    failed_remediations INTEGER DEFAULT 0,
    skipped_documents INTEGER DEFAULT 0,
    approval_status TEXT DEFAULT 'pending',  -- pending, approved, rejected, partial
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    created_by TEXT,
    error_message TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bulk_remediation_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_name TEXT NOT NULL,
    finding_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, complete, failed, skipped
    remediation_job_id TEXT,  -- links to individual remediation
    changes_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0,
    approval_status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    approved_by TEXT,
    approved_at TEXT,
    error_message TEXT,
    processed_at TEXT,
    FOREIGN KEY (job_id) REFERENCES bulk_remediation_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bulk_job_inst ON bulk_remediation_jobs(institution_id);
CREATE INDEX IF NOT EXISTS idx_bulk_job_status ON bulk_remediation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_bulk_item_job ON bulk_remediation_items(job_id);
CREATE INDEX IF NOT EXISTS idx_bulk_item_status ON bulk_remediation_items(status);
