"""Chat Context Service for conversation persistence and management.

Provides functionality for:
- Creating and managing chat conversations
- Persisting messages with metadata
- Auto-generating conversation titles
- Retrieving conversation history
"""

import json
import sqlite3
from typing import List, Dict, Optional, Any
from src.db.connection import get_conn
from src.core.models import generate_id, now_iso


class ChatContextService:
    """Service for managing persistent chat conversations."""

    def __init__(self, ai_client=None):
        """Initialize the service.

        Args:
            ai_client: Optional AIClient instance for title generation.
        """
        self.ai_client = ai_client

    def create_conversation(
        self,
        institution_id: str,
        user_id: Optional[str] = None
    ) -> str:
        """Create a new conversation.

        Args:
            institution_id: ID of the associated institution.
            user_id: Optional user ID (for multi-user support).

        Returns:
            The newly created conversation ID.
        """
        conn = get_conn()
        conv_id = generate_id("conv")
        now = now_iso()

        conn.execute(
            """
            INSERT INTO chat_conversations
            (id, institution_id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, institution_id, user_id, None, now, now)
        )
        conn.commit()

        return conv_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a message to a conversation.

        Args:
            conversation_id: ID of the conversation.
            role: Message role ('user', 'assistant', 'system').
            content: Message content.
            metadata: Optional metadata dict (suggested prompts, evidence refs, etc.).

        Returns:
            The newly created message ID.
        """
        conn = get_conn()
        msg_id = generate_id("msg")
        now = now_iso()

        # Convert metadata to JSON if provided
        metadata_json = json.dumps(metadata) if metadata else None

        conn.execute(
            """
            INSERT INTO chat_messages
            (id, conversation_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (msg_id, conversation_id, role, content, metadata_json, now)
        )

        # Update conversation timestamp
        conn.execute(
            """
            UPDATE chat_conversations
            SET updated_at = ?
            WHERE id = ?
            """,
            (now, conversation_id)
        )

        conn.commit()

        # Auto-title if this is the first user message
        if role == "user":
            conv = self.get_conversation(conversation_id)
            if conv and not conv.get("title"):
                self._auto_title(conversation_id, content)

        return msg_id

    def _auto_title(self, conversation_id: str, first_message: str) -> None:
        """Auto-generate a conversation title from the first message.

        Args:
            conversation_id: ID of the conversation.
            first_message: The first user message.
        """
        # Simple rule-based title generation
        title = first_message.strip()

        # Truncate to 50 chars
        if len(title) > 50:
            title = title[:47] + "..."

        # If starts with common patterns, use as-is
        common_starts = ["Explain", "Show", "Find", "What", "How", "Why", "When", "Where"]
        if not any(title.startswith(start) for start in common_starts):
            # Try AI generation if client available
            if self.ai_client:
                try:
                    system_prompt = "Generate a short title (under 10 words) for this conversation. Return ONLY the title, no quotes or explanation."
                    ai_title = self.ai_client.generate(
                        system_prompt=system_prompt,
                        user_prompt=f"First message: {first_message[:200]}",
                        max_tokens=20
                    )
                    if ai_title and len(ai_title) < 60:
                        title = ai_title.strip().strip('"').strip("'")
                except Exception:
                    # Fall back to truncated message
                    pass

        # Update conversation title
        conn = get_conn()
        conn.execute(
            """
            UPDATE chat_conversations
            SET title = ?
            WHERE id = ?
            """,
            (title, conversation_id)
        )
        conn.commit()

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> List[Dict[str, str]]:
        """Get conversation message history.

        Args:
            conversation_id: ID of the conversation.
            limit: Maximum number of messages to return (default 50).

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        conn = get_conn()
        cursor = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (conversation_id, limit)
        )

        messages = []
        for row in cursor.fetchall():
            messages.append({
                "role": row["role"],
                "content": row["content"]
            })

        return messages

    def list_conversations(
        self,
        institution_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent conversations for an institution.

        Args:
            institution_id: ID of the institution.
            limit: Maximum number of conversations to return (default 20).

        Returns:
            List of conversation dicts with id, title, updated_at, message_count.
        """
        conn = get_conn()
        cursor = conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.updated_at,
                c.created_at,
                COUNT(m.id) as message_count
            FROM chat_conversations c
            LEFT JOIN chat_messages m ON c.id = m.conversation_id
            WHERE c.institution_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (institution_id, limit)
        )

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                "id": row["id"],
                "title": row["title"] or "New Conversation",
                "updated_at": row["updated_at"],
                "created_at": row["created_at"],
                "message_count": row["message_count"]
            })

        return conversations

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation metadata.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Conversation dict or None if not found.
        """
        conn = get_conn()
        cursor = conn.execute(
            """
            SELECT id, institution_id, user_id, title, created_at, updated_at
            FROM chat_conversations
            WHERE id = ?
            """,
            (conversation_id,)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "institution_id": row["institution_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: ID of the conversation to delete.
        """
        conn = get_conn()
        # CASCADE delete handles messages automatically
        conn.execute(
            "DELETE FROM chat_conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
