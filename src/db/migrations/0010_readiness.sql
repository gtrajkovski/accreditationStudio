-- Readiness Score Snapshots
-- Stores historical readiness scores for trend tracking

CREATE TABLE IF NOT EXISTS institution_readiness_snapshots (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    score_total INTEGER NOT NULL,
    score_documents INTEGER NOT NULL,
    score_compliance INTEGER NOT NULL,
    score_evidence INTEGER NOT NULL,
    score_consistency INTEGER NOT NULL,
    blockers_json TEXT NOT NULL DEFAULT '[]',
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_readiness_institution_created
ON institution_readiness_snapshots(institution_id, created_at DESC);

-- Required Document Types per Accreditor
-- Defines which document types are required for each accrediting body

CREATE TABLE IF NOT EXISTS institution_required_doc_types (
    id TEXT PRIMARY KEY,
    accreditor_code TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    doc_type_label TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    weight INTEGER NOT NULL DEFAULT 15,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(accreditor_code, doc_type)
);

-- Seed required document types for ACCSC
INSERT OR IGNORE INTO institution_required_doc_types (id, accreditor_code, doc_type, doc_type_label, required, weight) VALUES
    ('req_accsc_catalog', 'ACCSC', 'catalog', 'Institutional Catalog', 1, 15),
    ('req_accsc_enrollment', 'ACCSC', 'enrollment_agreement', 'Enrollment Agreement', 1, 15),
    ('req_accsc_refund', 'ACCSC', 'refund_policy', 'Refund Policy', 1, 15),
    ('req_accsc_program', 'ACCSC', 'program_outline', 'Program Outline', 1, 12),
    ('req_accsc_faculty', 'ACCSC', 'faculty_handbook', 'Faculty Qualifications/Handbook', 1, 12),
    ('req_accsc_admissions', 'ACCSC', 'admissions_policy', 'Admissions Policy', 1, 10),
    ('req_accsc_attendance', 'ACCSC', 'attendance_policy', 'Attendance Policy', 1, 8);

-- Seed required document types for COE
INSERT OR IGNORE INTO institution_required_doc_types (id, accreditor_code, doc_type, doc_type_label, required, weight) VALUES
    ('req_coe_catalog', 'COE', 'catalog', 'Institutional Catalog', 1, 15),
    ('req_coe_enrollment', 'COE', 'enrollment_agreement', 'Enrollment Agreement', 1, 15),
    ('req_coe_refund', 'COE', 'refund_policy', 'Refund Policy', 1, 15),
    ('req_coe_program', 'COE', 'program_outline', 'Program Outline', 1, 12),
    ('req_coe_faculty', 'COE', 'faculty_credentials', 'Faculty Credentials', 1, 12),
    ('req_coe_handbook', 'COE', 'student_handbook', 'Student Handbook', 1, 10);

-- Readiness cache marker (for invalidation)
ALTER TABLE institutions ADD COLUMN readiness_stale INTEGER DEFAULT 1;
ALTER TABLE institutions ADD COLUMN readiness_computed_at TEXT;
