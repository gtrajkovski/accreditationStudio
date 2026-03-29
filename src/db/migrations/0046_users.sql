-- 0046_users.sql
-- Add authentication columns to existing users table
-- Create sessions and password_resets tables

-- Add password_hash column to users
ALTER TABLE users ADD COLUMN password_hash TEXT;

-- Add name column (map from display_name if present)
ALTER TABLE users ADD COLUMN name TEXT;

-- Add role column with default
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'viewer';

-- Add institution_id column
ALTER TABLE users ADD COLUMN institution_id TEXT REFERENCES institutions(id);

-- Add is_active column
ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;

-- Add last_login column
ALTER TABLE users ADD COLUMN last_login TEXT;

-- Update name from display_name where it exists
UPDATE users SET name = display_name WHERE display_name IS NOT NULL AND name IS NULL;

-- Create sessions table for token-based auth
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create password_resets table
CREATE TABLE IF NOT EXISTS password_resets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_institution ON users(institution_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token);
