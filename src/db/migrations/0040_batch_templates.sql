-- Phase 9-05: Enhanced Batch Processing - Templates
-- Migration: 0040_batch_templates.sql

CREATE TABLE IF NOT EXISTS batch_templates (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    operation_type TEXT NOT NULL,
    document_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of document IDs
    concurrency INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Index for listing templates by institution
CREATE INDEX IF NOT EXISTS idx_batch_templates_institution
ON batch_templates(institution_id, created_at DESC);

-- Index for filtering by operation type
CREATE INDEX IF NOT EXISTS idx_batch_templates_operation
ON batch_templates(institution_id, operation_type);
