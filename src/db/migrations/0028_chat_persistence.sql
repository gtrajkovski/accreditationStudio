-- Migration: Chat persistence with conversation management
-- Created: 2026-03-20
-- Description: Adds chat_conversations and chat_messages tables for persistent chat

-- Conversations table
CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    user_id TEXT,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

-- Messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON for suggested prompts, evidence_refs, etc.
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
    ON chat_messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_institution
    ON chat_conversations(institution_id, updated_at DESC);
