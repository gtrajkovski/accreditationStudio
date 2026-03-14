-- 0017_impact_analysis.sql
-- Impact Analysis: fact references, impact simulations, fact dependencies

PRAGMA foreign_keys = ON;

-- ============================================================================
-- FACT REFERENCES TABLE
-- Tracks which documents/chunks contain references to each truth index fact
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_references (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    fact_key TEXT NOT NULL,

    -- Document location
    document_id TEXT NOT NULL,
    chunk_id TEXT,
    page_number INTEGER,
    section_header TEXT,
    line_offset INTEGER,

    -- Reference context
    reference_type TEXT NOT NULL DEFAULT 'literal',
    context_snippet TEXT,
    matched_text TEXT,

    -- Detection metadata
    detection_method TEXT NOT NULL DEFAULT 'scan',
    confidence REAL NOT NULL DEFAULT 1.0,

    -- Verification
    verified INTEGER NOT NULL DEFAULT 0,
    verified_by TEXT,
    verified_at TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_refs_institution ON fact_references(institution_id);
CREATE INDEX IF NOT EXISTS idx_fact_refs_fact_key ON fact_references(fact_key);
CREATE INDEX IF NOT EXISTS idx_fact_refs_document ON fact_references(document_id);

-- ============================================================================
-- IMPACT SIMULATIONS TABLE
-- Stores "what-if" analyses before committing changes
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_simulations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,

    -- Proposed change
    fact_key TEXT NOT NULL,
    current_value TEXT,
    proposed_value TEXT NOT NULL,
    change_reason TEXT,

    -- Impact assessment
    documents_affected INTEGER DEFAULT 0,
    chunks_affected INTEGER DEFAULT 0,
    standards_affected TEXT DEFAULT '[]',

    -- Risk assessment
    impact_severity TEXT NOT NULL DEFAULT 'low',
    auto_remediation_possible INTEGER DEFAULT 1,

    -- Result data
    affected_documents TEXT DEFAULT '[]',
    affected_chunks TEXT DEFAULT '[]',
    preview_diffs TEXT DEFAULT '{}',
    dependent_facts TEXT DEFAULT '[]',

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',
    computed_at TEXT,
    applied_at TEXT,
    applied_by TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (applied_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_impact_sim_institution ON impact_simulations(institution_id);
CREATE INDEX IF NOT EXISTS idx_impact_sim_fact_key ON impact_simulations(fact_key);
CREATE INDEX IF NOT EXISTS idx_impact_sim_status ON impact_simulations(status);

-- ============================================================================
-- FACT DEPENDENCIES TABLE
-- Tracks computed/derived facts that depend on other facts
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_dependencies (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    dependent_fact TEXT NOT NULL,
    source_fact TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'direct',
    formula TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    UNIQUE (institution_id, dependent_fact, source_fact)
);

CREATE INDEX IF NOT EXISTS idx_fact_deps_dependent ON fact_dependencies(institution_id, dependent_fact);
CREATE INDEX IF NOT EXISTS idx_fact_deps_source ON fact_dependencies(institution_id, source_fact);

-- ============================================================================
-- IMPACT CHANGE HISTORY TABLE
-- Audit trail of all applied changes
-- ============================================================================

CREATE TABLE IF NOT EXISTS impact_change_history (
    id TEXT PRIMARY KEY,
    simulation_id TEXT,
    institution_id TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,

    -- Remediation tracking
    documents_updated INTEGER DEFAULT 0,
    remediation_jobs_created TEXT DEFAULT '[]',

    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    applied_by TEXT,

    FOREIGN KEY (simulation_id) REFERENCES impact_simulations(id) ON DELETE SET NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (applied_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_impact_history_institution ON impact_change_history(institution_id);
CREATE INDEX IF NOT EXISTS idx_impact_history_fact ON impact_change_history(fact_key);
CREATE INDEX IF NOT EXISTS idx_impact_history_applied ON impact_change_history(applied_at);
