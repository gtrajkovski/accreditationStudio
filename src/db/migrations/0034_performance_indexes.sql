-- Migration: 0034_performance_indexes.sql
-- Performance indexes for common query patterns

-- Audit findings: often filtered by (audit_run_id, status)
CREATE INDEX IF NOT EXISTS idx_audit_findings_run_status
ON audit_findings(audit_run_id, status);

-- Audit findings: often filtered by (audit_run_id, severity)
CREATE INDEX IF NOT EXISTS idx_audit_findings_run_severity
ON audit_findings(audit_run_id, severity);

-- Document versions: often queried by (document_id, version_type)
CREATE INDEX IF NOT EXISTS idx_document_versions_doc_type
ON document_versions(document_id, version_type);

-- Readiness snapshots: batch loading by institution list + time
CREATE INDEX IF NOT EXISTS idx_readiness_snapshots_inst_time
ON institution_readiness_snapshots(institution_id, created_at DESC);

-- Evidence refs: often joined with findings
CREATE INDEX IF NOT EXISTS idx_evidence_refs_finding
ON evidence_refs(finding_id);
