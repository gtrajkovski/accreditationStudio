-- Migration 0027: Scheduled Reports
-- Add scheduled report generation with email delivery

CREATE TABLE IF NOT EXISTS report_schedules (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'compliance',
    schedule_type TEXT NOT NULL, -- 'daily', 'weekly', 'monthly'
    schedule_hour INTEGER NOT NULL DEFAULT 8,
    schedule_day_of_week INTEGER, -- 0-6 for weekly (0=Monday)
    schedule_day_of_month INTEGER, -- 1-31 for monthly
    recipients TEXT NOT NULL, -- JSON array of email addresses
    enabled BOOLEAN NOT NULL DEFAULT 1,
    last_run_at TEXT,
    last_status TEXT, -- 'success', 'failed'
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_report_schedules_institution ON report_schedules(institution_id);
CREATE INDEX IF NOT EXISTS idx_report_schedules_enabled ON report_schedules(enabled);

-- Email delivery log
CREATE TABLE IF NOT EXISTS email_delivery_log (
    id TEXT PRIMARY KEY,
    schedule_id TEXT,
    report_id TEXT,
    recipients TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL, -- 'sent', 'failed'
    error_message TEXT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (schedule_id) REFERENCES report_schedules(id),
    FOREIGN KEY (report_id) REFERENCES reports(id)
);

CREATE INDEX IF NOT EXISTS idx_email_delivery_schedule ON email_delivery_log(schedule_id);
CREATE INDEX IF NOT EXISTS idx_email_delivery_report ON email_delivery_log(report_id);
CREATE INDEX IF NOT EXISTS idx_email_delivery_status ON email_delivery_log(status);
