-- 0032_standards_harvester.sql
-- Standards Harvester: Track standards versions with SHA256 hashing

PRAGMA foreign_keys = ON;

-- Standards versions table
CREATE TABLE IF NOT EXISTS standards_versions (
    id TEXT PRIMARY KEY,
    accreditor_code TEXT NOT NULL,
    version_date TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'web_scrape', 'pdf_parse', 'manual_upload'
    source_url TEXT,
    extracted_text_length INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sv_accreditor ON standards_versions(accreditor_code);
CREATE INDEX IF NOT EXISTS idx_sv_accreditor_date ON standards_versions(accreditor_code, version_date DESC);
CREATE INDEX IF NOT EXISTS idx_sv_hash ON standards_versions(content_hash);
