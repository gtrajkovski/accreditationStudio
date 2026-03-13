-- 0019_knowledge_graph_entities.sql
-- Full Knowledge Graph: Entities and typed relationships for institutional modeling

PRAGMA foreign_keys = ON;

-- Core entity table - represents nodes in the knowledge graph
CREATE TABLE IF NOT EXISTS kg_entities (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- program, policy, standard, faculty, document, finding
    entity_id TEXT NOT NULL,     -- FK to source table (program_id, doc_id, etc.)
    display_name TEXT NOT NULL,
    category TEXT,               -- Grouping category within entity type
    attributes TEXT,             -- JSON blob for type-specific data
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Relationship table - represents edges in the knowledge graph
CREATE TABLE IF NOT EXISTS kg_relationships (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  -- teaches, implements, evidences, complies_with, requires, addresses, depends_on
    strength REAL DEFAULT 1.0,         -- Relationship strength/weight (0.0-1.0)
    metadata TEXT,                     -- JSON for relationship attributes
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
    FOREIGN KEY (source_entity_id) REFERENCES kg_entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES kg_entities(id) ON DELETE CASCADE
);

-- Indexes for efficient graph traversal
CREATE INDEX IF NOT EXISTS idx_kg_entities_inst_type ON kg_entities(institution_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entities_entity_id ON kg_entities(institution_id, entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_entities_category ON kg_entities(institution_id, category);

CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_type ON kg_relationships(institution_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_kg_rel_pair ON kg_relationships(source_entity_id, target_entity_id);

-- Unique constraint to prevent duplicate relationships
CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_rel_unique
ON kg_relationships(source_entity_id, target_entity_id, relationship_type);
