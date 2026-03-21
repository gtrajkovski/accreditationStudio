"""Reports API Blueprint.

Endpoints for generating and managing compliance reports.
"""

import os
import re
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file, current_app
from datetime import datetime

from src.services.report_service import ReportService
from src.exporters.pdf_exporter import PDFExporter
from src.services.scheduler_service import (
    schedule_report, pause_schedule, resume_schedule, remove_schedule,
    list_schedules, get_schedule, get_delivery_logs
)


reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")
_workspace_manager = None


def init_reports_bp(workspace_manager):
    """Initialize reports blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance
    """
    global _workspace_manager
    _workspace_manager = workspace_manager


@reports_bp.route("/institutions/<institution_id>/compliance", methods=["POST"])
def generate_compliance_report(institution_id: str):
    """Generate compliance report for institution.

    Args:
        institution_id: Institution ID

    Returns:
        JSON with report_id, file_path, download_url
    """
    try:
        # Generate report data
        report_data = ReportService.generate_compliance_report_data(institution_id)

        # Generate PDF
        pdf_bytes = PDFExporter.generate_compliance_report(report_data)

        # Generate report ID
        report_id = f"rpt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Save to workspace
        workspace_dir = os.getenv("WORKSPACE_DIR", "./workspace")
        file_path = PDFExporter.save_to_workspace(
            institution_id,
            pdf_bytes,
            report_id,
            workspace_dir
        )

        # Save metadata to database
        title = f"Compliance Report - {report_data['institution']['name']}"
        file_size = len(pdf_bytes)

        report_id = ReportService.save_report_metadata(
            institution_id=institution_id,
            report_type="compliance",
            title=title,
            file_path=file_path,
            file_size=file_size,
            generated_by=request.args.get("user", "system"),
            metadata={
                "readiness_total": report_data["readiness"]["total"],
                "findings_count": sum(
                    report_data["findings_summary"][s]["count"]
                    for s in ["critical", "high", "medium", "low"]
                ),
            }
        )

        return jsonify({
            "success": True,
            "report_id": report_id,
            "file_path": file_path,
            "download_url": f"/api/reports/{report_id}/download",
        }), 201

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error generating compliance report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to generate report"}), 500


@reports_bp.route("/institutions/<institution_id>", methods=["GET"])
def list_institution_reports(institution_id: str):
    """List reports for institution.

    Query params:
        type: Filter by report type (optional)
        limit: Maximum number of reports (default 20)

    Returns:
        JSON array of report metadata
    """
    try:
        report_type = request.args.get("type")
        limit = int(request.args.get("limit", 20))

        reports = ReportService.list_reports(institution_id, report_type, limit)

        return jsonify({
            "success": True,
            "reports": reports,
            "count": len(reports),
        })

    except Exception as e:
        current_app.logger.error(f"Error listing reports: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to list reports"}), 500


@reports_bp.route("/institutions/<institution_id>/trend", methods=["GET"])
def get_institution_trend(institution_id: str):
    """Get readiness trend for institution.

    Query params:
        days: Number of days to look back (default 30, max 365)

    Returns:
        JSON with trend data points
    """
    try:
        # Parse days parameter with validation
        days = int(request.args.get("days", 30))
        if days < 1:
            return jsonify({"success": False, "error": "days must be at least 1"}), 400
        if days > 365:
            return jsonify({"success": False, "error": "days cannot exceed 365"}), 400

        # Get trend data
        trend = ReportService.get_readiness_trend(institution_id, days)

        return jsonify({
            "success": True,
            "trend": trend,
            "count": len(trend),
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error getting trend: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to get trend"}), 500


@reports_bp.route("/<report_id>", methods=["GET"])
def get_report(report_id: str):
    """Get single report metadata.

    Args:
        report_id: Report ID

    Returns:
        JSON with report metadata
    """
    try:
        report = ReportService.get_report(report_id)

        if not report:
            return jsonify({"success": False, "error": "Report not found"}), 404

        return jsonify({
            "success": True,
            "report": report,
        })

    except Exception as e:
        current_app.logger.error(f"Error getting report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to get report"}), 500


@reports_bp.route("/<report_id>/download", methods=["GET"])
def download_report(report_id: str):
    """Download report PDF file.

    Args:
        report_id: Report ID

    Returns:
        PDF file as attachment
    """
    try:
        report = ReportService.get_report(report_id)

        if not report:
            return jsonify({"success": False, "error": "Report not found"}), 404

        if not report.get("file_path"):
            return jsonify({"success": False, "error": "Report file not found"}), 404

        workspace_dir = os.getenv("WORKSPACE_DIR", "./workspace")
        file_path = Path(workspace_dir) / report["file_path"]

        if not file_path.exists():
            return jsonify({"success": False, "error": "Report file does not exist"}), 404

        # Generate filename from generated_at or use report_id
        if report.get("generated_at"):
            date_str = report["generated_at"][:10]
            filename = f"compliance_report_{date_str}.pdf"
        else:
            filename = f"{report_id}.pdf"

        return send_file(
            file_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to download report"}), 500


@reports_bp.route("/<report_id>", methods=["DELETE"])
def delete_report(report_id: str):
    """Delete report and its file.

    Args:
        report_id: Report ID

    Returns:
        JSON with success status
    """
    try:
        success = ReportService.delete_report(report_id)

        if not success:
            return jsonify({"success": False, "error": "Report not found"}), 404

        return jsonify({
            "success": True,
            "message": "Report deleted successfully",
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to delete report"}), 500


# =============================================================================
# Scheduled Reports Endpoints
# =============================================================================

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email_list(emails):
    """Validate list of email addresses.

    Args:
        emails: List of email addresses

    Returns:
        True if all valid, False otherwise
    """
    return all(EMAIL_REGEX.match(e) for e in emails)


@reports_bp.route("/schedules", methods=["POST"])
def create_schedule():
    """Create new scheduled report.

    Body:
        {
            "institution_id": "inst_123",
            "report_type": "compliance",
            "schedule_type": "daily|weekly|monthly",
            "hour": 8,
            "recipients": ["email1@example.com", "email2@example.com"],
            "day_of_week": 0,  # Optional, for weekly (0=Monday, 6=Sunday)
            "day_of_month": 1  # Optional, for monthly (1-31)
        }

    Returns:
        JSON with schedule_id
    """
    try:
        data = request.get_json()

        # Validate required fields
        required = ["institution_id", "report_type", "schedule_type", "hour", "recipients"]
        for field in required:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

        # Validate schedule_type
        if data["schedule_type"] not in ["daily", "weekly", "monthly"]:
            return jsonify({"success": False, "error": "schedule_type must be daily, weekly, or monthly"}), 400

        # Validate hour
        hour = int(data["hour"])
        if hour < 0 or hour > 23:
            return jsonify({"success": False, "error": "hour must be between 0 and 23"}), 400

        # Validate recipients
        recipients = data["recipients"]
        if not isinstance(recipients, list) or len(recipients) == 0:
            return jsonify({"success": False, "error": "recipients must be a non-empty list"}), 400

        if not validate_email_list(recipients):
            return jsonify({"success": False, "error": "Invalid email address in recipients"}), 400

        # Extract optional fields
        day_of_week = data.get("day_of_week")
        day_of_month = data.get("day_of_month")

        # Validate weekly schedule
        if data["schedule_type"] == "weekly":
            if day_of_week is None:
                return jsonify({"success": False, "error": "day_of_week required for weekly schedules"}), 400
            if day_of_week < 0 or day_of_week > 6:
                return jsonify({"success": False, "error": "day_of_week must be between 0 and 6"}), 400

        # Validate monthly schedule
        if data["schedule_type"] == "monthly":
            if day_of_month is None:
                return jsonify({"success": False, "error": "day_of_month required for monthly schedules"}), 400
            if day_of_month < 1 or day_of_month > 31:
                return jsonify({"success": False, "error": "day_of_month must be between 1 and 31"}), 400

        # Create schedule
        schedule_id = schedule_report(
            institution_id=data["institution_id"],
            report_type=data["report_type"],
            schedule_type=data["schedule_type"],
            hour=hour,
            recipients=recipients,
            day_of_week=day_of_week,
            day_of_month=day_of_month
        )

        return jsonify({
            "success": True,
            "schedule_id": schedule_id,
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error creating schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to create schedule"}), 500


@reports_bp.route("/schedules", methods=["GET"])
def get_schedules():
    """List schedules for institution.

    Query params:
        institution_id: Institution ID (required)

    Returns:
        JSON array of schedules
    """
    try:
        institution_id = request.args.get("institution_id")
        if not institution_id:
            return jsonify({"success": False, "error": "Missing institution_id parameter"}), 400

        schedules = list_schedules(institution_id)

        return jsonify({
            "success": True,
            "schedules": schedules,
            "count": len(schedules),
        })

    except Exception as e:
        current_app.logger.error(f"Error listing schedules: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to list schedules"}), 500


@reports_bp.route("/schedules/<schedule_id>", methods=["GET"])
def get_single_schedule(schedule_id: str):
    """Get single schedule details.

    Args:
        schedule_id: Schedule ID

    Returns:
        JSON with schedule details
    """
    try:
        schedule = get_schedule(schedule_id)

        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        return jsonify({
            "success": True,
            "schedule": schedule,
        })

    except Exception as e:
        current_app.logger.error(f"Error getting schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to get schedule"}), 500


@reports_bp.route("/schedules/<schedule_id>", methods=["PATCH"])
def update_schedule(schedule_id: str):
    """Update schedule.

    Body:
        {
            "recipients": ["..."],  # Optional
            "hour": 9,              # Optional
            "enabled": true         # Optional
        }

    Returns:
        JSON with success status
    """
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        data = request.get_json()

        # If changing schedule timing, we need to remove and re-add the job
        timing_changed = False
        if "hour" in data and data["hour"] != schedule["schedule_hour"]:
            timing_changed = True

        # Update database
        from src.db.connection import get_conn
        conn = get_conn()

        updates = []
        params = []

        if "recipients" in data:
            if not validate_email_list(data["recipients"]):
                return jsonify({"success": False, "error": "Invalid email address in recipients"}), 400
            updates.append("recipients = ?")
            import json
            params.append(json.dumps(data["recipients"]))

        if "hour" in data:
            hour = int(data["hour"])
            if hour < 0 or hour > 23:
                return jsonify({"success": False, "error": "hour must be between 0 and 23"}), 400
            updates.append("schedule_hour = ?")
            params.append(hour)

        if "enabled" in data:
            updates.append("enabled = ?")
            params.append(1 if data["enabled"] else 0)

        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(schedule_id)

            query = f"UPDATE report_schedules SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()

            # If timing changed, re-register job
            if timing_changed:
                remove_schedule(schedule_id)
                # Re-create with new timing
                updated_schedule = get_schedule(schedule_id)
                from src.services.scheduler_service import _add_job_from_schedule
                _add_job_from_schedule(updated_schedule)

        return jsonify({
            "success": True,
            "message": "Schedule updated successfully",
        })

    except Exception as e:
        current_app.logger.error(f"Error updating schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to update schedule"}), 500


@reports_bp.route("/schedules/<schedule_id>/pause", methods=["POST"])
def pause_schedule_endpoint(schedule_id: str):
    """Pause a schedule.

    Args:
        schedule_id: Schedule ID

    Returns:
        JSON with success status
    """
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        pause_schedule(schedule_id)

        return jsonify({
            "success": True,
            "message": "Schedule paused successfully",
        })

    except Exception as e:
        current_app.logger.error(f"Error pausing schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to pause schedule"}), 500


@reports_bp.route("/schedules/<schedule_id>/resume", methods=["POST"])
def resume_schedule_endpoint(schedule_id: str):
    """Resume a paused schedule.

    Args:
        schedule_id: Schedule ID

    Returns:
        JSON with success status
    """
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        resume_schedule(schedule_id)

        return jsonify({
            "success": True,
            "message": "Schedule resumed successfully",
        })

    except Exception as e:
        current_app.logger.error(f"Error resuming schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to resume schedule"}), 500


@reports_bp.route("/schedules/<schedule_id>", methods=["DELETE"])
def delete_schedule(schedule_id: str):
    """Delete a schedule.

    Args:
        schedule_id: Schedule ID

    Returns:
        JSON with success status
    """
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        remove_schedule(schedule_id)

        return jsonify({
            "success": True,
            "message": "Schedule deleted successfully",
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting schedule: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to delete schedule"}), 500


@reports_bp.route("/schedules/<schedule_id>/logs", methods=["GET"])
def get_schedule_logs(schedule_id: str):
    """Get email delivery logs for schedule.

    Args:
        schedule_id: Schedule ID

    Query params:
        limit: Maximum number of logs (default 20)

    Returns:
        JSON array of delivery logs
    """
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            return jsonify({"success": False, "error": "Schedule not found"}), 404

        limit = int(request.args.get("limit", 20))
        logs = get_delivery_logs(schedule_id, limit)

        return jsonify({
            "success": True,
            "logs": logs,
            "count": len(logs),
        })

    except Exception as e:
        current_app.logger.error(f"Error getting schedule logs: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to get schedule logs"}), 500
