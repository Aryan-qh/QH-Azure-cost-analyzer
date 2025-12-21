// components/agent.js
import { sessionState } from '../state/sessionState.js';
import { apiService } from '../services/apiService.js';
import { domHelpers } from '../utils/domHelpers.js';
import { notifications } from '../ui/notifications.js';
import { loading } from '../ui/loading.js';
import { tabs } from './tabs.js';
import { configuration } from './configuration.js';
import { chatUI } from '../ui/chatUI.js';

/**
 * AI Agent Component
 * 
 * Provides conversational interface to Azure cost analysis
 * Features:
 * - Multi-turn conversations with context
 * - Conversation management (create, list, delete)
 * - Tool call visualization
 * - Message history
 */
export const agent = {
    currentConversationId: null,
    conversations: [],
    messages: [],

    init() {
        this.setupEventListeners();
        this.loadConversations();
    },

    setupEventListeners() {
        // Chat form submission
        const chatForm = domHelpers.getElementById('agent-chat-form');
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => this.handleSendMessage(e));
        }

        // New conversation button
        const newConvBtn = domHelpers.getElementById('new-conversation-btn');
        if (newConvBtn) {
            newConvBtn.addEventListener('click', () => this.createNewConversation());
        }

        // Input auto-resize
        const messageInput = domHelpers.getElementById('agent-message-input');
        if (messageInput) {
            messageInput.addEventListener('input', (e) => this.autoResizeInput(e.target));
        }

        // Enter to send (Shift+Enter for new line)
        if (messageInput) {
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    chatForm.dispatchEvent(new Event('submit'));
                }
            });
        }
    },

    async loadConversations() {
        if (!sessionState.isSessionActive()) {
            return;
        }

        try {
            const data = await apiService.listConversations(sessionState.getSessionId());
            this.conversations = data.conversations || [];
            this.renderConversationList();

            // If no current conversation, create one
            if (this.conversations.length === 0) {
                await this.createNewConversation();
            } else {
                // Load most recent conversation
                const mostRecent = this.conversations[0];
                await this.loadConversation(mostRecent.conversation_id);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    },

    renderConversationList() {
        const container = domHelpers.getElementById('conversation-list');
        if (!container) return;

        if (this.conversations.length === 0) {
            container.innerHTML = '<div class="no-conversations">No conversations yet</div>';
            return;
        }

        container.innerHTML = '';
        this.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (conv.conversation_id === this.currentConversationId) {
                item.classList.add('active');
            }

            const date = new Date(conv.last_updated);
            const timeStr = this.formatTime(date);

            item.innerHTML = `
                <div class="conversation-info">
                    <div class="conversation-title">Conversation</div>
                    <div class="conversation-meta">${conv.message_count} messages • ${timeStr}</div>
                </div>
                <button class="conversation-delete" data-id="${conv.conversation_id}" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            `;

            // Click to load conversation
            item.querySelector('.conversation-info').addEventListener('click', () => {
                this.loadConversation(conv.conversation_id);
            });

            // Delete button
            item.querySelector('.conversation-delete').addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.conversation_id);
            });

            container.appendChild(item);
        });
    },

    async createNewConversation() {
        if (!sessionState.isSessionActive()) {
            notifications.alert('Please configure your credentials first');
            tabs.switchToConfigTab();
            return;
        }

        try {
            const data = await apiService.createConversation(sessionState.getSessionId());
            this.currentConversationId = data.conversation_id;
            this.messages = [];

            // Refresh conversation list
            await this.loadConversations();

            // Clear and show welcome message
            this.renderMessages();
            this.showWelcomeMessage();

        } catch (error) {
            console.error('Error creating conversation:', error);
            notifications.alert(`Error: ${error.message}`);
        }
    },

    async loadConversation(conversationId) {
        if (!sessionState.isSessionActive()) {
            return;
        }

        try {
            const data = await apiService.getConversationHistory(
                conversationId,
                sessionState.getSessionId()
            );

            this.currentConversationId = conversationId;
            this.messages = data.messages || [];

            this.renderMessages();
            this.renderConversationList(); // Update active state

        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    },

    async deleteConversation(conversationId) {
        if (!confirm('Delete this conversation?')) {
            return;
        }

        try {
            await apiService.deleteConversation(
                conversationId,
                sessionState.getSessionId()
            );

            // If deleting current conversation, clear it
            if (conversationId === this.currentConversationId) {
                this.currentConversationId = null;
                this.messages = [];
                this.renderMessages();
            }

            // Refresh list
            await this.loadConversations();

        } catch (error) {
            console.error('Error deleting conversation:', error);
            notifications.alert(`Error: ${error.message}`);
        }
    },

    async handleSendMessage(e) {
        e.preventDefault();

        if (!sessionState.isSessionActive()) {
            notifications.alert('Please configure your credentials first');
            tabs.switchToConfigTab();
            return;
        }

        const input = domHelpers.getElementById('agent-message-input');
        const message = input.value.trim();

        if (!message) return;

        // Clear input
        input.value = '';
        this.autoResizeInput(input);

        // Add user message to UI immediately
        this.addMessageToUI('user', message);

        // Show typing indicator
        this.showTypingIndicator();

        // Disable input while processing
        const submitBtn = domHelpers.getElementById('agent-send-btn');
        domHelpers.disable(input);
        domHelpers.disable(submitBtn);

        try {
            const data = await apiService.sendAgentMessage(
                sessionState.getSessionId(),
                message,
                this.currentConversationId
            );

            // Update conversation ID if this was first message
            if (!this.currentConversationId) {
                this.currentConversationId = data.conversation_id;
                await this.loadConversations();
            }

            // Remove typing indicator
            this.hideTypingIndicator();

            // Add assistant response to UI
            this.addMessageToUI('assistant', data.response, data.tool_calls_made);

        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();

            if (error.message.includes('Session expired')) {
                configuration.clearSession();
                notifications.alert('Session expired. Please reconfigure your credentials.');
                setTimeout(() => tabs.switchToConfigTab(), 2000);
            } else {
                this.addMessageToUI('error', `Error: ${error.message}`);
            }
        } finally {
            // Re-enable input
            domHelpers.enable(input);
            domHelpers.enable(submitBtn);
            input.focus();
        }
    },

    addMessageToUI(role, content, toolCalls = null) {
        const message = {
            role,
            content,
            timestamp: new Date().toISOString(),
            tool_calls: toolCalls
        };

        this.messages.push(message);
        this.renderMessages();
    },

    renderMessages() {
        const container = domHelpers.getElementById('agent-messages');
        if (!container) return;

        container.innerHTML = '';

        if (this.messages.length === 0) {
            this.showWelcomeMessage();
            return;
        }

        this.messages.forEach(msg => {
            const messageEl = chatUI.createMessage(msg);
            container.appendChild(messageEl);
        });

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;
    },

    showWelcomeMessage() {
        const container = domHelpers.getElementById('agent-messages');
        if (!container) return;

        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                </div>
                <h3>Azure Cost Analysis AI Assistant</h3>
                <p>Ask me anything about your Azure costs and subscriptions:</p>
                <ul class="example-questions">
                    <li>"What were the costs for my subscriptions yesterday?"</li>
                    <li>"Check for any cost anomalies in the last week"</li>
                    <li>"Show me the cost trend for Virtual Machines"</li>
                    <li>"Are there any unusual spikes in spending?"</li>
                </ul>
            </div>
        `;
    },

    showTypingIndicator() {
        const container = domHelpers.getElementById('agent-messages');
        if (!container) return;

        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;

        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    },

    hideTypingIndicator() {
        const indicator = domHelpers.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    },

    autoResizeInput(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    },

    formatTime(date) {
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        return date.toLocaleDateString();
    }
};