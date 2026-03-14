-- Phase 10: Site Visit Mode
-- Fast unified search for use during accreditor site visits

-- Search history for auditor continuity
CREATE TABLE IF NOT EXISTS site_visit_searches (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    query TEXT NOT NULL,
    filters_json TEXT NOT NULL DEFAULT '{}',
    sources_searched TEXT NOT NULL DEFAULT '[]',
    result_count INTEGER NOT NULL DEFAULT 0,
    query_time_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_site_visit_searches_inst
    ON site_visit_searches(institution_id);
CREATE INDEX IF NOT EXISTS idx_site_visit_searches_time
    ON site_visit_searches(created_at DESC);

-- Saved/favorite searches for quick access
CREATE TABLE IF NOT EXISTS site_visit_saved_searches (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    query TEXT NOT NULL,
    filters_json TEXT NOT NULL DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_inst
    ON site_visit_saved_searches(institution_id);

-- Full-text search virtual table for standards (improves search speed)
CREATE VIRTUAL TABLE IF NOT EXISTS standards_fts USING fts5(
    standard_code,
    title,
    body_text,
    content='standards',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync with standards table
CREATE TRIGGER IF NOT EXISTS standards_fts_insert AFTER INSERT ON standards BEGIN
    INSERT INTO standards_fts(rowid, standard_code, title, body_text)
    VALUES (NEW.rowid, NEW.standard_code, NEW.title, NEW.body_text);
END;

CREATE TRIGGER IF NOT EXISTS standards_fts_update AFTER UPDATE ON standards BEGIN
    DELETE FROM standards_fts WHERE rowid = OLD.rowid;
    INSERT INTO standards_fts(rowid, standard_code, title, body_text)
    VALUES (NEW.rowid, NEW.standard_code, NEW.title, NEW.body_text);
END;

CREATE TRIGGER IF NOT EXISTS standards_fts_delete AFTER DELETE ON standards BEGIN
    DELETE FROM standards_fts WHERE rowid = OLD.rowid;
END;

-- Full-text search virtual table for audit findings
CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
    summary,
    recommendation,
    content='audit_findings',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS findings_fts_insert AFTER INSERT ON audit_findings BEGIN
    INSERT INTO findings_fts(rowid, summary, recommendation)
    VALUES (NEW.rowid, NEW.summary, NEW.recommendation);
END;

CREATE TRIGGER IF NOT EXISTS findings_fts_update AFTER UPDATE ON audit_findings BEGIN
    DELETE FROM findings_fts WHERE rowid = OLD.rowid;
    INSERT INTO findings_fts(rowid, summary, recommendation)
    VALUES (NEW.rowid, NEW.summary, NEW.recommendation);
END;

CREATE TRIGGER IF NOT EXISTS findings_fts_delete AFTER DELETE ON audit_findings BEGIN
    DELETE FROM findings_fts WHERE rowid = OLD.rowid;
END;

-- Rebuild FTS indexes from existing data
INSERT OR IGNORE INTO standards_fts(rowid, standard_code, title, body_text)
SELECT rowid, standard_code, title, body_text FROM standards;

INSERT OR IGNORE INTO findings_fts(rowid, summary, recommendation)
SELECT rowid, summary, recommendation FROM audit_findings;
