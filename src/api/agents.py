"""Agent API endpoints for AccreditAI.

Provides endpoints for:
- Starting accreditation workflows
- Monitoring agent sessions via SSE
- Managing checkpoints (approve/reject)
- Viewing session history and stats
"""

import json
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, Response, stream_with_context
from datetime import datetime

from src.agents import OrchestratorAgent, AgentType
from src.core.models import AgentSession, SessionStatus


# Create Blueprint
agents_bp = Blueprint('agents', __name__)

# Module-level references (set during initialization)
_workspace_manager = None
_active_sessions: Dict[str, AgentSession] = {}


def init_agents_bp(workspace_manager):
    """Initialize the agents blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
    """
    global _workspace_manager
    _workspace_manager = workspace_manager
    return agents_bp


@agents_bp.route('/api/agents/start-workflow', methods=['POST'])
def start_workflow():
    """Start an accreditation preparation workflow.

    Request Body:
        institution_id: Institution ID (required)
        accrediting_body: Target accrediting body (optional, uses institution default)

    Returns:
        JSON with session ID and stream URL.
    """
    data = request.get_json() or {}

    institution_id = data.get('institution_id')
    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    # Verify institution exists
    institution = _workspace_manager.load_institution(institution_id)
    if not institution:
        return jsonify({"error": "Institution not found"}), 404

    accrediting_body = data.get('accrediting_body', institution.accrediting_body.value)

    # Create session
    session = AgentSession(
        agent_type="orchestrator",
        institution_id=institution_id,
    )

    # Store in active sessions
    _active_sessions[session.id] = session

    # Save initial session
    _workspace_manager.save_agent_session(institution_id, session.to_dict())

    return jsonify({
        "session_id": session.id,
        "status": session.status.value,
        "institution_id": institution_id,
        "accrediting_body": accrediting_body,
        "stream_url": f"/api/agents/sessions/{session.id}/stream",
        "message": "Workflow session created",
    }), 201


@agents_bp.route('/api/agents/sessions/<session_id>/stream', methods=['GET'])
def stream_session(session_id: str):
    """Stream session progress via Server-Sent Events.

    Query Parameters:
        resume: Set to 'true' to resume an existing session

    Returns:
        SSE stream of progress updates.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    resume = request.args.get('resume', 'false').lower() == 'true'

    def generate():
        """Generate SSE events."""
        try:
            # Create orchestrator
            orchestrator = OrchestratorAgent(
                session=session,
                workspace_manager=_workspace_manager,
                on_update=lambda s: _on_session_update(s),
            )

            # Run or resume workflow
            if resume:
                for update in orchestrator.run_all_tasks():
                    yield f"data: {json.dumps(update)}\n\n"
                    _save_session(session)
            else:
                for update in orchestrator.run_workflow(
                    institution_id=session.institution_id,
                    accrediting_body=session.metadata.get('accrediting_body', 'HLC'),
                ):
                    yield f"data: {json.dumps(update)}\n\n"
                    _save_session(session)

            # Final save
            _save_session(session)

            yield f"data: {json.dumps({'type': 'stream_complete', 'session_id': session.id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@agents_bp.route('/api/agents/sessions', methods=['GET'])
def list_sessions():
    """List all agent sessions.

    Query Parameters:
        institution_id: Filter by institution (optional)
        status: Filter by status (optional)

    Returns:
        JSON list of session summaries.
    """
    institution_id = request.args.get('institution_id')
    status_filter = request.args.get('status')

    sessions = []

    # Include active sessions
    for session in _active_sessions.values():
        if institution_id and session.institution_id != institution_id:
            continue
        if status_filter and session.status.value != status_filter:
            continue
        sessions.append(_session_summary(session))

    return jsonify(sessions), 200


@agents_bp.route('/api/agents/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get detailed session information.

    Returns:
        JSON with full session details.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict()), 200


@agents_bp.route('/api/agents/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a session.

    Returns:
        JSON with success status.
    """
    if session_id not in _active_sessions:
        return jsonify({"error": "Session not found"}), 404

    session = _active_sessions.pop(session_id)

    return jsonify({
        "success": True,
        "message": "Session deleted",
        "session_id": session_id,
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/checkpoints', methods=['GET'])
def list_checkpoints(session_id: str):
    """List checkpoints for a session.

    Returns:
        JSON list of checkpoints.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    checkpoints = [c.to_dict() for c in session.checkpoints]
    return jsonify(checkpoints), 200


@agents_bp.route('/api/agents/sessions/<session_id>/checkpoints/<checkpoint_id>/approve', methods=['POST'])
def approve_checkpoint(session_id: str, checkpoint_id: str):
    """Approve a checkpoint and allow workflow to continue.

    Request Body:
        feedback: Optional feedback (string)

    Returns:
        JSON with updated session status.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Find checkpoint
    checkpoint = None
    for cp in session.checkpoints:
        if cp.id == checkpoint_id:
            checkpoint = cp
            break

    if not checkpoint:
        return jsonify({"error": "Checkpoint not found"}), 404

    if checkpoint.status != "pending":
        return jsonify({"error": f"Checkpoint already {checkpoint.status}"}), 400

    # Update checkpoint
    data = request.get_json() or {}
    checkpoint.status = "approved"
    checkpoint.feedback = data.get('feedback', '')
    checkpoint.resolved_at = datetime.now().isoformat()

    # Update session status
    session.status = SessionStatus.RUNNING

    _save_session(session)

    return jsonify({
        "success": True,
        "checkpoint_id": checkpoint_id,
        "status": "approved",
        "session_status": session.status.value,
        "message": "Checkpoint approved. Resume via stream endpoint with resume=true.",
        "resume_url": f"/api/agents/sessions/{session_id}/stream?resume=true",
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/checkpoints/<checkpoint_id>/reject', methods=['POST'])
def reject_checkpoint(session_id: str, checkpoint_id: str):
    """Reject a checkpoint and cancel the workflow.

    Request Body:
        feedback: Rejection reason (required)

    Returns:
        JSON with updated session status.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Find checkpoint
    checkpoint = None
    for cp in session.checkpoints:
        if cp.id == checkpoint_id:
            checkpoint = cp
            break

    if not checkpoint:
        return jsonify({"error": "Checkpoint not found"}), 404

    if checkpoint.status != "pending":
        return jsonify({"error": f"Checkpoint already {checkpoint.status}"}), 400

    data = request.get_json() or {}
    feedback = data.get('feedback')
    if not feedback:
        return jsonify({"error": "feedback is required for rejection"}), 400

    # Update checkpoint
    checkpoint.status = "rejected"
    checkpoint.feedback = feedback
    checkpoint.resolved_at = datetime.now().isoformat()

    # Cancel session
    session.status = SessionStatus.CANCELLED
    session.completed_at = datetime.now().isoformat()

    _save_session(session)

    return jsonify({
        "success": True,
        "checkpoint_id": checkpoint_id,
        "status": "rejected",
        "session_status": session.status.value,
        "message": "Checkpoint rejected. Workflow cancelled.",
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/cancel', methods=['POST'])
def cancel_session(session_id: str):
    """Cancel a running session.

    Returns:
        JSON with updated session status.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    terminal_states = (SessionStatus.COMPLETED, SessionStatus.CANCELLED, SessionStatus.FAILED)
    if session.status in terminal_states:
        return jsonify({
            "error": f"Session already in terminal state: {session.status.value}"
        }), 400

    session.status = SessionStatus.CANCELLED
    session.completed_at = datetime.now().isoformat()

    _save_session(session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "status": session.status.value,
        "message": "Session cancelled.",
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """Pause a running session.

    Returns:
        JSON with updated session status.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    if session.status != SessionStatus.RUNNING:
        return jsonify({
            "error": f"Cannot pause session in state: {session.status.value}"
        }), 400

    session.status = SessionStatus.PAUSED
    _save_session(session)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "status": session.status.value,
        "message": "Session paused.",
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """Resume a paused or waiting session.

    Returns:
        JSON with stream URL to continue execution.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    resumable_states = (SessionStatus.PAUSED, SessionStatus.WAITING_FOR_HUMAN)
    if session.status not in resumable_states:
        return jsonify({
            "error": f"Cannot resume session in state: {session.status.value}"
        }), 400

    return jsonify({
        "success": True,
        "session_id": session_id,
        "stream_url": f"/api/agents/sessions/{session_id}/stream?resume=true",
        "message": "Ready to resume. Connect to stream_url.",
    }), 200


@agents_bp.route('/api/agents/sessions/<session_id>/stats', methods=['GET'])
def get_session_stats(session_id: str):
    """Get execution statistics for a session.

    Returns:
        JSON with token usage, API calls, timing, etc.
    """
    session = _active_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Calculate timing
    duration_seconds = None
    if session.started_at and session.completed_at:
        start = datetime.fromisoformat(session.started_at)
        end = datetime.fromisoformat(session.completed_at)
        duration_seconds = (end - start).total_seconds()

    # Task stats
    tasks_by_status = {}
    for task in session.tasks:
        status = task.status
        tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

    # Tool call stats
    tools_used = {}
    for tc in session.tool_calls:
        name = tc.tool_name
        tools_used[name] = tools_used.get(name, 0) + 1

    return jsonify({
        "session_id": session_id,
        "status": session.status.value,
        "tokens": {
            "input": session.total_input_tokens,
            "output": session.total_output_tokens,
            "total": session.total_input_tokens + session.total_output_tokens,
        },
        "api_calls": session.total_api_calls,
        "duration_seconds": duration_seconds,
        "tasks": {
            "total": len(session.tasks),
            "by_status": tasks_by_status,
        },
        "tool_calls": {
            "total": len(session.tool_calls),
            "by_tool": tools_used,
        },
        "checkpoints": {
            "total": len(session.checkpoints),
            "pending": len([c for c in session.checkpoints if c.status == "pending"]),
            "approved": len([c for c in session.checkpoints if c.status == "approved"]),
            "rejected": len([c for c in session.checkpoints if c.status == "rejected"]),
        },
        "errors": len(session.errors),
    }), 200


# Helper functions

def _on_session_update(session: AgentSession) -> None:
    """Handle session update callback."""
    _active_sessions[session.id] = session


def _save_session(session: AgentSession) -> None:
    """Save session to disk."""
    if _workspace_manager and session.institution_id:
        _workspace_manager.save_agent_session(
            session.institution_id,
            session.to_dict()
        )


def _session_summary(session: AgentSession) -> Dict[str, Any]:
    """Create a summary dict for session listing."""
    return {
        "id": session.id,
        "agent_type": session.agent_type,
        "institution_id": session.institution_id,
        "status": session.status.value,
        "created_at": session.created_at,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "task_count": len(session.tasks),
        "checkpoint_count": len(session.checkpoints),
        "pending_checkpoints": len([c for c in session.checkpoints if c.status == "pending"]),
    }
