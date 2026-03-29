"""
Role-Based Access Control service for multi-user permissions.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import secrets

from src.db.connection import get_conn
from src.core.models.helpers import generate_id, now_iso


# Role hierarchy (lowest to highest privilege)
ROLE_HIERARCHY = ['viewer', 'department_head', 'compliance_officer', 'admin', 'owner']

# Permission matrix
ROLE_PERMISSIONS = {
    'viewer': ['view_dashboard', 'view_reports'],
    'department_head': ['view_dashboard', 'view_reports', 'upload_documents', 'complete_tasks'],
    'compliance_officer': [
        'view_dashboard', 'view_reports', 'upload_documents', 'complete_tasks',
        'run_audits', 'approve_remediation', 'export_packets', 'manage_standards',
        'view_audit_trail'
    ],
    'admin': ['*'],  # All except delete_institution
    'owner': ['**']  # All including delete_institution
}


def check_permission(user_id: str, action: str, institution_id: Optional[str] = None) -> bool:
    """
    Check if user has permission to perform an action.

    Args:
        user_id: User ID
        action: Permission action (e.g., 'run_audits', 'delete_institution')
        institution_id: Optional institution ID for scoped permissions

    Returns:
        True if user has permission, False otherwise
    """
    role = get_user_role(user_id, institution_id)
    if not role:
        return False

    permissions = ROLE_PERMISSIONS.get(role, [])

    # Owner has all permissions
    if '**' in permissions:
        return True

    # Admin has all except delete_institution
    if '*' in permissions:
        return action != 'delete_institution'

    # Check specific permissions
    return action in permissions


def get_user_role(user_id: str, institution_id: Optional[str] = None) -> Optional[str]:
    """
    Get user's role for a specific institution or global role.

    Args:
        user_id: User ID
        institution_id: Optional institution ID for scoped role

    Returns:
        Role string or None if user not found
    """
    conn = get_conn()

    # If institution_id provided, check for institution-specific role
    if institution_id:
        # Check if user has institution-specific role via user_permissions
        perm_row = conn.execute(
            """
            SELECT permission FROM user_permissions
            WHERE user_id = ? AND institution_id = ? AND permission LIKE 'role:%'
            LIMIT 1
            """,
            (user_id, institution_id)
        ).fetchone()

        if perm_row:
            # Extract role from 'role:owner' format
            return perm_row['permission'].split(':', 1)[1]

    # Fall back to user's global role
    user_row = conn.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user_row:
        return user_row['role']

    return None


def assign_role(
    user_id: str,
    role: str,
    institution_id: str,
    assigned_by: str
) -> Dict[str, Any]:
    """
    Assign a role to a user for a specific institution.

    Args:
        user_id: User ID
        role: Role to assign (must be in ROLE_HIERARCHY)
        institution_id: Institution ID
        assigned_by: User ID who is assigning the role

    Returns:
        Success dict with details

    Raises:
        ValueError: If role invalid or user not found
    """
    if role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid role: {role}")

    conn = get_conn()

    # Verify user exists
    user_row = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user_row:
        raise ValueError("User not found")

    # Store role as permission 'role:owner', 'role:admin', etc.
    permission = f"role:{role}"
    perm_id = generate_id("perm")
    created_at = now_iso()

    # Delete existing role permission for this institution
    conn.execute(
        """
        DELETE FROM user_permissions
        WHERE user_id = ? AND institution_id = ? AND permission LIKE 'role:%'
        """,
        (user_id, institution_id)
    )

    # Insert new role permission
    conn.execute(
        """
        INSERT INTO user_permissions (id, user_id, institution_id, permission, granted_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (perm_id, user_id, institution_id, permission, assigned_by, created_at)
    )

    conn.commit()

    return {
        "success": True,
        "user_id": user_id,
        "role": role,
        "institution_id": institution_id
    }


def create_invitation(
    email: str,
    role: str,
    institution_id: str,
    invited_by: str
) -> Dict[str, Any]:
    """
    Create an invitation for a user to join an institution.

    Args:
        email: Email address to invite
        role: Role to assign (must be in ROLE_HIERARCHY)
        institution_id: Institution ID
        invited_by: User ID who is creating the invitation

    Returns:
        Invitation dict with token

    Raises:
        ValueError: If role invalid
    """
    if role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid role: {role}")

    conn = get_conn()

    invitation_id = generate_id("inv")
    token = secrets.token_urlsafe(32)
    created_at = now_iso()
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()

    conn.execute(
        """
        INSERT INTO user_invitations (id, email, role, institution_id, invited_by, token, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (invitation_id, email, role, institution_id, invited_by, token, expires_at, created_at)
    )

    conn.commit()

    return {
        "id": invitation_id,
        "email": email,
        "role": role,
        "institution_id": institution_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": created_at
    }


def accept_invitation(token: str, user_id: str) -> Dict[str, Any]:
    """
    Accept an invitation and assign role to user.

    Args:
        token: Invitation token
        user_id: User ID accepting the invitation

    Returns:
        Success dict with details

    Raises:
        ValueError: If token invalid, expired, or already accepted
    """
    conn = get_conn()

    invitation = conn.execute(
        """
        SELECT id, email, role, institution_id, accepted, expires_at
        FROM user_invitations
        WHERE token = ?
        """,
        (token,)
    ).fetchone()

    if not invitation:
        raise ValueError("Invalid invitation token")

    if invitation['accepted']:
        raise ValueError("Invitation already accepted")

    # Check if expired
    expires_at = datetime.fromisoformat(invitation['expires_at'])
    if datetime.utcnow() > expires_at:
        raise ValueError("Invitation has expired")

    # Mark invitation as accepted
    conn.execute(
        "UPDATE user_invitations SET accepted = 1 WHERE token = ?",
        (token,)
    )

    # Assign role to user
    assign_role(
        user_id=user_id,
        role=invitation['role'],
        institution_id=invitation['institution_id'],
        assigned_by=user_id  # Self-assignment via invitation
    )

    conn.commit()

    return {
        "success": True,
        "user_id": user_id,
        "role": invitation['role'],
        "institution_id": invitation['institution_id']
    }


def list_users(institution_id: str) -> List[Dict[str, Any]]:
    """
    List all users with access to an institution.

    Args:
        institution_id: Institution ID

    Returns:
        List of user dicts with roles
    """
    conn = get_conn()

    # Get users with permissions for this institution
    rows = conn.execute(
        """
        SELECT DISTINCT u.id, u.email, u.name, u.active, u.last_login, u.created_at,
               up.permission
        FROM users u
        LEFT JOIN user_permissions up ON u.id = up.user_id AND up.institution_id = ?
        WHERE up.permission LIKE 'role:%' OR u.id IN (
            SELECT user_id FROM user_permissions WHERE institution_id = ?
        )
        ORDER BY u.name
        """,
        (institution_id, institution_id)
    ).fetchall()

    users = []
    for row in rows:
        role = None
        if row['permission'] and row['permission'].startswith('role:'):
            role = row['permission'].split(':', 1)[1]

        users.append({
            "id": row['id'],
            "email": row['email'],
            "name": row['name'],
            "role": role or 'viewer',
            "active": bool(row['active']),
            "last_login": row['last_login'],
            "created_at": row['created_at']
        })

    return users


def remove_user(user_id: str, institution_id: str, removed_by: str) -> Dict[str, Any]:
    """
    Remove a user's access to an institution.

    Args:
        user_id: User ID to remove
        institution_id: Institution ID
        removed_by: User ID performing the removal

    Returns:
        Success dict

    Raises:
        ValueError: If trying to remove last owner
    """
    conn = get_conn()

    # Check if user is the last owner
    current_role = get_user_role(user_id, institution_id)
    if current_role == 'owner':
        # Count owners for this institution
        owner_count = conn.execute(
            """
            SELECT COUNT(*) as count FROM user_permissions
            WHERE institution_id = ? AND permission = 'role:owner'
            """,
            (institution_id,)
        ).fetchone()

        if owner_count['count'] <= 1:
            raise ValueError("Cannot remove last owner")

    # Remove all permissions for this institution
    conn.execute(
        """
        DELETE FROM user_permissions
        WHERE user_id = ? AND institution_id = ?
        """,
        (user_id, institution_id)
    )

    conn.commit()

    return {
        "success": True,
        "user_id": user_id,
        "institution_id": institution_id
    }


def list_pending_invitations(institution_id: str) -> List[Dict[str, Any]]:
    """
    List pending invitations for an institution.

    Args:
        institution_id: Institution ID

    Returns:
        List of invitation dicts
    """
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT id, email, role, invited_by, token, expires_at, created_at
        FROM user_invitations
        WHERE institution_id = ? AND accepted = 0
        ORDER BY created_at DESC
        """,
        (institution_id,)
    ).fetchall()

    invitations = []
    for row in rows:
        invitations.append({
            "id": row['id'],
            "email": row['email'],
            "role": row['role'],
            "invited_by": row['invited_by'],
            "token": row['token'],
            "expires_at": row['expires_at'],
            "created_at": row['created_at']
        })

    return invitations


def cancel_invitation(invitation_id: str) -> Dict[str, Any]:
    """
    Cancel a pending invitation.

    Args:
        invitation_id: Invitation ID

    Returns:
        Success dict

    Raises:
        ValueError: If invitation not found or already accepted
    """
    conn = get_conn()

    invitation = conn.execute(
        "SELECT accepted FROM user_invitations WHERE id = ?",
        (invitation_id,)
    ).fetchone()

    if not invitation:
        raise ValueError("Invitation not found")

    if invitation['accepted']:
        raise ValueError("Cannot cancel accepted invitation")

    conn.execute(
        "DELETE FROM user_invitations WHERE id = ?",
        (invitation_id,)
    )

    conn.commit()

    return {
        "success": True,
        "invitation_id": invitation_id
    }
