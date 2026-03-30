"""
Tasks API Blueprint

Endpoints for task management: CRUD, assignment, comments, bulk creation.
"""

from flask import Blueprint, request, jsonify
from typing import Optional
from src.services import task_service
from src.auth.decorators import require_auth, require_role


tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@tasks_bp.route("/", methods=["GET"])
@require_auth
@require_role("department_head")
def list_tasks():
    """List tasks with filters (department_head+)."""
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    filters = {}
    if request.args.get("status"):
        filters["status"] = request.args.get("status")
    if request.args.get("priority"):
        filters["priority"] = request.args.get("priority")
    if request.args.get("assigned_to"):
        filters["assigned_to"] = request.args.get("assigned_to")
    if request.args.get("category"):
        filters["category"] = request.args.get("category")
    if request.args.get("overdue") == "true":
        filters["overdue"] = True
    if request.args.get("source_type"):
        filters["source_type"] = request.args.get("source_type")

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    result = task_service.get_tasks(institution_id, filters, page, per_page)
    return jsonify(result)


@tasks_bp.route("/", methods=["POST"])
@require_auth
@require_role("compliance_officer")
def create_task():
    """Create a new task (compliance_officer+)."""
    data = request.get_json()

    required = ["institution_id", "title"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    try:
        task_id = task_service.create_task(
            institution_id=data["institution_id"],
            title=data["title"],
            description=data.get("description"),
            assigned_to=data.get("assigned_to"),
            assigned_by=data.get("assigned_by"),
            due_date=data.get("due_date"),
            priority=data.get("priority", "normal"),
            source_type=data.get("source_type"),
            source_id=data.get("source_id"),
            category=data.get("category")
        )

        task = task_service.get_task_by_id(task_id)
        return jsonify({"success": True, "task": task}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/<task_id>", methods=["GET"])
@require_auth
@require_role("department_head")
def get_task(task_id: str):
    """Get task details (department_head+)."""
    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    return jsonify({"task": task})


@tasks_bp.route("/<task_id>", methods=["PUT"])
@require_auth
def update_task(task_id: str):
    """Update task (compliance_officer+ or assigned user)."""
    data = request.get_json()
    user = request.current_user

    # Check permissions
    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Compliance officer+ can update any task
    # Regular users can only update tasks assigned to them
    is_compliance_or_higher = user.get("role") in ["compliance_officer", "president", "admin"]
    is_assigned = task.get("assigned_to") == user.get("id")

    if not (is_compliance_or_higher or is_assigned):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        success = task_service.update_task(task_id, data)
        if success:
            updated_task = task_service.get_task_by_id(task_id)
            return jsonify({"success": True, "task": updated_task})
        else:
            return jsonify({"error": "Update failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/<task_id>/complete", methods=["POST"])
@require_auth
def complete_task(task_id: str):
    """Complete a task (assigned user or compliance_officer+)."""
    user = request.current_user

    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Check permissions
    is_compliance_or_higher = user.get("role") in ["compliance_officer", "president", "admin"]
    is_assigned = task.get("assigned_to") == user.get("id")

    if not (is_compliance_or_higher or is_assigned):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        success = task_service.complete_task(task_id, user.get("id"))
        if success:
            updated_task = task_service.get_task_by_id(task_id)
            return jsonify({"success": True, "task": updated_task})
        else:
            return jsonify({"error": "Complete failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/<task_id>/assign", methods=["POST"])
@require_auth
@require_role("compliance_officer")
def assign_task(task_id: str):
    """Assign task to a user (compliance_officer+)."""
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    try:
        assigned_by = request.current_user.get("id")
        success = task_service.assign_task(task_id, user_id, assigned_by)
        if success:
            updated_task = task_service.get_task_by_id(task_id)
            return jsonify({"success": True, "task": updated_task})
        else:
            return jsonify({"error": "Assignment failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/<task_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_task(task_id: str):
    """Delete a task (admin only)."""
    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    try:
        success = task_service.delete_task(task_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Delete failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/my", methods=["GET"])
@require_auth
def get_my_tasks():
    """Get tasks assigned to current user."""
    user = request.current_user

    filters = {}
    if request.args.get("status"):
        filters["status"] = request.args.get("status")
    if request.args.get("priority"):
        filters["priority"] = request.args.get("priority")
    if request.args.get("category"):
        filters["category"] = request.args.get("category")
    if request.args.get("overdue") == "true":
        filters["overdue"] = True

    tasks = task_service.get_my_tasks(user.get("id"), filters)
    return jsonify({"tasks": tasks, "total": len(tasks)})


@tasks_bp.route("/stats", methods=["GET"])
@require_auth
@require_role("compliance_officer")
def get_stats():
    """Get task statistics (compliance_officer+)."""
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    stats = task_service.get_task_stats(institution_id)
    return jsonify({"stats": stats})


@tasks_bp.route("/overdue", methods=["GET"])
@require_auth
@require_role("compliance_officer")
def get_overdue():
    """Get overdue tasks (compliance_officer+)."""
    institution_id = request.args.get("institution_id")
    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    tasks = task_service.get_overdue_tasks(institution_id)
    return jsonify({"tasks": tasks, "total": len(tasks)})


@tasks_bp.route("/<task_id>/comments", methods=["POST"])
@require_auth
def add_comment(task_id: str):
    """Add a comment to a task."""
    data = request.get_json()
    content = data.get("content")

    if not content or not content.strip():
        return jsonify({"error": "content required"}), 400

    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    try:
        user = request.current_user
        comment_id = task_service.add_comment(
            task_id=task_id,
            user_id=user.get("id"),
            user_name=user.get("name", "Unknown"),
            content=content.strip()
        )

        comments = task_service.get_comments(task_id)
        return jsonify({"success": True, "comment_id": comment_id, "comments": comments}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tasks_bp.route("/<task_id>/comments", methods=["GET"])
@require_auth
def get_comments(task_id: str):
    """Get comments for a task."""
    task = task_service.get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    comments = task_service.get_comments(task_id)
    return jsonify({"comments": comments})


@tasks_bp.route("/from-findings", methods=["POST"])
@require_auth
@require_role("compliance_officer")
def create_from_findings():
    """Bulk create tasks from audit findings (compliance_officer+)."""
    data = request.get_json()

    institution_id = data.get("institution_id")
    findings = data.get("findings", [])

    if not institution_id:
        return jsonify({"error": "institution_id required"}), 400

    if not findings:
        return jsonify({"error": "findings required"}), 400

    try:
        assigned_by = request.current_user.get("id")
        task_ids = task_service.create_tasks_from_findings(
            institution_id=institution_id,
            findings=findings,
            assigned_by=assigned_by
        )

        return jsonify({
            "success": True,
            "task_ids": task_ids,
            "count": len(task_ids)
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
