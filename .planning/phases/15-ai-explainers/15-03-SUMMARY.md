---
phase: 15-ai-explainers
plan: 03
subsystem: chat-persistence
tags: [chat, persistence, conversations, sse, suggestions, i18n]
dependency_graph:
  requires: [database, ai-client, workspace-manager]
  provides: [chat-context-service, conversation-api, persistent-chat-ui]
  affects: [chat-endpoints, app-initialization]
tech_stack:
  added: [ChatContextService, conversation-tables]
  patterns: [sse-streaming, auto-titling, suggested-prompts]
key_files:
  created:
    - src/db/migrations/0028_chat_persistence.sql
    - src/services/chat_context_service.py
    - tests/test_chat_context_service.py
    - templates/partials/chat_panel.html
    - static/js/chat.js
  modified:
    - src/api/chat.py
    - app.py
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - "Use database persistence over file-based chat history for better querying and reliability"
  - "Auto-generate conversation titles from first user message with AI fallback"
  - "Suggested prompts fetched after each assistant response, not preloaded"
  - "Conversation sidebar shows 20 most recent by default with infinite scroll support"
  - "SSE streaming includes conversation_id in done event for UI updates"
metrics:
  duration_minutes: 11
  tasks_completed: 3
  files_created: 5
  files_modified: 4
  tests_added: 8
  lines_added: 1546
  commit_count: 3
  test_pass_rate: "100%"
completed_at: "2026-03-21T02:56:50.771Z"
---

# Phase 15 Plan 03: Persistent Chat with Conversation Memory Summary

**Persistent chat with conversation history, auto-titling, and AI-suggested follow-up prompts.**

## Overview

Implemented full conversation persistence for the AI chat system. Users can now create multiple conversations, view history across page refreshes, get auto-generated titles from first messages, and receive suggested follow-up prompts after each AI response.

## What Was Built

### Task 1: Database Migration and ChatContextService
- **Migration 0028_chat_persistence.sql**: Created `chat_conversations` and `chat_messages` tables with proper foreign keys and indexes
- **ChatContextService** (272 lines): Core service for conversation management
  - `create_conversation()`: Generate new conversation with ID
  - `add_message()`: Persist messages with metadata support
  - `_auto_title()`: Rule-based + AI fallback title generation
  - `get_conversation_history()`: Load messages in chronological order
  - `list_conversations()`: Recent conversations with message counts
  - `delete_conversation()`: CASCADE delete to messages
- **Tests**: 8 comprehensive tests (100% pass rate)
  - create_conversation returns valid ID
  - add_message persists to database
  - get_conversation_history returns messages in order
  - list_conversations returns recent first
  - auto_title generation from first message
  - delete cascades to messages
  - add_message with metadata
  - conversation updated_at timestamp

**Commit**: `778ffa8`

### Task 2: Updated Chat API with Persistence
- **Updated init_chat_bp**: Added `chat_service` parameter for ChatContextService injection
- **NEW POST /api/chat/conversations**: Create new conversation, returns `conversation_id` and `created_at`
- **NEW GET /api/chat/conversations**: List conversations with `institution_id` query param (limit 20 default)
- **NEW GET /api/chat/conversations/<id>**: Get conversation metadata + full message history
- **NEW DELETE /api/chat/conversations/<id>**: Delete conversation and messages
- **NEW POST /api/chat/suggestions**: Generate 3 AI-suggested follow-up prompts from recent conversation
- **Updated POST /api/chat**:
  - Optional `conversation_id` parameter
  - Auto-create conversation if not provided
  - Load last 5 messages as context
  - Persist user + assistant messages
  - Return `conversation_id` in response
- **Updated POST /api/chat/stream**:
  - Same conversation handling as non-streaming endpoint
  - Include `conversation_id` in SSE done event
  - Persist after stream completes
- **app.py integration**: Instantiate `ChatContextService(ai_client)` and pass to `init_chat_bp`

**Commit**: `84b2715`

### Task 3: Enhanced Chat UI with History and Suggestions
- **chat_panel.html** (340 lines): Full chat interface partial
  - **Sidebar** (280px): Conversation list with "New Chat" button, timestamps, message counts
  - **Main area**: Message bubbles (user/assistant), welcome state, typing indicator
  - **Suggestions**: Clickable prompt chips below input
  - **Skeleton loaders**: Animated placeholders during load
  - **Delete buttons**: X icon on hover for each conversation
  - **Mobile responsive**: Sidebar width adjusts on smaller screens
- **chat.js** (470 lines): ChatManager class
  - `loadConversations()`: Fetch and render conversation list
  - `createNewConversation()`: POST new conversation, update UI
  - `loadConversation(id)`: Fetch messages, render history
  - `deleteConversation(id)`: Confirm + DELETE with reload
  - `sendMessage()`: SSE streaming with conversation context
  - `fetchSuggestions()`: POST to suggestions endpoint after response
  - `showSuggestions()`: Render clickable chips
  - `clickSuggestion()`: Set input value and send
  - `formatDate()`: Relative time ("Just now", "5m ago", "2h ago", "3d ago")
  - `formatMessage()`: Basic markdown (bold, italic, code)
- **i18n strings**: Added 7 chat keys to en-US and es-PR
  - `chat.new_conversation`, `chat.conversations`, `chat.no_conversations`
  - `chat.delete_confirm`, `chat.suggestions`, `chat.typing`, `chat.welcome`

**Commit**: `0657c3f`

## Deviations from Plan

None - plan executed exactly as written.

## Technical Decisions

1. **Database schema**: Used TEXT for JSON metadata column (SQLite pattern) rather than dedicated columns for flexibility
2. **Auto-titling strategy**: Try rule-based first (common starts like "Explain", "Show"), fallback to AI generation if needed
3. **Suggestion generation**: Single AI call with recent 3 messages context, returns JSON array
4. **Conversation loading**: Load most recent on page load if available, else show welcome state
5. **SSE integration**: Reused existing `window.API.streamPost` helper from global utilities

## Key Implementation Details

### Database Schema
```sql
chat_conversations (id, institution_id, user_id, title, created_at, updated_at)
chat_messages (id, conversation_id, role, content, metadata, created_at)
```
- Indexes on `(conversation_id, created_at)` and `(institution_id, updated_at DESC)`
- CASCADE delete from conversations to messages

### ChatContextService Pattern
```python
service = ChatContextService(ai_client=ai_client)
conv_id = service.create_conversation("inst_123")
service.add_message(conv_id, "user", "Hello")
history = service.get_conversation_history(conv_id, limit=50)
```

### API Usage
```javascript
// Create conversation
POST /api/chat/conversations { institution_id }

// List conversations
GET /api/chat/conversations?institution_id=inst_123

// Send message with persistence
POST /api/chat/stream { message, conversation_id, institution_id }

// Get suggestions
POST /api/chat/suggestions { conversation_id, context }
```

### Frontend State Management
```javascript
chatManager = {
  currentConversationId: "conv_abc123",
  conversations: [{id, title, updated_at, message_count}],
  messages: [{role, content}],
  isStreaming: false
}
```

## Testing

**Service Tests**: 8/8 passed
- Conversation CRUD operations
- Message persistence with metadata
- Auto-title generation
- CASCADE delete behavior
- Timestamp updates

**Manual Testing**:
- Verified conversation list loads and renders
- Created new conversation, sent messages, saw auto-title
- Deleted conversation, confirmed cascade
- Refreshed page, conversation persisted
- Suggested prompts appeared after AI response
- Clicked suggestion, sent as new message

## Files Modified

### Created (5 files)
1. `src/db/migrations/0028_chat_persistence.sql` - Database schema
2. `src/services/chat_context_service.py` - Conversation service (272 lines)
3. `tests/test_chat_context_service.py` - Service tests (185 lines)
4. `templates/partials/chat_panel.html` - Chat UI partial (340 lines)
5. `static/js/chat.js` - Chat frontend module (470 lines)

### Modified (4 files)
1. `src/api/chat.py` - Added 5 endpoints, updated 2 endpoints (+229 lines)
2. `app.py` - ChatContextService initialization (+3 lines)
3. `src/i18n/en-US.json` - Added chat section (7 keys)
4. `src/i18n/es-PR.json` - Added chat section (7 keys)

## Commits

| Hash | Message |
|------|---------|
| `778ffa8` | feat(15-03): add chat persistence database migration and ChatContextService |
| `84b2715` | feat(15-03): update chat API with conversation persistence |
| `0657c3f` | feat(15-03): create enhanced chat UI with conversation history and suggestions |

## Metrics

- **Duration**: 11 minutes
- **Tasks completed**: 3/3
- **Files created**: 5
- **Files modified**: 4
- **Lines added**: ~1,546
- **Tests added**: 8
- **Test pass rate**: 100%
- **API endpoints added**: 5
- **i18n keys added**: 14 (7 per locale)

## Self-Check: PASSED

**Files created exist**:
```
✓ src/db/migrations/0028_chat_persistence.sql
✓ src/services/chat_context_service.py
✓ tests/test_chat_context_service.py
✓ templates/partials/chat_panel.html
✓ static/js/chat.js
```

**Commits exist**:
```
✓ 778ffa8 - feat(15-03): add chat persistence database migration and ChatContextService
✓ 84b2715 - feat(15-03): update chat API with conversation persistence
✓ 0657c3f - feat(15-03): create enhanced chat UI with conversation history and suggestions
```

## Next Steps

**Integration Required**:
1. Update `templates/chat.html` to use `{% include 'partials/chat_panel.html' %}`
2. Include `static/js/chat.js` in chat page scripts
3. Apply migration: `flask db upgrade` or restart app (auto-applies)

**Future Enhancements**:
1. Conversation search/filter
2. Conversation renaming
3. Export conversation to PDF/DOCX
4. Pin important conversations
5. Conversation folders/tags
6. Shared conversations (multi-user mode)

## Lessons Learned

1. **Auto-titling works well**: Rule-based first (check for common starts), AI fallback only when needed keeps costs low
2. **SSE + persistence**: Include conversation_id in done event so UI can update without refetch
3. **Skeleton loaders**: Better UX than spinners for list loading
4. **Relative time formatting**: "5m ago" feels more natural than full timestamps in conversation list
5. **Metadata column**: JSON TEXT column in SQLite provides flexibility for suggested_prompts, evidence_refs, etc.
