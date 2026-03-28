"""Batch Queue API Blueprint.

Provides endpoints for:
- Real-time queue monitoring
- Batch template CRUD and execution
"""

from flask import Blueprint, request, jsonify

from src.services.batch_queue_service import BatchQueueService
from src.services.batch_template_service import BatchTemplateService


# Create Blueprint
batch_queue_bp = Blueprint('batch_queue', __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_batch_queue_bp(workspace_manager):
    """Initialize the batch queue blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return batch_queue_bp


# =============================================================================
# Queue Monitoring Endpoints
# =============================================================================

@batch_queue_bp.route('/api/batches/queue/status', methods=['GET'])
def get_queue_status():
    """Get global queue status across all institutions.

    Query Parameters:
        institution_id: Optional filter by institution.

    Returns:
        JSON with status counts, queue depth, and active batches.
    """
    institution_id = request.args.get('institution_id')
    service = BatchQueueService(institution_id)
    return jsonify(service.get_queue_status()), 200


@batch_queue_bp.route('/api/batches/queue/activity', methods=['GET'])
def get_recent_activity():
    """Get recent batch activity.

    Query Parameters:
        institution_id: Optional filter by institution.
        limit: Maximum items (default 10, max 50).

    Returns:
        JSON list of recent batch summaries.
    """
    institution_id = request.args.get('institution_id')
    limit = min(int(request.args.get('limit', 10)), 50)

    service = BatchQueueService(institution_id)
    activity = service.get_recent_activity(limit)

    return jsonify({"activity": activity}), 200


# =============================================================================
# Template Endpoints
# =============================================================================

@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates', methods=['GET'])
def list_templates(institution_id: str):
    """List batch templates for an institution.

    Query Parameters:
        operation_type: Optional filter (audit, remediation).
        limit: Maximum templates (default 50).
        offset: Pagination offset.

    Returns:
        JSON list of templates.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    operation_type = request.args.get('operation_type')
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    service = BatchTemplateService(_workspace_manager)
    templates = service.list_templates(
        institution_id=institution_id,
        operation_type=operation_type,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "templates": [t.to_dict() for t in templates],
        "count": len(templates),
    }), 200


@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates', methods=['POST'])
def create_template(institution_id: str):
    """Create a new batch template.

    Request Body:
        name: Template name (required).
        operation_type: "audit" or "remediation" (required).
        document_ids: List of document IDs (required).
        description: Optional description.
        concurrency: Concurrency level 1-5 (default 1).

    Returns:
        JSON with created template.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    # Validate required fields
    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400
    if not data.get('operation_type'):
        return jsonify({"error": "operation_type is required"}), 400
    if data['operation_type'] not in ('audit', 'remediation'):
        return jsonify({"error": "operation_type must be 'audit' or 'remediation'"}), 400
    if not data.get('document_ids') or not isinstance(data['document_ids'], list):
        return jsonify({"error": "document_ids must be a non-empty list"}), 400

    service = BatchTemplateService(_workspace_manager)
    template = service.create_template(
        institution_id=institution_id,
        name=data['name'],
        operation_type=data['operation_type'],
        document_ids=data['document_ids'],
        description=data.get('description', ''),
        concurrency=data.get('concurrency', 1),
    )

    return jsonify(template.to_dict()), 201


@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates/<template_id>', methods=['GET'])
def get_template(institution_id: str, template_id: str):
    """Get a batch template by ID.

    Returns:
        JSON with template details.
    """
    service = BatchTemplateService(_workspace_manager)
    template = service.get_template(template_id)

    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.institution_id != institution_id:
        return jsonify({"error": "Template does not belong to this institution"}), 403

    return jsonify(template.to_dict()), 200


@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates/<template_id>', methods=['PUT'])
def update_template(institution_id: str, template_id: str):
    """Update a batch template.

    Request Body:
        name: Optional new name.
        description: Optional new description.
        document_ids: Optional new document list.
        concurrency: Optional new concurrency.

    Returns:
        JSON with updated template.
    """
    service = BatchTemplateService(_workspace_manager)
    template = service.get_template(template_id)

    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.institution_id != institution_id:
        return jsonify({"error": "Template does not belong to this institution"}), 403

    data = request.get_json() or {}
    updated = service.update_template(template_id, **data)

    return jsonify(updated.to_dict()), 200


@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates/<template_id>', methods=['DELETE'])
def delete_template(institution_id: str, template_id: str):
    """Delete a batch template.

    Returns:
        JSON with deletion confirmation.
    """
    service = BatchTemplateService(_workspace_manager)
    template = service.get_template(template_id)

    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.institution_id != institution_id:
        return jsonify({"error": "Template does not belong to this institution"}), 403

    service.delete_template(template_id)

    return jsonify({"message": "Template deleted", "id": template_id}), 200


@batch_queue_bp.route('/api/institutions/<institution_id>/batch-templates/<template_id>/execute', methods=['POST'])
def execute_template(institution_id: str, template_id: str):
    """Execute a template to create a new batch operation.

    Returns:
        JSON with created batch details.
    """
    service = BatchTemplateService(_workspace_manager)
    template = service.get_template(template_id)

    if not template:
        return jsonify({"error": "Template not found"}), 404

    if template.institution_id != institution_id:
        return jsonify({"error": "Template does not belong to this institution"}), 403

    result = service.execute_template(template_id)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({
        "message": "Batch created from template",
        **result,
    }), 201


# =============================================================================
# Priority Endpoints
# =============================================================================

@batch_queue_bp.route('/api/institutions/<institution_id>/batches/<batch_id>/priority', methods=['PATCH'])
def update_batch_priority(institution_id: str, batch_id: str):
    """Update priority of a batch.

    Request Body:
        priority_level: New priority (1=critical, 2=high, 3=normal, 4=low).

    Returns:
        JSON with updated priority info.
    """
    from src.services.batch_service import BatchService

    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    if 'priority_level' not in data:
        return jsonify({"error": "priority_level is required"}), 400

    try:
        priority_level = int(data['priority_level'])
    except (TypeError, ValueError):
        return jsonify({"error": "priority_level must be an integer"}), 400

    if priority_level < 1 or priority_level > 4:
        return jsonify({"error": "priority_level must be 1-4"}), 400

    batch_service = BatchService(_workspace_manager)

    # Verify batch belongs to institution
    batch = batch_service.get_batch(batch_id)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    result = batch_service.update_priority(batch_id, priority_level)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({
        "message": "Priority updated",
        **result,
    }), 200
