-- Migration: Accreditor Packages
-- Created: 2026-03-29
-- Description: Add accreditor packages table for modular accreditor support

CREATE TABLE IF NOT EXISTS accreditor_packages (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- institutional, programmatic
    scope TEXT NOT NULL,  -- national, regional
    standards_url TEXT,
    fetch_cadence TEXT DEFAULT 'monthly',
    last_fetched TEXT,
    manifest_hash TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_packages_code ON accreditor_packages(code);
CREATE INDEX IF NOT EXISTS idx_packages_enabled ON accreditor_packages(enabled);
