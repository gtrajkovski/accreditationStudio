"""Bulk Remediation API endpoints.

Provides endpoints for:
- Previewing scope (document counts, findings)
- Creating bulk remediation jobs
- Running jobs with SSE progress streaming
- Pausing/resuming/cancelling jobs
- Approving/rejecting items individually or in batch
"""

import json
import logging
from flask import Blueprint, jsonify, request, Response, stream_with_context

from src.services.bulk_remediation_service import (
    BulkRemediationService,
    BulkRemediationScope,
)

logger = logging.getLogger(__name__)

bulk_remediation_bp = Blueprint(
    "bulk_remediation",
    __name__,
    url_prefix="/api/institutions/<institution_id>/bulk-remediation"
)

_service: BulkRemediationService = None
_workspace_manager = None


def init_bulk_remediation_bp(workspace_manager, remediation_agent=None):
    """Initialize the bulk remediation blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance
        remediation_agent: Optional remediation agent for running remediations
    """
    global _service, _workspace_manager
    _workspace_manager = workspace_manager
    _service = BulkRemediationService(
        remediation_agent=remediation_agent,
        workspace_manager=workspace_manager,
    )
    return bulk_remediation_bp


@bulk_remediation_bp.route("/preview", methods=["POST"])
def preview_scope(institution_id: str):
    """Preview documents affected by scope.

    Request Body:
        scope_type: Type of scope (all, doc_type, program, severity)
        doc_types: List of document types (optional)
        program_ids: List of program IDs (optional)
        severities: List of severity levels (optional)

    Returns:
        JSON with document_count, total_findings, documents list (first 20),
        has_more flag, and all_document_ids.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    scope = BulkRemediationScope(
        scope_type=data.get("scope_type", "all"),
        doc_types=data.get("doc_types", []),
        program_ids=data.get("program_ids", []),
        severities=data.get("severities", [])
    )

    try:
        preview = _service.preview_scope(institution_id, scope)
        return jsonify(preview)
    except Exception as e:
        logger.error("Failed to preview scope: %s", e)
        return jsonify({"error": str(e)}), 500


@bulk_remediation_bp.route("/jobs", methods=["POST"])
def create_job(institution_id: str):
    """Create bulk remediation job.

    Request Body:
        scope_type: Type of scope (all, doc_type, program, severity)
        doc_types: List of document types (optional)
        program_ids: List of program IDs (optional)
        severities: List of severity levels (optional)
        created_by: User identifier (optional)

    Returns:
        JSON with job details including id, status, total_documents.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    scope = BulkRemediationScope(
        scope_type=data.get("scope_type", "all"),
        doc_types=data.get("doc_types", []),
        program_ids=data.get("program_ids", []),
        severities=data.get("severities", [])
    )

    try:
        job = _service.create_job(institution_id, scope, data.get("created_by"))
        return jsonify(job.to_dict()), 201
    except Exception as e:
        logger.error("Failed to create job: %s", e)
        return jsonify({"error": str(e)}), 500


@bulk_remediation_bp.route("/jobs", methods=["GET"])
def list_jobs(institution_id: str):
    """List bulk remediation jobs for an institution.

    Query Parameters:
        status: Filter by status (optional)
        limit: Maximum jobs to return (default 50)
        offset: Pagination offset (default 0)

    Returns:
        JSON with jobs list and pagination info.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    status = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    try:
        result = _service.list_jobs(institution_id, status, limit, offset)
        return jsonify(result)
    except Exception as e:
        logger.error("Failed to list jobs: %s", e)
        return jsonify({"error": str(e)}), 500


@bulk_remediation_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job(institution_id: str, job_id: str):
    """Get job details with items.

    Returns:
        JSON with job details including items list.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Verify job belongs to institution
    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    return jsonify(job)


@bulk_remediation_bp.route("/jobs/<job_id>/stats", methods=["GET"])
def get_job_stats(institution_id: str, job_id: str):
    """Get job statistics.

    Returns:
        JSON with approval stats, completion counts, etc.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    stats = _service.get_job_stats(job_id)
    return jsonify(stats)


@bulk_remediation_bp.route("/jobs/<job_id>/run", methods=["POST"])
def run_job(institution_id: str, job_id: str):
    """Run job with SSE progress.

    Returns:
        SSE stream of progress events.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    if job.get("status") not in ("pending", "paused"):
        return jsonify({"error": f"Job cannot be run (status: {job.get('status')})"}), 400

    def generate():
        """Generate SSE events for job progress."""
        try:
            for event in _service.run_job(job_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error("Error during job execution: %s", e)
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@bulk_remediation_bp.route("/jobs/<job_id>/pause", methods=["POST"])
def pause_job(institution_id: str, job_id: str):
    """Pause running job.

    Returns:
        JSON with success flag.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    success = _service.pause_job(job_id)
    return jsonify({"success": success})


@bulk_remediation_bp.route("/jobs/<job_id>/resume", methods=["POST"])
def resume_job(institution_id: str, job_id: str):
    """Resume paused job.

    Returns:
        JSON with success flag.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    success = _service.resume_job(job_id)
    return jsonify({"success": success})


@bulk_remediation_bp.route("/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(institution_id: str, job_id: str):
    """Cancel a job.

    Returns:
        JSON with success flag.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    success = _service.cancel_job(job_id)
    return jsonify({"success": success})


@bulk_remediation_bp.route("/jobs/<job_id>/approve-all", methods=["POST"])
def approve_all(institution_id: str, job_id: str):
    """Approve all completed items in job.

    Request Body:
        approved_by: User identifier (optional, defaults to "system")

    Returns:
        JSON with approved_count.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    data = request.get_json() or {}
    count = _service.approve_all(job_id, data.get("approved_by", "system"))
    return jsonify({"approved_count": count})


@bulk_remediation_bp.route("/jobs/<job_id>/reject-all", methods=["POST"])
def reject_all(institution_id: str, job_id: str):
    """Reject all completed items in job.

    Request Body:
        approved_by: User identifier (optional, defaults to "system")

    Returns:
        JSON with rejected_count.
    """
    job = _service.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("institution_id") != institution_id:
        return jsonify({"error": "Job does not belong to this institution"}), 403

    data = request.get_json() or {}
    count = _service.reject_all(job_id, data.get("approved_by", "system"))
    return jsonify({"rejected_count": count})


@bulk_remediation_bp.route("/items/<item_id>/approve", methods=["POST"])
def approve_item(institution_id: str, item_id: str):
    """Approve single item.

    Request Body:
        approved_by: User identifier (optional, defaults to "system")

    Returns:
        JSON with success flag.
    """
    data = request.get_json() or {}
    success = _service.approve_item(item_id, data.get("approved_by", "system"))
    return jsonify({"success": success})


@bulk_remediation_bp.route("/items/<item_id>/reject", methods=["POST"])
def reject_item(institution_id: str, item_id: str):
    """Reject single item.

    Request Body:
        approved_by: User identifier (optional, defaults to "system")

    Returns:
        JSON with success flag.
    """
    data = request.get_json() or {}
    success = _service.reject_item(item_id, data.get("approved_by", "system"))
    return jsonify({"success": success})
