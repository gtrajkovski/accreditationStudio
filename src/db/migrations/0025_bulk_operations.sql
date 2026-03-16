-- 0025_bulk_operations.sql
-- Add batch operations and batch items tables for bulk audit/remediation tracking

PRAGMA foreign_keys = ON;

-- Batch operations table
CREATE TABLE IF NOT EXISTS batch_operations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK(operation_type IN ('audit', 'remediation')),
    document_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    estimated_cost REAL,
    actual_cost REAL,
    concurrency INTEGER DEFAULT 3 CHECK(concurrency BETWEEN 1 AND 5),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'cancelled', 'failed')),
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    parent_batch_id TEXT,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_batch_id) REFERENCES batch_operations(id) ON DELETE SET NULL
);

-- Batch items table
CREATE TABLE IF NOT EXISTS batch_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    document_name TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    task_id TEXT,
    result_path TEXT,
    error TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    findings_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (batch_id) REFERENCES batch_operations(id) ON DELETE CASCADE
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_batch_operations_institution
    ON batch_operations(institution_id);

CREATE INDEX IF NOT EXISTS idx_batch_operations_status
    ON batch_operations(status);

CREATE INDEX IF NOT EXISTS idx_batch_items_batch
    ON batch_items(batch_id);

CREATE INDEX IF NOT EXISTS idx_batch_items_status
    ON batch_items(status);
