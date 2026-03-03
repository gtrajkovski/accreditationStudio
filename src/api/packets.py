"""Packets API blueprint.

Provides REST endpoints for submission packet management:
- Create and manage packets
- Add sections and exhibits
- Validate and export
"""

import json
from flask import Blueprint, request, jsonify, Response

from src.agents.packet_agent import PacketAgent
from src.core.models import AgentSession, generate_id

packets_bp = Blueprint("packets", __name__, url_prefix="/api/institutions/<institution_id>/packets")

# Module-level dependencies (injected by init function)
_workspace_manager = None


def init_packets_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _create_agent(institution_id: str) -> PacketAgent:
    """Create a packet agent instance."""
    session = AgentSession(
        agent_type="packet",
        institution_id=institution_id,
    )
    return PacketAgent(session, workspace_manager=_workspace_manager)


@packets_bp.route("", methods=["GET"])
def list_packets(institution_id: str):
    """List all packets for an institution."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    # List packet files from submissions folder
    packets = []
    inst_path = _workspace_manager.get_institution_path(institution_id)
    submissions_dir = inst_path / "submissions"

    if submissions_dir.exists():
        for f in submissions_dir.glob("pkt_*.json"):
            try:
                data = json.loads(f.read_text())
                packets.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "submission_type": data.get("submission_type"),
                    "accrediting_body": data.get("accrediting_body"),
                    "status": data.get("status"),
                    "total_sections": data.get("total_sections", 0),
                    "total_exhibits": data.get("total_exhibits", 0),
                    "is_valid": data.get("is_valid", False),
                    "created_at": data.get("created_at"),
                })
            except Exception:
                continue

    return jsonify({"packets": packets})


@packets_bp.route("", methods=["POST"])
def create_packet(institution_id: str):
    """Create a new submission packet."""
    data = request.get_json() or {}

    name = data.get("name")
    accrediting_body = data.get("accrediting_body")

    if not name or not accrediting_body:
        return jsonify({"error": "name and accrediting_body are required"}), 400

    agent = _create_agent(institution_id)

    result = agent._tool_create_packet({
        "institution_id": institution_id,
        "name": name,
        "accrediting_body": accrediting_body,
        "submission_type": data.get("submission_type", "response_to_findings"),
        "description": data.get("description", ""),
    })

    if "error" in result:
        return jsonify(result), 400

    # Save immediately
    agent._tool_save({"packet_id": result["packet_id"]})

    return jsonify(result), 201


@packets_bp.route("/<packet_id>", methods=["GET"])
def get_packet(institution_id: str, packet_id: str):
    """Get a specific packet."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not data:
        return jsonify({"error": "Packet not found"}), 404

    return jsonify(data)


@packets_bp.route("/<packet_id>/findings", methods=["POST"])
def load_findings(institution_id: str, packet_id: str):
    """Load findings into a packet."""
    data = request.get_json() or {}
    findings_report_id = data.get("findings_report_id")

    if not findings_report_id:
        return jsonify({"error": "findings_report_id is required"}), 400

    # Load existing packet
    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    # Recreate packet in agent cache
    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_load_findings({
        "packet_id": packet_id,
        "findings_report_id": findings_report_id,
        "severity_filter": data.get("severity_filter", []),
    })

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/sections", methods=["POST"])
def add_section(institution_id: str, packet_id: str):
    """Add a narrative section to a packet."""
    data = request.get_json() or {}

    # Load existing packet
    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_add_narrative({
        "packet_id": packet_id,
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "finding_id": data.get("finding_id", ""),
        "standard_refs": data.get("standard_refs", []),
        "evidence_refs": data.get("evidence_refs", []),
    })

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/exhibits", methods=["POST"])
def add_exhibit(institution_id: str, packet_id: str):
    """Add an exhibit to a packet."""
    data = request.get_json() or {}

    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_add_exhibit({
        "packet_id": packet_id,
        "exhibit_number": data.get("exhibit_number", ""),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "document_id": data.get("document_id", ""),
        "file_path": data.get("file_path", ""),
        "standard_refs": data.get("standard_refs", []),
        "finding_refs": data.get("finding_refs", []),
    })

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/cover", methods=["POST"])
def generate_cover(institution_id: str, packet_id: str):
    """Generate cover page for a packet."""
    data = request.get_json() or {}

    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_generate_cover({
        "packet_id": packet_id,
        "institution_name": data.get("institution_name", ""),
        "submission_date": data.get("submission_date", ""),
        "contact_name": data.get("contact_name", ""),
        "contact_title": data.get("contact_title", ""),
    })

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/validate", methods=["POST"])
def validate_packet(institution_id: str, packet_id: str):
    """Validate a packet for export."""
    data = request.get_json() or {}

    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_validate({
        "packet_id": packet_id,
        "strict": data.get("strict", True),
    })

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/export/docx", methods=["POST"])
def export_docx(institution_id: str, packet_id: str):
    """Export packet as DOCX."""
    data = request.get_json() or {}

    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_export_docx({
        "packet_id": packet_id,
        "include_exhibits": data.get("include_exhibits", False),
    })

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/export/zip", methods=["POST"])
def export_zip(institution_id: str, packet_id: str):
    """Export packet as ZIP folder."""
    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    agent = _create_agent(institution_id)

    from src.core.models import SubmissionPacket
    packet = SubmissionPacket.from_dict(packet_data)
    agent._packet_cache[packet_id] = packet

    result = agent._tool_export_zip({"packet_id": packet_id})

    if "error" in result:
        return jsonify(result), 400

    agent._tool_save({"packet_id": packet_id})
    return jsonify(result)


@packets_bp.route("/<packet_id>/download/<export_type>", methods=["GET"])
def download_export(institution_id: str, packet_id: str, export_type: str):
    """Download exported packet file."""
    if export_type not in ["docx", "zip"]:
        return jsonify({"error": "Invalid export type"}), 400

    packet_data = _workspace_manager.load_file(institution_id, f"submissions/{packet_id}.json")
    if not packet_data:
        return jsonify({"error": "Packet not found"}), 404

    # Get the path
    path_key = "docx_path" if export_type == "docx" else "zip_path"
    file_path = packet_data.get(path_key)

    if not file_path:
        return jsonify({"error": f"No {export_type} export available"}), 404

    file_data = _workspace_manager.load_file(institution_id, file_path)
    if not file_data:
        return jsonify({"error": "Export file not found"}), 404

    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if export_type == "docx" else "application/zip"
    filename = f"{packet_data.get('name', 'packet')}.{export_type}"

    return Response(
        file_data,
        mimetype=mime_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
