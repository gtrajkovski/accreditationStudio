-- 0012_change_detection.sql
-- Change detection: track document changes and trigger re-audits

PRAGMA foreign_keys = ON;

-- Document change events
CREATE TABLE IF NOT EXISTS document_changes (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    previous_sha256 TEXT,
    new_sha256 TEXT,
    previous_version_id TEXT,
    new_version_id TEXT,

    -- Diff summary
    sections_added INTEGER DEFAULT 0,
    sections_removed INTEGER DEFAULT 0,
    sections_modified INTEGER DEFAULT 0,
    diff_summary TEXT,

    -- Re-audit tracking
    affected_standards TEXT DEFAULT '[]',
    reaudit_required INTEGER DEFAULT 0,
    reaudit_triggered INTEGER DEFAULT 0,
    reaudit_session_id TEXT,

    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,

    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Audit invalidations from changes
CREATE TABLE IF NOT EXISTS audit_invalidations (
    id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    standard_ref TEXT,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (change_id) REFERENCES document_changes(id) ON DELETE CASCADE,
    FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_doc_changes_document ON document_changes(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_changes_institution ON document_changes(institution_id);
CREATE INDEX IF NOT EXISTS idx_doc_changes_detected ON document_changes(detected_at);
CREATE INDEX IF NOT EXISTS idx_audit_invalidations_change ON audit_invalidations(change_id);
CREATE INDEX IF NOT EXISTS idx_audit_invalidations_status ON audit_invalidations(status);
