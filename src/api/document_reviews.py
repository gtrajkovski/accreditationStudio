"""Document Reviews API Blueprint.

Handles document review scheduling, tracking, and reporting.
"""

import json
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from src.core.models import AgentSession, generate_id, now_iso
from src.db.connection import get_conn
from src.agents.base_agent import AgentType
from src.agents.registry import AgentRegistry


document_reviews_bp = Blueprint("document_reviews", __name__, url_prefix="/api/document-reviews")

_workspace_manager = None


def init_document_reviews_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


# Default review cycles
REVIEW_CYCLES = {
    "annual": 365,
    "semi-annual": 182,
    "quarterly": 91,
    "monthly": 30,
}


# =============================================================================
# Reviews CRUD
# =============================================================================

@document_reviews_bp.route("/", methods=["GET"])
def list_reviews():
    """List document reviews."""
    institution_id = request.args.get("institution_id")
    status = request.args.get("status")
    document_type = request.args.get("document_type")
    days_ahead = request.args.get("days_ahead", 90, type=int)
    include_completed = request.args.get("include_completed", "false").lower() == "true"

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    query = """
        SELECT * FROM document_reviews
        WHERE institution_id = ?
    """
    params = [institution_id]

    if not include_completed:
        query += " AND (status != 'completed' OR next_review_date <= ?)"
        params.append(future_date)

    if status:
        query += " AND status = ?"
        params.append(status)

    if document_type:
        query += " AND document_type = ?"
        params.append(document_type)

    query += " ORDER BY next_review_date ASC"

    rows = conn.execute(query, params).fetchall()

    reviews = []
    for row in rows:
        review = dict(row)
        if review.get("next_review_date"):
            try:
                next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
                review["days_until"] = (next_date - datetime.now()).days
            except ValueError:
                review["days_until"] = None
        reviews.append(review)

    return jsonify({
        "reviews": reviews,
        "count": len(reviews),
    })


@document_reviews_bp.route("/<review_id>", methods=["GET"])
def get_review(review_id: str):
    """Get a specific review."""
    conn = get_conn()

    review = conn.execute(
        "SELECT * FROM document_reviews WHERE id = ?",
        (review_id,)
    ).fetchone()

    if not review:
        return jsonify({"error": "Review not found"}), 404

    review_data = dict(review)
    if review_data.get("next_review_date"):
        try:
            next_date = datetime.strptime(review_data["next_review_date"], "%Y-%m-%d")
            review_data["days_until"] = (next_date - datetime.now()).days
        except ValueError:
            pass

    return jsonify(review_data)


@document_reviews_bp.route("/", methods=["POST"])
def create_review():
    """Schedule a new document review."""
    data = request.get_json()

    if not data.get("institution_id"):
        return jsonify({"error": "institution_id is required"}), 400
    if not data.get("document_id"):
        return jsonify({"error": "document_id is required"}), 400

    review_cycle = data.get("review_cycle", "annual")
    cycle_days = REVIEW_CYCLES.get(review_cycle, 365)

    # Calculate next review date
    next_review_date = data.get("next_review_date")
    if not next_review_date:
        next_review_date = (datetime.now() + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

    review_id = generate_id("rev")
    now = now_iso()

    conn = get_conn()

    # Check if already exists
    existing = conn.execute(
        "SELECT id FROM document_reviews WHERE institution_id = ? AND document_id = ?",
        (data["institution_id"], data["document_id"])
    ).fetchone()

    if existing:
        return jsonify({"error": "Review already scheduled for this document", "review_id": existing["id"]}), 409

    conn.execute(
        """INSERT INTO document_reviews
           (id, institution_id, document_id, document_type, review_cycle,
            next_review_date, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            review_id,
            data.get("institution_id"),
            data.get("document_id"),
            data.get("document_type", "other"),
            review_cycle,
            next_review_date,
            "scheduled",
            now,
            now,
        )
    )
    conn.commit()

    return jsonify({
        "id": review_id,
        "status": "created",
        "next_review_date": next_review_date,
    }), 201


@document_reviews_bp.route("/<review_id>", methods=["PATCH"])
def update_review(review_id: str):
    """Update a review."""
    data = request.get_json()
    conn = get_conn()

    existing = conn.execute(
        "SELECT id FROM document_reviews WHERE id = ?",
        (review_id,)
    ).fetchone()

    if not existing:
        return jsonify({"error": "Review not found"}), 404

    updates = []
    params = []

    for field in ["document_type", "review_cycle", "next_review_date",
                  "reviewer_id", "reviewer_notes", "status"]:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if updates:
        updates.append("updated_at = ?")
        params.append(now_iso())
        params.append(review_id)

        conn.execute(
            f"UPDATE document_reviews SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    return jsonify({"id": review_id, "status": "updated"})


@document_reviews_bp.route("/<review_id>", methods=["DELETE"])
def delete_review(review_id: str):
    """Delete a review schedule."""
    conn = get_conn()

    result = conn.execute(
        "DELETE FROM document_reviews WHERE id = ?",
        (review_id,)
    )
    conn.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Review not found"}), 404

    return jsonify({"id": review_id, "status": "deleted"})


# =============================================================================
# Review Actions
# =============================================================================

@document_reviews_bp.route("/<review_id>/complete", methods=["POST"])
def complete_review(review_id: str):
    """Mark a review as completed and schedule next."""
    data = request.get_json() or {}
    conn = get_conn()
    now = now_iso()

    # Get current review
    review = conn.execute(
        "SELECT * FROM document_reviews WHERE id = ?",
        (review_id,)
    ).fetchone()

    if not review:
        return jsonify({"error": "Review not found"}), 404

    review_data = dict(review)

    # Calculate next review date
    review_cycle = review_data.get("review_cycle", "annual")
    cycle_days = REVIEW_CYCLES.get(review_cycle, 365)

    next_review_date = data.get("next_review_date")
    if not next_review_date:
        next_review_date = (datetime.now() + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

    # Update current review
    conn.execute(
        """UPDATE document_reviews
           SET status = 'completed', last_reviewed_at = ?,
               reviewer_id = ?, reviewer_notes = ?, updated_at = ?
           WHERE id = ?""",
        (
            now[:10],
            data.get("reviewer_id", ""),
            data.get("reviewer_notes", ""),
            now,
            review_id,
        )
    )

    # Create next scheduled review
    next_review_id = generate_id("rev")
    conn.execute(
        """INSERT INTO document_reviews
           (id, institution_id, document_id, document_type, review_cycle,
            last_reviewed_at, next_review_date, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            next_review_id,
            review_data["institution_id"],
            review_data["document_id"],
            review_data.get("document_type", "other"),
            review_cycle,
            now[:10],
            next_review_date,
            "scheduled",
            now,
            now,
        )
    )

    conn.commit()

    return jsonify({
        "id": review_id,
        "status": "completed",
        "completed_at": now[:10],
        "next_review_id": next_review_id,
        "next_review_date": next_review_date,
    })


@document_reviews_bp.route("/<review_id>/skip", methods=["POST"])
def skip_review(review_id: str):
    """Skip a review (reschedule without completing)."""
    data = request.get_json() or {}
    conn = get_conn()
    now = now_iso()

    review = conn.execute(
        "SELECT * FROM document_reviews WHERE id = ?",
        (review_id,)
    ).fetchone()

    if not review:
        return jsonify({"error": "Review not found"}), 404

    review_data = dict(review)

    # Calculate new date (default: push out by 30 days)
    days_to_push = data.get("days", 30)
    new_date = (datetime.now() + timedelta(days=days_to_push)).strftime("%Y-%m-%d")

    conn.execute(
        """UPDATE document_reviews
           SET next_review_date = ?, reviewer_notes = ?, updated_at = ?
           WHERE id = ?""",
        (
            new_date,
            data.get("reason", "Review skipped"),
            now,
            review_id,
        )
    )
    conn.commit()

    return jsonify({
        "id": review_id,
        "status": "rescheduled",
        "new_date": new_date,
    })


# =============================================================================
# Pending & Overdue
# =============================================================================

@document_reviews_bp.route("/pending", methods=["GET"])
def get_pending():
    """Get pending reviews (due soon or overdue)."""
    institution_id = request.args.get("institution_id")
    days_ahead = request.args.get("days_ahead", 30, type=int)

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT * FROM document_reviews
           WHERE institution_id = ?
           AND next_review_date <= ?
           AND status NOT IN ('completed', 'skipped')
           ORDER BY next_review_date ASC""",
        (institution_id, future_date)
    ).fetchall()

    reviews = []
    overdue = 0
    due_soon = 0

    for row in rows:
        review = dict(row)
        next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
        days_until = (next_date - datetime.now()).days
        review["days_until"] = days_until

        if days_until < 0:
            review["urgency"] = "overdue"
            overdue += 1
        elif days_until <= 7:
            review["urgency"] = "urgent"
            due_soon += 1
        else:
            review["urgency"] = "upcoming"

        reviews.append(review)

    return jsonify({
        "reviews": reviews,
        "count": len(reviews),
        "overdue": overdue,
        "due_soon": due_soon,
    })


@document_reviews_bp.route("/overdue", methods=["GET"])
def get_overdue():
    """Get all overdue reviews."""
    institution_id = request.args.get("institution_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT * FROM document_reviews
           WHERE institution_id = ?
           AND next_review_date < ?
           AND status NOT IN ('completed', 'skipped')
           ORDER BY next_review_date ASC""",
        (institution_id, today)
    ).fetchall()

    reviews = []
    for row in rows:
        review = dict(row)
        next_date = datetime.strptime(review["next_review_date"], "%Y-%m-%d")
        review["days_overdue"] = abs((next_date - datetime.now()).days)
        reviews.append(review)

        # Update status
        if review["status"] != "overdue":
            conn.execute(
                "UPDATE document_reviews SET status = 'overdue', updated_at = ? WHERE id = ?",
                (now_iso(), review["id"])
            )

    conn.commit()

    return jsonify({
        "reviews": reviews,
        "count": len(reviews),
    })


# =============================================================================
# Bulk Operations
# =============================================================================

@document_reviews_bp.route("/bulk-schedule", methods=["POST"])
def bulk_schedule():
    """Schedule reviews for all documents of a type."""
    data = request.get_json()
    institution_id = data.get("institution_id")
    document_type = data.get("document_type")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    session = AgentSession(
        agent_type=AgentType.DOCUMENT_REVIEW.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.DOCUMENT_REVIEW,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Document Review agent"}), 500

    result = agent._tool_bulk_schedule({
        "institution_id": institution_id,
        "document_type": document_type,
    })

    return jsonify(result)


@document_reviews_bp.route("/recommend-priorities", methods=["POST"])
def recommend_priorities():
    """Get AI-recommended review priorities."""
    data = request.get_json()
    institution_id = data.get("institution_id")
    accreditor_code = data.get("accreditor_code", "")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    session = AgentSession(
        agent_type=AgentType.DOCUMENT_REVIEW.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.DOCUMENT_REVIEW,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Document Review agent"}), 500

    result = agent._tool_recommend_priorities({
        "institution_id": institution_id,
        "accreditor_code": accreditor_code,
    })

    return jsonify(result)


# =============================================================================
# Reports & Stats
# =============================================================================

@document_reviews_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get review statistics for dashboard."""
    institution_id = request.args.get("institution_id")

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    week_ahead = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    month_ahead = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Total scheduled
    total = conn.execute(
        "SELECT COUNT(*) FROM document_reviews WHERE institution_id = ?",
        (institution_id,)
    ).fetchone()[0]

    # Overdue
    overdue = conn.execute(
        """SELECT COUNT(*) FROM document_reviews
           WHERE institution_id = ? AND next_review_date < ?
           AND status NOT IN ('completed', 'skipped')""",
        (institution_id, today)
    ).fetchone()[0]

    # Due this week
    this_week = conn.execute(
        """SELECT COUNT(*) FROM document_reviews
           WHERE institution_id = ? AND next_review_date >= ?
           AND next_review_date <= ?
           AND status NOT IN ('completed', 'skipped')""",
        (institution_id, today, week_ahead)
    ).fetchone()[0]

    # Due this month
    this_month = conn.execute(
        """SELECT COUNT(*) FROM document_reviews
           WHERE institution_id = ? AND next_review_date >= ?
           AND next_review_date <= ?
           AND status NOT IN ('completed', 'skipped')""",
        (institution_id, today, month_ahead)
    ).fetchone()[0]

    # Completed this month
    completed_recent = conn.execute(
        """SELECT COUNT(*) FROM document_reviews
           WHERE institution_id = ? AND status = 'completed'
           AND last_reviewed_at >= ?""",
        (institution_id, month_ago)
    ).fetchone()[0]

    # By document type
    by_type = conn.execute(
        """SELECT document_type, COUNT(*) as count,
                  SUM(CASE WHEN next_review_date < ? AND status NOT IN ('completed', 'skipped') THEN 1 ELSE 0 END) as overdue
           FROM document_reviews
           WHERE institution_id = ?
           GROUP BY document_type""",
        (today, institution_id)
    ).fetchall()

    return jsonify({
        "total": total,
        "overdue": overdue,
        "due_this_week": this_week,
        "due_this_month": this_month,
        "completed_this_month": completed_recent,
        "by_type": [dict(row) for row in by_type],
    })


@document_reviews_bp.route("/report", methods=["GET"])
def generate_report():
    """Generate a review status report."""
    institution_id = request.args.get("institution_id")
    period_days = request.args.get("period_days", 90, type=int)

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    session = AgentSession(
        agent_type=AgentType.DOCUMENT_REVIEW.value,
        institution_id=institution_id,
    )

    agent = AgentRegistry.create(
        AgentType.DOCUMENT_REVIEW,
        session,
        workspace_manager=_workspace_manager,
    )

    if not agent:
        return jsonify({"error": "Could not create Document Review agent"}), 500

    result = agent._tool_generate_report({
        "institution_id": institution_id,
        "period_days": period_days,
    })

    return jsonify(result)


# =============================================================================
# History
# =============================================================================

@document_reviews_bp.route("/history/<document_id>", methods=["GET"])
def get_history(document_id: str):
    """Get review history for a document."""
    limit = request.args.get("limit", 10, type=int)

    conn = get_conn()

    rows = conn.execute(
        """SELECT * FROM document_reviews
           WHERE document_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (document_id, limit)
    ).fetchall()

    return jsonify({
        "document_id": document_id,
        "history": [dict(row) for row in rows],
        "count": len(rows),
    })
