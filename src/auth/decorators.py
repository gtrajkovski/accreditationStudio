"""
Authentication and authorization decorators.

Provides:
- require_auth: Requires valid authentication token
- require_role: Requires specific role or higher
"""

from functools import wraps
from flask import request, jsonify, g
from typing import Callable


def require_auth(f: Callable) -> Callable:
    """
    Decorator to require authentication.

    Validates session token and attaches user to request.current_user and g.current_user.
    Returns 401 if authentication fails.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate session token
        from src.services import auth_service
        user = auth_service.validate_session(token)

        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401

        # Attach user to request and g
        request.current_user = user
        g.current_user = user

        return f(*args, **kwargs)

    return decorated


# Role hierarchy (higher = more permissions)
ROLE_HIERARCHY = {
    "viewer": 0,
    "department_head": 1,
    "compliance_officer": 2,
    "president": 3,
    "admin": 4
}


def require_role(required_role: str) -> Callable:
    """
    Decorator to require specific role or higher.

    Checks that authenticated user has at least the required role level.
    Returns 403 if user lacks required role.

    Args:
        required_role: Minimum role required (viewer, department_head, compliance_officer, president, admin)
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @require_auth  # First ensure user is authenticated
        def decorated(*args, **kwargs):
            user = getattr(request, 'current_user', None)

            if not user:
                return jsonify({"error": "Authentication required"}), 401

            user_role = user.get("role", "viewer")

            # Check role hierarchy
            user_level = ROLE_HIERARCHY.get(user_role, 0)
            required_level = ROLE_HIERARCHY.get(required_role, 0)

            if user_level < required_level:
                return jsonify({"error": "Insufficient permissions"}), 403

            return f(*args, **kwargs)

        return decorated

    return decorator
