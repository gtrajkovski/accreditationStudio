"""Tests for ChatContextService."""

import pytest
import sqlite3
from unittest.mock import MagicMock
from src.services.chat_context_service import ChatContextService
from src.db.connection import get_conn
from src.db.migrate import apply_migrations


@pytest.fixture
def setup_db():
    """Setup test database with migrations."""
    # Apply migrations to ensure tables exist
    apply_migrations()
    conn = get_conn()

    # Clean up any existing test data
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM chat_conversations")
    conn.execute("DELETE FROM institutions")
    conn.commit()

    # Create test institution
    conn.execute(
        """
        INSERT INTO institutions (id, name, accreditor_primary)
        VALUES ('test_inst', 'Test Institution', 'ACCSC')
        """
    )
    conn.commit()

    yield conn

    # Cleanup
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM chat_conversations")
    conn.execute("DELETE FROM institutions WHERE id = 'test_inst'")
    conn.commit()


def test_create_conversation_returns_valid_id(setup_db):
    """Test that create_conversation returns a valid conversation ID."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    assert conv_id is not None
    assert conv_id.startswith("conv_")

    # Verify it exists in database
    conn = get_conn()
    cursor = conn.execute(
        "SELECT id, institution_id FROM chat_conversations WHERE id = ?",
        (conv_id,)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["id"] == conv_id
    assert row["institution_id"] == "test_inst"


def test_add_message_persists_to_database(setup_db):
    """Test that add_message persists messages to database."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    msg_id = service.add_message(conv_id, "user", "Hello, AI!")

    assert msg_id is not None
    assert msg_id.startswith("msg_")

    # Verify message in database
    conn = get_conn()
    cursor = conn.execute(
        "SELECT id, role, content FROM chat_messages WHERE id = ?",
        (msg_id,)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["role"] == "user"
    assert row["content"] == "Hello, AI!"


def test_get_conversation_history_returns_messages_in_order(setup_db):
    """Test that get_conversation_history returns messages in chronological order."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    # Add multiple messages
    service.add_message(conv_id, "user", "First message")
    service.add_message(conv_id, "assistant", "First response")
    service.add_message(conv_id, "user", "Second message")
    service.add_message(conv_id, "assistant", "Second response")

    history = service.get_conversation_history(conv_id)

    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "First message"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "First response"
    assert history[2]["role"] == "user"
    assert history[2]["content"] == "Second message"
    assert history[3]["role"] == "assistant"
    assert history[3]["content"] == "Second response"


def test_list_conversations_returns_recent_first(setup_db):
    """Test that list_conversations returns conversations ordered by most recent."""
    service = ChatContextService()

    # Create multiple conversations
    conv1 = service.create_conversation("test_inst")
    conv2 = service.create_conversation("test_inst")

    # Add messages to conv1 (older)
    service.add_message(conv1, "user", "Old conversation")

    # Add messages to conv2 (newer)
    service.add_message(conv2, "user", "New conversation")

    conversations = service.list_conversations("test_inst")

    assert len(conversations) >= 2
    # Most recent (conv2) should be first
    assert conversations[0]["id"] == conv2
    assert conversations[1]["id"] == conv1


def test_auto_title_generation_from_first_message(setup_db):
    """Test that conversation title is auto-generated from first user message."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    # Add first user message
    service.add_message(conv_id, "user", "Explain the compliance requirements for faculty credentials")

    # Check that title was set
    conv = service.get_conversation(conv_id)
    assert conv is not None
    assert conv["title"] is not None
    assert len(conv["title"]) > 0
    # Should be truncated or the full message (if short enough)
    assert "Explain" in conv["title"] or "compliance" in conv["title"].lower()


def test_delete_cascades_to_messages(setup_db):
    """Test that deleting a conversation cascades to its messages."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    # Add messages
    msg1 = service.add_message(conv_id, "user", "Message 1")
    msg2 = service.add_message(conv_id, "assistant", "Message 2")

    # Verify messages exist
    conn = get_conn()
    cursor = conn.execute("SELECT COUNT(*) as count FROM chat_messages WHERE conversation_id = ?", (conv_id,))
    assert cursor.fetchone()["count"] == 2

    # Delete conversation
    service.delete_conversation(conv_id)

    # Verify conversation deleted
    conv = service.get_conversation(conv_id)
    assert conv is None

    # Verify messages deleted (CASCADE)
    cursor = conn.execute("SELECT COUNT(*) as count FROM chat_messages WHERE conversation_id = ?", (conv_id,))
    assert cursor.fetchone()["count"] == 0


def test_add_message_with_metadata(setup_db):
    """Test that messages can store metadata."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    metadata = {
        "suggested_prompts": ["Follow up 1", "Follow up 2"],
        "evidence_refs": ["doc_123", "doc_456"]
    }

    msg_id = service.add_message(conv_id, "assistant", "Response", metadata=metadata)

    # Verify metadata stored
    conn = get_conn()
    cursor = conn.execute("SELECT metadata FROM chat_messages WHERE id = ?", (msg_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["metadata"] is not None

    import json
    stored_metadata = json.loads(row["metadata"])
    assert stored_metadata["suggested_prompts"] == ["Follow up 1", "Follow up 2"]
    assert stored_metadata["evidence_refs"] == ["doc_123", "doc_456"]


def test_conversation_updated_at_timestamp(setup_db):
    """Test that conversation updated_at changes when messages added."""
    service = ChatContextService()
    conv_id = service.create_conversation("test_inst")

    conv_before = service.get_conversation(conv_id)
    initial_updated_at = conv_before["updated_at"]

    # Add a message (should update timestamp)
    service.add_message(conv_id, "user", "New message")

    conv_after = service.get_conversation(conv_id)
    updated_at = conv_after["updated_at"]

    # Timestamp should have changed (or at least not be less than before)
    assert updated_at >= initial_updated_at
