/**
 * Task Activity Panel Module
 * Displays currently executing tasks with phases, progress, and live activity logs
 * Supports expand/collapse for individual task logs and SSE real-time updates
 */

const TaskActivityPanel = (function() {
    'use strict';

    // State
    let state = {
        tasks: new Map(),
        expandedTasks: new Set(),
        eventSource: null,
        container: null,
        pollTimer: null,
        logBuffer: new Map(), // taskId -> array of log lines
        MAX_LOG_LINES: 100,
        POLL_INTERVAL: 3000,
        AUTO_SCROLL: true
    };

    // Task phase constants
    const TaskPhase = {
        PLANNING: 'planning',
        INITIALIZING: 'initializing',
        EXECUTING: 'executing',
        VALIDATING: 'validating',
        COMPLETING: 'completing',
        COMPLETED: 'completed',
        FAILED: 'failed'
    };

    // Task status constants
    const TaskStatus = {
        PLANNING: 'planning',
        PENDING: 'pending',
        RUNNING: 'running',
        COMPLETED: 'completed',
        FAILED: 'failed'
    };

    /**
     * Initialize the task activity panel
     * @param {string} containerId - ID of the container element
     */
    function init(containerId) {
        containerId = containerId || 'task-activity-panel';
        state.container = document.getElementById(containerId);

        if (!state.container) {
            // Create container if it doesn't exist
            state.container = document.createElement('div');
            state.container.id = containerId;
            state.container.className = 'task-activity-panel';
            // Insert after live-builds or at a reasonable location
            var liveBuilds = document.getElementById('live-builds-container');
            if (liveBuilds && liveBuilds.parentNode) {
                liveBuilds.parentNode.insertBefore(state.container, liveBuilds.nextSibling);
            } else {
                document.body.appendChild(state.container);
            }
        }

        // Add panel styles
        addPanelStyles();

        // Render initial UI
        renderPanel();

        // Start polling for tasks
        startPolling();

        // Connect to SSE for real-time updates
        connectSSE();

        // Cleanup on page unload
        window.addEventListener('beforeunload', cleanup);
    }

    /**
     * Add CSS styles for the panel
     */
    function addPanelStyles() {
        if (document.getElementById('task-activity-panel-styles')) return;

        var style = document.createElement('style');
        style.id = 'task-activity-panel-styles';
        style.textContent = [
            '.task-activity-panel { margin-bottom: 1.5rem; }',
            '.task-card { border-radius: 0.75rem; overflow: hidden; transition: all 0.3s ease; }',
            '.task-card:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }',
            '.task-card.planning { opacity: 0.7; pointer-events: none; }',
            '.task-card.planning .task-header { cursor: default; }',
            '.task-phase-indicator { display: flex; align-items: center; gap: 0.25rem; }',
            '.task-phase-dot { width: 8px; height: 8px; border-radius: 50%; background: #9CA3AF; }',
            '.task-phase-dot.active { background: #3B82F6; animation: phase-pulse 1.5s ease-in-out infinite; }',
            '.task-phase-dot.completed { background: #10B981; }',
            '.task-phase-dot.failed { background: #EF4444; }',
            '@keyframes phase-pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.2); opacity: 0.7; } }',
            '.task-log-container { max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 0.75rem; line-height: 1.4; background: #1F2937; color: #D1D5DB; padding: 0.75rem; border-radius: 0.5rem; margin-top: 0.75rem; }',
            '.task-log-container.collapsed { display: none; }',
            '.task-log-line { white-space: pre-wrap; word-break: break-all; }',
            '.task-log-line.info { color: #93C5FD; }',
            '.task-log-line.warning { color: #FCD34D; }',
            '.task-log-line.error { color: #FCA5A5; }',
            '.task-log-line.success { color: #6EE7B7; }',
            '.task-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem; cursor: pointer; }',
            '.task-header:hover { background: rgba(0,0,0,0.02); }',
            '.task-expand-icon { transition: transform 0.2s ease; }',
            '.task-expand-icon.expanded { transform: rotate(180deg); }',
            '.task-progress-phases { display: flex; align-items: center; gap: 0.5rem; padding: 0 1rem 0.75rem; }',
            '.task-no-tasks { text-align: center; padding: 2rem; color: #6B7280; }',
            '.planning-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.8); border-radius: 0.75rem; }',
            '.planning-spinner { animation: spin 1s linear infinite; }',
            '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }'
        ].join('\n');
        document.head.appendChild(style);
    }

    /**
     * Render the panel container
     */
    function renderPanel() {
        if (!state.container) return;

        state.container.innerHTML = [
            '<div class="glass rounded-2xl overflow-hidden">',
            '  <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">',
            '    <div class="flex items-center">',
            '      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center mr-3 shadow-md">',
            '        <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
            '        </svg>',
            '      </div>',
            '      <div>',
            '        <h3 class="text-lg font-semibold text-primary">Active Tasks</h3>',
            '        <p class="text-xs text-tertiary">Real-time task execution status</p>',
            '      </div>',
            '    </div>',
            '    <div class="flex items-center space-x-2">',
            '      <span id="task-activity-count" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">0</span>',
            '      <button id="task-activity-refresh" type="button" class="p-2 rounded-lg hover:bg-gray-100 transition-colors" title="Refresh">',
            '        <svg class="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>',
            '        </svg>',
            '      </button>',
            '    </div>',
            '  </div>',
            '  <div id="task-activity-list" class="divide-y divide-gray-100">',
            '    <div id="task-activity-empty" class="task-no-tasks">',
            '      <svg class="h-12 w-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>',
            '      </svg>',
            '      <p class="text-sm">No active tasks</p>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('\n');

        // Attach refresh handler
        var refreshBtn = document.getElementById('task-activity-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                var icon = refreshBtn.querySelector('svg');
                if (icon) icon.classList.add('animate-spin');
                fetchTasks().finally(function() {
                    setTimeout(function() {
                        if (icon) icon.classList.remove('animate-spin');
                    }, 500);
                });
            });
        }
    }

    /**
     * Add a task to the panel
     * @param {Object} task - Task object with id, name, status, phase, progress
     */
    function addTask(task) {
        if (!task || !task.id) return;

        var taskData = {
            id: task.id,
            name: task.name || task.title || 'Task ' + task.id.substring(0, 8),
            status: task.status || TaskStatus.PENDING,
            phase: task.phase || TaskPhase.INITIALIZING,
            progress: task.progress || 0,
            currentStep: task.current_step || task.currentStep || '',
            startedAt: task.started_at || task.startedAt || new Date().toISOString(),
            planId: task.plan_id || task.planId || null,
            totalSteps: task.total_steps || task.totalSteps || 0,
            currentStepNum: task.current_step_num || task.currentStepNum || 0
        };

        state.tasks.set(task.id, taskData);

        // Initialize log buffer for this task
        if (!state.logBuffer.has(task.id)) {
            state.logBuffer.set(task.id, []);
        }

        updateUI();
    }

    /**
     * Update an existing task
     * @param {string} taskId - Task ID to update
     * @param {Object} updates - Properties to update
     */
    function updateTask(taskId, updates) {
        if (!taskId || !updates) return;

        var task = state.tasks.get(taskId);
        if (!task) {
            // If task doesn't exist, add it
            addTask({ id: taskId, ...updates });
            return;
        }

        // Apply updates
        Object.assign(task, updates);
        state.tasks.set(taskId, task);

        // Handle status transitions
        if (updates.status === TaskStatus.COMPLETED || updates.status === TaskStatus.FAILED) {
            // Keep completed/failed tasks visible briefly then remove
            setTimeout(function() {
                removeTask(taskId);
            }, 5000);
        }

        updateUI();
    }

    /**
     * Remove a task from the panel
     * @param {string} taskId - Task ID to remove
     */
    function removeTask(taskId) {
        if (!taskId) return;

        state.tasks.delete(taskId);
        state.logBuffer.delete(taskId);
        state.expandedTasks.delete(taskId);
        updateUI();
    }

    /**
     * Render a log line for a task
     * @param {string} taskId - Task ID
     * @param {string|Object} logEntry - Log line text or object with message and level
     */
    function renderLogLine(taskId, logEntry) {
        if (!taskId || !logEntry) return;

        var logText = typeof logEntry === 'string' ? logEntry : (logEntry.message || logEntry.text || '');
        var level = typeof logEntry === 'object' ? (logEntry.level || 'info') : 'info';

        // Get or create log buffer
        var logs = state.logBuffer.get(taskId);
        if (!logs) {
            logs = [];
            state.logBuffer.set(taskId, logs);
        }

        // Add timestamp
        var timestamp = new Date().toLocaleTimeString();
        var formattedLine = {
            text: '[' + timestamp + '] ' + logText,
            level: level
        };

        logs.push(formattedLine);

        // Trim buffer if too large
        if (logs.length > state.MAX_LOG_LINES) {
            logs.shift();
        }

        // Update log display if task is expanded
        if (state.expandedTasks.has(taskId)) {
            updateTaskLogDisplay(taskId);
        }
    }

    /**
     * Update the log display for a task
     * @param {string} taskId - Task ID
     */
    function updateTaskLogDisplay(taskId) {
        var logContainer = document.getElementById('task-log-' + taskId);
        if (!logContainer) return;

        var logs = state.logBuffer.get(taskId) || [];

        var html = logs.map(function(log) {
            return '<div class="task-log-line ' + escapeHtml(log.level) + '">' + escapeHtml(log.text) + '</div>';
        }).join('');

        logContainer.innerHTML = html;

        // Auto-scroll to bottom
        if (state.AUTO_SCROLL) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    }

    /**
     * Update the UI to reflect current state
     */
    function updateUI() {
        var countEl = document.getElementById('task-activity-count');
        var listEl = document.getElementById('task-activity-list');
        var emptyEl = document.getElementById('task-activity-empty');

        if (!listEl) return;

        var activeTasks = Array.from(state.tasks.values()).filter(function(t) {
            return t.status !== TaskStatus.COMPLETED && t.status !== TaskStatus.FAILED;
        });

        // Update count
        if (countEl) {
            countEl.textContent = activeTasks.length;
        }

        // Show/hide empty message
        if (state.tasks.size === 0) {
            if (emptyEl) emptyEl.style.display = 'block';
            // Clear task cards but keep empty message
            var cards = listEl.querySelectorAll('.task-card');
            cards.forEach(function(card) { card.remove(); });
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';

        // Render task cards
        state.tasks.forEach(function(task) {
            var existingCard = document.getElementById('task-card-' + task.id);
            if (existingCard) {
                updateTaskCard(existingCard, task);
            } else {
                var card = createTaskCard(task);
                listEl.appendChild(card);
            }
        });

        // Remove cards for tasks no longer in state
        var cards = listEl.querySelectorAll('.task-card');
        cards.forEach(function(card) {
            var taskId = card.id.replace('task-card-', '');
            if (!state.tasks.has(taskId)) {
                card.remove();
            }
        });
    }

    /**
     * Create a task card element
     * @param {Object} task - Task data
     * @returns {HTMLElement} Task card element
     */
    function createTaskCard(task) {
        var card = document.createElement('div');
        card.id = 'task-card-' + task.id;
        card.className = 'task-card border-b border-gray-100';

        if (task.status === TaskStatus.PLANNING) {
            card.classList.add('planning');
        }

        var isExpanded = state.expandedTasks.has(task.id);
        var statusBadgeClass = getStatusBadgeClass(task.status);
        var phaseHtml = renderPhaseIndicators(task);
        var elapsed = getElapsedTime(task.startedAt);

        card.innerHTML = [
            '<div class="relative">',
            task.status === TaskStatus.PLANNING ? renderPlanningOverlay() : '',
            '  <div class="task-header" onclick="TaskActivityPanel.toggleExpand(\'' + escapeHtml(task.id) + '\')">',
            '    <div class="flex items-center space-x-3">',
            '      <div class="w-10 h-10 rounded-lg bg-gradient-to-br ' + getTaskGradient(task.status) + ' flex items-center justify-center shadow-sm">',
            '        ' + getTaskIcon(task.status),
            '      </div>',
            '      <div class="min-w-0">',
            '        <div class="flex items-center">',
            '          <span class="text-sm font-medium text-primary truncate">' + escapeHtml(task.name) + '</span>',
            '          ' + (task.planId ? '<a href="/plans/' + escapeHtml(task.planId) + '" class="ml-2 text-xs text-blue-600 hover:text-blue-800" onclick="event.stopPropagation()">View Plan</a>' : ''),
            '        </div>',
            '        <div class="text-xs text-tertiary truncate">' + escapeHtml(task.currentStep || 'Initializing...') + '</div>',
            '      </div>',
            '    </div>',
            '    <div class="flex items-center space-x-3">',
            '      <span class="text-xs text-gray-500 elapsed-time" data-started="' + escapeHtml(task.startedAt) + '">' + elapsed + '</span>',
            '      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + statusBadgeClass + '">' + escapeHtml(task.status) + '</span>',
            '      <svg class="h-5 w-5 text-gray-400 task-expand-icon ' + (isExpanded ? 'expanded' : '') + '" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>',
            '      </svg>',
            '    </div>',
            '  </div>',
            '  <div class="task-progress-phases">',
            '    ' + phaseHtml,
            '  </div>',
            '  <div class="px-4 pb-3">',
            '    <div class="flex items-center justify-between text-xs mb-1">',
            '      <span class="text-tertiary">' + (task.totalSteps > 0 ? 'Step ' + task.currentStepNum + ' of ' + task.totalSteps : 'Progress') + '</span>',
            '      <span class="font-medium text-primary">' + task.progress + '%</span>',
            '    </div>',
            '    <div class="w-full bg-gray-200 rounded-full h-2">',
            '      <div class="task-progress-bar h-2 rounded-full ' + getProgressBarClass(task.status) + ' transition-all duration-300" style="width: ' + task.progress + '%"></div>',
            '    </div>',
            '  </div>',
            '  <div id="task-log-' + escapeHtml(task.id) + '" class="task-log-container ' + (isExpanded ? '' : 'collapsed') + '"></div>',
            '</div>'
        ].join('\n');

        // Populate log display if expanded
        if (isExpanded) {
            setTimeout(function() {
                updateTaskLogDisplay(task.id);
            }, 0);
        }

        return card;
    }

    /**
     * Update an existing task card
     * @param {HTMLElement} card - Card element
     * @param {Object} task - Task data
     */
    function updateTaskCard(card, task) {
        // Update status badge
        var statusBadge = card.querySelector('.rounded-full');
        if (statusBadge) {
            statusBadge.textContent = task.status;
            statusBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + getStatusBadgeClass(task.status);
        }

        // Update progress bar
        var progressBar = card.querySelector('.task-progress-bar');
        if (progressBar) {
            progressBar.style.width = task.progress + '%';
            progressBar.className = 'task-progress-bar h-2 rounded-full ' + getProgressBarClass(task.status) + ' transition-all duration-300';
        }

        // Update progress text
        var progressText = card.querySelector('.font-medium.text-primary');
        if (progressText) {
            progressText.textContent = task.progress + '%';
        }

        // Update current step text
        var stepText = card.querySelector('.text-tertiary.truncate');
        if (stepText) {
            stepText.textContent = task.currentStep || 'Processing...';
        }

        // Update step counter
        var stepCounter = card.querySelector('.task-progress-phases + div .text-tertiary');
        if (stepCounter && task.totalSteps > 0) {
            stepCounter.textContent = 'Step ' + task.currentStepNum + ' of ' + task.totalSteps;
        }

        // Update planning state
        if (task.status === TaskStatus.PLANNING) {
            card.classList.add('planning');
        } else {
            card.classList.remove('planning');
        }
    }

    /**
     * Render phase indicators
     * @param {Object} task - Task data
     * @returns {string} HTML string
     */
    function renderPhaseIndicators(task) {
        var phases = [
            { key: TaskPhase.PLANNING, label: 'Plan' },
            { key: TaskPhase.INITIALIZING, label: 'Init' },
            { key: TaskPhase.EXECUTING, label: 'Execute' },
            { key: TaskPhase.VALIDATING, label: 'Validate' },
            { key: TaskPhase.COMPLETING, label: 'Complete' }
        ];

        var currentPhaseIndex = phases.findIndex(function(p) { return p.key === task.phase; });

        return phases.map(function(phase, index) {
            var dotClass = 'task-phase-dot';
            if (index < currentPhaseIndex) {
                dotClass += ' completed';
            } else if (index === currentPhaseIndex) {
                dotClass += ' active';
            }
            if (task.status === TaskStatus.FAILED && index === currentPhaseIndex) {
                dotClass = 'task-phase-dot failed';
            }

            return '<div class="task-phase-indicator">' +
                '<div class="' + dotClass + '"></div>' +
                '<span class="text-xs text-tertiary">' + phase.label + '</span>' +
                '</div>';
        }).join('<div class="flex-1 h-px bg-gray-200"></div>');
    }

    /**
     * Render planning overlay
     * @returns {string} HTML string
     */
    function renderPlanningOverlay() {
        return [
            '<div class="planning-overlay">',
            '  <div class="flex items-center space-x-2">',
            '    <svg class="planning-spinner h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24">',
            '      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
            '      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
            '    </svg>',
            '    <span class="text-sm text-gray-500">Planning...</span>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    /**
     * Toggle task log expansion
     * @param {string} taskId - Task ID
     */
    function toggleExpand(taskId) {
        var task = state.tasks.get(taskId);
        if (!task || task.status === TaskStatus.PLANNING) return;

        var logContainer = document.getElementById('task-log-' + taskId);
        var expandIcon = document.querySelector('#task-card-' + taskId + ' .task-expand-icon');

        if (state.expandedTasks.has(taskId)) {
            state.expandedTasks.delete(taskId);
            if (logContainer) logContainer.classList.add('collapsed');
            if (expandIcon) expandIcon.classList.remove('expanded');
        } else {
            state.expandedTasks.add(taskId);
            if (logContainer) logContainer.classList.remove('collapsed');
            if (expandIcon) expandIcon.classList.add('expanded');
            updateTaskLogDisplay(taskId);
        }
    }

    /**
     * Get status badge CSS class
     * @param {string} status - Task status
     * @returns {string} CSS class string
     */
    function getStatusBadgeClass(status) {
        var classMap = {
            planning: 'bg-gray-100 text-gray-800',
            pending: 'bg-yellow-100 text-yellow-800',
            running: 'bg-blue-100 text-blue-800',
            completed: 'bg-green-100 text-green-800',
            failed: 'bg-red-100 text-red-800'
        };
        return classMap[status] || 'bg-gray-100 text-gray-800';
    }

    /**
     * Get progress bar CSS class
     * @param {string} status - Task status
     * @returns {string} CSS class string
     */
    function getProgressBarClass(status) {
        var classMap = {
            planning: 'bg-gray-400',
            pending: 'bg-yellow-500',
            running: 'bg-blue-500',
            completed: 'bg-green-500',
            failed: 'bg-red-500'
        };
        return classMap[status] || 'bg-gray-500';
    }

    /**
     * Get task gradient class
     * @param {string} status - Task status
     * @returns {string} CSS class string
     */
    function getTaskGradient(status) {
        var classMap = {
            planning: 'from-gray-400 to-gray-500',
            pending: 'from-yellow-400 to-orange-500',
            running: 'from-blue-400 to-indigo-500',
            completed: 'from-green-400 to-emerald-500',
            failed: 'from-red-400 to-rose-500'
        };
        return classMap[status] || 'from-gray-400 to-gray-500';
    }

    /**
     * Get task icon SVG
     * @param {string} status - Task status
     * @returns {string} SVG HTML string
     */
    function getTaskIcon(status) {
        var icons = {
            planning: '<svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>',
            pending: '<svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            running: '<svg class="h-5 w-5 text-white animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>',
            completed: '<svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>',
            failed: '<svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
        };
        return icons[status] || icons.pending;
    }

    /**
     * Get elapsed time string
     * @param {string} startedAt - ISO timestamp
     * @returns {string} Formatted elapsed time
     */
    function getElapsedTime(startedAt) {
        if (!startedAt) return '--:--';

        var start = new Date(startedAt);
        var now = new Date();
        var seconds = Math.floor((now - start) / 1000);

        if (seconds < 0) return '0:00';

        var minutes = Math.floor(seconds / 60);
        var secs = seconds % 60;

        return minutes + ':' + (secs < 10 ? '0' : '') + secs;
    }

    /**
     * Escape HTML for safe rendering
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Start polling for task updates
     */
    function startPolling() {
        if (state.pollTimer) {
            clearInterval(state.pollTimer);
        }

        fetchTasks();
        state.pollTimer = setInterval(fetchTasks, state.POLL_INTERVAL);
    }

    /**
     * Stop polling
     */
    function stopPolling() {
        if (state.pollTimer) {
            clearInterval(state.pollTimer);
            state.pollTimer = null;
        }
    }

    /**
     * Fetch active tasks from server
     */
    async function fetchTasks() {
        try {
            var response = await fetch('/api/tasks/active');
            if (!response.ok) return;

            var data = await response.json();
            if (data.tasks && Array.isArray(data.tasks)) {
                syncTasks(data.tasks);
            }
        } catch (error) {
            console.debug('Task fetch failed:', error);
        }
    }

    /**
     * Sync tasks with server data
     * @param {Array} serverTasks - Tasks from server
     */
    function syncTasks(serverTasks) {
        var serverTaskIds = new Set(serverTasks.map(function(t) { return t.id; }));

        // Update or add tasks
        serverTasks.forEach(function(task) {
            if (state.tasks.has(task.id)) {
                updateTask(task.id, task);
            } else {
                addTask(task);
            }
        });

        // Remove tasks no longer on server
        state.tasks.forEach(function(task, id) {
            if (!serverTaskIds.has(id) &&
                task.status !== TaskStatus.COMPLETED &&
                task.status !== TaskStatus.FAILED) {
                removeTask(id);
            }
        });
    }

    /**
     * Connect to SSE for real-time updates
     */
    function connectSSE() {
        if (state.eventSource) {
            state.eventSource.close();
        }

        try {
            state.eventSource = new EventSource('/api/tasks/events');

            state.eventSource.onmessage = function(e) {
                try {
                    var event = JSON.parse(e.data);
                    handleSSEEvent(event);
                } catch (err) {
                    console.debug('SSE parse error:', err);
                }
            };

            state.eventSource.onerror = function() {
                setTimeout(function() {
                    if (state.eventSource) {
                        state.eventSource.close();
                    }
                    connectSSE();
                }, 5000);
            };
        } catch (error) {
            console.debug('SSE connection failed:', error);
        }
    }

    /**
     * Handle SSE event
     * @param {Object} event - Event data
     */
    function handleSSEEvent(event) {
        if (!event || !event.type) return;

        var taskId = event.task_id || event.taskId || (event.task && event.task.id);

        switch (event.type) {
            case 'task_started':
            case 'task_added':
                addTask(event.task);
                break;
            case 'task_updated':
            case 'task_progress':
                updateTask(taskId, event.task || event.updates || event);
                break;
            case 'task_log':
                renderLogLine(taskId, event.message || event.log);
                break;
            case 'task_completed':
                updateTask(taskId, { status: TaskStatus.COMPLETED, progress: 100 });
                break;
            case 'task_failed':
                updateTask(taskId, { status: TaskStatus.FAILED, message: event.error || 'Task failed' });
                break;
            case 'task_removed':
                removeTask(taskId);
                break;
        }
    }

    /**
     * Cleanup resources
     */
    function cleanup() {
        stopPolling();
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }
    }

    /**
     * Get all tasks
     * @returns {Array} Array of task objects
     */
    function getTasks() {
        return Array.from(state.tasks.values());
    }

    /**
     * Get active task count
     * @returns {number} Number of active tasks
     */
    function getActiveCount() {
        return Array.from(state.tasks.values()).filter(function(t) {
            return t.status !== TaskStatus.COMPLETED && t.status !== TaskStatus.FAILED;
        }).length;
    }

    // Public API
    return {
        init: init,
        addTask: addTask,
        updateTask: updateTask,
        removeTask: removeTask,
        renderLogLine: renderLogLine,
        toggleExpand: toggleExpand,
        getTasks: getTasks,
        getActiveCount: getActiveCount,
        cleanup: cleanup,
        TaskStatus: TaskStatus,
        TaskPhase: TaskPhase
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskActivityPanel;
}
