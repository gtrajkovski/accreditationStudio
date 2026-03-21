-- Migration 0029: Report Templates
-- Add custom report templates for customizable report generation
-- Available section IDs:
--   - readiness: Overall readiness scores
--   - findings_summary: Findings by severity table
--   - documents: Document counts and status
--   - top_standards: Standards with most findings
--   - charts: Visual charts (readiness breakdown, findings)

CREATE TABLE IF NOT EXISTS report_templates (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sections TEXT NOT NULL, -- JSON array of section IDs
    description TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_report_templates_institution ON report_templates(institution_id);
CREATE INDEX IF NOT EXISTS idx_report_templates_default ON report_templates(institution_id, is_default);
