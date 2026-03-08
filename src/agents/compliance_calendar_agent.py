"""Compliance Calendar Agent.

Manages accreditation deadlines, reporting requirements, and renewal dates:
- Track upcoming deadlines and due dates
- Create and manage calendar events
- Generate timeline sequences for milestones
- Send reminders before deadlines
- Sync with action plans
- Export calendar data
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, AgentResult, now_iso, generate_id
from src.db.connection import get_conn


@dataclass
class CalendarEvent:
    """A compliance calendar event."""
    id: str = field(default_factory=lambda: generate_id("evt"))
    institution_id: str = ""
    event_type: str = ""  # deadline, renewal, report_due, visit, review
    title: str = ""
    description: str = ""
    due_date: str = ""
    reminder_days: int = 30
    recurrence: str = "none"  # none, annual, semi-annual, quarterly
    accreditor_code: str = ""
    related_entity_type: str = ""  # team_report, finding, document, action_plan
    related_entity_id: str = ""
    status: str = "pending"  # pending, reminded, completed, overdue
    completed_at: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date,
            "reminder_days": self.reminder_days,
            "recurrence": self.recurrence,
            "accreditor_code": self.accreditor_code,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "status": self.status,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarEvent":
        known_fields = {
            "id", "institution_id", "event_type", "title", "description",
            "due_date", "reminder_days", "recurrence", "accreditor_code",
            "related_entity_type", "related_entity_id", "status",
            "completed_at", "created_at", "updated_at"
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class Reminder:
    """A generated reminder for an upcoming deadline."""
    id: str = field(default_factory=lambda: generate_id("rem"))
    event_id: str = ""
    event_title: str = ""
    due_date: str = ""
    days_until: int = 0
    priority: str = "normal"  # low, normal, high, critical
    message: str = ""
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_title": self.event_title,
            "due_date": self.due_date,
            "days_until": self.days_until,
            "priority": self.priority,
            "message": self.message,
            "created_at": self.created_at,
        }


@register_agent(AgentType.COMPLIANCE_CALENDAR)
class ComplianceCalendarAgent(BaseAgent):
    """Agent for managing compliance calendar and deadlines."""

    def __init__(self, session: AgentSession, workspace_manager=None, on_update=None):
        super().__init__(session, workspace_manager, on_update)
        self._events: List[CalendarEvent] = []
        self._reminders: List[Reminder] = []

    @property
    def agent_type(self) -> AgentType:
        return AgentType.COMPLIANCE_CALENDAR

    @property
    def system_prompt(self) -> str:
        return """You are an expert accreditation compliance calendar manager. Your role is to help
institutions track and manage all accreditation-related deadlines and milestones.

EXPERTISE:
- Deep understanding of accreditation cycles and timelines
- Knowledge of reporting requirements for various accreditors
- Experience with compliance deadline management

RESPONSIBILITIES:
- Track all accreditation deadlines and due dates
- Generate reminders before critical deadlines
- Calculate milestone sequences for accreditation processes
- Identify potential timeline conflicts
- Ensure no deadlines are missed

ACCREDITATION CYCLES:
- Annual reports (typically due 60-90 days after fiscal year end)
- Renewal cycles (5-10 years depending on accreditor)
- Substantive change notifications (30-180 days depending on type)
- Team visit follow-ups (typically 30-90 days post-visit)"""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_calendar_events",
                "description": "List upcoming calendar events and deadlines.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "days_ahead": {"type": "integer", "description": "Number of days to look ahead (default 90)"},
                        "event_type": {"type": "string", "description": "Filter by event type"},
                        "include_completed": {"type": "boolean", "description": "Include completed events"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "create_deadline",
                "description": "Create a new deadline or calendar event.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "event_type": {
                            "type": "string",
                            "enum": ["deadline", "renewal", "report_due", "visit", "review"],
                            "description": "Type of event"
                        },
                        "title": {"type": "string", "description": "Event title"},
                        "description": {"type": "string", "description": "Event description"},
                        "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
                        "reminder_days": {"type": "integer", "description": "Days before to remind"},
                        "recurrence": {
                            "type": "string",
                            "enum": ["none", "annual", "semi-annual", "quarterly"],
                            "description": "Recurrence pattern"
                        },
                        "accreditor_code": {"type": "string", "description": "Accreditor code"},
                    },
                    "required": ["institution_id", "title", "due_date"],
                },
            },
            {
                "name": "calculate_timeline",
                "description": "Calculate a sequence of milestone dates for an accreditation process.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "process_type": {
                            "type": "string",
                            "enum": ["initial_accreditation", "reaffirmation", "substantive_change", "team_visit_response"],
                            "description": "Type of accreditation process"
                        },
                        "target_date": {"type": "string", "description": "Target completion date (YYYY-MM-DD)"},
                        "accreditor_code": {"type": "string", "description": "Accreditor code"},
                    },
                    "required": ["institution_id", "process_type", "target_date"],
                },
            },
            {
                "name": "generate_reminders",
                "description": "Generate reminders for upcoming deadlines.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "days_ahead": {"type": "integer", "description": "Check deadlines within N days"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "sync_action_plans",
                "description": "Sync action plan deadlines to the calendar.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "export_calendar",
                "description": "Export calendar events to iCal or JSON format.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "format": {
                            "type": "string",
                            "enum": ["ical", "json"],
                            "description": "Export format"
                        },
                        "days_ahead": {"type": "integer", "description": "Days to include"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "mark_complete",
                "description": "Mark a calendar event as completed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "Event ID to mark complete"},
                    },
                    "required": ["event_id"],
                },
            },
            {
                "name": "get_overdue",
                "description": "Get all overdue events for an institution.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "get_calendar_events": self._tool_get_events,
            "create_deadline": self._tool_create_deadline,
            "calculate_timeline": self._tool_calculate_timeline,
            "generate_reminders": self._tool_generate_reminders,
            "sync_action_plans": self._tool_sync_action_plans,
            "export_calendar": self._tool_export_calendar,
            "mark_complete": self._tool_mark_complete,
            "get_overdue": self._tool_get_overdue,
        }
        handler = handlers.get(tool_name)
        return handler(tool_input) if handler else {"error": f"Unknown tool: {tool_name}"}

    def _tool_get_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get calendar events for an institution."""
        institution_id = params.get("institution_id", "")
        days_ahead = params.get("days_ahead", 90)
        event_type = params.get("event_type")
        include_completed = params.get("include_completed", False)

        if not institution_id:
            return {"error": "institution_id is required"}

        conn = get_conn()
        today = datetime.now().strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        query = """
            SELECT * FROM compliance_calendar
            WHERE institution_id = ?
            AND due_date <= ?
        """
        params_list = [institution_id, future_date]

        if not include_completed:
            query += " AND status != 'completed'"

        if event_type:
            query += " AND event_type = ?"
            params_list.append(event_type)

        query += " ORDER BY due_date ASC"

        rows = conn.execute(query, params_list).fetchall()

        events = []
        for row in rows:
            event = dict(row)
            # Calculate days until
            if event.get("due_date"):
                due = datetime.strptime(event["due_date"], "%Y-%m-%d")
                event["days_until"] = (due - datetime.now()).days

                # Update status if overdue
                if event["days_until"] < 0 and event["status"] == "pending":
                    event["status"] = "overdue"
            events.append(event)

        return {
            "events": events,
            "count": len(events),
            "days_ahead": days_ahead,
        }

    def _tool_create_deadline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event."""
        institution_id = params.get("institution_id", "")
        event_type = params.get("event_type", "deadline")
        title = params.get("title", "")
        description = params.get("description", "")
        due_date = params.get("due_date", "")
        reminder_days = params.get("reminder_days", 30)
        recurrence = params.get("recurrence", "none")
        accreditor_code = params.get("accreditor_code", "")

        if not institution_id or not title or not due_date:
            return {"error": "institution_id, title, and due_date are required"}

        # Validate date format
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            return {"error": "due_date must be in YYYY-MM-DD format"}

        event_id = generate_id("evt")
        now = now_iso()

        conn = get_conn()
        conn.execute(
            """INSERT INTO compliance_calendar
               (id, institution_id, event_type, title, description, due_date,
                reminder_days, recurrence, accreditor_code, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                institution_id,
                event_type,
                title,
                description,
                due_date,
                reminder_days,
                recurrence,
                accreditor_code,
                "pending",
                now,
                now,
            )
        )
        conn.commit()

        return {
            "success": True,
            "event_id": event_id,
            "title": title,
            "due_date": due_date,
            "event_type": event_type,
        }

    def _tool_calculate_timeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate milestone timeline for an accreditation process."""
        institution_id = params.get("institution_id", "")
        process_type = params.get("process_type", "")
        target_date = params.get("target_date", "")
        accreditor_code = params.get("accreditor_code", "")

        if not institution_id or not process_type or not target_date:
            return {"error": "institution_id, process_type, and target_date are required"}

        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            return {"error": "target_date must be in YYYY-MM-DD format"}

        # Define milestone templates for different processes
        templates = {
            "initial_accreditation": [
                {"name": "Submit Application", "days_before": 365},
                {"name": "Application Review Complete", "days_before": 300},
                {"name": "Self-Study Begins", "days_before": 270},
                {"name": "Self-Study Draft Complete", "days_before": 180},
                {"name": "Self-Study Final", "days_before": 120},
                {"name": "Site Visit Preparation", "days_before": 90},
                {"name": "Site Visit", "days_before": 60},
                {"name": "Team Report Response Due", "days_before": 30},
                {"name": "Commission Decision", "days_before": 0},
            ],
            "reaffirmation": [
                {"name": "Begin Self-Study Planning", "days_before": 540},
                {"name": "Compliance Certification Due", "days_before": 365},
                {"name": "QEP Development Begins", "days_before": 300},
                {"name": "Self-Study Draft", "days_before": 180},
                {"name": "Self-Study Final", "days_before": 120},
                {"name": "On-Site Review", "days_before": 60},
                {"name": "Response to Team Report", "days_before": 30},
                {"name": "Reaffirmation Decision", "days_before": 0},
            ],
            "substantive_change": [
                {"name": "Identify Change Requirements", "days_before": 180},
                {"name": "Prepare Prospectus", "days_before": 150},
                {"name": "Submit Prospectus", "days_before": 120},
                {"name": "Staff Review Period", "days_before": 90},
                {"name": "Site Visit (if required)", "days_before": 45},
                {"name": "Decision Date", "days_before": 0},
            ],
            "team_visit_response": [
                {"name": "Receive Team Report", "days_before": 60},
                {"name": "Review Findings", "days_before": 55},
                {"name": "Draft Response", "days_before": 40},
                {"name": "Evidence Gathering Complete", "days_before": 25},
                {"name": "Internal Review", "days_before": 15},
                {"name": "Final Response Due", "days_before": 0},
            ],
        }

        template = templates.get(process_type)
        if not template:
            return {"error": f"Unknown process type: {process_type}"}

        # Calculate dates
        milestones = []
        events_created = 0
        conn = get_conn()
        now = now_iso()

        for milestone in template:
            milestone_date = target - timedelta(days=milestone["days_before"])
            milestone_data = {
                "name": milestone["name"],
                "date": milestone_date.strftime("%Y-%m-%d"),
                "days_before_target": milestone["days_before"],
            }
            milestones.append(milestone_data)

            # Create calendar event
            event_id = generate_id("evt")
            conn.execute(
                """INSERT INTO compliance_calendar
                   (id, institution_id, event_type, title, description, due_date,
                    reminder_days, accreditor_code, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    institution_id,
                    "deadline",
                    f"{process_type.replace('_', ' ').title()}: {milestone['name']}",
                    f"Milestone for {process_type.replace('_', ' ')} process",
                    milestone_date.strftime("%Y-%m-%d"),
                    14,  # 2 weeks reminder
                    accreditor_code,
                    "pending",
                    now,
                    now,
                )
            )
            events_created += 1

        conn.commit()

        return {
            "success": True,
            "process_type": process_type,
            "target_date": target_date,
            "milestones": milestones,
            "events_created": events_created,
        }

    def _tool_generate_reminders(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate reminders for upcoming deadlines."""
        institution_id = params.get("institution_id", "")
        days_ahead = params.get("days_ahead", 30)

        if not institution_id:
            return {"error": "institution_id is required"}

        conn = get_conn()
        today = datetime.now()
        future_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Get upcoming events
        rows = conn.execute(
            """SELECT * FROM compliance_calendar
               WHERE institution_id = ?
               AND due_date <= ?
               AND status IN ('pending', 'reminded')
               ORDER BY due_date ASC""",
            (institution_id, future_date)
        ).fetchall()

        reminders = []
        for row in rows:
            event = dict(row)
            due = datetime.strptime(event["due_date"], "%Y-%m-%d")
            days_until = (due - today).days

            # Determine priority based on days until due
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

            reminder = Reminder(
                event_id=event["id"],
                event_title=event["title"],
                due_date=event["due_date"],
                days_until=days_until,
                priority=priority,
                message=message,
            )
            reminders.append(reminder)

            # Update event status to reminded if within reminder window
            if days_until <= event.get("reminder_days", 30) and event["status"] == "pending":
                conn.execute(
                    "UPDATE compliance_calendar SET status = 'reminded', updated_at = ? WHERE id = ?",
                    (now_iso(), event["id"])
                )

        conn.commit()

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        reminders.sort(key=lambda r: (priority_order.get(r.priority, 4), r.days_until))

        self._reminders = reminders

        return {
            "reminders": [r.to_dict() for r in reminders],
            "count": len(reminders),
            "critical_count": sum(1 for r in reminders if r.priority == "critical"),
            "high_count": sum(1 for r in reminders if r.priority == "high"),
        }

    def _tool_sync_action_plans(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sync action plan deadlines to calendar."""
        institution_id = params.get("institution_id", "")

        if not institution_id:
            return {"error": "institution_id is required"}

        conn = get_conn()
        now = now_iso()

        # Get action plan items with deadlines
        try:
            action_items = conn.execute(
                """SELECT * FROM action_plan_items
                   WHERE institution_id = ?
                   AND deadline IS NOT NULL
                   AND status != 'completed'""",
                (institution_id,)
            ).fetchall()
        except Exception:
            # Table may not exist
            return {"synced": 0, "message": "No action plan items found"}

        synced = 0
        for item in action_items:
            item_data = dict(item)

            # Check if calendar event already exists
            existing = conn.execute(
                """SELECT id FROM compliance_calendar
                   WHERE institution_id = ?
                   AND related_entity_type = 'action_plan'
                   AND related_entity_id = ?""",
                (institution_id, item_data["id"])
            ).fetchone()

            if existing:
                # Update existing event
                conn.execute(
                    """UPDATE compliance_calendar
                       SET title = ?, due_date = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        f"Action Item: {item_data.get('title', 'Untitled')}",
                        item_data["deadline"],
                        now,
                        existing["id"],
                    )
                )
            else:
                # Create new event
                event_id = generate_id("evt")
                conn.execute(
                    """INSERT INTO compliance_calendar
                       (id, institution_id, event_type, title, description, due_date,
                        reminder_days, related_entity_type, related_entity_id,
                        status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event_id,
                        institution_id,
                        "deadline",
                        f"Action Item: {item_data.get('title', 'Untitled')}",
                        item_data.get("description", ""),
                        item_data["deadline"],
                        7,  # 1 week reminder
                        "action_plan",
                        item_data["id"],
                        "pending",
                        now,
                        now,
                    )
                )
                synced += 1

        conn.commit()

        return {
            "success": True,
            "synced": synced,
            "total_items": len(action_items) if action_items else 0,
        }

    def _tool_export_calendar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export calendar events."""
        institution_id = params.get("institution_id", "")
        export_format = params.get("format", "json")
        days_ahead = params.get("days_ahead", 365)

        if not institution_id:
            return {"error": "institution_id is required"}

        # Get events
        result = self._tool_get_events({
            "institution_id": institution_id,
            "days_ahead": days_ahead,
            "include_completed": False,
        })

        events = result.get("events", [])

        if export_format == "ical":
            # Generate iCal format
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//AccreditAI//Compliance Calendar//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
            ]

            for event in events:
                due_date = event.get("due_date", "").replace("-", "")
                ical_lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{event['id']}@accreditai",
                    f"DTSTART;VALUE=DATE:{due_date}",
                    f"DTEND;VALUE=DATE:{due_date}",
                    f"SUMMARY:{event.get('title', '')}",
                    f"DESCRIPTION:{event.get('description', '')}",
                    f"STATUS:{'COMPLETED' if event.get('status') == 'completed' else 'CONFIRMED'}",
                    "END:VEVENT",
                ])

            ical_lines.append("END:VCALENDAR")
            ical_content = "\r\n".join(ical_lines)

            # Save to workspace
            if self.workspace_manager:
                filename = f"compliance_calendar_{now_iso()[:10]}.ics"
                path = f"calendar/{filename}"
                self.workspace_manager.save_file(
                    institution_id,
                    path,
                    ical_content
                )

                return {
                    "success": True,
                    "format": "ical",
                    "path": path,
                    "events_count": len(events),
                }

            return {
                "success": True,
                "format": "ical",
                "content": ical_content,
                "events_count": len(events),
            }

        else:
            # JSON format
            export_data = {
                "institution_id": institution_id,
                "exported_at": now_iso(),
                "events": events,
            }

            if self.workspace_manager:
                filename = f"compliance_calendar_{now_iso()[:10]}.json"
                path = f"calendar/{filename}"
                self.workspace_manager.save_file(
                    institution_id,
                    path,
                    export_data
                )

                return {
                    "success": True,
                    "format": "json",
                    "path": path,
                    "events_count": len(events),
                }

            return export_data

    def _tool_mark_complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark an event as completed."""
        event_id = params.get("event_id", "")

        if not event_id:
            return {"error": "event_id is required"}

        conn = get_conn()
        now = now_iso()

        # Check event exists
        event = conn.execute(
            "SELECT * FROM compliance_calendar WHERE id = ?",
            (event_id,)
        ).fetchone()

        if not event:
            return {"error": f"Event {event_id} not found"}

        # Update status
        conn.execute(
            """UPDATE compliance_calendar
               SET status = 'completed', completed_at = ?, updated_at = ?
               WHERE id = ?""",
            (now, now, event_id)
        )

        # Handle recurrence
        event_data = dict(event)
        if event_data.get("recurrence") and event_data["recurrence"] != "none":
            # Create next occurrence
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
                new_event_id = generate_id("evt")
                conn.execute(
                    """INSERT INTO compliance_calendar
                       (id, institution_id, event_type, title, description, due_date,
                        reminder_days, recurrence, accreditor_code, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_event_id,
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

        return {
            "success": True,
            "event_id": event_id,
            "status": "completed",
            "next_occurrence_created": event_data.get("recurrence", "none") != "none",
        }

    def _tool_get_overdue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get all overdue events."""
        institution_id = params.get("institution_id", "")

        if not institution_id:
            return {"error": "institution_id is required"}

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

        return {
            "overdue_events": events,
            "count": len(events),
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run calendar workflow actions."""
        if action == "daily_check":
            # Run daily check - get reminders and overdue items
            institution_id = inputs.get("institution_id")
            if not institution_id:
                return AgentResult.error("institution_id required")

            reminders = self._tool_generate_reminders({
                "institution_id": institution_id,
                "days_ahead": 30,
            })

            overdue = self._tool_get_overdue({
                "institution_id": institution_id,
            })

            return AgentResult.success(
                data={
                    "reminders": reminders,
                    "overdue": overdue,
                },
                confidence=1.0
            )

        return AgentResult.error(f"Unknown workflow: {action}")
