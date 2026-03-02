-- 0004_standards.sql
-- Standards and regulatory: accreditors, standards, translations

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accreditors (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'institutional',
    scope TEXT,
    default_language TEXT NOT NULL DEFAULT 'en-US',
    website TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS standards (
    id TEXT PRIMARY KEY,
    accreditor_id TEXT NOT NULL,
    standard_code TEXT NOT NULL,
    title TEXT NOT NULL,
    body_text TEXT,
    body_path TEXT,
    parent_id TEXT,
    source_language TEXT NOT NULL DEFAULT 'en-US',
    effective_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (accreditor_id) REFERENCES accreditors(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES standards(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS standard_translations (
    id TEXT PRIMARY KEY,
    standard_id TEXT NOT NULL,
    target_language TEXT NOT NULL,
    title_translated TEXT,
    body_translated TEXT,
    body_translated_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE,
    UNIQUE (standard_id, target_language)
);

CREATE TABLE IF NOT EXISTS checklists (
    id TEXT PRIMARY KEY,
    accreditor_id TEXT NOT NULL,
    name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    version TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (accreditor_id) REFERENCES accreditors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id TEXT PRIMARY KEY,
    checklist_id TEXT NOT NULL,
    item_number TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS checklist_item_standard_refs (
    id TEXT PRIMARY KEY,
    checklist_item_id TEXT NOT NULL,
    standard_id TEXT NOT NULL,
    FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE,
    FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_standards_accreditor_id ON standards(accreditor_id);
CREATE INDEX IF NOT EXISTS idx_standards_parent_id ON standards(parent_id);
CREATE INDEX IF NOT EXISTS idx_standards_code ON standards(standard_code);
CREATE INDEX IF NOT EXISTS idx_standard_translations_lang ON standard_translations(target_language);
CREATE INDEX IF NOT EXISTS idx_checklists_accreditor ON checklists(accreditor_id);
CREATE INDEX IF NOT EXISTS idx_checklist_items_checklist ON checklist_items(checklist_id);
