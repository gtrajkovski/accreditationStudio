"""Autopilot API - Scheduled job management with async execution and SSE progress."""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Blueprint, jsonify, request, Response, send_file

from src.config import Config
from src.services.autopilot_service import (
    AutopilotConfig,
    AutopilotRun,
    RunStatus,
    TriggerType,
    create_run,
    get_autopilot_config,
    save_autopilot_config,
    get_run_history,
    get_run,
    get_latest_run,
    update_run,
    execute_autopilot_run,
    schedule_institution,
)


autopilot_bp = Blueprint("autopilot", __name__, url_prefix="/api/autopilot")

_workspace_manager = None

# In-memory progress tracking for SSE
_run_progress: Dict[str, Dict[str, Any]] = {}
_run_progress_lock = threading.Lock()


def init_autopilot_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _update_progress(run_id: str, message: str, percent: int, status: str = "running"):
    """Update progress for a run (thread-safe)."""
    with _run_progress_lock:
        _run_progress[run_id] = {
            "message": message,
            "percent": percent,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _get_progress(run_id: str) -> Optional[Dict[str, Any]]:
    """Get current progress for a run."""
    with _run_progress_lock:
        return _run_progress.get(run_id)


def _clear_progress(run_id: str):
    """Clear progress tracking for a run."""
    with _run_progress_lock:
        _run_progress.pop(run_id, None)


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
    """Manually trigger an autopilot run (synchronous, legacy)."""
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


@autopilot_bp.route("/institutions/<institution_id>/run-now", methods=["POST"])
def run_now(institution_id: str):
    """Trigger an autopilot run asynchronously.

    Returns 202 Accepted immediately with run_id.
    Use SSE endpoint to stream progress.
    """
    from src.db.connection import get_conn

    config = get_autopilot_config(institution_id)

    # Create run record immediately
    conn = get_conn()
    run = create_run(institution_id, TriggerType.MANUAL, conn)

    # Initialize progress tracking
    _update_progress(run.id, "Starting autopilot run...", 0, "running")

    def run_in_background():
        """Execute the autopilot run in background thread."""
        try:
            # Progress callback
            def on_progress(message: str, percent: int):
                _update_progress(run.id, message, percent, "running")

            # Execute
            result = execute_autopilot_run(
                institution_id=institution_id,
                trigger_type=TriggerType.MANUAL,
                config=config,
                workspace_manager=_workspace_manager,
                on_progress=on_progress,
            )

            # Mark complete
            _update_progress(
                run.id,
                "Complete!",
                100,
                "completed" if result.status == RunStatus.COMPLETED else "failed"
            )

        except Exception as e:
            _update_progress(run.id, f"Error: {str(e)}", 100, "error")

    # Start background thread
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()

    return jsonify({
        "run_id": run.id,
        "status": "running",
    }), 202


@autopilot_bp.route("/institutions/<institution_id>/runs/<run_id>/progress", methods=["GET"])
def stream_progress(institution_id: str, run_id: str):
    """Stream autopilot run progress via SSE.

    Events:
      - progress: {"message": "...", "percent": 50}
      - complete: {"run_id": "...", "status": "completed", "score_after": 85}
      - error: {"error": "..."}
    """
    import json
    import time

    def generate():
        last_percent = -1
        timeout_count = 0
        max_timeout = 300  # 5 minutes max

        while timeout_count < max_timeout:
            progress = _get_progress(run_id)

            if progress is None:
                # Check if run exists and is completed
                run = get_run(run_id)
                if run is None:
                    yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                    break
                elif run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
                    # Already completed before we started streaming
                    event_data = {
                        "run_id": run.id,
                        "status": run.status.value if hasattr(run.status, 'value') else run.status,
                        "score_after": run.readiness_score_after,
                    }
                    yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                    break
                else:
                    # Run exists but no progress yet, wait
                    time.sleep(0.5)
                    timeout_count += 0.5
                    continue

            # Send progress if changed
            if progress["percent"] != last_percent:
                last_percent = progress["percent"]

                if progress["status"] in ("completed", "failed", "error"):
                    # Final event
                    if progress["status"] == "error":
                        yield f"event: error\ndata: {json.dumps({'error': progress['message']})}\n\n"
                    else:
                        run = get_run(run_id)
                        event_data = {
                            "run_id": run_id,
                            "status": progress["status"],
                            "score_after": run.readiness_score_after if run else None,
                        }
                        yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"

                    # Clean up progress tracking
                    _clear_progress(run_id)
                    break
                else:
                    # Progress event
                    event_data = {
                        "message": progress["message"],
                        "percent": progress["percent"],
                    }
                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

            time.sleep(0.5)
            timeout_count += 0.5

        # Timeout reached
        if timeout_count >= max_timeout:
            yield f"event: error\ndata: {json.dumps({'error': 'Timeout waiting for run completion'})}\n\n"
            _clear_progress(run_id)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


# =============================================================================
# Brief Retrieval Endpoints
# =============================================================================


def _get_briefs_dir(institution_id: str) -> Path:
    """Get the briefs directory for an institution."""
    workspace_dir = Config.WORKSPACE_DIR
    return Path(workspace_dir) / institution_id / "briefs"


def _list_briefs(institution_id: str, days: int = 30) -> list:
    """List briefs for an institution within a date range.

    Args:
        institution_id: Institution ID
        days: Number of days to look back (default 30)

    Returns:
        List of brief metadata dicts sorted by date descending
    """
    from datetime import timedelta

    briefs_dir = _get_briefs_dir(institution_id)

    if not briefs_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    briefs = []

    for brief_file in briefs_dir.glob("*.md"):
        # Parse date from filename (YYYY-MM-DD.md)
        try:
            date_str = brief_file.stem
            brief_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

            if brief_date >= cutoff:
                # Read first few lines for preview
                content = brief_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                # Extract readiness score from content
                score = None
                for line in lines:
                    if "**" in line and "%" in line:
                        # Find pattern like **75%**
                        import re
                        match = re.search(r"\*\*(\d+)%\*\*", line)
                        if match:
                            score = int(match.group(1))
                            break

                briefs.append({
                    "date": date_str,
                    "file_name": brief_file.name,
                    "size_bytes": brief_file.stat().st_size,
                    "readiness_score": score,
                    "created_at": brief_date.isoformat(),
                })

        except (ValueError, OSError):
            continue

    # Sort by date descending
    briefs.sort(key=lambda b: b["date"], reverse=True)
    return briefs


@autopilot_bp.route("/institutions/<institution_id>/briefs/latest", methods=["GET"])
def get_latest_brief(institution_id: str):
    """Get the most recent morning brief.

    Returns:
        JSON with brief content and metadata, or 404 if none exist
    """
    briefs = _list_briefs(institution_id, days=30)

    if not briefs:
        return jsonify({"error": "No briefs found"}), 404

    latest = briefs[0]
    briefs_dir = _get_briefs_dir(institution_id)
    brief_path = briefs_dir / latest["file_name"]

    try:
        content = brief_path.read_text(encoding="utf-8")
        return jsonify({
            "brief": {
                "date": latest["date"],
                "content": content,
                "readiness_score": latest["readiness_score"],
                "created_at": latest["created_at"],
            }
        })
    except OSError as e:
        return jsonify({"error": f"Failed to read brief: {str(e)}"}), 500


@autopilot_bp.route("/institutions/<institution_id>/briefs", methods=["GET"])
def list_briefs(institution_id: str):
    """List morning briefs for an institution.

    Query params:
        days: Number of days to look back (default 30, max 365)

    Returns:
        JSON with list of brief metadata
    """
    days = request.args.get("days", 30, type=int)
    days = min(max(days, 1), 365)  # Clamp to 1-365

    briefs = _list_briefs(institution_id, days=days)

    return jsonify({
        "briefs": briefs,
        "total": len(briefs),
        "days": days,
    })


@autopilot_bp.route("/institutions/<institution_id>/briefs/<date>/download", methods=["GET"])
def download_brief(institution_id: str, date: str):
    """Download a morning brief as markdown file.

    Args:
        institution_id: Institution ID
        date: Brief date in YYYY-MM-DD format

    Returns:
        Markdown file download
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    briefs_dir = _get_briefs_dir(institution_id)
    brief_path = briefs_dir / f"{date}.md"

    if not brief_path.exists():
        return jsonify({"error": f"Brief not found for {date}"}), 404

    return send_file(
        brief_path,
        mimetype="text/markdown",
        as_attachment=True,
        download_name=f"morning-brief-{date}.md",
    )
