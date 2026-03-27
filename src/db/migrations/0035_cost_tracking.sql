-- Migration: Cost Tracking
-- Phase 29 Plan 02
-- Creates tables for AI cost tracking and budget management

-- Cost tracking for AI API calls
CREATE TABLE IF NOT EXISTS ai_cost_log (
    id TEXT PRIMARY KEY,
    institution_id TEXT,
    agent_type TEXT,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    operation TEXT,  -- 'audit', 'remediation', 'chat', 'pii_detection', etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_cost_log_institution ON ai_cost_log(institution_id);
CREATE INDEX idx_cost_log_agent ON ai_cost_log(agent_type);
CREATE INDEX idx_cost_log_created ON ai_cost_log(created_at);

-- Budget configuration per institution
CREATE TABLE IF NOT EXISTS ai_budgets (
    institution_id TEXT PRIMARY KEY,
    monthly_budget_usd REAL DEFAULT 100.0,
    alert_threshold REAL DEFAULT 0.8,  -- Alert at 80% of budget
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
