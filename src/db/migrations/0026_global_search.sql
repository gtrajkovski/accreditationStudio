-- Migration 0026: Global Search Filter Presets
-- Phase: 13-search-enhancement
-- Description: Add filter_presets table for saving and reusing search filter combinations

CREATE TABLE IF NOT EXISTS filter_presets (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    filters_json TEXT NOT NULL,  -- JSON: {doc_types: [], compliance_status: [], date_range: {start, end}}
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    usage_count INTEGER DEFAULT 0,
    UNIQUE(institution_id, name),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_filter_presets_institution
ON filter_presets(institution_id);
