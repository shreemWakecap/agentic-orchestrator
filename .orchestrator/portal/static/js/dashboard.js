/**
 * Dashboard page functionality
 * Handles quick actions navigation and live build monitoring
 */

/**
 * Live Builds Module
 * Handles real-time build progress updates via polling and SSE
 * Uses SSEConnectionManager for robust connection handling
 */
let liveBuildsState = {
    pollTimer: null,
    elapsedTimer: null,
    sseConnections: {},  // SSEConnectionManager instances keyed by runId
    POLL_INTERVAL: 2000, // 2 seconds
    ELAPSED_INTERVAL: 1000
};

function initLiveBuilds() {
    const container = document.getElementById('live-builds-container');
    if (!container) return;

    // Initial fetch
    fetchActiveRuns();

    // Start polling every 2 seconds
    startLivePolling();

    // Start elapsed time updates
    startElapsedTimeUpdates();

    // Setup refresh button
    const refreshBtn = document.getElementById('refresh-builds-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            const icon = refreshBtn.querySelector('svg');
            if (icon) icon.classList.add('animate-spin');
            fetchActiveRuns().finally(function() {
                setTimeout(function() {
                    if (icon) icon.classList.remove('animate-spin');
                }, 500);
            });
        });
    }

    // Start SSE for existing active builds
    document.querySelectorAll('.live-build-card').forEach(function(card) {
        const runId = card.dataset.runId;
        const status = card.dataset.runStatus;
        if (status === 'running' || status === 'pending') {
            connectSSE(runId, card);
        }
    });
}

function startLivePolling() {
    if (liveBuildsState.pollTimer) {
        clearInterval(liveBuildsState.pollTimer);
    }
    liveBuildsState.pollTimer = setInterval(fetchActiveRuns, liveBuildsState.POLL_INTERVAL);
}

function stopLivePolling() {
    if (liveBuildsState.pollTimer) {
        clearInterval(liveBuildsState.pollTimer);
        liveBuildsState.pollTimer = null;
    }
}

async function fetchActiveRuns() {
    try {
        const response = await fetch('/api/runs?status=running,pending&limit=10');
        if (!response.ok) {
            throw new Error('Failed to fetch runs');
        }
        const data = await response.json();
        updateLiveBuildsUI(data.runs || []);
        return data;
    } catch (error) {
        console.error('Error fetching active runs:', error);
        return null;
    }
}

function updateLiveBuildsUI(runs) {
    const container = document.getElementById('live-builds-container');
    const indicator = document.getElementById('live-builds-indicator');
    const noBuildsMsg = document.getElementById('no-builds-message');
    let listEl = document.getElementById('live-builds-list');

    if (!container) return;

    // Show/hide indicator based on active runs
    if (indicator) {
        indicator.style.display = runs.length > 0 ? 'flex' : 'none';
    }

    if (runs.length === 0) {
        if (noBuildsMsg) noBuildsMsg.style.display = 'block';
        if (listEl) listEl.innerHTML = '';
        return;
    }

    if (noBuildsMsg) noBuildsMsg.style.display = 'none';

    // Create list container if needed
    if (!listEl) {
        listEl = document.createElement('div');
        listEl.id = 'live-builds-list';
        listEl.className = 'space-y-4';
        container.innerHTML = '';
        container.appendChild(listEl);
    }

    // Update or create cards for each run
    runs.forEach(function(run) {
        let card = document.querySelector('.live-build-card[data-run-id="' + run.id + '"]');

        if (card) {
            // Update existing card
            updateBuildCardProgress(card, run);
        } else {
            // Create new card
            card = createBuildCard(run);
            listEl.appendChild(card);

            // Connect SSE for new active run
            if (run.status === 'running' || run.status === 'pending') {
                connectSSE(run.id, card);
            }
        }
    });

    // Remove cards for runs no longer active
    document.querySelectorAll('.live-build-card').forEach(function(card) {
        var runId = card.dataset.runId;
        var stillActive = runs.some(function(r) { return r.id === runId; });
        if (!stillActive) {
            // Clean up SSE connection before removing card
            disconnectSSE(runId, card);
            card.classList.add('opacity-50');
            setTimeout(function() { card.remove(); }, 1000);
        }
    });
}

function createBuildCard(run) {
    const card = document.createElement('div');
    card.className = 'border border-gray-200 rounded-lg p-4 live-build-card';
    card.dataset.runId = run.id;
    card.dataset.runStatus = run.status;
    card.dataset.startedAt = run.started_at || new Date().toISOString();

    const statusClasses = getStatusClasses(run.status);
    const progress = run.progress || 0;
    const currentStep = run.current_step || 'Initializing...';
    const workflow = run.workflow ? run.workflow.charAt(0).toUpperCase() + run.workflow.slice(1) : 'Build';

    card.innerHTML =
        '<div class="flex items-center justify-between mb-3">' +
            '<div class="flex items-center">' +
                '<a href="/runs/' + escapeHtml(run.id) + '" class="text-sm font-medium text-blue-600 hover:text-blue-800">' +
                    escapeHtml(workflow) +
                '</a>' +
                '<span class="ml-2 text-xs text-gray-500">' + escapeHtml(run.id.substring(0, 8)) + '</span>' +
            '</div>' +
            '<div class="flex items-center space-x-3">' +
                '<span class="text-xs text-gray-500 elapsed-time" data-started="' + escapeHtml(run.started_at || '') + '">--:--</span>' +
                '<span class="status-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + statusClasses + '">' +
                    escapeHtml(run.status) +
                '</span>' +
            '</div>' +
        '</div>' +
        '<div class="mb-2">' +
            '<div class="flex items-center justify-between text-xs text-gray-600 mb-1">' +
                '<span class="current-step">' + escapeHtml(currentStep) + '</span>' +
                '<span class="progress-percent">' + progress + '%</span>' +
            '</div>' +
            '<div class="w-full bg-gray-200 rounded-full h-2.5">' +
                '<div class="progress-bar bg-blue-600 h-2.5 rounded-full transition-all duration-300" style="width: ' + progress + '%"></div>' +
            '</div>' +
        '</div>' +
        '<div class="step-details mt-2 text-xs text-gray-500">' +
            (run.total_steps ? '<span>Step ' + (run.current_step_num || 0) + ' of ' + run.total_steps + '</span>' : '') +
        '</div>';

    return card;
}

function updateBuildCardProgress(card, run) {
    // Update progress bar
    const progressBar = card.querySelector('.progress-bar');
    const progressPercent = card.querySelector('.progress-percent');
    const progress = run.progress || 0;

    if (progressBar) {
        progressBar.style.width = progress + '%';
    }
    if (progressPercent) {
        progressPercent.textContent = progress + '%';
    }

    // Update current step
    if (run.current_step) {
        const stepEl = card.querySelector('.current-step');
        if (stepEl) {
            stepEl.textContent = run.current_step;
        }
    }

    // Update status badge
    if (run.status) {
        const badge = card.querySelector('.status-badge');
        if (badge) {
            badge.textContent = run.status;
            badge.className = 'status-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + getStatusClasses(run.status);
        }
        card.dataset.runStatus = run.status;
    }

    // Update step details
    if (run.total_steps) {
        const stepDetails = card.querySelector('.step-details');
        if (stepDetails) {
            stepDetails.innerHTML = '<span>Step ' + (run.current_step_num || 0) + ' of ' + run.total_steps + '</span>';
        }
    }
}

/**
 * Connect to SSE for a specific run using SSEConnectionManager
 * @param {string} runId - The run ID to connect to
 * @param {HTMLElement} card - The build card element
 */
function connectSSE(runId, card) {
    // Close existing connection if any
    if (liveBuildsState.sseConnections[runId]) {
        liveBuildsState.sseConnections[runId].disconnect();
        delete liveBuildsState.sseConnections[runId];
    }

    // Check if SSEConnectionManager is available
    if (typeof SSEConnectionManager === 'undefined') {
        console.warn('SSEConnectionManager not available, using fallback polling');
        return;
    }

    var url = '/api/runs/' + runId + '/events';
    var manager = new SSEConnectionManager(url, {
        maxReconnectAttempts: 5,
        heartbeatTimeout: 45000,
        enablePollingFallback: true,
        pollingInterval: 2000
    });

    // Set up polling fallback
    manager.setPollingFallback(function() {
        return fetchRunStatus(runId).then(function(run) {
            if (run) {
                updateBuildCardProgress(card, run);
                // Clean up if terminal state
                if (run.status === 'completed' || run.status === 'failed' || run.status === 'error') {
                    disconnectSSE(runId, card);
                }
            }
        });
    });

    // Handle connection state changes
    manager.onStateChange(function(newState, oldState) {
        updateCardConnectionState(card, newState, runId);
    });

    // Handle incoming messages
    manager.onMessage(function(data, event) {
        handleSSEEvent(card, data);

        // Clean up on terminal events
        if (data && (data.type === 'done' || data.status === 'completed' || data.status === 'failed' || data.status === 'error')) {
            disconnectSSE(runId, card);
        }
    });

    // Store connection and connect
    liveBuildsState.sseConnections[runId] = manager;
    manager.connect();
}

/**
 * Disconnect SSE for a specific run and clean up
 * @param {string} runId - The run ID to disconnect
 * @param {HTMLElement} [card] - Optional card element to update
 */
function disconnectSSE(runId, card) {
    var manager = liveBuildsState.sseConnections[runId];
    if (manager) {
        manager.disconnect();
        delete liveBuildsState.sseConnections[runId];
    }

    // Clear connection state indicator
    if (card) {
        updateCardConnectionState(card, 'disconnected', runId);
    }
}

/**
 * Update card UI to reflect SSE connection state
 * @param {HTMLElement} card - The build card element
 * @param {string} state - The connection state
 * @param {string} runId - The run ID (for logging)
 */
function updateCardConnectionState(card, state, runId) {
    if (!card) return;

    // Find or create connection indicator
    var indicator = card.querySelector('.sse-connection-indicator');
    if (!indicator) {
        indicator = document.createElement('span');
        indicator.className = 'sse-connection-indicator';
        // Insert in header area
        var header = card.querySelector('.flex.items-center.justify-between');
        if (header) {
            var statusContainer = header.querySelector('.flex.items-center.space-x-3');
            if (statusContainer) {
                statusContainer.insertBefore(indicator, statusContainer.firstChild);
            }
        }
    }

    // Update indicator based on state
    var ConnectionState = SSEConnectionManager.ConnectionState;
    switch (state) {
        case ConnectionState.CONNECTING:
            indicator.innerHTML = '<span class="inline-flex items-center text-xs text-gray-400" title="Connecting..."><svg class="animate-spin h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg></span>';
            indicator.style.display = 'inline-flex';
            break;

        case ConnectionState.CONNECTED:
            indicator.innerHTML = '<span class="inline-flex items-center text-xs text-green-500" title="Live"><span class="relative flex h-2 w-2 mr-1"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span></span></span>';
            indicator.style.display = 'inline-flex';
            break;

        case ConnectionState.RECONNECTING:
            indicator.innerHTML = '<span class="inline-flex items-center text-xs text-yellow-500" title="Reconnecting..."><svg class="animate-spin h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg></span>';
            indicator.style.display = 'inline-flex';
            card.classList.add('sse-reconnecting');
            break;

        case ConnectionState.FAILED:
            indicator.innerHTML = '<span class="inline-flex items-center text-xs text-orange-500" title="Using polling fallback"><svg class="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg></span>';
            indicator.style.display = 'inline-flex';
            card.classList.remove('sse-reconnecting');
            break;

        case ConnectionState.DISCONNECTED:
        default:
            indicator.style.display = 'none';
            card.classList.remove('sse-reconnecting');
            break;
    }
}

/**
 * Fetch run status for polling fallback
 * @param {string} runId - The run ID to fetch
 * @returns {Promise<Object|null>} The run data or null on error
 */
async function fetchRunStatus(runId) {
    try {
        var response = await fetch('/api/runs/' + encodeURIComponent(runId));
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.debug('fetchRunStatus error:', error);
        return null;
    }
}

function handleSSEEvent(card, event) {
    if (!event || !card) return;

    // Update progress
    if (event.progress !== undefined) {
        var progressBar = card.querySelector('.progress-bar');
        var progressPercent = card.querySelector('.progress-percent');
        if (progressBar) progressBar.style.width = event.progress + '%';
        if (progressPercent) progressPercent.textContent = event.progress + '%';
    }

    // Update current step
    if (event.step) {
        var stepEl = card.querySelector('.current-step');
        if (stepEl) stepEl.textContent = event.step;
    }

    // Update status
    if (event.status) {
        var badge = card.querySelector('.status-badge');
        if (badge) {
            badge.textContent = event.status;
            badge.className = 'status-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + getStatusClasses(event.status);
        }
        card.dataset.runStatus = event.status;
    }

    // Handle completion or failure (terminal states)
    var isTerminal = event.type === 'done' ||
                     event.status === 'completed' ||
                     event.status === 'failed' ||
                     event.status === 'error';

    if (isTerminal) {
        var runId = card.dataset.runId;
        // Note: disconnectSSE is called by the connectSSE message handler
        // to ensure cleanup happens in one place

        // Fade out after completion
        setTimeout(function() {
            card.classList.add('opacity-50');
        }, 1000);
    }
}

function getStatusClasses(status) {
    const classMap = {
        completed: 'bg-green-100 text-green-800',
        running: 'bg-blue-100 text-blue-800',
        pending: 'bg-yellow-100 text-yellow-800',
        failed: 'bg-red-100 text-red-800',
        error: 'bg-red-100 text-red-800'
    };
    return classMap[status] || 'bg-gray-100 text-gray-800';
}

function startElapsedTimeUpdates() {
    if (liveBuildsState.elapsedTimer) {
        clearInterval(liveBuildsState.elapsedTimer);
    }

    function updateAllElapsed() {
        document.querySelectorAll('.elapsed-time').forEach(function(el) {
            const started = el.dataset.started;
            if (!started) return;

            const startTime = new Date(started);
            const now = new Date();
            const elapsed = Math.floor((now - startTime) / 1000);

            el.textContent = formatElapsedTime(elapsed);
        });
    }

    updateAllElapsed();
    liveBuildsState.elapsedTimer = setInterval(updateAllElapsed, liveBuildsState.ELAPSED_INTERVAL);
}

function formatElapsedTime(seconds) {
    if (seconds < 0) seconds = 0;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const pad = function(n) { return n < 10 ? '0' + n : '' + n; };

    if (hours > 0) {
        return hours + ':' + pad(minutes) + ':' + pad(secs);
    }
    return minutes + ':' + pad(secs);
}

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Poll a task until it completes or fails
 * @param {string} taskId - The task ID to poll
 * @param {string} taskType - The task type for indicator updates
 * @param {number} maxAttempts - Maximum poll attempts (default 120 = 2 minutes at 1s interval)
 * @param {number} interval - Poll interval in ms (default 1000)
 * @returns {Promise<Object>} The task result
 */
async function pollTaskUntilComplete(taskId, taskType, maxAttempts, interval) {
    maxAttempts = maxAttempts || 120;
    interval = interval || 1000;

    let attempts = 0;

    while (attempts < maxAttempts) {
        attempts++;

        try {
            const response = await fetch('/api/background-tasks/' + encodeURIComponent(taskId));

            if (!response.ok) {
                throw new Error('Failed to fetch task status: HTTP ' + response.status);
            }

            const task = await response.json();

            // Update background indicator with progress
            if (typeof BackgroundTasksIndicator !== 'undefined' && BackgroundTasksIndicator.updateTask) {
                try {
                    BackgroundTasksIndicator.updateTask(taskId, {
                        status: task.status,
                        progress: task.progress || 0,
                        message: task.message || task.current_step || 'Processing...'
                    });
                } catch (e) {
                    console.warn('BackgroundTasksIndicator.updateTask error:', e);
                }
            }

            // Check if task is complete
            if (task.status === 'completed') {
                // Mark as completed in indicator
                if (typeof BackgroundTasksIndicator !== 'undefined' && BackgroundTasksIndicator.updateTask) {
                    try {
                        BackgroundTasksIndicator.updateTask(taskId, {
                            status: 'completed',
                            progress: 100,
                            message: 'Completed'
                        });
                    } catch (e) {
                        console.warn('BackgroundTasksIndicator.updateTask error:', e);
                    }
                }
                console.log('Task completed, result:', task.result);
                return task.result || task;
            }

            // Check if task failed
            if (task.status === 'failed' || task.status === 'error') {
                // Mark as failed in indicator
                if (typeof BackgroundTasksIndicator !== 'undefined' && BackgroundTasksIndicator.updateTask) {
                    try {
                        BackgroundTasksIndicator.updateTask(taskId, {
                            status: 'failed',
                            message: task.error || 'Task failed'
                        });
                    } catch (e) {
                        console.warn('BackgroundTasksIndicator.updateTask error:', e);
                    }
                }
                throw new Error(task.error || 'Task failed');
            }

            // Wait before next poll
            await new Promise(function(resolve) { setTimeout(resolve, interval); });

        } catch (error) {
            // On network error, wait and retry
            if (attempts < maxAttempts) {
                await new Promise(function(resolve) { setTimeout(resolve, interval * 2); });
            } else {
                throw error;
            }
        }
    }

    // Timeout reached
    if (typeof BackgroundTasksIndicator !== 'undefined') {
        BackgroundTasksIndicator.updateTask(taskId, {
            status: 'failed',
            message: 'Task timed out'
        });
    }
    throw new Error('Task polling timed out after ' + maxAttempts + ' attempts');
}

// Cleanup function for page unload
function cleanupLiveBuilds() {
    stopLivePolling();
    if (liveBuildsState.elapsedTimer) {
        clearInterval(liveBuildsState.elapsedTimer);
        liveBuildsState.elapsedTimer = null;
    }

    // Disconnect all SSE connections using SSEConnectionManager
    Object.keys(liveBuildsState.sseConnections).forEach(function(runId) {
        var manager = liveBuildsState.sseConnections[runId];
        if (manager && typeof manager.disconnect === 'function') {
            manager.disconnect();
        }
    });
    liveBuildsState.sseConnections = {};
}

/**
 * Stuck Plans Recovery Module
 * Handles detection and recovery of stuck/stale builds
 */
let stuckPlansState = {
    pollTimer: null,
    POLL_INTERVAL: 30000 // 30 seconds
};

function initStuckPlans() {
    const section = document.getElementById('stuck-plans-section');
    if (!section) return;

    // Initial fetch
    fetchStuckPlans();

    // Start polling for stuck plans
    startStuckPlanPolling();

    // Setup refresh button
    const refreshBtn = document.getElementById('refresh-stuck-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            const icon = refreshBtn.querySelector('svg');
            if (icon) icon.classList.add('animate-spin');
            fetchStuckPlans().finally(function() {
                setTimeout(function() {
                    if (icon) icon.classList.remove('animate-spin');
                }, 500);
            });
        });
    }
}

function startStuckPlanPolling() {
    if (stuckPlansState.pollTimer) {
        clearInterval(stuckPlansState.pollTimer);
    }
    stuckPlansState.pollTimer = setInterval(fetchStuckPlans, stuckPlansState.POLL_INTERVAL);
}

async function fetchStuckPlans() {
    try {
        const response = await fetch('/api/plans/recovery/stuck');
        if (!response.ok) {
            throw new Error('Failed to fetch stuck plans');
        }
        const data = await response.json();
        updateStuckPlansUI(data.plans || []);
        return data;
    } catch (error) {
        console.error('Error fetching stuck plans:', error);
        // Hide section on error
        const section = document.getElementById('stuck-plans-section');
        if (section) section.classList.add('hidden');
        return null;
    }
}

function updateStuckPlansUI(plans) {
    const section = document.getElementById('stuck-plans-section');
    const listEl = document.getElementById('stuck-plans-list');

    if (!section || !listEl) return;

    if (!plans || plans.length === 0) {
        section.classList.add('hidden');
        return;
    }

    // Show section
    section.classList.remove('hidden');

    // Build cards HTML
    var html = '';
    plans.forEach(function(plan) {
        html += createStuckPlanCard(plan);
    });

    listEl.innerHTML = html;

    // Attach event handlers
    plans.forEach(function(plan) {
        attachRecoveryHandlers(plan.plan_id);
    });
}

function createStuckPlanCard(plan) {
    var statusBadgeClass = plan.status === 'building'
        ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white'
        : 'bg-gradient-to-r from-amber-500 to-orange-500 text-white';

    var timeStale = formatStaleTime(plan.minutes_stale || 0);
    var progressPercent = plan.progress_percent || 0;
    var currentStep = plan.current_step || 'Unknown step';
    var planName = plan.plan_name || plan.plan_id.substring(0, 8);

    var html = '';
    html += '<div class="glass rounded-2xl p-6 stuck-plan-card group hover:shadow-lg transition-all duration-300" data-plan-id="' + escapeHtml(plan.plan_id) + '">';

    // Header row
    html += '<div class="flex items-center justify-between mb-4">';
    html += '<div class="flex items-center">';
    html += '<div class="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-red-600 flex items-center justify-center mr-4 shadow-md group-hover:scale-105 transition-transform">';
    html += '<svg class="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
    html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>';
    html += '</svg>';
    html += '</div>';
    html += '<div>';
    html += '<a href="/plans/' + escapeHtml(plan.plan_id) + '" class="text-lg font-semibold text-primary dark:text-primary hover:text-blue-600 dark:hover:text-blue-400 transition-colors">';
    html += escapeHtml(planName);
    html += '</a>';
    html += '<div class="text-xs text-tertiary dark:text-tertiary mt-0.5">Stuck for <span class="font-semibold text-amber-600 dark:text-amber-400">' + timeStale + '</span></div>';
    html += '</div>';
    html += '</div>';

    // Status badge
    html += '<span class="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold tracking-wide uppercase shadow-sm ' + statusBadgeClass + '">';
    html += escapeHtml(plan.status);
    html += '</span>';
    html += '</div>';

    // Progress info
    html += '<div class="mb-4">';
    html += '<div class="flex items-center justify-between text-sm mb-2">';
    html += '<span class="text-secondary dark:text-secondary font-medium">' + escapeHtml(currentStep) + '</span>';
    html += '<span class="font-bold text-primary dark:text-primary">' + progressPercent + '%</span>';
    html += '</div>';
    html += '<div class="relative w-full h-3 bg-tertiary dark:bg-tertiary rounded-full overflow-hidden">';
    html += '<div class="h-full rounded-full bg-gradient-to-r from-amber-500 to-red-500" style="width: ' + progressPercent + '%"></div>';
    html += '</div>';
    html += '</div>';

    // Additional info
    if (plan.last_error) {
        html += '<div class="glass rounded-lg p-3 mb-4 text-sm">';
        html += '<div class="flex items-start">';
        html += '<svg class="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
        html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>';
        html += '</svg>';
        html += '<span class="text-red-600 dark:text-red-400">' + escapeHtml(plan.last_error) + '</span>';
        html += '</div>';
        html += '</div>';
    }

    // Recovery actions
    html += '<div class="flex items-center gap-3">';
    if (plan.can_resume) {
        html += '<button type="button" class="resume-btn btn btn-primary btn-modern group flex-1" data-plan-id="' + escapeHtml(plan.plan_id) + '">';
        html += '<svg class="h-4 w-4 mr-2 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
        html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>';
        html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>';
        html += '</svg>';
        html += 'Resume Build';
        html += '</button>';
    }
    html += '<button type="button" class="restart-btn btn btn-secondary btn-modern group" data-plan-id="' + escapeHtml(plan.plan_id) + '">';
    html += '<svg class="h-4 w-4 mr-2 group-hover:rotate-180 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
    html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>';
    html += '</svg>';
    html += 'Restart';
    html += '</button>';
    html += '<button type="button" class="cancel-btn btn btn-sm text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20" data-plan-id="' + escapeHtml(plan.plan_id) + '" title="Cancel build">';
    html += '<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
    html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>';
    html += '</svg>';
    html += '</button>';
    html += '</div>';

    html += '</div>';

    return html;
}

function attachRecoveryHandlers(planId) {
    var card = document.querySelector('.stuck-plan-card[data-plan-id="' + planId + '"]');
    if (!card) return;

    var resumeBtn = card.querySelector('.resume-btn');
    var restartBtn = card.querySelector('.restart-btn');
    var cancelBtn = card.querySelector('.cancel-btn');

    if (resumeBtn) {
        resumeBtn.addEventListener('click', function() {
            recoverPlan(planId, 'resume');
        });
    }

    if (restartBtn) {
        restartBtn.addEventListener('click', function() {
            recoverPlan(planId, 'restart');
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            if (confirm('Cancel the build for this plan? You can resume or restart later.')) {
                cancelBuild(planId);
            }
        });
    }
}

async function recoverPlan(planId, action) {
    var card = document.querySelector('.stuck-plan-card[data-plan-id="' + planId + '"]');
    var button = card ? card.querySelector('.' + action + '-btn') : null;
    var originalText = '';

    if (button) {
        originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>' +
            (action === 'resume' ? 'Resuming...' : 'Restarting...');
    }

    try {
        var response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/recover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });

        if (!response.ok) {
            var errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Recovery failed');
        }

        var data = await response.json();

        if (data.run_id) {
            // Redirect to the run page
            window.location.href = '/runs/' + data.run_id;
        } else {
            // Refresh stuck plans list
            fetchStuckPlans();
        }
    } catch (error) {
        console.error('Error recovering plan:', error);
        alert('Failed to ' + action + ' plan: ' + error.message);

        if (button) {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
}

async function cancelBuild(planId) {
    try {
        var response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            var errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Cancel failed');
        }

        // Refresh stuck plans list
        fetchStuckPlans();
    } catch (error) {
        console.error('Error canceling build:', error);
        alert('Failed to cancel build: ' + error.message);
    }
}

function formatStaleTime(minutes) {
    if (minutes < 1) {
        return 'less than a minute';
    } else if (minutes === 1) {
        return '1 minute';
    } else if (minutes < 60) {
        return minutes + ' minutes';
    } else {
        var hours = Math.floor(minutes / 60);
        var remainingMinutes = minutes % 60;
        if (hours === 1) {
            return remainingMinutes > 0 ? '1 hour ' + remainingMinutes + ' min' : '1 hour';
        }
        return remainingMinutes > 0 ? hours + ' hours ' + remainingMinutes + ' min' : hours + ' hours';
    }
}

function cleanupStuckPlans() {
    if (stuckPlansState.pollTimer) {
        clearInterval(stuckPlansState.pollTimer);
        stuckPlansState.pollTimer = null;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initLiveBuilds();
    initStuckPlans();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    cleanupLiveBuilds();
    cleanupStuckPlans();
});
