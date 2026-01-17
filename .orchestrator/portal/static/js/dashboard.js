/**
 * Dashboard page functionality
 * Handles plan creation form submission
 */

function initDashboard() {
    const form = document.getElementById('plan-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('plan-description');
        const description = input.value;
        const button = this.querySelector('button[type="submit"]');

        if (!description.trim()) {
            input.focus();
            input.style.borderColor = '#EF4444';
            setTimeout(() => input.style.borderColor = '', 2000);
            return;
        }

        // Show confirmation dialog before proceeding
        const confirmed = await PlanConfirmDialog.showPlanConfirmDialog(description);
        if (!confirmed) {
            return;
        }

        button.disabled = true;
        button.textContent = 'Creating...';

        try {
            const response = await fetch('/api/workflows/plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: description })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.run_id) {
                window.location.href = '/runs/' + data.run_id;
            } else {
                throw new Error('No run_id in response');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to create plan: ' + error.message);
            button.disabled = false;
            button.textContent = 'Create Plan';
        }
    });
}

function initSyncRemote() {
    const button = document.getElementById('sync-remote-btn');
    if (!button) return;

    button.addEventListener('click', async function() {
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = 'Syncing...';

        try {
            const response = await fetch('/api/workflows/sync-remote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.run_id) {
                window.location.href = '/runs/' + data.run_id;
            } else {
                throw new Error('No run_id in response');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to sync remote: ' + error.message);
            button.disabled = false;
            button.textContent = originalText;
        }
    });
}

/**
 * Live Builds Module
 * Handles real-time build progress updates via polling and SSE
 */
let liveBuildsState = {
    pollTimer: null,
    elapsedTimer: null,
    eventSources: {},
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
        const runId = card.dataset.runId;
        const stillActive = runs.some(function(r) { return r.id === runId; });
        if (!stillActive) {
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

function connectSSE(runId, card) {
    // Close existing connection if any
    if (liveBuildsState.eventSources[runId]) {
        liveBuildsState.eventSources[runId].close();
    }

    const es = new EventSource('/api/runs/' + runId + '/events');

    es.onmessage = function(e) {
        try {
            const event = JSON.parse(e.data);
            handleSSEEvent(card, event);
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    };

    es.onerror = function() {
        console.log('SSE closed for run:', runId);
        es.close();
        delete liveBuildsState.eventSources[runId];
    };

    liveBuildsState.eventSources[runId] = es;
}

function handleSSEEvent(card, event) {
    // Update progress
    if (event.progress !== undefined) {
        const progressBar = card.querySelector('.progress-bar');
        const progressPercent = card.querySelector('.progress-percent');
        if (progressBar) progressBar.style.width = event.progress + '%';
        if (progressPercent) progressPercent.textContent = event.progress + '%';
    }

    // Update current step
    if (event.step) {
        const stepEl = card.querySelector('.current-step');
        if (stepEl) stepEl.textContent = event.step;
    }

    // Update status
    if (event.status) {
        const badge = card.querySelector('.status-badge');
        if (badge) {
            badge.textContent = event.status;
            badge.className = 'status-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + getStatusClasses(event.status);
        }
        card.dataset.runStatus = event.status;
    }

    // Handle completion
    if (event.type === 'done') {
        const runId = card.dataset.runId;
        if (liveBuildsState.eventSources[runId]) {
            liveBuildsState.eventSources[runId].close();
            delete liveBuildsState.eventSources[runId];
        }
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

// Cleanup function for page unload
function cleanupLiveBuilds() {
    stopLivePolling();
    if (liveBuildsState.elapsedTimer) {
        clearInterval(liveBuildsState.elapsedTimer);
    }
    Object.keys(liveBuildsState.eventSources).forEach(function(runId) {
        liveBuildsState.eventSources[runId].close();
    });
    liveBuildsState.eventSources = {};
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
    initSyncRemote();
    initLiveBuilds();
});

// Cleanup on page unload
window.addEventListener('beforeunload', cleanupLiveBuilds);
