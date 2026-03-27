"""Action Plans API blueprint.

Provides REST endpoints for action plan management:
- Create and manage action plans
- Track action items with status and deadlines
- Generate plans from findings
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

from src.core.models import (
    ActionItem,
    ActionItemPriority,
    ActionItemStatus,
    ActionPlan,
    generate_id,
    now_iso,
)

action_plans_bp = Blueprint("action_plans", __name__, url_prefix="/api/institutions/<institution_id>/action-plans")

_workspace_manager = None


def init_action_plans_bp(workspace_manager):
    """Initialize blueprint with dependencies."""
    global _workspace_manager
    _workspace_manager = workspace_manager


def _load_plan(institution_id: str, plan_id: str):
    """Load an action plan from workspace."""
    data = _workspace_manager.load_file(institution_id, f"action_plans/{plan_id}.json")
    if data:
        return ActionPlan.from_dict(data)
    return None


def _save_plan(plan: ActionPlan):
    """Save an action plan to workspace."""
    plan.update_stats()
    _workspace_manager.save_file(
        plan.institution_id,
        f"action_plans/{plan.id}.json",
        plan.to_dict()
    )


@action_plans_bp.route("", methods=["GET"])
def list_plans(institution_id: str):
    """List all action plans for an institution."""
    if not _workspace_manager:
        return jsonify({"error": "Workspace not configured"}), 500

    plans = []
    inst_path = _workspace_manager.get_institution_path(institution_id)
    plans_dir = inst_path / "action_plans"

    if plans_dir.exists():
        for f in plans_dir.glob("plan_*.json"):
            try:
                data = json.loads(f.read_text())
                plans.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "total_items": data.get("total_items", 0),
                    "items_completed": data.get("items_completed", 0),
                    "items_overdue": data.get("items_overdue", 0),
                    "target_completion_date": data.get("target_completion_date"),
                    "created_at": data.get("created_at"),
                })
            except Exception as e:
                logger.debug("Failed to parse action plan %s: %s", f.name, e)
                continue

    return jsonify({"plans": plans})


@action_plans_bp.route("", methods=["POST"])
def create_plan(institution_id: str):
    """Create a new action plan."""
    data = request.get_json() or {}

    name = data.get("name", f"Action Plan {datetime.now().strftime('%Y-%m-%d')}")

    plan = ActionPlan(
        institution_id=institution_id,
        name=name,
        description=data.get("description", ""),
        findings_report_id=data.get("findings_report_id", ""),
        packet_id=data.get("packet_id", ""),
        target_completion_date=data.get("target_completion_date"),
    )

    _save_plan(plan)

    return jsonify({
        "success": True,
        "plan_id": plan.id,
        "name": plan.name,
    }), 201


@action_plans_bp.route("/<plan_id>", methods=["GET"])
def get_plan(institution_id: str, plan_id: str):
    """Get a specific action plan."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    return jsonify(plan.to_dict())


@action_plans_bp.route("/<plan_id>", methods=["PUT"])
def update_plan(institution_id: str, plan_id: str):
    """Update an action plan."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    data = request.get_json() or {}

    if "name" in data:
        plan.name = data["name"]
    if "description" in data:
        plan.description = data["description"]
    if "target_completion_date" in data:
        plan.target_completion_date = data["target_completion_date"]

    _save_plan(plan)

    return jsonify({"success": True, "plan_id": plan.id})


@action_plans_bp.route("/<plan_id>/items", methods=["GET"])
def list_items(institution_id: str, plan_id: str):
    """List action items in a plan."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")

    items = plan.items

    if status_filter:
        items = [i for i in items if i.status.value == status_filter]
    if priority_filter:
        items = [i for i in items if i.priority.value == priority_filter]

    return jsonify({
        "items": [i.to_dict() for i in items],
        "total": len(items),
    })


@action_plans_bp.route("/<plan_id>/items", methods=["POST"])
def create_item(institution_id: str, plan_id: str):
    """Create a new action item."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    data = request.get_json() or {}

    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    item = ActionItem(
        title=data["title"],
        description=data.get("description", ""),
        priority=ActionItemPriority(data.get("priority", "medium")),
        finding_id=data.get("finding_id", ""),
        standard_ref=data.get("standard_ref", ""),
        document_id=data.get("document_id", ""),
        assigned_to=data.get("assigned_to", ""),
        due_date=data.get("due_date"),
    )

    plan.items.append(item)
    _save_plan(plan)

    return jsonify({
        "success": True,
        "item_id": item.id,
        "title": item.title,
    }), 201


@action_plans_bp.route("/<plan_id>/items/<item_id>", methods=["PUT"])
def update_item(institution_id: str, plan_id: str, item_id: str):
    """Update an action item."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    item = next((i for i in plan.items if i.id == item_id), None)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json() or {}

    if "title" in data:
        item.title = data["title"]
    if "description" in data:
        item.description = data["description"]
    if "priority" in data:
        item.priority = ActionItemPriority(data["priority"])
    if "status" in data:
        new_status = ActionItemStatus(data["status"])
        if new_status == ActionItemStatus.IN_PROGRESS and not item.started_at:
            item.started_at = now_iso()
        if new_status == ActionItemStatus.COMPLETED and not item.completed_at:
            item.completed_at = now_iso()
        item.status = new_status
    if "assigned_to" in data:
        item.assigned_to = data["assigned_to"]
    if "due_date" in data:
        item.due_date = data["due_date"]
    if "progress_note" in data:
        item.progress_notes.append(f"{now_iso()[:10]}: {data['progress_note']}")
    if "blocker" in data:
        item.blockers.append(data["blocker"])

    item.updated_at = now_iso()
    _save_plan(plan)

    return jsonify({"success": True, "item": item.to_dict()})


@action_plans_bp.route("/<plan_id>/items/<item_id>", methods=["DELETE"])
def delete_item(institution_id: str, plan_id: str, item_id: str):
    """Delete an action item."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    plan.items = [i for i in plan.items if i.id != item_id]
    _save_plan(plan)

    return jsonify({"success": True})


@action_plans_bp.route("/<plan_id>/generate-from-findings", methods=["POST"])
def generate_from_findings(institution_id: str, plan_id: str):
    """Generate action items from a findings report."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    data = request.get_json() or {}
    findings_report_id = data.get("findings_report_id")

    if not findings_report_id:
        return jsonify({"error": "findings_report_id required"}), 400

    # Load findings report
    report_data = _workspace_manager.load_file(institution_id, f"findings/{findings_report_id}.json")
    if not report_data:
        return jsonify({"error": "Findings report not found"}), 404

    findings = report_data.get("findings", [])
    items_created = 0

    priority_map = {
        "critical": ActionItemPriority.CRITICAL,
        "significant": ActionItemPriority.HIGH,
        "advisory": ActionItemPriority.MEDIUM,
        "informational": ActionItemPriority.LOW,
    }

    for finding in findings:
        if finding.get("status") in ["non_compliant", "partial"]:
            severity = finding.get("severity", "medium")
            item = ActionItem(
                title=f"Address {finding.get('item_number', 'Finding')}",
                description=finding.get("recommendation", finding.get("finding_detail", "")),
                priority=priority_map.get(severity, ActionItemPriority.MEDIUM),
                finding_id=finding.get("id", ""),
                standard_ref=finding.get("item_number", ""),
            )
            plan.items.append(item)
            items_created += 1

    plan.findings_report_id = findings_report_id
    _save_plan(plan)

    return jsonify({
        "success": True,
        "items_created": items_created,
        "total_items": len(plan.items),
    })


@action_plans_bp.route("/<plan_id>/stats", methods=["GET"])
def get_stats(institution_id: str, plan_id: str):
    """Get action plan statistics."""
    plan = _load_plan(institution_id, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    plan.update_stats()

    completion_pct = 0
    if plan.total_items > 0:
        completion_pct = round((plan.items_completed / plan.total_items) * 100)

    return jsonify({
        "total_items": plan.total_items,
        "items_completed": plan.items_completed,
        "items_in_progress": plan.items_in_progress,
        "items_blocked": plan.items_blocked,
        "items_overdue": plan.items_overdue,
        "completion_percentage": completion_pct,
        "by_priority": {
            "critical": sum(1 for i in plan.items if i.priority == ActionItemPriority.CRITICAL),
            "high": sum(1 for i in plan.items if i.priority == ActionItemPriority.HIGH),
            "medium": sum(1 for i in plan.items if i.priority == ActionItemPriority.MEDIUM),
            "low": sum(1 for i in plan.items if i.priority == ActionItemPriority.LOW),
        },
    })
