"""Batch Schedule API Blueprint.

Provides endpoints for batch schedule management with cron-based automation.
"""

from flask import Blueprint, request, jsonify

from src.services.batch_schedule_service import BatchScheduleService
from src.services.scheduler_service import get_scheduler


# Create Blueprint
batch_schedule_bp = Blueprint('batch_schedule', __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_batch_schedule_bp(workspace_manager):
    """Initialize the batch schedule blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager

    # Register all active schedules on startup
    try:
        scheduler = get_scheduler()
        service = BatchScheduleService(workspace_manager, scheduler)
        count = service.register_all_active_schedules()
        print(f"Registered {count} active batch schedules")
    except Exception as e:
        print(f"Failed to register batch schedules: {e}")

    return batch_schedule_bp


# =============================================================================
# Schedule Endpoints
# =============================================================================

@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules', methods=['GET'])
def list_schedules(institution_id: str):
    """List batch schedules for an institution.

    Query Parameters:
        status: Optional filter (active, paused).
        limit: Maximum schedules (default 50).
        offset: Pagination offset.

    Returns:
        JSON list of schedules.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedules = service.list_schedules(
        institution_id=institution_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "schedules": [s.to_dict() for s in schedules],
        "count": len(schedules),
    }), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules', methods=['POST'])
def create_schedule(institution_id: str):
    """Create a new batch schedule.

    Request Body:
        template_id: Template to execute (required).
        name: Schedule name (required).
        cron_expression: Cron expression for timing (required).

    Returns:
        JSON with created schedule.
    """
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    data = request.get_json() or {}

    # Validate required fields
    if not data.get('template_id'):
        return jsonify({"error": "template_id is required"}), 400
    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400
    if not data.get('cron_expression'):
        return jsonify({"error": "cron_expression is required"}), 400

    service = BatchScheduleService(_workspace_manager, get_scheduler())

    try:
        schedule = service.create_schedule(
            institution_id=institution_id,
            template_id=data['template_id'],
            name=data['name'],
            cron_expression=data['cron_expression'],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(schedule.to_dict()), 201


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>', methods=['GET'])
def get_schedule(institution_id: str, schedule_id: str):
    """Get a batch schedule by ID.

    Returns:
        JSON with schedule details.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    return jsonify(schedule.to_dict()), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>', methods=['PUT'])
def update_schedule(institution_id: str, schedule_id: str):
    """Update a batch schedule.

    Request Body:
        name: Optional new name.
        cron_expression: Optional new cron expression.

    Returns:
        JSON with updated schedule.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    data = request.get_json() or {}

    try:
        updated = service.update_schedule(schedule_id, **data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(updated.to_dict()), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(institution_id: str, schedule_id: str):
    """Delete a batch schedule.

    Returns:
        JSON with deletion confirmation.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    service.delete_schedule(schedule_id)

    return jsonify({"message": "Schedule deleted", "id": schedule_id}), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>/pause', methods=['POST'])
def pause_schedule(institution_id: str, schedule_id: str):
    """Pause a batch schedule.

    Returns:
        JSON with updated schedule.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    updated = service.pause_schedule(schedule_id)

    return jsonify({
        "message": "Schedule paused",
        "schedule": updated.to_dict(),
    }), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>/resume', methods=['POST'])
def resume_schedule(institution_id: str, schedule_id: str):
    """Resume a paused batch schedule.

    Returns:
        JSON with updated schedule.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    if schedule.status != "paused":
        return jsonify({"error": "Schedule is not paused"}), 400

    updated = service.resume_schedule(schedule_id)

    return jsonify({
        "message": "Schedule resumed",
        "schedule": updated.to_dict(),
    }), 200


@batch_schedule_bp.route('/api/institutions/<institution_id>/batch-schedules/<schedule_id>/trigger', methods=['POST'])
def trigger_schedule(institution_id: str, schedule_id: str):
    """Manually trigger a scheduled batch.

    Returns:
        JSON with created batch details.
    """
    service = BatchScheduleService(_workspace_manager, get_scheduler())
    schedule = service.get_schedule(schedule_id)

    if not schedule:
        return jsonify({"error": "Schedule not found"}), 404

    if schedule.institution_id != institution_id:
        return jsonify({"error": "Schedule does not belong to this institution"}), 403

    result = service.trigger_schedule(schedule_id)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({
        "message": "Batch created from schedule",
        **result,
    }), 201
