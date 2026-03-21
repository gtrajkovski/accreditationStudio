"""PDF Exporter for Compliance Reports.

Uses WeasyPrint to generate PDFs from HTML templates.
"""

import os
from pathlib import Path
from typing import Dict, Any
from flask import render_template
from weasyprint import HTML

from src.exporters.chart_generator import ChartGenerator


class PDFExporter:
    """Exports compliance reports to PDF format."""

    @staticmethod
    def generate_compliance_report(data: Dict[str, Any]) -> bytes:
        """Generate compliance report PDF from data.

        Args:
            data: Report data dict from ReportService.generate_compliance_report_data()

        Returns:
            PDF bytes
        """
        # Generate charts as base64 strings
        readiness_chart = ChartGenerator.generate_readiness_chart(data["readiness"])
        findings_chart = ChartGenerator.generate_findings_bar_chart(data["findings_summary"])

        # Add charts to data
        data["charts"] = {
            "readiness": readiness_chart,
            "findings": findings_chart,
        }

        # Render HTML template
        html_string = render_template(
            "reports/compliance_report.html",
            data=data,
        )

        # Generate PDF
        pdf_bytes = HTML(string=html_string).write_pdf()

        return pdf_bytes

    @staticmethod
    def save_to_workspace(institution_id: str, pdf_bytes: bytes, report_id: str, workspace_dir: str = "./workspace") -> str:
        """Save PDF to workspace directory.

        Args:
            institution_id: Institution ID
            pdf_bytes: PDF content
            report_id: Report ID (used as filename)
            workspace_dir: Root workspace directory

        Returns:
            Relative file path
        """
        reports_dir = Path(workspace_dir) / institution_id / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        file_path = reports_dir / f"{report_id}.pdf"
        file_path.write_bytes(pdf_bytes)

        # Return relative path for database storage
        return str(file_path.relative_to(workspace_dir))
