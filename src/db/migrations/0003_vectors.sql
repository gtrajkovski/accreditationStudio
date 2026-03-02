-- 0003_vectors.sql
-- Vector storage: document chunks and embeddings

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    section_header TEXT,
    language TEXT NOT NULL DEFAULT 'en-US',
    redacted_text_path TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON document_chunks(section_header);

-- Embeddings table as stable interface for vector storage
-- Vector operations will use sqlite-vss extension when available
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL DEFAULT 384,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE
);

-- Virtual table for vector similarity search (requires sqlite-vss)
-- This will be created separately when sqlite-vss is loaded
-- CREATE VIRTUAL TABLE IF NOT EXISTS vss_chunks USING vss0(embedding(384));
