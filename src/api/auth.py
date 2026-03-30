"""
Authentication API blueprint.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any

from src.services import auth_service, activity_service


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Global reference for dependency injection
_auth_service = None


def init_auth_bp(service=None):
    """
    Initialize auth blueprint with dependencies.

    Args:
        service: Auth service module (defaults to auth_service)
    """
    global _auth_service
    _auth_service = service or auth_service


def _get_token_from_request() -> str:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return ""


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.

    Request body:
        {
            "email": "user@example.com",
            "password": "password123",
            "name": "User Name",
            "institution_id": "inst_xxx" (optional)
        }

    Returns:
        200: {"user": {...}, "token": "..."}
        400: {"error": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        email = data.get("email", "").strip()
        password = data.get("password", "")
        name = data.get("name", "").strip()
        institution_id = data.get("institution_id")

        if not email or not password or not name:
            return jsonify({"error": "Email, password, and name are required"}), 400

        # Register user
        user = _auth_service.register_user(
            email=email,
            password=password,
            name=name,
            institution_id=institution_id
        )

        # Auto-login after registration
        auth_result = _auth_service.authenticate(email, password)

        return jsonify({
            "user": auth_result["user"],
            "token": auth_result["token"],
            "expires_at": auth_result["expires_at"]
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with email/password.

    Request body:
        {
            "email": "user@example.com",
            "password": "password123"
        }

    Returns:
        200: {"user": {...}, "token": "..."}
        401: {"error": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        # Authenticate
        result = _auth_service.authenticate(email, password)

        # Log activity
        user = result.get("user")
        if user:
            activity_service.log_activity(
                user_id=user.get("id"),
                user_name=user.get("name") or user.get("email"),
                institution_id=user.get("institution_id"),
                action="user.login",
                details=f"Login via email: {email}",
                ip_address=request.remote_addr
            )

        return jsonify(result), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout current user.

    Requires:
        Authorization: Bearer <token>

    Returns:
        200: {"success": true}
        401: {"error": "..."}
    """
    try:
        token = _get_token_from_request()

        if not token:
            return jsonify({"error": "Authentication required"}), 401

        # Validate session first
        user = _auth_service.validate_session(token)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401

        # Log activity before logout
        activity_service.log_activity(
            user_id=user.get("id"),
            user_name=user.get("name") or user.get("email"),
            institution_id=user.get("institution_id"),
            action="user.logout",
            details="User logged out",
            ip_address=request.remote_addr
        )

        # Logout
        _auth_service.logout(token)

        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": f"Logout failed: {str(e)}"}), 500


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """
    Get current authenticated user.

    Requires:
        Authorization: Bearer <token>

    Returns:
        200: {"user": {...}}
        401: {"error": "..."}
    """
    try:
        token = _get_token_from_request()

        if not token:
            return jsonify({"error": "Authentication required"}), 401

        # Validate session
        user = _auth_service.validate_session(token)
        if not user:
            return jsonify({"error": "Invalid or expired session"}), 401

        return jsonify({"user": user}), 200

    except Exception as e:
        return jsonify({"error": f"Failed to get user: {str(e)}"}), 500


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Request password reset.

    Request body:
        {
            "email": "user@example.com"
        }

    Returns:
        200: {"success": true} (always, even if email not found - security best practice)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        email = data.get("email", "").strip()

        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Generate reset token (returns None if user not found, but we don't reveal that)
        token = _auth_service.request_password_reset(email)

        # In production, send email with reset link here
        # For now, return token in response (dev only)
        response = {"success": True, "message": "If this email exists, a reset link has been sent"}

        # Include token in dev mode for testing
        if token:
            response["token"] = token  # Remove this in production

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": f"Failed to process request: {str(e)}"}), 500


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Reset password with token.

    Request body:
        {
            "token": "...",
            "password": "newpassword123"
        }

    Returns:
        200: {"success": true}
        400: {"error": "..."}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body required"}), 400

        token = data.get("token", "").strip()
        password = data.get("password", "")

        if not token or not password:
            return jsonify({"error": "Token and password are required"}), 400

        # Reset password
        success = _auth_service.reset_password(token, password)

        if not success:
            return jsonify({"error": "Invalid or expired reset token"}), 400

        return jsonify({"success": True, "message": "Password reset successfully"}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to reset password: {str(e)}"}), 500
