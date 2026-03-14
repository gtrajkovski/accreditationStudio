-- 0018_knowledge_graph.sql
-- Knowledge Graph: Extend existing tables for multi-entity graph support

PRAGMA foreign_keys = ON;

-- Extend fact_references with relationship type
-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS, so we use a workaround
-- Check if column exists first via pragma, then add if missing

-- Add relationship_type to fact_references (references, depends_on, implements, evidences, complies_with)
ALTER TABLE fact_references ADD COLUMN relationship_type TEXT DEFAULT 'references';

-- Extend fact_dependencies with entity types
ALTER TABLE fact_dependencies ADD COLUMN source_entity_type TEXT DEFAULT 'fact';
ALTER TABLE fact_dependencies ADD COLUMN target_entity_type TEXT DEFAULT 'fact';

-- Extend truth_index with entity metadata
ALTER TABLE truth_index ADD COLUMN entity_type TEXT DEFAULT 'fact';
ALTER TABLE truth_index ADD COLUMN display_name TEXT;
ALTER TABLE truth_index ADD COLUMN category TEXT;

-- Create index for relationship type filtering
CREATE INDEX IF NOT EXISTS idx_fact_refs_rel_type ON fact_references(relationship_type);
CREATE INDEX IF NOT EXISTS idx_fact_deps_entity_types ON fact_dependencies(source_entity_type, target_entity_type);
CREATE INDEX IF NOT EXISTS idx_truth_index_entity_type ON truth_index(entity_type);
CREATE INDEX IF NOT EXISTS idx_truth_index_category ON truth_index(category);
