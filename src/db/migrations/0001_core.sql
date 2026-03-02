-- 0001_core.sql
-- Core tables: users, institutions, programs, memberships

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    locale TEXT NOT NULL DEFAULT 'en-US',
    theme_preference TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT,
    accreditor_primary TEXT,
    timezone TEXT NOT NULL DEFAULT 'America/New_York',
    default_locale TEXT NOT NULL DEFAULT 'en-US',
    supported_locales TEXT NOT NULL DEFAULT '["en-US"]',
    theme_preference TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS programs (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    name TEXT NOT NULL,
    credential_level TEXT,
    delivery_modes TEXT NOT NULL DEFAULT '[]',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS institution_memberships (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_programs_institution_id ON programs(institution_id);
CREATE INDEX IF NOT EXISTS idx_memberships_institution_id ON institution_memberships(institution_id);
CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON institution_memberships(user_id);
