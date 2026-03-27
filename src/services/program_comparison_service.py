"""Program Comparison Service.

Builds a comparison matrix of programs within an institution,
with metrics for readiness, findings, evidence coverage, and faculty compliance.
Used for cross-program analysis and identification of outliers.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.db.connection import get_conn

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ProgramMetrics:
    """Metrics for a single program."""
    program_id: str
    program_name: str
    credential_level: Optional[str] = None

    # Core metrics (0-100)
    readiness_score: int = 0
    finding_count: int = 0
    critical_findings: int = 0
    evidence_coverage: int = 0
    faculty_compliance: int = 0

    # Additional detail
    document_count: int = 0
    audit_count: int = 0
    faculty_count: int = 0
    qualified_faculty: int = 0

    # Status
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonMatrix:
    """Complete comparison matrix for an institution's programs."""
    institution_id: str
    program_count: int
    programs: List[ProgramMetrics] = field(default_factory=list)

    # Aggregate stats
    avg_readiness: int = 0
    avg_evidence_coverage: int = 0
    avg_faculty_compliance: int = 0
    total_findings: int = 0

    # Outliers
    highest_readiness: Optional[str] = None
    lowest_readiness: Optional[str] = None
    most_findings: Optional[str] = None

    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution_id": self.institution_id,
            "program_count": self.program_count,
            "programs": [p.to_dict() for p in self.programs],
            "avg_readiness": self.avg_readiness,
            "avg_evidence_coverage": self.avg_evidence_coverage,
            "avg_faculty_compliance": self.avg_faculty_compliance,
            "total_findings": self.total_findings,
            "highest_readiness": self.highest_readiness,
            "lowest_readiness": self.lowest_readiness,
            "most_findings": self.most_findings,
            "computed_at": self.computed_at,
        }


# =============================================================================
# Metric Computation
# =============================================================================

def _compute_program_readiness(conn, institution_id: str, program_id: str) -> int:
    """Compute readiness score for a specific program.

    Based on:
    - Document completeness (required docs uploaded)
    - Audit findings (fewer critical = higher score)
    - Evidence coverage
    """
    score = 100

    # Check document count
    cursor = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE institution_id = ? AND program_id = ?",
        (institution_id, program_id)
    )
    doc_count = cursor.fetchone()["cnt"]

    # Get finding counts
    cursor = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN severity = 'major' THEN 1 ELSE 0 END) as major
        FROM audit_findings af
        JOIN audits a ON af.audit_id = a.id
        WHERE a.institution_id = ? AND a.program_id = ?
        AND af.status != 'resolved'
        """,
        (institution_id, program_id)
    )
    findings = cursor.fetchone()

    # Deduct for findings
    if findings["critical"]:
        score -= findings["critical"] * 15
    if findings["major"]:
        score -= findings["major"] * 5

    # Bonus for having documents
    if doc_count >= 5:
        score = min(100, score + 5)

    return max(0, min(100, score))


def _compute_evidence_coverage(conn, institution_id: str, program_id: str) -> int:
    """Compute evidence coverage percentage for a program.

    Based on standards with evidence vs total standards.
    """
    # Count standards with linked evidence for this program
    cursor = conn.execute(
        """
        SELECT
            COUNT(DISTINCT e.standard_code) as covered,
            (SELECT COUNT(*) FROM standards WHERE accreditor_code =
                (SELECT accreditor_primary FROM institutions WHERE id = ?)) as total
        FROM evidence e
        JOIN documents d ON e.document_id = d.id
        WHERE d.institution_id = ? AND d.program_id = ?
        """,
        (institution_id, institution_id, program_id)
    )
    row = cursor.fetchone()

    covered = row["covered"] or 0
    total = row["total"] or 1  # Avoid division by zero

    return min(100, int((covered / total) * 100))


def _compute_faculty_compliance(conn, institution_id: str, program_id: str) -> tuple:
    """Compute faculty compliance metrics for a program.

    Returns: (compliance_percentage, faculty_count, qualified_count)
    """
    # Check faculty teaching assignments for this program
    cursor = conn.execute(
        """
        SELECT
            fm.id,
            fm.meets_minimum_qualifications
        FROM faculty_members fm
        JOIN faculty_teaching_assignments fta ON fm.id = fta.faculty_id
        WHERE fm.institution_id = ? AND fta.program_id = ?
        """,
        (institution_id, program_id)
    )

    rows = cursor.fetchall()
    total = len(rows)
    qualified = sum(1 for r in rows if r["meets_minimum_qualifications"])

    if total == 0:
        return (100, 0, 0)  # No faculty requirement = compliant

    compliance = int((qualified / total) * 100)
    return (compliance, total, qualified)


def _get_finding_counts(conn, institution_id: str, program_id: str) -> tuple:
    """Get finding counts for a program.

    Returns: (total_findings, critical_findings, audit_count)
    """
    cursor = conn.execute(
        """
        SELECT
            COUNT(DISTINCT a.id) as audit_count,
            COUNT(af.id) as total_findings,
            SUM(CASE WHEN af.severity = 'critical' THEN 1 ELSE 0 END) as critical
        FROM audits a
        LEFT JOIN audit_findings af ON a.id = af.audit_id AND af.status != 'resolved'
        WHERE a.institution_id = ? AND a.program_id = ?
        """,
        (institution_id, program_id)
    )
    row = cursor.fetchone()

    return (
        row["total_findings"] or 0,
        row["critical"] or 0,
        row["audit_count"] or 0
    )


def _get_document_count(conn, institution_id: str, program_id: str) -> int:
    """Get document count for a program."""
    cursor = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE institution_id = ? AND program_id = ?",
        (institution_id, program_id)
    )
    return cursor.fetchone()["cnt"]


# =============================================================================
# Main API
# =============================================================================

def build_comparison_matrix(institution_id: str) -> ComparisonMatrix:
    """Build a comparison matrix of all programs for an institution.

    Args:
        institution_id: Institution ID

    Returns:
        ComparisonMatrix with metrics for each program
    """
    conn = get_conn()

    # Get all programs for this institution
    cursor = conn.execute(
        """
        SELECT id, name, credential_level, active
        FROM programs
        WHERE institution_id = ?
        ORDER BY name
        """,
        (institution_id,)
    )
    programs = cursor.fetchall()

    if not programs:
        return ComparisonMatrix(
            institution_id=institution_id,
            program_count=0,
        )

    program_metrics = []
    total_readiness = 0
    total_evidence = 0
    total_faculty = 0
    total_findings = 0

    for prog in programs:
        program_id = prog["id"]

        # Compute all metrics
        readiness = _compute_program_readiness(conn, institution_id, program_id)
        evidence_coverage = _compute_evidence_coverage(conn, institution_id, program_id)
        faculty_compliance, faculty_count, qualified_faculty = _compute_faculty_compliance(
            conn, institution_id, program_id
        )
        finding_count, critical_findings, audit_count = _get_finding_counts(
            conn, institution_id, program_id
        )
        document_count = _get_document_count(conn, institution_id, program_id)

        metrics = ProgramMetrics(
            program_id=program_id,
            program_name=prog["name"],
            credential_level=prog["credential_level"],
            readiness_score=readiness,
            finding_count=finding_count,
            critical_findings=critical_findings,
            evidence_coverage=evidence_coverage,
            faculty_compliance=faculty_compliance,
            document_count=document_count,
            audit_count=audit_count,
            faculty_count=faculty_count,
            qualified_faculty=qualified_faculty,
            active=bool(prog["active"]),
        )
        program_metrics.append(metrics)

        # Aggregate
        total_readiness += readiness
        total_evidence += evidence_coverage
        total_faculty += faculty_compliance
        total_findings += finding_count

    program_count = len(program_metrics)

    # Find outliers
    sorted_by_readiness = sorted(program_metrics, key=lambda p: p.readiness_score)
    sorted_by_findings = sorted(program_metrics, key=lambda p: p.finding_count, reverse=True)

    matrix = ComparisonMatrix(
        institution_id=institution_id,
        program_count=program_count,
        programs=program_metrics,
        avg_readiness=total_readiness // program_count if program_count else 0,
        avg_evidence_coverage=total_evidence // program_count if program_count else 0,
        avg_faculty_compliance=total_faculty // program_count if program_count else 0,
        total_findings=total_findings,
        highest_readiness=sorted_by_readiness[-1].program_name if sorted_by_readiness else None,
        lowest_readiness=sorted_by_readiness[0].program_name if sorted_by_readiness else None,
        most_findings=sorted_by_findings[0].program_name if sorted_by_findings and sorted_by_findings[0].finding_count > 0 else None,
    )

    return matrix


def get_program_detail(institution_id: str, program_id: str) -> Optional[ProgramMetrics]:
    """Get detailed metrics for a single program.

    Args:
        institution_id: Institution ID
        program_id: Program ID

    Returns:
        ProgramMetrics or None if not found
    """
    conn = get_conn()

    cursor = conn.execute(
        "SELECT id, name, credential_level, active FROM programs WHERE id = ? AND institution_id = ?",
        (program_id, institution_id)
    )
    prog = cursor.fetchone()

    if not prog:
        return None

    readiness = _compute_program_readiness(conn, institution_id, program_id)
    evidence_coverage = _compute_evidence_coverage(conn, institution_id, program_id)
    faculty_compliance, faculty_count, qualified_faculty = _compute_faculty_compliance(
        conn, institution_id, program_id
    )
    finding_count, critical_findings, audit_count = _get_finding_counts(
        conn, institution_id, program_id
    )
    document_count = _get_document_count(conn, institution_id, program_id)

    return ProgramMetrics(
        program_id=program_id,
        program_name=prog["name"],
        credential_level=prog["credential_level"],
        readiness_score=readiness,
        finding_count=finding_count,
        critical_findings=critical_findings,
        evidence_coverage=evidence_coverage,
        faculty_compliance=faculty_compliance,
        document_count=document_count,
        audit_count=audit_count,
        faculty_count=faculty_count,
        qualified_faculty=qualified_faculty,
        active=bool(prog["active"]),
    )


def get_comparison_radar_data(institution_id: str) -> Dict[str, Any]:
    """Get radar chart data for program comparison.

    Returns data formatted for Chart.js radar chart with programs as datasets
    and metrics as labels.
    """
    matrix = build_comparison_matrix(institution_id)

    if not matrix.programs:
        return {
            "labels": ["Readiness", "Evidence", "Faculty", "Documents", "Audits"],
            "datasets": [],
        }

    # Normalize document and audit counts to 0-100 scale
    max_docs = max(p.document_count for p in matrix.programs) or 1
    max_audits = max(p.audit_count for p in matrix.programs) or 1

    datasets = []
    colors = [
        "rgba(201, 168, 76, 0.6)",   # Gold
        "rgba(74, 222, 128, 0.6)",   # Green
        "rgba(59, 130, 246, 0.6)",   # Blue
        "rgba(236, 72, 153, 0.6)",   # Pink
        "rgba(168, 85, 247, 0.6)",   # Purple
        "rgba(251, 146, 60, 0.6)",   # Orange
    ]

    for i, prog in enumerate(matrix.programs):
        datasets.append({
            "label": prog.program_name,
            "data": [
                prog.readiness_score,
                prog.evidence_coverage,
                prog.faculty_compliance,
                int((prog.document_count / max_docs) * 100),
                int((prog.audit_count / max_audits) * 100) if prog.audit_count else 0,
            ],
            "backgroundColor": colors[i % len(colors)],
            "borderColor": colors[i % len(colors)].replace("0.6", "1"),
            "borderWidth": 2,
        })

    return {
        "labels": ["Readiness", "Evidence Coverage", "Faculty Compliance", "Documents", "Audits"],
        "datasets": datasets,
    }
