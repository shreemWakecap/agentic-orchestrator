/**
 * Live Log Viewer Component
 *
 * Displays job output in real-time with:
 * - Auto-scrolling
 * - Log level filtering
 * - Search/highlight
 * - Download capability
 *
 * Usage:
 *   const viewer = new LogViewerComponent('#log-container', 'job-123', {
 *       maxLines: 5000,
 *       autoScroll: true,
 *       showTimestamps: true,
 *   });
 *
 *   // Later: cleanup
 *   viewer.destroy();
 */

class LogViewerComponent {
    /**
     * Create a log viewer component
     * @param {string|Element} container - Container selector or element
     * @param {string} jobId - Job ID to display logs for
     * @param {Object} options - Component options
     */
    constructor(container, jobId, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        this.jobId = jobId;
        this.options = {
            maxLines: 1000,
            autoScroll: true,
            showTimestamps: true,
            showLevels: true,
            levelFilter: null, // null = show all
            searchTerm: '',
            connectOnInit: true,
            ...options
        };

        this.logs = [];
        this.eventStream = null;
        this.isScrolledToBottom = true;
        this.elements = {};

        if (!this.container) {
            throw new Error('LogViewerComponent: Container not found');
        }

        this.render();

        if (this.options.connectOnInit) {
            this.connect();
        }
    }

    /**
     * Render the component HTML
     */
    render() {
        this.container.innerHTML = `
            <div class="log-viewer">
                <div class="log-viewer-toolbar">
                    <div class="log-viewer-filters">
                        <select class="log-level-filter">
                            <option value="">All Levels</option>
                            <option value="debug">Debug</option>
                            <option value="info">Info</option>
                            <option value="warn">Warning</option>
                            <option value="error">Error</option>
                        </select>
                        <input type="text" class="log-search" placeholder="Search logs...">
                    </div>
                    <div class="log-viewer-controls">
                        <label class="auto-scroll-toggle">
                            <input type="checkbox" ${this.options.autoScroll ? 'checked' : ''}> Auto-scroll
                        </label>
                        <button class="btn btn-sm btn-secondary clear-btn">Clear</button>
                        <button class="btn btn-sm btn-secondary download-btn">Download</button>
                    </div>
                </div>
                <div class="log-viewer-status">
                    <span class="connection-status">Disconnected</span>
                    <span class="log-count">0 lines</span>
                </div>
                <div class="log-viewer-content"></div>
            </div>
        `;

        this.elements = {
            root: this.container.querySelector('.log-viewer'),
            content: this.container.querySelector('.log-viewer-content'),
            levelFilter: this.container.querySelector('.log-level-filter'),
            search: this.container.querySelector('.log-search'),
            autoScrollToggle: this.container.querySelector('.auto-scroll-toggle input'),
            clearBtn: this.container.querySelector('.clear-btn'),
            downloadBtn: this.container.querySelector('.download-btn'),
            connectionStatus: this.container.querySelector('.connection-status'),
            logCount: this.container.querySelector('.log-count'),
        };

        this._attachEventListeners();
    }

    /**
     * Attach DOM event listeners
     * @private
     */
    _attachEventListeners() {
        // Level filter
        this.elements.levelFilter.addEventListener('change', (e) => {
            this.options.levelFilter = e.target.value || null;
            this.renderLogs();
        });

        // Search
        this.elements.search.addEventListener('input', (e) => {
            this.options.searchTerm = e.target.value;
            this.renderLogs();
        });

        // Auto-scroll toggle
        this.elements.autoScrollToggle.addEventListener('change', (e) => {
            this.options.autoScroll = e.target.checked;
            if (this.options.autoScroll) {
                this.scrollToBottom();
            }
        });

        // Clear button
        this.elements.clearBtn.addEventListener('click', () => {
            this.clear();
        });

        // Download button
        this.elements.downloadBtn.addEventListener('click', () => {
            this.download();
        });

        // Scroll detection for auto-scroll
        this.elements.content.addEventListener('scroll', () => {
            const el = this.elements.content;
            this.isScrolledToBottom = (el.scrollHeight - el.scrollTop - el.clientHeight) < 50;
        });

        // Keyboard shortcuts
        this.elements.search.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.elements.search.value = '';
                this.options.searchTerm = '';
                this.renderLogs();
            }
        });
    }

    /**
     * Connect to the event stream
     */
    connect() {
        if (this.eventStream) {
            return;
        }

        this.eventStream = new JobEventStream(this.jobId);

        // Connection state changes
        this.eventStream.on('stateChange', ({ state, attempt, maxAttempts }) => {
            this.updateConnectionStatus(state, attempt, maxAttempts);
        });

        // Log events
        this.eventStream.on('log', (data) => {
            this.addLog({
                level: data.level || 'info',
                message: data.message,
                timestamp: data.timestamp || data.ts,
            });
        });

        // Raw output events
        this.eventStream.on('raw', (data) => {
            this.addLog({
                level: 'info',
                message: data.line || data.message || data.content,
                timestamp: data.timestamp || data.ts,
                type: 'raw',
            });
        });

        // Progress events
        this.eventStream.on('progress', (data) => {
            this.addLog({
                level: 'info',
                message: `[${data.phase}] ${data.percent}%${data.message ? ' - ' + data.message : ''}`,
                timestamp: data.timestamp || data.ts,
                type: 'progress',
            });
        });

        // Checkpoint events
        this.eventStream.on('checkpoint', (data) => {
            this.addLog({
                level: 'info',
                message: `[CHECKPOINT] ${data.id} at ${data.percent}% (${data.phase})`,
                timestamp: data.timestamp || data.ts,
                type: 'checkpoint',
            });
        });

        // Error events
        this.eventStream.on('error', (data) => {
            if (data.message) {
                this.addLog({
                    level: 'error',
                    message: data.message,
                    timestamp: data.timestamp || data.ts,
                    type: 'error',
                });
            }
        });

        // Complete event
        this.eventStream.on('complete', (data) => {
            const status = data.exit_code === 0 ? 'succeeded' : 'failed';
            this.addLog({
                level: data.exit_code === 0 ? 'info' : 'error',
                message: `[COMPLETE] Job ${status} (exit code: ${data.exit_code})`,
                timestamp: data.timestamp || data.ts,
                type: 'complete',
            });
        });

        // Status update events
        this.eventStream.on('status', (data) => {
            if (data.status) {
                this.addLog({
                    level: 'info',
                    message: `[STATUS] ${data.status}`,
                    timestamp: data.timestamp || data.ts,
                    type: 'status',
                });
            }
        });

        this.eventStream.connect();
    }

    /**
     * Add a log entry
     * @param {Object} log - Log entry
     */
    addLog(log) {
        // Parse timestamp
        if (log.timestamp && typeof log.timestamp === 'string') {
            log.timestamp = new Date(log.timestamp);
        } else if (!log.timestamp) {
            log.timestamp = new Date();
        }

        // Normalize level
        log.level = (log.level || 'info').toLowerCase();

        this.logs.push(log);

        // Trim if over max
        if (this.logs.length > this.options.maxLines) {
            const removeCount = this.logs.length - this.options.maxLines;
            this.logs = this.logs.slice(removeCount);
            this.renderLogs();
        } else {
            // Append single log for efficiency
            if (this.matchesFilter(log)) {
                this.appendLogElement(log);
            }
        }

        this.updateLogCount();

        if (this.options.autoScroll && this.isScrolledToBottom) {
            this.scrollToBottom();
        }
    }

    /**
     * Add multiple log entries at once
     * @param {Array} logs - Array of log entries
     */
    addLogs(logs) {
        logs.forEach(log => {
            if (log.timestamp && typeof log.timestamp === 'string') {
                log.timestamp = new Date(log.timestamp);
            } else if (!log.timestamp) {
                log.timestamp = new Date();
            }
            log.level = (log.level || 'info').toLowerCase();
            this.logs.push(log);
        });

        // Trim if over max
        if (this.logs.length > this.options.maxLines) {
            this.logs = this.logs.slice(-this.options.maxLines);
        }

        this.renderLogs();

        if (this.options.autoScroll) {
            this.scrollToBottom();
        }
    }

    /**
     * Render all logs
     */
    renderLogs() {
        const filtered = this.getFilteredLogs();
        this.elements.content.innerHTML = filtered.map(log => this.formatLogElement(log)).join('');
        this.updateLogCount();
    }

    /**
     * Append a single log element
     * @param {Object} log - Log entry
     */
    appendLogElement(log) {
        this.elements.content.insertAdjacentHTML('beforeend', this.formatLogElement(log));
    }

    /**
     * Format a log entry as HTML
     * @param {Object} log - Log entry
     * @returns {string} - HTML string
     */
    formatLogElement(log) {
        const levelClass = `log-level-${log.level}`;
        const typeClass = log.type ? `log-type-${log.type}` : '';

        const timestamp = this.options.showTimestamps
            ? `<span class="log-timestamp">${this.formatTimestamp(log.timestamp)}</span>`
            : '';

        const level = this.options.showLevels
            ? `<span class="log-level ${levelClass}">${log.level.toUpperCase().padEnd(5)}</span>`
            : '';

        const message = this.highlightSearch(this.escapeHtml(log.message));

        return `<div class="log-line ${levelClass} ${typeClass}">${timestamp}${level}<span class="log-message">${message}</span></div>`;
    }

    /**
     * Get filtered logs
     * @returns {Array} - Filtered log entries
     */
    getFilteredLogs() {
        return this.logs.filter(log => this.matchesFilter(log));
    }

    /**
     * Check if a log matches current filters
     * @param {Object} log - Log entry
     * @returns {boolean} - True if matches
     */
    matchesFilter(log) {
        // Level filter
        if (this.options.levelFilter && log.level !== this.options.levelFilter) {
            return false;
        }

        // Search filter
        if (this.options.searchTerm) {
            const searchLower = this.options.searchTerm.toLowerCase();
            if (!log.message.toLowerCase().includes(searchLower)) {
                return false;
            }
        }

        return true;
    }

    /**
     * Highlight search term in text
     * @param {string} text - Text to highlight
     * @returns {string} - Text with highlights
     */
    highlightSearch(text) {
        if (!this.options.searchTerm) {
            return text;
        }
        const regex = new RegExp(`(${this.escapeRegex(this.options.searchTerm)})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    /**
     * Update connection status display
     * @param {string} state - Connection state
     * @param {number} attempt - Reconnection attempt number
     * @param {number} maxAttempts - Maximum reconnection attempts
     */
    updateConnectionStatus(state, attempt, maxAttempts) {
        const statusMap = {
            'connecting': 'Connecting...',
            'connected': 'Connected',
            'reconnecting': `Reconnecting (${attempt}/${maxAttempts})...`,
            'disconnected': 'Disconnected',
            'failed': 'Connection failed',
        };
        this.elements.connectionStatus.textContent = statusMap[state] || state;
        this.elements.connectionStatus.className = `connection-status status-${state}`;
    }

    /**
     * Update log count display
     */
    updateLogCount() {
        const filtered = this.getFilteredLogs().length;
        const total = this.logs.length;
        if (filtered === total) {
            this.elements.logCount.textContent = `${total} lines`;
        } else {
            this.elements.logCount.textContent = `${filtered}/${total} lines`;
        }
    }

    /**
     * Scroll to bottom of log content
     */
    scrollToBottom() {
        requestAnimationFrame(() => {
            this.elements.content.scrollTop = this.elements.content.scrollHeight;
        });
    }

    /**
     * Clear all logs
     */
    clear() {
        this.logs = [];
        this.elements.content.innerHTML = '';
        this.updateLogCount();
    }

    /**
     * Download logs as text file
     */
    download() {
        const content = this.logs.map(log => {
            const ts = this.formatTimestamp(log.timestamp);
            const level = log.level.toUpperCase().padEnd(5);
            return `[${ts}] [${level}] ${log.message}`;
        }).join('\n');

        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `job-${this.jobId}-logs-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Disconnect from event stream
     */
    disconnect() {
        if (this.eventStream) {
            this.eventStream.disconnect();
            this.eventStream = null;
        }
    }

    /**
     * Destroy the component
     */
    destroy() {
        this.disconnect();
        this.container.innerHTML = '';
    }

    /**
     * Format timestamp for display
     * @param {Date} date - Date object
     * @returns {string} - Formatted timestamp
     */
    formatTimestamp(date) {
        if (!(date instanceof Date)) {
            date = new Date(date);
        }
        return date.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        }) + '.' + String(date.getMilliseconds()).padStart(3, '0');
    }

    /**
     * Escape HTML special characters
     * @param {string} text - Text to escape
     * @returns {string} - Escaped text
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Escape regex special characters
     * @param {string} string - String to escape
     * @returns {string} - Escaped string
     */
    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * Set filter programmatically
     * @param {string} level - Level filter
     */
    setLevelFilter(level) {
        this.options.levelFilter = level || null;
        this.elements.levelFilter.value = level || '';
        this.renderLogs();
    }

    /**
     * Set search term programmatically
     * @param {string} term - Search term
     */
    setSearchTerm(term) {
        this.options.searchTerm = term;
        this.elements.search.value = term;
        this.renderLogs();
    }

    /**
     * Get all logs
     * @returns {Array} - All log entries
     */
    getLogs() {
        return this.logs;
    }

    /**
     * Check if connected to stream
     * @returns {boolean} - True if connected
     */
    isConnected() {
        return this.eventStream && this.eventStream.isConnected();
    }
}

// Export
window.LogViewerComponent = LogViewerComponent;
