"""
Authentication service for user management and session handling.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

from src.db.connection import get_conn
from src.core.utils import generate_id, now_iso


def register_user(
    email: str,
    password: str,
    name: str,
    institution_id: Optional[str] = None,
    role: str = "viewer"
) -> Dict[str, Any]:
    """
    Register a new user with email/password.

    Args:
        email: User email (unique)
        password: Plain text password (min 8 chars)
        name: User display name
        institution_id: Optional institution ID to associate
        role: User role (default: viewer)

    Returns:
        User dict without password_hash

    Raises:
        ValueError: If email already exists or password too short
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    conn = get_conn()

    # Check if email already exists
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if existing:
        raise ValueError("Email already registered")

    user_id = generate_id("user")
    password_hash = generate_password_hash(password)
    now = now_iso()

    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, name, role, institution_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (user_id, email, password_hash, name, role, institution_id, now, now)
    )
    conn.commit()

    return {
        "id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "institution_id": institution_id,
        "is_active": True,
        "last_login": None,
        "created_at": now,
        "updated_at": now
    }


def authenticate(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate user and create session token.

    Args:
        email: User email
        password: Plain text password

    Returns:
        Dict with user and token

    Raises:
        ValueError: If credentials invalid or user inactive
    """
    conn = get_conn()

    user_row = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not user_row:
        raise ValueError("Invalid email or password")

    user = dict(user_row)

    if not user["is_active"]:
        raise ValueError("Account is disabled")

    if not check_password_hash(user["password_hash"], password):
        raise ValueError("Invalid email or password")

    # Create session token (UUID4)
    token = str(uuid.uuid4())
    session_id = generate_id("sess")
    now = now_iso()
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"

    conn.execute(
        """
        INSERT INTO sessions (id, user_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, user["id"], token, expires_at, now)
    )

    # Update last_login
    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (now, user["id"])
    )
    conn.commit()

    # Remove password_hash from response
    del user["password_hash"]
    user["last_login"] = now

    return {
        "user": user,
        "token": token,
        "expires_at": expires_at
    }


def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate session token and return user.

    Args:
        token: Session token

    Returns:
        User dict without password_hash, or None if invalid/expired
    """
    conn = get_conn()

    session_row = conn.execute(
        """
        SELECT s.*, u.*
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
        """,
        (token,)
    ).fetchone()

    if not session_row:
        return None

    session = dict(session_row)

    # Check expiry
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
        # Session expired - delete it
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return None

    # Check if user is active
    if not session["is_active"]:
        return None

    # Return user data (extract from joined row)
    user = {
        "id": session["user_id"],
        "email": session["email"],
        "name": session["name"],
        "role": session["role"],
        "institution_id": session["institution_id"],
        "is_active": session["is_active"],
        "last_login": session["last_login"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"]
    }

    return user


def logout(token: str) -> bool:
    """
    Logout user by deleting session.

    Args:
        token: Session token

    Returns:
        True if session deleted
    """
    conn = get_conn()

    result = conn.execute(
        "DELETE FROM sessions WHERE token = ?",
        (token,)
    )
    conn.commit()

    return result.rowcount > 0


def request_password_reset(email: str) -> Optional[str]:
    """
    Generate password reset token.

    Args:
        email: User email

    Returns:
        Reset token, or None if user not found
    """
    conn = get_conn()

    user_row = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not user_row:
        return None

    user_id = user_row["id"]
    token = str(uuid.uuid4())
    reset_id = generate_id("reset")
    now = now_iso()
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

    conn.execute(
        """
        INSERT INTO password_resets (id, user_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (reset_id, user_id, token, expires_at, now)
    )
    conn.commit()

    return token


def reset_password(token: str, new_password: str) -> bool:
    """
    Reset password using reset token.

    Args:
        token: Password reset token
        new_password: New password (min 8 chars)

    Returns:
        True if password reset, False if token invalid/expired/used

    Raises:
        ValueError: If password too short
    """
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")

    conn = get_conn()

    reset_row = conn.execute(
        "SELECT * FROM password_resets WHERE token = ?",
        (token,)
    ).fetchone()

    if not reset_row:
        return False

    reset = dict(reset_row)

    # Check if already used
    if reset["used"]:
        return False

    # Check expiry
    expires_at = datetime.fromisoformat(reset["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
        return False

    # Update password
    password_hash = generate_password_hash(new_password)
    now = now_iso()

    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (password_hash, now, reset["user_id"])
    )

    # Mark reset token as used
    conn.execute(
        "UPDATE password_resets SET used = 1 WHERE id = ?",
        (reset["id"],)
    )

    # Invalidate all sessions for this user
    conn.execute(
        "DELETE FROM sessions WHERE user_id = ?",
        (reset["user_id"],)
    )

    conn.commit()

    return True


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User dict without password_hash, or None if not found
    """
    conn = get_conn()

    user_row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user_row:
        return None

    user = dict(user_row)
    del user["password_hash"]

    return user


def update_user(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update user fields.

    Args:
        user_id: User ID
        updates: Dict with fields to update (name, email)

    Returns:
        Updated user dict, or None if user not found

    Raises:
        ValueError: If email already exists
    """
    conn = get_conn()

    # Check user exists
    user_row = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user_row:
        return None

    # Check email uniqueness if updating
    if "email" in updates:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? AND id != ?",
            (updates["email"], user_id)
        ).fetchone()

        if existing:
            raise ValueError("Email already registered")

    # Build update query
    allowed_fields = ["name", "email", "role", "institution_id", "is_active"]
    update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

    if not update_fields:
        return get_user(user_id)

    update_fields["updated_at"] = now_iso()

    set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
    values = list(update_fields.values()) + [user_id]

    conn.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        values
    )
    conn.commit()

    return get_user(user_id)
