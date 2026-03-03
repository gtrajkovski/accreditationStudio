"""Audit API endpoints for AccreditAI.

Provides endpoints for:
- Starting compliance audits on documents
- Monitoring audit progress via SSE
- Retrieving audit results and findings
- Listing audits for an institution
"""

import json
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, Response, stream_with_context

from src.agents.compliance_audit import ComplianceAuditAgent
from src.core.models import AgentSession, AuditStatus, generate_id


# Create Blueprint
audits_bp = Blueprint('audits', __name__)

# Module-level references (set during initialization)
_workspace_manager = None
_active_audits: Dict[str, Dict[str, Any]] = {}  # audit_id -> {session, agent, institution_id}


def init_audits_bp(workspace_manager):
    """Initialize the audits blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return audits_bp


@audits_bp.route('/api/institutions/<institution_id>/audits', methods=['POST'])
def start_audit(institution_id: str):
    """Start a compliance audit on a document.

    Request Body:
        document_id: Document ID to audit (required)
        standards_library_id: Standards library to audit against (required)
            Examples: std_accsc, std_sacscoc, std_hlc, std_abhes, std_coe

    Returns:
        JSON with audit ID and stream URL.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    document_id = data.get('document_id')
    if not document_id:
        return jsonify({"error": "document_id is required"}), 400

    standards_library_id = data.get('standards_library_id')
    if not standards_library_id:
        return jsonify({"error": "standards_library_id is required"}), 400

    # Verify document exists
    doc = None
    for d in institution.documents:
        if d.id == document_id:
            doc = d
            break

    if not doc:
        return jsonify({"error": "Document not found"}), 404

    # Verify standards library exists
    from src.core.standards_store import get_standards_store
    standards_store = get_standards_store()
    library = standards_store.load(standards_library_id)
    if not library:
        return jsonify({"error": f"Standards library not found: {standards_library_id}"}), 404

    # Create session for the audit agent
    session = AgentSession(
        id=generate_id("sess"),
        agent_type="compliance_audit",
        institution_id=institution_id,
    )

    # Create agent
    agent = ComplianceAuditAgent(
        session=session,
        workspace_manager=_workspace_manager,
    )

    # Initialize the audit
    init_result = agent._tool_initialize_audit({
        "institution_id": institution_id,
        "document_id": document_id,
        "standards_library_id": standards_library_id,
    })

    if "error" in init_result:
        return jsonify({"error": init_result["error"]}), 400

    audit_id = init_result["audit_id"]

    # Store in active audits for streaming
    _active_audits[audit_id] = {
        "session": session,
        "agent": agent,
        "institution_id": institution_id,
        "document_id": document_id,
        "standards_library_id": standards_library_id,
    }

    return jsonify({
        "audit_id": audit_id,
        "session_id": session.id,
        "document_id": document_id,
        "document_type": doc.doc_type.value,
        "standards_library_id": standards_library_id,
        "applicable_items": init_result.get("applicable_items_count", 0),
        "stream_url": f"/api/institutions/{institution_id}/audits/{audit_id}/stream",
        "status_url": f"/api/institutions/{institution_id}/audits/{audit_id}",
        "message": "Audit initialized. Use stream_url to run and monitor progress.",
    }), 201


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/stream', methods=['GET'])
def stream_audit(institution_id: str, audit_id: str):
    """Run audit and stream progress via Server-Sent Events.

    This endpoint executes all 5 audit passes and streams progress updates.

    Returns:
        SSE stream of progress updates.
    """
    audit_info = _active_audits.get(audit_id)
    if not audit_info:
        # Try to load from workspace
        return jsonify({"error": "Audit session not found. Start a new audit."}), 404

    agent = audit_info["agent"]

    def generate():
        """Generate SSE events for audit progress."""
        try:
            yield f"data: {json.dumps({'type': 'audit_started', 'audit_id': audit_id})}\n\n"

            # Run Pass 1: Completeness
            yield f"data: {json.dumps({'type': 'pass_started', 'pass': 1, 'name': 'completeness'})}\n\n"
            result1 = agent._tool_completeness_pass({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'pass_completed', 'pass': 1, 'result': result1})}\n\n"

            # Run Pass 2: Standards Analysis
            yield f"data: {json.dumps({'type': 'pass_started', 'pass': 2, 'name': 'standards'})}\n\n"
            result2 = agent._tool_standards_pass({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'pass_completed', 'pass': 2, 'result': result2})}\n\n"

            # Run Pass 3: Consistency
            yield f"data: {json.dumps({'type': 'pass_started', 'pass': 3, 'name': 'consistency'})}\n\n"
            result3 = agent._tool_consistency_pass({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'pass_completed', 'pass': 3, 'result': result3})}\n\n"

            # Run Pass 4: Severity Assessment
            yield f"data: {json.dumps({'type': 'pass_started', 'pass': 4, 'name': 'severity'})}\n\n"
            result4 = agent._tool_assess_severity({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'pass_completed', 'pass': 4, 'result': result4})}\n\n"

            # Run Pass 5: Remediation
            yield f"data: {json.dumps({'type': 'pass_started', 'pass': 5, 'name': 'remediation'})}\n\n"
            result5 = agent._tool_generate_remediation({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'pass_completed', 'pass': 5, 'result': result5})}\n\n"

            # Finalize
            yield f"data: {json.dumps({'type': 'finalizing'})}\n\n"
            final_result = agent._tool_finalize_audit({"audit_id": audit_id})
            yield f"data: {json.dumps({'type': 'audit_completed', 'result': final_result})}\n\n"

            # Clean up active audit
            if audit_id in _active_audits:
                del _active_audits[audit_id]

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/run', methods=['POST'])
def run_audit_sync(institution_id: str, audit_id: str):
    """Run all audit passes synchronously (non-streaming).

    Use this for simpler integrations that don't need real-time updates.

    Returns:
        JSON with complete audit results.
    """
    audit_info = _active_audits.get(audit_id)
    if not audit_info:
        return jsonify({"error": "Audit session not found. Start a new audit."}), 404

    agent = audit_info["agent"]

    try:
        # Run all passes
        result1 = agent._tool_completeness_pass({"audit_id": audit_id})
        result2 = agent._tool_standards_pass({"audit_id": audit_id})
        result3 = agent._tool_consistency_pass({"audit_id": audit_id})
        result4 = agent._tool_assess_severity({"audit_id": audit_id})
        result5 = agent._tool_generate_remediation({"audit_id": audit_id})
        final_result = agent._tool_finalize_audit({"audit_id": audit_id})

        # Clean up
        if audit_id in _active_audits:
            del _active_audits[audit_id]

        return jsonify({
            "success": True,
            "audit_id": audit_id,
            "passes": {
                "completeness": result1,
                "standards": result2,
                "consistency": result3,
                "severity": result4,
                "remediation": result5,
            },
            "final": final_result,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>', methods=['GET'])
def get_audit(institution_id: str, audit_id: str):
    """Get audit results.

    Returns:
        JSON with audit details and findings.
    """
    # Check active audits first
    if audit_id in _active_audits:
        agent = _active_audits[audit_id]["agent"]
        audit = agent._load_audit(audit_id)
        if audit:
            return jsonify(audit.to_dict()), 200

    # Try to load from workspace
    try:
        audit_path = f"audits/{audit_id}.json"
        data = _workspace_manager.read_file(institution_id, audit_path)
        if data:
            audit_data = json.loads(data.decode("utf-8"))
            return jsonify(audit_data), 200
    except Exception:
        pass

    return jsonify({"error": "Audit not found"}), 404


@audits_bp.route('/api/institutions/<institution_id>/audits', methods=['GET'])
def list_audits(institution_id: str):
    """List all audits for an institution.

    Query Parameters:
        document_id: Filter by document (optional)
        status: Filter by status (optional)

    Returns:
        JSON list of audit summaries.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    document_id = request.args.get('document_id')
    status_filter = request.args.get('status')

    audits = []

    # Try to list audit files from workspace
    try:
        institution_path = _workspace_manager.get_institution_path(institution_id)
        if institution_path:
            audits_dir = institution_path / "audits"
            if audits_dir.exists():
                for audit_file in audits_dir.glob("audit_*.json"):
                    try:
                        with open(audit_file, "r") as f:
                            audit_data = json.load(f)

                        # Apply filters
                        if document_id and audit_data.get("document_id") != document_id:
                            continue
                        if status_filter and audit_data.get("status") != status_filter:
                            continue

                        # Create summary
                        audits.append({
                            "id": audit_data.get("id"),
                            "document_id": audit_data.get("document_id"),
                            "standards_library_id": audit_data.get("standards_library_id"),
                            "status": audit_data.get("status"),
                            "summary": audit_data.get("summary", {}),
                            "passes_completed": audit_data.get("passes_completed", 0),
                            "started_at": audit_data.get("started_at"),
                            "completed_at": audit_data.get("completed_at"),
                            "findings_count": len(audit_data.get("findings", [])),
                        })
                    except Exception:
                        continue
    except Exception:
        pass

    # Include active audits
    for audit_id, audit_info in _active_audits.items():
        if audit_info["institution_id"] != institution_id:
            continue
        if document_id and audit_info["document_id"] != document_id:
            continue

        agent = audit_info["agent"]
        audit = agent._load_audit(audit_id)
        if audit:
            if status_filter and audit.status.value != status_filter:
                continue
            audits.append({
                "id": audit.id,
                "document_id": audit.document_id,
                "standards_library_id": audit.standards_library_id,
                "status": audit.status.value,
                "summary": audit.summary,
                "passes_completed": audit.passes_completed,
                "started_at": audit.started_at,
                "completed_at": audit.completed_at,
                "findings_count": len(audit.findings),
            })

    # Sort by started_at (most recent first)
    audits.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    return jsonify(audits), 200


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/findings', methods=['GET'])
def get_audit_findings(institution_id: str, audit_id: str):
    """Get findings for an audit with optional filters.

    Query Parameters:
        status: Filter by compliance status (compliant, partial, non_compliant, na)
        severity: Filter by severity (critical, significant, advisory, informational)

    Returns:
        JSON list of findings.
    """
    status_filter = request.args.get('status')
    severity_filter = request.args.get('severity')

    # Load audit
    audit_data = None

    # Check active audits first
    if audit_id in _active_audits:
        agent = _active_audits[audit_id]["agent"]
        audit = agent._load_audit(audit_id)
        if audit:
            audit_data = audit.to_dict()

    # Try workspace
    if not audit_data:
        try:
            audit_path = f"audits/{audit_id}.json"
            data = _workspace_manager.read_file(institution_id, audit_path)
            if data:
                audit_data = json.loads(data.decode("utf-8"))
        except Exception:
            pass

    if not audit_data:
        return jsonify({"error": "Audit not found"}), 404

    findings = audit_data.get("findings", [])

    # Apply filters
    if status_filter:
        findings = [f for f in findings if f.get("status") == status_filter]
    if severity_filter:
        findings = [f for f in findings if f.get("severity") == severity_filter]

    return jsonify({
        "audit_id": audit_id,
        "total": len(findings),
        "filters": {
            "status": status_filter,
            "severity": severity_filter,
        },
        "findings": findings,
    }), 200


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/findings/<finding_id>', methods=['PATCH'])
def update_finding(institution_id: str, audit_id: str, finding_id: str):
    """Update a finding (human review/override).

    Request Body:
        human_override_status: Override status (compliant, partial, non_compliant, na)
        human_notes: Notes explaining the override

    Returns:
        JSON with updated finding.
    """
    data = request.get_json() or {}

    # Load audit from workspace
    try:
        audit_path = f"audits/{audit_id}.json"
        audit_bytes = _workspace_manager.read_file(institution_id, audit_path)
        if not audit_bytes:
            return jsonify({"error": "Audit not found"}), 404
        audit_data = json.loads(audit_bytes.decode("utf-8"))
    except Exception:
        return jsonify({"error": "Audit not found"}), 404

    # Find and update finding
    finding_updated = False
    for finding in audit_data.get("findings", []):
        if finding.get("id") == finding_id:
            if "human_override_status" in data:
                finding["human_override_status"] = data["human_override_status"]
            if "human_notes" in data:
                finding["human_notes"] = data["human_notes"]
            finding_updated = True
            break

    if not finding_updated:
        return jsonify({"error": "Finding not found"}), 404

    # Save updated audit
    try:
        _workspace_manager.save_file(
            institution_id,
            audit_path,
            json.dumps(audit_data, indent=2).encode("utf-8"),
            create_version=True
        )
    except Exception as e:
        return jsonify({"error": f"Failed to save: {str(e)}"}), 500

    # Return updated finding
    for finding in audit_data.get("findings", []):
        if finding.get("id") == finding_id:
            return jsonify(finding), 200

    return jsonify({"error": "Finding not found after update"}), 500
