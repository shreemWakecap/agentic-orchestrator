/**
 * SSE Connection Manager Module
 *
 * Manages Server-Sent Events (EventSource) connections with:
 * - Configurable exponential backoff reconnection
 * - Heartbeat timeout detection
 * - Connection state tracking
 * - Automatic fallback to HTTP polling
 * - Proper cleanup on disconnect
 * - Event dispatching for connection state changes
 */

const SSEConnectionManager = (function() {
    'use strict';

    // =========================================================================
    // Connection States
    // =========================================================================

    const ConnectionState = {
        CONNECTING: 'connecting',
        CONNECTED: 'connected',
        RECONNECTING: 'reconnecting',
        DISCONNECTED: 'disconnected',
        FAILED: 'failed'
    };

    // =========================================================================
    // Default Configuration
    // =========================================================================

    const DEFAULT_CONFIG = {
        // Reconnection settings
        initialReconnectDelay: 1000,      // 1 second
        maxReconnectDelay: 30000,         // 30 seconds
        reconnectBackoffMultiplier: 2,    // Exponential backoff multiplier
        maxReconnectAttempts: 5,          // Max attempts before fallback

        // Heartbeat settings
        heartbeatTimeout: 45000,          // 45 seconds

        // Polling fallback settings
        pollingInterval: 3000,            // 3 seconds
        enablePollingFallback: true
    };

    // =========================================================================
    // SSEConnectionManager Class
    // =========================================================================

    /**
     * Create a new SSE Connection Manager instance
     * @param {string} url - The SSE endpoint URL
     * @param {Object} [options] - Configuration options
     */
    function SSEConnectionManager(url, options) {
        if (!url) {
            throw new Error('SSEConnectionManager: URL is required');
        }

        this.url = url;
        this.config = Object.assign({}, DEFAULT_CONFIG, options || {});

        // Internal state
        this._eventSource = null;
        this._state = ConnectionState.DISCONNECTED;
        this._reconnectAttempts = 0;
        this._reconnectTimer = null;
        this._heartbeatTimer = null;
        this._pollingTimer = null;
        this._lastHeartbeat = null;
        this._isPollingMode = false;

        // Event handlers
        this._stateChangeHandlers = [];
        this._messageHandlers = [];
        this._eventHandlers = {};

        // Bind methods to preserve context
        this._onOpen = this._onOpen.bind(this);
        this._onMessage = this._onMessage.bind(this);
        this._onError = this._onError.bind(this);
        this._checkHeartbeat = this._checkHeartbeat.bind(this);
    }

    // =========================================================================
    // Public Methods
    // =========================================================================

    /**
     * Connect to the SSE endpoint
     * @returns {SSEConnectionManager} this instance for chaining
     */
    SSEConnectionManager.prototype.connect = function() {
        // Don't connect if already connecting or connected
        if (this._state === ConnectionState.CONNECTING ||
            this._state === ConnectionState.CONNECTED) {
            return this;
        }

        this._isPollingMode = false;
        this._stopPolling();
        this._setState(ConnectionState.CONNECTING);

        try {
            this._eventSource = new EventSource(this.url);
            this._eventSource.onopen = this._onOpen;
            this._eventSource.onmessage = this._onMessage;
            this._eventSource.onerror = this._onError;

            // Register named event handlers
            var self = this;
            Object.keys(this._eventHandlers).forEach(function(eventType) {
                self._eventSource.addEventListener(eventType, function(e) {
                    self._handleNamedEvent(eventType, e);
                });
            });
        } catch (error) {
            console.error('SSEConnectionManager: Failed to create EventSource:', error);
            this._handleConnectionFailure();
        }

        return this;
    };

    /**
     * Disconnect from the SSE endpoint
     * @returns {SSEConnectionManager} this instance for chaining
     */
    SSEConnectionManager.prototype.disconnect = function() {
        this._cleanup();
        this._setState(ConnectionState.DISCONNECTED);
        this._reconnectAttempts = 0;
        return this;
    };

    /**
     * Get the current connection state
     * @returns {string} Current connection state
     */
    SSEConnectionManager.prototype.getState = function() {
        return this._state;
    };

    /**
     * Check if currently connected
     * @returns {boolean} True if connected
     */
    SSEConnectionManager.prototype.isConnected = function() {
        return this._state === ConnectionState.CONNECTED;
    };

    /**
     * Check if in polling fallback mode
     * @returns {boolean} True if using HTTP polling
     */
    SSEConnectionManager.prototype.isPollingMode = function() {
        return this._isPollingMode;
    };

    /**
     * Register a callback for connection state changes
     * @param {Function} handler - Callback function(newState, oldState)
     * @returns {Function} Cleanup function to remove the handler
     */
    SSEConnectionManager.prototype.onStateChange = function(handler) {
        if (typeof handler !== 'function') {
            throw new Error('SSEConnectionManager: Handler must be a function');
        }

        this._stateChangeHandlers.push(handler);

        var self = this;
        return function() {
            var index = self._stateChangeHandlers.indexOf(handler);
            if (index > -1) {
                self._stateChangeHandlers.splice(index, 1);
            }
        };
    };

    /**
     * Register a callback for incoming messages
     * @param {Function} handler - Callback function(data, event)
     * @returns {Function} Cleanup function to remove the handler
     */
    SSEConnectionManager.prototype.onMessage = function(handler) {
        if (typeof handler !== 'function') {
            throw new Error('SSEConnectionManager: Handler must be a function');
        }

        this._messageHandlers.push(handler);

        var self = this;
        return function() {
            var index = self._messageHandlers.indexOf(handler);
            if (index > -1) {
                self._messageHandlers.splice(index, 1);
            }
        };
    };

    /**
     * Register a callback for a specific named event type
     * @param {string} eventType - The event type name
     * @param {Function} handler - Callback function(data, event)
     * @returns {Function} Cleanup function to remove the handler
     */
    SSEConnectionManager.prototype.on = function(eventType, handler) {
        if (typeof eventType !== 'string' || !eventType) {
            throw new Error('SSEConnectionManager: Event type must be a non-empty string');
        }
        if (typeof handler !== 'function') {
            throw new Error('SSEConnectionManager: Handler must be a function');
        }

        if (!this._eventHandlers[eventType]) {
            this._eventHandlers[eventType] = [];

            // If already connected, add the listener to the EventSource
            if (this._eventSource) {
                var self = this;
                this._eventSource.addEventListener(eventType, function(e) {
                    self._handleNamedEvent(eventType, e);
                });
            }
        }

        this._eventHandlers[eventType].push(handler);

        var self = this;
        return function() {
            var handlers = self._eventHandlers[eventType];
            if (handlers) {
                var index = handlers.indexOf(handler);
                if (index > -1) {
                    handlers.splice(index, 1);
                }
            }
        };
    };

    /**
     * Set the polling fallback function
     * @param {Function} pollFn - Async function to call for polling
     * @returns {SSEConnectionManager} this instance for chaining
     */
    SSEConnectionManager.prototype.setPollingFallback = function(pollFn) {
        if (typeof pollFn !== 'function') {
            throw new Error('SSEConnectionManager: Poll function must be a function');
        }
        this._pollingFallbackFn = pollFn;
        return this;
    };

    /**
     * Force switch to polling mode (useful for testing)
     * @returns {SSEConnectionManager} this instance for chaining
     */
    SSEConnectionManager.prototype.switchToPolling = function() {
        this._cleanup();
        this._startPollingFallback();
        return this;
    };

    // =========================================================================
    // Private Methods - Event Handlers
    // =========================================================================

    /**
     * Handle EventSource open event
     */
    SSEConnectionManager.prototype._onOpen = function() {
        this._setState(ConnectionState.CONNECTED);
        this._reconnectAttempts = 0;
        this._lastHeartbeat = Date.now();
        this._startHeartbeatMonitor();

        // Dispatch custom event for connection
        this._dispatchEvent('sse:connected', { url: this.url });
    };

    /**
     * Handle EventSource message event
     */
    SSEConnectionManager.prototype._onMessage = function(event) {
        // Reset heartbeat timer on any message
        this._lastHeartbeat = Date.now();

        var data = null;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            data = event.data;
        }

        // Handle heartbeat messages
        if (data && data.type === 'heartbeat') {
            this._handleHeartbeat(data);
            return;
        }

        // Notify message handlers
        var self = this;
        this._messageHandlers.forEach(function(handler) {
            try {
                handler(data, event);
            } catch (err) {
                console.error('SSEConnectionManager: Message handler error:', err);
            }
        });
    };

    /**
     * Handle EventSource error event
     */
    SSEConnectionManager.prototype._onError = function(event) {
        console.warn('SSEConnectionManager: Connection error', event);

        // Close the current connection
        if (this._eventSource) {
            this._eventSource.close();
            this._eventSource = null;
        }

        this._stopHeartbeatMonitor();

        // Attempt reconnection
        this._attemptReconnect();
    };

    /**
     * Handle named SSE events
     */
    SSEConnectionManager.prototype._handleNamedEvent = function(eventType, event) {
        // Reset heartbeat timer on any event
        this._lastHeartbeat = Date.now();

        var data = null;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            data = event.data;
        }

        var handlers = this._eventHandlers[eventType];
        if (handlers) {
            handlers.forEach(function(handler) {
                try {
                    handler(data, event);
                } catch (err) {
                    console.error('SSEConnectionManager: Event handler error:', err);
                }
            });
        }
    };

    /**
     * Handle heartbeat message
     */
    SSEConnectionManager.prototype._handleHeartbeat = function(data) {
        this._lastHeartbeat = Date.now();
        this._dispatchEvent('sse:heartbeat', { timestamp: this._lastHeartbeat, data: data });
    };

    // =========================================================================
    // Private Methods - Reconnection
    // =========================================================================

    /**
     * Attempt to reconnect with exponential backoff
     */
    SSEConnectionManager.prototype._attemptReconnect = function() {
        this._reconnectAttempts++;

        // Check if we've exceeded max attempts
        if (this._reconnectAttempts > this.config.maxReconnectAttempts) {
            this._handleConnectionFailure();
            return;
        }

        this._setState(ConnectionState.RECONNECTING);

        // Calculate delay with exponential backoff
        var delay = Math.min(
            this.config.initialReconnectDelay * Math.pow(this.config.reconnectBackoffMultiplier, this._reconnectAttempts - 1),
            this.config.maxReconnectDelay
        );

        console.log('SSEConnectionManager: Reconnecting in ' + delay + 'ms (attempt ' + this._reconnectAttempts + ')');

        var self = this;
        this._reconnectTimer = setTimeout(function() {
            self._reconnectTimer = null;
            self.connect();
        }, delay);
    };

    /**
     * Handle final connection failure - switch to polling fallback
     */
    SSEConnectionManager.prototype._handleConnectionFailure = function() {
        console.warn('SSEConnectionManager: Max reconnection attempts reached');

        if (this.config.enablePollingFallback && this._pollingFallbackFn) {
            this._startPollingFallback();
        } else {
            this._setState(ConnectionState.FAILED);
            this._dispatchEvent('sse:failed', {
                url: this.url,
                attempts: this._reconnectAttempts
            });
        }
    };

    // =========================================================================
    // Private Methods - Heartbeat
    // =========================================================================

    /**
     * Start heartbeat monitoring
     */
    SSEConnectionManager.prototype._startHeartbeatMonitor = function() {
        this._stopHeartbeatMonitor();

        var self = this;
        this._heartbeatTimer = setInterval(this._checkHeartbeat, this.config.heartbeatTimeout / 2);
    };

    /**
     * Stop heartbeat monitoring
     */
    SSEConnectionManager.prototype._stopHeartbeatMonitor = function() {
        if (this._heartbeatTimer) {
            clearInterval(this._heartbeatTimer);
            this._heartbeatTimer = null;
        }
    };

    /**
     * Check if heartbeat has timed out
     */
    SSEConnectionManager.prototype._checkHeartbeat = function() {
        if (!this._lastHeartbeat) return;

        var elapsed = Date.now() - this._lastHeartbeat;
        if (elapsed > this.config.heartbeatTimeout) {
            console.warn('SSEConnectionManager: Heartbeat timeout (' + elapsed + 'ms)');

            // Close connection and trigger reconnect
            if (this._eventSource) {
                this._eventSource.close();
                this._eventSource = null;
            }
            this._stopHeartbeatMonitor();
            this._attemptReconnect();
        }
    };

    // =========================================================================
    // Private Methods - Polling Fallback
    // =========================================================================

    /**
     * Start polling fallback mode
     */
    SSEConnectionManager.prototype._startPollingFallback = function() {
        this._stopPolling();
        this._isPollingMode = true;
        this._setState(ConnectionState.CONNECTED);

        console.log('SSEConnectionManager: Switching to polling fallback');
        this._dispatchEvent('sse:polling', { url: this.url, interval: this.config.pollingInterval });

        // Initial poll
        this._executePoll();

        // Start polling interval
        var self = this;
        this._pollingTimer = setInterval(function() {
            self._executePoll();
        }, this.config.pollingInterval);
    };

    /**
     * Stop polling
     */
    SSEConnectionManager.prototype._stopPolling = function() {
        if (this._pollingTimer) {
            clearInterval(this._pollingTimer);
            this._pollingTimer = null;
        }
    };

    /**
     * Execute a single poll
     */
    SSEConnectionManager.prototype._executePoll = function() {
        if (!this._pollingFallbackFn) return;

        var self = this;
        try {
            var result = this._pollingFallbackFn();
            if (result && typeof result.then === 'function') {
                result.catch(function(err) {
                    console.debug('SSEConnectionManager: Poll error:', err);
                });
            }
        } catch (err) {
            console.debug('SSEConnectionManager: Poll error:', err);
        }
    };

    // =========================================================================
    // Private Methods - State Management
    // =========================================================================

    /**
     * Set the connection state and notify handlers
     */
    SSEConnectionManager.prototype._setState = function(newState) {
        if (this._state === newState) return;

        var oldState = this._state;
        this._state = newState;

        // Notify state change handlers
        var self = this;
        this._stateChangeHandlers.forEach(function(handler) {
            try {
                handler(newState, oldState);
            } catch (err) {
                console.error('SSEConnectionManager: State change handler error:', err);
            }
        });

        // Dispatch custom event
        this._dispatchEvent('sse:statechange', {
            state: newState,
            previousState: oldState,
            url: this.url
        });
    };

    /**
     * Dispatch a custom event on the document
     */
    SSEConnectionManager.prototype._dispatchEvent = function(name, detail) {
        var event = new CustomEvent(name, {
            detail: detail || {},
            bubbles: true,
            cancelable: true
        });
        document.dispatchEvent(event);
    };

    // =========================================================================
    // Private Methods - Cleanup
    // =========================================================================

    /**
     * Cleanup all resources
     */
    SSEConnectionManager.prototype._cleanup = function() {
        // Clear timers
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }

        this._stopHeartbeatMonitor();
        this._stopPolling();

        // Close EventSource
        if (this._eventSource) {
            this._eventSource.close();
            this._eventSource = null;
        }
    };

    // =========================================================================
    // Static Properties
    // =========================================================================

    SSEConnectionManager.ConnectionState = ConnectionState;
    SSEConnectionManager.DEFAULT_CONFIG = DEFAULT_CONFIG;

    return SSEConnectionManager;
})();

// Expose globally for use by other modules
window.SSEConnectionManager = SSEConnectionManager;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SSEConnectionManager;
}
