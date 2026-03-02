-- 0006_remediation.sql
-- Remediation: truth index, consistency checks, remediation jobs

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS truth_index (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string',
    source_document_id TEXT,
    source_page INTEGER,
    source_locator TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (institution_id, key)
);

CREATE TABLE IF NOT EXISTS consistency_checks (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_keys_checked INTEGER DEFAULT 0,
    issues_found INTEGER DEFAULT 0,
    started_at TEXT,
    completed_at TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS consistency_issues (
    id TEXT PRIMARY KEY,
    check_id TEXT NOT NULL,
    key TEXT NOT NULL,
    found_values TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    resolved INTEGER NOT NULL DEFAULT 0,
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (check_id) REFERENCES consistency_checks(id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS remediation_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    audit_run_id TEXT,
    finding_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'queued',
    redline_path TEXT,
    final_path TEXT,
    crossref_path TEXT,
    changes_made TEXT NOT NULL DEFAULT '[]',
    started_at TEXT,
    completed_at TEXT,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_truth_index_institution ON truth_index(institution_id);
CREATE INDEX IF NOT EXISTS idx_truth_index_key ON truth_index(key);
CREATE INDEX IF NOT EXISTS idx_consistency_checks_institution ON consistency_checks(institution_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_check ON consistency_issues(check_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_resolved ON consistency_issues(resolved);
CREATE INDEX IF NOT EXISTS idx_remediation_jobs_document ON remediation_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_remediation_jobs_status ON remediation_jobs(status);
