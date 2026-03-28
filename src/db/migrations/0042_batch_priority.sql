-- Phase 9-05: Enhanced Batch Processing - Priority Queue
-- Migration: 0042_batch_priority.sql

-- Add priority_level column to batch_operations
-- Values: 1=critical, 2=high, 3=normal, 4=low
ALTER TABLE batch_operations ADD COLUMN priority_level INTEGER DEFAULT 3;

-- Add sla_deadline for critical batches (optional deadline timestamp)
ALTER TABLE batch_operations ADD COLUMN sla_deadline TEXT;

-- Index for priority-based queue ordering
CREATE INDEX IF NOT EXISTS idx_batch_operations_priority
ON batch_operations(status, priority_level, created_at);

-- Update existing records to have normal priority
UPDATE batch_operations SET priority_level = 3 WHERE priority_level IS NULL;
