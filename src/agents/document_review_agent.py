"""Document Review Scheduler Agent.

Manages periodic document reviews to ensure policies and procedures stay current:
- Schedule reviews for documents based on type and importance
- Track review status and history
- Identify overdue reviews
- Generate review reports and reminders
- Recommend review priorities based on compliance impact
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, AgentResult, now_iso, generate_id
from src.db.connection import get_conn
from src.config import Config


# Default review cycles by document type (in days)
DEFAULT_REVIEW_CYCLES = {
    "policy": 365,           # Annual
    "procedure": 365,        # Annual
    "catalog": 365,          # Annual (before each academic year)
    "enrollment_agreement": 365,  # Annual
    "refund_policy": 365,    # Annual
    "syllabus": 182,         # Semi-annual
    "faculty_handbook": 365, # Annual
    "student_handbook": 365, # Annual
    "safety_plan": 365,      # Annual
    "compliance_report": 182, # Semi-annual
    "financial_statement": 365,  # Annual
    "accreditation_doc": 365,    # Annual
    "other": 365,            # Default annual
}


@dataclass
class DocumentReview:
    """A scheduled document review."""
    id: str = field(default_factory=lambda: generate_id("rev"))
    institution_id: str = ""
    document_id: str = ""
    document_type: str = ""
    document_title: str = ""
    review_cycle: str = "annual"  # annual, semi-annual, quarterly, monthly
    review_cycle_days: int = 365
    last_reviewed_at: str = ""
    next_review_date: str = ""
    reviewer_id: str = ""
    reviewer_notes: str = ""
    status: str = "scheduled"  # scheduled, due, overdue, completed, skipped
    priority: str = "normal"  # low, normal, high, critical
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "document_title": self.document_title,
            "review_cycle": self.review_cycle,
            "review_cycle_days": self.review_cycle_days,
            "last_reviewed_at": self.last_reviewed_at,
            "next_review_date": self.next_review_date,
            "reviewer_id": self.reviewer_id,
            "reviewer_notes": self.reviewer_notes,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentReview":
        known_fields = {
            "id", "institution_id", "document_id", "document_type",
            "document_title", "review_cycle", "review_cycle_days",
            "last_reviewed_at", "next_review_date", "reviewer_id",
            "reviewer_notes", "status", "priority", "created_at", "updated_at"
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class ReviewReport:
    """Summary report of document review status."""
    institution_id: str = ""
    generated_at: str = field(default_factory=now_iso)
    total_documents: int = 0
    reviews_scheduled: int = 0
    reviews_due: int = 0
    reviews_overdue: int = 0
    reviews_completed_this_period: int = 0
    by_document_type: Dict[str, Dict[str, int]] = field(default_factory=dict)
    overdue_documents: List[Dict[str, Any]] = field(default_factory=list)
    upcoming_reviews: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution_id": self.institution_id,
            "generated_at": self.generated_at,
            "total_documents": self.total_documents,
            "reviews_scheduled": self.reviews_scheduled,
            "reviews_due": self.reviews_due,
            "reviews_overdue": self.reviews_overdue,
            "reviews_completed_this_period": self.reviews_completed_this_period,
            "by_document_type": self.by_document_type,
            "overdue_documents": self.overdue_documents,
            "upcoming_reviews": self.upcoming_reviews,
        }


@register_agent(AgentType.DOCUMENT_REVIEW)
class DocumentReviewAgent(BaseAgent):
    """Agent for scheduling and tracking document reviews."""

    def __init__(self, session: AgentSession, workspace_manager=None, on_update=None):
        super().__init__(session, workspace_manager, on_update)

    @property
    def agent_type(self) -> AgentType:
        return AgentType.DOCUMENT_REVIEW

    @property
    def system_prompt(self) -> str:
        return """You are an expert document review coordinator for accreditation compliance.
Your role is to ensure all institutional documents are reviewed regularly to maintain
accuracy and compliance.

EXPERTISE:
- Document lifecycle management
- Compliance review scheduling
- Accreditation documentation requirements
- Policy and procedure maintenance

REVIEW PRIORITIES:
- Critical: Documents directly affecting student outcomes or safety
- High: Core compliance documents (catalogs, policies, agreements)
- Normal: Standard operational documents
- Low: Supporting documentation

REVIEW CYCLES:
- Annual: Most policies, handbooks, catalogs
- Semi-annual: Syllabi, compliance reports
- Quarterly: Financial documents, enrollment data
- Monthly: Safety checklists, attendance records

Always recommend reviews before accreditation visits or regulatory deadlines."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "schedule_review",
                "description": "Schedule a review for a document.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "document_id": {"type": "string", "description": "Document ID"},
                        "document_title": {"type": "string", "description": "Document title"},
                        "document_type": {"type": "string", "description": "Document type"},
                        "review_cycle": {
                            "type": "string",
                            "enum": ["annual", "semi-annual", "quarterly", "monthly"],
                            "description": "Review frequency"
                        },
                        "next_review_date": {"type": "string", "description": "Next review date (YYYY-MM-DD)"},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "critical"],
                            "description": "Review priority"
                        },
                    },
                    "required": ["institution_id", "document_id", "document_title"],
                },
            },
            {
                "name": "list_pending_reviews",
                "description": "List documents due for review.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "days_ahead": {"type": "integer", "description": "Days to look ahead (default 30)"},
                        "include_overdue": {"type": "boolean", "description": "Include overdue reviews"},
                        "document_type": {"type": "string", "description": "Filter by document type"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "mark_reviewed",
                "description": "Mark a document as reviewed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "review_id": {"type": "string", "description": "Review schedule ID"},
                        "reviewer_id": {"type": "string", "description": "ID of reviewer"},
                        "reviewer_notes": {"type": "string", "description": "Review notes"},
                        "changes_made": {"type": "boolean", "description": "Were changes made to document"},
                        "next_review_date": {"type": "string", "description": "Override next review date"},
                    },
                    "required": ["review_id"],
                },
            },
            {
                "name": "set_review_cycle",
                "description": "Set or update the review cycle for a document.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "review_id": {"type": "string", "description": "Review schedule ID"},
                        "review_cycle": {
                            "type": "string",
                            "enum": ["annual", "semi-annual", "quarterly", "monthly"],
                            "description": "New review cycle"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "critical"],
                            "description": "New priority"
                        },
                    },
                    "required": ["review_id", "review_cycle"],
                },
            },
            {
                "name": "generate_review_report",
                "description": "Generate a summary report of document review status.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "period_days": {"type": "integer", "description": "Period to report on (default 90)"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "bulk_schedule",
                "description": "Schedule reviews for multiple documents based on type defaults.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "document_type": {"type": "string", "description": "Document type to schedule"},
                    },
                    "required": ["institution_id"],
                },
            },
            {
                "name": "get_review_history",
                "description": "Get review history for a document.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string", "description": "Document ID"},
                        "limit": {"type": "integer", "description": "Max records to return"},
                    },
                    "required": ["document_id"],
                },
            },
            {
                "name": "recommend_priorities",
                "description": "AI-recommended review priorities based on compliance impact.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string", "description": "Institution ID"},
                        "accreditor_code": {"type": "string", "description": "Accreditor code for context"},
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "schedule_review": self._tool_schedule_review,
            "list_pending_reviews": self._tool_list_pending,
            "mark_reviewed": self._tool_mark_reviewed,
            "set_review_cycle": self._tool_set_cycle,
            "generate_review_report": self._tool_generate_report,
            "bulk_schedule": self._tool_bulk_schedule,
            "get_review_history": self._tool_get_history,
            "recommend_priorities": self._tool_recommend_priorities,
        }
        handler = handlers.get(tool_name)
        return handler(tool_input) if handler else {"error": f"Unknown tool: {tool_name}"}

    def _cycle_to_days(self, cycle: str) -> int:
        """Convert review cycle name to days."""
        cycles = {
            "annual": 365,
            "semi-annual": 182,
            "quarterly": 91,
            "monthly": 30,
        }
        return cycles.get(cycle, 365)

    def _tool_schedule_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a document review."""
        institution_id = params.get("institution_id", "")
        document_id = params.get("document_id", "")
        document_title = params.get("document_title", "")
        document_type = params.get("document_type", "other")
        review_cycle = params.get("review_cycle", "annual")
        next_review_date = params.get("next_review_date")
        priority = params.get("priority", "normal")

        if not institution_id or not document_id:
            return {"error": "institution_id and document_id are required"}

        # Calculate next review date if not provided
        cycle_days = self._cycle_to_days(review_cycle)
        if not next_review_date:
            next_date = datetime.now() + timedelta(days=cycle_days)
            next_review_date = next_date.strftime("%Y-%m-%d")

        # Check if review already scheduled
        conn = get_conn()
        existing = conn.execute(
            "SELECT id FROM document_reviews WHERE institution_id = ? AND document_id = ?",
            (institution_id, document_id)
        ).fetchone()

        review_id = existing["id"] if existing else generate_id("rev")
        now = now_iso()

        if existing:
            # Update existing
            conn.execute(
                """UPDATE document_reviews
                   SET document_type = ?, review_cycle = ?, next_review_date = ?,
                       status = 'scheduled', updated_at = ?
                   WHERE id = ?""",
                (document_type, review_cycle, next_review_date, now, review_id)
            )
        else:
            # Create new
            conn.execute(
                """INSERT INTO document_reviews
                   (id, institution_id, document_id, document_type, review_cycle,
                    next_review_date, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review_id,
                    institution_id,
                    document_id,
                    document_type,
                    review_cycle,
                    next_review_date,
                    "scheduled",
                    now,
                    now,
                )
            )

        conn.commit()

        return {
            "success": True,
            "review_id": review_id,
            "document_id": document_id,
            "document_title": document_title,
            "next_review_date": next_review_date,
            "review_cycle": review_cycle,
            "updated": bool(existing),
        }

    def _tool_list_pending(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List pending document reviews."""
        institution_id = params.get("institution_id", "")
        days_ahead = params.get("days_ahead", 30)
        include_overdue = params.get("include_overdue", True)
        document_type = params.get("document_type")

        if not institution_id:
            return {"error": "institution_id is required"}

        conn = get_conn()
        today = datetime.now().strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Build query
        if include_overdue:
            query = """
                SELECT * FROM document_reviews
                WHERE institution_id = ?
                AND next_review_date <= ?
                AND status != 'completed'
            """
            query_params = [institution_id, future_date]
        else:
            query = """
                SELECT * FROM document_reviews
                WHERE institution_id = ?
                AND next_review_date >= ?
                AND next_review_date <= ?
                AND status != 'completed'
            """
            query_params = [institution_id, today, future_date]

        if document_type:
            query += " AND document_type = ?"
            query_params.append(document_type)

        query += " ORDER BY next_review_date ASC"

        rows = conn.execute(query, query_params).fetchall()

        reviews = []
        overdue_count = 0
        due_count = 0

        for row in rows:
            review = dict(row)
            next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
            review["days_until"] = (next_date - datetime.now()).days

            # Update status
            if review["days_until"] < 0:
                review["status"] = "overdue"
                overdue_count += 1
                # Update in DB
                conn.execute(
                    "UPDATE document_reviews SET status = 'overdue', updated_at = ? WHERE id = ?",
                    (now_iso(), review["id"])
                )
            elif review["days_until"] <= 7:
                review["status"] = "due"
                due_count += 1
                conn.execute(
                    "UPDATE document_reviews SET status = 'due', updated_at = ? WHERE id = ?",
                    (now_iso(), review["id"])
                )

            reviews.append(review)

        conn.commit()

        # Sort by priority then date
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        reviews.sort(key=lambda r: (
            priority_order.get(r.get("priority", "normal"), 2),
            r["days_until"]
        ))

        return {
            "reviews": reviews,
            "count": len(reviews),
            "overdue_count": overdue_count,
            "due_this_week": due_count,
        }

    def _tool_mark_reviewed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mark a document as reviewed."""
        review_id = params.get("review_id", "")
        reviewer_id = params.get("reviewer_id", "")
        reviewer_notes = params.get("reviewer_notes", "")
        changes_made = params.get("changes_made", False)
        next_review_override = params.get("next_review_date")

        if not review_id:
            return {"error": "review_id is required"}

        conn = get_conn()
        now = now_iso()

        # Get current review
        review = conn.execute(
            "SELECT * FROM document_reviews WHERE id = ?",
            (review_id,)
        ).fetchone()

        if not review:
            return {"error": f"Review {review_id} not found"}

        review_data = dict(review)

        # Calculate next review date
        if next_review_override:
            next_date = next_review_override
        else:
            cycle_days = self._cycle_to_days(review_data.get("review_cycle", "annual"))
            next_date = (datetime.now() + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

        # Update review
        conn.execute(
            """UPDATE document_reviews
               SET status = 'completed', last_reviewed_at = ?, next_review_date = ?,
                   reviewer_id = ?, reviewer_notes = ?, updated_at = ?
               WHERE id = ?""",
            (
                now[:10],  # Just date part
                next_date,
                reviewer_id,
                reviewer_notes,
                now,
                review_id,
            )
        )

        # Create a new scheduled review for the next cycle
        new_review_id = generate_id("rev")
        conn.execute(
            """INSERT INTO document_reviews
               (id, institution_id, document_id, document_type, review_cycle,
                last_reviewed_at, next_review_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_review_id,
                review_data["institution_id"],
                review_data["document_id"],
                review_data.get("document_type", "other"),
                review_data.get("review_cycle", "annual"),
                now[:10],
                next_date,
                "scheduled",
                now,
                now,
            )
        )

        conn.commit()

        return {
            "success": True,
            "review_id": review_id,
            "status": "completed",
            "reviewed_at": now[:10],
            "next_review_date": next_date,
            "next_review_id": new_review_id,
            "changes_made": changes_made,
        }

    def _tool_set_cycle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set or update review cycle."""
        review_id = params.get("review_id", "")
        review_cycle = params.get("review_cycle", "annual")
        priority = params.get("priority")

        if not review_id:
            return {"error": "review_id is required"}

        conn = get_conn()

        # Check exists
        existing = conn.execute(
            "SELECT * FROM document_reviews WHERE id = ?",
            (review_id,)
        ).fetchone()

        if not existing:
            return {"error": f"Review {review_id} not found"}

        # Calculate new next review date
        existing_data = dict(existing)
        last_reviewed = existing_data.get("last_reviewed_at")

        if last_reviewed:
            base_date = datetime.strptime(last_reviewed, "%Y-%m-%d")
        else:
            base_date = datetime.now()

        cycle_days = self._cycle_to_days(review_cycle)
        next_date = (base_date + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

        # Update
        updates = ["review_cycle = ?", "next_review_date = ?", "updated_at = ?"]
        update_params = [review_cycle, next_date, now_iso()]

        if priority:
            updates.append("priority = ?")
            update_params.append(priority)

        update_params.append(review_id)

        conn.execute(
            f"UPDATE document_reviews SET {', '.join(updates)} WHERE id = ?",
            update_params
        )
        conn.commit()

        return {
            "success": True,
            "review_id": review_id,
            "review_cycle": review_cycle,
            "next_review_date": next_date,
            "priority": priority or existing_data.get("priority", "normal"),
        }

    def _tool_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate review status report."""
        institution_id = params.get("institution_id", "")
        period_days = params.get("period_days", 90)

        if not institution_id:
            return {"error": "institution_id is required"}

        conn = get_conn()
        today = datetime.now().strftime("%Y-%m-%d")
        period_start = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        upcoming_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        # Get all reviews
        all_reviews = conn.execute(
            "SELECT * FROM document_reviews WHERE institution_id = ?",
            (institution_id,)
        ).fetchall()

        # Calculate stats
        total = len(all_reviews)
        scheduled = 0
        due = 0
        overdue = 0
        completed_this_period = 0
        by_type: Dict[str, Dict[str, int]] = {}
        overdue_docs = []
        upcoming = []

        for row in all_reviews:
            review = dict(row)
            doc_type = review.get("document_type", "other")
            status = review.get("status", "scheduled")

            # Init type stats
            if doc_type not in by_type:
                by_type[doc_type] = {"total": 0, "due": 0, "overdue": 0, "completed": 0}

            by_type[doc_type]["total"] += 1

            # Check status
            if review.get("next_review_date"):
                next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
                days_until = (next_date - datetime.now()).days

                if days_until < 0 and status != "completed":
                    overdue += 1
                    by_type[doc_type]["overdue"] += 1
                    overdue_docs.append({
                        "document_id": review["document_id"],
                        "document_type": doc_type,
                        "next_review_date": review["next_review_date"],
                        "days_overdue": abs(days_until),
                    })
                elif days_until <= 30 and status != "completed":
                    due += 1
                    by_type[doc_type]["due"] += 1
                    upcoming.append({
                        "document_id": review["document_id"],
                        "document_type": doc_type,
                        "next_review_date": review["next_review_date"],
                        "days_until": days_until,
                    })

            if status == "completed":
                by_type[doc_type]["completed"] += 1
                if review.get("last_reviewed_at") and review["last_reviewed_at"] >= period_start:
                    completed_this_period += 1
            elif status == "scheduled":
                scheduled += 1

        # Sort overdue by days
        overdue_docs.sort(key=lambda x: x["days_overdue"], reverse=True)
        upcoming.sort(key=lambda x: x["days_until"])

        report = ReviewReport(
            institution_id=institution_id,
            total_documents=total,
            reviews_scheduled=scheduled,
            reviews_due=due,
            reviews_overdue=overdue,
            reviews_completed_this_period=completed_this_period,
            by_document_type=by_type,
            overdue_documents=overdue_docs[:10],  # Top 10
            upcoming_reviews=upcoming[:10],
        )

        # Save report to workspace
        if self.workspace_manager:
            path = f"reviews/report_{now_iso()[:10]}.json"
            self.workspace_manager.save_file(
                institution_id,
                path,
                report.to_dict()
            )

        return report.to_dict()

    def _tool_bulk_schedule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk schedule reviews for documents."""
        institution_id = params.get("institution_id", "")
        document_type = params.get("document_type")

        if not institution_id:
            return {"error": "institution_id is required"}

        # Get documents from workspace
        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        try:
            docs = self.workspace_manager.list_documents(institution_id)
        except Exception:
            return {"scheduled": 0, "message": "Could not list documents"}

        conn = get_conn()
        now = now_iso()
        scheduled = 0

        for doc in docs:
            doc_type = doc.get("doc_type", "other")

            # Filter by type if specified
            if document_type and doc_type != document_type:
                continue

            # Check if already scheduled
            existing = conn.execute(
                "SELECT id FROM document_reviews WHERE institution_id = ? AND document_id = ?",
                (institution_id, doc.get("id", ""))
            ).fetchone()

            if existing:
                continue

            # Get default cycle for this type
            cycle_days = DEFAULT_REVIEW_CYCLES.get(doc_type, 365)
            cycle_name = "annual"
            if cycle_days <= 30:
                cycle_name = "monthly"
            elif cycle_days <= 91:
                cycle_name = "quarterly"
            elif cycle_days <= 182:
                cycle_name = "semi-annual"

            next_date = (datetime.now() + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

            conn.execute(
                """INSERT INTO document_reviews
                   (id, institution_id, document_id, document_type, review_cycle,
                    next_review_date, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    generate_id("rev"),
                    institution_id,
                    doc.get("id", ""),
                    doc_type,
                    cycle_name,
                    next_date,
                    "scheduled",
                    now,
                    now,
                )
            )
            scheduled += 1

        conn.commit()

        return {
            "success": True,
            "scheduled": scheduled,
            "document_type": document_type or "all",
        }

    def _tool_get_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get review history for a document."""
        document_id = params.get("document_id", "")
        limit = params.get("limit", 10)

        if not document_id:
            return {"error": "document_id is required"}

        conn = get_conn()

        rows = conn.execute(
            """SELECT * FROM document_reviews
               WHERE document_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (document_id, limit)
        ).fetchall()

        history = [dict(row) for row in rows]

        return {
            "document_id": document_id,
            "history": history,
            "count": len(history),
        }

    def _tool_recommend_priorities(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """AI-recommended review priorities."""
        institution_id = params.get("institution_id", "")
        accreditor_code = params.get("accreditor_code", "")

        if not institution_id:
            return {"error": "institution_id is required"}

        # Define priority recommendations based on document type and accreditor
        critical_types = ["refund_policy", "enrollment_agreement", "catalog", "safety_plan"]
        high_types = ["policy", "procedure", "faculty_handbook", "student_handbook"]

        conn = get_conn()

        # Get current reviews
        rows = conn.execute(
            """SELECT * FROM document_reviews
               WHERE institution_id = ?
               AND status != 'completed'""",
            (institution_id,)
        ).fetchall()

        recommendations = []
        updates_made = 0

        for row in rows:
            review = dict(row)
            doc_type = review.get("document_type", "other")
            current_priority = review.get("priority", "normal")

            # Determine recommended priority
            if doc_type in critical_types:
                recommended = "critical"
            elif doc_type in high_types:
                recommended = "high"
            else:
                recommended = "normal"

            # Check if overdue
            if review.get("next_review_date"):
                next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
                if (next_date - datetime.now()).days < 0:
                    # Bump priority for overdue
                    if recommended == "normal":
                        recommended = "high"
                    elif recommended == "high":
                        recommended = "critical"

            if recommended != current_priority:
                recommendations.append({
                    "review_id": review["id"],
                    "document_type": doc_type,
                    "current_priority": current_priority,
                    "recommended_priority": recommended,
                    "reason": f"{doc_type} documents should be {recommended} priority"
                             + (" (overdue)" if review.get("status") == "overdue" else ""),
                })

                # Update priority
                conn.execute(
                    "UPDATE document_reviews SET priority = ?, updated_at = ? WHERE id = ?",
                    (recommended, now_iso(), review["id"])
                )
                updates_made += 1

        conn.commit()

        return {
            "recommendations": recommendations,
            "updates_made": updates_made,
            "total_reviewed": len(rows),
        }

    def run_workflow(self, action: str, inputs: Dict[str, Any]) -> AgentResult:
        """Run document review workflow actions."""
        if action == "daily_check":
            institution_id = inputs.get("institution_id")
            if not institution_id:
                return AgentResult.error("institution_id required")

            pending = self._tool_list_pending({
                "institution_id": institution_id,
                "days_ahead": 7,
                "include_overdue": True,
            })

            return AgentResult.success(data=pending, confidence=1.0)

        elif action == "setup_reviews":
            institution_id = inputs.get("institution_id")
            if not institution_id:
                return AgentResult.error("institution_id required")

            # Bulk schedule and set priorities
            scheduled = self._tool_bulk_schedule({"institution_id": institution_id})
            priorities = self._tool_recommend_priorities({"institution_id": institution_id})

            return AgentResult.success(
                data={
                    "scheduled": scheduled,
                    "priorities": priorities,
                },
                confidence=0.9
            )

        return AgentResult.error(f"Unknown workflow: {action}")
