-- 0013_audit_reproducibility.sql
-- Audit reproducibility: capture full context for defensible audits

PRAGMA foreign_keys = ON;

-- Audit execution context for reproducibility
CREATE TABLE IF NOT EXISTS audit_snapshots (
    id TEXT PRIMARY KEY,
    audit_run_id TEXT NOT NULL UNIQUE,
    institution_id TEXT NOT NULL,

    -- Model info
    model_id TEXT NOT NULL,
    model_version TEXT,
    api_version TEXT,

    -- Prompts used
    system_prompt_hash TEXT,
    system_prompt TEXT,
    tool_definitions_hash TEXT,

    -- Document state at audit time
    document_hashes TEXT NOT NULL DEFAULT '{}',
    truth_index_hash TEXT,

    -- Standards version
    accreditor_code TEXT,
    standards_version TEXT,
    standards_hash TEXT,

    -- Configuration
    confidence_threshold REAL,
    agent_config TEXT DEFAULT '{}',

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Individual finding reproducibility
CREATE TABLE IF NOT EXISTS finding_provenance (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL UNIQUE,
    audit_snapshot_id TEXT NOT NULL,

    -- AI interaction that produced this finding
    prompt_hash TEXT,
    prompt_text TEXT,
    response_hash TEXT,
    response_text TEXT,

    -- Token usage
    input_tokens INTEGER,
    output_tokens INTEGER,

    -- Evidence hashes
    evidence_chunk_hashes TEXT DEFAULT '[]',

    -- Reasoning chain
    reasoning_steps TEXT DEFAULT '[]',

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
    FOREIGN KEY (audit_snapshot_id) REFERENCES audit_snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_snapshots_run ON audit_snapshots(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_audit_snapshots_institution ON audit_snapshots(institution_id);
CREATE INDEX IF NOT EXISTS idx_finding_provenance_finding ON finding_provenance(finding_id);
CREATE INDEX IF NOT EXISTS idx_finding_provenance_snapshot ON finding_provenance(audit_snapshot_id);
