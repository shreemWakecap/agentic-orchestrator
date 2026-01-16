/**
 * Build Progress Module
 *
 * Handles build/run progress tracking including:
 * - Status badge updates
 * - Progress bar updates
 * - Current step display
 * - SSE (Server-Sent Events) for real-time updates
 *
 * DOM Requirements:
 * - #status-badge - Status badge element
 * - #progress-bar - Progress bar element
 * - #progress-percent - Progress percentage text
 * - #current-step - Current step text (optional)
 * - #events-log - Events log container (optional)
 *
 * Data Attributes:
 * - data-run-status - Initial run status (on container)
 * - data-run-id - Run ID for SSE connection (on container)
 */

const BuildProgress = (function() {
    'use strict';

    // Configuration
    const config = {
        statusClasses: {
            completed: { bg: 'bg-green-100', text: 'text-green-800' },
            running: { bg: 'bg-blue-100', text: 'text-blue-800' },
            pending: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
            failed: { bg: 'bg-red-100', text: 'text-red-800' },
            error: { bg: 'bg-red-100', text: 'text-red-800' }
        },
        eventBadgeClasses: {
            error: 'bg-red-100 text-red-800',
            complete: 'bg-green-100 text-green-800',
            done: 'bg-green-100 text-green-800',
            warning: 'bg-yellow-100 text-yellow-800',
            info: 'bg-blue-100 text-blue-800',
            default: 'bg-gray-100 text-gray-800'
        }
    };

    // State
    let eventSource = null;
    let runId = null;
    let isConnected = false;

    // DOM element references
    const elements = {
        statusBadge: null,
        progressBar: null,
        progressPercent: null,
        currentStep: null,
        eventsLog: null
    };

    /**
     * Initialize the module
     * @param {Object} options - Configuration options
     * @param {string} options.runId - Run ID for SSE connection
     * @param {string} options.runStatus - Current run status
     * @param {string} [options.containerId] - Optional container ID for element lookup
     */
    function init(options) {
        if (!options) {
            options = {};
        }

        cacheElements(options.containerId);

        runId = options.runId;
        const status = options.runStatus;

        // Start streaming if run is active
        if (runId && (status === 'running' || status === 'pending')) {
            startStreaming(runId);
        }
    }

    /**
     * Cache DOM element references
     * @param {string} [containerId] - Optional container ID
     */
    function cacheElements(containerId) {
        const container = containerId ? document.getElementById(containerId) : document;

        elements.statusBadge = document.getElementById('status-badge');
        elements.progressBar = document.getElementById('progress-bar');
        elements.progressPercent = document.getElementById('progress-percent');
        elements.currentStep = document.getElementById('current-step');
        elements.eventsLog = document.getElementById('events-log');
    }

    /**
     * Start SSE streaming for a run
     * @param {string} id - The run ID to stream events from
     */
    function startStreaming(id) {
        if (eventSource) {
            eventSource.close();
        }

        runId = id;
        const url = '/api/runs/' + runId + '/events';
        eventSource = new EventSource(url);

        eventSource.onopen = function() {
            isConnected = true;
            dispatchEvent('connected', { runId: runId });
        };

        eventSource.onmessage = function(e) {
            const event = JSON.parse(e.data);
            handleEvent(event);
        };

        eventSource.onerror = function() {
            console.log('SSE connection closed');
            isConnected = false;
            stopStreaming();
            dispatchEvent('disconnected', { runId: runId });
        };
    }

    /**
     * Stop streaming
     */
    function stopStreaming() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        isConnected = false;
    }

    /**
     * Handle incoming SSE event
     * @param {Object} event - The event data
     */
    function handleEvent(event) {
        // Update status on completion
        if (event.type === 'done') {
            updateStatus(event.status);
            stopStreaming();
            dispatchEvent('complete', { status: event.status });
        }

        // Update progress
        if (event.progress !== undefined) {
            updateProgress(event.progress);
        }

        // Update current step
        if (event.step) {
            updateCurrentStep(event.step);
        }

        // Add event to log
        addEventToLog(event);

        // Dispatch event for external listeners
        dispatchEvent('event', event);
    }

    /**
     * Update the status badge
     * @param {string} status - The new status
     */
    function updateStatus(status) {
        if (!elements.statusBadge) return;

        elements.statusBadge.textContent = status;

        // Remove existing status classes
        const classRegex = /bg-\w+-100|text-\w+-800/g;
        elements.statusBadge.className = elements.statusBadge.className.replace(classRegex, '').trim();

        // Add new status classes
        const statusConfig = config.statusClasses[status] || config.statusClasses.error;
        elements.statusBadge.classList.add(statusConfig.bg, statusConfig.text);
    }

    /**
     * Update the progress bar
     * @param {number} progress - Progress percentage (0-100)
     */
    function updateProgress(progress) {
        const percent = Math.max(0, Math.min(100, progress));

        if (elements.progressBar) {
            elements.progressBar.style.width = percent + '%';
        }

        if (elements.progressPercent) {
            elements.progressPercent.textContent = percent + '%';
        }
    }

    /**
     * Update the current step display
     * @param {string} step - The current step text
     */
    function updateCurrentStep(step) {
        if (elements.currentStep) {
            elements.currentStep.textContent = step;
        }
    }

    /**
     * Add an event to the log container
     * @param {Object} event - The event to add
     */
    function addEventToLog(event) {
        if (!elements.eventsLog) return;

        const eventDiv = document.createElement('div');
        eventDiv.className = 'px-4 py-3 text-sm fade-in';

        const badgeClass = config.eventBadgeClasses[event.type] || config.eventBadgeClasses.default;
        const timestamp = event.timestamp || new Date().toISOString().slice(0, 19);

        let content = '<span class="text-gray-500">' + escapeHtml(timestamp) + '</span>';
        content += '<span class="ml-2 px-2 py-0.5 rounded text-xs font-medium ' + badgeClass + '">' + escapeHtml(event.type || 'info') + '</span>';

        if (event.step) {
            content += '<span class="ml-2 text-gray-700">' + escapeHtml(event.step) + '</span>';
        }

        if (event.message) {
            content += '<span class="ml-2 text-gray-700">' + escapeHtml(event.message) + '</span>';
        }

        eventDiv.innerHTML = content;
        elements.eventsLog.appendChild(eventDiv);
        elements.eventsLog.scrollTop = elements.eventsLog.scrollHeight;
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Dispatch custom event for external listeners
     * @param {string} name - Event name
     * @param {Object} detail - Event detail data
     */
    function dispatchEvent(name, detail) {
        const event = new CustomEvent('buildProgress:' + name, { detail: detail });
        document.dispatchEvent(event);
    }

    /**
     * Get current connection state
     * @returns {boolean} Whether connected to event stream
     */
    function isStreamConnected() {
        return isConnected;
    }

    /**
     * Get current run ID
     * @returns {string|null} The current run ID
     */
    function getRunId() {
        return runId;
    }

    /**
     * Manually set progress (for testing or external updates)
     * @param {number} progress - Progress percentage
     */
    function setProgress(progress) {
        updateProgress(progress);
    }

    /**
     * Manually set status (for testing or external updates)
     * @param {string} status - Status string
     */
    function setStatus(status) {
        updateStatus(status);
    }

    // Public API
    return {
        init: init,
        startStreaming: startStreaming,
        stopStreaming: stopStreaming,
        updateStatus: updateStatus,
        updateProgress: updateProgress,
        updateCurrentStep: updateCurrentStep,
        addEventToLog: addEventToLog,
        isConnected: isStreamConnected,
        getRunId: getRunId,
        setProgress: setProgress,
        setStatus: setStatus,
        escapeHtml: escapeHtml
    };
})();

// Auto-initialize from data attributes on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    const pageContainer = document.getElementById('run-detail-page') || document.querySelector('[data-build-progress-init]');

    if (pageContainer) {
        const runStatus = pageContainer.dataset.runStatus;
        const runId = pageContainer.dataset.runId;

        BuildProgress.init({
            runId: runId,
            runStatus: runStatus,
            containerId: pageContainer.id
        });
    }
});

// Expose globally for external access
window.BuildProgress = BuildProgress;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BuildProgress;
}
