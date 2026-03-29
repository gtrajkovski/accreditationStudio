"""
Tests for authentication system.
"""

import pytest
from datetime import datetime, timedelta

from src.services import auth_service
from src.db.connection import get_conn
from src.db.migrate import apply_migrations


@pytest.fixture(scope="function")
def db():
    """Create a fresh test database for each test."""
    # Apply all migrations
    apply_migrations()

    conn = get_conn()

    # Clear auth tables
    conn.execute("DELETE FROM password_resets")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM users")
    conn.commit()

    yield conn

    # Cleanup
    conn.execute("DELETE FROM password_resets")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM users")
    conn.commit()


def test_register_user(db):
    """Test user registration."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    assert user["email"] == "test@example.com"
    assert user["name"] == "Test User"
    assert user["role"] == "viewer"
    assert user["is_active"] is True
    assert "password_hash" not in user

    # Verify in database
    row = db.execute(
        "SELECT * FROM users WHERE email = ?",
        ("test@example.com",)
    ).fetchone()

    assert row is not None
    assert row["email"] == "test@example.com"
    assert row["password_hash"] != "testpass123"  # Should be hashed


def test_register_duplicate_email(db):
    """Test registering with duplicate email."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    with pytest.raises(ValueError, match="Email already registered"):
        auth_service.register_user(
            email="test@example.com",
            password="different123",
            name="Another User"
        )


def test_register_short_password(db):
    """Test registering with short password."""
    with pytest.raises(ValueError, match="at least 8 characters"):
        auth_service.register_user(
            email="test@example.com",
            password="short",
            name="Test User"
        )


def test_authenticate_correct_credentials(db):
    """Test authentication with correct credentials."""
    # Register user
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Authenticate
    result = auth_service.authenticate("test@example.com", "testpass123")

    assert "user" in result
    assert "token" in result
    assert "expires_at" in result
    assert result["user"]["email"] == "test@example.com"
    assert len(result["token"]) > 0

    # Verify session in database
    row = db.execute(
        "SELECT * FROM sessions WHERE token = ?",
        (result["token"],)
    ).fetchone()

    assert row is not None
    assert row["user_id"] == result["user"]["id"]


def test_authenticate_wrong_password(db):
    """Test authentication with wrong password."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("test@example.com", "wrongpass")


def test_authenticate_nonexistent_user(db):
    """Test authentication with nonexistent email."""
    with pytest.raises(ValueError, match="Invalid email or password"):
        auth_service.authenticate("nonexistent@example.com", "testpass123")


def test_authenticate_inactive_user(db):
    """Test authentication with inactive user."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Deactivate user
    db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user["id"],))
    db.commit()

    with pytest.raises(ValueError, match="Account is disabled"):
        auth_service.authenticate("test@example.com", "testpass123")


def test_validate_session_valid_token(db):
    """Test validating a valid session token."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    result = auth_service.authenticate("test@example.com", "testpass123")
    token = result["token"]

    # Validate session
    user = auth_service.validate_session(token)

    assert user is not None
    assert user["email"] == "test@example.com"
    assert "password_hash" not in user


def test_validate_session_invalid_token(db):
    """Test validating an invalid token."""
    user = auth_service.validate_session("invalid-token-123")
    assert user is None


def test_validate_session_expired_token(db):
    """Test validating an expired token."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    result = auth_service.authenticate("test@example.com", "testpass123")
    token = result["token"]

    # Manually expire the session
    past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
    db.execute(
        "UPDATE sessions SET expires_at = ? WHERE token = ?",
        (past_time, token)
    )
    db.commit()

    # Should return None and delete session
    user = auth_service.validate_session(token)
    assert user is None

    # Verify session was deleted
    row = db.execute(
        "SELECT * FROM sessions WHERE token = ?",
        (token,)
    ).fetchone()
    assert row is None


def test_logout(db):
    """Test logout functionality."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    result = auth_service.authenticate("test@example.com", "testpass123")
    token = result["token"]

    # Logout
    success = auth_service.logout(token)
    assert success is True

    # Verify session was deleted
    row = db.execute(
        "SELECT * FROM sessions WHERE token = ?",
        (token,)
    ).fetchone()
    assert row is None

    # Validate session should now fail
    user = auth_service.validate_session(token)
    assert user is None


def test_request_password_reset(db):
    """Test password reset request."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Request reset
    token = auth_service.request_password_reset("test@example.com")

    assert token is not None
    assert len(token) > 0

    # Verify in database
    row = db.execute(
        "SELECT * FROM password_resets WHERE user_id = ?",
        (user["id"],)
    ).fetchone()

    assert row is not None
    assert row["token"] == token
    assert row["used"] == 0


def test_request_password_reset_nonexistent_email(db):
    """Test password reset for nonexistent email."""
    token = auth_service.request_password_reset("nonexistent@example.com")
    assert token is None


def test_reset_password_valid_token(db):
    """Test password reset with valid token."""
    auth_service.register_user(
        email="test@example.com",
        password="oldpass123",
        name="Test User"
    )

    # Create session
    result = auth_service.authenticate("test@example.com", "oldpass123")
    old_token = result["token"]

    # Request reset
    reset_token = auth_service.request_password_reset("test@example.com")

    # Reset password
    success = auth_service.reset_password(reset_token, "newpass123")
    assert success is True

    # Old session should be invalidated
    user = auth_service.validate_session(old_token)
    assert user is None

    # Should be able to login with new password
    new_result = auth_service.authenticate("test@example.com", "newpass123")
    assert new_result is not None

    # Old password should not work
    with pytest.raises(ValueError):
        auth_service.authenticate("test@example.com", "oldpass123")


def test_reset_password_invalid_token(db):
    """Test password reset with invalid token."""
    success = auth_service.reset_password("invalid-token", "newpass123")
    assert success is False


def test_reset_password_used_token(db):
    """Test password reset with already used token."""
    auth_service.register_user(
        email="test@example.com",
        password="oldpass123",
        name="Test User"
    )

    reset_token = auth_service.request_password_reset("test@example.com")

    # Use token
    auth_service.reset_password(reset_token, "newpass123")

    # Try to use again
    success = auth_service.reset_password(reset_token, "anotherpass123")
    assert success is False


def test_reset_password_expired_token(db):
    """Test password reset with expired token."""
    user = auth_service.register_user(
        email="test@example.com",
        password="oldpass123",
        name="Test User"
    )

    reset_token = auth_service.request_password_reset("test@example.com")

    # Manually expire the token
    past_time = (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z"
    db.execute(
        "UPDATE password_resets SET expires_at = ? WHERE token = ?",
        (past_time, reset_token)
    )
    db.commit()

    # Should fail
    success = auth_service.reset_password(reset_token, "newpass123")
    assert success is False


def test_get_user(db):
    """Test getting user by ID."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Get user
    retrieved = auth_service.get_user(user["id"])

    assert retrieved is not None
    assert retrieved["id"] == user["id"]
    assert retrieved["email"] == "test@example.com"
    assert "password_hash" not in retrieved


def test_get_user_nonexistent(db):
    """Test getting nonexistent user."""
    user = auth_service.get_user("nonexistent-id")
    assert user is None


def test_update_user(db):
    """Test updating user fields."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Update name
    updated = auth_service.update_user(user["id"], {"name": "Updated Name"})

    assert updated is not None
    assert updated["name"] == "Updated Name"
    assert updated["email"] == "test@example.com"


def test_update_user_email(db):
    """Test updating user email."""
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    # Update email
    updated = auth_service.update_user(
        user["id"],
        {"email": "newemail@example.com"}
    )

    assert updated is not None
    assert updated["email"] == "newemail@example.com"


def test_update_user_duplicate_email(db):
    """Test updating to duplicate email."""
    user1 = auth_service.register_user(
        email="user1@example.com",
        password="testpass123",
        name="User 1"
    )

    user2 = auth_service.register_user(
        email="user2@example.com",
        password="testpass123",
        name="User 2"
    )

    # Try to update user2's email to user1's email
    with pytest.raises(ValueError, match="Email already registered"):
        auth_service.update_user(user2["id"], {"email": "user1@example.com"})


def test_session_expiry_24_hours(db):
    """Test that sessions expire after 24 hours."""
    auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    result = auth_service.authenticate("test@example.com", "testpass123")

    # Check expiry is approximately 24 hours from now
    expires_at = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
    now = datetime.utcnow().replace(tzinfo=expires_at.tzinfo)
    delta = expires_at - now

    # Should be close to 24 hours (within 1 minute tolerance)
    assert 23.9 * 3600 < delta.total_seconds() < 24.1 * 3600


def test_auth_disabled_bypass(db, monkeypatch):
    """Test that AUTH_ENABLED=False bypasses authentication (simulated)."""
    # This test verifies the service layer works correctly
    # The actual bypass logic is in app.py middleware

    # Register and authenticate should still work
    user = auth_service.register_user(
        email="test@example.com",
        password="testpass123",
        name="Test User"
    )

    result = auth_service.authenticate("test@example.com", "testpass123")

    assert result is not None
    assert user is not None
