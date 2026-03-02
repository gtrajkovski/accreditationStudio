-- 0007_submissions.sql
-- Submission packets and items

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS submission_packets (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    program_id TEXT,
    packet_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    due_date TEXT,
    submitted_at TEXT,
    docx_path TEXT,
    pdf_path TEXT,
    zip_path TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS packet_items (
    id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    title TEXT,
    description TEXT,
    ref TEXT NOT NULL DEFAULT '{}',
    file_path TEXT,
    order_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (packet_id) REFERENCES submission_packets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS packet_checklist_mappings (
    id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL,
    checklist_id TEXT NOT NULL,
    FOREIGN KEY (packet_id) REFERENCES submission_packets(id) ON DELETE CASCADE,
    FOREIGN KEY (checklist_id) REFERENCES checklists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deadlines (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    packet_id TEXT,
    reminder_days TEXT NOT NULL DEFAULT '[30, 14, 7, 1]',
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (packet_id) REFERENCES submission_packets(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_packets_institution ON submission_packets(institution_id);
CREATE INDEX IF NOT EXISTS idx_packets_status ON submission_packets(status);
CREATE INDEX IF NOT EXISTS idx_packets_type ON submission_packets(packet_type);
CREATE INDEX IF NOT EXISTS idx_packet_items_packet ON packet_items(packet_id);
CREATE INDEX IF NOT EXISTS idx_packet_items_order ON packet_items(order_index);
CREATE INDEX IF NOT EXISTS idx_deadlines_institution ON deadlines(institution_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_due_date ON deadlines(due_date);
CREATE INDEX IF NOT EXISTS idx_deadlines_status ON deadlines(status);
