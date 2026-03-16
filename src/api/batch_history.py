"""Batch History API endpoints for AccreditAI.

Provides endpoints for:
- Listing batch operations for an institution
- Retrieving batch details and items
- Viewing batch statistics
"""

import json
from typing import Optional
from flask import Blueprint, request, jsonify

from src.services.batch_service import BatchService


# Create Blueprint
batch_history_bp = Blueprint('batch_history', __name__)

# Module-level references (set during initialization)
_workspace_manager = None


def init_batch_history_bp(workspace_manager):
    """Initialize the batch history blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return batch_history_bp


@batch_history_bp.route('/api/institutions/<institution_id>/batches', methods=['GET'])
def list_batches(institution_id: str):
    """List batch operations for an institution.

    Query Parameters:
        limit: Maximum batches to return (default 20)
        offset: Offset for pagination (default 0)
        operation_type: Filter by operation type (optional: audit, remediation)

    Returns:
        JSON list of batch summaries.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    # Get query parameters
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    operation_type = request.args.get('operation_type')

    # Validate
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 20

    # Get batches
    batch_service = BatchService(_workspace_manager)
    batches = batch_service.list_batches(
        institution_id=institution_id,
        limit=limit,
        offset=offset,
        operation_type=operation_type,
    )

    # Get total count
    from src.db.connection import get_conn
    conn = get_conn()
    cursor = conn.cursor()

    if operation_type:
        cursor.execute(
            "SELECT COUNT(*) as total FROM batch_operations WHERE institution_id = ? AND operation_type = ?",
            (institution_id, operation_type)
        )
    else:
        cursor.execute(
            "SELECT COUNT(*) as total FROM batch_operations WHERE institution_id = ?",
            (institution_id,)
        )

    total = cursor.fetchone()['total']

    return jsonify({
        "batches": [batch.to_dict() for batch in batches],
        "total": total,
        "limit": limit,
        "offset": offset,
    }), 200


@batch_history_bp.route('/api/institutions/<institution_id>/batches/<batch_id>', methods=['GET'])
def get_batch(institution_id: str, batch_id: str):
    """Get batch details with items.

    Returns:
        JSON with full batch information including items.
    """
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.get_batch(batch_id)

    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    # Calculate computed fields
    batch_dict = batch.to_dict()

    # Success rate
    if batch.document_count > 0:
        success_rate = round((batch.completed_count / batch.document_count) * 100, 1)
    else:
        success_rate = 0.0

    batch_dict['success_rate'] = success_rate

    # Duration
    if batch.started_at and batch.completed_at:
        from datetime import datetime
        started = datetime.fromisoformat(batch.started_at.replace('Z', '+00:00'))
        completed = datetime.fromisoformat(batch.completed_at.replace('Z', '+00:00'))
        duration_ms = int((completed - started).total_seconds() * 1000)
        batch_dict['duration_ms'] = duration_ms
    else:
        batch_dict['duration_ms'] = 0

    # Total tokens
    total_input = sum(item.input_tokens for item in batch.items)
    total_output = sum(item.output_tokens for item in batch.items)
    batch_dict['total_input_tokens'] = total_input
    batch_dict['total_output_tokens'] = total_output

    return jsonify(batch_dict), 200


@batch_history_bp.route('/api/institutions/<institution_id>/batches/<batch_id>/items', methods=['GET'])
def get_batch_items(institution_id: str, batch_id: str):
    """Get batch items with optional status filter.

    Query Parameters:
        status: Filter by status (optional: pending, running, completed, failed)

    Returns:
        JSON list of batch items.
    """
    batch_service = BatchService(_workspace_manager)
    batch = batch_service.get_batch(batch_id)

    if not batch:
        return jsonify({"error": "Batch not found"}), 404

    if batch.institution_id != institution_id:
        return jsonify({"error": "Batch does not belong to this institution"}), 403

    # Get status filter
    status_filter = request.args.get('status')

    # Filter items
    items = batch.items
    if status_filter:
        items = [item for item in items if item.status == status_filter]

    return jsonify({
        "batch_id": batch_id,
        "total_items": len(batch.items),
        "filtered_items": len(items),
        "filter": status_filter,
        "items": [item.to_dict() for item in items],
    }), 200


@batch_history_bp.route('/api/institutions/<institution_id>/batches/stats', methods=['GET'])
def get_batch_stats(institution_id: str):
    """Get aggregate batch statistics for institution.

    Returns:
        JSON with aggregated statistics.
    """
    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    from src.db.connection import get_conn
    conn = get_conn()
    cursor = conn.cursor()

    # Total batches
    cursor.execute(
        "SELECT COUNT(*) as total FROM batch_operations WHERE institution_id = ?",
        (institution_id,)
    )
    total_batches = cursor.fetchone()['total']

    # Total documents processed
    cursor.execute(
        """
        SELECT SUM(completed_count + failed_count) as total
        FROM batch_operations
        WHERE institution_id = ? AND status = 'completed'
        """,
        (institution_id,)
    )
    total_docs_processed = cursor.fetchone()['total'] or 0

    # Total cost
    cursor.execute(
        """
        SELECT SUM(actual_cost) as total
        FROM batch_operations
        WHERE institution_id = ? AND actual_cost IS NOT NULL
        """,
        (institution_id,)
    )
    total_cost = cursor.fetchone()['total'] or 0.0

    # Average success rate
    cursor.execute(
        """
        SELECT AVG(CAST(completed_count AS FLOAT) / NULLIF(document_count, 0)) as avg_rate
        FROM batch_operations
        WHERE institution_id = ? AND status = 'completed' AND document_count > 0
        """,
        (institution_id,)
    )
    avg_success_rate_raw = cursor.fetchone()['avg_rate']
    avg_success_rate = round(avg_success_rate_raw * 100, 1) if avg_success_rate_raw else 0.0

    # By operation type
    cursor.execute(
        """
        SELECT operation_type, COUNT(*) as count
        FROM batch_operations
        WHERE institution_id = ?
        GROUP BY operation_type
        """,
        (institution_id,)
    )
    by_operation_type = {row['operation_type']: row['count'] for row in cursor.fetchall()}

    return jsonify({
        "total_batches": total_batches,
        "total_documents_processed": total_docs_processed,
        "total_cost": round(total_cost, 2),
        "avg_success_rate": avg_success_rate,
        "by_operation_type": by_operation_type,
    }), 200
