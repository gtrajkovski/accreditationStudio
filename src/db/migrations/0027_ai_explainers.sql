-- Migration 0027: AI Explainers
-- Adds standard_explanations table for caching plain-English interpretations

CREATE TABLE IF NOT EXISTS standard_explanations (
    id TEXT PRIMARY KEY,
    standard_id TEXT NOT NULL,
    accreditor TEXT NOT NULL,
    plain_english TEXT NOT NULL,
    required_evidence TEXT NOT NULL,  -- JSON array of evidence types
    common_mistakes TEXT,             -- JSON array of common mistakes
    regulatory_context TEXT,          -- Why this standard matters
    confidence REAL DEFAULT 0.85,
    version TEXT NOT NULL,            -- Hash of standard body for cache invalidation
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_standard_explanations_standard_version
ON standard_explanations(standard_id, version);

CREATE INDEX IF NOT EXISTS idx_standard_explanations_accreditor
ON standard_explanations(accreditor);
