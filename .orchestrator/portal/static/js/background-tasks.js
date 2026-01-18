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
        sseManager: null,
        taskSubscriptions: new Map(), // Map<taskId, SSEConnectionManager> for task-specific streams
        container: null,
        useSSE: true,
        sseConnectionState: 'disconnected', // 'connected', 'reconnecting', 'disconnected', 'fallback'
        POLL_INTERVAL: 3000, // 3 seconds (normal)
        POLL_INTERVAL_FALLBACK: 2000 // 2 seconds (when SSE fails)
    };

    // Task status constants
    const TaskStatus = {
        PENDING: 'pending',
        RUNNING: 'running',
        COMPLETED: 'completed',
        FAILED: 'failed'
    };

    /**
     * Initialize the background tasks indicator
     * Creates the floating UI and starts SSE or polling for tasks
     */
    function init() {
        createFloatingUI();

        // Try SSE first if enabled, fall back to polling
        if (state.useSSE && typeof SSEConnectionManager !== 'undefined') {
            connectSSE();
        } else {
            // SSE not available, use polling
            state.sseConnectionState = 'fallback';
            updateConnectionIndicator();
            startPolling();
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', cleanup);

        // Cleanup on page navigation (SPA)
        window.addEventListener('pagehide', cleanup);
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
                        <!-- SSE Connection State Indicator -->
                        <span id="background-tasks-connection"
                              class="sse-indicator-compact sse-disconnected cursor-help"
                              title="Disconnected">
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

            /* SSE Connection Indicator Styles (inline fallback) */
            .sse-indicator-compact {
                width: 0.5rem;
                height: 0.5rem;
                border-radius: 9999px;
                flex-shrink: 0;
                transition: all 0.2s ease;
            }

            /* Connected state - Green with pulse */
            .sse-indicator-compact.sse-connected {
                background-color: #10b981;
                animation: sse-connected-pulse 2s ease-in-out infinite;
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4);
            }

            @keyframes sse-connected-pulse {
                0%, 100% {
                    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4);
                    opacity: 1;
                }
                50% {
                    box-shadow: 0 0 0 4px rgba(16, 185, 129, 0);
                    opacity: 0.8;
                }
            }

            /* Reconnecting state - Yellow with faster pulse */
            .sse-indicator-compact.sse-reconnecting {
                background-color: #f59e0b;
                animation: sse-reconnecting-pulse 1s ease-in-out infinite;
            }

            @keyframes sse-reconnecting-pulse {
                0%, 100% {
                    box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.5);
                    opacity: 1;
                    transform: scale(1);
                }
                50% {
                    box-shadow: 0 0 0 4px rgba(245, 158, 11, 0);
                    opacity: 0.6;
                    transform: scale(0.9);
                }
            }

            /* Fallback state - Orange static (slow pulse) */
            .sse-indicator-compact.sse-fallback {
                background-color: #f97316;
                animation: sse-fallback-pulse 3s ease-in-out infinite;
            }

            @keyframes sse-fallback-pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            /* Disconnected state - Red static (no animation) */
            .sse-indicator-compact.sse-disconnected {
                background-color: #ef4444;
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
     * Start polling for task updates
     * @param {number} [interval] - Optional polling interval in ms (defaults to POLL_INTERVAL)
     */
    function startPolling(interval) {
        if (state.pollTimer) {
            clearInterval(state.pollTimer);
        }

        var pollInterval = interval || state.POLL_INTERVAL;

        // Initial fetch
        fetchTasks();

        // Poll periodically
        state.pollTimer = setInterval(fetchTasks, pollInterval);
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
     */
    function syncTasks(serverTasks) {
        const serverTaskIds = new Set(serverTasks.map(function(t) { return t.id; }));

        // Update or add tasks from server
        serverTasks.forEach(function(task) {
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
     * Connect to SSE for real-time updates using SSEConnectionManager
     */
    function connectSSE() {
        // Disconnect existing manager
        if (state.sseManager) {
            state.sseManager.disconnect();
            state.sseManager = null;
        }

        try {
            // Create SSE Connection Manager with fallback enabled
            state.sseManager = new SSEConnectionManager('/api/background-tasks/events', {
                maxReconnectAttempts: 5,
                initialReconnectDelay: 1000,
                maxReconnectDelay: 30000,
                heartbeatTimeout: 45000,
                pollingInterval: state.POLL_INTERVAL_FALLBACK,
                enablePollingFallback: true
            });

            // Set polling fallback function
            state.sseManager.setPollingFallback(fetchTasks);

            // Register state change handler
            state.sseManager.onStateChange(function(newState, oldState) {
                handleSSEStateChange(newState, oldState);
            });

            // Register handler for generic messages
            state.sseManager.onMessage(function(data, event) {
                // Handle generic message events that have a type field
                if (data && data.type) {
                    handleSSEEvent(data);
                }
            });

            // Register named event handlers for each event type
            state.sseManager.on('initial', function(data) {
                handleSSEEvent({ type: 'initial', tasks: data.tasks || data });
            });

            state.sseManager.on('task_added', function(data) {
                handleSSEEvent({ type: 'task_added', task: data.task || data });
            });

            state.sseManager.on('task_updated', function(data) {
                handleSSEEvent({ type: 'task_updated', task_id: data.task_id, task: data.task || data });
            });

            state.sseManager.on('task_completed', function(data) {
                handleSSEEvent({ type: 'task_completed', task_id: data.task_id || data.id });
            });

            state.sseManager.on('task_failed', function(data) {
                handleSSEEvent({ type: 'task_failed', task_id: data.task_id || data.id, error: data.error });
            });

            state.sseManager.on('task_cancelled', function(data) {
                handleSSEEvent({ type: 'task_cancelled', task_id: data.task_id || data.id });
            });

            state.sseManager.on('heartbeat', function(data) {
                // Heartbeat handled internally by SSEConnectionManager
                // Update local heartbeat tracking if needed
                console.debug('Background tasks SSE heartbeat received');
            });

            // Connect to SSE
            state.sseManager.connect();

        } catch (error) {
            console.warn('SSE connection setup failed, falling back to polling:', error);
            state.sseConnectionState = 'fallback';
            updateConnectionIndicator();
            startPolling();
        }
    }

    /**
     * Handle SSE connection state changes
     */
    function handleSSEStateChange(newState, oldState) {
        var ConnectionState = SSEConnectionManager.ConnectionState;

        switch (newState) {
            case ConnectionState.CONNECTED:
                state.sseConnectionState = 'connected';
                // Stop polling when SSE is connected
                stopPolling();
                // Do an initial fetch to sync state
                fetchTasks();
                break;

            case ConnectionState.CONNECTING:
                state.sseConnectionState = 'reconnecting';
                break;

            case ConnectionState.RECONNECTING:
                state.sseConnectionState = 'reconnecting';
                // Start polling during reconnection with faster interval
                startPolling(state.POLL_INTERVAL_FALLBACK);
                break;

            case ConnectionState.DISCONNECTED:
                state.sseConnectionState = 'disconnected';
                break;

            case ConnectionState.FAILED:
                // SSE completely failed, switch to fallback polling
                state.sseConnectionState = 'fallback';
                startPolling(state.POLL_INTERVAL_FALLBACK);
                break;
        }

        // Check if in polling mode
        if (state.sseManager && state.sseManager.isPollingMode()) {
            state.sseConnectionState = 'fallback';
        }

        updateConnectionIndicator();
    }

    /**
     * Update the visual connection state indicator
     * Uses CSS classes from background-tasks.css:
     * - Green pulse = connected (SSE active)
     * - Yellow pulse = reconnecting
     * - Orange static = fallback (polling mode)
     * - Red static = disconnected
     */
    function updateConnectionIndicator() {
        var indicatorEl = document.getElementById('background-tasks-connection');

        if (!indicatorEl) return;

        // Remove all state classes
        indicatorEl.classList.remove('sse-connected', 'sse-reconnecting', 'sse-fallback', 'sse-disconnected');

        var title = '';
        var stateClass = 'sse-disconnected';

        switch (state.sseConnectionState) {
            case 'connected':
                stateClass = 'sse-connected';
                title = 'Real-time updates active (SSE connected)';
                break;
            case 'reconnecting':
                stateClass = 'sse-reconnecting';
                title = 'Reconnecting to server...';
                break;
            case 'fallback':
                stateClass = 'sse-fallback';
                title = 'Using polling mode (SSE unavailable)';
                break;
            case 'disconnected':
            default:
                stateClass = 'sse-disconnected';
                title = 'Disconnected from server';
                break;
        }

        indicatorEl.classList.add(stateClass);
        indicatorEl.setAttribute('title', title);
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
            case 'initial':
                // Initial sync of all tasks when connection established
                if (event.tasks && Array.isArray(event.tasks)) {
                    syncTasks(event.tasks);
                }
                break;
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
            case 'task_cancelled':
                // Task was cancelled - remove it from the list
                removeTask(taskId);
                break;
        }
    }

    /**
     * Subscribe to updates for a specific task via SSE
     * Creates a dedicated SSEConnectionManager for the task's stream endpoint
     * @param {string} taskId - The task ID to subscribe to
     * @returns {boolean} True if subscription was created, false if already subscribed or SSE unavailable
     */
    function subscribeToTask(taskId) {
        if (!taskId) return false;

        // Check if already subscribed
        if (state.taskSubscriptions.has(taskId)) {
            console.debug('Already subscribed to task:', taskId);
            return false;
        }

        // Check if SSE is available
        if (typeof SSEConnectionManager === 'undefined') {
            console.warn('SSEConnectionManager not available, cannot subscribe to task:', taskId);
            return false;
        }

        // Check if task is already in terminal state
        var existingTask = state.tasks.get(taskId);
        if (existingTask && (existingTask.status === TaskStatus.COMPLETED || existingTask.status === TaskStatus.FAILED)) {
            console.debug('Task already in terminal state, not subscribing:', taskId);
            return false;
        }

        try {
            // Create SSE Connection Manager for this specific task
            var taskManager = new SSEConnectionManager('/api/background-tasks/' + taskId + '/stream', {
                maxReconnectAttempts: 3,
                initialReconnectDelay: 1000,
                maxReconnectDelay: 10000,
                heartbeatTimeout: 45000,
                enablePollingFallback: false // Don't use polling fallback for individual tasks
            });

            // Handle state changes
            taskManager.onStateChange(function(newState, oldState) {
                var ConnectionState = SSEConnectionManager.ConnectionState;
                if (newState === ConnectionState.FAILED || newState === ConnectionState.DISCONNECTED) {
                    // Connection failed or disconnected, clean up subscription
                    console.debug('Task SSE connection ended for:', taskId, 'state:', newState);
                }
            });

            // Handle generic messages
            taskManager.onMessage(function(data, event) {
                handleTaskSSEEvent(taskId, data);
            });

            // Register named event handlers
            taskManager.on('task_status', function(data) {
                handleTaskSSEEvent(taskId, { type: 'task_status', ...data });
            });

            taskManager.on('task_done', function(data) {
                handleTaskSSEEvent(taskId, { type: 'task_done', ...data });
            });

            taskManager.on('heartbeat', function(data) {
                console.debug('Task SSE heartbeat for:', taskId);
            });

            taskManager.on('error', function(data) {
                console.warn('Task SSE error for:', taskId, data.message);
                unsubscribeFromTask(taskId);
            });

            // Store subscription and connect
            state.taskSubscriptions.set(taskId, taskManager);
            taskManager.connect();

            console.debug('Subscribed to task updates:', taskId);
            return true;

        } catch (error) {
            console.warn('Failed to subscribe to task:', taskId, error);
            return false;
        }
    }

    /**
     * Handle SSE events from task-specific stream
     * @param {string} taskId - The task ID
     * @param {Object} event - The SSE event data
     */
    function handleTaskSSEEvent(taskId, event) {
        if (!event || !event.type) return;

        switch (event.type) {
            case 'task_status':
                // Update task with received status
                updateTask(taskId, {
                    status: event.status,
                    progress: event.progress,
                    message: event.message,
                    result: event.result
                });
                break;

            case 'task_done':
                // Task reached terminal state - update and unsubscribe
                updateTask(taskId, {
                    status: event.status,
                    progress: event.status === TaskStatus.COMPLETED ? 100 : event.progress,
                    message: event.message,
                    result: event.result
                });
                // Auto-unsubscribe since task is done
                unsubscribeFromTask(taskId);
                break;

            case 'error':
                console.warn('Task stream error:', taskId, event.message);
                unsubscribeFromTask(taskId);
                break;
        }
    }

    /**
     * Unsubscribe from updates for a specific task
     * Disconnects and removes the task-specific SSEConnectionManager
     * @param {string} taskId - The task ID to unsubscribe from
     * @returns {boolean} True if unsubscribed, false if not subscribed
     */
    function unsubscribeFromTask(taskId) {
        if (!taskId) return false;

        var taskManager = state.taskSubscriptions.get(taskId);
        if (!taskManager) {
            return false;
        }

        try {
            taskManager.disconnect();
        } catch (error) {
            console.debug('Error disconnecting task subscription:', taskId, error);
        }

        state.taskSubscriptions.delete(taskId);
        console.debug('Unsubscribed from task:', taskId);
        return true;
    }

    /**
     * Unsubscribe from all task-specific SSE streams
     * Called during cleanup to ensure all connections are closed
     */
    function unsubscribeAllTasks() {
        state.taskSubscriptions.forEach(function(taskManager, taskId) {
            try {
                taskManager.disconnect();
            } catch (error) {
                console.debug('Error disconnecting task subscription:', taskId, error);
            }
        });
        state.taskSubscriptions.clear();
        console.debug('Unsubscribed from all task streams');
    }

    /**
     * Cleanup resources
     */
    function cleanup() {
        stopPolling();

        // Disconnect all task-specific SSE subscriptions
        unsubscribeAllTasks();

        // Disconnect global SSE manager
        if (state.sseManager) {
            state.sseManager.disconnect();
            state.sseManager = null;
        }

        // Update connection state
        state.sseConnectionState = 'disconnected';
        updateConnectionIndicator();
    }

    /**
     * Get current task count
     */
    function getTaskCount() {
        return state.tasks.size;
    }

    /**
     * Get all active tasks
     */
    function getActiveTasks() {
        return Array.from(state.tasks.values()).filter(function(t) {
            return t.status === TaskStatus.PENDING || t.status === TaskStatus.RUNNING;
        });
    }

    /**
     * Get current SSE connection state
     * @returns {string} 'connected', 'reconnecting', 'fallback', or 'disconnected'
     */
    function getConnectionState() {
        return state.sseConnectionState;
    }

    /**
     * Check if SSE is connected
     * @returns {boolean}
     */
    function isSSEConnected() {
        return state.sseConnectionState === 'connected';
    }

    /**
     * Manually reconnect SSE
     */
    function reconnect() {
        if (state.useSSE && typeof SSEConnectionManager !== 'undefined') {
            connectSSE();
        }
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
        getConnectionState: getConnectionState,
        isSSEConnected: isSSEConnected,
        reconnect: reconnect,
        cleanup: cleanup,
        subscribeToTask: subscribeToTask,
        unsubscribeFromTask: unsubscribeFromTask,
        TaskStatus: TaskStatus
    };
})();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    BackgroundTasksIndicator.init();
});
