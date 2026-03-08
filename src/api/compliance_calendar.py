"""Compliance Calendar API Blueprint.

Handles calendar events, deadlines, reminders, and timeline management.
"""

import json
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from src.core.models import AgentSession, generate_id, now_iso
from src.db.connection import get_conn
from src.agents.base_agent import AgentType
from src.agents.registry import AgentRegistry


compliance_calendar_bp = Blueprint("compliance_calendar", __name__, url_prefix="/api/calendar")

_workspace_manager = None


def init_compliance_calendar_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


# =============================================================================
# Calendar Events CRUD
# =============================================================================

@compliance_calendar_bp.route("/events", methods=["GET"])
def list_events():
    """List calendar events."""
    institution_id = request.args.get("institution_id")
    days_ahead = request.args.get("days_ahead", 90, type=int)
    event_type = request.args.get("event_type")
    status = request.args.get("status")
    include_completed = request.args.get("include_completed", "false").lower() == "true"

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    query = """
        SELECT * FROM compliance_calendar
        WHERE institution_id = ?
        AND due_date <= ?
    """
    params = [institution_id, future_date]

    if not include_completed:
        query += " AND status != 'completed'"

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY due_date ASC"

    rows = conn.execute(query, params).fetchall()

    events = []
    for row in rows:
        event = dict(row)
        # Calculate days until due
        if event.get("due_date"):
            try:
                due = datetime.strptime(event["due_date"], "%Y-%m-%d")
                event["days_until"] = (due - datetime.now()).days
            except ValueError:
                event["days_until"] = None
        events.append(event)

    return jsonify({
        "events": events,
        "count": len(events),
    })


@compliance_calendar_bp.route("/events/<event_id>", methods=["GET"])
def get_event(event_id: str):
    """Get a specific calendar event."""
    conn = get_conn()

    event = conn.execute(
        "SELECT * FROM compliance_calendar WHERE id = ?",
        (event_id,)
    ).fetchone()

    if not event:
        return jsonify({"error": "Event not found"}), 404

    event_data = dict(event)
    if event_data.get("due_date"):
        try:
            due = datetime.strptime(event_data["due_date"], "%Y-%m-%d")
            event_data["days_until"] = (due - datetime.now()).days
        except ValueError:
            pass

    return jsonify(event_data)


@compliance_calendar_bp.route("/events", methods=["POST"])
def create_event():
    """Create a new calendar event."""
    data = request.get_json()

    if not data.get("institution_id"):
        return jsonify({"error": "institution_id is required"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400
    if not data.get("due_date"):
        return jsonify({"error": "due_date is required"}), 400

    # Validate date format
    try:
        datetime.strptime(data["due_date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "due_date must be in YYYY-MM-DD format"}), 400

    event_id = generate_id("evt")
    now = now_iso()

    conn = get_conn()
    conn.execute(
        """INSERT INTO compliance_calendar
           (id, institution_id, event_type, title, description, due_date,
            reminder_days, recurrence, accreditor_code, related_entity_type,
            related_entity_id, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            data.get("institution_id"),
            data.get("event_type", "deadline"),
            data.get("title"),
            data.get("description", ""),
            data.get("due_date"),
            data.get("reminder_days", 30),
            data.get("recurrence", "none"),
            data.get("accreditor_code", ""),
            data.get("related_entity_type", ""),
            data.get("related_entity_id", ""),
            "pending",
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({
        "id": event_id,
        "status": "created",
    }), 201


@compliance_calendar_bp.route("/events/<event_id>", methods=["PATCH"])
def update_event(event_id: str):
    """Update a calendar event."""
    data = request.get_json()
    conn = get_conn()

    # Check exists
    existing = conn.execute(
        "SELECT id FROM compliance_calendar WHERE id = ?",
        (event_id,)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Event not found"}), 404

    updates = []
    params = []

    for field in ["event_type", "title", "description", "due_date",
                  "reminder_days", "recurrence", "accreditor_code", "status"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if updates:
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(event_id)

        conn.execute(
            f"UPDATE compliance_calendar SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    return jsonify({"id": event_id, "status": "updated"})


@compliance_calendar_bp.route("/events/<event_id>", methods=["DELETE"])
def delete_event(event_id: str):
    """Delete a calendar event."""
    conn = get_conn()

    result = conn.execute(
        "DELETE FROM compliance_calendar WHERE id = ?",
        (event_id,)
    )
    conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Event not found"}), 404

    return jsonify({"id": event_id, "status": "deleted"})


@compliance_calendar_bp.route("/events/<event_id>/complete", methods=["POST"])
def complete_event(event_id: str):
    """Mark an event as completed."""
    conn = get_conn()
    now = now_iso()

    # Get event
    event = conn.execute(
        "SELECT * FROM compliance_calendar WHERE id = ?",
        (event_id,)
    ).fetchone()

    if not event:
        return jsonify({"error": "Event not found"}), 404

    event_data = dict(event)

    # Update status
    conn.execute(
        """UPDATE compliance_calendar
           SET status = 'completed', completed_at = ?, updated_at = ?
           WHERE id = ?""",
        (now, now, event_id)
    )

    next_occurrence_id = None

    # Handle recurrence
    if event_data.get("recurrence") and event_data["recurrence"] != "none":
        current_due = datetime.strptime(event_data["due_date"], "%Y-%m-%d")

        if event_data["recurrence"] == "annual":
            next_due = current_due.replace(year=current_due.year + 1)
        elif event_data["recurrence"] == "semi-annual":
            next_due = current_due + timedelta(days=182)
        elif event_data["recurrence"] == "quarterly":
            next_due = current_due + timedelta(days=91)
        else:
            next_due = None

        if next_due:
            next_occurrence_id = generate_id("evt")
            conn.execute(
                """INSERT INTO compliance_calendar
                   (id, institution_id, event_type, title, description, due_date,
                    reminder_days, recurrence, accreditor_code, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    next_occurrence_id,
                    event_data["institution_id"],
                    event_data["event_type"],
                    event_data["title"],
                    event_data.get("description", ""),
                    next_due.strftime("%Y-%m-%d"),
                    event_data.get("reminder_days", 30),
                    event_data["recurrence"],
                    event_data.get("accreditor_code", ""),
                    "pending",
                    now,
                    now,
                )
            )

    conn.commit()

    return jsonify({
        "id": event_id,
        "status": "completed",
        "next_occurrence_id": next_occurrence_id,
    })


# =============================================================================
# Reminders
# =============================================================================

@compliance_calendar_bp.route("/reminders", methods=["GET"])
def get_reminders():
    """Get reminders for upcoming deadlines."""
    institution_id = request.args.get("institution_id")
    days_ahead = request.args.get("days_ahead", 30, type=int)

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now()
    future_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT * FROM compliance_calendar
           WHERE institution_id = ?
           AND due_date <= ?
           AND status IN ('pending', 'reminded', 'overdue')
           ORDER BY due_date ASC""",
        (institution_id, future_date)
    ).fetchall()

    reminders = []
    for row in rows:
        event = dict(row)
        due = datetime.strptime(event["due_date"], "%Y-%m-%d")
        days_until = (due - today).days

        # Determine priority
        if days_until < 0:
            priority = "critical"
            message = f"OVERDUE: {event['title']} was due {abs(days_until)} days ago!"
        elif days_until == 0:
            priority = "critical"
            message = f"DUE TODAY: {event['title']}"
        elif days_until <= 3:
            priority = "high"
            message = f"Due in {days_until} days: {event['title']}"
        elif days_until <= 7:
            priority = "high"
            message = f"Due this week: {event['title']} ({event['due_date']})"
        elif days_until <= 14:
            priority = "normal"
            message = f"Coming up: {event['title']} due {event['due_date']}"
        else:
            priority = "low"
            message = f"Upcoming: {event['title']} due {event['due_date']}"

        reminders.append({
            "event_id": event["id"],
            "event_title": event["title"],
            "due_date": event["due_date"],
            "days_until": days_until,
            "priority": priority,
            "message": message,
            "event_type": event["event_type"],
        })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    reminders.sort(key=lambda r: (priority_order.get(r["priority"], 4), r["days_until"]))

    return jsonify({
        "reminders": reminders,
        "count": len(reminders),
        "critical_count": sum(1 for r in reminders if r["priority"] == "critical"),
        "high_count": sum(1 for r in reminders if r["priority"] == "high"),
    })


# =============================================================================
# Overdue Events
# =============================================================================

@compliance_calendar_bp.route("/overdue", methods=["GET"])
def get_overdue():
    """Get all overdue events."""
    institution_id = request.args.get("institution_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT * FROM compliance_calendar
           WHERE institution_id = ?
           AND due_date < ?
           AND status != 'completed'
           ORDER BY due_date ASC""",
        (institution_id, today)
    ).fetchall()

    events = []
    for row in rows:
        event = dict(row)
        due = datetime.strptime(event["due_date"], "%Y-%m-%d")
        event["days_overdue"] = (datetime.now() - due).days
        events.append(event)

        # Update status to overdue
        if event["status"] != "overdue":
            conn.execute(
                "UPDATE compliance_calendar SET status = 'overdue', updated_at = ? WHERE id = ?",
                (now_iso(), event["id"])
            )

    conn.commit()

    return jsonify({
        "overdue_events": events,
        "count": len(events),
    })


# =============================================================================
# Timeline Generation
# =============================================================================

@compliance_calendar_bp.route("/timeline", methods=["POST"])
def generate_timeline():
    """Generate a milestone timeline for an accreditation process."""
    data = request.get_json()

    institution_id = data.get("institution_id")
    process_type = data.get("process_type")
    target_date = data.get("target_date")
    accreditor_code = data.get("accreditor_code", "")

    if not institution_id or not process_type or not target_date:
        return jsonify({"error": "institution_id, process_type, and target_date are required"}), 400

    # Create agent session
    session = AgentSession(
        agent_type=AgentType.COMPLIANCE_CALENDAR.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.COMPLIANCE_CALENDAR,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Calendar agent"}), 500

    result = agent._tool_calculate_timeline({
        "institution_id": institution_id,
        "process_type": process_type,
        "target_date": target_date,
        "accreditor_code": accreditor_code,
    })

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


# =============================================================================
# Sync Action Plans
# =============================================================================

@compliance_calendar_bp.route("/sync-action-plans", methods=["POST"])
def sync_action_plans():
    """Sync action plan deadlines to calendar."""
    data = request.get_json()
    institution_id = data.get("institution_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    session = AgentSession(
        agent_type=AgentType.COMPLIANCE_CALENDAR.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.COMPLIANCE_CALENDAR,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Calendar agent"}), 500

    result = agent._tool_sync_action_plans({"institution_id": institution_id})

    return jsonify(result)


# =============================================================================
# Export
# =============================================================================

@compliance_calendar_bp.route("/export", methods=["GET"])
def export_calendar():
    """Export calendar to iCal or JSON."""
    institution_id = request.args.get("institution_id")
    export_format = request.args.get("format", "json")
    days_ahead = request.args.get("days_ahead", 365, type=int)

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    session = AgentSession(
        agent_type=AgentType.COMPLIANCE_CALENDAR.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.COMPLIANCE_CALENDAR,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Calendar agent"}), 500

    result = agent._tool_export_calendar({
        "institution_id": institution_id,
        "format": export_format,
        "days_ahead": days_ahead,
    })

    return jsonify(result)


# =============================================================================
# Dashboard Stats
# =============================================================================

@compliance_calendar_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get calendar statistics for dashboard."""
    institution_id = request.args.get("institution_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    week_ahead = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    month_ahead = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Total events
    total = conn.execute(
        "SELECT COUNT(*) FROM compliance_calendar WHERE institution_id = ?",
        (institution_id,)
    ).fetchone()[0]

    # Overdue
    overdue = conn.execute(
        """SELECT COUNT(*) FROM compliance_calendar
           WHERE institution_id = ? AND due_date < ? AND status != 'completed'""",
        (institution_id, today)
    ).fetchone()[0]

    # Due this week
    this_week = conn.execute(
        """SELECT COUNT(*) FROM compliance_calendar
           WHERE institution_id = ? AND due_date >= ? AND due_date <= ?
           AND status != 'completed'""",
        (institution_id, today, week_ahead)
    ).fetchone()[0]

    # Due this month
    this_month = conn.execute(
        """SELECT COUNT(*) FROM compliance_calendar
           WHERE institution_id = ? AND due_date >= ? AND due_date <= ?
           AND status != 'completed'""",
        (institution_id, today, month_ahead)
    ).fetchone()[0]

    # Completed
    completed = conn.execute(
        "SELECT COUNT(*) FROM compliance_calendar WHERE institution_id = ? AND status = 'completed'",
        (institution_id,)
    ).fetchone()[0]

    # Next deadline
    next_event = conn.execute(
        """SELECT title, due_date FROM compliance_calendar
           WHERE institution_id = ? AND due_date >= ? AND status != 'completed'
           ORDER BY due_date ASC LIMIT 1""",
        (institution_id, today)
    ).fetchone()

    return jsonify({
        "total": total,
        "overdue": overdue,
        "due_this_week": this_week,
        "due_this_month": this_month,
        "completed": completed,
        "next_deadline": dict(next_event) if next_event else None,
    })
