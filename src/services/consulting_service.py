"""Consulting Service.

Provides consulting-level deliverables that replace the work of $150-300/hr accreditation consultants:
- Readiness assessments with recommendations
- Pre-visit checklists organized by evaluation area
- Guided self-assessment with expert commentary
"""

import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.db.connection import get_conn
from src.services.readiness_service import compute_readiness, ReadinessScore


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SectionAssessment:
    """Compliance assessment for one evaluation section."""
    section: str  # e.g., "Administration & Management"
    section_code: str  # e.g., "admin"
    rating: str  # "compliant", "conditionally_ready", "not_ready"
    score: int  # 0-100
    total_standards: int
    compliant_count: int
    partial_count: int
    non_compliant_count: int
    critical_gaps: List[Dict[str, Any]] = field(default_factory=list)
    findings_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReadinessAssessment:
    """Complete readiness assessment report."""
    institution_id: str
    institution_name: str
    accreditor_code: str
    overall_rating: str  # "ready", "conditionally_ready", "not_ready"
    readiness_score: int  # 0-100
    sections: List[SectionAssessment] = field(default_factory=list)
    critical_gaps: List[Dict[str, Any]] = field(default_factory=list)
    timeline_recommendation: str = ""
    remediation_effort: str = ""  # "low", "medium", "high"
    executive_summary: str = ""
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution_id": self.institution_id,
            "institution_name": self.institution_name,
            "accreditor_code": self.accreditor_code,
            "overall_rating": self.overall_rating,
            "readiness_score": self.readiness_score,
            "sections": [s.to_dict() for s in self.sections],
            "critical_gaps": self.critical_gaps,
            "timeline_recommendation": self.timeline_recommendation,
            "remediation_effort": self.remediation_effort,
            "executive_summary": self.executive_summary,
            "computed_at": self.computed_at,
        }


@dataclass
class ChecklistItem:
    """One item in pre-visit checklist."""
    requirement: str
    section: str
    section_code: str
    status: str  # "met", "not_met", "partial"
    evidence_reference: Optional[str] = None
    action_needed: Optional[str] = None
    standard_code: Optional[str] = None
    page_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PreVisitChecklist:
    """Complete pre-visit checklist organized by section."""
    institution_id: str
    accreditor_code: str
    sections: Dict[str, List[ChecklistItem]] = field(default_factory=dict)
    section_progress: Dict[str, Dict[str, int]] = field(default_factory=dict)  # {section: {met: N, partial: N, not_met: N}}
    overall_progress: Dict[str, int] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution_id": self.institution_id,
            "accreditor_code": self.accreditor_code,
            "sections": {
                section: [item.to_dict() for item in items]
                for section, items in self.sections.items()
            },
            "section_progress": self.section_progress,
            "overall_progress": self.overall_progress,
            "generated_at": self.generated_at,
        }


@dataclass
class SelfAssessmentQuestion:
    """One self-assessment question with guidance."""
    standard_code: str
    section: str
    requirement_text: str
    what_to_look_for: str
    evidence_to_prepare: List[str] = field(default_factory=list)
    common_deficiencies: List[str] = field(default_factory=list)
    ai_assessment: Optional[str] = None
    ai_assessment_status: Optional[str] = None  # "compliant", "partial", "non_compliant", "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# =============================================================================
# ACCSC Evaluation Areas (default structure)
# =============================================================================

ACCSC_SECTIONS = {
    "admin": {
        "name": "Administration & Management",
        "order": 1,
        "keywords": ["governance", "management", "organization", "leadership", "planning"],
    },
    "academics": {
        "name": "Academics",
        "order": 2,
        "keywords": ["curriculum", "instruction", "program", "learning", "assessment"],
    },
    "admissions": {
        "name": "Admissions",
        "order": 3,
        "keywords": ["admission", "enrollment", "recruitment", "student selection"],
    },
    "student_services": {
        "name": "Student Services",
        "order": 4,
        "keywords": ["student services", "support", "advising", "counseling"],
    },
    "financial": {
        "name": "Financial Stability",
        "order": 5,
        "keywords": ["financial", "fiscal", "budget", "accounting"],
    },
    "facilities": {
        "name": "Facilities & Equipment",
        "order": 6,
        "keywords": ["facility", "facilities", "equipment", "resources"],
    },
    "catalog": {
        "name": "Catalog & Publications",
        "order": 7,
        "keywords": ["catalog", "publication", "advertising", "disclosure"],
    },
    "achievement": {
        "name": "Student Achievement",
        "order": 8,
        "keywords": ["achievement", "completion", "placement", "outcomes"],
    },
}


# =============================================================================
# Readiness Assessment Generation
# =============================================================================

def generate_readiness_assessment(
    institution_id: str,
    accreditor_code: str = "ACCSC"
) -> ReadinessAssessment:
    """Generate comprehensive readiness assessment report.

    Pulls from:
    - Readiness score (compute_readiness)
    - Audit findings (by section)
    - Document inventory
    - Task status
    - Faculty credentials (if available)
    - Student outcomes (if available)

    Returns structured report with overall rating and section-by-section breakdown.
    """
    conn = get_conn()

    # Get institution name
    cursor = conn.execute(
        "SELECT name FROM institutions WHERE id = ?",
        (institution_id,)
    )
    inst_row = cursor.fetchone()
    institution_name = inst_row["name"] if inst_row else "Unknown Institution"

    # Compute readiness score
    readiness = compute_readiness(institution_id, accreditor_code)

    # Determine overall rating
    overall_rating = _determine_overall_rating(readiness.total, readiness.blockers)

    # Generate section assessments
    sections = _generate_section_assessments(conn, institution_id, accreditor_code)

    # Extract critical gaps across all sections
    critical_gaps = []
    for section in sections:
        critical_gaps.extend(section.critical_gaps)

    # Add blockers from readiness score
    for blocker in readiness.blockers:
        if blocker.severity in ("critical", "high"):
            critical_gaps.append({
                "type": blocker.type,
                "severity": blocker.severity,
                "message": blocker.message,
                "action": blocker.action,
                "link": blocker.link,
            })

    # Generate timeline recommendation
    timeline = _generate_timeline_recommendation(readiness.total, critical_gaps)

    # Estimate remediation effort
    effort = _estimate_remediation_effort(readiness.total, len(critical_gaps))

    # Generate executive summary
    summary = _generate_executive_summary(
        institution_name,
        overall_rating,
        readiness.total,
        len(critical_gaps),
        sections
    )

    return ReadinessAssessment(
        institution_id=institution_id,
        institution_name=institution_name,
        accreditor_code=accreditor_code,
        overall_rating=overall_rating,
        readiness_score=readiness.total,
        sections=sections,
        critical_gaps=critical_gaps,
        timeline_recommendation=timeline,
        remediation_effort=effort,
        executive_summary=summary,
    )


def _determine_overall_rating(score: int, blockers: List) -> str:
    """Determine overall readiness rating."""
    critical_blockers = [b for b in blockers if b.severity == "critical"]

    if score >= 90 and len(critical_blockers) == 0:
        return "ready"
    elif score >= 70 and len(critical_blockers) <= 1:
        return "conditionally_ready"
    else:
        return "not_ready"


def _generate_section_assessments(
    conn: sqlite3.Connection,
    institution_id: str,
    accreditor_code: str
) -> List[SectionAssessment]:
    """Generate section-by-section compliance assessment."""
    sections = []

    # Get latest audit run
    cursor = conn.execute("""
        SELECT id FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    audit = cursor.fetchone()

    if not audit:
        # No audit - return empty sections with "unknown" status
        for code, info in ACCSC_SECTIONS.items():
            sections.append(SectionAssessment(
                section=info["name"],
                section_code=code,
                rating="unknown",
                score=0,
                total_standards=0,
                compliant_count=0,
                partial_count=0,
                non_compliant_count=0,
                findings_summary="No audit data available",
            ))
        return sorted(sections, key=lambda s: ACCSC_SECTIONS[s.section_code]["order"])

    audit_id = audit["id"]

    # Get all findings grouped by section
    for code, info in ACCSC_SECTIONS.items():
        # Match findings to section using keywords (simplified approach)
        # In production, this would use standard_code mapping
        keywords = "|".join(info["keywords"])

        cursor = conn.execute("""
            SELECT
                status,
                severity,
                COUNT(*) as count
            FROM audit_findings
            WHERE audit_run_id = ?
              AND (summary LIKE ? OR recommendation LIKE ?)
            GROUP BY status, severity
        """, (audit_id, f"%{info['keywords'][0]}%", f"%{info['keywords'][0]}%"))

        findings = cursor.fetchall()

        total = sum(row["count"] for row in findings)
        compliant = sum(row["count"] for row in findings if row["status"] == "compliant")
        partial = sum(row["count"] for row in findings if row["status"] == "partial")
        non_compliant = sum(row["count"] for row in findings if row["status"] == "non_compliant")

        # If no findings for this section, check standards directly
        if total == 0:
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM standards s
                JOIN accreditors a ON s.accreditor_id = a.id
                WHERE a.code = ?
                  AND (s.title LIKE ? OR s.body_text LIKE ?)
            """, (accreditor_code, f"%{info['keywords'][0]}%", f"%{info['keywords'][0]}%"))
            std_row = cursor.fetchone()
            total = std_row["count"] if std_row else 0

        # Calculate section score
        if total > 0:
            score = int((compliant / total) * 100)
        else:
            score = 0

        # Determine section rating
        if score >= 90 and non_compliant == 0:
            rating = "compliant"
        elif score >= 70:
            rating = "conditionally_ready"
        else:
            rating = "not_ready"

        # Get critical gaps for this section
        cursor = conn.execute("""
            SELECT id, severity, summary, recommendation
            FROM audit_findings
            WHERE audit_run_id = ?
              AND (summary LIKE ? OR recommendation LIKE ?)
              AND severity IN ('critical', 'significant')
              AND status = 'non_compliant'
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'significant' THEN 2
                    ELSE 3
                END
            LIMIT 5
        """, (audit_id, f"%{info['keywords'][0]}%", f"%{info['keywords'][0]}%"))

        gaps = []
        for finding in cursor.fetchall():
            gaps.append({
                "finding_id": finding["id"],
                "severity": finding["severity"],
                "summary": finding["summary"],
                "recommendation": finding["recommendation"],
            })

        # Generate findings summary
        summary_parts = []
        if compliant > 0:
            summary_parts.append(f"{compliant} compliant")
        if partial > 0:
            summary_parts.append(f"{partial} partially compliant")
        if non_compliant > 0:
            summary_parts.append(f"{non_compliant} non-compliant")

        findings_summary = ", ".join(summary_parts) if summary_parts else "No findings"

        sections.append(SectionAssessment(
            section=info["name"],
            section_code=code,
            rating=rating,
            score=score,
            total_standards=total,
            compliant_count=compliant,
            partial_count=partial,
            non_compliant_count=non_compliant,
            critical_gaps=gaps,
            findings_summary=findings_summary,
        ))

    return sorted(sections, key=lambda s: ACCSC_SECTIONS[s.section_code]["order"])


def _generate_timeline_recommendation(score: int, critical_gaps: List[Dict]) -> str:
    """Generate timeline recommendation based on readiness."""
    critical_count = len([g for g in critical_gaps if g.get("severity") == "critical"])

    if score >= 90:
        return "Ready for submission. Schedule site visit within 2-4 weeks."
    elif score >= 80:
        return "Nearly ready. Address remaining issues (2-4 weeks), then schedule site visit."
    elif score >= 70:
        if critical_count > 0:
            return f"Conditionally ready with {critical_count} critical gaps. Remediate critical issues (4-6 weeks), then reassess."
        else:
            return "Conditionally ready. Address moderate issues (4-6 weeks), then schedule site visit."
    elif score >= 60:
        return "Significant work needed. Focus on high-priority issues (6-12 weeks), then reassess."
    else:
        return "Not ready for submission. Comprehensive remediation required (12-24 weeks)."


def _estimate_remediation_effort(score: int, gap_count: int) -> str:
    """Estimate remediation effort level."""
    if score >= 85 and gap_count <= 3:
        return "low"
    elif score >= 70 and gap_count <= 8:
        return "medium"
    else:
        return "high"


def _generate_executive_summary(
    institution_name: str,
    rating: str,
    score: int,
    gap_count: int,
    sections: List[SectionAssessment]
) -> str:
    """Generate executive summary text."""
    rating_text = {
        "ready": "READY for accreditation site visit",
        "conditionally_ready": "CONDITIONALLY READY for accreditation",
        "not_ready": "NOT READY for accreditation site visit",
        "unknown": "ASSESSMENT INCOMPLETE",
    }

    summary = f"{institution_name} is {rating_text.get(rating, 'UNKNOWN STATUS')} "
    summary += f"with an overall readiness score of {score}/100.\n\n"

    # Section highlights
    strong = [s for s in sections if s.rating == "compliant"]
    weak = [s for s in sections if s.rating == "not_ready"]

    if strong:
        summary += f"Strong areas: {', '.join([s.section for s in strong[:3]])}.\n"

    if weak:
        summary += f"Areas needing attention: {', '.join([s.section for s in weak[:3]])}.\n"

    if gap_count > 0:
        summary += f"\nCritical gaps identified: {gap_count}. Immediate action required on high-priority findings.\n"

    return summary.strip()


# =============================================================================
# Pre-Visit Checklist Generation
# =============================================================================

def generate_pre_visit_checklist(
    institution_id: str,
    accreditor_code: str = "ACCSC"
) -> PreVisitChecklist:
    """Generate pre-visit checklist organized by evaluation area.

    Auto-populated from:
    - Audit findings
    - Document status
    - Evidence coverage

    Returns checklist items with status and action needed.
    """
    conn = get_conn()

    checklist = PreVisitChecklist(
        institution_id=institution_id,
        accreditor_code=accreditor_code,
    )

    # Get latest audit
    cursor = conn.execute("""
        SELECT id FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    audit = cursor.fetchone()

    if not audit:
        # No audit - generate basic checklist from standards
        _populate_basic_checklist(conn, checklist, accreditor_code)
    else:
        # Populate from audit findings
        _populate_checklist_from_audit(conn, checklist, audit["id"], accreditor_code)

    # Calculate progress per section
    for section_code, items in checklist.sections.items():
        met = len([i for i in items if i.status == "met"])
        partial = len([i for i in items if i.status == "partial"])
        not_met = len([i for i in items if i.status == "not_met"])

        checklist.section_progress[section_code] = {
            "met": met,
            "partial": partial,
            "not_met": not_met,
            "total": len(items),
        }

    # Calculate overall progress
    all_items = sum(len(items) for items in checklist.sections.values())
    all_met = sum(p["met"] for p in checklist.section_progress.values())
    all_partial = sum(p["partial"] for p in checklist.section_progress.values())
    all_not_met = sum(p["not_met"] for p in checklist.section_progress.values())

    checklist.overall_progress = {
        "met": all_met,
        "partial": all_partial,
        "not_met": all_not_met,
        "total": all_items,
        "percent_complete": int((all_met / all_items) * 100) if all_items > 0 else 0,
    }

    return checklist


def _populate_basic_checklist(
    conn: sqlite3.Connection,
    checklist: PreVisitChecklist,
    accreditor_code: str
) -> None:
    """Populate checklist from standards (no audit data)."""
    cursor = conn.execute("""
        SELECT s.id, s.standard_code, s.title
        FROM standards s
        JOIN accreditors a ON s.accreditor_id = a.id
        WHERE a.code = ?
        ORDER BY s.standard_code
    """, (accreditor_code,))

    for row in cursor.fetchall():
        # Categorize by keywords (simplified)
        section_code = _categorize_standard(row["title"])

        if section_code not in checklist.sections:
            checklist.sections[section_code] = []

        checklist.sections[section_code].append(ChecklistItem(
            requirement=row["title"],
            section=ACCSC_SECTIONS[section_code]["name"],
            section_code=section_code,
            status="not_met",  # Default: no evidence
            standard_code=row["standard_code"],
            action_needed="Upload supporting documentation",
        ))


def _populate_checklist_from_audit(
    conn: sqlite3.Connection,
    checklist: PreVisitChecklist,
    audit_id: str,
    accreditor_code: str
) -> None:
    """Populate checklist from audit findings."""
    cursor = conn.execute("""
        SELECT
            f.id,
            f.status,
            f.summary,
            f.recommendation,
            f.severity,
            ci.text as item_text,
            s.standard_code,
            s.title as standard_title,
            GROUP_CONCAT(e.page || ':' || COALESCE(e.snippet_text, ''), '|') as evidence
        FROM audit_findings f
        LEFT JOIN checklist_items ci ON f.checklist_item_id = ci.id
        LEFT JOIN checklist_item_standard_refs csr ON ci.id = csr.checklist_item_id
        LEFT JOIN standards s ON csr.standard_id = s.id
        LEFT JOIN evidence_refs e ON f.id = e.finding_id
        WHERE f.audit_run_id = ?
        GROUP BY f.id
        ORDER BY
            CASE f.severity
                WHEN 'critical' THEN 1
                WHEN 'significant' THEN 2
                WHEN 'moderate' THEN 3
                WHEN 'advisory' THEN 4
            END,
            f.status
    """, (audit_id,))

    for row in cursor.fetchall():
        # Determine section
        text = row["item_text"] or row["summary"] or row["standard_title"] or ""
        section_code = _categorize_standard(text)

        if section_code not in checklist.sections:
            checklist.sections[section_code] = []

        # Map finding status to checklist status
        if row["status"] == "compliant":
            item_status = "met"
            action = None
        elif row["status"] == "partial":
            item_status = "partial"
            action = row["recommendation"] or "Address partial compliance"
        else:
            item_status = "not_met"
            action = row["recommendation"] or "Remediate finding"

        # Extract evidence reference
        evidence_ref = None
        if row["evidence"]:
            pages = [e.split(":")[0] for e in row["evidence"].split("|") if e]
            if pages:
                evidence_ref = f"Pages: {', '.join(pages[:3])}"

        checklist.sections[section_code].append(ChecklistItem(
            requirement=row["item_text"] or row["summary"],
            section=ACCSC_SECTIONS[section_code]["name"],
            section_code=section_code,
            status=item_status,
            evidence_reference=evidence_ref,
            action_needed=action,
            standard_code=row["standard_code"],
            page_reference=evidence_ref,
        ))


def _categorize_standard(text: str) -> str:
    """Categorize a standard/finding into an ACCSC section."""
    text_lower = text.lower()

    # Match against keywords
    for code, info in ACCSC_SECTIONS.items():
        for keyword in info["keywords"]:
            if keyword in text_lower:
                return code

    # Default to administration
    return "admin"


# =============================================================================
# Guided Self-Assessment
# =============================================================================

def get_self_assessment_questions(
    accreditor_code: str = "ACCSC",
    section: Optional[str] = None
) -> List[SelfAssessmentQuestion]:
    """Get self-assessment questions with guidance.

    For each requirement:
    - Standard text
    - What accreditor looks for
    - Evidence to prepare
    - Common deficiencies
    - AccreditAI's current assessment (if available)

    Returns questions optionally filtered by section.
    """
    conn = get_conn()

    # Get standards with guidance
    query = """
        SELECT
            s.id,
            s.standard_code,
            s.title,
            s.body_text
        FROM standards s
        JOIN accreditors a ON s.accreditor_id = a.id
        WHERE a.code = ?
        ORDER BY s.standard_code
    """

    cursor = conn.execute(query, (accreditor_code,))

    questions = []
    for row in cursor.fetchall():
        # Determine section
        section_code = _categorize_standard(row["title"])

        # Filter by section if specified
        if section and section != section_code:
            continue

        # Generate guidance (in production, this would come from a knowledge base)
        what_to_look_for = _generate_what_to_look_for(row["standard_code"], row["title"])
        evidence_list = _generate_evidence_list(row["standard_code"], row["title"])
        common_issues = _generate_common_deficiencies(row["standard_code"])

        questions.append(SelfAssessmentQuestion(
            standard_code=row["standard_code"],
            section=ACCSC_SECTIONS[section_code]["name"],
            requirement_text=row["title"] + "\n\n" + (row["body_text"] or ""),
            what_to_look_for=what_to_look_for,
            evidence_to_prepare=evidence_list,
            common_deficiencies=common_issues,
        ))

    return questions


def get_self_assessment_with_ai(
    institution_id: str,
    accreditor_code: str = "ACCSC",
    section: Optional[str] = None
) -> List[SelfAssessmentQuestion]:
    """Get self-assessment questions with AI assessments included.

    Includes current compliance status from audit findings.
    """
    conn = get_conn()

    # Get base questions
    questions = get_self_assessment_questions(accreditor_code, section)

    # Get latest audit
    cursor = conn.execute("""
        SELECT id FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    audit = cursor.fetchone()

    if not audit:
        return questions

    audit_id = audit["id"]

    # Enhance questions with AI findings
    for q in questions:
        cursor = conn.execute("""
            SELECT f.status, f.summary, f.confidence
            FROM audit_findings f
            JOIN finding_standard_refs fsr ON f.id = fsr.finding_id
            JOIN standards s ON fsr.standard_id = s.id
            WHERE f.audit_run_id = ?
              AND s.standard_code = ?
            ORDER BY f.created_at DESC
            LIMIT 1
        """, (audit_id, q.standard_code))

        finding = cursor.fetchone()
        if finding:
            q.ai_assessment = finding["summary"]
            q.ai_assessment_status = finding["status"]

    return questions


def _generate_what_to_look_for(standard_code: str, title: str) -> str:
    """Generate 'what to look for' guidance (stub for knowledge base)."""
    return f"Evaluators will examine whether {title.lower()} meets accreditor standards. " \
           f"Ensure documentation is clear, complete, and up-to-date."


def _generate_evidence_list(standard_code: str, title: str) -> List[str]:
    """Generate evidence list (stub for knowledge base)."""
    return [
        "Current policy documents",
        "Supporting procedures",
        "Evidence of implementation",
        "Records of compliance",
    ]


def _generate_common_deficiencies(standard_code: str) -> List[str]:
    """Generate common deficiencies (stub for knowledge base)."""
    return [
        "Incomplete or outdated documentation",
        "Lack of evidence of implementation",
        "Inconsistent policies across documents",
    ]
