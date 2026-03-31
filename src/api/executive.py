"""
Executive Dashboard API Blueprint

Provides aggregated metrics, readiness trends, AI-generated attention summaries,
and upcoming deadlines for executive-level oversight.

Endpoints:
- GET /api/executive/overview - Aggregated metrics dashboard
- GET /api/executive/trends - Readiness trend data
- GET /api/executive/attention - AI-powered what-needs-attention summary
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone
from typing import Optional
import sqlite3

from src.db.connection import get_conn
from src.services.readiness_service import get_readiness_trend, get_or_compute_readiness
from src.ai.client import AIClient
from src.auth.decorators import require_auth, require_role


executive_bp = Blueprint("executive", __name__, url_prefix="/api/executive")

_ai_client: Optional[AIClient] = None


def init_executive_bp(ai_client: AIClient):
    """Initialize the executive blueprint with dependencies."""
    global _ai_client
    _ai_client = ai_client


# =============================================================================
# Helper Functions
# =============================================================================

def _get_document_metrics(institution_id: str, conn: sqlite3.Connection) -> dict:
    """Get document metrics."""
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'indexed' THEN 1 ELSE 0 END) as audited,
            SUM(CASE WHEN status = 'indexed' AND EXISTS(
                SELECT 1 FROM audit_findings af
                JOIN audit_runs ar ON af.audit_run_id = ar.id
                WHERE ar.institution_id = ? AND af.status = 'compliant'
            ) THEN 1 ELSE 0 END) as compliant
        FROM documents
        WHERE institution_id = ?
    """, (institution_id, institution_id))
    row = cursor.fetchone()

    total = row["total"] or 0
    audited = row["audited"] or 0
    compliant = row["compliant"] or 0
    needing_attention = audited - compliant if audited > compliant else 0

    return {
        "total": total,
        "audited": audited,
        "compliant": compliant,
        "needing_attention": needing_attention
    }


def _get_findings_metrics(institution_id: str, conn: sqlite3.Connection) -> dict:
    """Get findings metrics from latest audit."""
    # Get latest audit
    cursor = conn.execute("""
        SELECT id FROM audit_runs
        WHERE institution_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (institution_id,))
    audit_row = cursor.fetchone()

    if not audit_row:
        return {
            "total": 0,
            "resolved": 0,
            "open_critical": 0,
            "open_major": 0,
            "open_minor": 0
        }

    audit_id = audit_row["id"]

    cursor = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('compliant', 'resolved', 'dismissed') THEN 1 ELSE 0 END) as resolved,
            SUM(CASE WHEN severity = 'critical' AND status NOT IN ('compliant', 'resolved', 'dismissed') THEN 1 ELSE 0 END) as open_critical,
            SUM(CASE WHEN severity IN ('significant', 'moderate') AND status NOT IN ('compliant', 'resolved', 'dismissed') THEN 1 ELSE 0 END) as open_major,
            SUM(CASE WHEN severity = 'advisory' AND status NOT IN ('compliant', 'resolved', 'dismissed') THEN 1 ELSE 0 END) as open_minor
        FROM audit_findings
        WHERE audit_run_id = ?
    """, (audit_id,))
    row = cursor.fetchone()

    return {
        "total": row["total"] or 0,
        "resolved": row["resolved"] or 0,
        "open_critical": row["open_critical"] or 0,
        "open_major": row["open_major"] or 0,
        "open_minor": row["open_minor"] or 0
    }


def _get_task_metrics(institution_id: str, conn: sqlite3.Connection) -> dict:
    """Get task metrics (Phase 44)."""
    try:
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN due_date < datetime('now') AND status != 'completed' THEN 1 ELSE 0 END) as overdue,
                SUM(CASE WHEN due_date >= datetime('now') AND due_date < datetime('now', '+7 days') AND status != 'completed' THEN 1 ELSE 0 END) as due_this_week
            FROM tasks
            WHERE institution_id = ?
        """, (institution_id,))
        row = cursor.fetchone()

        return {
            "total": row["total"] or 0,
            "completed": row["completed"] or 0,
            "overdue": row["overdue"] or 0,
            "due_this_week": row["due_this_week"] or 0
        }
    except Exception:
        # Tasks table may not exist yet
        return {
            "total": 0,
            "completed": 0,
            "overdue": 0,
            "due_this_week": 0
        }


def _get_upcoming_deadlines(institution_id: str, conn: sqlite3.Connection, limit: int = 5) -> list:
    """Get upcoming compliance deadlines."""
    try:
        cursor = conn.execute("""
            SELECT
                title,
                due_date,
                CAST((julianday(due_date) - julianday('now')) AS INTEGER) as days_remaining
            FROM compliance_calendar_events
            WHERE institution_id = ?
              AND due_date >= date('now')
              AND event_type IN ('deadline', 'submission')
            ORDER BY due_date ASC
            LIMIT ?
        """, (institution_id, limit))

        deadlines = []
        for row in cursor.fetchall():
            deadlines.append({
                "title": row["title"],
                "due": row["due_date"],
                "days_remaining": row["days_remaining"]
            })

        return deadlines
    except Exception:
        # Compliance calendar may not exist yet
        return []


def _get_recent_activity_count(institution_id: str, conn: sqlite3.Connection, days: int = 30) -> int:
    """Count recent activity events."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM activity_trail
            WHERE institution_id = ?
              AND timestamp >= ?
        """, (institution_id, cutoff))

        row = cursor.fetchone()
        return row["count"] or 0
    except Exception:
        # Activity trail may not exist yet
        return 0


def _get_last_audit_date(institution_id: str, conn: sqlite3.Connection) -> Optional[str]:
    """Get last audit completion date."""
    cursor = conn.execute("""
        SELECT completed_at
        FROM audit_runs
        WHERE institution_id = ?
          AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
    """, (institution_id,))

    row = cursor.fetchone()
    return row["completed_at"] if row else None


def _generate_attention_summary_ai(
    institution_id: str,
    overview_data: dict
) -> str:
    """Generate AI-powered attention summary."""
    if not _ai_client:
        return _generate_attention_summary_template(overview_data)

    try:
        # Build context for AI
        readiness = overview_data["readiness"]
        findings = overview_data["findings"]
        tasks = overview_data["tasks"]
        deadlines = overview_data["upcoming_deadlines"]

        prompt = f"""Generate a 3-5 sentence executive summary of what needs attention for this institution's accreditation readiness.

Current Readiness Score: {readiness['current']}% (previous: {readiness.get('previous', 'N/A')}%)
Trend: {readiness.get('trend', 'unknown')}

Open Findings:
- Critical: {findings['open_critical']}
- Major: {findings['open_major']}
- Minor: {findings['open_minor']}
- Resolved: {findings['resolved']} of {findings['total']}

Tasks:
- Overdue: {tasks['overdue']}
- Due this week: {tasks['due_this_week']}
- Completed: {tasks['completed']} of {tasks['total']}

Upcoming Deadlines: {len(deadlines)}

Be specific, concise, and actionable. Focus on critical items and urgent deadlines. Use natural, professional language."""

        response = _ai_client.chat(
            user_message=prompt,
            system_prompt="You are an executive accreditation advisor. Provide concise, actionable summaries.",
            model="claude-haiku-3-5-20241022",  # Use Haiku for speed and cost
            track_cost=True,
            institution_id=institution_id,
            operation="executive_attention_summary"
        )

        return response.strip()

    except Exception:
        # Fallback to template if AI fails
        return _generate_attention_summary_template(overview_data)


def _generate_attention_summary_template(overview_data: dict) -> str:
    """Generate template-based attention summary (fallback)."""
    readiness = overview_data["readiness"]
    findings = overview_data["findings"]
    tasks = overview_data["tasks"]
    deadlines = overview_data["upcoming_deadlines"]

    # Build summary parts
    parts = []

    # Readiness trend
    current = readiness["current"]
    previous = readiness.get("previous")
    if previous:
        delta = current - previous
        if delta > 0:
            parts.append(f"Your institution's readiness score has improved {delta} points to {current}% this period.")
        elif delta < 0:
            parts.append(f"Your institution's readiness score has decreased {abs(delta)} points to {current}% this period.")
        else:
            parts.append(f"Your institution's readiness score remains at {current}%.")
    else:
        parts.append(f"Your institution's readiness score is {current}%.")

    # Critical findings
    if findings["open_critical"] > 0:
        parts.append(f"However, {findings['open_critical']} critical finding(s) remain unresolved.")

    # Overdue tasks
    if tasks["overdue"] > 0:
        parts.append(f"{tasks['overdue']} task(s) are overdue.")

    # Upcoming deadlines
    if deadlines:
        next_deadline = deadlines[0]
        parts.append(f"Next deadline: {next_deadline['title']} in {next_deadline['days_remaining']} days.")

    # Call to action
    if findings["open_critical"] > 0 or tasks["overdue"] > 0:
        parts.append("Immediate attention required on critical items.")
    elif current < 75:
        parts.append("Focus on closing compliance gaps to improve readiness.")
    else:
        parts.append("Continue maintaining current compliance levels.")

    return " ".join(parts)


# =============================================================================
# API Endpoints
# =============================================================================

@executive_bp.route("/overview", methods=["GET"])
@require_auth
@require_role("admin")
def get_overview():
    """Get aggregated executive metrics (admin+ only).

    Query params:
        institution_id: Required institution ID

    Returns:
        {
            "success": true,
            "readiness": {"current": 72, "previous": 65, "trend": "up"},
            "documents": {"total": 45, "audited": 38, "compliant": 30, "needing_attention": 8},
            "findings": {"total": 127, "resolved": 98, "open_critical": 3, "open_major": 12, "open_minor": 14},
            "tasks": {"total": 42, "completed": 28, "overdue": 5, "due_this_week": 8},
            "upcoming_deadlines": [...],
            "recent_activity_count": 156,
            "last_audit_date": "2026-03-25"
        }
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    conn = get_conn()
    try:
        # Get current readiness
        readiness_data = get_or_compute_readiness(institution_id)
        current_score = readiness_data["total"]

        # Get previous score (7 days ago)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        cursor = conn.execute("""
            SELECT score
            FROM readiness_snapshots
            WHERE institution_id = ?
              AND recorded_at <= ?
            ORDER BY recorded_at DESC
            LIMIT 1
        """, (institution_id, cutoff))
        prev_row = cursor.fetchone()
        previous_score = int(prev_row["score"]) if prev_row else None

        # Determine trend
        trend = "stable"
        if previous_score:
            if current_score > previous_score + 2:
                trend = "up"
            elif current_score < previous_score - 2:
                trend = "down"

        # Aggregate metrics
        overview = {
            "readiness": {
                "current": current_score,
                "previous": previous_score,
                "trend": trend
            },
            "documents": _get_document_metrics(institution_id, conn),
            "findings": _get_findings_metrics(institution_id, conn),
            "tasks": _get_task_metrics(institution_id, conn),
            "upcoming_deadlines": _get_upcoming_deadlines(institution_id, conn),
            "recent_activity_count": _get_recent_activity_count(institution_id, conn),
            "last_audit_date": _get_last_audit_date(institution_id, conn)
        }

        return jsonify({"success": True, **overview})

    finally:
        conn.close()


@executive_bp.route("/trends", methods=["GET"])
@require_auth
@require_role("admin")
def get_trends():
    """Get readiness trend data (admin+ only).

    Query params:
        institution_id: Required institution ID
        days: Optional number of days to look back (default 90)

    Returns:
        {
            "success": true,
            "trends": [
                {"date": "2026-01-15", "score": 65, "documents_score": 70, ...},
                {"date": "2026-01-22", "score": 68, ...}
            ]
        }
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    days = int(request.args.get("days", 90))

    trend_data = get_readiness_trend(institution_id, days=days)

    return jsonify({
        "success": True,
        "trends": trend_data
    })


@executive_bp.route("/attention", methods=["GET"])
@require_auth
@require_role("admin")
def get_attention_summary():
    """Get AI-generated what-needs-attention summary (admin+ only).

    Query params:
        institution_id: Required institution ID

    Returns:
        {
            "success": true,
            "summary": "Your institution's readiness score has improved 7 points..."
        }
    """
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    # Get overview data for context
    conn = get_conn()
    try:
        # Reuse overview logic
        readiness_data = get_or_compute_readiness(institution_id)
        current_score = readiness_data["total"]

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        cursor = conn.execute("""
            SELECT score FROM readiness_snapshots
            WHERE institution_id = ? AND recorded_at <= ?
            ORDER BY recorded_at DESC LIMIT 1
        """, (institution_id, cutoff))
        prev_row = cursor.fetchone()
        previous_score = int(prev_row["score"]) if prev_row else None

        trend = "stable"
        if previous_score:
            if current_score > previous_score + 2:
                trend = "up"
            elif current_score < previous_score - 2:
                trend = "down"

        overview_data = {
            "readiness": {
                "current": current_score,
                "previous": previous_score,
                "trend": trend
            },
            "documents": _get_document_metrics(institution_id, conn),
            "findings": _get_findings_metrics(institution_id, conn),
            "tasks": _get_task_metrics(institution_id, conn),
            "upcoming_deadlines": _get_upcoming_deadlines(institution_id, conn)
        }

        # Generate AI summary
        summary = _generate_attention_summary_ai(institution_id, overview_data)

        return jsonify({
            "success": True,
            "summary": summary
        })

    finally:
        conn.close()
