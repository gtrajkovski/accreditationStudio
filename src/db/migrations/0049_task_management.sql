-- Migration 0049: Task Management
-- Phase 44: Task Assignment & Deadline Management

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'normal',
    assigned_to TEXT,
    assigned_by TEXT,
    due_date TEXT,
    completed_at TEXT,
    source_type TEXT,
    source_id TEXT,
    category TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    -- Note: FKs intentionally omitted - tasks persist after users/institutions deleted
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    user_id TEXT,
    user_name TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
    -- user_id FK omitted - comments persist after users deleted
);

CREATE INDEX IF NOT EXISTS idx_tasks_institution ON tasks(institution_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id);
