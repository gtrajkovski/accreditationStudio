/**
 * Chat Module - Persistent chat with conversation management
 *
 * Features:
 * - Conversation list with create/delete
 * - Message persistence across sessions
 * - Auto-title generation
 * - Suggested follow-up prompts
 * - SSE streaming
 */

class ChatManager {
    constructor() {
        this.currentConversationId = null;
        this.conversations = [];
        this.messages = [];
        this.isStreaming = false;
        this.institutionId = null;

        // DOM elements
        this.elements = {
            sidebar: document.getElementById('chat-sidebar'),
            conversationList: document.getElementById('conversation-list'),
            newChatBtn: document.getElementById('new-chat-btn'),
            messagesContainer: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendBtn: document.getElementById('send-btn'),
            chatWelcome: document.getElementById('chat-welcome'),
            suggestionsContainer: document.getElementById('chat-suggestions'),
            suggestionsChips: document.getElementById('suggestions-chips')
        };

        this.init();
    }

    init() {
        // Get institution ID from page context
        this.institutionId = this.getInstitutionId();

        // Bind event listeners
        this.elements.newChatBtn.addEventListener('click', () => this.createNewConversation());
        this.elements.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

        // Load conversations
        if (this.institutionId) {
            this.loadConversations();
        } else {
            this.showWelcome();
        }
    }

    getInstitutionId() {
        // Try to get from URL params, page data, or localStorage
        const urlParams = new URLSearchParams(window.location.search);
        const urlId = urlParams.get('institution_id');
        if (urlId) return urlId;

        // Check for institution selector in page
        const selector = document.getElementById('institution-select');
        if (selector && selector.value) return selector.value;

        // Fallback to localStorage
        return localStorage.getItem('current_institution_id');
    }

    async loadConversations() {
        if (!this.institutionId) return;

        try {
            // Show skeleton loader
            this.elements.conversationList.innerHTML = `
                <div class="skeleton-loader">
                    <div class="skeleton-conversation"></div>
                    <div class="skeleton-conversation"></div>
                    <div class="skeleton-conversation"></div>
                </div>
            `;

            const response = await fetch(`/api/chat/conversations?institution_id=${this.institutionId}`);
            if (!response.ok) throw new Error('Failed to load conversations');

            const data = await response.json();
            this.conversations = data.conversations || [];

            this.renderConversations();

            // Load most recent conversation if available
            if (this.conversations.length > 0) {
                await this.loadConversation(this.conversations[0].id);
            } else {
                this.showWelcome();
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
            this.elements.conversationList.innerHTML = `
                <div class="no-conversations">
                    ${window.t ? t('chat.no_conversations') : 'No conversations yet'}
                </div>
            `;
            this.showWelcome();
        }
    }

    renderConversations() {
        if (this.conversations.length === 0) {
            this.elements.conversationList.innerHTML = `
                <div class="no-conversations">
                    ${window.t ? t('chat.no_conversations') : 'No conversations yet'}
                </div>
            `;
            return;
        }

        this.elements.conversationList.innerHTML = this.conversations.map(conv => `
            <div class="conversation-item ${conv.id === this.currentConversationId ? 'active' : ''}"
                 data-conv-id="${conv.id}"
                 onclick="chatManager.loadConversation('${conv.id}')">
                <div class="conversation-info">
                    <div class="conversation-title">${this.escapeHtml(conv.title || 'New Conversation')}</div>
                    <div class="conversation-meta">
                        ${this.formatDate(conv.updated_at)} • ${conv.message_count} msg
                    </div>
                </div>
                <div class="conversation-actions">
                    <button class="delete-conversation-btn"
                            onclick="event.stopPropagation(); chatManager.deleteConversation('${conv.id}')"
                            title="Delete">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');
    }

    async createNewConversation() {
        if (!this.institutionId) {
            window.toast && toast.error('Please select an institution first');
            return;
        }

        try {
            const response = await fetch('/api/chat/conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ institution_id: this.institutionId })
            });

            if (!response.ok) throw new Error('Failed to create conversation');

            const data = await response.json();
            this.currentConversationId = data.conversation_id;

            // Reload conversations
            await this.loadConversations();

            // Clear messages and show empty state
            this.messages = [];
            this.renderMessages();
            this.enableInput();

            window.toast && toast.success('New conversation started');
        } catch (error) {
            console.error('Error creating conversation:', error);
            window.toast && toast.error('Failed to create conversation');
        }
    }

    async loadConversation(conversationId) {
        if (conversationId === this.currentConversationId) return;

        try {
            const response = await fetch(`/api/chat/conversations/${conversationId}`);
            if (!response.ok) throw new Error('Failed to load conversation');

            const data = await response.json();
            this.currentConversationId = conversationId;
            this.messages = data.messages || [];

            this.renderMessages();
            this.renderConversations(); // Update active state
            this.enableInput();

            // Hide suggestions when loading conversation
            this.hideSuggestions();
        } catch (error) {
            console.error('Error loading conversation:', error);
            window.toast && toast.error('Failed to load conversation');
        }
    }

    async deleteConversation(conversationId) {
        const confirmed = window.confirm(
            window.t ? t('chat.delete_confirm') : 'Delete this conversation?'
        );

        if (!confirmed) return;

        try {
            const response = await fetch(`/api/chat/conversations/${conversationId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete conversation');

            // If deleting current conversation, clear it
            if (conversationId === this.currentConversationId) {
                this.currentConversationId = null;
                this.messages = [];
                this.showWelcome();
                this.disableInput();
            }

            // Reload conversations
            await this.loadConversations();

            window.toast && toast.success('Conversation deleted');
        } catch (error) {
            console.error('Error deleting conversation:', error);
            window.toast && toast.error('Failed to delete conversation');
        }
    }

    renderMessages() {
        // Hide welcome, show messages
        if (this.elements.chatWelcome) {
            this.elements.chatWelcome.style.display = 'none';
        }

        // Clear existing messages
        const existingMessages = this.elements.messagesContainer.querySelectorAll('.chat-message');
        existingMessages.forEach(el => el.remove());

        // Render all messages
        this.messages.forEach(msg => {
            this.addMessageElement(msg.content, msg.role);
        });

        this.scrollToBottom();
    }

    addMessageElement(content, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        messageDiv.innerHTML = this.formatMessage(content);

        this.elements.messagesContainer.appendChild(messageDiv);
        return messageDiv;
    }

    async sendMessage() {
        const message = this.elements.chatInput.value.trim();
        if (!message || this.isStreaming) return;

        // Create conversation if needed
        if (!this.currentConversationId) {
            await this.createNewConversation();
            if (!this.currentConversationId) return;
        }

        // Add user message immediately
        this.addMessageElement(message, 'user');
        this.elements.chatInput.value = '';

        // Create assistant message with typing indicator
        const assistantDiv = this.addMessageElement(
            '<div class="typing-indicator"><span></span><span></span><span></span></div>',
            'assistant'
        );

        this.isStreaming = true;
        this.elements.sendBtn.disabled = true;
        this.scrollToBottom();

        try {
            let fullResponse = '';

            await window.API.streamPost('/api/chat/stream', {
                message,
                conversation_id: this.currentConversationId,
                institution_id: this.institutionId
            }, {
                onChunk: (text) => {
                    fullResponse += text;
                    assistantDiv.innerHTML = this.formatMessage(fullResponse);
                    this.scrollToBottom();
                },
                onComplete: (data) => {
                    assistantDiv.innerHTML = this.formatMessage(fullResponse);

                    // Update conversation ID if returned
                    if (data.conversation_id) {
                        this.currentConversationId = data.conversation_id;
                    }

                    // Reload conversations to update title and timestamp
                    this.loadConversations();

                    // Fetch and show suggestions
                    this.fetchSuggestions();
                },
                onError: (error) => {
                    assistantDiv.innerHTML = `<span class="text-error">Error: ${error.message || 'Unknown error'}</span>`;
                    window.toast && toast.error('Failed to get response');
                }
            });
        } catch (error) {
            console.error('Error sending message:', error);
            assistantDiv.innerHTML = `<span class="text-error">Error: ${error.message}</span>`;
            window.toast && toast.error('Failed to send message');
        } finally {
            this.isStreaming = false;
            this.elements.sendBtn.disabled = false;
            this.elements.chatInput.focus();
        }
    }

    async fetchSuggestions() {
        if (!this.currentConversationId) return;

        try {
            const response = await fetch('/api/chat/suggestions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: this.currentConversationId,
                    context: ''
                })
            });

            if (!response.ok) return;

            const data = await response.json();
            if (data.suggestions && data.suggestions.length > 0) {
                this.showSuggestions(data.suggestions);
            }
        } catch (error) {
            console.error('Error fetching suggestions:', error);
            // Fail silently - suggestions are optional
        }
    }

    showSuggestions(suggestions) {
        this.elements.suggestionsChips.innerHTML = suggestions.map(suggestion => `
            <button class="suggestion-chip" onclick="chatManager.clickSuggestion(\`${this.escapeHtml(suggestion)}\`)">
                ${this.escapeHtml(suggestion)}
            </button>
        `).join('');

        this.elements.suggestionsContainer.style.display = 'block';
    }

    hideSuggestions() {
        this.elements.suggestionsContainer.style.display = 'none';
    }

    clickSuggestion(prompt) {
        this.elements.chatInput.value = prompt;
        this.elements.chatInput.focus();
        this.hideSuggestions();
        this.sendMessage();
    }

    showWelcome() {
        if (this.elements.chatWelcome) {
            this.elements.chatWelcome.style.display = 'block';
        }

        // Clear messages
        const existingMessages = this.elements.messagesContainer.querySelectorAll('.chat-message');
        existingMessages.forEach(el => el.remove());
    }

    enableInput() {
        this.elements.chatInput.disabled = false;
        this.elements.sendBtn.disabled = false;
        this.elements.chatInput.focus();
    }

    disableInput() {
        this.elements.chatInput.disabled = true;
        this.elements.sendBtn.disabled = true;
    }

    scrollToBottom() {
        this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
    }

    formatMessage(text) {
        // Simple markdown-like formatting
        return text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }

    formatDate(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;

        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h ago`;

        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
let chatManager;
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if chat panel exists
    if (document.getElementById('chat-messages')) {
        chatManager = new ChatManager();
    }
});
