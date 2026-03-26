-- Phase 25: Context-Sensitive Search
-- FTS5 indexes with scope columns for contextual search

PRAGMA foreign_keys = ON;

-- =============================================================================
-- Document Text FTS5 (for searching document chunk content)
-- =============================================================================

-- Create FTS5 table for document chunk text with scope columns
-- Uses external content from document_chunks table
CREATE VIRTUAL TABLE IF NOT EXISTS document_text_fts USING fts5(
    content,
    section_header,
    document_id UNINDEXED,
    institution_id UNINDEXED,
    program_id UNINDEXED,
    tokenize='porter unicode61'
);

-- Populate from existing document_chunks joined with documents for scope
INSERT OR IGNORE INTO document_text_fts(rowid, content, section_header, document_id, institution_id, program_id)
SELECT
    dc.rowid,
    COALESCE(dc.redacted_text_path, ''),  -- Text is stored in file, use path as placeholder
    COALESCE(dc.section_header, ''),
    dc.document_id,
    d.institution_id,
    d.program_id
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id;

-- Note: For full content search, app layer reads text from redacted_text_path files
-- This FTS5 table enables scope filtering; semantic search via ChromaDB handles content matching

-- =============================================================================
-- Evidence FTS5 (for searching evidence references)
-- =============================================================================

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
    snippet_text,
    document_id UNINDEXED,
    finding_id UNINDEXED,
    institution_id UNINDEXED,
    tokenize='porter unicode61'
);

-- Populate from existing evidence_refs joined with audit chain for scope
INSERT OR IGNORE INTO evidence_fts(rowid, snippet_text, document_id, finding_id, institution_id)
SELECT
    er.rowid,
    COALESCE(er.snippet_text, ''),
    er.document_id,
    er.finding_id,
    ar.institution_id
FROM evidence_refs er
JOIN audit_findings af ON er.finding_id = af.id
JOIN audit_runs ar ON af.audit_run_id = ar.id;

-- Triggers to keep evidence_fts in sync
CREATE TRIGGER IF NOT EXISTS evidence_fts_insert AFTER INSERT ON evidence_refs BEGIN
    INSERT INTO evidence_fts(rowid, snippet_text, document_id, finding_id, institution_id)
    SELECT
        NEW.rowid,
        COALESCE(NEW.snippet_text, ''),
        NEW.document_id,
        NEW.finding_id,
        ar.institution_id
    FROM audit_findings af
    JOIN audit_runs ar ON af.audit_run_id = ar.id
    WHERE af.id = NEW.finding_id;
END;

CREATE TRIGGER IF NOT EXISTS evidence_fts_update AFTER UPDATE ON evidence_refs BEGIN
    DELETE FROM evidence_fts WHERE rowid = OLD.rowid;
    INSERT INTO evidence_fts(rowid, snippet_text, document_id, finding_id, institution_id)
    SELECT
        NEW.rowid,
        COALESCE(NEW.snippet_text, ''),
        NEW.document_id,
        NEW.finding_id,
        ar.institution_id
    FROM audit_findings af
    JOIN audit_runs ar ON af.audit_run_id = ar.id
    WHERE af.id = NEW.finding_id;
END;

CREATE TRIGGER IF NOT EXISTS evidence_fts_delete AFTER DELETE ON evidence_refs BEGIN
    DELETE FROM evidence_fts WHERE rowid = OLD.rowid;
END;

-- =============================================================================
-- Scope-aware indexes on existing tables
-- =============================================================================

-- Add index on standards for accreditor scoping (if not exists)
CREATE INDEX IF NOT EXISTS idx_standards_accreditor ON standards(accreditor_id);

-- Add compound index on findings for institution scoping
CREATE INDEX IF NOT EXISTS idx_findings_institution ON audit_findings(audit_run_id);

-- =============================================================================
-- Contextual search history (extends site_visit_searches)
-- =============================================================================

-- Add scope columns to track contextual searches
ALTER TABLE site_visit_searches ADD COLUMN scope TEXT DEFAULT 'global';
ALTER TABLE site_visit_searches ADD COLUMN program_id TEXT;
ALTER TABLE site_visit_searches ADD COLUMN document_id TEXT;

CREATE INDEX IF NOT EXISTS idx_site_visit_scope ON site_visit_searches(scope);
