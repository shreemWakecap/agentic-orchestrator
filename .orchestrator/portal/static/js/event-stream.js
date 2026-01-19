/**
 * Event Stream Client
 *
 * Wraps EventSource with:
 * - Automatic reconnection with exponential backoff
 * - Event type handling
 * - Connection state management
 * - Last-Event-ID tracking for replay
 *
 * Usage:
 *   const stream = new JobEventStream('job-123');
 *
 *   stream.on('progress', (data) => {
 *       console.log(`Progress: ${data.percent}%`);
 *   });
 *
 *   stream.on('log', (data) => {
 *       console.log(`[${data.level}] ${data.message}`);
 *   });
 *
 *   stream.on('stateChange', ({ state }) => {
 *       console.log(`Connection: ${state}`);
 *   });
 *
 *   stream.connect();
 *
 *   // Later: cleanup
 *   stream.disconnect();
 */

class JobEventStream {
    /**
     * Create an event stream for a job
     * @param {string} jobId - Job ID to stream
     * @param {Object} options - Stream options
     */
    constructor(jobId, options = {}) {
        this.jobId = jobId;
        this.options = {
            baseUrl: '/api/jobs',
            reconnectDelay: 1000,
            maxReconnectDelay: 30000,
            maxReconnectAttempts: 10,
            ...options
        };

        this.eventSource = null;
        this.handlers = new Map();
        this.lastEventId = 0;
        this.reconnectAttempts = 0;
        this.state = 'disconnected';
        this.manualClose = false;
        this.reconnectTimeout = null;
    }

    // =========================================================================
    // Connection Management
    // =========================================================================

    /**
     * Connect to the event stream
     */
    connect() {
        if (this.eventSource) {
            return;
        }

        this.manualClose = false;
        this._createConnection();
    }

    /**
     * Create the EventSource connection
     * @private
     */
    _createConnection() {
        const url = `${this.options.baseUrl}/${this.jobId}/stream`;

        try {
            this.eventSource = new EventSource(url);
            this.state = 'connecting';
            this._emit('stateChange', { state: this.state });

            this.eventSource.onopen = () => {
                this.state = 'connected';
                this.reconnectAttempts = 0;
                this._emit('stateChange', { state: this.state });
                this._emit('connected', {});
            };

            this.eventSource.onerror = (error) => {
                this._emit('error', { error });

                if (this.eventSource.readyState === EventSource.CLOSED) {
                    this.state = 'disconnected';
                    this._emit('stateChange', { state: this.state });

                    if (!this.manualClose) {
                        this._scheduleReconnect();
                    }
                }
            };

            // Register all event types
            const eventTypes = [
                'connected',
                'status',
                'progress',
                'log',
                'checkpoint',
                'error',
                'complete',
                'raw',
                'heartbeat'
            ];

            eventTypes.forEach(type => {
                this.eventSource.addEventListener(type, (event) => {
                    this._handleEvent(type, event);
                });
            });

            // Also handle generic messages
            this.eventSource.onmessage = (event) => {
                this._handleEvent('message', event);
            };
        } catch (error) {
            console.error('Failed to create EventSource:', error);
            this.state = 'disconnected';
            this._emit('stateChange', { state: this.state });
            this._emit('error', { error });

            if (!this.manualClose) {
                this._scheduleReconnect();
            }
        }
    }

    /**
     * Handle incoming event
     * @private
     * @param {string} type - Event type
     * @param {MessageEvent} event - SSE event
     */
    _handleEvent(type, event) {
        // Track last event ID for reconnection
        if (event.lastEventId) {
            this.lastEventId = parseInt(event.lastEventId, 10) || this.lastEventId;
        }

        // Parse data
        let data;
        try {
            data = JSON.parse(event.data);
        } catch (e) {
            data = { message: event.data };
        }

        // Add metadata
        data._eventId = event.lastEventId;
        data._eventType = type;

        // Emit to specific handlers
        this._emit(type, data);

        // Emit to wildcard handler
        this._emit('*', { type, data });
    }

    /**
     * Schedule a reconnection attempt
     * @private
     */
    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.state = 'failed';
            this._emit('stateChange', { state: this.state });
            this._emit('reconnectFailed', { attempts: this.reconnectAttempts });
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.options.maxReconnectDelay
        );

        this.state = 'reconnecting';
        this._emit('stateChange', {
            state: this.state,
            attempt: this.reconnectAttempts,
            delay,
            maxAttempts: this.options.maxReconnectAttempts
        });

        this.reconnectTimeout = setTimeout(() => {
            if (!this.manualClose) {
                this._cleanup();
                this._createConnection();
            }
        }, delay);
    }

    /**
     * Disconnect from the event stream
     */
    disconnect() {
        this.manualClose = true;
        this._cleanup();
        this.state = 'disconnected';
        this._emit('stateChange', { state: this.state });
        this._emit('disconnected', {});
    }

    /**
     * Clean up resources
     * @private
     */
    _cleanup() {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    // =========================================================================
    // Event Handling
    // =========================================================================

    /**
     * Register an event handler
     * @param {string} event - Event name
     * @param {Function} handler - Handler function
     * @returns {JobEventStream} - For chaining
     */
    on(event, handler) {
        if (!this.handlers.has(event)) {
            this.handlers.set(event, []);
        }
        this.handlers.get(event).push(handler);
        return this;
    }

    /**
     * Remove an event handler
     * @param {string} event - Event name
     * @param {Function} handler - Handler to remove
     * @returns {JobEventStream} - For chaining
     */
    off(event, handler) {
        const handlers = this.handlers.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
        return this;
    }

    /**
     * Register a one-time event handler
     * @param {string} event - Event name
     * @param {Function} handler - Handler function
     * @returns {JobEventStream} - For chaining
     */
    once(event, handler) {
        const wrappedHandler = (data) => {
            this.off(event, wrappedHandler);
            handler(data);
        };
        return this.on(event, wrappedHandler);
    }

    /**
     * Emit an event to all registered handlers
     * @private
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    _emit(event, data) {
        const handlers = this.handlers.get(event) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (e) {
                console.error(`Error in event handler for ${event}:`, e);
            }
        });
    }

    // =========================================================================
    // State Queries
    // =========================================================================

    /**
     * Check if connected
     * @returns {boolean} - True if connected
     */
    isConnected() {
        return this.state === 'connected';
    }

    /**
     * Get current connection state
     * @returns {string} - Connection state
     */
    getState() {
        return this.state;
    }

    /**
     * Get last event ID
     * @returns {number} - Last event ID
     */
    getLastEventId() {
        return this.lastEventId;
    }

    /**
     * Get reconnection attempt count
     * @returns {number} - Attempt count
     */
    getReconnectAttempts() {
        return this.reconnectAttempts;
    }

    /**
     * Reset reconnection counter (useful after manual recovery)
     */
    resetReconnectCounter() {
        this.reconnectAttempts = 0;
    }
}

// Export
window.JobEventStream = JobEventStream;
