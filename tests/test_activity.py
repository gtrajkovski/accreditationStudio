"""
Tests for activity logging service and API.
"""

import pytest
from datetime import datetime, timedelta
from src.services import activity_service
from src.db.connection import get_conn
from src.core.models import generate_id, now_iso


@pytest.fixture
def setup_activity_table():
    """Ensure activity_log table exists."""
    conn = get_conn()
    # Apply migration if needed
    from src.db.migrate import apply_migrations
    apply_migrations()

    # Clean up any existing test data
    conn.execute("DELETE FROM activity_log WHERE institution_id LIKE 'test_%'")
    conn.commit()

    yield

    # Cleanup
    conn.execute("DELETE FROM activity_log WHERE institution_id LIKE 'test_%'")
    conn.commit()


def test_log_activity(setup_activity_table):
    """Test that activity can be logged."""
    institution_id = "test_inst_001"
    user_id = "test_user_001"

    activity_id = activity_service.log_activity(
        user_id=user_id,
        user_name="Test User",
        institution_id=institution_id,
        action="document.upload",
        entity_type="document",
        entity_id="doc_123",
        details="Uploaded test.pdf",
        ip_address="192.168.1.1"
    )

    assert activity_id.startswith("activity_")

    # Verify it was logged
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM activity_log WHERE id = ?",
        (activity_id,)
    ).fetchone()

    assert row is not None
    assert row["user_id"] == user_id
    assert row["institution_id"] == institution_id
    assert row["action"] == "document.upload"
    assert row["entity_type"] == "document"
    assert row["entity_id"] == "doc_123"
    assert row["details"] == "Uploaded test.pdf"
    assert row["ip_address"] == "192.168.1.1"


def test_get_activity_pagination(setup_activity_table):
    """Test that activity retrieval supports pagination."""
    institution_id = "test_inst_002"

    # Log 25 activities
    for i in range(25):
        activity_service.log_activity(
            user_id=f"user_{i}",
            user_name=f"User {i}",
            institution_id=institution_id,
            action="document.upload",
            entity_type="document",
            entity_id=f"doc_{i}",
            details=f"Upload {i}"
        )

    # Get first page
    result = activity_service.get_activity(institution_id, page=1, per_page=10)

    assert result["total"] == 25
    assert len(result["items"]) == 10
    assert result["page"] == 1
    assert result["pages"] == 3

    # Get second page
    result2 = activity_service.get_activity(institution_id, page=2, per_page=10)

    assert result2["total"] == 25
    assert len(result2["items"]) == 10
    assert result2["page"] == 2


def test_get_activity_filters(setup_activity_table):
    """Test that activity can be filtered by user, action, and date."""
    institution_id = "test_inst_003"

    # Log various activities
    activity_service.log_activity(
        user_id="user_a",
        user_name="User A",
        institution_id=institution_id,
        action="document.upload",
        entity_type="document",
        entity_id="doc_1"
    )

    activity_service.log_activity(
        user_id="user_b",
        user_name="User B",
        institution_id=institution_id,
        action="audit.start",
        entity_type="audit",
        entity_id="audit_1"
    )

    activity_service.log_activity(
        user_id="user_a",
        user_name="User A",
        institution_id=institution_id,
        action="audit.complete",
        entity_type="audit",
        entity_id="audit_1"
    )

    # Filter by user
    result = activity_service.get_activity(
        institution_id,
        filters={"user_id": "user_a"}
    )

    assert result["total"] == 2
    assert all(item["user_id"] == "user_a" for item in result["items"])

    # Filter by action
    result = activity_service.get_activity(
        institution_id,
        filters={"action": "audit.start"}
    )

    assert result["total"] == 1
    assert result["items"][0]["action"] == "audit.start"


def test_get_activity_for_entity(setup_activity_table):
    """Test retrieving activity for a specific entity."""
    institution_id = "test_inst_004"
    entity_id = "doc_special"

    # Log activities for this entity
    activity_service.log_activity(
        user_id="user_1",
        user_name="User 1",
        institution_id=institution_id,
        action="document.upload",
        entity_type="document",
        entity_id=entity_id,
        details="Initial upload"
    )

    activity_service.log_activity(
        user_id="user_2",
        user_name="User 2",
        institution_id=institution_id,
        action="document.update",
        entity_type="document",
        entity_id=entity_id,
        details="Updated content"
    )

    # Log activity for different entity
    activity_service.log_activity(
        user_id="user_1",
        user_name="User 1",
        institution_id=institution_id,
        action="document.upload",
        entity_type="document",
        entity_id="other_doc"
    )

    # Get activity for specific entity
    activities = activity_service.get_activity_for_entity("document", entity_id)

    assert len(activities) == 2
    assert all(a["entity_id"] == entity_id for a in activities)


def test_get_activity_summary(setup_activity_table):
    """Test activity summary by action type."""
    institution_id = "test_inst_005"

    # Log various activities
    for _ in range(5):
        activity_service.log_activity(
            user_id="user_1",
            user_name="User 1",
            institution_id=institution_id,
            action="document.upload"
        )

    for _ in range(3):
        activity_service.log_activity(
            user_id="user_1",
            user_name="User 1",
            institution_id=institution_id,
            action="audit.start"
        )

    for _ in range(2):
        activity_service.log_activity(
            user_id="user_1",
            user_name="User 1",
            institution_id=institution_id,
            action="user.login"
        )

    # Get summary
    summary = activity_service.get_activity_summary(institution_id, days=30)

    assert summary["document.upload"] == 5
    assert summary["audit.start"] == 3
    assert summary["user.login"] == 2


def test_export_activity_csv(setup_activity_table):
    """Test CSV export of activity log."""
    institution_id = "test_inst_006"

    # Log some activities
    activity_service.log_activity(
        user_id="user_1",
        user_name="Test User",
        institution_id=institution_id,
        action="document.upload",
        entity_type="document",
        entity_id="doc_1",
        details="Test upload",
        ip_address="192.168.1.1"
    )

    # Export CSV
    csv_data = activity_service.export_activity(institution_id)

    assert csv_data is not None
    assert "Timestamp" in csv_data
    assert "User Name" in csv_data
    assert "Action" in csv_data
    assert "Test User" in csv_data
    assert "document.upload" in csv_data


def test_activity_scoped_to_institution(setup_activity_table):
    """Test that activities are scoped to institutions."""
    institution_a = "test_inst_007a"
    institution_b = "test_inst_007b"

    # Log activities for institution A
    activity_service.log_activity(
        user_id="user_1",
        user_name="User 1",
        institution_id=institution_a,
        action="document.upload"
    )

    # Log activities for institution B
    activity_service.log_activity(
        user_id="user_1",
        user_name="User 1",
        institution_id=institution_b,
        action="document.upload"
    )

    # Get activities for A
    result_a = activity_service.get_activity(institution_a)
    assert result_a["total"] == 1

    # Get activities for B
    result_b = activity_service.get_activity(institution_b)
    assert result_b["total"] == 1


def test_login_logout_logged():
    """Test that login and logout actions are logged (integration test concept)."""
    # This would be an integration test with the auth API
    # For now, we verify the service can log these actions

    institution_id = "test_inst_008"

    activity_service.log_activity(
        user_id="user_1",
        user_name="Test User",
        institution_id=institution_id,
        action="user.login",
        details="Login via email: test@example.com",
        ip_address="192.168.1.1"
    )

    activity_service.log_activity(
        user_id="user_1",
        user_name="Test User",
        institution_id=institution_id,
        action="user.logout",
        details="User logged out",
        ip_address="192.168.1.1"
    )

    result = activity_service.get_activity(institution_id)
    assert result["total"] == 2

    actions = [item["action"] for item in result["items"]]
    assert "user.login" in actions
    assert "user.logout" in actions


def test_audit_lifecycle_logged():
    """Test that audit start and complete are logged."""
    institution_id = "test_inst_009"
    audit_id = "audit_test_001"

    activity_service.log_activity(
        user_id="user_1",
        user_name="Test User",
        institution_id=institution_id,
        action="audit.start",
        entity_type="audit",
        entity_id=audit_id,
        details="Started audit on document doc_1"
    )

    activity_service.log_activity(
        user_id="user_1",
        user_name="Test User",
        institution_id=institution_id,
        action="audit.complete",
        entity_type="audit",
        entity_id=audit_id,
        details="Completed audit"
    )

    # Get activity for this audit
    activities = activity_service.get_activity_for_entity("audit", audit_id)

    assert len(activities) == 2
    actions = [a["action"] for a in activities]
    assert "audit.start" in actions
    assert "audit.complete" in actions
