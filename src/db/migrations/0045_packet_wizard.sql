-- Migration 0045: Packet Wizard Sessions
-- Created for Phase 39: Packet Studio Wizard
--
-- Stores wizard session state for the 5-step submission packet creation workflow.
-- Steps: 1. Submission Type, 2. Standards, 3. Evidence, 4. Narrative, 5. Preview

CREATE TABLE IF NOT EXISTS packet_wizard_sessions (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    packet_id TEXT,  -- links to packets table when created
    current_step INTEGER DEFAULT 1,
    step_data TEXT NOT NULL DEFAULT '{}',  -- JSON per-step data
    status TEXT NOT NULL DEFAULT 'draft',  -- draft, complete, abandoned
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    created_by TEXT,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wizard_inst ON packet_wizard_sessions(institution_id);
CREATE INDEX IF NOT EXISTS idx_wizard_status ON packet_wizard_sessions(status);
