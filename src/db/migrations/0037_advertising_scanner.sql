-- Migration: advertising_scanner
-- Date: 2026-03-27
-- Description: Advertising/Marketing Compliance Scanner tables

PRAGMA foreign_keys = ON;

-- Main scan records
CREATE TABLE IF NOT EXISTS advertising_scans (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    scan_type TEXT NOT NULL,  -- 'url', 'document'
    source_url TEXT,          -- URL if web scan
    document_id TEXT,         -- Document ID if document scan
    title TEXT NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed

    -- Results Summary
    total_claims INTEGER DEFAULT 0,
    verified_claims INTEGER DEFAULT 0,
    unverified_claims INTEGER DEFAULT 0,
    violation_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,

    -- Scores
    compliance_score INTEGER DEFAULT 0,  -- 0-100
    risk_level TEXT,  -- low, medium, high, critical

    -- Content
    raw_content TEXT,         -- Extracted text
    content_hash TEXT,        -- SHA256 for change detection

    -- Timing
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER DEFAULT 0,

    -- Metadata
    scanned_by TEXT,          -- 'user' or 'scheduled'
    ai_model_used TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Individual findings from scan
CREATE TABLE IF NOT EXISTS advertising_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,

    -- Claim Info
    claim_type TEXT NOT NULL,  -- 'completion_rate', 'placement_rate', 'cost', 'program_length', etc.
    claim_text TEXT NOT NULL,  -- Exact text of the claim
    claim_context TEXT,        -- Surrounding context
    claim_location TEXT,       -- Page/section/URL path

    -- Finding Type
    finding_type TEXT NOT NULL,  -- 'violation', 'warning', 'verified', 'unverifiable'
    severity TEXT,             -- 'critical', 'significant', 'advisory', 'informational'

    -- Regulatory Reference
    regulation_code TEXT,      -- e.g., 'FTC-5', 'ACCSC-I.B.1'
    regulation_title TEXT,
    regulatory_source TEXT,    -- 'federal_ftc', 'accreditor', 'state'

    -- Verification
    verified_value TEXT,       -- Actual value from achievement data
    claimed_value TEXT,        -- Value stated in claim
    variance REAL,             -- Percentage variance if applicable
    evidence_source TEXT,      -- Where verified value came from

    -- Recommendation
    recommendation TEXT,
    remediation_effort TEXT,   -- 'low', 'medium', 'high'

    -- AI Confidence
    confidence REAL DEFAULT 0.0,
    requires_human_review INTEGER DEFAULT 0,

    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES advertising_scans(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_ad_scans_institution ON advertising_scans(institution_id);
CREATE INDEX IF NOT EXISTS idx_ad_scans_status ON advertising_scans(status);
CREATE INDEX IF NOT EXISTS idx_ad_scans_created ON advertising_scans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ad_findings_scan ON advertising_findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_ad_findings_type ON advertising_findings(finding_type);
CREATE INDEX IF NOT EXISTS idx_ad_findings_severity ON advertising_findings(severity);
