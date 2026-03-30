"""Audit API endpoints for AccreditAI.

Provides endpoints for:
- Starting compliance audits on documents
- Monitoring audit progress via SSE
- Retrieving audit results and findings
- Listing audits for an institution
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app, g

logger = logging.getLogger(__name__)

from src.agents.compliance_audit import ComplianceAuditAgent
from src.core.models import AgentSession, AuditStatus, generate_id
from src.services.batch_service import BatchService, estimate_batch_cost
from src.services.audit_reproducibility_service import (
    get_audit_snapshot,
    verify_audit_reproducibility,
)
from src.services import activity_service


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


def _require_compliance_officer(f):
    """Helper to check compliance_officer role."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import current_app, g, jsonify
        if not current_app.config.get('AUTH_ENABLED', True):
            return f(*args, **kwargs)
        user = g.get('current_user')
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        role = user.get('role', 'viewer')
        allowed_roles = {'compliance_officer', 'admin', 'owner'}
        if role not in allowed_roles:
            return jsonify({'error': 'Insufficient permissions'}), 403
        return f(*args, **kwargs)
    return decorated


@audits_bp.route('/api/institutions/<institution_id>/audits', methods=['POST'])
@_require_compliance_officer
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

    # Log activity
    user = g.get('current_user')
    if user:
        activity_service.log_activity(
            user_id=user.get('id'),
            user_name=user.get('name') or user.get('email'),
            institution_id=institution_id,
            action='audit.start',
            entity_type='audit',
            entity_id=audit_id,
            details=f"Started audit on document {document_id}",
            ip_address=request.remote_addr
        )

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
@_require_compliance_officer
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

        # Log activity
        user = g.get('current_user')
        if user:
            activity_service.log_activity(
                user_id=user.get('id'),
                user_name=user.get('name') or user.get('email'),
                institution_id=institution_id,
                action='audit.complete',
                entity_type='audit',
                entity_id=audit_id,
                details=f"Completed audit",
                ip_address=request.remote_addr
            )

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


@audits_bp.route('/api/institutions/<institution_id>/audits/batch/estimate', methods=['POST'])
@_require_compliance_officer
def estimate_batch_audit(institution_id: str):
    """Estimate cost for batch audit operation.

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
    estimate = estimate_batch_cost("audit", documents, model)

    return jsonify(estimate), 200


@audits_bp.route('/api/institutions/<institution_id>/audits/batch', methods=['POST'])
@_require_compliance_officer
def start_batch_audit(institution_id: str):
    """Start a batch audit operation.

    Request Body:
        document_ids: List of document IDs (required)
        concurrency: Concurrent operations (1-5, default 3)
        confirmed: User confirmed cost (required, must be true)
        standards_library_id: Standards library to audit against (required)

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
    standards_library_id = data.get('standards_library_id')

    # Validate
    if not document_ids:
        return jsonify({"error": "document_ids is required"}), 400

    if not confirmed:
        return jsonify({"error": "confirmed must be true"}), 400

    if not standards_library_id:
        return jsonify({"error": "standards_library_id is required"}), 400

    if not (1 <= concurrency <= 5):
        return jsonify({"error": "concurrency must be between 1 and 5"}), 400

    if len(document_ids) > 50:
        return jsonify({"error": "Maximum 50 documents per batch"}), 400

    # Create batch
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.create_batch(
        institution_id=institution_id,
        operation_type="audit",
        document_ids=document_ids,
        concurrency=concurrency,
    )

    # Store standards_library_id in metadata
    batch.metadata['standards_library_id'] = standards_library_id

    return jsonify({
        "batch_id": batch.id,
        "status": batch.status,
        "document_count": batch.document_count,
        "concurrency": batch.concurrency,
        "stream_url": f"/api/institutions/{institution_id}/audits/batch/{batch.id}/stream",
        "status_url": f"/api/institutions/{institution_id}/audits/batch/{batch.id}",
        "cancel_url": f"/api/institutions/{institution_id}/audits/batch/{batch.id}/cancel",
    }), 201


@audits_bp.route('/api/institutions/<institution_id>/audits/batch/<batch_id>/stream', methods=['GET'])
def stream_batch_audit(institution_id: str, batch_id: str):
    """Stream progress for a batch audit operation.

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


@audits_bp.route('/api/institutions/<institution_id>/audits/batch/<batch_id>/cancel', methods=['POST'])
@_require_compliance_officer
def cancel_batch_audit(institution_id: str, batch_id: str):
    """Cancel a batch audit operation.

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


@audits_bp.route('/api/institutions/<institution_id>/audits/batch/<batch_id>/retry-failed', methods=['POST'])
@_require_compliance_officer
def retry_failed_audits(institution_id: str, batch_id: str):
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
        operation_type="audit",
        document_ids=failed_doc_ids,
        concurrency=batch.concurrency,
        parent_batch_id=batch_id,
    )

    # Copy metadata
    new_batch.metadata = batch.metadata.copy()

    return jsonify({
        "new_batch_id": new_batch.id,
        "retrying_count": len(failed_doc_ids),
        "parent_batch_id": batch_id,
        "stream_url": f"/api/institutions/{institution_id}/audits/batch/{new_batch.id}/stream",
    }), 201


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
    except Exception as e:
        logger.debug("Failed to load audit %s: %s", audit_id, e)

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
                    except Exception as e:
                        logger.debug("Failed to parse audit file %s: %s", audit_file.name, e)
                        continue
    except Exception as e:
        logger.debug("Failed to list audits directory: %s", e)

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
        except Exception as e:
            logger.debug("Failed to load audit %s for findings: %s", audit_id, e)

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


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/reproducibility', methods=['GET'])
def get_audit_reproducibility(institution_id: str, audit_id: str):
    """Get reproducibility bundle for an audit.

    Returns complete audit context: model, prompts, document hashes, standards.

    Query Parameters:
        include_prompts: Include full prompt text (default: false, returns hashes only)
        verify: Check if audit can be reproduced with current state (default: false)

    Returns:
        JSON with reproducibility bundle and optional verification status.
    """
    include_prompts = request.args.get('include_prompts', 'false').lower() == 'true'
    verify = request.args.get('verify', 'false').lower() == 'true'

    # Get snapshot
    snapshot = get_audit_snapshot(audit_id)
    if not snapshot:
        return jsonify({"error": "Reproducibility data not found for this audit"}), 404

    # Build response (per D-05, D-06)
    result = {
        "audit_id": audit_id,
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at,

        # Executive summary (D-06)
        "summary": {
            "model": snapshot.model_id,
            "model_version": snapshot.model_version,
            "accreditor": snapshot.accreditor_code,
            "confidence_threshold": snapshot.confidence_threshold,
            "document_count": len(snapshot.document_hashes),
        },

        # Technical detail (shown when D-05 toggle enabled)
        "technical": {
            "system_prompt_hash": snapshot.system_prompt_hash,
            "tool_definitions_hash": snapshot.tool_definitions_hash,
            "document_hashes": snapshot.document_hashes,
            "truth_index_hash": snapshot.truth_index_hash,
            "agent_config": snapshot.agent_config,
        },
    }

    # Include full prompts if requested (D-07)
    if include_prompts:
        result["technical"]["system_prompt"] = snapshot.system_prompt

    # Verify reproducibility if requested (D-11, D-13)
    if verify:
        verification = verify_audit_reproducibility(audit_id)
        result["verification"] = verification
        if not verification["verified"]:
            result["warning"] = "Audit may not reproduce identically - see discrepancies"

    return jsonify(result), 200


@audits_bp.route('/api/institutions/<institution_id>/audits/<audit_id>/findings/<finding_id>/provenance', methods=['GET'])
def get_finding_provenance(institution_id: str, audit_id: str, finding_id: str):
    """Get provenance data for a specific finding.

    Returns the prompt, response, and reasoning that produced this finding.
    """
    from src.db.connection import get_conn

    conn = get_conn()
    cursor = conn.execute("""
        SELECT fp.*, asp.model_id
        FROM finding_provenance fp
        JOIN audit_snapshots asp ON fp.audit_snapshot_id = asp.id
        WHERE asp.audit_run_id = ?
          AND fp.finding_id LIKE ?
    """, (audit_id, f"%{finding_id}%"))

    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "Provenance not found"}), 404

    return jsonify({
        "finding_id": finding_id,
        "model": row["model_id"],
        "prompt_hash": row["prompt_hash"],
        "response_hash": row["response_hash"],
        "prompt_text": row["prompt_text"],
        "response_text": row["response_text"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "evidence_hashes": json.loads(row["evidence_chunk_hashes"] or "[]"),
        "reasoning_steps": json.loads(row["reasoning_steps"] or "[]"),
    }), 200
