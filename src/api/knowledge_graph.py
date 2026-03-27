"""Knowledge Graph API.

Provides endpoints for building, querying, and visualizing the institutional
knowledge graph that models entities and their relationships.

Endpoints:
- GET /api/institutions/<id>/knowledge-graph - Full graph data for visualization
- GET /api/institutions/<id>/knowledge-graph/entities - List entities (filterable)
- GET /api/institutions/<id>/knowledge-graph/entities/<eid> - Entity details
- GET /api/institutions/<id>/knowledge-graph/entities/<eid>/neighbors - Connected entities
- POST /api/institutions/<id>/knowledge-graph/build - Trigger graph build
- POST /api/institutions/<id>/knowledge-graph/relationships - Add relationship
- GET /api/institutions/<id>/knowledge-graph/paths - Find paths (query params: from, to)
- GET /api/institutions/<id>/knowledge-graph/impact/<eid> - Impact analysis
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Optional

logger = logging.getLogger(__name__)

from src.services import knowledge_graph_service as kg_service

knowledge_graph_bp = Blueprint('knowledge_graph', __name__, url_prefix='/api')

_workspace_manager = None
_standards_store = None


def init_knowledge_graph_bp(workspace_manager, standards_store=None):
    """Initialize the knowledge graph blueprint with dependencies."""
    global _workspace_manager, _standards_store
    _workspace_manager = workspace_manager
    _standards_store = standards_store


# =============================================================================
# Graph Data Endpoints
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph', methods=['GET'])
def get_graph(institution_id: str):
    """Get full graph data for D3.js visualization.

    Query params:
        entity_types: Comma-separated list of entity types to include
        relationship_types: Comma-separated list of relationship types to include

    Returns:
        {
            "success": true,
            "nodes": [...],
            "edges": [...],
            "stats": {
                "total_nodes": 45,
                "total_edges": 78,
                "entity_type_counts": {...},
                "relationship_type_counts": {...}
            }
        }
    """
    entity_types = request.args.get('entity_types')
    relationship_types = request.args.get('relationship_types')

    entity_types_list = entity_types.split(',') if entity_types else None
    relationship_types_list = relationship_types.split(',') if relationship_types else None

    try:
        graph = kg_service.get_graph_data(
            institution_id=institution_id,
            entity_types=entity_types_list,
            relationship_types=relationship_types_list
        )

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **graph
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "nodes": [],
            "edges": []
        }), 500


@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/build', methods=['POST'])
def build_graph(institution_id: str):
    """Trigger knowledge graph build from all data sources.

    Request body (optional):
        {
            "include_standards": true
        }

    Returns:
        {
            "success": true,
            "entities_created": 45,
            "relationships_created": 78,
            "entity_counts": {...},
            "built_at": "2026-03-13T..."
        }
    """
    data = request.get_json() or {}
    include_standards = data.get('include_standards', True)

    try:
        # Load institution
        if not _workspace_manager:
            return jsonify({
                "success": False,
                "error": "Workspace manager not initialized"
            }), 500

        institution = _workspace_manager.load_institution(institution_id)
        if not institution:
            return jsonify({
                "success": False,
                "error": "Institution not found"
            }), 404

        # Get programs
        programs = [p.to_dict() for p in institution.programs]

        # Get standards if requested
        standards_data = None
        if include_standards and _standards_store:
            try:
                accreditor = institution.accrediting_body.value if institution.accrediting_body else "ACCSC"
                standards_data = _standards_store.get_standards(accreditor)
            except Exception as e:
                logger.debug("Failed to load standards for graph build: %s", e)

        result = kg_service.build_graph_from_institution(
            institution_id=institution_id,
            programs=programs,
            standards_data=standards_data
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Entity Endpoints
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/entities', methods=['GET'])
def list_entities(institution_id: str):
    """List entities in the knowledge graph.

    Query params:
        type: Filter by entity type
        search: Search term for display name
        limit: Maximum results (default 100)
        offset: Results offset (default 0)

    Returns:
        {
            "success": true,
            "entities": [...],
            "count": 45
        }
    """
    entity_type = request.args.get('type')
    search = request.args.get('search')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        entities = kg_service.list_entities(
            institution_id=institution_id,
            entity_type=entity_type,
            search=search,
            limit=limit,
            offset=offset
        )

        # Group by type for UI
        by_type = {}
        for entity in entities:
            t = entity.entity_type
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(entity.to_dict())

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "entities": [e.to_dict() for e in entities],
            "by_type": by_type,
            "count": len(entities)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "entities": []
        }), 500


@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/entities/<entity_id>', methods=['GET'])
def get_entity(institution_id: str, entity_id: str):
    """Get details for a specific entity.

    Returns:
        {
            "success": true,
            "entity": {
                "id": "program:prog_123",
                "entity_type": "program",
                "display_name": "Medical Assisting",
                ...
            }
        }
    """
    try:
        entity = kg_service.get_entity(entity_id)

        if not entity:
            return jsonify({
                "success": False,
                "error": "Entity not found"
            }), 404

        if entity.institution_id != institution_id:
            return jsonify({
                "success": False,
                "error": "Entity does not belong to this institution"
            }), 403

        return jsonify({
            "success": True,
            "entity": entity.to_dict()
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/entities/<entity_id>/neighbors', methods=['GET'])
def get_neighbors(institution_id: str, entity_id: str):
    """Get entities connected to a given entity.

    Query params:
        depth: Number of hops (1-3, default 1)
        relationship_types: Comma-separated relationship types
        direction: outgoing, incoming, or both (default both)

    Returns:
        {
            "success": true,
            "source_entity_id": "program:prog_123",
            "neighbors": [...],
            "relationships": [...],
            "total_neighbors": 12
        }
    """
    depth = request.args.get('depth', 1, type=int)
    relationship_types = request.args.get('relationship_types')
    direction = request.args.get('direction', 'both')

    rel_types_list = relationship_types.split(',') if relationship_types else None

    try:
        result = kg_service.query_neighbors(
            entity_id=entity_id,
            depth=depth,
            relationship_types=rel_types_list,
            direction=direction
        )

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Relationship Endpoints
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/relationships', methods=['POST'])
def add_relationship(institution_id: str):
    """Add a relationship between two entities.

    Request body:
        {
            "source_entity_id": "faculty:fac_123",
            "target_entity_id": "program:prog_456",
            "relationship_type": "teaches",
            "strength": 1.0
        }

    Returns:
        {
            "success": true,
            "relationship": {...}
        }
    """
    data = request.get_json() or {}

    source_id = data.get('source_entity_id')
    target_id = data.get('target_entity_id')
    rel_type = data.get('relationship_type')
    strength = data.get('strength', 1.0)

    if not source_id or not target_id or not rel_type:
        return jsonify({
            "success": False,
            "error": "source_entity_id, target_entity_id, and relationship_type are required"
        }), 400

    try:
        rel = kg_service.add_relationship(
            institution_id=institution_id,
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=rel_type,
            strength=strength,
            metadata=data.get('metadata')
        )

        return jsonify({
            "success": True,
            "relationship": rel.to_dict()
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Path Finding Endpoints
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/paths', methods=['GET'])
def find_paths(institution_id: str):
    """Find paths between two entities.

    Query params:
        from: Source entity ID (required)
        to: Target entity ID (required)
        max_depth: Maximum path length (default 4)

    Returns:
        {
            "success": true,
            "paths": [
                {
                    "source_id": "...",
                    "target_id": "...",
                    "path": ["entity1", "entity2", "entity3"],
                    "relationships": ["teaches", "implements"],
                    "total_length": 2
                },
                ...
            ],
            "count": 3,
            "shortest_path": {...}
        }
    """
    source_id = request.args.get('from')
    target_id = request.args.get('to')
    max_depth = request.args.get('max_depth', 4, type=int)

    if not source_id or not target_id:
        return jsonify({
            "success": False,
            "error": "'from' and 'to' query parameters are required"
        }), 400

    try:
        paths = kg_service.find_paths(
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth
        )

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "paths": [p.to_dict() for p in paths],
            "count": len(paths),
            "shortest_path": paths[0].to_dict() if paths else None
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Impact Analysis Endpoint
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/impact/<entity_id>', methods=['GET'])
def get_impact(institution_id: str, entity_id: str):
    """Analyze what entities would be affected if this entity changes.

    Returns:
        {
            "success": true,
            "entity_id": "program:prog_123",
            "entity_name": "Medical Assisting",
            "directly_affected": [...],
            "indirectly_affected": [...],
            "total_affected": 8,
            "impact_score": 0.4
        }
    """
    try:
        result = kg_service.get_entity_impact(entity_id)

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **result.to_dict()
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Export Endpoint
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/export', methods=['GET'])
def export_graph(institution_id: str):
    """Export the knowledge graph.

    Query params:
        format: json or graphml (default json)

    Returns:
        Exported graph in requested format
    """
    export_format = request.args.get('format', 'json')

    if export_format not in ('json', 'graphml'):
        return jsonify({
            "success": False,
            "error": "Format must be 'json' or 'graphml'"
        }), 400

    try:
        result = kg_service.export_graph(
            institution_id=institution_id,
            format=export_format
        )

        if export_format == 'graphml':
            # Return as XML file
            from flask import Response
            return Response(
                result['content'],
                mimetype='application/xml',
                headers={
                    'Content-Disposition': f'attachment; filename=knowledge_graph_{institution_id}.graphml'
                }
            )

        return jsonify({
            "success": True,
            "institution_id": institution_id,
            **result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Entity Types & Relationship Types Info
# =============================================================================

@knowledge_graph_bp.route('/institutions/<institution_id>/knowledge-graph/meta', methods=['GET'])
def get_graph_meta(institution_id: str):
    """Get metadata about available entity and relationship types.

    Returns:
        {
            "success": true,
            "entity_types": [
                {"type": "program", "icon": "graduation-cap", "color": "#a78bfa"},
                ...
            ],
            "relationship_types": [
                {"type": "teaches", "label": "teaches", "directed": true},
                ...
            ]
        }
    """
    return jsonify({
        "success": True,
        "entity_types": [
            {"type": "program", "icon": "graduation-cap", "color": "#a78bfa"},
            {"type": "policy", "icon": "clipboard", "color": "#f472b6"},
            {"type": "standard", "icon": "ruler", "color": "#fb923c"},
            {"type": "faculty", "icon": "user", "color": "#34d399"},
            {"type": "document", "icon": "file", "color": "#60a5fa"},
            {"type": "finding", "icon": "alert-triangle", "color": "#fbbf24"},
        ],
        "relationship_types": [
            {"type": "teaches", "label": "teaches", "directed": True},
            {"type": "implements", "label": "implements", "directed": True},
            {"type": "evidences", "label": "evidences", "directed": True},
            {"type": "complies_with", "label": "complies with", "directed": True},
            {"type": "requires", "label": "requires", "directed": True},
            {"type": "addresses", "label": "addresses", "directed": True},
            {"type": "depends_on", "label": "depends on", "directed": True},
        ]
    })
