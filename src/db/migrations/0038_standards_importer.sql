-- Migration: standards_importer
-- Date: 2026-03-27
-- Description: Standards importer tracking tables

PRAGMA foreign_keys = ON;

-- Import history records
CREATE TABLE IF NOT EXISTS standards_imports (
    id TEXT PRIMARY KEY,
    institution_id TEXT,
    accreditor_code TEXT NOT NULL,

    -- Source info
    source_type TEXT NOT NULL,       -- pdf, excel, csv, text, web
    source_name TEXT,                -- Original filename or URL
    source_hash TEXT,                -- SHA256 of source content (first 16 chars)

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, extracting, parsing, validating, ready, imported, failed

    -- Results
    library_id TEXT,                 -- ID of created StandardsLibrary (if imported)
    sections_detected INTEGER DEFAULT 0,
    checklist_items_detected INTEGER DEFAULT 0,
    quality_score REAL DEFAULT 0.0,

    -- Validation
    validation_errors TEXT,          -- JSON array of ValidationIssue
    validation_warnings TEXT,        -- JSON array

    -- User mappings applied
    user_mappings TEXT,              -- JSON of user adjustments

    -- Timing
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER DEFAULT 0,

    -- Metadata
    imported_by TEXT DEFAULT 'user',
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE SET NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_std_imports_institution ON standards_imports(institution_id);
CREATE INDEX IF NOT EXISTS idx_std_imports_status ON standards_imports(status);
CREATE INDEX IF NOT EXISTS idx_std_imports_accreditor ON standards_imports(accreditor_code);
CREATE INDEX IF NOT EXISTS idx_std_imports_created ON standards_imports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_std_imports_library ON standards_imports(library_id);
CREATE INDEX IF NOT EXISTS idx_std_imports_source_hash ON standards_imports(source_hash);
