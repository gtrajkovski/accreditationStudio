-- Phase 7: Visit Prep, Interview, SER Drafting
-- Migration for interview prep, mock evaluations, and SER drafts

-- Interview prep session tracking
CREATE TABLE IF NOT EXISTS interview_prep_sessions (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    role TEXT NOT NULL,
    program_id TEXT,
    status TEXT DEFAULT 'pending',
    document_path TEXT,
    questions_count INTEGER DEFAULT 0,
    talking_points_count INTEGER DEFAULT 0,
    red_flags_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_interview_prep_institution
    ON interview_prep_sessions(institution_id);
CREATE INDEX IF NOT EXISTS idx_interview_prep_role
    ON interview_prep_sessions(role);

-- Mock evaluation history
CREATE TABLE IF NOT EXISTS mock_evaluations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    accreditor_code TEXT,
    readiness_score REAL,
    area_scores TEXT,  -- JSON: {"documents": 85, "compliance": 72, ...}
    predicted_findings TEXT,  -- JSON array of predicted findings
    strengths TEXT,  -- JSON array
    concerns TEXT,  -- JSON array
    evaluator_notes TEXT,
    created_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_mock_eval_institution
    ON mock_evaluations(institution_id);
CREATE INDEX IF NOT EXISTS idx_mock_eval_date
    ON mock_evaluations(created_at);

-- SER (Self-Evaluation Report) draft tracking
CREATE TABLE IF NOT EXISTS ser_drafts (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    accreditor_code TEXT,
    writing_mode TEXT DEFAULT 'draft',  -- draft, submission
    sections TEXT,  -- JSON: section data
    total_sections INTEGER DEFAULT 0,
    sections_complete INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',  -- in_progress, draft_complete, final
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_ser_draft_institution
    ON ser_drafts(institution_id);
CREATE INDEX IF NOT EXISTS idx_ser_draft_status
    ON ser_drafts(status);

-- SER section tracking (for granular progress)
CREATE TABLE IF NOT EXISTS ser_sections (
    id TEXT PRIMARY KEY,
    ser_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    title TEXT,
    content TEXT,
    word_count INTEGER DEFAULT 0,
    citations TEXT,  -- JSON array of citation references
    placeholders TEXT,  -- JSON array of unfilled placeholders
    is_complete INTEGER DEFAULT 0,
    last_generated_at TEXT,
    FOREIGN KEY (ser_id) REFERENCES ser_drafts(id)
);

CREATE INDEX IF NOT EXISTS idx_ser_section_ser
    ON ser_sections(ser_id);

-- Checklist validation history
CREATE TABLE IF NOT EXISTS checklist_validations (
    id TEXT PRIMARY KEY,
    checklist_id TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    items_validated INTEGER DEFAULT 0,
    items_verified INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    items_uncertain INTEGER DEFAULT 0,
    validation_mode TEXT,  -- strict, semantic
    results TEXT,  -- JSON array of validation results
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_checklist_validation_checklist
    ON checklist_validations(checklist_id);

-- Visit prep document exports
CREATE TABLE IF NOT EXISTS visit_prep_exports (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    export_type TEXT,  -- interview_prep, ser, checklist
    document_id TEXT,  -- reference to source document
    format TEXT,  -- docx, pdf, json
    file_path TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_visit_export_institution
    ON visit_prep_exports(institution_id);
