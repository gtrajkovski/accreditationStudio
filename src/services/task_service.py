"""
Task Service

Manages task lifecycle: creation, assignment, completion, commenting.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.db.connection import get_conn
from src.core.utils import generate_id, now_iso


# Task status values
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

# Priority values
PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"
PRIORITY_LOW = "low"

# Source types
SOURCE_AUDIT_FINDING = "audit_finding"
SOURCE_ACTION_PLAN = "action_plan"
SOURCE_MANUAL = "manual"
SOURCE_ONBOARDING = "onboarding"

# Categories
CATEGORY_DOCUMENTATION = "documentation"
CATEGORY_COMPLIANCE = "compliance"
CATEGORY_EVIDENCE = "evidence"
CATEGORY_FACULTY = "faculty"
CATEGORY_OUTCOMES = "outcomes"
CATEGORY_VISIT_PREP = "visit_prep"


def create_task(
    institution_id: str,
    title: str,
    description: Optional[str] = None,
    assigned_to: Optional[str] = None,
    assigned_by: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: str = PRIORITY_NORMAL,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    category: Optional[str] = None
) -> str:
    """Create a new task. Returns task ID."""
    task_id = generate_id("task")
    now = now_iso()

    conn = get_conn()
    conn.execute("""
        INSERT INTO tasks (
            id, institution_id, title, description, status, priority,
            assigned_to, assigned_by, due_date, source_type, source_id,
            category, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id, institution_id, title, description, STATUS_PENDING, priority,
        assigned_to, assigned_by, due_date, source_type, source_id,
        category, now, now
    ))
    conn.commit()

    return task_id


def update_task(task_id: str, updates: Dict[str, Any]) -> bool:
    """Update task fields. Returns True if successful."""
    if not updates:
        return False

    allowed_fields = {
        "title", "description", "status", "priority", "assigned_to",
        "assigned_by", "due_date", "category"
    }

    # Filter to allowed fields only
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    if not filtered:
        return False

    # Add updated_at timestamp
    filtered["updated_at"] = now_iso()

    # Build SET clause
    set_clause = ", ".join([f"{k} = ?" for k in filtered.keys()])
    values = list(filtered.values()) + [task_id]

    conn = get_conn()
    cursor = conn.execute(
        f"UPDATE tasks SET {set_clause} WHERE id = ?",
        values
    )
    conn.commit()

    return cursor.rowcount > 0


def complete_task(task_id: str, user_id: Optional[str] = None) -> bool:
    """Mark task as completed. Returns True if successful."""
    now = now_iso()

    conn = get_conn()
    cursor = conn.execute("""
        UPDATE tasks
        SET status = ?, completed_at = ?, updated_at = ?
        WHERE id = ?
    """, (STATUS_COMPLETED, now, now, task_id))
    conn.commit()

    return cursor.rowcount > 0


def assign_task(task_id: str, user_id: str, assigned_by: Optional[str] = None) -> bool:
    """Assign task to a user. Returns True if successful."""
    updates = {"assigned_to": user_id}
    if assigned_by:
        updates["assigned_by"] = assigned_by

    return update_task(task_id, updates)


def get_tasks(
    institution_id: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    per_page: int = 50
) -> Dict[str, Any]:
    """Get tasks with optional filters. Returns paginated results."""
    filters = filters or {}

    # Build WHERE clause
    conditions = ["institution_id = ?"]
    params = [institution_id]

    if filters.get("status"):
        conditions.append("status = ?")
        params.append(filters["status"])

    if filters.get("priority"):
        conditions.append("priority = ?")
        params.append(filters["priority"])

    if filters.get("assigned_to"):
        conditions.append("assigned_to = ?")
        params.append(filters["assigned_to"])

    if filters.get("category"):
        conditions.append("category = ?")
        params.append(filters["category"])

    if filters.get("overdue"):
        conditions.append("due_date < ? AND status != ?")
        params.extend([now_iso(), STATUS_COMPLETED])

    if filters.get("source_type"):
        conditions.append("source_type = ?")
        params.append(filters["source_type"])

    where_clause = " AND ".join(conditions)

    # Get total count
    conn = get_conn()
    count_row = conn.execute(
        f"SELECT COUNT(*) as total FROM tasks WHERE {where_clause}",
        params
    ).fetchone()
    total = count_row["total"] if count_row else 0

    # Get paginated results
    offset = (page - 1) * per_page
    rows = conn.execute(f"""
        SELECT * FROM tasks
        WHERE {where_clause}
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            due_date ASC,
            created_at DESC
        LIMIT ? OFFSET ?
    """, params + [per_page, offset]).fetchall()

    tasks = [dict(row) for row in rows]

    return {
        "tasks": tasks,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


def get_my_tasks(
    user_id: str,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Get tasks assigned to a specific user."""
    filters = filters or {}
    filters["assigned_to"] = user_id

    # Get all institutions for this user (simplified - would need join in real implementation)
    conn = get_conn()

    # Build WHERE clause
    conditions = ["assigned_to = ?"]
    params = [user_id]

    if filters.get("status"):
        conditions.append("status = ?")
        params.append(filters["status"])

    if filters.get("priority"):
        conditions.append("priority = ?")
        params.append(filters["priority"])

    if filters.get("category"):
        conditions.append("category = ?")
        params.append(filters["category"])

    if filters.get("overdue"):
        conditions.append("due_date < ? AND status != ?")
        params.extend([now_iso(), STATUS_COMPLETED])

    where_clause = " AND ".join(conditions)

    rows = conn.execute(f"""
        SELECT * FROM tasks
        WHERE {where_clause}
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            due_date ASC,
            created_at DESC
    """, params).fetchall()

    return [dict(row) for row in rows]


def get_overdue_tasks(institution_id: str) -> List[Dict[str, Any]]:
    """Get all overdue tasks for an institution."""
    conn = get_conn()
    now = now_iso()

    rows = conn.execute("""
        SELECT * FROM tasks
        WHERE institution_id = ?
        AND due_date < ?
        AND status != ?
        ORDER BY due_date ASC
    """, (institution_id, now, STATUS_COMPLETED)).fetchall()

    return [dict(row) for row in rows]


def get_task_stats(institution_id: str) -> Dict[str, int]:
    """Get task statistics for an institution."""
    conn = get_conn()
    now = now_iso()

    # Total tasks
    total_row = conn.execute(
        "SELECT COUNT(*) as count FROM tasks WHERE institution_id = ?",
        (institution_id,)
    ).fetchone()
    total = total_row["count"] if total_row else 0

    # Pending
    pending_row = conn.execute(
        "SELECT COUNT(*) as count FROM tasks WHERE institution_id = ? AND status = ?",
        (institution_id, STATUS_PENDING)
    ).fetchone()
    pending = pending_row["count"] if pending_row else 0

    # In progress
    in_progress_row = conn.execute(
        "SELECT COUNT(*) as count FROM tasks WHERE institution_id = ? AND status = ?",
        (institution_id, STATUS_IN_PROGRESS)
    ).fetchone()
    in_progress = in_progress_row["count"] if in_progress_row else 0

    # Completed
    completed_row = conn.execute(
        "SELECT COUNT(*) as count FROM tasks WHERE institution_id = ? AND status = ?",
        (institution_id, STATUS_COMPLETED)
    ).fetchone()
    completed = completed_row["count"] if completed_row else 0

    # Overdue
    overdue_row = conn.execute("""
        SELECT COUNT(*) as count FROM tasks
        WHERE institution_id = ?
        AND due_date < ?
        AND status != ?
    """, (institution_id, now, STATUS_COMPLETED)).fetchone()
    overdue = overdue_row["count"] if overdue_row else 0

    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "overdue": overdue
    }


def add_comment(
    task_id: str,
    user_id: Optional[str],
    user_name: str,
    content: str
) -> str:
    """Add a comment to a task. Returns comment ID."""
    comment_id = generate_id("comment")
    now = now_iso()

    conn = get_conn()
    conn.execute("""
        INSERT INTO task_comments (id, task_id, user_id, user_name, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (comment_id, task_id, user_id, user_name, content, now))
    conn.commit()

    return comment_id


def get_comments(task_id: str) -> List[Dict[str, Any]]:
    """Get all comments for a task."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM task_comments
        WHERE task_id = ?
        ORDER BY created_at ASC
    """, (task_id,)).fetchall()

    return [dict(row) for row in rows]


def create_tasks_from_findings(
    institution_id: str,
    findings: List[Dict[str, Any]],
    assigned_by: Optional[str] = None
) -> List[str]:
    """
    Bulk create tasks from audit findings.

    Findings should have: id, title, description, severity.
    Returns list of created task IDs.
    """
    task_ids = []

    # Calculate default due date (30 days from now)
    due_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    for finding in findings:
        # Map severity to priority
        severity = finding.get("severity", "minor").lower()
        if severity == "critical":
            priority = PRIORITY_CRITICAL
        elif severity == "major":
            priority = PRIORITY_HIGH
        else:
            priority = PRIORITY_NORMAL

        # Build description
        description = finding.get("description", "")
        recommendation = finding.get("recommendation", "")
        if recommendation:
            description = f"{description}\n\nRecommendation: {recommendation}"

        # Create task
        task_id = create_task(
            institution_id=institution_id,
            title=finding.get("title", "Compliance Issue"),
            description=description,
            priority=priority,
            due_date=due_date,
            source_type=SOURCE_AUDIT_FINDING,
            source_id=finding.get("id"),
            category=CATEGORY_COMPLIANCE,
            assigned_by=assigned_by
        )

        task_ids.append(task_id)

    return task_ids


def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    """Get a single task by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def delete_task(task_id: str) -> bool:
    """Delete a task (admin only). Returns True if successful."""
    conn = get_conn()
    cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return cursor.rowcount > 0
