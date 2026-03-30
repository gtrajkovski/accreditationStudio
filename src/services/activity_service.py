"""
Activity logging service for user actions across the platform.
"""

import json
import csv
from io import StringIO
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from src.db.connection import get_conn
from src.core.models import generate_id, now_iso


def log_activity(
    user_id: Optional[str],
    institution_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_name: Optional[str] = None
) -> str:
    """
    Log a user activity.

    Args:
        user_id: User performing the action
        institution_id: Institution context
        action: Action type (e.g., 'document.upload', 'audit.start')
        entity_type: Type of entity affected (e.g., 'document', 'audit')
        entity_id: ID of entity affected
        details: Additional details (JSON string or plain text)
        ip_address: IP address of user
        user_name: Display name of user

    Returns:
        Activity log ID
    """
    conn = get_conn()
    activity_id = generate_id("activity")

    conn.execute("""
        INSERT INTO activity_log (
            id, user_id, user_name, institution_id, action,
            entity_type, entity_id, details, ip_address, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        activity_id, user_id, user_name, institution_id, action,
        entity_type, entity_id, details, ip_address, now_iso()
    ))
    conn.commit()

    return activity_id


def get_activity(
    institution_id: str,
    filters: Optional[Dict[str, Any]] = None,
    page: int = 1,
    per_page: int = 50
) -> Dict[str, Any]:
    """
    Get paginated activity log with optional filters.

    Args:
        institution_id: Institution to filter by
        filters: Optional filters (user_id, action, start_date, end_date)
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Dictionary with items, total, page, per_page, pages
    """
    conn = get_conn()
    filters = filters or {}

    # Build WHERE clause
    where_clauses = ["institution_id = ?"]
    params = [institution_id]

    if filters.get("user_id"):
        where_clauses.append("user_id = ?")
        params.append(filters["user_id"])

    if filters.get("action"):
        where_clauses.append("action = ?")
        params.append(filters["action"])

    if filters.get("start_date"):
        where_clauses.append("created_at >= ?")
        params.append(filters["start_date"])

    if filters.get("end_date"):
        where_clauses.append("created_at <= ?")
        params.append(filters["end_date"])

    where_sql = " AND ".join(where_clauses)

    # Get total count
    count_sql = f"SELECT COUNT(*) as count FROM activity_log WHERE {where_sql}"
    row = conn.execute(count_sql, params).fetchone()
    total = row["count"]

    # Get paginated results
    offset = (page - 1) * per_page
    data_sql = f"""
        SELECT * FROM activity_log
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """

    rows = conn.execute(data_sql, params + [per_page, offset]).fetchall()
    items = [dict(row) for row in rows]

    pages = (total + per_page - 1) // per_page if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages
    }


def get_activity_for_entity(entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
    """
    Get all activity for a specific entity.

    Args:
        entity_type: Type of entity (e.g., 'document', 'audit')
        entity_id: ID of entity

    Returns:
        List of activity records
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM activity_log
        WHERE entity_type = ? AND entity_id = ?
        ORDER BY created_at DESC
    """, (entity_type, entity_id)).fetchall()

    return [dict(row) for row in rows]


def get_activity_summary(institution_id: str, days: int = 30) -> Dict[str, int]:
    """
    Get activity summary for the last N days.

    Args:
        institution_id: Institution to summarize
        days: Number of days to look back

    Returns:
        Dictionary mapping action types to counts
    """
    conn = get_conn()

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    rows = conn.execute("""
        SELECT action, COUNT(*) as count
        FROM activity_log
        WHERE institution_id = ? AND created_at >= ?
        GROUP BY action
        ORDER BY count DESC
    """, (institution_id, cutoff)).fetchall()

    return {row["action"]: row["count"] for row in rows}


def export_activity(
    institution_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    Export activity log as CSV.

    Args:
        institution_id: Institution to export
        start_date: Optional start date (ISO format)
        end_date: Optional end date (ISO format)

    Returns:
        CSV string
    """
    conn = get_conn()

    where_clauses = ["institution_id = ?"]
    params = [institution_id]

    if start_date:
        where_clauses.append("created_at >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("created_at <= ?")
        params.append(end_date)

    where_sql = " AND ".join(where_clauses)

    rows = conn.execute(f"""
        SELECT
            created_at, user_name, user_id, action,
            entity_type, entity_id, details, ip_address
        FROM activity_log
        WHERE {where_sql}
        ORDER BY created_at DESC
    """, params).fetchall()

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Timestamp", "User Name", "User ID", "Action",
        "Entity Type", "Entity ID", "Details", "IP Address"
    ])

    # Write data
    for row in rows:
        writer.writerow([
            row["created_at"],
            row["user_name"] or "",
            row["user_id"] or "",
            row["action"],
            row["entity_type"] or "",
            row["entity_id"] or "",
            row["details"] or "",
            row["ip_address"] or ""
        ])

    return output.getvalue()


def get_all_users_for_institution(institution_id: str) -> List[Dict[str, Any]]:
    """
    Get all unique users who have logged activity for an institution.

    Args:
        institution_id: Institution ID

    Returns:
        List of user records with id and name
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT user_id, user_name
        FROM activity_log
        WHERE institution_id = ? AND user_id IS NOT NULL
        ORDER BY user_name
    """, (institution_id,)).fetchall()

    return [{"id": row["user_id"], "name": row["user_name"]} for row in rows]


def get_all_actions() -> List[str]:
    """
    Get all unique action types in the system.

    Returns:
        List of action type strings
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT action
        FROM activity_log
        ORDER BY action
    """).fetchall()

    return [row["action"] for row in rows]
