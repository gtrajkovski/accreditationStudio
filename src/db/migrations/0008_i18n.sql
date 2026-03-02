-- 0008_i18n.sql
-- Internationalization: glossaries, document translations, chunk translations

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS terminology_glossaries (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    locale TEXT NOT NULL,
    entries TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    UNIQUE (institution_id, locale)
);

CREATE TABLE IF NOT EXISTS document_translations (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    translated_text_path TEXT,
    translated_structured_json_path TEXT,
    quality_score REAL,
    quality_flags TEXT NOT NULL DEFAULT '[]',
    translator_model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE (document_id, target_language)
);

CREATE TABLE IF NOT EXISTS document_chunk_translations (
    id TEXT PRIMARY KEY,
    document_chunk_id TEXT NOT NULL,
    target_language TEXT NOT NULL,
    translated_text TEXT,
    translated_text_path TEXT,
    quality_score REAL,
    quality_flags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (document_chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE,
    UNIQUE (document_chunk_id, target_language)
);

CREATE TABLE IF NOT EXISTS ui_translations (
    id TEXT PRIMARY KEY,
    locale TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (locale, key)
);

CREATE INDEX IF NOT EXISTS idx_glossaries_institution ON terminology_glossaries(institution_id);
CREATE INDEX IF NOT EXISTS idx_glossaries_locale ON terminology_glossaries(locale);
CREATE INDEX IF NOT EXISTS idx_doc_translations_doc_id ON document_translations(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_translations_status ON document_translations(status);
CREATE INDEX IF NOT EXISTS idx_doc_translations_target ON document_translations(target_language);
CREATE INDEX IF NOT EXISTS idx_chunk_translations_chunk ON document_chunk_translations(document_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_translations_lang ON document_chunk_translations(target_language);
CREATE INDEX IF NOT EXISTS idx_ui_translations_locale ON ui_translations(locale);
