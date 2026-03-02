-- Readiness Consistency Issues Table
-- Tracks cross-document consistency mismatches for readiness scoring
-- Note: Different from consistency_issues in 0006 which links to consistency_checks

CREATE TABLE IF NOT EXISTS readiness_consistency_issues (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    truth_key TEXT NOT NULL,
    expected_value TEXT,
    found_value TEXT,
    document_id TEXT,
    chunk_id TEXT,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_readiness_consistency_institution_status
ON readiness_consistency_issues(institution_id, status);

CREATE INDEX IF NOT EXISTS idx_readiness_consistency_severity
ON readiness_consistency_issues(institution_id, severity);
