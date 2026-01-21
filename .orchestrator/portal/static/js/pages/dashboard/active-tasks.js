/**
 * Active Tasks Dashboard Module
 *
 * Handles real-time task progress updates via SSE and polling.
 * Supports planning tasks (gray/disabled) and building tasks (active).
 *
 * Features:
 * - SSE connection management for real-time updates
 * - Polling fallback when SSE is unavailable
 * - Task card updates (progress, status, phase)
 * - Activity log management
 * - Elapsed time updates
 *
 * Dependencies:
 * - CoreUtils (core/utils.js) - for escapeHtml, formatElapsedClock
 * - Toast (toast.js) - for notifications (optional)
 *
 * DOM Requirements:
 * - .active-task-card elements with data-run-id, data-run-status
 * - .planning-task-card elements for planning tasks
 * - #active-tasks-indicator for status indicator
 * - #task-activity-log-panel for activity log
 *
 * @module ActiveTasks
 */

const ActiveTasks = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        pollInterval: 3000,           // Poll every 3 seconds
        elapsedUpdateInterval: 1000,  // Update elapsed time every second
        logMaxLines: 200              // Maximum log lines to keep
    };

    // =========================================================================
    // State
    // =========================================================================

    let eventSources = {};
    let pollTimer = null;
    let elapsedTimer = null;
    let logAutoScroll = true;
    let activityLogVisible = false;
    let isInitialized = false;

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the Active Tasks module
     */
    function init() {
        if (isInitialized) return;

        var taskCards = document.querySelectorAll('.active-task-card');
        var planningCards = document.querySelectorAll('.planning-task-card');

        if (taskCards.length === 0 && planningCards.length === 0) {
            hideIndicator();
        } else {
            showIndicator();
        }

        // Start SSE connections for active tasks
        taskCards.forEach(function(card) {
            var runId = card.dataset.runId;
            var status = card.dataset.runStatus;

            if (status === 'running' || status === 'pending') {
                startSSE(runId, card);
            }
        });

        startElapsedTimer();
        setupRefreshButton();
        setupLogPanelToggle();
        setupLogControls();
        startPolling();

        // Log TaskActivityPanel status
        if (typeof TaskActivityPanel !== 'undefined') {
            console.log('[ActiveTasks] TaskActivityPanel module loaded');
        }

        isInitialized = true;
    }

    // =========================================================================
    // SSE Connection Management
    // =========================================================================

    /**
     * Start SSE connection for a run
     * @param {string} runId - Run identifier
     * @param {HTMLElement} card - Task card element
     */
    function startSSE(runId, card) {
        // Close existing connection if any
        if (eventSources[runId]) {
            eventSources[runId].close();
        }

        var url = '/api/runs/' + runId + '/events';
        var es = new EventSource(url);

        es.onmessage = function(e) {
            try {
                var event = JSON.parse(e.data);
                updateTaskCard(card, event);
                appendLogLine(event);
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        };

        es.onerror = function() {
            console.log('SSE connection closed for run:', runId);
            es.close();
            delete eventSources[runId];
        };

        eventSources[runId] = es;
    }

    // =========================================================================
    // Task Card Updates
    // =========================================================================

    /**
     * Update a task card with event data
     * @param {HTMLElement} card - Task card element
     * @param {Object} event - Event data from SSE
     */
    function updateTaskCard(card, event) {
        // Update progress bar
        if (event.progress !== undefined) {
            var progressBar = card.querySelector('.progress-bar');
            var progressPercent = card.querySelector('.progress-percent');

            if (progressBar) {
                progressBar.style.width = event.progress + '%';
            }
            if (progressPercent) {
                progressPercent.textContent = event.progress + '%';
            }
        }

        // Update current step
        if (event.step) {
            var stepEl = card.querySelector('.current-step');
            if (stepEl) {
                stepEl.textContent = event.step;
            }
        }

        // Update phase indicators
        if (event.phase) {
            updatePhaseIndicators(card, event.phase);
        }

        // Update status badge
        if (event.status) {
            var badge = card.querySelector('.status-badge');
            if (badge) {
                var textContent = event.status.charAt(0).toUpperCase() + event.status.slice(1);
                badge.innerHTML = '<span class="status-dot"></span>' + textContent;
                updateStatusBadgeClasses(badge, event.status);
            }
            card.dataset.runStatus = event.status;
        }

        // Handle completion
        if (event.type === 'done' || event.type === 'completed') {
            var runId = card.dataset.runId;
            if (eventSources[runId]) {
                eventSources[runId].close();
                delete eventSources[runId];
            }

            setTimeout(function() {
                card.style.opacity = '0.6';
                setTimeout(function() {
                    refreshTasks();
                }, 2000);
            }, 1000);
        }
    }

    /**
     * Update phase indicator badges on a task card
     * @param {HTMLElement} card - Task card element
     * @param {string} currentPhase - Current phase name
     */
    function updatePhaseIndicators(card, currentPhase) {
        var phases = ['planning', 'initializing', 'executing', 'validating', 'completing', 'completed'];
        var phaseIndex = phases.indexOf(currentPhase);

        var badges = card.querySelectorAll('.task-phase-badge');
        var connectors = card.querySelectorAll('.task-phase-connector');

        badges.forEach(function(badge, index) {
            badge.classList.remove('pending', 'active', 'completed');
            if (index < phaseIndex) {
                badge.classList.add('completed');
            } else if (index === phaseIndex) {
                badge.classList.add('active');
            } else {
                badge.classList.add('pending');
            }
        });

        connectors.forEach(function(connector, index) {
            connector.classList.remove('completed', 'active');
            if (index < phaseIndex) {
                connector.classList.add('completed');
            } else if (index === phaseIndex) {
                connector.classList.add('active');
            }
        });
    }

    /**
     * Update status badge CSS classes based on status
     * @param {HTMLElement} badge - Badge element
     * @param {string} status - Status string
     */
    function updateStatusBadgeClasses(badge, status) {
        var statusClasses = {
            completed: 'status-badge-completed',
            running: 'status-badge-running',
            pending: 'status-badge-pending',
            planning: 'status-badge-pending',
            failed: 'status-badge-failed',
            error: 'status-badge-failed'
        };

        badge.classList.remove(
            'status-badge-completed',
            'status-badge-running',
            'status-badge-pending',
            'status-badge-failed',
            'status-badge-in-progress'
        );

        var statusClass = statusClasses[status] || statusClasses.pending;
        badge.classList.add(statusClass);

        var dot = badge.querySelector('.status-dot');
        if (dot) {
            dot.classList.remove(
                'status-dot-completed',
                'status-dot-running',
                'status-dot-pending',
                'status-dot-failed',
                'status-dot-in-progress'
            );
            dot.classList.add(statusClass.replace('badge', 'dot'));
        }
    }

    // =========================================================================
    // Activity Log
    // =========================================================================

    /**
     * Append a log line to the activity log panel
     * @param {Object} event - Event data
     */
    function appendLogLine(event) {
        var logOutput = document.getElementById('task-log-output');
        if (!logOutput) return;

        var timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });
        var level = 'info';
        var message = '';

        if (event.log || event.message) {
            message = event.log || event.message;
            level = event.level || 'info';
        } else if (event.step) {
            message = 'Step: ' + event.step;
            level = 'info';
        } else if (event.phase) {
            message = 'Phase changed to: ' + event.phase;
            level = 'success';
        } else if (event.error) {
            message = 'Error: ' + event.error;
            level = 'error';
        } else {
            return; // No loggable content
        }

        var logLine = document.createElement('div');
        logLine.className = 'task-log-line';

        // Use CoreUtils.escapeHtml if available, otherwise use local implementation
        var escapeHtml = (typeof CoreUtils !== 'undefined' && CoreUtils.escapeHtml)
            ? CoreUtils.escapeHtml
            : function(text) {
                if (typeof text !== 'string') return '';
                var div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            };

        logLine.innerHTML = [
            '<span class="task-log-timestamp">' + timestamp + '</span>',
            '<span class="task-log-level ' + level + '">' + level.toUpperCase() + '</span>',
            '<span class="task-log-message">' + escapeHtml(message) + '</span>'
        ].join('');

        // Remove placeholder if present
        var placeholder = logOutput.querySelector('.task-log-line:only-child');
        if (placeholder && placeholder.querySelector('.task-log-message').textContent === 'Waiting for task activity...') {
            placeholder.remove();
        }

        logOutput.appendChild(logLine);

        // Trim old logs
        while (logOutput.children.length > CONFIG.logMaxLines) {
            logOutput.removeChild(logOutput.firstChild);
        }

        // Auto-scroll
        if (logAutoScroll) {
            logOutput.scrollTop = logOutput.scrollHeight;
        }
    }

    // =========================================================================
    // Elapsed Time Management
    // =========================================================================

    /**
     * Start the elapsed time update timer
     */
    function startElapsedTimer() {
        if (elapsedTimer) {
            clearInterval(elapsedTimer);
        }

        updateAllElapsedTimes();
        elapsedTimer = setInterval(updateAllElapsedTimes, CONFIG.elapsedUpdateInterval);
    }

    /**
     * Update all elapsed time displays
     */
    function updateAllElapsedTimes() {
        var elapsedElements = document.querySelectorAll('.elapsed-time');

        elapsedElements.forEach(function(el) {
            var startedAt = el.dataset.started;
            if (!startedAt) return;

            var started = new Date(startedAt);
            var now = new Date();
            var elapsed = Math.floor((now - started) / 1000);

            // Use CoreUtils.formatElapsedClock if available
            var formatElapsed = (typeof CoreUtils !== 'undefined' && CoreUtils.formatElapsedClock)
                ? CoreUtils.formatElapsedClock
                : function(seconds) {
                    if (seconds < 0) seconds = 0;
                    var hours = Math.floor(seconds / 3600);
                    var minutes = Math.floor((seconds % 3600) / 60);
                    var secs = seconds % 60;
                    var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
                    if (hours > 0) {
                        return hours + ':' + pad(minutes) + ':' + pad(secs);
                    }
                    return pad(minutes) + ':' + pad(secs);
                };

            el.textContent = formatElapsed(elapsed);
        });
    }

    // =========================================================================
    // Polling
    // =========================================================================

    /**
     * Start the polling timer for task updates
     */
    function startPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
        }

        pollTimer = setInterval(function() {
            // Only poll if no active SSE connections
            if (Object.keys(eventSources).length === 0) {
                var activeCards = document.querySelectorAll(
                    '.active-task-card[data-run-status="running"], .active-task-card[data-run-status="pending"]'
                );
                if (activeCards.length > 0) {
                    refreshTasks();
                }
            }
            // Always check for planning task updates
            refreshPlanningTasks();
        }, CONFIG.pollInterval);
    }

    /**
     * Refresh active tasks from API
     */
    function refreshTasks() {
        fetch('/api/runs?status=running,pending&limit=10')
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                if (data.runs) {
                    updateTasksList(data.runs);
                }
            })
            .catch(function(err) {
                console.error('Failed to refresh tasks:', err);
            });
    }

    /**
     * Refresh planning tasks from API
     */
    function refreshPlanningTasks() {
        fetch('/api/tasks/planning')
            .then(function(response) {
                if (!response.ok) return { tasks: [] };
                return response.json();
            })
            .then(function(data) {
                if (data.tasks) {
                    updatePlanningTasksList(data.tasks);
                }
            })
            .catch(function(err) {
                console.debug('Planning tasks fetch failed:', err);
            });
    }

    /**
     * Update the tasks list with new data
     * @param {Array} runs - Array of run objects
     */
    function updateTasksList(runs) {
        var noTasksMsg = document.getElementById('no-tasks-message');
        var planningContainer = document.getElementById('planning-tasks-container');

        if (!runs || runs.length === 0) {
            if (noTasksMsg && !planningContainer) {
                noTasksMsg.style.display = 'block';
            } else if (noTasksMsg) {
                noTasksMsg.classList.add('hidden');
            }
            var list = document.getElementById('active-tasks-list');
            if (list) {
                list.innerHTML = '';
            }
            if (!planningContainer) {
                hideIndicator();
            }
            updateTaskCount();
            return;
        }

        if (noTasksMsg) {
            noTasksMsg.classList.add('hidden');
        }
        showIndicator();

        runs.forEach(function(run) {
            var card = document.querySelector('.active-task-card[data-run-id="' + run.id + '"]');

            if (card) {
                updateTaskCard(card, {
                    progress: run.progress || 0,
                    step: run.current_step,
                    status: run.status,
                    phase: run.phase
                });
            } else {
                // New task appeared, reload page to get full HTML
                window.location.reload();
            }
        });

        updateTaskCount();
    }

    /**
     * Update the planning tasks list
     * @param {Array} tasks - Array of planning task objects
     */
    function updatePlanningTasksList(tasks) {
        var planningContainer = document.getElementById('planning-tasks-container');
        if (!planningContainer) {
            // Create container if we have planning tasks
            if (tasks.length > 0) {
                window.location.reload();
            }
            return;
        }

        if (tasks.length === 0) {
            planningContainer.remove();
            var noTasksMsg = document.getElementById('no-tasks-message');
            var activeList = document.getElementById('active-tasks-list');
            if (noTasksMsg && (!activeList || activeList.children.length === 0)) {
                noTasksMsg.classList.remove('hidden');
            }
        }

        updateTaskCount();
    }

    /**
     * Update the active tasks count display
     */
    function updateTaskCount() {
        var activeCards = document.querySelectorAll('.active-task-card');
        var planningCards = document.querySelectorAll('.planning-task-card');
        var countEl = document.getElementById('active-tasks-count');

        var total = activeCards.length + planningCards.length;
        if (countEl) {
            countEl.textContent = total;
        }

        if (total === 0) {
            hideIndicator();
        } else {
            showIndicator();
        }
    }

    // =========================================================================
    // UI Controls Setup
    // =========================================================================

    /**
     * Set up the refresh button click handler
     */
    function setupRefreshButton() {
        var btn = document.getElementById('refresh-tasks-btn');
        if (!btn) return;

        btn.addEventListener('click', function() {
            var icon = btn.querySelector('svg');
            if (icon) {
                icon.classList.add('animate-spin');
            }

            refreshTasks();
            refreshPlanningTasks();

            setTimeout(function() {
                if (icon) {
                    icon.classList.remove('animate-spin');
                }
            }, 1000);
        });
    }

    /**
     * Set up the log panel toggle button
     */
    function setupLogPanelToggle() {
        var toggleBtn = document.getElementById('toggle-log-panel-btn');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', function() {
            toggleActivityLogPanel();
        });
    }

    /**
     * Set up log control buttons (auto-scroll, clear)
     */
    function setupLogControls() {
        var autoScrollBtn = document.getElementById('log-auto-scroll-btn');
        var clearBtn = document.getElementById('log-clear-btn');

        if (autoScrollBtn) {
            autoScrollBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                logAutoScroll = !logAutoScroll;
                autoScrollBtn.classList.toggle('active', logAutoScroll);
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                var logOutput = document.getElementById('task-log-output');
                if (logOutput) {
                    logOutput.innerHTML = [
                        '<div class="task-log-line info">',
                        '  <span class="task-log-timestamp">--:--:--</span>',
                        '  <span class="task-log-level info">INFO</span>',
                        '  <span class="task-log-message">Log cleared. Waiting for task activity...</span>',
                        '</div>'
                    ].join('');
                }
            });
        }
    }

    // =========================================================================
    // Activity Log Panel
    // =========================================================================

    /**
     * Toggle the activity log panel visibility
     */
    function toggleActivityLogPanel() {
        var panel = document.getElementById('task-activity-log-panel');
        if (!panel) return;

        activityLogVisible = !activityLogVisible;
        panel.classList.toggle('hidden', !activityLogVisible);
        panel.classList.toggle('collapsed', !activityLogVisible);
        panel.classList.toggle('expanded', activityLogVisible);

        var toggleBtn = document.getElementById('toggle-log-panel-btn');
        if (toggleBtn) {
            toggleBtn.classList.toggle('btn-primary', activityLogVisible);
            toggleBtn.classList.toggle('btn-secondary', !activityLogVisible);
        }
    }

    // =========================================================================
    // Indicator Management
    // =========================================================================

    /**
     * Hide the active tasks indicator
     */
    function hideIndicator() {
        var indicator = document.getElementById('active-tasks-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    /**
     * Show the active tasks indicator
     */
    function showIndicator() {
        var indicator = document.getElementById('active-tasks-indicator');
        if (indicator) {
            indicator.style.display = 'flex';
        }
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    /**
     * Clean up all resources (SSE connections, timers)
     */
    function destroy() {
        // Close all SSE connections
        Object.keys(eventSources).forEach(function(runId) {
            eventSources[runId].close();
        });
        eventSources = {};

        // Clear timers
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        if (elapsedTimer) {
            clearInterval(elapsedTimer);
            elapsedTimer = null;
        }

        isInitialized = false;
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM already loaded
        init();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', destroy);

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        destroy: destroy,
        refreshTasks: refreshTasks,
        refreshPlanningTasks: refreshPlanningTasks,
        toggleActivityLogPanel: toggleActivityLogPanel,
        updateTaskCount: updateTaskCount,
        CONFIG: CONFIG
    };
})();

// Expose globally
window.ActiveTasks = ActiveTasks;

// Expose toggleActivityLogPanel globally for onclick handlers in HTML
window.toggleActivityLogPanel = function() {
    return ActiveTasks.toggleActivityLogPanel();
};

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ActiveTasks;
}
