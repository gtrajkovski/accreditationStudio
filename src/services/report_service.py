"""Report Generation Service.

Aggregates data from multiple sources to generate comprehensive compliance reports.
"""

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from src.db.connection import get_conn
from src.services.readiness_service import compute_readiness


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ReportMetadata:
    """Report metadata record."""
    id: str
    institution_id: str
    report_type: str
    title: str
    status: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    generated_at: Optional[str] = None
    generated_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.metadata is None:
            result["metadata"] = {}
        return result


# =============================================================================
# Report Service
# =============================================================================

class ReportService:
    """Service for generating report data and managing report metadata."""

    @staticmethod
    def generate_compliance_report_data(institution_id: str) -> Dict[str, Any]:
        """Generate compliance report data for an institution.

        Args:
            institution_id: Institution ID

        Returns:
            Dict with institution, readiness, findings_summary, documents, generated_at
        """
        conn = get_conn()

        # Get institution info
        institution_row = conn.execute(
            "SELECT id, name, accreditor_code FROM institutions WHERE id = ?",
            (institution_id,)
        ).fetchone()

        if not institution_row:
            raise ValueError(f"Institution not found: {institution_id}")

        institution = {
            "id": institution_row["id"],
            "name": institution_row["name"],
            "accreditor_code": institution_row["accreditor_code"],
        }

        # Get readiness scores
        readiness = compute_readiness(institution_id, institution_row["accreditor_code"])

        # Get compliance findings summary by severity
        findings_query = """
            SELECT
                severity,
                COUNT(*) as count,
                COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open
            FROM compliance_findings
            WHERE institution_id = ?
            GROUP BY severity
        """
        findings_rows = conn.execute(findings_query, (institution_id,)).fetchall()

        findings_summary = {
            "critical": {"count": 0, "resolved": 0, "in_progress": 0, "open": 0},
            "high": {"count": 0, "resolved": 0, "in_progress": 0, "open": 0},
            "medium": {"count": 0, "resolved": 0, "in_progress": 0, "open": 0},
            "low": {"count": 0, "resolved": 0, "in_progress": 0, "open": 0},
        }

        for row in findings_rows:
            severity = row["severity"]
            if severity in findings_summary:
                findings_summary[severity] = {
                    "count": row["count"],
                    "resolved": row["resolved"],
                    "in_progress": row["in_progress"],
                    "open": row["open"],
                }

        # Get document counts
        docs_query = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'indexed' THEN 1 END) as indexed,
                COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as uploaded,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending
            FROM documents
            WHERE institution_id = ?
        """
        docs_row = conn.execute(docs_query, (institution_id,)).fetchone()

        documents = {
            "total": docs_row["total"] if docs_row else 0,
            "indexed": docs_row["indexed"] if docs_row else 0,
            "uploaded": docs_row["uploaded"] if docs_row else 0,
            "pending": docs_row["pending"] if docs_row else 0,
        }

        # Get top standards with low coverage
        standards_query = """
            SELECT
                s.code,
                s.title,
                COUNT(cf.id) as finding_count
            FROM standards s
            LEFT JOIN compliance_findings cf ON cf.standard_id = s.id AND cf.institution_id = ?
            WHERE s.accreditor_code = ?
            GROUP BY s.id
            ORDER BY finding_count DESC
            LIMIT 10
        """
        standards_rows = conn.execute(
            standards_query,
            (institution_id, institution_row["accreditor_code"])
        ).fetchall()

        top_standards = [
            {
                "code": row["code"],
                "title": row["title"],
                "finding_count": row["finding_count"],
            }
            for row in standards_rows
        ]

        return {
            "institution": institution,
            "readiness": readiness.to_dict(),
            "findings_summary": findings_summary,
            "documents": documents,
            "top_standards": top_standards,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def save_report_metadata(
        institution_id: str,
        report_type: str,
        title: str,
        file_path: str,
        file_size: int,
        generated_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save report metadata to database.

        Args:
            institution_id: Institution ID
            report_type: Type of report (e.g., 'compliance')
            title: Report title
            file_path: Path to generated PDF file
            file_size: File size in bytes
            generated_by: User/system identifier
            metadata: Additional metadata

        Returns:
            Report ID
        """
        conn = get_conn()
        report_id = f"rpt_{uuid4().hex[:12]}"
        generated_at = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO reports (
                id, institution_id, report_type, title, status,
                file_path, file_size, generated_at, generated_by, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                institution_id,
                report_type,
                title,
                "completed",
                file_path,
                file_size,
                generated_at,
                generated_by,
                json.dumps(metadata or {}),
            )
        )
        conn.commit()

        return report_id

    @staticmethod
    def list_reports(institution_id: str, report_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List reports for an institution.

        Args:
            institution_id: Institution ID
            report_type: Filter by report type (optional)
            limit: Maximum number of reports to return

        Returns:
            List of report metadata dicts
        """
        conn = get_conn()

        if report_type:
            query = """
                SELECT * FROM reports
                WHERE institution_id = ? AND report_type = ?
                ORDER BY generated_at DESC
                LIMIT ?
            """
            rows = conn.execute(query, (institution_id, report_type, limit)).fetchall()
        else:
            query = """
                SELECT * FROM reports
                WHERE institution_id = ?
                ORDER BY generated_at DESC
                LIMIT ?
            """
            rows = conn.execute(query, (institution_id, limit)).fetchall()

        reports = []
        for row in rows:
            report = dict(row)
            if report.get("metadata"):
                try:
                    report["metadata"] = json.loads(report["metadata"])
                except (json.JSONDecodeError, TypeError):
                    report["metadata"] = {}
            else:
                report["metadata"] = {}
            reports.append(report)

        return reports

    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        """Get a single report by ID.

        Args:
            report_id: Report ID

        Returns:
            Report metadata dict or None if not found
        """
        conn = get_conn()
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

        if not row:
            return None

        report = dict(row)
        if report.get("metadata"):
            try:
                report["metadata"] = json.loads(report["metadata"])
            except (json.JSONDecodeError, TypeError):
                report["metadata"] = {}
        else:
            report["metadata"] = {}

        return report

    @staticmethod
    def delete_report(report_id: str) -> bool:
        """Delete a report and its file.

        Args:
            report_id: Report ID

        Returns:
            True if deleted, False if not found
        """
        conn = get_conn()
        report = ReportService.get_report(report_id)

        if not report:
            return False

        # Delete file if exists
        if report.get("file_path"):
            file_path = Path(report["file_path"])
            if file_path.exists():
                file_path.unlink()

        # Delete from database
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()

        return True

    @staticmethod
    def compare_reports(report_id_a: str, report_id_b: str) -> Dict[str, Any]:
        """Compare two reports and return delta metrics.

        Args:
            report_id_a: First report ID (older)
            report_id_b: Second report ID (newer)

        Returns:
            Dict with report_a, report_b, deltas structure
        """
        conn = get_conn()

        # Fetch both reports
        rows = conn.execute(
            "SELECT * FROM reports WHERE id IN (?, ?)",
            (report_id_a, report_id_b)
        ).fetchall()

        if len(rows) != 2:
            raise ValueError("One or both reports not found")

        # Parse reports
        reports = {}
        for row in rows:
            report = dict(row)
            if report.get("metadata"):
                try:
                    report["metadata"] = json.loads(report["metadata"])
                except (json.JSONDecodeError, TypeError):
                    report["metadata"] = {}
            else:
                report["metadata"] = {}
            reports[report["id"]] = report

        report_a = reports[report_id_a]
        report_b = reports[report_id_b]

        # Get readiness and findings from metadata (stored during generation)
        readiness_a = report_a["metadata"].get("readiness_total", 0)
        readiness_b = report_b["metadata"].get("readiness_total", 0)
        findings_a = report_a["metadata"].get("findings_count", 0)
        findings_b = report_b["metadata"].get("findings_count", 0)

        # Regenerate full report data to get findings_summary breakdown
        data_a = ReportService.generate_compliance_report_data(report_a["institution_id"])
        data_b = ReportService.generate_compliance_report_data(report_b["institution_id"])

        findings_summary_a = data_a["findings_summary"]
        findings_summary_b = data_b["findings_summary"]

        # Calculate deltas
        readiness_delta = readiness_b - readiness_a
        findings_delta = findings_b - findings_a

        # Calculate severity-level deltas
        by_severity = {
            "critical": findings_summary_b["critical"]["count"] - findings_summary_a["critical"]["count"],
            "high": findings_summary_b["high"]["count"] - findings_summary_a["high"]["count"],
            "medium": findings_summary_b["medium"]["count"] - findings_summary_a["medium"]["count"],
            "low": findings_summary_b["low"]["count"] - findings_summary_a["low"]["count"],
        }

        # Determine direction
        if readiness_delta > 1:
            direction = "improved"
        elif readiness_delta < -1:
            direction = "declined"
        else:
            direction = "unchanged"

        return {
            "report_a": {
                "id": report_a["id"],
                "generated_at": report_a["generated_at"],
                "readiness_total": readiness_a,
                "findings_count": findings_a,
                "findings_summary": findings_summary_a,
            },
            "report_b": {
                "id": report_b["id"],
                "generated_at": report_b["generated_at"],
                "readiness_total": readiness_b,
                "findings_count": findings_b,
                "findings_summary": findings_summary_b,
            },
            "deltas": {
                "readiness": readiness_delta,
                "findings": findings_delta,
                "by_severity": by_severity,
            },
            "direction": direction,
        }

    @staticmethod
    def get_readiness_trend(institution_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get readiness score trend over time.

        Args:
            institution_id: Institution ID
            days: Number of days to look back (default 30)

        Returns:
            List of {date, readiness} dicts sorted by date ascending
        """
        from datetime import timedelta

        conn = get_conn()

        # Calculate cutoff date
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Query reports in date range
        query = """
            SELECT generated_at, metadata FROM reports
            WHERE institution_id = ? AND generated_at >= ?
            ORDER BY generated_at ASC
        """
        rows = conn.execute(query, (institution_id, cutoff)).fetchall()

        # Extract readiness scores from metadata
        trend_data = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                readiness_total = metadata.get("readiness_total")

                if readiness_total is not None:
                    trend_data.append({
                        "date": row["generated_at"],
                        "readiness": readiness_total
                    })
            except (json.JSONDecodeError, TypeError, KeyError):
                # Skip malformed records
                continue

        return trend_data
