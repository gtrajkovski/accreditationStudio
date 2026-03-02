"""Evidence Mapper Agent.

Builds the critical "Standard → Evidence" mappings used in self-studies,
responses, and compliance documentation. This is the core work accreditation
teams spend months doing manually.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.EVIDENCE_MAPPER)
class EvidenceMapperAgent(BaseAgent):
    """Evidence Mapper Agent.

    Responsibilities:
    - For each standard requirement, fetch candidate evidence from doc index
    - Rank evidence quality and relevance
    - Identify gaps where evidence is missing
    - Propose exhibit labels
    - Generate crosswalk tables for self-studies

    Outputs:
    - evidence_map.json
    - crosswalk_table.csv/docx
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.EVIDENCE_MAPPER

    @property
    def system_prompt(self) -> str:
        return """You are the Evidence Mapper Agent for AccreditAI.

Your critical mission is to build "Standard → Evidence" mappings that connect
accreditation requirements to documentary evidence in the institution's documents.

For each standard requirement you must:
1. Search the document index for relevant text passages
2. Rank evidence by quality and directness
3. Identify gaps where evidence is weak or missing
4. Propose exhibit labels (e.g., "Exhibit 1.A - Refund Policy")
5. Note page numbers and section references

Your output format should include:
- Standard citation (e.g., "ACCSC Section VII.A.4")
- Requirement text summary
- Evidence found (with document, page, confidence)
- Evidence quality rating (strong/adequate/weak/missing)
- Suggested exhibit label

Always be precise with citations. Never claim evidence exists if you cannot cite it."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "search_evidence",
                "description": "Search document index for evidence matching a requirement",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "requirement_text": {
                            "type": "string",
                            "description": "The requirement text to find evidence for"
                        },
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID to search within"
                        },
                        "doc_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Document types to search (optional filter)"
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "default": 10
                        }
                    },
                    "required": ["requirement_text", "institution_id"]
                }
            },
            {
                "name": "map_standard_to_evidence",
                "description": "Create an evidence mapping for a specific standard",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standard_id": {
                            "type": "string",
                            "description": "Standard section ID"
                        },
                        "standard_text": {
                            "type": "string",
                            "description": "Full text of the standard requirement"
                        },
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID"
                        }
                    },
                    "required": ["standard_id", "standard_text", "institution_id"]
                }
            },
            {
                "name": "generate_crosswalk_table",
                "description": "Generate a crosswalk table for a set of standards",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "standards_id": {
                            "type": "string",
                            "description": "Standards library ID"
                        },
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID"
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["json", "csv", "docx"],
                            "description": "Output format for crosswalk table"
                        }
                    },
                    "required": ["standards_id", "institution_id"]
                }
            },
            {
                "name": "identify_evidence_gaps",
                "description": "Identify standards with weak or missing evidence",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "evidence_map_id": {
                            "type": "string",
                            "description": "ID of existing evidence map to analyze"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Confidence threshold below which to flag gaps",
                            "default": 0.7
                        }
                    },
                    "required": ["evidence_map_id"]
                }
            },
            {
                "name": "save_evidence_map",
                "description": "Save evidence map to workspace",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID"
                        },
                        "evidence_map": {
                            "type": "object",
                            "description": "The evidence map data to save"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Filename for the evidence map"
                        }
                    },
                    "required": ["institution_id", "evidence_map"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an evidence mapper tool."""
        if tool_name == "search_evidence":
            return self._tool_search_evidence(tool_input)
        elif tool_name == "map_standard_to_evidence":
            return self._tool_map_standard_to_evidence(tool_input)
        elif tool_name == "generate_crosswalk_table":
            return self._tool_generate_crosswalk_table(tool_input)
        elif tool_name == "identify_evidence_gaps":
            return self._tool_identify_evidence_gaps(tool_input)
        elif tool_name == "save_evidence_map":
            return self._tool_save_evidence_map(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_search_evidence(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Search for evidence matching a requirement."""
        try:
            from src.search import get_search_service

            institution_id = tool_input.get("institution_id")
            requirement_text = tool_input.get("requirement_text")
            doc_types = tool_input.get("doc_types")
            n_results = tool_input.get("n_results", 10)

            search_service = get_search_service(institution_id)

            # Search with optional doc_type filter
            if doc_types and len(doc_types) == 1:
                results = search_service.search(
                    query=requirement_text,
                    n_results=n_results,
                    doc_type=doc_types[0]
                )
            else:
                results = search_service.search(
                    query=requirement_text,
                    n_results=n_results
                )

            evidence_items = []
            for result in results:
                evidence_items.append({
                    "chunk_id": result.chunk.id,
                    "document_id": result.chunk.document_id,
                    "page_number": result.chunk.page_number,
                    "section_header": result.chunk.section_header,
                    "text": result.chunk.text_anonymized[:500],
                    "relevance_score": result.score,
                    "quality": self._assess_evidence_quality(result.score)
                })

            return {
                "success": True,
                "requirement": requirement_text[:100] + "...",
                "evidence_found": len(evidence_items),
                "evidence": evidence_items
            }

        except Exception as e:
            return {"error": str(e)}

    def _assess_evidence_quality(self, score: float) -> str:
        """Assess evidence quality based on relevance score."""
        if score >= 0.85:
            return "strong"
        elif score >= 0.70:
            return "adequate"
        elif score >= 0.50:
            return "weak"
        return "insufficient"

    def _tool_map_standard_to_evidence(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Create evidence mapping for a standard."""
        standard_id = tool_input.get("standard_id")
        standard_text = tool_input.get("standard_text")
        institution_id = tool_input.get("institution_id")

        # Search for evidence
        search_result = self._tool_search_evidence({
            "requirement_text": standard_text,
            "institution_id": institution_id,
            "n_results": 5
        })

        if "error" in search_result:
            return search_result

        # Determine overall evidence status
        evidence_items = search_result.get("evidence", [])
        if not evidence_items:
            status = "missing"
            confidence = 0.0
        else:
            best_quality = max(e["quality"] for e in evidence_items)
            if best_quality == "strong":
                status = "satisfied"
                confidence = 0.9
            elif best_quality == "adequate":
                status = "partial"
                confidence = 0.7
            else:
                status = "weak"
                confidence = 0.4

        mapping = {
            "standard_id": standard_id,
            "standard_text": standard_text,
            "status": status,
            "confidence": confidence,
            "evidence": evidence_items,
            "suggested_exhibit": f"Exhibit {standard_id}" if evidence_items else None,
            "gap_notes": "Evidence missing or insufficient" if status in ["missing", "weak"] else None
        }

        return {
            "success": True,
            "mapping": mapping
        }

    def _tool_generate_crosswalk_table(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate crosswalk table (stub - returns placeholder)."""
        standards_id = tool_input.get("standards_id")
        institution_id = tool_input.get("institution_id")
        output_format = tool_input.get("output_format", "json")

        # Placeholder - would iterate through all standards and map evidence
        return {
            "success": True,
            "message": "Crosswalk table generation initiated",
            "standards_id": standards_id,
            "institution_id": institution_id,
            "output_format": output_format,
            "status": "pending",
            "note": "Full implementation requires iterating all standards sections"
        }

    def _tool_identify_evidence_gaps(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Identify gaps in evidence mapping (stub)."""
        return {
            "success": True,
            "message": "Gap analysis requires existing evidence map",
            "gaps": [],
            "note": "Run after generating evidence map"
        }

    def _tool_save_evidence_map(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Save evidence map to workspace."""
        import json
        from pathlib import Path
        from src.config import Config

        institution_id = tool_input.get("institution_id")
        evidence_map = tool_input.get("evidence_map")
        filename = tool_input.get("filename", "evidence_map.json")

        # Save to workspace
        output_dir = Config.WORKSPACE_DIR / institution_id / "evidence_maps"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / filename
        with open(output_path, "w") as f:
            json.dump(evidence_map, f, indent=2)

        return {
            "success": True,
            "path": str(output_path),
            "message": f"Evidence map saved to {output_path}"
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run an evidence mapping workflow."""
        if action == "map_all_standards":
            return self._workflow_map_all_standards(inputs)
        elif action == "gap_analysis":
            return self._workflow_gap_analysis(inputs)

        return AgentResult.error(f"Unknown workflow action: {action}")

    def _workflow_map_all_standards(self, inputs: Dict[str, Any]) -> AgentResult:
        """Map all standards to evidence (placeholder)."""
        return AgentResult.success(
            data={"message": "Full standards mapping workflow not yet implemented"},
            confidence=0.5,
            next_actions=[
                {"action": "implement_batch_mapping", "priority": "high"}
            ]
        )

    def _workflow_gap_analysis(self, inputs: Dict[str, Any]) -> AgentResult:
        """Perform gap analysis on evidence mapping."""
        return AgentResult.success(
            data={"message": "Gap analysis workflow not yet implemented"},
            confidence=0.5
        )
