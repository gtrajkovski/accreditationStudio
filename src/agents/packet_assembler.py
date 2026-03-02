"""Packet Assembler Agent.

Creates submission packages with cover, TOC, crosswalks, exhibits, and narratives.
"""

from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentResult


@register_agent(AgentType.PACKET_ASSEMBLER)
class PacketAssemblerAgent(BaseAgent):
    """Packet Assembler Agent.

    Generates:
    - Cover page
    - Table of contents
    - Crosswalk table
    - Exhibit list
    - Narrative sections
    - Attachments manifest

    Outputs: DOCX, PDF, ZIP packet
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.PACKET_ASSEMBLER

    @property
    def system_prompt(self) -> str:
        return """You are the Packet Assembler Agent for AccreditAI.

You create professional submission packages for accreditation submissions.

PACKET COMPONENTS:
1. Cover page with institution info and submission type
2. Table of contents with page numbers
3. Crosswalk table (standard → evidence mapping)
4. Exhibit list with labels and descriptions
5. Narrative sections for each issue/standard
6. Attachments manifest

OUTPUT FORMATS:
- .docx for editing
- .pdf for final submission
- .zip with folder structure for large packets"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "assemble_packet",
                "description": "Assemble a submission packet from components",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "submission_type": {
                            "type": "string",
                            "enum": ["self_study", "annual_report", "substantive_change",
                                     "response", "show_cause", "teach_out"]
                        },
                        "include_sections": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "exhibit_list": {
                            "type": "array",
                            "items": {"type": "object"}
                        }
                    },
                    "required": ["institution_id", "submission_type"]
                }
            },
            {
                "name": "generate_crosswalk_table",
                "description": "Generate crosswalk table for packet",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "evidence_map_id": {"type": "string"},
                        "standards_id": {"type": "string"}
                    },
                    "required": ["evidence_map_id"]
                }
            },
            {
                "name": "export_packet",
                "description": "Export assembled packet to file format",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "packet_id": {"type": "string"},
                        "format": {
                            "type": "string",
                            "enum": ["docx", "pdf", "zip"]
                        }
                    },
                    "required": ["packet_id", "format"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a packet assembly tool."""
        if tool_name == "assemble_packet":
            return self._tool_assemble_packet(tool_input)
        elif tool_name == "generate_crosswalk_table":
            return self._tool_generate_crosswalk(tool_input)
        elif tool_name == "export_packet":
            return self._tool_export_packet(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_assemble_packet(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble packet (stub)."""
        return {
            "success": True,
            "message": "Packet assembly requires document generation capabilities",
            "status": "stub",
            "submission_type": tool_input.get("submission_type"),
            "components_needed": [
                "cover_page",
                "table_of_contents",
                "crosswalk_table",
                "exhibit_list",
                "narratives",
                "attachments"
            ]
        }

    def _tool_generate_crosswalk(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Generate crosswalk table (stub)."""
        return {
            "success": True,
            "message": "Crosswalk generation requires evidence map",
            "status": "stub"
        }

    def _tool_export_packet(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Export packet (stub)."""
        return {
            "success": True,
            "message": "Export requires assembled packet",
            "status": "stub",
            "format": tool_input.get("format")
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run a packet assembly workflow."""
        return AgentResult.success(
            data={"message": f"Packet workflow '{action}' not yet implemented"},
            confidence=0.5
        )
