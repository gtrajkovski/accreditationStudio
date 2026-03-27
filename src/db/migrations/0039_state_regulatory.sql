-- 0039_state_regulatory.sql
-- State Regulatory Compliance Tracking

PRAGMA foreign_keys = ON;

-- =============================================================================
-- State Authorizations
-- =============================================================================

CREATE TABLE IF NOT EXISTS state_authorizations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    state_code TEXT NOT NULL,
    authorization_status TEXT NOT NULL CHECK (authorization_status IN ('authorized', 'pending', 'restricted', 'denied')),
    sara_member BOOLEAN DEFAULT FALSE,
    effective_date TEXT,
    renewal_date TEXT,
    contact_agency TEXT,
    contact_url TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(institution_id, state_code)
    -- FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_state_auth_institution ON state_authorizations(institution_id);
CREATE INDEX IF NOT EXISTS idx_state_auth_state ON state_authorizations(state_code);
CREATE INDEX IF NOT EXISTS idx_state_auth_status ON state_authorizations(authorization_status);
CREATE INDEX IF NOT EXISTS idx_state_auth_renewal ON state_authorizations(renewal_date);

-- =============================================================================
-- State Catalog Requirements
-- =============================================================================

CREATE TABLE IF NOT EXISTS state_catalog_requirements (
    id TEXT PRIMARY KEY,
    state_code TEXT NOT NULL,
    requirement_key TEXT NOT NULL,
    requirement_name TEXT NOT NULL,
    requirement_text TEXT,
    category TEXT CHECK (category IN ('disclosure', 'consumer_info', 'completion_rates')),
    required BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    UNIQUE(state_code, requirement_key)
);

CREATE INDEX IF NOT EXISTS idx_state_catalog_req_state ON state_catalog_requirements(state_code);
CREATE INDEX IF NOT EXISTS idx_state_catalog_req_category ON state_catalog_requirements(category);

-- =============================================================================
-- State Catalog Compliance
-- =============================================================================

CREATE TABLE IF NOT EXISTS state_catalog_compliance (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    state_code TEXT NOT NULL,
    requirement_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('satisfied', 'partial', 'missing')),
    evidence_doc_id TEXT,
    page_reference TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(institution_id, requirement_id)
    -- FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
    -- FOREIGN KEY (requirement_id) REFERENCES state_catalog_requirements(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_state_catalog_comp_inst ON state_catalog_compliance(institution_id);
CREATE INDEX IF NOT EXISTS idx_state_catalog_comp_state ON state_catalog_compliance(state_code);
CREATE INDEX IF NOT EXISTS idx_state_catalog_comp_status ON state_catalog_compliance(status);

-- =============================================================================
-- State Program Approvals
-- =============================================================================

CREATE TABLE IF NOT EXISTS state_program_approvals (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    program_id TEXT NOT NULL,
    state_code TEXT NOT NULL,
    board_name TEXT NOT NULL,
    board_url TEXT,
    approved BOOLEAN DEFAULT FALSE,
    approval_date TEXT,
    expiration_date TEXT,
    license_exam TEXT,
    min_pass_rate REAL,
    current_pass_rate REAL,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(institution_id, program_id, state_code)
    -- FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_state_program_inst ON state_program_approvals(institution_id);
CREATE INDEX IF NOT EXISTS idx_state_program_state ON state_program_approvals(state_code);
CREATE INDEX IF NOT EXISTS idx_state_program_program ON state_program_approvals(program_id);
CREATE INDEX IF NOT EXISTS idx_state_program_approved ON state_program_approvals(approved);
CREATE INDEX IF NOT EXISTS idx_state_program_expiration ON state_program_approvals(expiration_date);
