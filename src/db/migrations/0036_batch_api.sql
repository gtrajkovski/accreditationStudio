-- 0036_batch_api.sql
-- Add Anthropic Batch API integration columns

PRAGMA foreign_keys = ON;

-- Add columns for Anthropic batch tracking
ALTER TABLE batch_operations ADD COLUMN anthropic_batch_id TEXT;
ALTER TABLE batch_operations ADD COLUMN batch_mode TEXT DEFAULT 'realtime' CHECK(batch_mode IN ('realtime', 'async'));
ALTER TABLE batch_operations ADD COLUMN anthropic_status TEXT;  -- in_progress, ended, canceling
ALTER TABLE batch_operations ADD COLUMN results_url TEXT;
ALTER TABLE batch_operations ADD COLUMN expires_at TEXT;

-- Add index for batch_id lookup
CREATE INDEX IF NOT EXISTS idx_batch_operations_anthropic_id
    ON batch_operations(anthropic_batch_id);

-- Update batch_items for Anthropic custom_id mapping
ALTER TABLE batch_items ADD COLUMN anthropic_custom_id TEXT;
