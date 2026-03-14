"""Timeline Planner API Blueprint.

Provides REST endpoints for accreditation timeline management:
- CRUD for timelines, phases, milestones
- Template generation and application
- Gantt chart data export
- Progress tracking and statistics
"""

import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from src.db.connection import get_conn


timeline_planner_bp = Blueprint(
    "timeline_planner",
    __name__,
    url_prefix="/api/institutions/<institution_id>/timelines"
)

_workspace_manager = None


def init_timeline_planner_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now().isoformat()


def _parse_json_field(value):
    """Parse a JSON string field, return empty list if invalid."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_dict(row) -> dict:
    """Convert sqlite Row to dict."""
    return dict(row) if row else None


# =============================================================================
# Timeline CRUD
# =============================================================================

@timeline_planner_bp.route("", methods=["GET"])
def list_timelines(institution_id: str):
    """List all timelines for an institution."""
    status_filter = request.args.get("status")

    conn = get_conn()
    query = "SELECT * FROM accreditation_timelines WHERE institution_id = ?"
    params = [institution_id]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY target_date ASC"
    rows = conn.execute(query, params).fetchall()

    timelines = []
    for row in rows:
        tl = dict(row)

        # Get phase count
        tl["phase_count"] = conn.execute(
            "SELECT COUNT(*) FROM timeline_phases WHERE timeline_id = ?",
            (tl["id"],)
        ).fetchone()[0]

        # Get milestone counts
        tl["milestone_count"] = conn.execute(
            "SELECT COUNT(*) FROM timeline_milestones WHERE timeline_id = ?",
            (tl["id"],)
        ).fetchone()[0]

        tl["completed_count"] = conn.execute(
            "SELECT COUNT(*) FROM timeline_milestones WHERE timeline_id = ? AND status = 'completed'",
            (tl["id"],)
        ).fetchone()[0]

        # Check for overdue
        today = datetime.now().strftime("%Y-%m-%d")
        tl["overdue_count"] = conn.execute(
            """SELECT COUNT(*) FROM timeline_milestones
               WHERE timeline_id = ? AND due_date < ? AND status NOT IN ('completed', 'skipped')""",
            (tl["id"], today)
        ).fetchone()[0]

        timelines.append(tl)

    return jsonify({"timelines": timelines, "count": len(timelines)})


@timeline_planner_bp.route("", methods=["POST"])
def create_timeline(institution_id: str):
    """Create a new timeline."""
    data = request.get_json() or {}

    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not data.get("target_date"):
        return jsonify({"error": "target_date is required"}), 400

    timeline_id = _generate_id("tl")
    now = _now_iso()

    conn = get_conn()
    conn.execute(
        """INSERT INTO accreditation_timelines
           (id, institution_id, name, description, accreditor_code, process_type,
            target_date, start_date, status, progress_percentage, color_code,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            timeline_id,
            institution_id,
            data.get("name"),
            data.get("description", ""),
            data.get("accreditor_code", ""),
            data.get("process_type", "initial"),
            data.get("target_date"),
            data.get("start_date"),
            "planning",
            0,
            data.get("color_code", "#c9a84c"),
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({"success": True, "timeline_id": timeline_id}), 201


@timeline_planner_bp.route("/<timeline_id>", methods=["GET"])
def get_timeline(institution_id: str, timeline_id: str):
    """Get a timeline with all phases and milestones."""
    conn = get_conn()

    timeline = conn.execute(
        "SELECT * FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    ).fetchone()

    if not timeline:
        return jsonify({"error": "Timeline not found"}), 404

    result = dict(timeline)

    # Get phases with milestones
    phases = conn.execute(
        "SELECT * FROM timeline_phases WHERE timeline_id = ? ORDER BY phase_order",
        (timeline_id,)
    ).fetchall()

    result["phases"] = []
    for phase in phases:
        phase_dict = dict(phase)

        # Get milestones for phase
        milestones = conn.execute(
            "SELECT * FROM timeline_milestones WHERE phase_id = ? ORDER BY milestone_order",
            (phase["id"],)
        ).fetchall()

        phase_dict["milestones"] = []
        for m in milestones:
            ms = dict(m)
            # Parse JSON fields
            ms["depends_on"] = _parse_json_field(ms.get("depends_on"))
            ms["blocks"] = _parse_json_field(ms.get("blocks"))
            ms["linked_document_ids"] = _parse_json_field(ms.get("linked_document_ids"))
            ms["notes"] = _parse_json_field(ms.get("notes"))
            ms["checklist"] = _parse_json_field(ms.get("checklist"))
            phase_dict["milestones"].append(ms)

        result["phases"].append(phase_dict)

    return jsonify(result)


@timeline_planner_bp.route("/<timeline_id>", methods=["PUT"])
def update_timeline(institution_id: str, timeline_id: str):
    """Update a timeline."""
    data = request.get_json() or {}

    conn = get_conn()

    # Verify exists
    existing = conn.execute(
        "SELECT id FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Timeline not found"}), 404

    # Build update query
    updates = []
    params = []

    for field in ["name", "description", "accreditor_code", "process_type",
                  "target_date", "start_date", "status", "color_code"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(timeline_id)

    conn.execute(
        f"UPDATE accreditation_timelines SET {', '.join(updates)} WHERE id = ?",
        params
    )
    conn.commit()

    return jsonify({"success": True})


@timeline_planner_bp.route("/<timeline_id>", methods=["DELETE"])
def delete_timeline(institution_id: str, timeline_id: str):
    """Delete a timeline and all its phases/milestones."""
    conn = get_conn()

    # CASCADE delete handles phases and milestones
    result = conn.execute(
        "DELETE FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    )
    conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Timeline not found"}), 404

    return jsonify({"success": True, "deleted": timeline_id})


# =============================================================================
# Phase CRUD
# =============================================================================

@timeline_planner_bp.route("/<timeline_id>/phases", methods=["POST"])
def create_phase(institution_id: str, timeline_id: str):
    """Create a new phase in a timeline."""
    data = request.get_json() or {}

    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    conn = get_conn()

    # Verify timeline exists
    timeline = conn.execute(
        "SELECT id FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    ).fetchone()

    if not timeline:
        return jsonify({"error": "Timeline not found"}), 404

    # Get next order
    max_order = conn.execute(
        "SELECT COALESCE(MAX(phase_order), 0) FROM timeline_phases WHERE timeline_id = ?",
        (timeline_id,)
    ).fetchone()[0]

    phase_id = _generate_id("phase")
    now = _now_iso()

    conn.execute(
        """INSERT INTO timeline_phases
           (id, timeline_id, name, description, phase_order, start_date, end_date,
            status, progress_percentage, color_code, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            phase_id,
            timeline_id,
            data.get("name"),
            data.get("description", ""),
            data.get("phase_order", max_order + 1),
            data.get("start_date"),
            data.get("end_date"),
            "pending",
            0,
            data.get("color_code", ""),
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({"success": True, "phase_id": phase_id}), 201


@timeline_planner_bp.route("/<timeline_id>/phases/<phase_id>", methods=["PUT"])
def update_phase(institution_id: str, timeline_id: str, phase_id: str):
    """Update a phase."""
    data = request.get_json() or {}

    conn = get_conn()

    # Verify exists
    existing = conn.execute(
        "SELECT id FROM timeline_phases WHERE id = ? AND timeline_id = ?",
        (phase_id, timeline_id)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Phase not found"}), 404

    updates = []
    params = []

    for field in ["name", "description", "phase_order", "start_date", "end_date",
                  "status", "color_code", "collapsed"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(phase_id)

    conn.execute(
        f"UPDATE timeline_phases SET {', '.join(updates)} WHERE id = ?",
        params
    )

    # Recalculate phase progress
    _update_phase_progress(conn, phase_id)

    conn.commit()

    return jsonify({"success": True})


@timeline_planner_bp.route("/<timeline_id>/phases/<phase_id>", methods=["DELETE"])
def delete_phase(institution_id: str, timeline_id: str, phase_id: str):
    """Delete a phase and its milestones."""
    conn = get_conn()

    result = conn.execute(
        "DELETE FROM timeline_phases WHERE id = ? AND timeline_id = ?",
        (phase_id, timeline_id)
    )
    conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Phase not found"}), 404

    # Recalculate timeline progress
    _update_timeline_progress(conn, timeline_id)
    conn.commit()

    return jsonify({"success": True})


# =============================================================================
# Milestone CRUD
# =============================================================================

@timeline_planner_bp.route("/<timeline_id>/milestones", methods=["POST"])
def create_milestone(institution_id: str, timeline_id: str):
    """Create a new milestone."""
    data = request.get_json() or {}

    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not data.get("phase_id"):
        return jsonify({"error": "phase_id is required"}), 400
    if not data.get("due_date"):
        return jsonify({"error": "due_date is required"}), 400

    conn = get_conn()

    # Verify phase exists
    phase = conn.execute(
        "SELECT id FROM timeline_phases WHERE id = ? AND timeline_id = ?",
        (data["phase_id"], timeline_id)
    ).fetchone()

    if not phase:
        return jsonify({"error": "Phase not found"}), 404

    # Get next order
    max_order = conn.execute(
        "SELECT COALESCE(MAX(milestone_order), 0) FROM timeline_milestones WHERE phase_id = ?",
        (data["phase_id"],)
    ).fetchone()[0]

    milestone_id = _generate_id("ms")
    now = _now_iso()

    conn.execute(
        """INSERT INTO timeline_milestones
           (id, timeline_id, phase_id, name, description, milestone_order, due_date,
            start_date, status, priority, assigned_to, depends_on, checklist,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            milestone_id,
            timeline_id,
            data["phase_id"],
            data.get("name"),
            data.get("description", ""),
            data.get("milestone_order", max_order + 1),
            data.get("due_date"),
            data.get("start_date"),
            "pending",
            data.get("priority", "normal"),
            data.get("assigned_to", ""),
            json.dumps(data.get("depends_on", [])),
            json.dumps(data.get("checklist", [])),
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({"success": True, "milestone_id": milestone_id}), 201


@timeline_planner_bp.route("/<timeline_id>/milestones/<milestone_id>", methods=["PUT"])
def update_milestone(institution_id: str, timeline_id: str, milestone_id: str):
    """Update a milestone."""
    data = request.get_json() or {}

    conn = get_conn()

    # Verify exists
    existing = conn.execute(
        "SELECT phase_id FROM timeline_milestones WHERE id = ? AND timeline_id = ?",
        (milestone_id, timeline_id)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Milestone not found"}), 404

    updates = []
    params = []

    for field in ["name", "description", "milestone_order", "due_date", "start_date",
                  "status", "priority", "assigned_to", "completion_percentage"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    # Handle JSON fields
    for field in ["depends_on", "blocks", "linked_document_ids", "notes", "checklist"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(json.dumps(data[field]))

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(milestone_id)

    conn.execute(
        f"UPDATE timeline_milestones SET {', '.join(updates)} WHERE id = ?",
        params
    )

    # Recalculate progress
    _update_phase_progress(conn, existing["phase_id"])
    _update_timeline_progress(conn, timeline_id)

    conn.commit()

    return jsonify({"success": True})


@timeline_planner_bp.route("/<timeline_id>/milestones/<milestone_id>", methods=["DELETE"])
def delete_milestone(institution_id: str, timeline_id: str, milestone_id: str):
    """Delete a milestone."""
    conn = get_conn()

    # Get phase_id before delete
    existing = conn.execute(
        "SELECT phase_id FROM timeline_milestones WHERE id = ? AND timeline_id = ?",
        (milestone_id, timeline_id)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Milestone not found"}), 404

    conn.execute("DELETE FROM timeline_milestones WHERE id = ?", (milestone_id,))

    # Recalculate progress
    _update_phase_progress(conn, existing["phase_id"])
    _update_timeline_progress(conn, timeline_id)

    conn.commit()

    return jsonify({"success": True})


@timeline_planner_bp.route("/<timeline_id>/milestones/<milestone_id>/complete", methods=["POST"])
def complete_milestone(institution_id: str, timeline_id: str, milestone_id: str):
    """Mark a milestone as complete."""
    conn = get_conn()

    existing = conn.execute(
        "SELECT phase_id, status FROM timeline_milestones WHERE id = ? AND timeline_id = ?",
        (milestone_id, timeline_id)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Milestone not found"}), 404

    now = _now_iso()

    conn.execute(
        """UPDATE timeline_milestones
           SET status = 'completed', completion_percentage = 100, completed_at = ?, updated_at = ?
           WHERE id = ?""",
        (now, now, milestone_id)
    )

    # Recalculate progress
    _update_phase_progress(conn, existing["phase_id"])
    _update_timeline_progress(conn, timeline_id)

    conn.commit()

    return jsonify({"success": True, "completed_at": now})


# =============================================================================
# Gantt Data Export
# =============================================================================

@timeline_planner_bp.route("/<timeline_id>/gantt", methods=["GET"])
def get_gantt_data(institution_id: str, timeline_id: str):
    """Get timeline data formatted for Gantt chart visualization."""
    conn = get_conn()

    timeline = conn.execute(
        "SELECT * FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    ).fetchone()

    if not timeline:
        return jsonify({"error": "Timeline not found"}), 404

    gantt_data = {
        "timeline": dict(timeline),
        "items": [],
        "dependencies": [],
    }

    phases = conn.execute(
        "SELECT * FROM timeline_phases WHERE timeline_id = ? ORDER BY phase_order",
        (timeline_id,)
    ).fetchall()

    today = datetime.now().strftime("%Y-%m-%d")

    for phase in phases:
        # Phase as group row
        gantt_data["items"].append({
            "id": phase["id"],
            "type": "phase",
            "name": phase["name"],
            "start_date": phase["start_date"],
            "end_date": phase["end_date"],
            "progress": phase["progress_percentage"],
            "status": phase["status"],
            "color": phase["color_code"] or timeline["color_code"],
            "order": phase["phase_order"],
            "collapsed": bool(phase["collapsed"]),
            "parent": None,
        })

        # Milestones within phase
        milestones = conn.execute(
            "SELECT * FROM timeline_milestones WHERE phase_id = ? ORDER BY milestone_order",
            (phase["id"],)
        ).fetchall()

        for ms in milestones:
            # Auto-mark overdue
            status = ms["status"]
            if status not in ("completed", "skipped") and ms["due_date"] < today:
                status = "overdue"

            gantt_data["items"].append({
                "id": ms["id"],
                "type": "milestone",
                "name": ms["name"],
                "start_date": ms["start_date"] or ms["due_date"],
                "end_date": ms["due_date"],
                "progress": ms["completion_percentage"],
                "status": status,
                "priority": ms["priority"],
                "assigned_to": ms["assigned_to"],
                "order": ms["milestone_order"],
                "parent": phase["id"],
            })

            # Add dependencies
            depends_on = _parse_json_field(ms["depends_on"])
            for dep_id in depends_on:
                gantt_data["dependencies"].append({
                    "from": dep_id,
                    "to": ms["id"],
                })

    return jsonify(gantt_data)


# =============================================================================
# Statistics
# =============================================================================

@timeline_planner_bp.route("/<timeline_id>/stats", methods=["GET"])
def get_timeline_stats(institution_id: str, timeline_id: str):
    """Get detailed statistics for a timeline."""
    conn = get_conn()

    timeline = conn.execute(
        "SELECT * FROM accreditation_timelines WHERE id = ? AND institution_id = ?",
        (timeline_id, institution_id)
    ).fetchone()

    if not timeline:
        return jsonify({"error": "Timeline not found"}), 404

    today = datetime.now().strftime("%Y-%m-%d")

    # Status counts
    status_counts = {}
    for status in ["pending", "in_progress", "completed", "overdue", "blocked", "skipped"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM timeline_milestones WHERE timeline_id = ? AND status = ?",
            (timeline_id, status)
        ).fetchone()[0]
        status_counts[status] = count

    # Check for overdue (not yet marked)
    overdue_check = conn.execute(
        """SELECT COUNT(*) FROM timeline_milestones
           WHERE timeline_id = ? AND due_date < ? AND status NOT IN ('completed', 'skipped', 'overdue')""",
        (timeline_id, today)
    ).fetchone()[0]
    status_counts["overdue"] += overdue_check

    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)

    # Phase progress
    phases = conn.execute(
        "SELECT id, name, progress_percentage, status, phase_order FROM timeline_phases WHERE timeline_id = ? ORDER BY phase_order",
        (timeline_id,)
    ).fetchall()

    # Upcoming milestones (next 14 days)
    two_weeks = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    upcoming = conn.execute(
        """SELECT m.*, p.name as phase_name FROM timeline_milestones m
           JOIN timeline_phases p ON m.phase_id = p.id
           WHERE m.timeline_id = ? AND m.due_date BETWEEN ? AND ? AND m.status NOT IN ('completed', 'skipped')
           ORDER BY m.due_date LIMIT 5""",
        (timeline_id, today, two_weeks)
    ).fetchall()

    # Critical items
    critical = conn.execute(
        """SELECT m.*, p.name as phase_name FROM timeline_milestones m
           JOIN timeline_phases p ON m.phase_id = p.id
           WHERE m.timeline_id = ? AND m.priority = 'critical' AND m.status NOT IN ('completed', 'skipped')
           ORDER BY m.due_date LIMIT 5""",
        (timeline_id,)
    ).fetchall()

    return jsonify({
        "total_milestones": total,
        "status_counts": status_counts,
        "completion_rate": round(completed / total * 100) if total > 0 else 0,
        "overdue_count": status_counts.get("overdue", 0),
        "phases": [dict(p) for p in phases],
        "upcoming_milestones": [dict(u) for u in upcoming],
        "critical_items": [dict(c) for c in critical],
        "days_to_target": (datetime.strptime(timeline["target_date"], "%Y-%m-%d") - datetime.now()).days if timeline["target_date"] else None,
    })


# =============================================================================
# Template Generation
# =============================================================================

@timeline_planner_bp.route("/generate-from-template", methods=["POST"])
def generate_from_template(institution_id: str):
    """Generate a timeline from a template."""
    data = request.get_json() or {}

    template_id = data.get("template_id")
    target_date = data.get("target_date")
    name = data.get("name")

    if not template_id:
        return jsonify({"error": "template_id is required"}), 400
    if not target_date:
        return jsonify({"error": "target_date is required"}), 400

    conn = get_conn()

    # Load template
    template = conn.execute(
        "SELECT * FROM timeline_templates WHERE id = ?",
        (template_id,)
    ).fetchone()

    if not template:
        return jsonify({"error": "Template not found"}), 404

    template_data = dict(template)
    target = datetime.strptime(target_date, "%Y-%m-%d")
    now = _now_iso()

    # Parse template definitions
    phases_def = json.loads(template_data["phases"])
    milestones_def = json.loads(template_data["milestones"])

    # Create timeline
    timeline_id = _generate_id("tl")

    # Calculate start date from first phase
    earliest_days = max(p.get("days_before_end", 0) for p in phases_def)
    start_date = (target - timedelta(days=earliest_days)).strftime("%Y-%m-%d")

    conn.execute(
        """INSERT INTO accreditation_timelines
           (id, institution_id, name, description, accreditor_code, process_type,
            target_date, start_date, status, created_from_template, color_code,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            timeline_id,
            institution_id,
            name or f"{template_data['name']} - {target_date}",
            template_data["description"],
            template_data["accreditor_code"],
            template_data["process_type"],
            target_date,
            start_date,
            "planning",
            template_id,
            "#c9a84c",
            now,
            now,
        )
    )

    # Create phases
    phase_id_map = {}
    phases_created = 0

    for phase_def in sorted(phases_def, key=lambda p: p["order"]):
        phase_id = _generate_id("phase")
        phase_id_map[phase_def["order"]] = phase_id

        phase_start = (target - timedelta(days=phase_def.get("days_before_end", 30))).strftime("%Y-%m-%d")
        phase_end = (target - timedelta(days=phase_def.get("days_before_start", 0))).strftime("%Y-%m-%d")

        conn.execute(
            """INSERT INTO timeline_phases
               (id, timeline_id, name, description, phase_order, start_date, end_date,
                status, color_code, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                phase_id,
                timeline_id,
                phase_def["name"],
                phase_def.get("description", ""),
                phase_def["order"],
                phase_start,
                phase_end,
                "pending",
                phase_def.get("color_code", ""),
                now,
                now,
            )
        )
        phases_created += 1

    # Create milestones
    milestones_created = 0

    for ms_def in milestones_def:
        phase_id = phase_id_map.get(ms_def.get("phase_order"))
        if not phase_id:
            continue

        ms_id = _generate_id("ms")
        ms_date = (target - timedelta(days=ms_def.get("days_before_target", 0))).strftime("%Y-%m-%d")

        conn.execute(
            """INSERT INTO timeline_milestones
               (id, timeline_id, phase_id, name, description, milestone_order,
                due_date, status, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ms_id,
                timeline_id,
                phase_id,
                ms_def["name"],
                ms_def.get("description", ""),
                ms_def.get("order", 0),
                ms_date,
                "pending",
                ms_def.get("priority", "normal"),
                now,
                now,
            )
        )
        milestones_created += 1

    conn.commit()

    return jsonify({
        "success": True,
        "timeline_id": timeline_id,
        "phases_created": phases_created,
        "milestones_created": milestones_created,
    }), 201


# =============================================================================
# Templates List
# =============================================================================

@timeline_planner_bp.route("/templates", methods=["GET"])
def list_templates(institution_id: str):
    """List available timeline templates."""
    conn = get_conn()

    accreditor = request.args.get("accreditor")

    query = "SELECT id, name, accreditor_code, process_type, description, default_duration_days, is_system_template FROM timeline_templates"
    params = []

    if accreditor:
        query += " WHERE accreditor_code = ? OR accreditor_code IS NULL"
        params.append(accreditor)

    query += " ORDER BY is_system_template DESC, name ASC"

    rows = conn.execute(query, params).fetchall()

    return jsonify({
        "templates": [dict(r) for r in rows],
        "count": len(rows),
    })


# =============================================================================
# Helper Functions
# =============================================================================

def _update_phase_progress(conn, phase_id: str):
    """Recalculate phase progress from milestones."""
    result = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
           FROM timeline_milestones WHERE phase_id = ?""",
        (phase_id,)
    ).fetchone()

    if result["total"] > 0:
        progress = round(result["completed"] / result["total"] * 100)
        status = "completed" if progress == 100 else "in_progress" if progress > 0 else "pending"
    else:
        progress = 0
        status = "pending"

    conn.execute(
        "UPDATE timeline_phases SET progress_percentage = ?, status = ?, updated_at = ? WHERE id = ?",
        (progress, status, _now_iso(), phase_id)
    )


def _update_timeline_progress(conn, timeline_id: str):
    """Recalculate timeline progress from all milestones."""
    result = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
           FROM timeline_milestones WHERE timeline_id = ?""",
        (timeline_id,)
    ).fetchone()

    if result["total"] > 0:
        progress = round(result["completed"] / result["total"] * 100)
        status = "completed" if progress == 100 else "active" if progress > 0 else "planning"
    else:
        progress = 0
        status = "planning"

    conn.execute(
        "UPDATE accreditation_timelines SET progress_percentage = ?, status = ?, updated_at = ? WHERE id = ?",
        (progress, status, _now_iso(), timeline_id)
    )
