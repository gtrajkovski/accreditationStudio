-- 0014_faculty.sql
-- Faculty credential tracking for Phase 6

PRAGMA foreign_keys = ON;

-- Faculty members table
CREATE TABLE IF NOT EXISTS faculty_members (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    title TEXT,
    department TEXT,
    employment_type TEXT NOT NULL DEFAULT 'fulltime',
    employment_start_date TEXT,
    employment_end_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    work_experience_years INTEGER DEFAULT 0,
    work_experience_summary TEXT,
    foreign_credential_evaluation_json TEXT,
    professional_development_json TEXT NOT NULL DEFAULT '[]',
    compliance_status TEXT NOT NULL DEFAULT 'pending_verification',
    compliance_issues_json TEXT NOT NULL DEFAULT '[]',
    last_compliance_check TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Academic credentials table
CREATE TABLE IF NOT EXISTS faculty_credentials (
    id TEXT PRIMARY KEY,
    faculty_id TEXT NOT NULL,
    credential_type TEXT NOT NULL DEFAULT 'degree',
    title TEXT NOT NULL,
    field_of_study TEXT,
    institution_name TEXT,
    year_awarded INTEGER,
    transcript_on_file INTEGER DEFAULT 0,
    transcript_path TEXT,
    verified INTEGER DEFAULT 0,
    verified_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (faculty_id) REFERENCES faculty_members(id) ON DELETE CASCADE
);

-- Professional licenses table
CREATE TABLE IF NOT EXISTS faculty_licenses (
    id TEXT PRIMARY KEY,
    faculty_id TEXT NOT NULL,
    license_type TEXT NOT NULL,
    license_number TEXT,
    issuing_authority TEXT,
    state_code TEXT,
    issued_date TEXT,
    expiration_date TEXT,
    status TEXT DEFAULT 'active',
    verification_url TEXT,
    last_verified_at TEXT,
    verification_method TEXT,
    document_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (faculty_id) REFERENCES faculty_members(id) ON DELETE CASCADE
);

-- Teaching assignments table
CREATE TABLE IF NOT EXISTS faculty_teaching_assignments (
    id TEXT PRIMARY KEY,
    faculty_id TEXT NOT NULL,
    program_id TEXT,
    course_code TEXT,
    course_name TEXT,
    start_date TEXT,
    end_date TEXT,
    required_credentials_json TEXT DEFAULT '[]',
    qualification_basis TEXT,
    is_qualified INTEGER DEFAULT 1,
    qualification_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (faculty_id) REFERENCES faculty_members(id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_faculty_institution ON faculty_members(institution_id);
CREATE INDEX IF NOT EXISTS idx_faculty_status ON faculty_members(compliance_status);
CREATE INDEX IF NOT EXISTS idx_faculty_active ON faculty_members(is_active);
CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty_members(department);
CREATE INDEX IF NOT EXISTS idx_faculty_employment_type ON faculty_members(employment_type);

CREATE INDEX IF NOT EXISTS idx_credentials_faculty ON faculty_credentials(faculty_id);
CREATE INDEX IF NOT EXISTS idx_credentials_type ON faculty_credentials(credential_type);

CREATE INDEX IF NOT EXISTS idx_licenses_faculty ON faculty_licenses(faculty_id);
CREATE INDEX IF NOT EXISTS idx_licenses_expiration ON faculty_licenses(expiration_date);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON faculty_licenses(status);
CREATE INDEX IF NOT EXISTS idx_licenses_state ON faculty_licenses(state_code);

CREATE INDEX IF NOT EXISTS idx_assignments_faculty ON faculty_teaching_assignments(faculty_id);
CREATE INDEX IF NOT EXISTS idx_assignments_program ON faculty_teaching_assignments(program_id);
CREATE INDEX IF NOT EXISTS idx_assignments_qualified ON faculty_teaching_assignments(is_qualified);
