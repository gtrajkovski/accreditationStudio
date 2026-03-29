"""Workbench IDE API endpoints.

Provides endpoints for IDE-mode document workbench with:
- Document content with finding positions
- Remediation preview and apply
- Diff view between original and remediated
"""

import logging
from flask import Blueprint, jsonify, request

from src.services.workbench_ide_service import WorkbenchIDEService

logger = logging.getLogger(__name__)

workbench_ide_bp = Blueprint(
    "workbench_ide",
    __name__,
    url_prefix="/api/institutions/<institution_id>/workbench-ide"
)

_workspace_manager = None


def init_workbench_ide_bp(workspace_manager):
    """Initialize the workbench IDE blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return workbench_ide_bp


def _get_service(institution_id: str) -> WorkbenchIDEService:
    """Get service instance for institution."""
    return WorkbenchIDEService(institution_id, _workspace_manager)


@workbench_ide_bp.route("/documents", methods=["GET"])
def list_documents_with_findings(institution_id: str):
    """List all documents with findings.

    Query Parameters:
        severity: Comma-separated severities (critical,significant,minor)
        status: Comma-separated statuses (compliant,partial,non_compliant)
        limit: Maximum documents to return (default 50)

    Returns:
        JSON list of documents with finding counts.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    severity_filter = None
    if request.args.get("severity"):
        severity_filter = request.args.get("severity").split(",")

    status_filter = None
    if request.args.get("status"):
        status_filter = request.args.get("status").split(",")

    limit = int(request.args.get("limit", 50))

    try:
        service = _get_service(institution_id)
        documents = service.get_documents_with_findings(
            severity_filter=severity_filter,
            status_filter=status_filter,
            limit=limit,
        )
        return jsonify({"documents": documents})
    except Exception as e:
        logger.error("Failed to list documents with findings: %s", e)
        return jsonify({"error": str(e)}), 500


@workbench_ide_bp.route("/documents/<document_id>/ide-view", methods=["GET"])
def get_document_ide_view(institution_id: str, document_id: str):
    """Get document content with finding positions for IDE view.

    Returns:
        JSON with document content, pages, and finding positions.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        service = _get_service(institution_id)
        result = service.get_document_with_findings(document_id)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        logger.error("Failed to get document IDE view: %s", e)
        return jsonify({"error": str(e)}), 500


@workbench_ide_bp.route("/documents/<document_id>/findings/positions", methods=["GET"])
def get_finding_positions(institution_id: str, document_id: str):
    """Get finding positions for a document.

    Returns:
        JSON list of finding positions.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        service = _get_service(institution_id)
        findings = service.get_finding_positions(document_id)
        return jsonify({"findings": findings})
    except Exception as e:
        logger.error("Failed to get finding positions: %s", e)
        return jsonify({"error": str(e)}), 500


@workbench_ide_bp.route("/findings/<finding_id>/preview-fix", methods=["GET"])
def preview_fix(institution_id: str, finding_id: str):
    """Get preview of remediation fix.

    Returns:
        JSON with original text, remediated text, and change description.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        service = _get_service(institution_id)
        preview = service.get_remediation_preview(finding_id)
        if "error" in preview:
            return jsonify(preview), 404
        return jsonify(preview)
    except Exception as e:
        logger.error("Failed to get remediation preview: %s", e)
        return jsonify({"error": str(e)}), 500


@workbench_ide_bp.route("/findings/<finding_id>/apply-fix", methods=["POST"])
def apply_fix(institution_id: str, finding_id: str):
    """Apply remediation fix for a finding.

    Request Body (optional):
        new_text: Override text for the fix.

    Returns:
        JSON with success status and fix details.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}
    new_text = data.get("new_text")

    try:
        service = _get_service(institution_id)
        result = service.apply_fix(finding_id, new_text)
        if not result.get("success"):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logger.error("Failed to apply fix: %s", e)
        return jsonify({"error": str(e), "success": False}), 500


@workbench_ide_bp.route("/documents/<document_id>/diff", methods=["GET"])
def get_document_diff(institution_id: str, document_id: str):
    """Get diff between original and remediated document.

    Returns:
        JSON with original lines, remediated lines, unified diff, and change count.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    try:
        service = _get_service(institution_id)
        diff = service.get_diff(document_id)
        if "error" in diff:
            return jsonify(diff), 404
        return jsonify(diff)
    except Exception as e:
        logger.error("Failed to get document diff: %s", e)
        return jsonify({"error": str(e)}), 500
