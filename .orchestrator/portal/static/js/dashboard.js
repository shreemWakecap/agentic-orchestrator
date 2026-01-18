/**
 * Dashboard page functionality
 * Handles plan creation form submission
 */

function initDashboard() {
    const form = document.getElementById('plan-form');
    if (!form) return;

    // Setup "Improve with AI" button
    const improveBtn = document.getElementById('improve-request-btn');
    const descriptionInput = document.getElementById('plan-description');

    if (improveBtn && descriptionInput) {
        improveBtn.addEventListener('click', async function() {
            const draftText = descriptionInput.value.trim();

            if (!draftText) {
                descriptionInput.focus();
                descriptionInput.style.borderColor = '#EF4444';
                setTimeout(function() {
                    descriptionInput.style.borderColor = '';
                }, 2000);
                return;
            }

            // Show improving state
            const originalText = improveBtn.textContent;
            improveBtn.disabled = true;
            improveBtn.textContent = 'Improving...';

            try {
                // POST to create async task
                const response = await fetch('/api/workflows/improve-request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ draft: draftText })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                const taskId = data.task_id || data.run_id;

                if (!taskId) {
                    throw new Error('No task_id or run_id in response');
                }

                // Add task to background indicator (if available)
                if (typeof BackgroundTasksIndicator !== 'undefined' && BackgroundTasksIndicator.addTask) {
                    try {
                        BackgroundTasksIndicator.addTask({
                            id: taskId,
                            type: 'improve-request',
                            status: 'running',
                            progress: 0,
                            message: 'Improving request with AI...'
                        });
                    } catch (indicatorError) {
                        console.warn('BackgroundTasksIndicator error:', indicatorError);
                    }
                }

                // Poll for task completion
                console.log('Polling for task:', taskId);
                const result = await pollTaskUntilComplete(taskId, 'improve-request');
                console.log('Poll result:', result);

                // Update textarea with improved text
                // Backend returns: { improved: "...", original: "...", success: true }
                if (result && result.improved) {
                    descriptionInput.value = result.improved;
                    // Add visual feedback that text was updated
                    descriptionInput.style.borderColor = '#8B5CF6';
                    setTimeout(function() {
                        descriptionInput.style.borderColor = '';
                    }, 2000);
                } else if (result && result.error) {
                    throw new Error(result.error);
                } else {
                    console.warn('Unexpected result format:', result);
                    // Try to extract improved text from nested result
                    if (result && result.result && result.result.improved) {
                        descriptionInput.value = result.result.improved;
                        descriptionInput.style.borderColor = '#8B5CF6';
                        setTimeout(function() {
                            descriptionInput.style.borderColor = '';
                        }, 2000);
                    } else if (!result.success) {
                        console.log('Task completed but improvement failed, keeping original text');
                    }
                }
            } catch (error) {
                console.error('Error improving request:', error);
                alert('Failed to improve request: ' + error.message);
            } finally {
                improveBtn.disabled = false;
                improveBtn.textContent = originalText;
            }
        });
    }

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

        // Get auto-merge setting
        const autoMergeCheckbox = document.getElementById('sync-auto-merge');
        const autoMerge = autoMergeCheckbox ? autoMergeCheckbox.checked : true;

        try {
            const response = await fetch('/api/workflows/sync-remote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auto_merge: autoMerge })
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

    // Setup refresh sync status button
    const refreshBtn = document.getElementById('sync-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            const icon = refreshBtn.querySelector('svg');
            if (icon) icon.classList.add('animate-spin');
            fetchSyncStatus().finally(function() {
                setTimeout(function() {
                    if (icon) icon.classList.remove('animate-spin');
                }, 500);
            });
        });
    }

    // Setup pull latest button
    const pullLatestBtn = document.getElementById('pull-latest-btn');
    if (pullLatestBtn) {
        pullLatestBtn.addEventListener('click', async function() {
            pullLatestBtn.disabled = true;
            const icon = pullLatestBtn.querySelector('svg');
            if (icon) icon.classList.add('animate-bounce');

            try {
                const response = await fetch('/api/workflows/pull-latest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const data = await response.json();
                if (data.success) {
                    // Refresh sync status after pull
                    fetchSyncStatus();
                    fetchBranchesAndPRs();
                } else {
                    alert('Pull failed: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error pulling latest:', error);
                alert('Failed to pull latest: ' + error.message);
            } finally {
                pullLatestBtn.disabled = false;
                if (icon) icon.classList.remove('animate-bounce');
            }
        });
    }

    // Initial fetch of branches and PRs
    fetchBranchesAndPRs();
}

/**
 * Fetch and display local sync branches and open PRs
 */
async function fetchBranchesAndPRs() {
    // Fetch branches
    try {
        const branchResponse = await fetch('/api/workflows/branches');
        const branchData = await branchResponse.json();
        updateBranchList(branchData.branches || []);
    } catch (error) {
        console.error('Error fetching branches:', error);
    }

    // Fetch PRs
    try {
        const prResponse = await fetch('/api/workflows/prs');
        const prData = await prResponse.json();
        updatePRList(prData.prs || []);
    } catch (error) {
        console.error('Error fetching PRs:', error);
    }
}

function updateBranchList(branches) {
    const container = document.getElementById('sync-local-branches');
    const listEl = document.getElementById('sync-branch-list');
    const countEl = document.getElementById('sync-branch-count');

    if (!container || !listEl) return;

    if (branches.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    if (countEl) countEl.textContent = branches.length;

    var html = '';
    branches.forEach(function(branch) {
        html += '<li class="px-4 py-3 flex items-center justify-between hover:bg-tertiary/30 dark:hover:bg-tertiary/30">';
        html += '<div class="min-w-0 flex-1">';
        html += '<div class="text-sm font-mono text-primary dark:text-primary truncate">' + escapeHtml(branch.name) + '</div>';
        html += '<div class="text-xs text-tertiary dark:text-tertiary truncate">' + escapeHtml(branch.message || '') + '</div>';
        html += '</div>';
        html += '<button type="button" class="ml-3 btn btn-xs text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20" onclick="deleteBranch(\'' + escapeHtml(branch.name) + '\')" title="Delete branch">';
        html += '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>';
        html += '</button>';
        html += '</li>';
    });
    listEl.innerHTML = html;
}

function updatePRList(prs) {
    const container = document.getElementById('sync-open-prs');
    const listEl = document.getElementById('sync-pr-list');
    const countEl = document.getElementById('sync-pr-count');

    if (!container || !listEl) return;

    if (prs.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    if (countEl) countEl.textContent = prs.length;

    var html = '';
    prs.forEach(function(pr) {
        html += '<li class="px-4 py-3 flex items-center justify-between hover:bg-tertiary/30 dark:hover:bg-tertiary/30">';
        html += '<div class="min-w-0 flex-1">';
        html += '<a href="' + escapeHtml(pr.url) + '" target="_blank" class="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">';
        html += '#' + pr.number + ' ' + escapeHtml(pr.title);
        html += '</a>';
        html += '<div class="text-xs text-tertiary dark:text-tertiary">' + escapeHtml(pr.head_branch) + ' → ' + escapeHtml(pr.base_branch) + '</div>';
        html += '</div>';
        html += '<button type="button" class="ml-3 btn btn-xs btn-primary" onclick="mergePR(' + pr.number + ')" title="Merge PR">';
        html += '<svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>';
        html += 'Merge';
        html += '</button>';
        html += '</li>';
    });
    listEl.innerHTML = html;
}

async function deleteBranch(branchName) {
    if (!confirm('Delete branch "' + branchName + '"? This cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch('/api/workflows/branches/' + encodeURIComponent(branchName), {
            method: 'DELETE'
        });
        const data = await response.json();
        if (data.success) {
            fetchBranchesAndPRs();
        } else {
            alert('Failed to delete branch: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting branch:', error);
        alert('Failed to delete branch: ' + error.message);
    }
}

async function mergePR(prNumber) {
    if (!confirm('Merge PR #' + prNumber + '? This will merge and delete the remote branch.')) {
        return;
    }

    try {
        const response = await fetch('/api/workflows/prs/' + prNumber + '/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            // Pull latest after merge
            await fetch('/api/workflows/pull-latest', { method: 'POST' });
            fetchBranchesAndPRs();
            fetchSyncStatus();
        } else {
            alert('Failed to merge PR: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error merging PR:', error);
        alert('Failed to merge PR: ' + error.message);
    }
}

/**
 * Sync Status Module
 * Fetches and displays git sync status information
 */
async function fetchSyncStatus() {
    const syncButton = document.getElementById('sync-remote-btn');
    const fileCountEl = document.getElementById('sync-file-count');
    const fileListEl = document.getElementById('sync-file-list');
    const branchInfoEl = document.getElementById('sync-branch');
    const loadingEl = document.getElementById('sync-status-loading');
    const contentEl = document.getElementById('sync-status-content');
    const noChangesEl = document.getElementById('sync-no-changes');
    const stagedCountEl = document.getElementById('sync-staged-count');
    const unstagedCountEl = document.getElementById('sync-unstaged-count');

    // Show loading state
    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    if (noChangesEl) noChangesEl.style.display = 'none';

    try {
        const response = await fetch('/api/workflows/sync-status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Hide loading
        if (loadingEl) loadingEl.style.display = 'none';

        // Check if there are changes to sync
        const totalFiles = data.file_count || 0;

        if (totalFiles === 0 || !data.has_changes) {
            // No changes to sync
            if (noChangesEl) noChangesEl.style.display = 'block';
            if (contentEl) contentEl.style.display = 'none';
            if (syncButton) {
                syncButton.disabled = true;
                syncButton.title = 'No changes to sync';
            }
        } else {
            // Show content
            if (contentEl) contentEl.style.display = 'block';
            if (noChangesEl) noChangesEl.style.display = 'none';
            if (syncButton) {
                syncButton.disabled = false;
                syncButton.title = '';
            }

            // Update file count badge
            if (fileCountEl) {
                fileCountEl.textContent = totalFiles;
            }

            // Update branch info
            if (branchInfoEl) {
                branchInfoEl.textContent = data.branch || '--';
            }

            // Update staged/unstaged counts
            if (stagedCountEl) {
                stagedCountEl.textContent = data.staged_count || 0;
            }
            if (unstagedCountEl) {
                unstagedCountEl.textContent = data.unstaged_count || 0;
            }

            // Update file list (collapsible)
            if (fileListEl) {
                var listContainer = fileListEl.querySelector('ul');
                var emptyMsg = document.getElementById('sync-file-list-empty');

                if (data.files && data.files.length > 0) {
                    if (emptyMsg) emptyMsg.style.display = 'none';
                    if (listContainer) {
                        var listHtml = '';
                        data.files.forEach(function(file) {
                            listHtml += '<li class="px-4 py-2 flex items-center text-sm text-secondary dark:text-secondary">';
                            listHtml += '<svg class="h-4 w-4 mr-2 text-violet-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
                            listHtml += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>';
                            listHtml += '</svg>';
                            listHtml += '<span class="truncate">' + escapeHtml(file) + '</span></li>';
                        });
                        listContainer.innerHTML = listHtml;
                    }
                } else {
                    if (emptyMsg) emptyMsg.style.display = 'block';
                    if (listContainer) listContainer.innerHTML = '';
                }
            }
        }
    } catch (error) {
        console.error('Error fetching sync status:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        if (noChangesEl) {
            noChangesEl.style.display = 'block';
            noChangesEl.textContent = 'Failed to load sync status';
        }
    }
}

function toggleSyncFileList() {
    const fileListEl = document.getElementById('sync-file-list');
    const toggleBtn = document.getElementById('sync-file-list-toggle');
    const chevron = document.getElementById('sync-file-list-chevron');
    if (!fileListEl) return;

    const isHidden = fileListEl.classList.contains('hidden');
    if (isHidden) {
        fileListEl.classList.remove('hidden');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
    } else {
        fileListEl.classList.add('hidden');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
}

function initSyncFileListToggle() {
    const toggleBtn = document.getElementById('sync-file-list-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleSyncFileList);
    }
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
    initSyncFileListToggle();
    initLiveBuilds();
    fetchSyncStatus();
});

// Cleanup on page unload
window.addEventListener('beforeunload', cleanupLiveBuilds);
