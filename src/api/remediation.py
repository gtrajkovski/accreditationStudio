"""Remediation API endpoints for AccreditAI.

Provides endpoints for:
- Starting document remediation based on audit findings
- Monitoring remediation progress via SSE
- Retrieving remediation results
- Downloading generated documents (redlines, finals)
"""

import json
import logging
import time
from typing import Dict, Any
from flask import Blueprint, request, jsonify, Response, stream_with_context, send_file
from pathlib import Path

logger = logging.getLogger(__name__)

from src.agents.remediation_agent import RemediationAgent
from src.core.models import AgentSession, RemediationStatus, generate_id
from src.services.batch_service import BatchService, estimate_batch_cost


# Create Blueprint
remediation_bp = Blueprint('remediation', __name__)

# Module-level references (set during initialization)
_workspace_manager = None
_active_remediations: Dict[str, Dict[str, Any]] = {}


def init_remediation_bp(workspace_manager):
    """Initialize the remediation blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return remediation_bp


@remediation_bp.route('/api/institutions/<institution_id>/remediations', methods=['POST'])
def start_remediation(institution_id: str):
    """Start document remediation based on audit findings.

    Request Body:
        audit_id: Completed audit ID to remediate (required)
        max_findings: Maximum findings to process (optional, default 20)
        severity_filter: List of severities to include (optional)
            Examples: ["critical", "significant"]

    Returns:
        JSON with remediation ID and stream URL.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    audit_id = data.get('audit_id')
    if not audit_id:
        return jsonify({"error": "audit_id is required"}), 400

    max_findings = data.get('max_findings', 20)
    severity_filter = data.get('severity_filter', [])

    # Verify audit exists
    audit_path = f"audits/{audit_id}.json"
    audit_data = _workspace_manager.read_file(institution_id, audit_path)
    if not audit_data:
        return jsonify({"error": "Audit not found"}), 404

    audit_info = json.loads(audit_data.decode("utf-8"))
    if audit_info.get("status") not in ["completed", "reviewed", "approved"]:
        return jsonify({
            "error": f"Audit not completed. Status: {audit_info.get('status')}"
        }), 400

    # Create session for the remediation agent
    session = AgentSession(
        id=generate_id("sess"),
        agent_type="remediation",
        institution_id=institution_id,
    )

    # Create agent
    agent = RemediationAgent(
        session=session,
        workspace_manager=_workspace_manager,
    )

    # Load findings to initialize
    load_result = agent._tool_load_audit_findings({
        "institution_id": institution_id,
        "audit_id": audit_id,
        "severity_filter": severity_filter,
    })

    if "error" in load_result:
        return jsonify({"error": load_result["error"]}), 400

    remediation_id = load_result["remediation_id"]

    # Store in active remediations for streaming
    _active_remediations[remediation_id] = {
        "session": session,
        "agent": agent,
        "institution_id": institution_id,
        "audit_id": audit_id,
        "max_findings": max_findings,
    }

    return jsonify({
        "remediation_id": remediation_id,
        "session_id": session.id,
        "audit_id": audit_id,
        "document_id": load_result.get("document_id"),
        "findings_to_remediate": load_result.get("findings_needing_remediation", 0),
        "by_severity": load_result.get("by_severity", {}),
        "stream_url": f"/api/institutions/{institution_id}/remediations/{remediation_id}/stream",
        "status_url": f"/api/institutions/{institution_id}/remediations/{remediation_id}",
        "message": "Remediation initialized. Use stream_url to run and monitor progress.",
    }), 201


@remediation_bp.route('/api/institutions/<institution_id>/remediations/<remediation_id>/stream', methods=['GET'])
def stream_remediation(institution_id: str, remediation_id: str):
    """Run remediation and stream progress via Server-Sent Events.

    Returns:
        SSE stream of progress updates.
    """
    remed_info = _active_remediations.get(remediation_id)
    if not remed_info:
        return jsonify({"error": "Remediation session not found. Start a new remediation."}), 404

    agent = remed_info["agent"]
    audit_id = remed_info["audit_id"]
    max_findings = remed_info.get("max_findings", 20)

    def generate():
        """Generate SSE events for remediation progress."""
        try:
            yield f"data: {json.dumps({'type': 'remediation_started', 'remediation_id': remediation_id})}\n\n"

            # Step 1: Generate corrections
            yield f"data: {json.dumps({'type': 'step_started', 'step': 1, 'name': 'generating_corrections'})}\n\n"
            gen_result = agent._tool_generate_all_corrections({
                "institution_id": institution_id,
                "audit_id": audit_id,
                "max_findings": max_findings,
            })
            yield f"data: {json.dumps({'type': 'step_completed', 'step': 1, 'result': gen_result})}\n\n"

            if "error" in gen_result:
                yield f"data: {json.dumps({'type': 'error', 'error': gen_result['error']})}\n\n"
                return

            # Step 2: Apply truth index
            yield f"data: {json.dumps({'type': 'step_started', 'step': 2, 'name': 'applying_truth_index'})}\n\n"
            truth_result = agent._tool_apply_truth_index({
                "institution_id": institution_id,
                "remediation_id": remediation_id,
            })
            yield f"data: {json.dumps({'type': 'step_completed', 'step': 2, 'result': truth_result})}\n\n"

            # Step 3: Create redline document
            yield f"data: {json.dumps({'type': 'step_started', 'step': 3, 'name': 'creating_redline'})}\n\n"
            redline_result = agent._tool_create_redline_document({
                "institution_id": institution_id,
                "remediation_id": remediation_id,
            })
            yield f"data: {json.dumps({'type': 'step_completed', 'step': 3, 'result': redline_result})}\n\n"

            # Step 4: Create final document
            yield f"data: {json.dumps({'type': 'step_started', 'step': 4, 'name': 'creating_final'})}\n\n"
            final_result = agent._tool_create_final_document({
                "institution_id": institution_id,
                "remediation_id": remediation_id,
            })
            yield f"data: {json.dumps({'type': 'step_completed', 'step': 4, 'result': final_result})}\n\n"

            # Step 5: Save remediation
            yield f"data: {json.dumps({'type': 'step_started', 'step': 5, 'name': 'saving'})}\n\n"
            save_result = agent._tool_save_remediation({
                "institution_id": institution_id,
                "remediation_id": remediation_id,
            })
            yield f"data: {json.dumps({'type': 'step_completed', 'step': 5, 'result': save_result})}\n\n"

            yield f"data: {json.dumps({'type': 'remediation_completed', 'result': save_result})}\n\n"

            # Clean up active remediation
            if remediation_id in _active_remediations:
                del _active_remediations[remediation_id]

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


@remediation_bp.route('/api/institutions/<institution_id>/remediations/<remediation_id>/run', methods=['POST'])
def run_remediation_sync(institution_id: str, remediation_id: str):
    """Run all remediation steps synchronously (non-streaming).

    Use this for simpler integrations that don't need real-time updates.

    Returns:
        JSON with complete remediation results.
    """
    remed_info = _active_remediations.get(remediation_id)
    if not remed_info:
        return jsonify({"error": "Remediation session not found. Start a new remediation."}), 404

    agent = remed_info["agent"]
    audit_id = remed_info["audit_id"]
    max_findings = remed_info.get("max_findings", 20)

    try:
        # Run all steps
        gen_result = agent._tool_generate_all_corrections({
            "institution_id": institution_id,
            "audit_id": audit_id,
            "max_findings": max_findings,
        })

        truth_result = agent._tool_apply_truth_index({
            "institution_id": institution_id,
            "remediation_id": remediation_id,
        })

        redline_result = agent._tool_create_redline_document({
            "institution_id": institution_id,
            "remediation_id": remediation_id,
        })

        final_result = agent._tool_create_final_document({
            "institution_id": institution_id,
            "remediation_id": remediation_id,
        })

        save_result = agent._tool_save_remediation({
            "institution_id": institution_id,
            "remediation_id": remediation_id,
        })

        # Clean up
        if remediation_id in _active_remediations:
            del _active_remediations[remediation_id]

        return jsonify({
            "success": True,
            "remediation_id": remediation_id,
            "steps": {
                "corrections": gen_result,
                "truth_index": truth_result,
                "redline": redline_result,
                "final": final_result,
            },
            "result": save_result,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@remediation_bp.route('/api/institutions/<institution_id>/remediations/<remediation_id>', methods=['GET'])
def get_remediation(institution_id: str, remediation_id: str):
    """Get remediation results.

    Returns:
        JSON with remediation details and changes.
    """
    # Check active remediations first
    if remediation_id in _active_remediations:
        agent = _active_remediations[remediation_id]["agent"]
        for cache_key, remed in agent._remediation_cache.items():
            if remed.id == remediation_id:
                return jsonify(remed.to_dict()), 200

    # Try to load from workspace
    try:
        # Look for remediation files
        inst_path = _workspace_manager.get_institution_path(institution_id)
        if inst_path:
            remed_dir = inst_path / "remediations"
            if remed_dir.exists():
                for remed_file in remed_dir.glob("*_remediation.json"):
                    with open(remed_file, "r") as f:
                        remed_data = json.load(f)
                        if remed_data.get("id") == remediation_id:
                            return jsonify(remed_data), 200
    except Exception as e:
        logger.debug("Failed to load remediation %s: %s", remediation_id, e)

    return jsonify({"error": "Remediation not found"}), 404


@remediation_bp.route('/api/institutions/<institution_id>/remediations', methods=['GET'])
def list_remediations(institution_id: str):
    """List all remediations for an institution.

    Query Parameters:
        audit_id: Filter by audit (optional)
        status: Filter by status (optional)

    Returns:
        JSON list of remediation summaries.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    audit_id_filter = request.args.get('audit_id')
    status_filter = request.args.get('status')

    remediations = []

    try:
        inst_path = _workspace_manager.get_institution_path(institution_id)
        if inst_path:
            remed_dir = inst_path / "remediations"
            if remed_dir.exists():
                for remed_file in remed_dir.glob("*_remediation.json"):
                    try:
                        with open(remed_file, "r") as f:
                            remed_data = json.load(f)

                            # Apply filters
                            if audit_id_filter and remed_data.get("audit_id") != audit_id_filter:
                                continue
                            if status_filter and remed_data.get("status") != status_filter:
                                continue

                            remediations.append({
                                "id": remed_data.get("id"),
                                "audit_id": remed_data.get("audit_id"),
                                "document_id": remed_data.get("document_id"),
                                "status": remed_data.get("status"),
                                "findings_addressed": remed_data.get("findings_addressed", 0),
                                "changes_count": len(remed_data.get("changes", [])),
                                "redline_path": remed_data.get("redline_path"),
                                "final_path": remed_data.get("final_path"),
                                "created_at": remed_data.get("created_at"),
                                "completed_at": remed_data.get("completed_at"),
                            })
                    except (json.JSONDecodeError, KeyError):
                        continue
    except Exception as e:
        logger.debug("Failed to list remediations: %s", e)

    # Sort by created_at descending
    remediations.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return jsonify({
        "institution_id": institution_id,
        "total": len(remediations),
        "remediations": remediations,
    }), 200


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch/estimate', methods=['POST'])
def estimate_batch_remediation(institution_id: str):
    """Estimate cost for batch remediation operation.

    Request Body:
        document_ids: List of document IDs (required)
        model: Model to use for pricing (optional, default: claude-sonnet-4-20250514)

    Returns:
        JSON with cost breakdown.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    document_ids = data.get('document_ids', [])
    model = data.get('model', 'claude-sonnet-4-20250514')

    if not document_ids:
        return jsonify({"error": "document_ids is required"}), 400

    # Get document details
    documents = []
    for doc_id in document_ids:
        for doc in institution.documents:
            if doc.id == doc_id:
                documents.append({
                    "id": doc.id,
                    "name": doc.name,
                    "doc_type": doc.doc_type.value,
                })
                break

    if not documents:
        return jsonify({"error": "No valid documents found"}), 404

    # Estimate cost
    estimate = estimate_batch_cost("remediation", documents, model)

    return jsonify(estimate), 200


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch', methods=['POST'])
def start_batch_remediation(institution_id: str):
    """Start a batch remediation operation.

    Request Body:
        document_ids: List of document IDs (required)
        concurrency: Concurrent operations (1-5, default 3)
        confirmed: User confirmed cost (required, must be true)

    Returns:
        JSON with batch ID and stream URL.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    document_ids = data.get('document_ids', [])
    concurrency = data.get('concurrency', 3)
    confirmed = data.get('confirmed', False)

    # Validate
    if not document_ids:
        return jsonify({"error": "document_ids is required"}), 400

    if not confirmed:
        return jsonify({"error": "confirmed must be true"}), 400

    if not (1 <= concurrency <= 5):
        return jsonify({"error": "concurrency must be between 1 and 5"}), 400

    if len(document_ids) > 50:
        return jsonify({"error": "Maximum 50 documents per batch"}), 400

    # Create batch
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.create_batch(
        institution_id=institution_id,
        operation_type="remediation",
        document_ids=document_ids,
        concurrency=concurrency,
    )

    return jsonify({
        "batch_id": batch.id,
        "status": batch.status,
        "document_count": batch.document_count,
        "concurrency": batch.concurrency,
        "stream_url": f"/api/institutions/{institution_id}/remediations/batch/{batch.id}/stream",
        "status_url": f"/api/institutions/{institution_id}/remediations/batch/{batch.id}",
        "cancel_url": f"/api/institutions/{institution_id}/remediations/batch/{batch.id}/cancel",
    }), 201


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch/<batch_id>/stream', methods=['GET'])
def stream_batch_remediation(institution_id: str, batch_id: str):
    """Stream progress for a batch remediation operation.

    Returns:
        SSE stream of batch progress events.
    """
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.get_batch(batch_id)

    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    def generate():
        """Generate SSE events for batch progress."""
        try:
            yield f"data: {json.dumps({'type': 'batch_started', 'batch_id': batch_id})}\n\n"

            # Poll for progress
            last_progress = -1
            while True:
                progress = batch_service.get_progress(batch_id)

                # Emit progress event if changed
                if progress['progress_pct'] != last_progress:
                    yield f"data: {json.dumps({'type': 'progress', **progress})}\n\n"
                    last_progress = progress['progress_pct']

                # Check for item completions
                current_batch = batch_service.get_batch(batch_id)
                if current_batch:
                    for item in current_batch.items:
                        if item.status == 'completed' and not item.metadata.get('emitted'):
                            yield f"data: {json.dumps({'type': 'item_completed', 'item_id': item.id, 'document_id': item.document_id, 'document_name': item.document_name})}\n\n"
                            item.metadata['emitted'] = True
                        elif item.status == 'failed' and not item.metadata.get('emitted'):
                            yield f"data: {json.dumps({'type': 'item_failed', 'item_id': item.id, 'document_id': item.document_id, 'error': item.error})}\n\n"
                            item.metadata['emitted'] = True

                # Check if complete
                if progress['status'] in ('completed', 'cancelled', 'failed'):
                    yield f"data: {json.dumps({'type': 'batch_completed', **progress})}\n\n"
                    break

                time.sleep(1)  # Poll every second

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


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch/<batch_id>/cancel', methods=['POST'])
def cancel_batch_remediation(institution_id: str, batch_id: str):
    """Cancel a batch remediation operation.

    Returns:
        JSON with cancellation summary.
    """
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.get_batch(batch_id)

    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    result = batch_service.cancel_batch(batch_id)

    return jsonify(result), 200


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch/<batch_id>/retry-failed', methods=['POST'])
def retry_failed_remediations(institution_id: str, batch_id: str):
    """Retry failed items from a batch as a new batch.

    Returns:
        JSON with new batch ID.
    """
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.get_batch(batch_id)

    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    # Get failed document IDs
    failed_doc_ids = [
        item.document_id
        for item in batch.items
        if item.status == 'failed'
    ]

    if not failed_doc_ids:
        return jsonify({"error": "No failed items to retry"}), 400

    # Create new batch
    new_batch = batch_service.create_batch(
        institution_id=institution_id,
        operation_type="remediation",
        document_ids=failed_doc_ids,
        concurrency=batch.concurrency,
        parent_batch_id=batch_id,
    )

    return jsonify({
        "new_batch_id": new_batch.id,
        "retrying_count": len(failed_doc_ids),
        "parent_batch_id": batch_id,
        "stream_url": f"/api/institutions/{institution_id}/remediations/batch/{new_batch.id}/stream",
    }), 201


@remediation_bp.route('/api/institutions/<institution_id>/remediations/batch/from-audit/<audit_batch_id>', methods=['POST'])
def chain_from_audit_batch(institution_id: str, audit_batch_id: str):
    """Chain a remediation batch from a completed audit batch.

    Only includes documents with findings_count > 0 from the audit batch.

    Request Body:
        concurrency: Concurrent operations (1-5, default 3)

    Returns:
        JSON with new remediation batch ID.
    """
    batch_service = BatchService(_workspace_manager)
    audit_batch = batch_service.get_batch(audit_batch_id)

    if not audit_batch:
        return jsonify({"error": "Audit batch not found"}), 404

    if audit_batch.institution_id != institution_id:
        return jsonify({"error": "Audit batch does not belong to this institution"}), 403

    if audit_batch.operation_type != "audit":
        return jsonify({"error": "Batch is not an audit batch"}), 400

    if audit_batch.status != "completed":
        return jsonify({"error": "Audit batch not completed"}), 400

    # Get documents with findings
    doc_ids_with_findings = [
        item.document_id
        for item in audit_batch.items
        if item.status == 'completed' and item.findings_count > 0
    ]

    if not doc_ids_with_findings:
        return jsonify({"error": "No documents with findings to remediate"}), 400

    data = request.get_json() or {}
    concurrency = data.get('concurrency', 3)

    # Create remediation batch
    remed_batch = batch_service.create_batch(
        institution_id=institution_id,
        operation_type="remediation",
        document_ids=doc_ids_with_findings,
        concurrency=concurrency,
        parent_batch_id=audit_batch_id,
    )

    return jsonify({
        "batch_id": remed_batch.id,
        "document_count": len(doc_ids_with_findings),
        "chained_from": audit_batch_id,
        "stream_url": f"/api/institutions/{institution_id}/remediations/batch/{remed_batch.id}/stream",
    }), 201


@remediation_bp.route('/api/institutions/<institution_id>/remediations/<remediation_id>/download/<doc_type>', methods=['GET'])
def download_remediation_document(institution_id: str, remediation_id: str, doc_type: str):
    """Download a generated remediation document.

    Args:
        doc_type: 'redline' or 'final'

    Returns:
        DOCX file download.
    """
    if doc_type not in ['redline', 'final']:
        return jsonify({"error": "doc_type must be 'redline' or 'final'"}), 400

    # Find the remediation
    remed_data = None
    try:
        inst_path = _workspace_manager.get_institution_path(institution_id)
        if inst_path:
            remed_dir = inst_path / "remediations"
            if remed_dir.exists():
                for remed_file in remed_dir.glob("*_remediation.json"):
                    with open(remed_file, "r") as f:
                        data = json.load(f)
                        if data.get("id") == remediation_id:
                            remed_data = data
                            break
    except Exception as e:
        logger.debug("Failed to find remediation %s for download: %s", remediation_id, e)

    if not remed_data:
        return jsonify({"error": "Remediation not found"}), 404

    # Get the file path
    if doc_type == 'redline':
        file_path = remed_data.get("redline_path")
    else:
        file_path = remed_data.get("final_path")

    if not file_path:
        return jsonify({"error": f"No {doc_type} document available"}), 404

    # Build full path
    inst_path = _workspace_manager.get_institution_path(institution_id)
    full_path = inst_path / file_path

    if not full_path.exists():
        return jsonify({"error": "Document file not found"}), 404

    return send_file(
        full_path,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=full_path.name,
    )
