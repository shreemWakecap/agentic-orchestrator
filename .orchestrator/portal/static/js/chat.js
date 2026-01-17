/**
 * Chat Module
 *
 * Provides chat functionality with WebSocket connection for real-time
 * message exchange in the SDLC Orchestrator.
 *
 * Features:
 * - WebSocket-based real-time messaging
 * - Message sending and receiving
 * - DOM updates for chat display
 * - Auto-scroll to latest messages
 * - Connection status management
 * - Reconnection with exponential backoff
 *
 * DOM Requirements:
 * - #chat-container or element with data-chat-init attribute
 * - #chat-messages - Message display container
 * - #chat-input - Text input for new messages
 * - #chat-send-btn - Send button
 * - #chat-connection-status - Optional connection indicator
 */

const ChatModule = {
    // Configuration
    config: {
        maxMessages: 500,
        reconnectDelay: 1000,
        reconnectMaxDelay: 30000,
        reconnectAttempts: 10,
        autoScroll: true
    },

    // State
    state: {
        websocket: null,
        messages: [],
        reconnectCount: 0,
        reconnectTimer: null,
        isConnected: false,
        userId: null,
        sessionId: null
    },

    // DOM Elements
    elements: {
        container: null,
        messagesContainer: null,
        inputField: null,
        sendButton: null,
        connectionStatus: null
    },

    /**
     * Initialize the chat module
     * @param {Object} options - Configuration options
     * @param {string} [options.containerId] - ID of the chat container element
     * @param {string} [options.wsUrl] - WebSocket URL for chat connection
     * @param {string} [options.userId] - User identifier
     * @param {string} [options.sessionId] - Session identifier
     */
    init(options = {}) {
        this.cacheElements(options.containerId);
        this.state.userId = options.userId || this.generateId();
        this.state.sessionId = options.sessionId || this.generateId();

        if (!this.elements.container) {
            console.warn('Chat container not found, chat module not initialized');
            return;
        }

        this.bindEvents();

        // Connect if WebSocket URL provided or available via data attribute
        const wsUrl = options.wsUrl || this.elements.container.dataset.wsUrl;
        if (wsUrl) {
            this.connect(wsUrl);
        }

        // Load any existing messages from DOM
        this.loadExistingMessages();
    },

    /**
     * Cache DOM element references
     * @param {string} containerId - ID of the main chat container
     */
    cacheElements(containerId) {
        this.elements.container = document.getElementById(containerId || 'chat-container')
            || document.querySelector('[data-chat-init]');

        if (this.elements.container) {
            this.elements.messagesContainer = document.getElementById('chat-messages')
                || this.elements.container.querySelector('[data-chat-messages]');
            this.elements.inputField = document.getElementById('chat-input')
                || this.elements.container.querySelector('[data-chat-input]');
            this.elements.sendButton = document.getElementById('chat-send-btn')
                || this.elements.container.querySelector('[data-chat-send]');
            this.elements.connectionStatus = document.getElementById('chat-connection-status')
                || this.elements.container.querySelector('[data-chat-status]');
        }
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Send button click
        if (this.elements.sendButton) {
            this.elements.sendButton.addEventListener('click', () => {
                this.sendMessage();
            });
        }

        // Enter key to send
        if (this.elements.inputField) {
            this.elements.inputField.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }

        // Handle visibility change for reconnection
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && !this.state.isConnected && this.state.websocket) {
                this.reconnect();
            }
        });

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.disconnect();
        });
    },

    /**
     * Load existing messages from DOM
     */
    loadExistingMessages() {
        if (!this.elements.messagesContainer) return;

        const existingMessages = this.elements.messagesContainer.querySelectorAll('[data-message]');
        existingMessages.forEach(msgEl => {
            this.state.messages.push({
                element: msgEl,
                id: msgEl.dataset.messageId || this.generateId(),
                userId: msgEl.dataset.userId || 'system',
                content: msgEl.dataset.messageContent || msgEl.textContent,
                timestamp: msgEl.dataset.timestamp || new Date().toISOString(),
                type: msgEl.dataset.messageType || 'message'
            });
        });
    },

    /**
     * Connect to WebSocket server
     * @param {string} url - WebSocket URL
     */
    connect(url) {
        if (this.state.websocket && this.state.websocket.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        try {
            this.state.websocket = new WebSocket(url);

            this.state.websocket.onopen = () => {
                this.state.isConnected = true;
                this.state.reconnectCount = 0;
                this.updateConnectionStatus('connected');
                this.dispatchCustomEvent('connected', { url });

                // Send join message
                this.sendSystemMessage('join', {
                    userId: this.state.userId,
                    sessionId: this.state.sessionId
                });
            };

            this.state.websocket.onmessage = (event) => {
                this.handleMessage(event.data);
            };

            this.state.websocket.onclose = (event) => {
                this.state.isConnected = false;
                this.updateConnectionStatus('disconnected');
                this.dispatchCustomEvent('disconnected', { code: event.code, reason: event.reason });

                // Attempt reconnection if not a clean close
                if (event.code !== 1000 && event.code !== 1001) {
                    this.scheduleReconnect(url);
                }
            };

            this.state.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.dispatchCustomEvent('error', { error });
            };
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.updateConnectionStatus('error');
        }
    },

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        if (this.state.reconnectTimer) {
            clearTimeout(this.state.reconnectTimer);
            this.state.reconnectTimer = null;
        }

        if (this.state.websocket) {
            // Send leave message before closing
            if (this.state.isConnected) {
                this.sendSystemMessage('leave', {
                    userId: this.state.userId,
                    sessionId: this.state.sessionId
                });
            }

            this.state.websocket.close(1000, 'User disconnected');
            this.state.websocket = null;
        }

        this.state.isConnected = false;
        this.updateConnectionStatus('disconnected');
    },

    /**
     * Schedule a reconnection attempt
     * @param {string} url - WebSocket URL to reconnect to
     */
    scheduleReconnect(url) {
        if (this.state.reconnectCount >= this.config.reconnectAttempts) {
            console.log('Max reconnection attempts reached');
            this.dispatchCustomEvent('connectionFailed', { attempts: this.state.reconnectCount });
            return;
        }

        // Exponential backoff
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.state.reconnectCount),
            this.config.reconnectMaxDelay
        );

        this.state.reconnectCount++;
        this.updateConnectionStatus('reconnecting');

        this.state.reconnectTimer = setTimeout(() => {
            this.connect(url);
        }, delay);
    },

    /**
     * Attempt to reconnect using stored URL
     */
    reconnect() {
        if (this.state.websocket && this.state.websocket.url) {
            this.connect(this.state.websocket.url);
        }
    },

    /**
     * Handle incoming WebSocket message
     * @param {string} data - Raw message data
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            this.processMessage(message);
        } catch (error) {
            // Handle plain text messages
            this.processMessage({
                type: 'message',
                content: data,
                userId: 'system',
                timestamp: new Date().toISOString()
            });
        }
    },

    /**
     * Process a parsed message object
     * @param {Object} message - Message object
     */
    processMessage(message) {
        switch (message.type) {
            case 'message':
            case 'chat':
                this.addMessage(message);
                break;
            case 'system':
                this.addSystemMessage(message.content);
                break;
            case 'error':
                this.addErrorMessage(message.content || message.error);
                break;
            case 'typing':
                this.handleTypingIndicator(message);
                break;
            case 'presence':
                this.handlePresenceUpdate(message);
                break;
            default:
                // Add unknown message types as regular messages
                this.addMessage(message);
        }

        // Dispatch event for external listeners
        this.dispatchCustomEvent('message', message);
    },

    /**
     * Send a chat message
     * @param {string} [content] - Message content (uses input field if not provided)
     * @returns {boolean} Whether message was sent
     */
    sendMessage(content) {
        const messageContent = content || (this.elements.inputField && this.elements.inputField.value.trim());

        if (!messageContent) {
            return false;
        }

        if (!this.state.isConnected) {
            console.warn('Cannot send message: not connected');
            this.addErrorMessage('Cannot send message: not connected');
            return false;
        }

        const message = {
            type: 'message',
            id: this.generateId(),
            userId: this.state.userId,
            sessionId: this.state.sessionId,
            content: messageContent,
            timestamp: new Date().toISOString()
        };

        try {
            this.state.websocket.send(JSON.stringify(message));

            // Add to local display
            this.addMessage(message, true);

            // Clear input field
            if (this.elements.inputField && !content) {
                this.elements.inputField.value = '';
                this.elements.inputField.focus();
            }

            return true;
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addErrorMessage('Failed to send message');
            return false;
        }
    },

    /**
     * Send a system message (join, leave, etc.)
     * @param {string} type - System message type
     * @param {Object} data - Additional data
     */
    sendSystemMessage(type, data) {
        if (!this.state.isConnected || !this.state.websocket) {
            return false;
        }

        try {
            this.state.websocket.send(JSON.stringify({
                type: 'system',
                action: type,
                ...data,
                timestamp: new Date().toISOString()
            }));
            return true;
        } catch (error) {
            console.error('Failed to send system message:', error);
            return false;
        }
    },

    /**
     * Add a message to the chat display
     * @param {Object} message - Message object
     * @param {boolean} [isOwn=false] - Whether this is the current user's message
     */
    addMessage(message, isOwn = false) {
        if (!this.elements.messagesContainer) return;

        // Enforce max messages limit
        if (this.state.messages.length >= this.config.maxMessages) {
            const oldMessage = this.state.messages.shift();
            if (oldMessage.element && oldMessage.element.parentNode) {
                oldMessage.element.parentNode.removeChild(oldMessage.element);
            }
        }

        const messageDiv = document.createElement('div');
        const isOwnMessage = isOwn || message.userId === this.state.userId;

        messageDiv.className = isOwnMessage
            ? 'chat-message chat-message-own px-4 py-2 mb-2 rounded-lg bg-blue-100 ml-auto max-w-xs md:max-w-md'
            : 'chat-message chat-message-other px-4 py-2 mb-2 rounded-lg bg-gray-100 mr-auto max-w-xs md:max-w-md';

        messageDiv.dataset.message = 'true';
        messageDiv.dataset.messageId = message.id || this.generateId();
        messageDiv.dataset.userId = message.userId || 'unknown';
        messageDiv.dataset.timestamp = message.timestamp || new Date().toISOString();
        messageDiv.dataset.messageType = message.type || 'message';

        // Build message content
        const timestamp = message.timestamp
            ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : '';

        let content = '';
        if (!isOwnMessage && message.userId) {
            content += `<div class="text-xs text-gray-500 mb-1">${this.escapeHtml(message.userId)}</div>`;
        }
        content += `<div class="message-content">${this.escapeHtml(message.content)}</div>`;
        content += `<div class="text-xs text-gray-400 mt-1 text-right">${timestamp}</div>`;

        messageDiv.innerHTML = content;

        // Store message
        const storedMessage = {
            element: messageDiv,
            id: message.id,
            userId: message.userId,
            content: message.content,
            timestamp: message.timestamp,
            type: message.type
        };
        this.state.messages.push(storedMessage);

        // Add to DOM
        this.elements.messagesContainer.appendChild(messageDiv);

        // Auto-scroll if enabled
        if (this.config.autoScroll) {
            this.scrollToBottom();
        }
    },

    /**
     * Add a system message to the chat display
     * @param {string} content - System message content
     */
    addSystemMessage(content) {
        if (!this.elements.messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-system-message text-center text-sm text-gray-500 py-2 my-2';
        messageDiv.dataset.message = 'true';
        messageDiv.dataset.messageType = 'system';
        messageDiv.textContent = content;

        this.elements.messagesContainer.appendChild(messageDiv);

        if (this.config.autoScroll) {
            this.scrollToBottom();
        }
    },

    /**
     * Add an error message to the chat display
     * @param {string} content - Error message content
     */
    addErrorMessage(content) {
        if (!this.elements.messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-error-message text-center text-sm text-red-500 py-2 my-2';
        messageDiv.dataset.message = 'true';
        messageDiv.dataset.messageType = 'error';
        messageDiv.textContent = content;

        this.elements.messagesContainer.appendChild(messageDiv);

        if (this.config.autoScroll) {
            this.scrollToBottom();
        }
    },

    /**
     * Handle typing indicator
     * @param {Object} message - Typing message
     */
    handleTypingIndicator(message) {
        // Implement typing indicator UI updates
        this.dispatchCustomEvent('typing', message);
    },

    /**
     * Handle presence updates (user join/leave)
     * @param {Object} message - Presence message
     */
    handlePresenceUpdate(message) {
        const action = message.action || message.status;
        const userId = message.userId || message.user;

        if (action === 'join' && userId !== this.state.userId) {
            this.addSystemMessage(`${userId} joined the chat`);
        } else if (action === 'leave' && userId !== this.state.userId) {
            this.addSystemMessage(`${userId} left the chat`);
        }

        this.dispatchCustomEvent('presence', message);
    },

    /**
     * Scroll messages container to bottom
     */
    scrollToBottom() {
        if (this.elements.messagesContainer) {
            this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
        }
    },

    /**
     * Update connection status indicator
     * @param {string} status - 'connected', 'disconnected', 'reconnecting', or 'error'
     */
    updateConnectionStatus(status) {
        if (this.elements.connectionStatus) {
            const statusClasses = {
                connected: 'inline-block w-2 h-2 rounded-full bg-green-500',
                disconnected: 'inline-block w-2 h-2 rounded-full bg-red-500',
                reconnecting: 'inline-block w-2 h-2 rounded-full bg-yellow-500 animate-pulse',
                error: 'inline-block w-2 h-2 rounded-full bg-red-500'
            };

            const statusTitles = {
                connected: 'Connected to chat',
                disconnected: 'Disconnected from chat',
                reconnecting: 'Reconnecting...',
                error: 'Connection error'
            };

            this.elements.connectionStatus.className = statusClasses[status] || statusClasses.disconnected;
            this.elements.connectionStatus.title = statusTitles[status] || 'Unknown status';
        }

        // Update send button state
        if (this.elements.sendButton) {
            this.elements.sendButton.disabled = status !== 'connected';
        }
    },

    /**
     * Dispatch custom event for external listeners
     * @param {string} name - Event name
     * @param {Object} detail - Event detail data
     */
    dispatchCustomEvent(name, detail) {
        const event = new CustomEvent(`chat:${name}`, { detail });
        document.dispatchEvent(event);
    },

    /**
     * Generate a unique ID
     * @returns {string} Unique identifier
     */
    generateId() {
        return 'chat_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
    },

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Clear all messages
     */
    clearMessages() {
        if (this.elements.messagesContainer) {
            this.elements.messagesContainer.innerHTML = '';
        }
        this.state.messages = [];
    },

    /**
     * Get all messages
     * @returns {Array} Array of message objects
     */
    getMessages() {
        return this.state.messages.map(msg => ({
            id: msg.id,
            userId: msg.userId,
            content: msg.content,
            timestamp: msg.timestamp,
            type: msg.type
        }));
    },

    /**
     * Check if connected
     * @returns {boolean} Connection status
     */
    isConnected() {
        return this.state.isConnected;
    },

    /**
     * Set auto-scroll behavior
     * @param {boolean} enabled - Whether to enable auto-scroll
     */
    setAutoScroll(enabled) {
        this.config.autoScroll = enabled;
    }
};

// Auto-initialize from data attributes on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container')
        || document.querySelector('[data-chat-init]');

    if (chatContainer) {
        const wsUrl = chatContainer.dataset.wsUrl;
        const userId = chatContainer.dataset.userId;
        const sessionId = chatContainer.dataset.sessionId;

        ChatModule.init({
            containerId: chatContainer.id,
            wsUrl: wsUrl,
            userId: userId,
            sessionId: sessionId
        });
    }
});

// Expose globally for onclick handlers and external access
window.ChatModule = ChatModule;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatModule;
}
