-- 0023_portfolios.sql
-- Multi-Institution Mode: Portfolio management for consultants

PRAGMA foreign_keys = ON;

-- Portfolios: Named groups of institutions
CREATE TABLE IF NOT EXISTS portfolios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#C9A84C',  -- Gold accent default
    icon TEXT DEFAULT 'folder',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Portfolio membership: which institutions belong to which portfolios
-- An institution can belong to multiple portfolios
CREATE TABLE IF NOT EXISTS portfolio_institutions (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, institution_id)
);

-- Portfolio readiness snapshots: aggregate metrics over time
CREATE TABLE IF NOT EXISTS portfolio_readiness_snapshots (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    avg_score INTEGER NOT NULL DEFAULT 0,
    min_score INTEGER NOT NULL DEFAULT 0,
    max_score INTEGER NOT NULL DEFAULT 0,
    institution_count INTEGER NOT NULL DEFAULT 0,
    at_risk_count INTEGER NOT NULL DEFAULT 0,    -- score < 60
    ready_count INTEGER NOT NULL DEFAULT 0,       -- score >= 80
    breakdown_json TEXT NOT NULL DEFAULT '{}',   -- by accreditor, by score range
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);

-- Recent institution access: for quick-switcher "Recent" section
CREATE TABLE IF NOT EXISTS recent_institutions (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL UNIQUE,
    accessed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_portfolio_inst_portfolio
    ON portfolio_institutions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_inst_institution
    ON portfolio_institutions(institution_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_inst_sort
    ON portfolio_institutions(portfolio_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_portfolio
    ON portfolio_readiness_snapshots(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_created
    ON portfolio_readiness_snapshots(portfolio_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recent_institutions_time
    ON recent_institutions(accessed_at DESC);

-- Create default "All Institutions" portfolio
INSERT OR IGNORE INTO portfolios (id, name, description, sort_order)
VALUES ('portfolio_all', 'All Institutions', 'Default portfolio containing all institutions', -1);
