/**
 * Log Streaming Module
 *
 * Provides log streaming, auto-scroll, and filtering functionality
 * for real-time log viewing in the SDLC Orchestrator.
 */

const LogsModule = {
    // Configuration
    config: {
        autoScroll: true,
        maxLogEntries: 1000,
        reconnectDelay: 3000,
        reconnectAttempts: 5
    },

    // State
    state: {
        eventSource: null,
        logEntries: [],
        filters: {
            types: new Set(),
            searchTerm: ''
        },
        reconnectCount: 0,
        isConnected: false
    },

    // DOM Elements
    elements: {
        logContainer: null,
        autoScrollToggle: null,
        filterTypeSelect: null,
        searchInput: null,
        connectionStatus: null,
        clearButton: null
    },

    /**
     * Initialize the logs module
     * @param {Object} options - Configuration options
     * @param {string} options.containerId - ID of the log container element
     * @param {string} [options.runId] - Run ID for SSE connection
     * @param {string} [options.runStatus] - Current run status
     */
    init(options = {}) {
        this.cacheElements(options.containerId);
        this.bindEvents();

        // Start streaming if run is active
        if (options.runId && (options.runStatus === 'running' || options.runStatus === 'pending')) {
            this.startStreaming(options.runId);
        }

        // Load any existing log entries from DOM
        this.loadExistingEntries();
    },

    /**
     * Cache DOM element references
     * @param {string} containerId - ID of the main log container
     */
    cacheElements(containerId) {
        this.elements.logContainer = document.getElementById(containerId || 'events-log');
        this.elements.autoScrollToggle = document.getElementById('auto-scroll-toggle');
        this.elements.filterTypeSelect = document.getElementById('log-type-filter');
        this.elements.searchInput = document.getElementById('log-search');
        this.elements.connectionStatus = document.getElementById('connection-status');
        this.elements.clearButton = document.getElementById('clear-logs');
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Auto-scroll toggle
        if (this.elements.autoScrollToggle) {
            this.elements.autoScrollToggle.addEventListener('change', (e) => {
                this.config.autoScroll = e.target.checked;
            });
        }

        // Type filter
        if (this.elements.filterTypeSelect) {
            this.elements.filterTypeSelect.addEventListener('change', (e) => {
                this.setTypeFilter(e.target.value);
            });
        }

        // Search input with debounce
        if (this.elements.searchInput) {
            let debounceTimer;
            this.elements.searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    this.setSearchFilter(e.target.value);
                }, 300);
            });
        }

        // Clear logs button
        if (this.elements.clearButton) {
            this.elements.clearButton.addEventListener('click', () => {
                this.clearLogs();
            });
        }

        // Handle visibility change for reconnection
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && !this.state.isConnected && this.state.eventSource) {
                this.reconnect();
            }
        });
    },

    /**
     * Load existing log entries from DOM
     */
    loadExistingEntries() {
        if (!this.elements.logContainer) return;

        const existingEntries = this.elements.logContainer.querySelectorAll('[data-log-entry]');
        existingEntries.forEach(entry => {
            this.state.logEntries.push({
                element: entry,
                type: entry.dataset.logType || 'info',
                timestamp: entry.dataset.logTimestamp || '',
                message: entry.textContent
            });
        });
    },

    /**
     * Start SSE streaming for a run
     * @param {string} runId - The run ID to stream events from
     */
    startStreaming(runId) {
        if (this.state.eventSource) {
            this.state.eventSource.close();
        }

        const url = `/api/runs/${runId}/events`;
        this.state.eventSource = new EventSource(url);
        this.state.reconnectCount = 0;

        this.state.eventSource.onopen = () => {
            this.state.isConnected = true;
            this.state.reconnectCount = 0;
            this.updateConnectionStatus('connected');
        };

        this.state.eventSource.onmessage = (e) => {
            this.handleEvent(JSON.parse(e.data));
        };

        this.state.eventSource.onerror = () => {
            this.state.isConnected = false;
            this.updateConnectionStatus('disconnected');
            this.handleConnectionError();
        };
    },

    /**
     * Stop streaming
     */
    stopStreaming() {
        if (this.state.eventSource) {
            this.state.eventSource.close();
            this.state.eventSource = null;
        }
        this.state.isConnected = false;
        this.updateConnectionStatus('disconnected');
    },

    /**
     * Handle incoming SSE event
     * @param {Object} event - The event data
     */
    handleEvent(event) {
        // Check for completion
        if (event.type === 'done') {
            this.stopStreaming();
            this.dispatchCustomEvent('streamComplete', { status: event.status });
        }

        // Add log entry
        this.addLogEntry(event);

        // Dispatch event for external listeners
        this.dispatchCustomEvent('logEvent', event);
    },

    /**
     * Add a log entry to the display
     * @param {Object} event - The event to add
     */
    addLogEntry(event) {
        if (!this.elements.logContainer) return;

        // Enforce max entries limit
        if (this.state.logEntries.length >= this.config.maxLogEntries) {
            const oldEntry = this.state.logEntries.shift();
            if (oldEntry.element && oldEntry.element.parentNode) {
                oldEntry.element.parentNode.removeChild(oldEntry.element);
            }
        }

        // Create log entry element
        const entryDiv = document.createElement('div');
        entryDiv.className = 'px-4 py-3 text-sm fade-in';
        entryDiv.dataset.logEntry = 'true';
        entryDiv.dataset.logType = event.type || 'info';
        entryDiv.dataset.logTimestamp = event.timestamp || new Date().toISOString();

        // Determine badge styling based on event type
        const badgeClass = this.getBadgeClass(event.type);

        // Build content
        const timestamp = event.timestamp || new Date().toISOString().slice(0, 19);
        let content = `<span class="text-gray-500">${this.escapeHtml(timestamp)}</span>`;
        content += `<span class="ml-2 px-2 py-0.5 rounded text-xs font-medium ${badgeClass}">${this.escapeHtml(event.type || 'info')}</span>`;

        if (event.step) {
            content += `<span class="ml-2 text-gray-700">${this.escapeHtml(event.step)}</span>`;
        }

        if (event.message) {
            content += `<span class="ml-2 text-gray-700">${this.escapeHtml(event.message)}</span>`;
        }

        entryDiv.innerHTML = content;

        // Store entry
        const entry = {
            element: entryDiv,
            type: event.type || 'info',
            timestamp: timestamp,
            step: event.step || '',
            message: event.message || ''
        };
        this.state.logEntries.push(entry);

        // Apply filters before adding to DOM
        if (this.shouldShowEntry(entry)) {
            this.elements.logContainer.appendChild(entryDiv);

            // Auto-scroll if enabled
            if (this.config.autoScroll) {
                this.scrollToBottom();
            }
        } else {
            entryDiv.style.display = 'none';
            this.elements.logContainer.appendChild(entryDiv);
        }
    },

    /**
     * Get badge CSS class based on event type
     * @param {string} type - Event type
     * @returns {string} CSS classes for the badge
     */
    getBadgeClass(type) {
        const typeClasses = {
            'error': 'bg-red-100 text-red-800',
            'complete': 'bg-green-100 text-green-800',
            'done': 'bg-green-100 text-green-800',
            'warning': 'bg-yellow-100 text-yellow-800',
            'info': 'bg-blue-100 text-blue-800',
            'debug': 'bg-purple-100 text-purple-800'
        };
        return typeClasses[type] || 'bg-gray-100 text-gray-800';
    },

    /**
     * Set type filter
     * @param {string} type - Type to filter by (empty for all)
     */
    setTypeFilter(type) {
        this.state.filters.types.clear();
        if (type) {
            this.state.filters.types.add(type);
        }
        this.applyFilters();
    },

    /**
     * Set search filter
     * @param {string} term - Search term
     */
    setSearchFilter(term) {
        this.state.filters.searchTerm = term.toLowerCase();
        this.applyFilters();
    },

    /**
     * Check if entry should be shown based on current filters
     * @param {Object} entry - Log entry to check
     * @returns {boolean} Whether entry should be shown
     */
    shouldShowEntry(entry) {
        // Check type filter
        if (this.state.filters.types.size > 0 && !this.state.filters.types.has(entry.type)) {
            return false;
        }

        // Check search filter
        if (this.state.filters.searchTerm) {
            const searchContent = `${entry.type} ${entry.step} ${entry.message}`.toLowerCase();
            if (!searchContent.includes(this.state.filters.searchTerm)) {
                return false;
            }
        }

        return true;
    },

    /**
     * Apply current filters to all log entries
     */
    applyFilters() {
        this.state.logEntries.forEach(entry => {
            if (entry.element) {
                entry.element.style.display = this.shouldShowEntry(entry) ? '' : 'none';
            }
        });
    },

    /**
     * Clear all log entries
     */
    clearLogs() {
        if (this.elements.logContainer) {
            this.elements.logContainer.innerHTML = '';
        }
        this.state.logEntries = [];
    },

    /**
     * Scroll log container to bottom
     */
    scrollToBottom() {
        if (this.elements.logContainer) {
            this.elements.logContainer.scrollTop = this.elements.logContainer.scrollHeight;
        }
    },

    /**
     * Handle connection errors with retry logic
     */
    handleConnectionError() {
        if (this.state.reconnectCount < this.config.reconnectAttempts) {
            this.state.reconnectCount++;
            setTimeout(() => {
                this.reconnect();
            }, this.config.reconnectDelay);
        } else {
            console.log('Max reconnection attempts reached');
            this.dispatchCustomEvent('connectionFailed', { attempts: this.state.reconnectCount });
        }
    },

    /**
     * Attempt to reconnect
     */
    reconnect() {
        if (this.state.eventSource && this.state.eventSource.url) {
            const runId = this.state.eventSource.url.match(/\/api\/runs\/([^/]+)\/events/)?.[1];
            if (runId) {
                this.startStreaming(runId);
            }
        }
    },

    /**
     * Update connection status indicator
     * @param {string} status - 'connected' or 'disconnected'
     */
    updateConnectionStatus(status) {
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.className = status === 'connected'
                ? 'inline-block w-2 h-2 rounded-full bg-green-500'
                : 'inline-block w-2 h-2 rounded-full bg-red-500';
            this.elements.connectionStatus.title = status === 'connected'
                ? 'Connected to event stream'
                : 'Disconnected from event stream';
        }
    },

    /**
     * Dispatch custom event for external listeners
     * @param {string} name - Event name
     * @param {Object} detail - Event detail data
     */
    dispatchCustomEvent(name, detail) {
        const event = new CustomEvent(`logs:${name}`, { detail });
        document.dispatchEvent(event);
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
     * Get current log entries (for export/debugging)
     * @returns {Array} Array of log entry objects
     */
    getEntries() {
        return this.state.logEntries.map(entry => ({
            type: entry.type,
            timestamp: entry.timestamp,
            step: entry.step,
            message: entry.message
        }));
    },

    /**
     * Export logs as JSON
     * @returns {string} JSON string of log entries
     */
    exportAsJson() {
        return JSON.stringify(this.getEntries(), null, 2);
    },

    /**
     * Export logs as plain text
     * @returns {string} Plain text log output
     */
    exportAsText() {
        return this.getEntries()
            .map(entry => `[${entry.timestamp}] [${entry.type.toUpperCase()}] ${entry.step ? entry.step + ': ' : ''}${entry.message}`)
            .join('\n');
    }
};

// Auto-initialize from data attributes on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    const pageContainer = document.getElementById('run-detail-page') || document.querySelector('[data-logs-init]');

    if (pageContainer) {
        const runStatus = pageContainer.dataset.runStatus;
        const runId = pageContainer.dataset.runId;
        const containerId = pageContainer.dataset.logsContainer || 'events-log';

        LogsModule.init({
            containerId: containerId,
            runId: runId,
            runStatus: runStatus
        });
    }
});

// Expose globally for onclick handlers and external access
window.LogsModule = LogsModule;
