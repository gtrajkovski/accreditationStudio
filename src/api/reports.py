"""Reports API Blueprint.

Endpoints for generating and managing compliance reports.
"""

import os
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file, current_app
from datetime import datetime

from src.services.report_service import ReportService
from src.exporters.pdf_exporter import PDFExporter


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
