"""Standards Librarian Agent.

Maintains the standards corpus and checklists for accreditation compliance.
Parses accreditor standards into hierarchical trees, manages versions,
and creates checklist packs per deliverable type.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.STANDARDS_LIBRARIAN)
class StandardsLibrarianAgent(BaseAgent):
    """Standards Librarian Agent.

    Responsibilities:
    - Parse accreditor standards into tree + requirements
    - Manage versions (year/edition)
    - Create checklist packs per deliverable type
    - Support ACCSC, HLC, SACSCOC, ABHES, COE presets
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.STANDARDS_LIBRARIAN

    @property
    def system_prompt(self) -> str:
        return """You are the Standards Librarian Agent for AccreditAI.

Your responsibilities:
1. Parse and organize accreditation standards into hierarchical structures
2. Manage standards versions and effective dates
3. Create document-specific checklist packs
4. Map requirements to document types (catalog, enrollment agreement, etc.)

You have access to the standards library and can:
- List available standards by accreditor
- Get section hierarchy for a standards set
- Create checklist packs for specific document audits
- Search standards by keyword or requirement type

Always cite specific standard sections when referencing requirements.
Format responses with clear section numbers and requirement text."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "list_standards",
                "description": "List all available standards libraries",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "accreditor": {
                            "type": "string",
                            "description": "Filter by accrediting body (ACCSC, HLC, etc.)"
                        }
                    }
                }
            },
            {
                "name": "get_standards_tree",
                "description": "Get the hierarchical section tree for a standards library",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standards_id": {
                            "type": "string",
                            "description": "ID of the standards library"
                        }
                    },
                    "required": ["standards_id"]
                }
            },
            {
                "name": "create_checklist_pack",
                "description": "Create a checklist pack for a specific document type",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standards_id": {
                            "type": "string",
                            "description": "ID of the standards library"
                        },
                        "document_type": {
                            "type": "string",
                            "description": "Type of document (catalog, enrollment_agreement, etc.)"
                        }
                    },
                    "required": ["standards_id", "document_type"]
                }
            },
            {
                "name": "search_standards",
                "description": "Search standards by keyword or requirement text",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "accreditor": {
                            "type": "string",
                            "description": "Filter by accrediting body"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a standards librarian tool."""
        if tool_name == "list_standards":
            return self._tool_list_standards(tool_input)
        elif tool_name == "get_standards_tree":
            return self._tool_get_standards_tree(tool_input)
        elif tool_name == "create_checklist_pack":
            return self._tool_create_checklist_pack(tool_input)
        elif tool_name == "search_standards":
            return self._tool_search_standards(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_list_standards(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """List available standards libraries."""
        from src.core.standards_store import StandardsStore

        store = StandardsStore()
        accreditor = tool_input.get("accreditor")

        libraries = store.list_standards(accreditor)
        return {
            "success": True,
            "standards": [lib.to_dict() for lib in libraries],
            "count": len(libraries)
        }

    def _tool_get_standards_tree(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get hierarchical section tree."""
        from src.core.standards_store import StandardsStore

        store = StandardsStore()
        standards_id = tool_input.get("standards_id")

        library = store.get_standards(standards_id)
        if not library:
            return {"error": f"Standards library not found: {standards_id}"}

        tree = store.get_section_tree(standards_id)
        return {
            "success": True,
            "standards_id": standards_id,
            "name": library.name,
            "tree": tree
        }

    def _tool_create_checklist_pack(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create a checklist pack for document type."""
        from src.core.standards_store import StandardsStore

        store = StandardsStore()
        standards_id = tool_input.get("standards_id")
        doc_type = tool_input.get("document_type")

        items = store.get_checklist_items(standards_id, applies_to=doc_type)
        return {
            "success": True,
            "standards_id": standards_id,
            "document_type": doc_type,
            "checklist_items": [item.to_dict() for item in items],
            "count": len(items)
        }

    def _tool_search_standards(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Search standards by keyword."""
        from src.core.standards_store import StandardsStore

        store = StandardsStore()
        query = tool_input.get("query", "")
        accreditor = tool_input.get("accreditor")

        # Get all libraries matching accreditor
        libraries = store.list_standards(accreditor)

        results = []
        for lib in libraries:
            # Search sections
            for section in lib.sections:
                if query.lower() in section.title.lower() or query.lower() in section.text.lower():
                    results.append({
                        "type": "section",
                        "standards_id": lib.id,
                        "accreditor": lib.accrediting_body.value,
                        "section_number": section.number,
                        "title": section.title,
                        "text_preview": section.text[:200] + "..." if len(section.text) > 200 else section.text
                    })

            # Search checklist items
            for item in lib.checklist_items:
                if query.lower() in item.description.lower():
                    results.append({
                        "type": "checklist_item",
                        "standards_id": lib.id,
                        "accreditor": lib.accrediting_body.value,
                        "item_number": item.number,
                        "description": item.description,
                        "section_reference": item.section_reference
                    })

        return {
            "success": True,
            "query": query,
            "results": results[:50],  # Limit results
            "count": len(results)
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a standards librarian workflow.

        Args:
            action: The workflow action to perform.
            inputs: Workflow inputs.

        Returns:
            AgentResult with workflow output.
        """
        if action == "create_audit_checklist":
            return self._workflow_create_audit_checklist(inputs)
        elif action == "compare_versions":
            return self._workflow_compare_versions(inputs)

        return AgentResult.error(f"Unknown workflow action: {action}")

    def _workflow_create_audit_checklist(self, inputs: Dict[str, Any]) -> AgentResult:
        """Create a complete audit checklist for a document."""
        standards_id = inputs.get("standards_id")
        doc_type = inputs.get("document_type")

        result = self._tool_create_checklist_pack({
            "standards_id": standards_id,
            "document_type": doc_type
        })

        if "error" in result:
            return AgentResult.error(result["error"])

        return AgentResult.success(
            data=result,
            confidence=1.0,
            citations=[{
                "type": "standards_library",
                "id": standards_id,
                "description": f"Checklist for {doc_type}"
            }]
        )

    def _workflow_compare_versions(self, inputs: Dict[str, Any]) -> AgentResult:
        """Compare two versions of standards (stub)."""
        return AgentResult.success(
            data={"message": "Version comparison not yet implemented"},
            confidence=0.5
        )
