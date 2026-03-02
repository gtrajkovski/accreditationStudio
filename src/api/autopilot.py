"""Autopilot API - Scheduled job management."""

from flask import Blueprint, jsonify, request

from src.services.autopilot_service import (
    AutopilotConfig,
    TriggerType,
    get_autopilot_config,
    save_autopilot_config,
    get_run_history,
    get_run,
    get_latest_run,
    execute_autopilot_run,
    schedule_institution,
)


autopilot_bp = Blueprint("autopilot", __name__, url_prefix="/api/autopilot")

_workspace_manager = None


def init_autopilot_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


@autopilot_bp.route("/institutions/<institution_id>/config", methods=["GET"])
def get_config(institution_id: str):
    """Get autopilot configuration for an institution."""
    config = get_autopilot_config(institution_id)

    if config is None:
        # Return default config
        config = AutopilotConfig(institution_id=institution_id)

    return jsonify(config.to_dict())


@autopilot_bp.route("/institutions/<institution_id>/config", methods=["PUT"])
def update_config(institution_id: str):
    """Update autopilot configuration."""
    data = request.get_json()

    # Get existing or create new
    config = get_autopilot_config(institution_id)
    if config is None:
        config = AutopilotConfig(institution_id=institution_id)

    # Update fields
    if "enabled" in data:
        config.enabled = bool(data["enabled"])
    if "schedule_hour" in data:
        config.schedule_hour = int(data["schedule_hour"]) % 24
    if "schedule_minute" in data:
        config.schedule_minute = int(data["schedule_minute"]) % 60
    if "run_reindex" in data:
        config.run_reindex = bool(data["run_reindex"])
    if "run_consistency" in data:
        config.run_consistency = bool(data["run_consistency"])
    if "run_audit" in data:
        config.run_audit = bool(data["run_audit"])
    if "run_readiness" in data:
        config.run_readiness = bool(data["run_readiness"])
    if "notify_on_complete" in data:
        config.notify_on_complete = bool(data["notify_on_complete"])
    if "notify_on_error" in data:
        config.notify_on_error = bool(data["notify_on_error"])

    # Save config
    save_autopilot_config(config)

    # Update scheduler
    schedule_institution(institution_id, config, _workspace_manager)

    return jsonify({
        "success": True,
        "config": config.to_dict(),
    })


@autopilot_bp.route("/institutions/<institution_id>/run", methods=["POST"])
def trigger_run(institution_id: str):
    """Manually trigger an autopilot run."""
    config = get_autopilot_config(institution_id)

    # Execute the run
    run = execute_autopilot_run(
        institution_id=institution_id,
        trigger_type=TriggerType.MANUAL,
        config=config,
        workspace_manager=_workspace_manager,
    )

    return jsonify({
        "success": True,
        "run": run.to_dict(),
    })


@autopilot_bp.route("/institutions/<institution_id>/history", methods=["GET"])
def get_history(institution_id: str):
    """Get autopilot run history for an institution."""
    limit = request.args.get("limit", 20, type=int)

    runs = get_run_history(institution_id, limit=min(limit, 100))

    return jsonify({
        "runs": [r.to_dict() for r in runs],
        "total": len(runs),
    })


@autopilot_bp.route("/institutions/<institution_id>/latest", methods=["GET"])
def get_latest(institution_id: str):
    """Get the most recent autopilot run."""
    run = get_latest_run(institution_id)

    if run is None:
        return jsonify({"run": None})

    return jsonify({"run": run.to_dict()})


@autopilot_bp.route("/runs/<run_id>", methods=["GET"])
def get_run_details(run_id: str):
    """Get details of a specific run."""
    run = get_run(run_id)

    if run is None:
        return jsonify({"error": "Run not found"}), 404

    return jsonify({"run": run.to_dict()})


@autopilot_bp.route("/status", methods=["GET"])
def get_scheduler_status():
    """Get overall scheduler status."""
    from src.services.autopilot_service import get_scheduler, get_enabled_configs

    scheduler = get_scheduler()
    configs = get_enabled_configs()

    jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

    return jsonify({
        "scheduler_running": scheduler is not None and scheduler.running,
        "enabled_institutions": len(configs),
        "scheduled_jobs": jobs,
    })
