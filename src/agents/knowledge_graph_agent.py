"""Knowledge Graph Agent.

Builds and manages the institutional knowledge graph, modeling entities
(programs, policies, standards, faculty, documents) as nodes with typed
relationships between them.

Tools:
1. build_graph - Extract all entities and relationships
2. add_entity - Manually add entity
3. add_relationship - Create relationship between entities
4. query_graph - Search entities by type/name/attributes
5. get_neighbors - Find connected entities
6. find_path - Path between two entities
7. analyze_impact - What's affected if entity changes
8. export_graph - Export as JSON/GraphML
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.services import knowledge_graph_service as kg_service


@register_agent(AgentType.KNOWLEDGE_GRAPH)
class KnowledgeGraphAgent(BaseAgent):
    """Agent for building and querying the institutional knowledge graph.

    The knowledge graph models institutional entities (programs, policies,
    standards, faculty, documents, findings) as nodes with typed relationships
    between them (teaches, implements, evidences, complies_with, etc.).

    Use this agent to:
    - Build a complete graph from institution data
    - Query for connected entities and paths
    - Analyze change impact across the graph
    - Export the graph for external analysis
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.KNOWLEDGE_GRAPH

    @property
    def system_prompt(self) -> str:
        return """You are the Knowledge Graph Agent for AccreditAI.

Your role is to build and maintain a knowledge graph that models the relationships
between institutional entities: programs, policies, standards, faculty, documents,
and compliance findings.

## Entity Types
- **program**: Academic programs offered by the institution
- **policy**: Institutional policies and procedures
- **standard**: Accreditation standards from various accreditors
- **faculty**: Faculty members and their credentials
- **document**: Uploaded documents (catalogs, policies, evidence)
- **finding**: Audit findings from compliance audits

## Relationship Types
- **teaches**: Faculty teaches in a program
- **implements**: Policy implements a standard requirement
- **evidences**: Document serves as evidence for a standard
- **complies_with**: Program complies with regulatory requirements
- **requires**: Standard requires specific documentation
- **addresses**: Finding addresses a specific standard
- **depends_on**: Fact or entity depends on another

## Workflow
1. Use `build_graph` to extract entities from all data sources
2. Use `query_graph` to search and explore entities
3. Use `get_neighbors` to find connected entities
4. Use `find_path` to discover relationships between entities
5. Use `analyze_impact` to understand change propagation
6. Use `add_entity` and `add_relationship` for manual additions
7. Use `export_graph` to export for visualization or analysis

## Best Practices
- Build the graph before querying to ensure fresh data
- Use depth=1 for immediate neighbors, depth=2-3 for broader context
- Impact analysis helps understand cascade effects before changes
- Export to GraphML for use in external graph analysis tools

Always provide clear explanations of graph structure and relationships."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "build_graph",
                "description": "Build the complete knowledge graph from all institution data sources. Extracts entities (programs, documents, faculty, standards, findings) and infers relationships between them.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_standards": {
                            "type": "boolean",
                            "description": "Whether to include standards from the standards store",
                            "default": True
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "add_entity",
                "description": "Manually add an entity to the knowledge graph.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["program", "policy", "standard", "faculty", "document", "finding", "custom"],
                            "description": "Type of entity to add"
                        },
                        "entity_id": {
                            "type": "string",
                            "description": "Unique identifier for the source entity"
                        },
                        "display_name": {
                            "type": "string",
                            "description": "Human-readable name for display"
                        },
                        "category": {
                            "type": "string",
                            "description": "Category or grouping for the entity"
                        },
                        "attributes": {
                            "type": "object",
                            "description": "Additional attributes as key-value pairs"
                        }
                    },
                    "required": ["entity_type", "entity_id", "display_name"]
                }
            },
            {
                "name": "add_relationship",
                "description": "Create a relationship between two entities in the graph.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source_entity_id": {
                            "type": "string",
                            "description": "ID of the source entity (format: type:id)"
                        },
                        "target_entity_id": {
                            "type": "string",
                            "description": "ID of the target entity (format: type:id)"
                        },
                        "relationship_type": {
                            "type": "string",
                            "enum": ["teaches", "implements", "evidences", "complies_with", "requires", "addresses", "depends_on"],
                            "description": "Type of relationship"
                        },
                        "strength": {
                            "type": "number",
                            "description": "Relationship strength from 0.0 to 1.0",
                            "default": 1.0
                        }
                    },
                    "required": ["source_entity_id", "target_entity_id", "relationship_type"]
                }
            },
            {
                "name": "query_graph",
                "description": "Search for entities in the knowledge graph by type, name, or attributes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["program", "policy", "standard", "faculty", "document", "finding"],
                            "description": "Filter by entity type"
                        },
                        "search": {
                            "type": "string",
                            "description": "Search term to match against display names"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 50
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_neighbors",
                "description": "Find entities connected to a given entity within specified depth.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "Entity ID to find neighbors for"
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Number of hops to traverse (1-3)",
                            "default": 1
                        },
                        "relationship_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by relationship types"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["outgoing", "incoming", "both"],
                            "description": "Direction of relationships to follow",
                            "default": "both"
                        }
                    },
                    "required": ["entity_id"]
                }
            },
            {
                "name": "find_path",
                "description": "Find paths between two entities in the graph.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Starting entity ID"
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Destination entity ID"
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum path length",
                            "default": 4
                        }
                    },
                    "required": ["source_id", "target_id"]
                }
            },
            {
                "name": "analyze_impact",
                "description": "Analyze what entities would be affected if a given entity changes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "Entity ID to analyze impact for"
                        }
                    },
                    "required": ["entity_id"]
                }
            },
            {
                "name": "export_graph",
                "description": "Export the knowledge graph in JSON or GraphML format.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["json", "graphml"],
                            "description": "Export format",
                            "default": "json"
                        },
                        "entity_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter to specific entity types"
                        },
                        "relationship_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter to specific relationship types"
                        }
                    },
                    "required": []
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a knowledge graph tool."""
        institution = self.get_institution()
        if not institution:
            return {"error": "No institution found in session"}

        institution_id = institution.id

        if tool_name == "build_graph":
            return self._build_graph(institution, tool_input)
        elif tool_name == "add_entity":
            return self._add_entity(institution_id, tool_input)
        elif tool_name == "add_relationship":
            return self._add_relationship(institution_id, tool_input)
        elif tool_name == "query_graph":
            return self._query_graph(institution_id, tool_input)
        elif tool_name == "get_neighbors":
            return self._get_neighbors(tool_input)
        elif tool_name == "find_path":
            return self._find_path(tool_input)
        elif tool_name == "analyze_impact":
            return self._analyze_impact(tool_input)
        elif tool_name == "export_graph":
            return self._export_graph(institution_id, tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _build_graph(self, institution, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Build the complete knowledge graph."""
        include_standards = tool_input.get("include_standards", True)

        # Get programs from institution
        programs = [p.to_dict() for p in institution.programs]

        # Get standards data if requested
        standards_data = None
        if include_standards and self.workspace_manager:
            try:
                from src.core.standards_store import StandardsStore
                store = StandardsStore()
                # Get standards for institution's accreditor
                accreditor = institution.accrediting_body.value if institution.accrediting_body else "ACCSC"
                standards_data = store.get_standards(accreditor)
            except Exception as e:
                logger.debug("Standards not available for knowledge graph: %s", e)

        result = kg_service.build_graph_from_institution(
            institution_id=institution.id,
            programs=programs,
            standards_data=standards_data
        )

        return result

    def _add_entity(self, institution_id: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Add an entity to the graph."""
        entity = kg_service.add_entity(
            institution_id=institution_id,
            entity_type=tool_input["entity_type"],
            entity_id=tool_input["entity_id"],
            display_name=tool_input["display_name"],
            category=tool_input.get("category"),
            attributes=tool_input.get("attributes")
        )

        return {
            "success": True,
            "entity": entity.to_dict(),
            "message": f"Added entity: {entity.display_name}"
        }

    def _add_relationship(self, institution_id: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Add a relationship to the graph."""
        rel = kg_service.add_relationship(
            institution_id=institution_id,
            source_entity_id=tool_input["source_entity_id"],
            target_entity_id=tool_input["target_entity_id"],
            relationship_type=tool_input["relationship_type"],
            strength=tool_input.get("strength", 1.0)
        )

        return {
            "success": True,
            "relationship": rel.to_dict(),
            "message": f"Added {rel.relationship_type} relationship"
        }

    def _query_graph(self, institution_id: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Query entities in the graph."""
        entities = kg_service.list_entities(
            institution_id=institution_id,
            entity_type=tool_input.get("entity_type"),
            search=tool_input.get("search"),
            limit=tool_input.get("limit", 50)
        )

        return {
            "success": True,
            "entities": [e.to_dict() for e in entities],
            "count": len(entities)
        }

    def _get_neighbors(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get neighbors for an entity."""
        result = kg_service.query_neighbors(
            entity_id=tool_input["entity_id"],
            depth=tool_input.get("depth", 1),
            relationship_types=tool_input.get("relationship_types"),
            direction=tool_input.get("direction", "both")
        )

        return {
            "success": True,
            **result
        }

    def _find_path(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Find paths between entities."""
        paths = kg_service.find_paths(
            source_id=tool_input["source_id"],
            target_id=tool_input["target_id"],
            max_depth=tool_input.get("max_depth", 4)
        )

        return {
            "success": True,
            "paths": [p.to_dict() for p in paths],
            "count": len(paths),
            "shortest_path": paths[0].to_dict() if paths else None
        }

    def _analyze_impact(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze impact of entity changes."""
        result = kg_service.get_entity_impact(
            entity_id=tool_input["entity_id"]
        )

        return {
            "success": True,
            **result.to_dict()
        }

    def _export_graph(self, institution_id: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Export the graph."""
        export_format = tool_input.get("format", "json")

        result = kg_service.export_graph(
            institution_id=institution_id,
            format=export_format
        )

        return {
            "success": True,
            **result
        }
