-- 0011_autopilot.sql
-- Autopilot scheduler: job runs, configuration, history

PRAGMA foreign_keys = ON;

-- Autopilot configuration per institution
CREATE TABLE IF NOT EXISTS autopilot_config (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 0,
    schedule_hour INTEGER NOT NULL DEFAULT 2,
    schedule_minute INTEGER NOT NULL DEFAULT 0,
    run_reindex INTEGER NOT NULL DEFAULT 1,
    run_consistency INTEGER NOT NULL DEFAULT 1,
    run_audit INTEGER NOT NULL DEFAULT 0,
    run_readiness INTEGER NOT NULL DEFAULT 1,
    notify_on_complete INTEGER NOT NULL DEFAULT 1,
    notify_on_error INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Job run history
CREATE TABLE IF NOT EXISTS autopilot_runs (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL DEFAULT 'scheduled',
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    duration_seconds INTEGER,

    -- Job results
    docs_indexed INTEGER DEFAULT 0,
    docs_failed INTEGER DEFAULT 0,
    consistency_issues_found INTEGER DEFAULT 0,
    consistency_issues_resolved INTEGER DEFAULT 0,
    audit_findings_count INTEGER DEFAULT 0,
    readiness_score_before INTEGER,
    readiness_score_after INTEGER,

    -- Error tracking
    error_message TEXT,
    error_details TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Individual task results within a run
CREATE TABLE IF NOT EXISTS autopilot_run_tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    result_summary TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES autopilot_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_autopilot_config_institution ON autopilot_config(institution_id);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_institution ON autopilot_runs(institution_id);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_status ON autopilot_runs(status);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_created ON autopilot_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_autopilot_run_tasks_run ON autopilot_run_tasks(run_id);
