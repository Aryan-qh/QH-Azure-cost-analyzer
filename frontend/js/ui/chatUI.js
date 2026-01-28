// ui/chatUI.js
import { formatters } from '../utils/formatters.js';

/**
 * Chat UI Component
 * 
 * Handles rendering of chat messages with different types:
 * - User messages
 * - Assistant messages
 * - Tool call indicators
 * - Error messages
 */
export const chatUI = {
    
    createMessage(message) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper message-${message.role}`;

        if (message.role === 'user') {
            wrapper.innerHTML = `
                <div class="message message-user">
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${this.formatTimestamp(message.timestamp)}</div>
                </div>
            `;
        } else if (message.role === 'assistant') {
            const toolCallsHtml = message.tool_calls ? this.renderToolCalls(message.tool_calls) : '';
            
            wrapper.innerHTML = `
                <div class="message message-assistant">
                    <div class="message-avatar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/>
                        </svg>
                    </div>
                    <div class="message-body">
                        ${toolCallsHtml}
                        <div class="message-content">${this.formatContent(message.content)}</div>
                        <div class="message-time">${this.formatTimestamp(message.timestamp)}</div>
                    </div>
                </div>
            `;
        } else if (message.role === 'error') {
            wrapper.innerHTML = `
                <div class="message message-error">
                    <div class="message-content">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        ${this.escapeHtml(message.content)}
                    </div>
                </div>
            `;
        }

        return wrapper;
    },

    renderToolCalls(toolCalls) {
        if (!toolCalls || toolCalls.length === 0) return '';

        const toolsHtml = toolCalls.map(tool => {
            const toolName = this.getToolDisplayName(tool.tool);
            const toolIcon = this.getToolIcon(tool.tool);
            
            return `
                <div class="tool-call">
                    <div class="tool-call-icon">${toolIcon}</div>
                    <div class="tool-call-text">
                        <strong>${toolName}</strong>
                        <div class="tool-call-params">${this.formatToolParams(tool.input)}</div>
                    </div>
                </div>
            `;
        }).join('');

        return `<div class="tool-calls">${toolsHtml}</div>`;
    },

    getToolDisplayName(toolName) {
        const names = {
            'get_subscription_list': 'Getting Subscriptions',
            'get_cost_summary': 'Fetching Cost Data',
            'detect_anomalies': 'Detecting Anomalies'
        };
        return names[toolName] || toolName;
    },

    getToolIcon(toolName) {
        const icons = {
            'get_subscription_list': `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                </svg>
            `,
            'get_cost_summary': `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="1" x2="12" y2="23"></line>
                    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                </svg>
            `,
            'detect_anomalies': `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
            `
        };
        return icons[toolName] || `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
            </svg>
        `;
    },

    formatToolParams(params) {
        if (!params) return '';

        const parts = [];
        
        if (params.subscription_names) {
            parts.push(`Subscriptions: ${params.subscription_names.join(', ')}`);
        }
        if (params.num_days) {
            parts.push(`${params.num_days} days`);
        }
        if (params.target_date) {
            parts.push(`Date: ${params.target_date}`);
        }
        if (params.threshold_percent) {
            parts.push(`Threshold: ${params.threshold_percent}%`);
        }

        return parts.join(' • ') || 'No parameters';
    },

    formatContent(content) {
        // Convert newlines to <br>
        let formatted = this.escapeHtml(content);
        formatted = formatted.replace(/\n/g, '<br>');

        // Convert **bold** to <strong>
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Convert *italic* to <em>
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Convert `code` to <code>
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        return formatted;
    },

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        
        const isToday = date.toDateString() === now.toDateString();
        
        if (isToday) {
            return date.toLocaleTimeString('en-US', { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            });
        } else {
            return date.toLocaleString('en-US', { 
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};