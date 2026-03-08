-- Phase 8: Post-Visit + Ongoing
-- Migration for team report responses, compliance calendar, document reviews

-- Team reports received from accreditors
CREATE TABLE IF NOT EXISTS team_reports (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    accreditor_code TEXT,
    visit_date TEXT,
    report_date TEXT,
    team_chair TEXT,
    overall_recommendation TEXT,  -- reaffirm, defer, warning, probation, withdraw
    response_due_date TEXT,
    commendations TEXT,  -- JSON array
    status TEXT DEFAULT 'received',  -- received, analyzing, responding, submitted
    document_path TEXT,  -- Path to original report document
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_team_report_institution
    ON team_reports(institution_id);
CREATE INDEX IF NOT EXISTS idx_team_report_status
    ON team_reports(status);
CREATE INDEX IF NOT EXISTS idx_team_report_due_date
    ON team_reports(response_due_date);

-- Findings extracted from team reports
CREATE TABLE IF NOT EXISTS team_report_findings (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    finding_number TEXT,
    standard_reference TEXT,
    severity TEXT DEFAULT 'moderate',  -- critical, moderate, minor, observation
    finding_text TEXT,
    requirement_text TEXT,
    evidence_cited TEXT,  -- JSON array
    response_deadline TEXT,
    response_status TEXT DEFAULT 'pending',  -- pending, drafted, reviewed, submitted
    response_priority INTEGER DEFAULT 0,
    created_at TEXT,
    FOREIGN KEY (report_id) REFERENCES team_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_finding_report
    ON team_report_findings(report_id);
CREATE INDEX IF NOT EXISTS idx_finding_severity
    ON team_report_findings(severity);
CREATE INDEX IF NOT EXISTS idx_finding_status
    ON team_report_findings(response_status);

-- Institution responses to findings
CREATE TABLE IF NOT EXISTS finding_responses (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    response_text TEXT,
    evidence_refs TEXT,  -- JSON array of evidence references
    action_items TEXT,  -- JSON array of action items
    word_count INTEGER DEFAULT 0,
    ai_confidence REAL DEFAULT 0.0,
    requires_review INTEGER DEFAULT 1,
    reviewer_id TEXT,
    reviewer_notes TEXT,
    status TEXT DEFAULT 'draft',  -- draft, reviewed, approved, submitted
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (finding_id) REFERENCES team_report_findings(id)
);

CREATE INDEX IF NOT EXISTS idx_response_finding
    ON finding_responses(finding_id);
CREATE INDEX IF NOT EXISTS idx_response_status
    ON finding_responses(status);

-- Response packets for submission
CREATE TABLE IF NOT EXISTS response_packets (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    packet_name TEXT,
    format TEXT DEFAULT 'docx',  -- docx, pdf, json
    file_path TEXT,
    findings_count INTEGER DEFAULT 0,
    responses_included INTEGER DEFAULT 0,
    include_evidence INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft',  -- draft, final, submitted
    submitted_at TEXT,
    created_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id),
    FOREIGN KEY (report_id) REFERENCES team_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_packet_institution
    ON response_packets(institution_id);
CREATE INDEX IF NOT EXISTS idx_packet_report
    ON response_packets(report_id);

-- Compliance calendar events
CREATE TABLE IF NOT EXISTS compliance_calendar (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- deadline, renewal, report_due, visit, review
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT NOT NULL,
    reminder_days INTEGER DEFAULT 30,  -- Days before to send reminder
    recurrence TEXT,  -- none, annual, semi-annual, quarterly
    accreditor_code TEXT,
    related_entity_type TEXT,  -- team_report, finding, document
    related_entity_id TEXT,
    status TEXT DEFAULT 'pending',  -- pending, reminded, completed, overdue
    completed_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_institution
    ON compliance_calendar(institution_id);
CREATE INDEX IF NOT EXISTS idx_calendar_due_date
    ON compliance_calendar(due_date);
CREATE INDEX IF NOT EXISTS idx_calendar_status
    ON compliance_calendar(status);
CREATE INDEX IF NOT EXISTS idx_calendar_type
    ON compliance_calendar(event_type);

-- Document review schedule
CREATE TABLE IF NOT EXISTS document_reviews (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_type TEXT,
    review_cycle TEXT DEFAULT 'annual',  -- annual, semi-annual, quarterly, monthly
    last_reviewed_at TEXT,
    next_review_date TEXT,
    reviewer_id TEXT,
    reviewer_notes TEXT,
    status TEXT DEFAULT 'scheduled',  -- scheduled, due, overdue, completed
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_doc_review_institution
    ON document_reviews(institution_id);
CREATE INDEX IF NOT EXISTS idx_doc_review_next_date
    ON document_reviews(next_review_date);
CREATE INDEX IF NOT EXISTS idx_doc_review_status
    ON document_reviews(status);
