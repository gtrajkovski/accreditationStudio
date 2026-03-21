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
from src.services.chat_context_service import ChatContextService


# Create Blueprint
chat_bp = Blueprint('chat', __name__)

# Module-level references (set during initialization)
_workspace_manager = None
_ai_client: Optional[AIClient] = None
_chat_service: Optional[ChatContextService] = None


def init_chat_bp(workspace_manager, ai_client: AIClient, chat_service: ChatContextService = None):
    """Initialize the chat blueprint with dependencies.

    Args:
        workspace_manager: WorkspaceManager instance for persistence.
        ai_client: AIClient instance for AI interactions.
        chat_service: ChatContextService instance for conversation management.
    """
    global _workspace_manager, _ai_client, _chat_service
    _workspace_manager = workspace_manager
    _ai_client = ai_client
    _chat_service = chat_service
    return chat_bp


@chat_bp.route('/api/chat/conversations', methods=['POST'])
def create_conversation():
    """Create a new conversation.

    Request Body:
        institution_id: Institution ID (required)

    Returns:
        JSON with conversation_id and created_at.
    """
    if not _chat_service:
        return jsonify({"error": "Chat service not initialized"}), 503

    data = request.get_json() or {}
    institution_id = data.get('institution_id')

    if not institution_id:
        return jsonify({"error": "institution_id is required"}), 400

    try:
        conversation_id = _chat_service.create_conversation(institution_id)
        conv = _chat_service.get_conversation(conversation_id)

        return jsonify({
            "conversation_id": conversation_id,
            "created_at": conv["created_at"] if conv else None
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/conversations', methods=['GET'])
def list_conversations():
    """List conversations for an institution.

    Query Parameters:
        institution_id: Institution ID (required)
        limit: Max conversations to return (default: 20)

    Returns:
        JSON list of conversations with id, title, updated_at, message_count.
    """
    if not _chat_service:
        return jsonify({"error": "Chat service not initialized"}), 503

    institution_id = request.args.get('institution_id')
    if not institution_id:
        return jsonify({"error": "institution_id query parameter is required"}), 400

    limit = request.args.get('limit', 20, type=int)

    try:
        conversations = _chat_service.list_conversations(institution_id, limit)
        return jsonify({"conversations": conversations}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id: str):
    """Get conversation details with message history.

    Returns:
        JSON with conversation metadata and messages.
    """
    if not _chat_service:
        return jsonify({"error": "Chat service not initialized"}), 503

    try:
        conv = _chat_service.get_conversation(conversation_id)
        if not conv:
            return jsonify({"error": "Conversation not found"}), 404

        messages = _chat_service.get_conversation_history(conversation_id)

        return jsonify({
            "conversation": conv,
            "messages": messages
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages.

    Returns:
        JSON with success status.
    """
    if not _chat_service:
        return jsonify({"error": "Chat service not initialized"}), 503

    try:
        _chat_service.delete_conversation(conversation_id)
        return jsonify({"success": True, "message": "Conversation deleted"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat/suggestions', methods=['POST'])
def generate_suggestions():
    """Generate suggested follow-up prompts.

    Request Body:
        conversation_id: Conversation ID (optional)
        context: Additional context (optional)

    Returns:
        JSON with list of suggested prompts.
    """
    if not _ai_client:
        return jsonify({"error": "AI client not initialized"}), 503

    data = request.get_json() or {}
    conversation_id = data.get('conversation_id')
    context = data.get('context', '')

    try:
        # Load recent messages if conversation provided
        recent_messages = []
        if conversation_id and _chat_service:
            history = _chat_service.get_conversation_history(conversation_id, limit=5)
            recent_messages = history[-3:] if len(history) > 0 else []

        # Build prompt for suggestion generation
        system_prompt = """Generate 3 suggested follow-up questions or prompts based on the conversation.
Focus on:
1. Drilling deeper into the last topic
2. Related compliance topics
3. Next practical steps

Return ONLY a JSON array of strings, no explanation."""

        context_text = context if context else "No additional context."
        if recent_messages:
            msgs_text = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in recent_messages])
            user_prompt = f"Recent conversation:\n{msgs_text}\n\nContext: {context_text}"
        else:
            user_prompt = f"Context: {context_text}"

        response = _ai_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=150
        )

        # Parse JSON response
        import json
        try:
            suggestions = json.loads(response.strip())
            if not isinstance(suggestions, list):
                suggestions = ["Tell me more", "What are the requirements?", "Show me an example"]
        except json.JSONDecodeError:
            suggestions = ["Tell me more", "What are the requirements?", "Show me an example"]

        return jsonify({"suggestions": suggestions}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/api/chat', methods=['POST'])
def chat():
    """Send a message and get a response (non-streaming).

    Request Body:
        message: User message (required)
        institution_id: Associated institution (optional)
        conversation_id: Conversation ID (optional)
        context: Additional context for the AI (optional)

    Returns:
        JSON with assistant response and conversation_id.
    """
    data = request.get_json() or {}

    message = data.get('message')
    if not message:
        return jsonify({"error": "message is required"}), 400

    institution_id = data.get('institution_id')
    conversation_id = data.get('conversation_id')
    context = data.get('context', '')

    try:
        # Create conversation if needed
        if institution_id and _chat_service and not conversation_id:
            conversation_id = _chat_service.create_conversation(institution_id)

        # Load conversation history if available
        history_context = ""
        if conversation_id and _chat_service:
            history = _chat_service.get_conversation_history(conversation_id, limit=10)
            if history:
                history_context = "\n\nRecent conversation:\n" + "\n".join(
                    [f"{m['role']}: {m['content']}" for m in history[-5:]]
                )

        # Build system prompt with optional context
        system_prompt = _build_system_prompt(institution_id, context + history_context)

        # Get response
        response = _ai_client.chat(message, system_prompt=system_prompt)

        # Save messages to conversation
        if conversation_id and _chat_service:
            _chat_service.add_message(conversation_id, "user", message)
            _chat_service.add_message(conversation_id, "assistant", response)
        elif institution_id:
            # Legacy file-based storage
            _save_chat_message(institution_id, "user", message)
            _save_chat_message(institution_id, "assistant", response)

        return jsonify({
            "response": response,
            "conversation_id": conversation_id,
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
        conversation_id: Conversation ID (optional)
        context: Additional context for the AI (optional)

    Returns:
        Server-Sent Events stream with:
        - event: chunk, data: {"type": "chunk", "text": str}
        - event: done, data: {"type": "done", "full_response": str, "conversation_id": str}
        - event: error, data: {"type": "error", "error": str}
    """
    data = request.get_json() or {}

    message = data.get('message')
    if not message:
        return jsonify({"error": "message is required"}), 400

    institution_id = data.get('institution_id')
    conversation_id = data.get('conversation_id')
    context = data.get('context', '')

    def generate():
        """Generator function for SSE stream."""
        nonlocal conversation_id
        try:
            # Create conversation if needed
            if institution_id and _chat_service and not conversation_id:
                conversation_id = _chat_service.create_conversation(institution_id)

            # Load conversation history if available
            history_context = ""
            if conversation_id and _chat_service:
                history = _chat_service.get_conversation_history(conversation_id, limit=10)
                if history:
                    history_context = "\n\nRecent conversation:\n" + "\n".join(
                        [f"{m['role']}: {m['content']}" for m in history[-5:]]
                    )

            # Build system prompt
            system_prompt = _build_system_prompt(institution_id, context + history_context)

            # Stream response
            full_response = []

            for chunk in _ai_client.chat_stream(message, system_prompt=system_prompt):
                full_response.append(chunk)
                event_data = json.dumps({'type': 'chunk', 'text': chunk})
                yield f"event: chunk\ndata: {event_data}\n\n"

            # Combine full response
            full_text = ''.join(full_response)

            # Save messages to conversation
            if conversation_id and _chat_service:
                _chat_service.add_message(conversation_id, "user", message)
                _chat_service.add_message(conversation_id, "assistant", full_text)
            elif institution_id:
                # Legacy file-based storage
                _save_chat_message(institution_id, "user", message)
                _save_chat_message(institution_id, "assistant", full_text)

            # Send completion event
            done_data = json.dumps({
                'type': 'done',
                'full_response': full_text,
                'conversation_id': conversation_id,
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
