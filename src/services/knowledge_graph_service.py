"""Knowledge Graph Service.

Builds and queries a full knowledge graph modeling institutional entities
(programs, policies, standards, faculty, documents) as nodes with typed
relationships between them.

Key capabilities:
- Extract entities from institution data sources
- Infer relationships from audits, mappings, and references
- Query graph for neighbors, paths, and impact analysis
- Export graph for visualization
"""

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from uuid import uuid4

from src.db.connection import get_conn


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class KGEntity:
    """A node in the knowledge graph."""
    id: str
    institution_id: str
    entity_type: str  # program, policy, standard, faculty, document, finding
    entity_id: str    # FK to source table
    display_name: str
    category: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if isinstance(result.get("attributes"), dict):
            result["attributes"] = result["attributes"]
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class KGRelationship:
    """An edge in the knowledge graph."""
    id: str
    institution_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str  # teaches, implements, evidences, complies_with, requires, addresses, depends_on
    strength: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class GraphPath:
    """A path between two entities."""
    source_id: str
    target_id: str
    path: List[str]  # Entity IDs in order
    relationships: List[str]  # Relationship types along the path
    total_length: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ImpactResult:
    """Result of impact analysis for an entity."""
    entity_id: str
    entity_name: str
    directly_affected: List[Dict[str, Any]]
    indirectly_affected: List[Dict[str, Any]]
    total_affected: int
    impact_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_id(prefix: str = "kg") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def _make_entity_id(entity_type: str, entity_id: str) -> str:
    """Create a canonical entity ID from type and source ID."""
    return f"{entity_type}:{entity_id}"


# =============================================================================
# Entity Extraction Functions
# =============================================================================

def extract_program_entities(
    institution_id: str,
    programs: List[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """Extract program entities from institution data.

    Args:
        institution_id: Institution ID
        programs: List of program dictionaries
        conn: Optional database connection

    Returns:
        List of KGEntity objects for programs
    """
    entities = []

    for prog in programs:
        prog_id = prog.get("id", "")
        name = prog.get("name_en") or prog.get("name", "Unknown Program")

        entity = KGEntity(
            id=_make_entity_id("program", prog_id),
            institution_id=institution_id,
            entity_type="program",
            entity_id=prog_id,
            display_name=name,
            category=prog.get("credential_type", "program"),
            attributes={
                "credential_type": prog.get("credential_type"),
                "duration_months": prog.get("duration_months"),
                "total_cost": prog.get("total_cost"),
                "status": prog.get("status", "active"),
                "cip_code": prog.get("cip_code"),
            },
            created_at=_now_iso(),
            updated_at=_now_iso()
        )
        entities.append(entity)

    return entities


def extract_document_entities(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """Extract document entities from database.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGEntity objects for documents
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT id, original_file_path, doc_type, status, title
            FROM documents
            WHERE institution_id = ?
        """, (institution_id,))

        entities = []
        for row in cursor.fetchall():
            entity = KGEntity(
                id=_make_entity_id("document", row["id"]),
                institution_id=institution_id,
                entity_type="document",
                entity_id=row["id"],
                display_name=row["title"] or row["original_file_path"] or row["id"],
                category=row["doc_type"],
                attributes={
                    "doc_type": row["doc_type"],
                    "status": row["status"],
                    "file_path": row["original_file_path"],
                },
                created_at=_now_iso(),
                updated_at=_now_iso()
            )
            entities.append(entity)

        return entities

    except sqlite3.OperationalError:
        return []

    finally:
        if should_close:
            conn.close()


def extract_faculty_entities(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """Extract faculty entities from database.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGEntity objects for faculty
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT id, full_name, title, department, employment_type, status
            FROM faculty
            WHERE institution_id = ?
        """, (institution_id,))

        entities = []
        for row in cursor.fetchall():
            entity = KGEntity(
                id=_make_entity_id("faculty", row["id"]),
                institution_id=institution_id,
                entity_type="faculty",
                entity_id=row["id"],
                display_name=row["full_name"],
                category=row["department"] or "faculty",
                attributes={
                    "title": row["title"],
                    "department": row["department"],
                    "employment_type": row["employment_type"],
                    "status": row["status"],
                },
                created_at=_now_iso(),
                updated_at=_now_iso()
            )
            entities.append(entity)

        return entities

    except sqlite3.OperationalError:
        # Table doesn't exist or has different schema
        return []

    finally:
        if should_close:
            conn.close()


def extract_standard_entities(
    institution_id: str,
    standards_data: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """Extract standard entities from standards store.

    Args:
        institution_id: Institution ID
        standards_data: Standards dictionary from StandardsStore
        conn: Optional database connection

    Returns:
        List of KGEntity objects for standards
    """
    entities = []

    # Flatten nested standards structure
    def extract_standards(data: Dict[str, Any], prefix: str = "", accreditor: str = ""):
        for key, value in data.items():
            if isinstance(value, dict):
                if "description" in value or "text" in value:
                    # This is a standard entry
                    std_id = f"{prefix}{key}" if prefix else key
                    entity = KGEntity(
                        id=_make_entity_id("standard", std_id),
                        institution_id=institution_id,
                        entity_type="standard",
                        entity_id=std_id,
                        display_name=value.get("title") or value.get("description", std_id)[:100],
                        category=accreditor or "standard",
                        attributes={
                            "reference": std_id,
                            "accreditor": accreditor,
                            "description": value.get("description"),
                            "text": value.get("text"),
                        },
                        created_at=_now_iso(),
                        updated_at=_now_iso()
                    )
                    entities.append(entity)
                else:
                    # Nested structure
                    new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                    extract_standards(value, new_prefix, accreditor or key)

    extract_standards(standards_data)
    return entities


def extract_finding_entities(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """Extract audit finding entities from database.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGEntity objects for findings
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT af.id, af.severity, af.status, af.summary
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ?
        """, (institution_id,))

        entities = []
        for row in cursor.fetchall():
            entity = KGEntity(
                id=_make_entity_id("finding", row["id"]),
                institution_id=institution_id,
                entity_type="finding",
                entity_id=row["id"],
                display_name=row["summary"][:60] if row["summary"] else f"Finding {row['id'][:8]}",
                category=row["severity"] or "finding",
                attributes={
                    "severity": row["severity"],
                    "status": row["status"],
                    "summary": row["summary"][:200] if row["summary"] else None,
                },
                created_at=_now_iso(),
                updated_at=_now_iso()
            )
            entities.append(entity)

        return entities

    except sqlite3.OperationalError:
        return []

    finally:
        if should_close:
            conn.close()


# =============================================================================
# Relationship Inference Functions
# =============================================================================

def infer_faculty_program_relationships(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGRelationship]:
    """Infer faculty-to-program teaching relationships.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGRelationship objects
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Check if faculty_programs junction table exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='faculty_programs'
        """)

        relationships = []

        if cursor.fetchone():
            cursor = conn.execute("""
                SELECT faculty_id, program_id
                FROM faculty_programs
                WHERE institution_id = ?
            """, (institution_id,))

            for row in cursor.fetchall():
                rel = KGRelationship(
                    id=_generate_id("rel"),
                    institution_id=institution_id,
                    source_entity_id=_make_entity_id("faculty", row["faculty_id"]),
                    target_entity_id=_make_entity_id("program", row["program_id"]),
                    relationship_type="teaches",
                    strength=1.0,
                    metadata={},
                    created_at=_now_iso()
                )
                relationships.append(rel)

        return relationships

    finally:
        if should_close:
            conn.close()


def infer_document_standard_relationships(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGRelationship]:
    """Infer document-to-standard evidence relationships from audits.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGRelationship objects
    """
    # Currently no direct document-standard mapping in schema
    # This would need checklist_items to have standard references
    return []


def infer_finding_standard_relationships(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGRelationship]:
    """Infer finding-to-standard address relationships.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGRelationship objects
    """
    # Current schema doesn't have standard_ref on findings
    # Findings link to checklist_items which could link to standards
    return []


def infer_fact_dependency_relationships(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGRelationship]:
    """Import fact dependencies from impact analysis as graph relationships.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of KGRelationship objects
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT source_fact, dependent_fact, dependency_type
            FROM fact_dependencies
            WHERE institution_id = ?
        """, (institution_id,))

        relationships = []

        for row in cursor.fetchall():
            rel = KGRelationship(
                id=_generate_id("rel"),
                institution_id=institution_id,
                source_entity_id=f"fact:{row['source_fact']}",
                target_entity_id=f"fact:{row['dependent_fact']}",
                relationship_type="depends_on",
                strength=1.0,
                metadata={"dependency_type": row["dependency_type"]},
                created_at=_now_iso()
            )
            relationships.append(rel)

        return relationships

    except sqlite3.OperationalError:
        return []

    finally:
        if should_close:
            conn.close()


# =============================================================================
# Core Graph Functions
# =============================================================================

def build_graph_from_institution(
    institution_id: str,
    programs: List[Dict[str, Any]],
    standards_data: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Build full knowledge graph from all institution data sources.

    Args:
        institution_id: Institution ID
        programs: List of program dictionaries from Institution
        standards_data: Optional standards data from StandardsStore
        conn: Optional database connection

    Returns:
        Summary of entities and relationships created
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Disable foreign keys for this session (institutions stored as JSON, not in DB)
        conn.execute("PRAGMA foreign_keys = OFF")

        # Clear existing graph for this institution
        conn.execute("DELETE FROM kg_relationships WHERE institution_id = ?", (institution_id,))
        conn.execute("DELETE FROM kg_entities WHERE institution_id = ?", (institution_id,))

        # Extract all entities
        all_entities = []

        # Programs
        program_entities = extract_program_entities(institution_id, programs, conn)
        all_entities.extend(program_entities)

        # Documents
        doc_entities = extract_document_entities(institution_id, conn)
        all_entities.extend(doc_entities)

        # Faculty
        faculty_entities = extract_faculty_entities(institution_id, conn)
        all_entities.extend(faculty_entities)

        # Standards (if provided)
        if standards_data:
            std_entities = extract_standard_entities(institution_id, standards_data, conn)
            all_entities.extend(std_entities)

        # Findings
        finding_entities = extract_finding_entities(institution_id, conn)
        all_entities.extend(finding_entities)

        # Save entities
        entities_saved = 0
        for entity in all_entities:
            try:
                conn.execute("""
                    INSERT INTO kg_entities (
                        id, institution_id, entity_type, entity_id,
                        display_name, category, attributes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entity.id,
                    entity.institution_id,
                    entity.entity_type,
                    entity.entity_id,
                    entity.display_name,
                    entity.category,
                    json.dumps(entity.attributes),
                    entity.created_at,
                    entity.updated_at
                ))
                entities_saved += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

        # Infer relationships
        all_relationships = []

        all_relationships.extend(infer_faculty_program_relationships(institution_id, conn))
        all_relationships.extend(infer_document_standard_relationships(institution_id, conn))
        all_relationships.extend(infer_finding_standard_relationships(institution_id, conn))
        all_relationships.extend(infer_fact_dependency_relationships(institution_id, conn))

        # Save relationships
        rels_saved = 0
        for rel in all_relationships:
            try:
                conn.execute("""
                    INSERT INTO kg_relationships (
                        id, institution_id, source_entity_id, target_entity_id,
                        relationship_type, strength, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel.id,
                    rel.institution_id,
                    rel.source_entity_id,
                    rel.target_entity_id,
                    rel.relationship_type,
                    rel.strength,
                    json.dumps(rel.metadata),
                    rel.created_at
                ))
                rels_saved += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

        conn.commit()

        return {
            "success": True,
            "institution_id": institution_id,
            "entities_created": entities_saved,
            "relationships_created": rels_saved,
            "entity_counts": {
                "programs": len(program_entities),
                "documents": len(doc_entities),
                "faculty": len(faculty_entities),
                "standards": len(std_entities) if standards_data else 0,
                "findings": len(finding_entities),
            },
            "built_at": _now_iso()
        }

    finally:
        if should_close:
            conn.close()


def get_graph_data(
    institution_id: str,
    entity_types: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Get graph data for D3.js visualization.

    Args:
        institution_id: Institution ID
        entity_types: Optional filter for entity types
        relationship_types: Optional filter for relationship types
        conn: Optional database connection

    Returns:
        Graph with nodes and edges for D3.js
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Build query for entities
        entity_query = """
            SELECT id, entity_type, entity_id, display_name, category, attributes
            FROM kg_entities
            WHERE institution_id = ?
        """
        params = [institution_id]

        if entity_types:
            placeholders = ",".join("?" * len(entity_types))
            entity_query += f" AND entity_type IN ({placeholders})"
            params.extend(entity_types)

        cursor = conn.execute(entity_query, params)

        nodes = []
        node_ids = set()
        for row in cursor.fetchall():
            attrs = json.loads(row["attributes"]) if row["attributes"] else {}
            nodes.append({
                "id": row["id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "label": row["display_name"][:40],
                "category": row["category"],
                "attributes": attrs,
            })
            node_ids.add(row["id"])

        # Build query for relationships
        rel_query = """
            SELECT id, source_entity_id, target_entity_id, relationship_type, strength, metadata
            FROM kg_relationships
            WHERE institution_id = ?
        """
        params = [institution_id]

        if relationship_types:
            placeholders = ",".join("?" * len(relationship_types))
            rel_query += f" AND relationship_type IN ({placeholders})"
            params.extend(relationship_types)

        cursor = conn.execute(rel_query, params)

        edges = []
        for row in cursor.fetchall():
            # Only include edges where both nodes exist
            if row["source_entity_id"] in node_ids and row["target_entity_id"] in node_ids:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
                edges.append({
                    "id": row["id"],
                    "source": row["source_entity_id"],
                    "target": row["target_entity_id"],
                    "relationship_type": row["relationship_type"],
                    "weight": row["strength"],
                    "metadata": meta,
                })

        # Compute stats
        type_counts = {}
        for node in nodes:
            t = node["entity_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        rel_counts = {}
        for edge in edges:
            t = edge["relationship_type"]
            rel_counts[t] = rel_counts.get(t, 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "entity_type_counts": type_counts,
                "relationship_type_counts": rel_counts,
            }
        }

    finally:
        if should_close:
            conn.close()


def list_entities(
    institution_id: str,
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    conn: Optional[sqlite3.Connection] = None
) -> List[KGEntity]:
    """List entities with optional filtering.

    Args:
        institution_id: Institution ID
        entity_type: Optional filter by entity type
        search: Optional search term for display_name
        limit: Maximum results
        offset: Results offset
        conn: Optional database connection

    Returns:
        List of KGEntity objects
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        query = """
            SELECT id, institution_id, entity_type, entity_id, display_name,
                   category, attributes, created_at, updated_at
            FROM kg_entities
            WHERE institution_id = ?
        """
        params = [institution_id]

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)

        if search:
            query += " AND display_name LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY entity_type, display_name LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)

        entities = []
        for row in cursor.fetchall():
            attrs = json.loads(row["attributes"]) if row["attributes"] else {}
            entity = KGEntity(
                id=row["id"],
                institution_id=row["institution_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                display_name=row["display_name"],
                category=row["category"],
                attributes=attrs,
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            entities.append(entity)

        return entities

    finally:
        if should_close:
            conn.close()


def get_entity(
    entity_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[KGEntity]:
    """Get a single entity by ID.

    Args:
        entity_id: Entity ID
        conn: Optional database connection

    Returns:
        KGEntity or None
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT id, institution_id, entity_type, entity_id, display_name,
                   category, attributes, created_at, updated_at
            FROM kg_entities
            WHERE id = ?
        """, (entity_id,))

        row = cursor.fetchone()
        if not row:
            return None

        attrs = json.loads(row["attributes"]) if row["attributes"] else {}
        return KGEntity(
            id=row["id"],
            institution_id=row["institution_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            display_name=row["display_name"],
            category=row["category"],
            attributes=attrs,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    finally:
        if should_close:
            conn.close()


def query_neighbors(
    entity_id: str,
    depth: int = 1,
    relationship_types: Optional[List[str]] = None,
    direction: str = "both",
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Query connected entities (neighbors) for a given entity.

    Args:
        entity_id: Source entity ID
        depth: How many hops to traverse (1-3)
        relationship_types: Optional filter for relationship types
        direction: "outgoing", "incoming", or "both"
        conn: Optional database connection

    Returns:
        Dict with neighbors and connecting relationships
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        depth = min(max(depth, 1), 3)  # Clamp to 1-3

        visited_entities: Set[str] = {entity_id}
        all_neighbors: List[Dict[str, Any]] = []
        all_edges: List[Dict[str, Any]] = []

        current_level = {entity_id}

        for level in range(1, depth + 1):
            next_level = set()

            for current_id in current_level:
                # Build query based on direction
                queries = []

                if direction in ("outgoing", "both"):
                    queries.append(("outgoing", """
                        SELECT r.id, r.target_entity_id as neighbor_id, r.relationship_type, r.strength,
                               e.entity_type, e.display_name, e.category
                        FROM kg_relationships r
                        JOIN kg_entities e ON r.target_entity_id = e.id
                        WHERE r.source_entity_id = ?
                    """))

                if direction in ("incoming", "both"):
                    queries.append(("incoming", """
                        SELECT r.id, r.source_entity_id as neighbor_id, r.relationship_type, r.strength,
                               e.entity_type, e.display_name, e.category
                        FROM kg_relationships r
                        JOIN kg_entities e ON r.source_entity_id = e.id
                        WHERE r.target_entity_id = ?
                    """))

                for dir_type, query in queries:
                    if relationship_types:
                        placeholders = ",".join("?" * len(relationship_types))
                        query += f" AND r.relationship_type IN ({placeholders})"
                        cursor = conn.execute(query, [current_id] + relationship_types)
                    else:
                        cursor = conn.execute(query, [current_id])

                    for row in cursor.fetchall():
                        neighbor_id = row["neighbor_id"]

                        if neighbor_id not in visited_entities:
                            visited_entities.add(neighbor_id)
                            next_level.add(neighbor_id)

                            all_neighbors.append({
                                "id": neighbor_id,
                                "entity_type": row["entity_type"],
                                "display_name": row["display_name"],
                                "category": row["category"],
                                "depth": level,
                            })

                        # Record edge
                        all_edges.append({
                            "id": row["id"],
                            "source": current_id if dir_type == "outgoing" else neighbor_id,
                            "target": neighbor_id if dir_type == "outgoing" else current_id,
                            "relationship_type": row["relationship_type"],
                            "direction": dir_type,
                            "depth": level,
                        })

            current_level = next_level
            if not current_level:
                break

        return {
            "source_entity_id": entity_id,
            "neighbors": all_neighbors,
            "relationships": all_edges,
            "total_neighbors": len(all_neighbors),
            "depth_reached": min(depth, len([n for n in all_neighbors if n["depth"] == depth]) > 0 and depth or depth - 1)
        }

    finally:
        if should_close:
            conn.close()


def find_paths(
    source_id: str,
    target_id: str,
    max_depth: int = 4,
    conn: Optional[sqlite3.Connection] = None
) -> List[GraphPath]:
    """Find paths between two entities using BFS.

    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        max_depth: Maximum path length
        conn: Optional database connection

    Returns:
        List of GraphPath objects
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        if source_id == target_id:
            return [GraphPath(
                source_id=source_id,
                target_id=target_id,
                path=[source_id],
                relationships=[],
                total_length=0
            )]

        # BFS to find paths
        paths: List[GraphPath] = []
        queue: List[Tuple[str, List[str], List[str]]] = [(source_id, [source_id], [])]
        visited_paths: Set[str] = set()

        while queue and len(paths) < 5:  # Limit to 5 paths
            current_id, path, rels = queue.pop(0)

            if len(path) > max_depth:
                continue

            # Get neighbors
            cursor = conn.execute("""
                SELECT target_entity_id as neighbor, relationship_type
                FROM kg_relationships
                WHERE source_entity_id = ?
                UNION
                SELECT source_entity_id as neighbor, relationship_type
                FROM kg_relationships
                WHERE target_entity_id = ?
            """, (current_id, current_id))

            for row in cursor.fetchall():
                neighbor = row["neighbor"]
                rel_type = row["relationship_type"]

                if neighbor in path:
                    continue  # Avoid cycles

                new_path = path + [neighbor]
                new_rels = rels + [rel_type]
                path_key = "->".join(new_path)

                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)

                if neighbor == target_id:
                    paths.append(GraphPath(
                        source_id=source_id,
                        target_id=target_id,
                        path=new_path,
                        relationships=new_rels,
                        total_length=len(new_rels)
                    ))
                else:
                    queue.append((neighbor, new_path, new_rels))

        # Sort by path length
        paths.sort(key=lambda p: p.total_length)
        return paths

    finally:
        if should_close:
            conn.close()


def get_entity_impact(
    entity_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> ImpactResult:
    """Analyze what entities would be affected if this entity changes.

    Args:
        entity_id: Entity to analyze
        conn: Optional database connection

    Returns:
        ImpactResult with affected entities
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Get entity info
        entity = get_entity(entity_id, conn)
        entity_name = entity.display_name if entity else entity_id

        # Direct dependencies (entities that depend on this one)
        cursor = conn.execute("""
            SELECT e.id, e.entity_type, e.display_name, e.category, r.relationship_type
            FROM kg_relationships r
            JOIN kg_entities e ON r.source_entity_id = e.id
            WHERE r.target_entity_id = ?
        """, (entity_id,))

        directly_affected = []
        for row in cursor.fetchall():
            directly_affected.append({
                "id": row["id"],
                "entity_type": row["entity_type"],
                "display_name": row["display_name"],
                "relationship_type": row["relationship_type"],
            })

        # Indirect dependencies (2-hop)
        indirectly_affected = []
        direct_ids = [d["id"] for d in directly_affected]

        if direct_ids:
            placeholders = ",".join("?" * len(direct_ids))
            cursor = conn.execute(f"""
                SELECT DISTINCT e.id, e.entity_type, e.display_name, e.category, r.relationship_type
                FROM kg_relationships r
                JOIN kg_entities e ON r.source_entity_id = e.id
                WHERE r.target_entity_id IN ({placeholders})
                  AND e.id != ?
                  AND e.id NOT IN ({placeholders})
            """, direct_ids + [entity_id] + direct_ids)

            for row in cursor.fetchall():
                indirectly_affected.append({
                    "id": row["id"],
                    "entity_type": row["entity_type"],
                    "display_name": row["display_name"],
                    "relationship_type": row["relationship_type"],
                })

        total = len(directly_affected) + len(indirectly_affected)

        # Calculate impact score (0-1)
        impact_score = min(1.0, total / 20.0)  # Normalize, max at 20 affected

        return ImpactResult(
            entity_id=entity_id,
            entity_name=entity_name,
            directly_affected=directly_affected,
            indirectly_affected=indirectly_affected,
            total_affected=total,
            impact_score=impact_score
        )

    finally:
        if should_close:
            conn.close()


def add_entity(
    institution_id: str,
    entity_type: str,
    entity_id: str,
    display_name: str,
    category: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> KGEntity:
    """Manually add an entity to the graph.

    Args:
        institution_id: Institution ID
        entity_type: Type of entity
        entity_id: Source entity ID
        display_name: Display name
        category: Optional category
        attributes: Optional attributes dict
        conn: Optional database connection

    Returns:
        Created KGEntity
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        entity = KGEntity(
            id=_make_entity_id(entity_type, entity_id),
            institution_id=institution_id,
            entity_type=entity_type,
            entity_id=entity_id,
            display_name=display_name,
            category=category,
            attributes=attributes or {},
            created_at=_now_iso(),
            updated_at=_now_iso()
        )

        conn.execute("""
            INSERT OR REPLACE INTO kg_entities (
                id, institution_id, entity_type, entity_id,
                display_name, category, attributes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.id,
            entity.institution_id,
            entity.entity_type,
            entity.entity_id,
            entity.display_name,
            entity.category,
            json.dumps(entity.attributes),
            entity.created_at,
            entity.updated_at
        ))
        conn.commit()

        return entity

    finally:
        if should_close:
            conn.close()


def add_relationship(
    institution_id: str,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    strength: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> KGRelationship:
    """Manually add a relationship to the graph.

    Args:
        institution_id: Institution ID
        source_entity_id: Source entity ID
        target_entity_id: Target entity ID
        relationship_type: Type of relationship
        strength: Relationship strength (0-1)
        metadata: Optional metadata dict
        conn: Optional database connection

    Returns:
        Created KGRelationship
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        rel = KGRelationship(
            id=_generate_id("rel"),
            institution_id=institution_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            strength=strength,
            metadata=metadata or {},
            created_at=_now_iso()
        )

        conn.execute("""
            INSERT OR REPLACE INTO kg_relationships (
                id, institution_id, source_entity_id, target_entity_id,
                relationship_type, strength, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rel.id,
            rel.institution_id,
            rel.source_entity_id,
            rel.target_entity_id,
            rel.relationship_type,
            rel.strength,
            json.dumps(rel.metadata),
            rel.created_at
        ))
        conn.commit()

        return rel

    finally:
        if should_close:
            conn.close()


def export_graph(
    institution_id: str,
    format: str = "json",
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Export the knowledge graph in specified format.

    Args:
        institution_id: Institution ID
        format: Export format ("json" or "graphml")
        conn: Optional database connection

    Returns:
        Exported graph data
    """
    graph_data = get_graph_data(institution_id, conn=conn)

    if format == "graphml":
        # Generate GraphML XML
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        xml_parts.append('  <key id="entity_type" for="node" attr.name="entity_type" attr.type="string"/>')
        xml_parts.append('  <key id="display_name" for="node" attr.name="display_name" attr.type="string"/>')
        xml_parts.append('  <key id="relationship_type" for="edge" attr.name="relationship_type" attr.type="string"/>')
        xml_parts.append('  <graph id="G" edgedefault="directed">')

        for node in graph_data["nodes"]:
            xml_parts.append(f'    <node id="{node["id"]}">')
            xml_parts.append(f'      <data key="entity_type">{node["entity_type"]}</data>')
            xml_parts.append(f'      <data key="display_name">{node["label"]}</data>')
            xml_parts.append('    </node>')

        for edge in graph_data["edges"]:
            xml_parts.append(f'    <edge source="{edge["source"]}" target="{edge["target"]}">')
            xml_parts.append(f'      <data key="relationship_type">{edge["relationship_type"]}</data>')
            xml_parts.append('    </edge>')

        xml_parts.append('  </graph>')
        xml_parts.append('</graphml>')

        return {
            "format": "graphml",
            "content": "\n".join(xml_parts),
            "stats": graph_data["stats"]
        }
    else:
        return {
            "format": "json",
            "content": graph_data,
            "stats": graph_data["stats"]
        }
