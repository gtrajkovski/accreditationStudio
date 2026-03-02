-- 0002_docs.sql
-- Document management: documents, versions, parses

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    program_id TEXT,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_language TEXT NOT NULL DEFAULT 'en-US',
    status TEXT NOT NULL DEFAULT 'uploaded',
    original_file_path TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    page_count INTEGER,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    version_type TEXT NOT NULL,
    label TEXT,
    file_path TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_parses (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extracted_text_path TEXT NOT NULL,
    structured_json_path TEXT,
    pii_redacted_text_path TEXT NOT NULL,
    parse_warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_institution_id ON documents(institution_id);
CREATE INDEX IF NOT EXISTS idx_documents_program_id ON documents(program_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_parses_document_id ON document_parses(document_id);
