/**
 * Background Tasks Indicator Module
 * Manages floating task status bar showing active background tasks
 * with expandable list, auto-updates via polling/SSE, and visual animations
 */

const BackgroundTasksIndicator = (function() {
    'use strict';

    // State
    let state = {
        tasks: new Map(),
        isExpanded: false,
        pollTimer: null,
        eventSource: null,
        container: null,
        sseConnected: false,  // Track SSE connection status
        POLL_INTERVAL: 3000 // 3 seconds
    };

    // Task status constants
    const TaskStatus = {
        PENDING: 'pending',
        RUNNING: 'running',
        COMPLETED: 'completed',
        FAILED: 'failed'
    };

    // Background task types - tasks that should appear in the indicator
    // Includes scout tasks explicitly for background processing visibility
    const BACKGROUND_TASK_TYPES = [
        'scout',
        'scout_task',
        'background',
        'research',
        'knowledge',
        'indexing',
        'analysis',
        'processing'
    ];

    /**
     * Check if a task type qualifies as a background task
     * @param {string} type - The task type to check
     * @returns {boolean} True if this is a background task type
     */
    function isBackgroundTask(task) {
        if (!task) return false;
        // Always include if explicitly marked as background
        if (task.background === true) return true;
        // Check if type matches known background task types
        if (task.type) {
            const taskType = task.type.toLowerCase();
            return BACKGROUND_TASK_TYPES.some(function(bgType) {
                return taskType === bgType || taskType.includes(bgType);
            });
        }
        // Default to true if no type specified (legacy behavior)
        return true;
    }

    /**
     * Initialize the background tasks indicator
     * Creates the floating UI and establishes real-time updates.
     * SSE is the primary update mechanism; polling is only used as fallback.
     */
    function init() {
        createFloatingUI();

        // Fetch tasks immediately for initial data
        fetchTasks();

        // Start polling initially (will be disabled when SSE connects)
        startPolling();

        // Connect SSE (primary) - will disable polling on successful connection
        connectSSE();

        // Cleanup on page unload
        window.addEventListener('beforeunload', cleanup);
    }

    /**
     * Create the floating task status bar UI
     */
    function createFloatingUI() {
        // Check if container already exists (placeholder in base.html)
        let container = document.getElementById('background-tasks-indicator');

        if (container) {
            // Existing container - populate it with UI
            state.container = container;
            container.className = 'fixed bottom-4 right-4 z-50 hidden';
        } else {
            // No container exists - create one
            container = document.createElement('div');
            container.id = 'background-tasks-indicator';
            container.className = 'fixed bottom-4 right-4 z-50 hidden';
            document.body.appendChild(container);
            state.container = container;
        }

        // Populate the container with UI content
        container.innerHTML = `
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden min-w-[280px] max-w-[400px]">
                <!-- Header/Toggle Bar -->
                <div id="background-tasks-header"
                     class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                     onclick="BackgroundTasksIndicator.toggle()">
                    <div class="flex items-center space-x-3">
                        <div id="background-tasks-pulse" class="relative">
                            <div class="h-3 w-3 rounded-full bg-blue-500"></div>
                            <div class="absolute inset-0 h-3 w-3 rounded-full bg-blue-500 animate-ping opacity-75"></div>
                        </div>
                        <span class="text-sm font-medium text-gray-700 dark:text-gray-200">
                            Background Tasks
                        </span>
                        <span id="background-tasks-count"
                              class="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                            0
                        </span>
                    </div>
                    <svg id="background-tasks-chevron"
                         class="h-5 w-5 text-gray-400 transition-transform duration-200"
                         fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                </div>

                <!-- Expandable Task List -->
                <div id="background-tasks-list" class="hidden border-t border-gray-200 dark:border-gray-700 max-h-[300px] overflow-y-auto">
                    <div id="background-tasks-empty" class="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                        No active background tasks
                    </div>
                    <ul id="background-tasks-items" class="divide-y divide-gray-100 dark:divide-gray-700"></ul>
                </div>
            </div>
        </div>
        `;

        // Add CSS for pulse animation if not present
        addPulseStyles();
    }

    /**
     * Add pulse animation styles
     */
    function addPulseStyles() {
        if (document.getElementById('background-tasks-styles')) return;

        const style = document.createElement('style');
        style.id = 'background-tasks-styles';
        style.textContent = `
            @keyframes task-pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .task-item-running {
                animation: task-pulse 2s ease-in-out infinite;
            }
            .task-progress-bar {
                transition: width 0.3s ease-out;
            }
            #background-tasks-indicator.expanded #background-tasks-chevron {
                transform: rotate(180deg);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Toggle expand/collapse of task list
     */
    function toggle() {
        state.isExpanded = !state.isExpanded;

        const list = document.getElementById('background-tasks-list');
        const container = document.getElementById('background-tasks-indicator');

        if (state.isExpanded) {
            list.classList.remove('hidden');
            container.classList.add('expanded');
        } else {
            list.classList.add('hidden');
            container.classList.remove('expanded');
        }
    }

    /**
     * Add a new task to the indicator
     * @param {Object} task - Task object with id, type, status, progress, message
     */
    function addTask(task) {
        if (!task || !task.id) return;

        const taskData = {
            id: task.id,
            type: task.type || 'task',
            status: task.status || TaskStatus.PENDING,
            progress: task.progress || 0,
            message: task.message || 'Starting...',
            startedAt: task.startedAt || new Date().toISOString()
        };

        state.tasks.set(task.id, taskData);
        updateUI();
        showIndicator();
    }

    /**
     * Remove a task from the indicator
     * @param {string} taskId - The task ID to remove
     */
    function removeTask(taskId) {
        if (!taskId) return;

        state.tasks.delete(taskId);
        updateUI();

        // Hide indicator if no tasks remain
        if (state.tasks.size === 0) {
            hideIndicator();
        }
    }

    /**
     * Update an existing task
     * @param {string} taskId - The task ID to update
     * @param {Object} updates - Object with properties to update
     */
    function updateTask(taskId, updates) {
        if (!taskId || !updates) return;

        const task = state.tasks.get(taskId);
        if (!task) {
            // If task doesn't exist, add it
            addTask({ id: taskId, ...updates });
            return;
        }

        // Apply updates
        Object.assign(task, updates);
        state.tasks.set(taskId, task);

        // If task completed or failed, remove after delay
        if (updates.status === TaskStatus.COMPLETED || updates.status === TaskStatus.FAILED) {
            setTimeout(function() {
                removeTask(taskId);
            }, 3000);
        }

        updateUI();
    }

    /**
     * Update the UI to reflect current task state
     */
    function updateUI() {
        const countEl = document.getElementById('background-tasks-count');
        const itemsEl = document.getElementById('background-tasks-items');
        const emptyEl = document.getElementById('background-tasks-empty');
        const pulseEl = document.getElementById('background-tasks-pulse');

        if (!countEl || !itemsEl) return;

        const activeTasks = Array.from(state.tasks.values()).filter(function(t) {
            return t.status === TaskStatus.PENDING || t.status === TaskStatus.RUNNING;
        });

        // Update count badge
        countEl.textContent = activeTasks.length;

        // Update pulse animation based on running tasks
        if (pulseEl) {
            const hasRunning = activeTasks.some(function(t) { return t.status === TaskStatus.RUNNING; });
            const pingEl = pulseEl.querySelector('.animate-ping');
            if (pingEl) {
                pingEl.style.display = hasRunning ? 'block' : 'none';
            }
        }

        // Show/hide empty message
        if (state.tasks.size === 0) {
            emptyEl.classList.remove('hidden');
            itemsEl.innerHTML = '';
            return;
        }
        emptyEl.classList.add('hidden');

        // Render task items
        let html = '';
        state.tasks.forEach(function(task) {
            html += renderTaskItem(task);
        });
        itemsEl.innerHTML = html;
    }

    /**
     * Render a single task item HTML
     * @param {Object} task - Task object
     * @returns {string} HTML string
     */
    function renderTaskItem(task) {
        const statusClasses = getTaskStatusClasses(task.status);
        const isActive = task.status === TaskStatus.PENDING || task.status === TaskStatus.RUNNING;
        const itemClass = isActive ? 'task-item-running' : '';
        const typeLabel = formatTaskType(task.type);
        const elapsed = getElapsedTime(task.startedAt);

        return `
            <li class="px-4 py-3 ${itemClass}">
                <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center space-x-2">
                        <span class="text-sm font-medium text-gray-700 dark:text-gray-200">${escapeHtml(typeLabel)}</span>
                        <span class="text-xs ${statusClasses} px-1.5 py-0.5 rounded">${escapeHtml(task.status)}</span>
                    </div>
                    <span class="text-xs text-gray-400">${elapsed}</span>
                </div>
                <div class="text-xs text-gray-500 dark:text-gray-400 mb-2 truncate">${escapeHtml(task.message)}</div>
                <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                    <div class="task-progress-bar h-1.5 rounded-full ${getProgressBarClass(task.status)}"
                         style="width: ${task.progress}%"></div>
                </div>
            </li>
        `;
    }

    /**
     * Get CSS classes for task status badge
     */
    function getTaskStatusClasses(status) {
        const classMap = {
            pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300',
            running: 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300',
            completed: 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300',
            failed: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300'
        };
        return classMap[status] || 'bg-gray-100 text-gray-800';
    }

    /**
     * Get progress bar color class based on status
     */
    function getProgressBarClass(status) {
        const classMap = {
            pending: 'bg-yellow-500',
            running: 'bg-blue-500',
            completed: 'bg-green-500',
            failed: 'bg-red-500'
        };
        return classMap[status] || 'bg-gray-500';
    }

    /**
     * Format task type for display
     */
    function formatTaskType(type) {
        if (!type) return 'Task';
        return type.charAt(0).toUpperCase() + type.slice(1).replace(/-/g, ' ');
    }

    /**
     * Get elapsed time string
     */
    function getElapsedTime(startedAt) {
        if (!startedAt) return '--:--';

        const start = new Date(startedAt);
        const now = new Date();
        const seconds = Math.floor((now - start) / 1000);

        if (seconds < 0) return '0:00';

        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;

        return minutes + ':' + (secs < 10 ? '0' : '') + secs;
    }

    /**
     * Escape HTML for safe rendering
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Show the floating indicator
     */
    function showIndicator() {
        if (state.container) {
            state.container.classList.remove('hidden');
        }
    }

    /**
     * Hide the floating indicator
     */
    function hideIndicator() {
        if (state.container) {
            state.container.classList.add('hidden');
            state.isExpanded = false;
            const list = document.getElementById('background-tasks-list');
            if (list) list.classList.add('hidden');
        }
    }

    /**
     * Start polling for task updates (fallback when SSE disconnected)
     */
    function startPolling() {
        // Don't start polling if SSE is connected
        if (state.sseConnected) {
            return;
        }

        // Don't duplicate if already polling
        if (state.pollTimer) {
            return;
        }

        // Poll periodically as fallback
        state.pollTimer = setInterval(fetchTasks, state.POLL_INTERVAL);
        console.debug('Background tasks: Polling started (SSE fallback)');
    }

    /**
     * Stop polling (called when SSE connects successfully)
     */
    function stopPolling() {
        if (state.pollTimer) {
            clearInterval(state.pollTimer);
            state.pollTimer = null;
            console.debug('Background tasks: Polling stopped (SSE active)');
        }
    }

    /**
     * Fetch active tasks from the server
     */
    async function fetchTasks() {
        try {
            const response = await fetch('/api/background-tasks');
            if (!response.ok) return;

            const data = await response.json();
            if (data.tasks && Array.isArray(data.tasks)) {
                syncTasks(data.tasks);
            }
        } catch (error) {
            // Silent fail - polling will retry
            console.debug('Background tasks fetch failed:', error);
        }
    }

    /**
     * Sync local task state with server data
     * Filters to only include background tasks (including scout tasks)
     */
    function syncTasks(serverTasks) {
        // Filter to only background tasks (scout, scout_task, etc.)
        const backgroundTasks = serverTasks.filter(isBackgroundTask);
        const serverTaskIds = new Set(backgroundTasks.map(function(t) { return t.id; }));

        // Update or add background tasks from server
        backgroundTasks.forEach(function(task) {
            if (state.tasks.has(task.id)) {
                updateTask(task.id, task);
            } else {
                addTask(task);
            }
        });

        // Remove tasks no longer on server (except recently completed)
        state.tasks.forEach(function(task, id) {
            if (!serverTaskIds.has(id) &&
                task.status !== TaskStatus.COMPLETED &&
                task.status !== TaskStatus.FAILED) {
                removeTask(id);
            }
        });
    }

    /**
     * Connect to SSE for real-time updates (primary method)
     * When SSE is connected, polling is disabled.
     * Polling only activates as fallback when SSE disconnects.
     */
    function connectSSE() {
        // Close existing connection
        if (state.eventSource) {
            state.eventSource.close();
            state.sseConnected = false;
        }

        try {
            state.eventSource = new EventSource('/api/background-tasks/events');

            state.eventSource.onopen = function() {
                // SSE connected - disable polling
                state.sseConnected = true;
                stopPolling();
                console.debug('Background tasks: SSE connected (primary)');
            };

            state.eventSource.onmessage = function(e) {
                try {
                    const event = JSON.parse(e.data);
                    handleSSEEvent(event);
                } catch (err) {
                    console.debug('SSE parse error:', err);
                }
            };

            state.eventSource.onerror = function() {
                // SSE disconnected - enable polling as fallback
                state.sseConnected = false;
                startPolling();
                console.debug('Background tasks: SSE disconnected, falling back to polling');

                // Reconnect after delay
                setTimeout(function() {
                    if (state.eventSource) {
                        state.eventSource.close();
                    }
                    connectSSE();
                }, 5000);
            };
        } catch (error) {
            console.debug('SSE connection failed:', error);
            state.sseConnected = false;
            startPolling();
        }
    }

    /**
     * Handle SSE event
     * Note: Backend sends snake_case (task_id), support both for compatibility
     */
    function handleSSEEvent(event) {
        if (!event || !event.type) return;

        // Support both snake_case (backend) and camelCase field names
        var taskId = event.task_id || event.taskId || (event.task && event.task.id);

        switch (event.type) {
            case 'task_added':
                addTask(event.task);
                break;
            case 'task_updated':
                updateTask(taskId, event.task || event.updates);
                break;
            case 'task_removed':
                removeTask(taskId);
                break;
            case 'task_completed':
                updateTask(taskId, { status: TaskStatus.COMPLETED, progress: 100 });
                break;
            case 'task_failed':
                updateTask(taskId, { status: TaskStatus.FAILED, message: event.error || 'Task failed' });
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
        state.sseConnected = false;
    }

    /**
     * Get current task count (background tasks only)
     */
    function getTaskCount() {
        return countBackgroundTasks();
    }

    /**
     * Count active background tasks (including scout tasks)
     * @returns {number} Count of active background tasks
     */
    function countBackgroundTasks() {
        return Array.from(state.tasks.values()).filter(function(t) {
            return isBackgroundTask(t) &&
                   (t.status === TaskStatus.PENDING || t.status === TaskStatus.RUNNING);
        }).length;
    }

    /**
     * Get all active tasks (background tasks only, including scout tasks)
     */
    function getActiveTasks() {
        return Array.from(state.tasks.values()).filter(function(t) {
            return isBackgroundTask(t) &&
                   (t.status === TaskStatus.PENDING || t.status === TaskStatus.RUNNING);
        });
    }

    /**
     * Get tasks as array (for external use)
     * Filters to background tasks only
     */
    function getTasksArray() {
        return Array.from(state.tasks.values()).filter(isBackgroundTask);
    }

    // Public API
    return {
        init: init,
        addTask: addTask,
        removeTask: removeTask,
        updateTask: updateTask,
        toggle: toggle,
        getTaskCount: getTaskCount,
        getActiveTasks: getActiveTasks,
        getTasksArray: getTasksArray,
        isBackgroundTask: isBackgroundTask,
        cleanup: cleanup,
        TaskStatus: TaskStatus,
        BACKGROUND_TASK_TYPES: BACKGROUND_TASK_TYPES
    };
})();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    BackgroundTasksIndicator.init();
});
