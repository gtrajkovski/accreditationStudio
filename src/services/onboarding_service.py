"""Onboarding wizard service for AccreditAI.

Manages the 4-step onboarding flow for new institutions:
1. Profile - institution name, accreditor, state, programs
2. Upload - key documents (catalog, enrollment agreement, handbook)
3. Audit - run initial compliance audit
4. Review - view results and next actions
"""

import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

from src.db.connection import get_conn


def generate_id(prefix: str = "onb") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


def now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def start_onboarding(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Start onboarding for a new institution.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        Progress record dict
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Check if already exists
        row = conn.execute(
            "SELECT * FROM onboarding_progress WHERE institution_id = ?",
            (institution_id,)
        ).fetchone()

        if row:
            return dict(row)

        # Create new progress record
        progress_id = generate_id("onb")
        conn.execute("""
            INSERT INTO onboarding_progress (
                id, institution_id, current_step, completed,
                profile_complete, documents_uploaded, initial_audit_run, review_complete
            ) VALUES (?, ?, 1, 0, 0, 0, 0, 0)
        """, (progress_id, institution_id))
        conn.commit()

        return {
            "id": progress_id,
            "institution_id": institution_id,
            "current_step": 1,
            "completed": False,
            "profile_complete": False,
            "documents_uploaded": False,
            "initial_audit_run": False,
            "review_complete": False,
        }
    finally:
        if should_close:
            conn.close()


def update_step(
    institution_id: str,
    step: int,
    data: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Update progress to specified step.

    Args:
        institution_id: Institution ID
        step: Step number (1-4)
        data: Optional step data (not stored, for future use)
        conn: Optional database connection

    Returns:
        Updated progress record
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Map step number to completion flag
        step_flags = {
            1: "profile_complete",
            2: "documents_uploaded",
            3: "initial_audit_run",
            4: "review_complete",
        }

        if step not in step_flags:
            raise ValueError(f"Invalid step: {step}. Must be 1-4.")

        # Get current progress
        row = conn.execute(
            "SELECT * FROM onboarding_progress WHERE institution_id = ?",
            (institution_id,)
        ).fetchone()

        if not row:
            # Start onboarding if not started
            start_onboarding(institution_id, conn)

        # Mark current step complete and advance
        flag_column = step_flags[step]
        next_step = min(step + 1, 4)
        completed = 1 if step == 4 else 0

        conn.execute(f"""
            UPDATE onboarding_progress
            SET {flag_column} = 1,
                current_step = ?,
                completed = ?,
                updated_at = datetime('now')
            WHERE institution_id = ?
        """, (next_step, completed, institution_id))
        conn.commit()

        return get_progress(institution_id, conn)
    finally:
        if should_close:
            conn.close()


def get_progress(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Get onboarding progress for institution.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        Progress dict or None if not started
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        row = conn.execute(
            "SELECT * FROM onboarding_progress WHERE institution_id = ?",
            (institution_id,)
        ).fetchone()

        if not row:
            return None

        return {
            "id": row["id"],
            "institution_id": row["institution_id"],
            "current_step": row["current_step"],
            "completed": bool(row["completed"]),
            "profile_complete": bool(row["profile_complete"]),
            "documents_uploaded": bool(row["documents_uploaded"]),
            "initial_audit_run": bool(row["initial_audit_run"]),
            "review_complete": bool(row["review_complete"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        if should_close:
            conn.close()


def is_onboarding_complete(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> bool:
    """Check if onboarding is complete.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        True if completed, False otherwise
    """
    progress = get_progress(institution_id, conn)
    if not progress:
        return False
    return progress["completed"]


def should_show_onboarding(
    user_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> bool:
    """Check if user should see onboarding wizard.

    Users should see onboarding if:
    - They have an institution assigned
    - That institution has not completed onboarding

    Args:
        user_id: User ID
        conn: Optional database connection

    Returns:
        True if should show onboarding
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Get user's institution
        user_row = conn.execute(
            "SELECT institution_id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user_row or not user_row["institution_id"]:
            # No institution - might show onboarding to create one
            # For now, return False (they need to create institution first)
            return False

        institution_id = user_row["institution_id"]

        # Check if onboarding complete
        return not is_onboarding_complete(institution_id, conn)
    finally:
        if should_close:
            conn.close()


def skip_onboarding(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Skip remaining onboarding steps and mark complete.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        Updated progress record
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Ensure progress record exists
        progress = get_progress(institution_id, conn)
        if not progress:
            start_onboarding(institution_id, conn)

        # Mark all steps complete
        conn.execute("""
            UPDATE onboarding_progress
            SET current_step = 4,
                completed = 1,
                updated_at = datetime('now')
            WHERE institution_id = ?
        """, (institution_id,))
        conn.commit()

        return get_progress(institution_id, conn)
    finally:
        if should_close:
            conn.close()
