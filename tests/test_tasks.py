"""
Tests for Task Management (Phase 44).

Tests task service, API endpoints, and integration with audits.
"""

import pytest
from datetime import datetime, timedelta
from src.services import task_service
from src.db.connection import get_conn


@pytest.fixture
def db():
    """Database fixture with cleanup."""
    conn = get_conn()
    # Clean up test data before and after
    conn.execute("DELETE FROM task_comments WHERE task_id LIKE 'task_test%'")
    conn.execute("DELETE FROM tasks WHERE id LIKE 'task_test%' OR institution_id LIKE 'test_%'")
    conn.commit()
    yield conn
    conn.execute("DELETE FROM task_comments WHERE task_id LIKE 'task_test%'")
    conn.execute("DELETE FROM tasks WHERE id LIKE 'task_test%' OR institution_id LIKE 'test_%'")
    conn.commit()


@pytest.fixture
def institution_id():
    """Test institution ID."""
    return "test_inst_001"


@pytest.fixture
def user_id():
    """Test user ID."""
    return "test_user_001"


@pytest.fixture
def sample_task(institution_id):
    """Create a sample task."""
    task_id = task_service.create_task(
        institution_id=institution_id,
        title="Test Task",
        description="Test description",
        priority="normal",
        category="compliance"
    )
    yield task_id
    # Cleanup
    task_service.delete_task(task_id)


def test_create_task(institution_id):
    """Test creating a task."""
    task_id = task_service.create_task(
        institution_id=institution_id,
        title="Test Task",
        description="Test description",
        priority="high",
        category="documentation"
    )

    assert task_id.startswith("task_")

    task = task_service.get_task_by_id(task_id)
    assert task is not None
    assert task["title"] == "Test Task"
    assert task["description"] == "Test description"
    assert task["status"] == "pending"
    assert task["priority"] == "high"
    assert task["category"] == "documentation"

    # Cleanup
    task_service.delete_task(task_id)


def test_update_task(sample_task):
    """Test updating a task."""
    success = task_service.update_task(sample_task, {
        "title": "Updated Title",
        "priority": "critical"
    })

    assert success is True

    task = task_service.get_task_by_id(sample_task)
    assert task["title"] == "Updated Title"
    assert task["priority"] == "critical"


def test_assign_task(sample_task, user_id):
    """Test assigning a task to a user."""
    success = task_service.assign_task(sample_task, user_id, assigned_by="user_admin")

    assert success is True

    task = task_service.get_task_by_id(sample_task)
    assert task["assigned_to"] == user_id
    assert task["assigned_by"] == "user_admin"


def test_complete_task(sample_task, user_id):
    """Test completing a task."""
    success = task_service.complete_task(sample_task, user_id)

    assert success is True

    task = task_service.get_task_by_id(sample_task)
    assert task["status"] == "completed"
    assert task["completed_at"] is not None


def test_get_tasks_with_filters(institution_id):
    """Test getting tasks with filters."""
    # Create test tasks
    task1_id = task_service.create_task(
        institution_id=institution_id,
        title="Task 1",
        priority="critical",
        category="compliance"
    )

    task2_id = task_service.create_task(
        institution_id=institution_id,
        title="Task 2",
        priority="normal",
        category="evidence"
    )

    # Filter by priority
    result = task_service.get_tasks(institution_id, filters={"priority": "critical"})
    assert result["total"] >= 1
    assert any(t["id"] == task1_id for t in result["tasks"])

    # Filter by category
    result = task_service.get_tasks(institution_id, filters={"category": "evidence"})
    assert result["total"] >= 1
    assert any(t["id"] == task2_id for t in result["tasks"])

    # Cleanup
    task_service.delete_task(task1_id)
    task_service.delete_task(task2_id)


def test_overdue_detection(institution_id):
    """Test detecting overdue tasks."""
    # Create overdue task
    past_date = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d")
    task_id = task_service.create_task(
        institution_id=institution_id,
        title="Overdue Task",
        due_date=past_date
    )

    overdue_tasks = task_service.get_overdue_tasks(institution_id)
    assert any(t["id"] == task_id for t in overdue_tasks)

    # Cleanup
    task_service.delete_task(task_id)


def test_task_stats(institution_id):
    """Test task statistics calculation."""
    # Create tasks - status is always pending on creation
    task1_id = task_service.create_task(
        institution_id=institution_id,
        title="Pending Task"
    )

    task2_id = task_service.create_task(
        institution_id=institution_id,
        title="Completed Task"
    )
    task_service.complete_task(task2_id, "user_test")

    stats = task_service.get_task_stats(institution_id)
    assert stats["total"] >= 2
    assert stats["pending"] >= 1
    assert stats["completed"] >= 1

    # Cleanup
    task_service.delete_task(task1_id)
    task_service.delete_task(task2_id)


def test_add_comment(sample_task, user_id):
    """Test adding a comment to a task."""
    comment_id = task_service.add_comment(
        task_id=sample_task,
        user_id=user_id,
        user_name="Test User",
        content="This is a test comment"
    )

    assert comment_id.startswith("comment_")

    comments = task_service.get_comments(sample_task)
    assert len(comments) >= 1
    assert any(c["content"] == "This is a test comment" for c in comments)


def test_get_comments(sample_task, user_id):
    """Test retrieving comments for a task."""
    # Add multiple comments
    task_service.add_comment(sample_task, user_id, "User 1", "Comment 1")
    task_service.add_comment(sample_task, user_id, "User 2", "Comment 2")

    comments = task_service.get_comments(sample_task)
    assert len(comments) >= 2


def test_bulk_create_from_findings(institution_id):
    """Test bulk creating tasks from audit findings."""
    findings = [
        {
            "id": "find_001",
            "title": "Missing Policy",
            "description": "Policy document is missing",
            "severity": "critical",
            "recommendation": "Upload the missing policy"
        },
        {
            "id": "find_002",
            "title": "Incomplete Documentation",
            "description": "Documentation is incomplete",
            "severity": "major",
            "recommendation": "Complete the documentation"
        }
    ]

    task_ids = task_service.create_tasks_from_findings(
        institution_id=institution_id,
        findings=findings,
        assigned_by="user_admin"
    )

    assert len(task_ids) == 2

    # Check first task
    task1 = task_service.get_task_by_id(task_ids[0])
    assert task1["title"] == "Missing Policy"
    assert task1["priority"] == "critical"
    assert task1["source_type"] == "audit_finding"
    assert task1["source_id"] == "find_001"
    assert task1["category"] == "compliance"

    # Check second task
    task2 = task_service.get_task_by_id(task_ids[1])
    assert task2["title"] == "Incomplete Documentation"
    assert task2["priority"] == "high"  # major maps to high

    # Cleanup
    for task_id in task_ids:
        task_service.delete_task(task_id)


def test_delete_task(institution_id):
    """Test deleting a task."""
    task_id = task_service.create_task(
        institution_id=institution_id,
        title="Task to Delete"
    )

    success = task_service.delete_task(task_id)
    assert success is True

    task = task_service.get_task_by_id(task_id)
    assert task is None


def test_get_my_tasks(institution_id, user_id):
    """Test getting tasks for a specific user."""
    # Create task assigned to user
    task_id = task_service.create_task(
        institution_id=institution_id,
        title="My Task",
        assigned_to=user_id
    )

    my_tasks = task_service.get_my_tasks(user_id)
    assert any(t["id"] == task_id for t in my_tasks)

    # Cleanup
    task_service.delete_task(task_id)


def test_task_pagination(institution_id):
    """Test task pagination."""
    # Create 15 tasks
    task_ids = []
    for i in range(15):
        task_id = task_service.create_task(
            institution_id=institution_id,
            title=f"Task {i}"
        )
        task_ids.append(task_id)

    # Get first page
    result = task_service.get_tasks(institution_id, page=1, per_page=10)
    assert result["total"] >= 15
    assert len(result["tasks"]) == 10
    assert result["pages"] >= 2

    # Get second page
    result = task_service.get_tasks(institution_id, page=2, per_page=10)
    assert len(result["tasks"]) >= 5

    # Cleanup
    for task_id in task_ids:
        task_service.delete_task(task_id)


def test_priority_sorting(institution_id):
    """Test that tasks are sorted by priority."""
    # Create tasks with different priorities
    low_task = task_service.create_task(
        institution_id=institution_id,
        title="Low Priority",
        priority="low"
    )

    critical_task = task_service.create_task(
        institution_id=institution_id,
        title="Critical Priority",
        priority="critical"
    )

    normal_task = task_service.create_task(
        institution_id=institution_id,
        title="Normal Priority",
        priority="normal"
    )

    # Get all tasks
    result = task_service.get_tasks(institution_id)

    # Find positions of our tasks
    task_ids = [t["id"] for t in result["tasks"]]
    critical_pos = task_ids.index(critical_task)
    normal_pos = task_ids.index(normal_task)
    low_pos = task_ids.index(low_task)

    # Critical should come before normal, normal before low
    assert critical_pos < normal_pos < low_pos

    # Cleanup
    task_service.delete_task(low_task)
    task_service.delete_task(critical_task)
    task_service.delete_task(normal_task)
