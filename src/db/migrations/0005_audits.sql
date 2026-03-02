-- 0005_audits.sql
-- Audit system: runs, findings, evidence, checkpoints

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_runs (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    program_id TEXT,
    checklist_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    started_at TEXT,
    completed_at TEXT,
    total_findings INTEGER DEFAULT 0,
    compliant_count INTEGER DEFAULT 0,
    partial_count INTEGER DEFAULT 0,
    non_compliant_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
    FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_findings (
    id TEXT PRIMARY KEY,
    audit_run_id TEXT NOT NULL,
    document_id TEXT,
    checklist_item_id TEXT,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommendation TEXT,
    confidence REAL NOT NULL,
    human_review_required INTEGER NOT NULL DEFAULT 0,
    reviewed_at TEXT,
    reviewed_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE SET NULL,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evidence_refs (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_version_id TEXT,
    page INTEGER,
    locator TEXT NOT NULL DEFAULT '{}',
    snippet_hash TEXT NOT NULL,
    snippet_text TEXT,
    snippet_text_path TEXT,
    language TEXT NOT NULL DEFAULT 'en-US',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS finding_standard_refs (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    standard_id TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
    FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS human_checkpoints (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    session_id TEXT,
    finding_id TEXT,
    checkpoint_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_by TEXT NOT NULL,
    reason TEXT,
    notes TEXT,
    resolved_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE SET NULL,
    FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_runs_institution_id ON audit_runs(institution_id);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON audit_runs(status);
CREATE INDEX IF NOT EXISTS idx_findings_audit_run_id ON audit_findings(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON audit_findings(status);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON audit_findings(severity);
CREATE INDEX IF NOT EXISTS idx_evidence_finding_id ON evidence_refs(finding_id);
CREATE INDEX IF NOT EXISTS idx_evidence_document_id ON evidence_refs(document_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_institution ON human_checkpoints(institution_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON human_checkpoints(status);
