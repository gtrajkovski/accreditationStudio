"""Evidence Coverage Contract - Block packet export without sufficient evidence."""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.db.connection import get_conn


@dataclass
class CoverageGap:
    """A standard lacking required evidence."""
    standard_ref: str
    standard_title: str
    required_evidence_count: int = 1
    actual_evidence_count: int = 0
    severity: str = "critical"  # critical, high, medium
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_ref": self.standard_ref,
            "standard_title": self.standard_title,
            "required_evidence_count": self.required_evidence_count,
            "actual_evidence_count": self.actual_evidence_count,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "gap": self.required_evidence_count - self.actual_evidence_count,
        }


@dataclass
class CoverageReport:
    """Evidence coverage assessment for an institution."""
    institution_id: str
    accreditor_code: str
    total_standards: int = 0
    standards_with_evidence: int = 0
    standards_without_evidence: int = 0
    coverage_percent: float = 0.0
    gaps: List[CoverageGap] = field(default_factory=list)
    export_allowed: bool = False
    minimum_coverage_required: float = 80.0
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution_id": self.institution_id,
            "accreditor_code": self.accreditor_code,
            "total_standards": self.total_standards,
            "standards_with_evidence": self.standards_with_evidence,
            "standards_without_evidence": self.standards_without_evidence,
            "coverage_percent": round(self.coverage_percent, 1),
            "gaps": [g.to_dict() for g in self.gaps],
            "export_allowed": self.export_allowed,
            "minimum_coverage_required": self.minimum_coverage_required,
            "computed_at": self.computed_at,
        }


def check_evidence_coverage(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    minimum_coverage: float = 80.0,
    conn: Optional[sqlite3.Connection] = None
) -> CoverageReport:
    """
    Check if institution has sufficient evidence coverage for packet export.

    Args:
        institution_id: Institution to check
        accreditor_code: Accreditor whose standards to check
        minimum_coverage: Minimum % of standards needing evidence (default 80%)
        conn: Database connection

    Returns:
        CoverageReport with gaps and export_allowed flag
    """
    conn = conn or get_conn()
    report = CoverageReport(
        institution_id=institution_id,
        accreditor_code=accreditor_code,
        minimum_coverage_required=minimum_coverage,
    )

    try:
        # Get all standards for this accreditor
        cursor = conn.execute("""
            SELECT s.id, s.ref_code, s.title, s.required
            FROM standards s
            JOIN accreditors a ON s.accreditor_id = a.id
            WHERE a.code = ?
            ORDER BY s.ref_code
        """, (accreditor_code,))

        standards = cursor.fetchall()
        report.total_standards = len(standards)

        if report.total_standards == 0:
            report.export_allowed = True
            return report

        # Check evidence for each standard
        for std in standards:
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT er.id) as evidence_count
                FROM evidence_refs er
                JOIN audit_findings af ON er.finding_id = af.id
                JOIN finding_standard_refs fsr ON fsr.finding_id = af.id
                JOIN audit_runs ar ON af.audit_run_id = ar.id
                WHERE ar.institution_id = ?
                  AND fsr.standard_ref = ?
                  AND er.confidence >= 0.7
            """, (institution_id, std["ref_code"]))

            evidence_count = cursor.fetchone()["evidence_count"]

            if evidence_count > 0:
                report.standards_with_evidence += 1
            else:
                report.standards_without_evidence += 1
                # Add to gaps
                severity = "critical" if std["required"] else "medium"
                report.gaps.append(CoverageGap(
                    standard_ref=std["ref_code"],
                    standard_title=std["title"] or std["ref_code"],
                    required_evidence_count=1,
                    actual_evidence_count=0,
                    severity=severity,
                    suggestion=f"Upload documents addressing {std['ref_code']}",
                ))

        # Calculate coverage
        if report.total_standards > 0:
            report.coverage_percent = (
                report.standards_with_evidence / report.total_standards * 100
            )

        # Sort gaps by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2}
        report.gaps.sort(key=lambda g: severity_order.get(g.severity, 2))

        # Determine if export allowed
        report.export_allowed = report.coverage_percent >= minimum_coverage

    except sqlite3.OperationalError:
        # Tables might not exist
        report.export_allowed = False

    return report


def validate_packet_export(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Validate if packet export should be allowed.

    Returns dict with allowed flag and blocking reasons.
    """
    report = check_evidence_coverage(institution_id, accreditor_code, conn=conn)

    blockers = []

    # Check evidence coverage
    if not report.export_allowed:
        blockers.append({
            "type": "evidence_coverage",
            "message": f"Evidence coverage {report.coverage_percent:.1f}% below {report.minimum_coverage_required}% minimum",
            "gaps_count": len(report.gaps),
        })

    # Check for critical gaps
    critical_gaps = [g for g in report.gaps if g.severity == "critical"]
    if critical_gaps:
        blockers.append({
            "type": "critical_gaps",
            "message": f"{len(critical_gaps)} critical standards lack evidence",
            "standards": [g.standard_ref for g in critical_gaps[:5]],
        })

    # Check for unresolved audit findings
    conn = conn or get_conn()
    try:
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ?
              AND af.severity = 'critical'
              AND af.compliance_status = 'non_compliant'
        """, (institution_id,))
        critical_findings = cursor.fetchone()["count"]

        if critical_findings > 0:
            blockers.append({
                "type": "critical_findings",
                "message": f"{critical_findings} critical non-compliant findings",
            })
    except sqlite3.OperationalError:
        pass

    return {
        "allowed": len(blockers) == 0,
        "blockers": blockers,
        "coverage_report": report.to_dict(),
    }


def get_missing_evidence_summary(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    limit: int = 10,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Get summary of standards missing evidence for quick display."""
    report = check_evidence_coverage(institution_id, accreditor_code, conn=conn)

    return [g.to_dict() for g in report.gaps[:limit]]
