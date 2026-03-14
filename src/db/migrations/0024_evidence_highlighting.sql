-- 0024_evidence_highlighting.sql
-- Add position tracking to evidence_refs for precise text highlighting

PRAGMA foreign_keys = ON;

-- Add offset columns for character-level positioning
ALTER TABLE evidence_refs ADD COLUMN start_offset INTEGER;
ALTER TABLE evidence_refs ADD COLUMN end_offset INTEGER;

-- Index for efficient document + page queries
CREATE INDEX IF NOT EXISTS idx_evidence_refs_doc_page
    ON evidence_refs(document_id, page);
