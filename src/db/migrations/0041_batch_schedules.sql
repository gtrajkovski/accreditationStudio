-- Phase 9-05: Enhanced Batch Processing - Scheduling
-- Migration: 0041_batch_schedules.sql

CREATE TABLE IF NOT EXISTS batch_schedules (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    next_run TEXT,
    last_run TEXT,
    last_batch_id TEXT,
    status TEXT DEFAULT 'active',  -- active, paused, deleted
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES batch_templates(id) ON DELETE CASCADE
);

-- Index for listing schedules by institution
CREATE INDEX IF NOT EXISTS idx_batch_schedules_institution
ON batch_schedules(institution_id, status);

-- Index for finding active schedules
CREATE INDEX IF NOT EXISTS idx_batch_schedules_active
ON batch_schedules(status, next_run);
