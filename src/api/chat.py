"""Chat API endpoints with SSE streaming.

Provides endpoints for:
- Conversational chat with the AI assistant
- Streaming responses via Server-Sent Events
- Chat history management
"""

import json
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, Response, stream_with_context
from datetime import datetime

from src.ai.client import AIClient
from src.core.models import ChatMessage


# Create Blueprint
chat_bp = Blueprint('chat', __name__)

# Module-level references (set during initialization)
_workspace_manager = None
_ai_client: Optional[AIClient] = None


def init_chat_bp(workspace_manager, ai_client: AIClient):
    """Initialize the chat blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
        ai_client: AIClient instance for AI interactions.
    """
    global _workspace_manager, _ai_client
    _workspace_manager = workspace_manager
    _ai_client = ai_client
    return chat_bp


@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    """Send a message and get a response (non-streaming).

    Request Body:
        message: User message (required)
        institution_id: Associated institution (optional)
        context: Additional context for the AI (optional)

    Returns:
        JSON with assistant response.
    """
    data = request.get_json() or {}

    message = data.get('message')
    if not message:
        return jsonify({"error": "message is required"}), 400

    institution_id = data.get('institution_id')
    context = data.get('context', '')

    try:
        # Build system prompt with optional context
        system_prompt = _build_system_prompt(institution_id, context)

        # Get response
        response = _ai_client.chat(message, system_prompt=system_prompt)

        # Save to chat history if institution provided
        if institution_id:
            _save_chat_message(institution_id, "user", message)
            _save_chat_message(institution_id, "assistant", response)

        return jsonify({
            "response": response,
            "institution_id": institution_id,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Send a message and stream the response via SSE.

    Request Body:
        message: User message (required)
        institution_id: Associated institution (optional)
        context: Additional context for the AI (optional)

    Returns:
        Server-Sent Events stream with:
        - event: chunk, data: {"type": "chunk", "text": str}
        - event: done, data: {"type": "done", "full_response": str}
        - event: error, data: {"type": "error", "error": str}
    """
    data = request.get_json() or {}

    message = data.get('message')
    if not message:
        return jsonify({"error": "message is required"}), 400

    institution_id = data.get('institution_id')
    context = data.get('context', '')

    def generate():
        """Generator function for SSE stream."""
        try:
            # Build system prompt
            system_prompt = _build_system_prompt(institution_id, context)

            # Stream response
            full_response = []

            for chunk in _ai_client.chat_stream(message, system_prompt=system_prompt):
                full_response.append(chunk)
                event_data = json.dumps({'type': 'chunk', 'text': chunk})
                yield f"event: chunk\ndata: {event_data}\n\n"

            # Combine full response
            full_text = ''.join(full_response)

            # Save to chat history if institution provided
            if institution_id:
                _save_chat_message(institution_id, "user", message)
                _save_chat_message(institution_id, "assistant", full_text)

            # Send completion event
            done_data = json.dumps({
                'type': 'done',
                'full_response': full_text,
            })
            yield f"event: done\ndata: {done_data}\n\n"

        except Exception as e:
            error_data = json.dumps({'type': 'error', 'error': str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@chat_bp.route('/api/chat/generate', methods=['POST'])
def generate():
    """Generate a one-shot response without history.

    Request Body:
        prompt: User prompt (required)
        system_prompt: System instructions (required)
        max_tokens: Optional token limit

    Returns:
        JSON with generated response.
    """
    data = request.get_json() or {}

    prompt = data.get('prompt')
    system_prompt = data.get('system_prompt')

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if not system_prompt:
        return jsonify({"error": "system_prompt is required"}), 400

    max_tokens = data.get('max_tokens')

    try:
        response = _ai_client.generate(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=max_tokens,
        )

        return jsonify({"response": response}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/history/<institution_id>', methods=['GET'])
def get_history(institution_id: str):
    """Get chat history for an institution.

    Query Parameters:
        limit: Max messages to return (default: 50)
        offset: Pagination offset (default: 0)

    Returns:
        JSON list of chat messages.
    """
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        history = _load_chat_history(institution_id, limit, offset)
        return jsonify({
            "institution_id": institution_id,
            "messages": history,
            "limit": limit,
            "offset": offset,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/history/<institution_id>', methods=['DELETE'])
def clear_history(institution_id: str):
    """Clear chat history for an institution.

    Returns:
        JSON with success status.
    """
    try:
        _clear_chat_history(institution_id)
        _ai_client.clear_history()

        return jsonify({
            "success": True,
            "message": "Chat history cleared",
            "institution_id": institution_id,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Helper functions

def _build_system_prompt(institution_id: Optional[str], context: str = "") -> str:
    """Build system prompt with institution context."""
    base_prompt = AIClient.DEFAULT_SYSTEM_PROMPT

    if institution_id and _workspace_manager:
        institution = _workspace_manager.load_institution(institution_id)
        if institution:
            base_prompt += f"""

Current Institution Context:
- Name: {institution.name}
- Accrediting Body: {institution.accrediting_body.value}
- Programs: {len(institution.programs)}
- Documents: {len(institution.documents)}
"""

    if context:
        base_prompt += f"\n\nAdditional Context:\n{context}"

    return base_prompt


def _save_chat_message(institution_id: str, role: str, content: str) -> None:
    """Save a chat message to history."""
    if not _workspace_manager:
        return

    message = ChatMessage(role=role, content=content)

    # Load existing history
    history_path = f"chat_history.json"
    workspace_path = _workspace_manager.get_institution_path(institution_id)
    if not workspace_path:
        return

    history_file = workspace_path / history_path

    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    # Append new message
    history.append(message.to_dict())

    # Save
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def _load_chat_history(
    institution_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list:
    """Load chat history from disk."""
    if not _workspace_manager:
        return []

    workspace_path = _workspace_manager.get_institution_path(institution_id)
    if not workspace_path:
        return []

    history_file = workspace_path / "chat_history.json"

    if not history_file.exists():
        return []

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

        # Apply pagination
        return history[offset:offset + limit]

    except (json.JSONDecodeError, IOError):
        return []


def _clear_chat_history(institution_id: str) -> None:
    """Clear chat history for an institution."""
    if not _workspace_manager:
        return

    workspace_path = _workspace_manager.get_institution_path(institution_id)
    if not workspace_path:
        return

    history_file = workspace_path / "chat_history.json"

    if history_file.exists():
        history_file.unlink()
