-- 0022_simulation.sql
-- Accreditation Simulation: Mock audit with predicted findings

PRAGMA foreign_keys = ON;

-- Main simulation run record
CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    accreditor_code TEXT NOT NULL,
    simulation_mode TEXT NOT NULL DEFAULT 'deep',  -- 'quick', 'deep'
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled

    -- Overall Prediction
    pass_prediction TEXT,  -- 'pass', 'conditional', 'fail'
    pass_confidence REAL DEFAULT 0.0,
    risk_level TEXT,  -- 'low', 'medium', 'high', 'critical'

    -- Scores (0-100)
    overall_score INTEGER DEFAULT 0,
    compliance_score INTEGER DEFAULT 0,
    evidence_score INTEGER DEFAULT 0,
    consistency_score INTEGER DEFAULT 0,
    documentation_score INTEGER DEFAULT 0,

    -- Counts
    documents_audited INTEGER DEFAULT 0,
    standards_evaluated INTEGER DEFAULT 0,
    total_findings INTEGER DEFAULT 0,
    critical_findings INTEGER DEFAULT 0,
    significant_findings INTEGER DEFAULT 0,
    advisory_findings INTEGER DEFAULT 0,

    -- Progress tracking
    current_phase TEXT,  -- 'initializing', 'auditing', 'aggregating', 'predicting', 'finalizing'
    progress_pct INTEGER DEFAULT 0,

    -- Timing
    started_at TEXT,
    completed_at TEXT,
    duration_seconds INTEGER DEFAULT 0,

    -- Metadata
    ai_model_used TEXT,
    parameters_json TEXT,  -- JSON: thresholds, weights, options
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Predicted findings from simulation
CREATE TABLE IF NOT EXISTS simulation_findings (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,

    -- Standard/Finding Info
    standard_code TEXT NOT NULL,
    standard_title TEXT,
    category TEXT,  -- Section grouping (e.g., "Institutional", "Program", "Student Services")
    regulatory_source TEXT,  -- 'accreditor', 'federal', 'state', 'professional'

    -- Prediction
    predicted_status TEXT NOT NULL,  -- 'compliant', 'concern', 'finding', 'critical_finding'
    likelihood TEXT NOT NULL,  -- 'likely', 'possible', 'unlikely'
    confidence REAL DEFAULT 0.0,

    -- Details
    finding_summary TEXT,
    evidence_summary TEXT,
    evidence_gaps_json TEXT,  -- JSON array of gap descriptions
    affected_documents_json TEXT,  -- JSON array of {doc_id, doc_title}

    -- Remediation
    remediation_priority INTEGER DEFAULT 0,  -- 1 = highest
    remediation_effort TEXT,  -- 'low', 'medium', 'high'
    remediation_recommendation TEXT,
    estimated_fix_days INTEGER DEFAULT 0,

    -- Source Tracking (which audit findings contributed)
    source_audit_ids_json TEXT,  -- JSON array
    source_finding_ids_json TEXT,  -- JSON array

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id) ON DELETE CASCADE
);

-- Risk assessment by category
CREATE TABLE IF NOT EXISTS simulation_risk_assessment (
    id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,

    risk_category TEXT NOT NULL,  -- 'accreditation', 'federal', 'state', 'programmatic'
    risk_level TEXT NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    risk_score REAL DEFAULT 0.0,  -- 0-100

    contributing_factors_json TEXT,  -- JSON array of factor descriptions
    mitigation_recommendations_json TEXT,  -- JSON array of recommendations

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_simulation_runs_institution
    ON simulation_runs(institution_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_status
    ON simulation_runs(status);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_created
    ON simulation_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_inst_created
    ON simulation_runs(institution_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_simulation_findings_simulation
    ON simulation_findings(simulation_id);
CREATE INDEX IF NOT EXISTS idx_simulation_findings_status
    ON simulation_findings(predicted_status);
CREATE INDEX IF NOT EXISTS idx_simulation_findings_priority
    ON simulation_findings(remediation_priority);

CREATE INDEX IF NOT EXISTS idx_simulation_risk_simulation
    ON simulation_risk_assessment(simulation_id);
CREATE INDEX IF NOT EXISTS idx_simulation_risk_category
    ON simulation_risk_assessment(risk_category);
