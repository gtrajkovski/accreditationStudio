-- Onboarding progress tracking

CREATE TABLE IF NOT EXISTS onboarding_progress (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL UNIQUE,
    current_step INTEGER NOT NULL DEFAULT 1,
    completed INTEGER NOT NULL DEFAULT 0,
    profile_complete INTEGER NOT NULL DEFAULT 0,
    documents_uploaded INTEGER NOT NULL DEFAULT 0,
    initial_audit_run INTEGER NOT NULL DEFAULT 0,
    review_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id)
);

CREATE INDEX IF NOT EXISTS idx_onboarding_institution ON onboarding_progress(institution_id);
