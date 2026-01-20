/**
 * Dashboard page functionality
 * Handles plan creation form submission using unified AI-enhanced dialog
 * Integrates with TaskActivityPanel for real-time task visibility
 */

// Task Activity Panel integration state
let taskActivityState = {
    initialized: false,
    logEventSources: {}, // Track SSE connections for task logs
    planningWorkflows: new Map() // Track planning workflows by ID
};

// Textarea enhancer instance for plan description
let planDescriptionEnhancer = null;

function initDashboard() {
    const form = document.getElementById('plan-form');
    if (!form) return;

    const descriptionInput = document.getElementById('plan-description');

    // Initialize TextareaEnhancer for the plan description field
    if (descriptionInput && typeof TextareaEnhancer !== 'undefined') {
        planDescriptionEnhancer = TextareaEnhancer.init(descriptionInput, {
            minHeight: 120,
            maxHeight: 300,
            showCharCount: true,
            minChars: 10,
            maxChars: 5000,
            warnThreshold: 0.9,
            errorThreshold: 0.98,
            ariaLabel: 'Plan description'
        });
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const description = descriptionInput ? descriptionInput.value.trim() : '';

        // Validate using TextareaEnhancer API if available
        if (planDescriptionEnhancer) {
            var charInfo = planDescriptionEnhancer.updateCharCount();

            // Check for empty input
            if (!description) {
                showTextareaError(descriptionInput, 'Please describe what you want to build');
                planDescriptionEnhancer.focus();
                return;
            }

            // Check minimum character requirement
            if (charInfo.count < 10) {
                showTextareaError(descriptionInput, 'Please provide more detail (at least 10 characters)');
                planDescriptionEnhancer.focus();
                return;
            }

            // Check if over max characters
            if (charInfo.status === 'error') {
                showTextareaError(descriptionInput, 'Description is too long. Please shorten it.');
                planDescriptionEnhancer.focus();
                return;
            }

            // Clear any previous error state
            clearTextareaError(descriptionInput);
        } else {
            // Fallback validation without enhancer
            if (!description) {
                if (descriptionInput) {
                    descriptionInput.focus();
                    descriptionInput.classList.add('textarea-enhanced-error');
                    setTimeout(function() {
                        descriptionInput.classList.remove('textarea-enhanced-error');
                    }, 2000);
                }
                return;
            }
        }

        // Use unified dialog which handles AI improvement and plan creation
        if (typeof UnifiedPlanDialog !== 'undefined' && UnifiedPlanDialog.showCreatePlanDialog) {
            var result = await UnifiedPlanDialog.showCreatePlanDialog(description);
            if (result.created) {
                // Dialog handles redirect, but clear input as backup
                if (descriptionInput) {
                    descriptionInput.value = '';
                    // Reset the enhancer state
                    if (planDescriptionEnhancer) {
                        planDescriptionEnhancer.setValue('');
                    }
                }
            }
        } else {
            console.error('UnifiedPlanDialog not available');
            alert('Plan creation dialog is not available. Please refresh the page.');
        }
    });
}

/**
 * Show error state on textarea with smooth visual feedback
 * @param {HTMLTextAreaElement} textarea - The textarea element
 * @param {string} message - Error message to display
 */
function showTextareaError(textarea, message) {
    if (!textarea) return;

    // Add error class for visual feedback
    textarea.classList.add('textarea-enhanced-error');

    // Find or create error message element
    var errorEl = textarea.parentNode.querySelector('.textarea-error-message');
    if (!errorEl) {
        errorEl = document.createElement('div');
        errorEl.className = 'textarea-error-message text-sm text-red-600 dark:text-red-400 mt-1 flex items-center animate-shake';
        errorEl.setAttribute('role', 'alert');
        errorEl.setAttribute('aria-live', 'polite');

        // Insert after char count if it exists, otherwise after textarea
        var charCount = textarea.parentNode.querySelector('.textarea-char-count');
        if (charCount) {
            charCount.parentNode.insertBefore(errorEl, charCount.nextSibling);
        } else {
            textarea.parentNode.insertBefore(errorEl, textarea.nextSibling);
        }
    }

    // Set error message with icon
    errorEl.innerHTML = '<svg class="h-4 w-4 mr-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
        '</svg>' +
        '<span>' + escapeHtml(message) + '</span>';

    // Remove error after delay
    setTimeout(function() {
        clearTextareaError(textarea);
    }, 4000);
}

/**
 * Clear error state from textarea
 * @param {HTMLTextAreaElement} textarea - The textarea element
 */
function clearTextareaError(textarea) {
    if (!textarea) return;

    textarea.classList.remove('textarea-enhanced-error');

    var errorEl = textarea.parentNode.querySelector('.textarea-error-message');
    if (errorEl) {
        errorEl.classList.add('animate-fade-out');
        setTimeout(function() {
            if (errorEl.parentNode) {
                errorEl.parentNode.removeChild(errorEl);
            }
        }, 200);
    }
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
        // Fetch both active runs AND planning workflows
        const [runsResponse, planningResponse] = await Promise.all([
            fetch('/api/runs?status=running,pending&limit=10'),
            fetch('/api/plans?status=planning&limit=10').catch(() => null)
        ]);

        if (!runsResponse.ok) {
            throw new Error('Failed to fetch runs');
        }

        const runsData = await runsResponse.json();
        var runs = runsData.runs || [];

        // Add planning workflows to the display
        if (planningResponse && planningResponse.ok) {
            const planningData = await planningResponse.json();
            const planningWorkflows = (planningData.plans || []).map(function(plan) {
                return {
                    id: 'planning-' + plan.id,
                    plan_id: plan.id,
                    workflow: 'planning',
                    status: 'planning',
                    progress: 0,
                    current_step: 'AI is analyzing your request...',
                    started_at: plan.created_at || new Date().toISOString(),
                    is_planning: true,
                    plan_name: plan.name || plan.description || 'New Plan'
                };
            });

            // Update tracking map
            taskActivityState.planningWorkflows.clear();
            planningWorkflows.forEach(function(pw) {
                taskActivityState.planningWorkflows.set(pw.plan_id, pw);
            });

            // Prepend planning workflows to runs
            runs = planningWorkflows.concat(runs);
        }

        updateLiveBuildsUI(runs);

        // Also sync with TaskActivityPanel if available
        syncWithTaskActivityPanel(runs);

        return { runs: runs };
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
    const isPlanning = run.status === 'planning' || run.is_planning;
    const isBuilding = run.status === 'running' || run.status === 'building';

    // Apply appropriate classes based on status
    var cardClasses = 'border rounded-lg p-4 live-build-card transition-all duration-300';
    if (isPlanning) {
        cardClasses += ' border-gray-300 bg-gray-50 dark:bg-gray-800/50 opacity-75 pointer-events-none';
    } else if (isBuilding) {
        cardClasses += ' border-violet-200 dark:border-violet-800 bg-violet-50/30 dark:bg-violet-900/10';
    } else {
        cardClasses += ' border-gray-200 dark:border-gray-700';
    }

    card.className = cardClasses;
    card.dataset.runId = run.id;
    card.dataset.runStatus = run.status;
    card.dataset.startedAt = run.started_at || new Date().toISOString();
    if (run.plan_id) {
        card.dataset.planId = run.plan_id;
    }

    const statusClasses = getStatusClasses(run.status);
    const progress = run.progress || 0;
    const currentStep = run.current_step || (isPlanning ? 'AI is analyzing your request...' : 'Initializing...');
    var workflow = run.workflow ? run.workflow.charAt(0).toUpperCase() + run.workflow.slice(1) : 'Build';

    // Use plan name for planning workflows
    if (isPlanning && run.plan_name) {
        workflow = run.plan_name.length > 30 ? run.plan_name.substring(0, 30) + '...' : run.plan_name;
    }

    // Build progress bar color based on status
    var progressBarClass = 'bg-blue-600';
    if (isPlanning) {
        progressBarClass = 'bg-gray-400 animate-pulse';
    } else if (isBuilding) {
        progressBarClass = 'bg-violet-500';
    }

    // Determine link behavior (disabled for planning)
    var titleHtml;
    if (isPlanning) {
        titleHtml = '<span class="text-sm font-medium text-gray-500 dark:text-gray-400 cursor-not-allowed">' +
            escapeHtml(workflow) +
            '</span>';
    } else {
        titleHtml = '<a href="/runs/' + escapeHtml(run.id) + '" class="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">' +
            escapeHtml(workflow) +
            '</a>';
    }

    // Build status indicator icon for planning/building
    var statusIconHtml = '';
    if (isPlanning) {
        statusIconHtml = '<div class="flex items-center mr-2">' +
            '<svg class="animate-spin h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24">' +
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>' +
            '</svg>' +
            '</div>';
    } else if (isBuilding) {
        statusIconHtml = '<div class="flex items-center mr-2">' +
            '<svg class="animate-pulse h-4 w-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>' +
            '</svg>' +
            '</div>';
    }

    // Build expand button for log streaming (not for planning)
    var expandButtonHtml = '';
    if (!isPlanning) {
        expandButtonHtml = '<button type="button" class="expand-logs-btn ml-2 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" title="View live logs">' +
            '<svg class="h-4 w-4 text-gray-400 expand-icon transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>' +
            '</svg>' +
            '</button>';
    }

    card.innerHTML =
        '<div class="flex items-center justify-between mb-3">' +
            '<div class="flex items-center">' +
                statusIconHtml +
                titleHtml +
                '<span class="ml-2 text-xs text-gray-500 dark:text-gray-400">' + escapeHtml(run.id.substring(0, 8)) + '</span>' +
            '</div>' +
            '<div class="flex items-center space-x-3">' +
                '<span class="text-xs text-gray-500 dark:text-gray-400 elapsed-time" data-started="' + escapeHtml(run.started_at || '') + '">--:--</span>' +
                '<span class="status-badge inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + statusClasses + '">' +
                    '<span class="status-dot status-dot-' + escapeHtml(run.status) + ' mr-1.5"></span>' +
                    escapeHtml(run.status) +
                '</span>' +
                expandButtonHtml +
            '</div>' +
        '</div>' +
        '<div class="mb-2">' +
            '<div class="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">' +
                '<span class="current-step">' + escapeHtml(currentStep) + '</span>' +
                '<span class="progress-percent">' + progress + '%</span>' +
            '</div>' +
            '<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">' +
                '<div class="progress-bar ' + progressBarClass + ' h-2.5 rounded-full transition-all duration-300" style="width: ' + progress + '%"></div>' +
            '</div>' +
        '</div>' +
        '<div class="step-details mt-2 text-xs text-gray-500 dark:text-gray-400">' +
            (run.total_steps ? '<span>Step ' + (run.current_step_num || 0) + ' of ' + run.total_steps + '</span>' : '') +
        '</div>' +
        // Hidden log container that expands
        '<div class="log-container hidden mt-3 max-h-48 overflow-y-auto bg-gray-900 rounded-lg p-3 font-mono text-xs text-gray-300">' +
            '<div class="log-content"></div>' +
        '</div>';

    // Attach expand button handler for non-planning cards
    if (!isPlanning) {
        var expandBtn = card.querySelector('.expand-logs-btn');
        if (expandBtn) {
            expandBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleLogContainer(card, run.id);
            });
        }
    }

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

/**
 * Get unified status badge class for a given status
 * Uses CSS classes from status-theme.css for consistent theming
 */
function getStatusClasses(status) {
    const classMap = {
        completed: 'status-badge-completed',
        running: 'status-badge-running',
        pending: 'status-badge-pending',
        failed: 'status-badge-failed',
        error: 'status-badge-failed',
        building: 'status-badge-building',
        paused: 'status-badge-paused',
        stuck: 'status-badge-stuck',
        in_progress: 'status-badge-in-progress',
        planning: 'status-badge-planning'
    };
    return classMap[status] || 'status-badge-paused';
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

/**
 * Toggle log container visibility and connect/disconnect SSE
 * @param {HTMLElement} card - The build card element
 * @param {string} runId - The run ID
 */
function toggleLogContainer(card, runId) {
    var logContainer = card.querySelector('.log-container');
    var expandIcon = card.querySelector('.expand-icon');

    if (!logContainer) return;

    var isExpanded = !logContainer.classList.contains('hidden');

    if (isExpanded) {
        // Collapse
        logContainer.classList.add('hidden');
        if (expandIcon) expandIcon.style.transform = 'rotate(0deg)';

        // Disconnect SSE
        disconnectLogSSE(runId);
    } else {
        // Expand
        logContainer.classList.remove('hidden');
        if (expandIcon) expandIcon.style.transform = 'rotate(180deg)';

        // Connect SSE for log streaming
        connectLogSSE(runId, card);
    }
}

/**
 * Connect SSE for live log streaming
 * @param {string} runId - The run ID
 * @param {HTMLElement} card - The build card element
 */
function connectLogSSE(runId, card) {
    // Close existing connection if any
    disconnectLogSSE(runId);

    var logContent = card.querySelector('.log-content');
    if (!logContent) return;

    // Add loading indicator
    logContent.innerHTML = '<div class="text-gray-500 animate-pulse">Connecting to log stream...</div>';

    try {
        var es = new EventSource('/api/runs/' + runId + '/events');

        es.onopen = function() {
            logContent.innerHTML = '<div class="text-green-400">Connected to live logs</div>';
        };

        es.onmessage = function(e) {
            try {
                var event = JSON.parse(e.data);
                appendLogEntry(logContent, event);
            } catch (err) {
                console.debug('Log SSE parse error:', err);
            }
        };

        es.addEventListener('log', function(e) {
            try {
                var data = JSON.parse(e.data);
                appendLogEntry(logContent, data);
            } catch (err) {
                console.debug('Log event parse error:', err);
            }
        });

        es.addEventListener('progress', function(e) {
            try {
                var data = JSON.parse(e.data);
                if (data.message || data.step) {
                    appendLogEntry(logContent, {
                        type: 'progress',
                        message: data.message || data.step,
                        timestamp: new Date().toISOString()
                    });
                }
            } catch (err) {
                console.debug('Progress event parse error:', err);
            }
        });

        es.onerror = function() {
            appendLogEntry(logContent, {
                type: 'error',
                message: 'Log stream disconnected',
                timestamp: new Date().toISOString()
            });
            es.close();
            delete taskActivityState.logEventSources[runId];
        };

        taskActivityState.logEventSources[runId] = es;
    } catch (error) {
        console.error('Failed to connect log SSE:', error);
        logContent.innerHTML = '<div class="text-red-400">Failed to connect to log stream</div>';
    }
}

/**
 * Disconnect SSE for log streaming
 * @param {string} runId - The run ID
 */
function disconnectLogSSE(runId) {
    if (taskActivityState.logEventSources[runId]) {
        taskActivityState.logEventSources[runId].close();
        delete taskActivityState.logEventSources[runId];
    }
}

/**
 * Append a log entry to the log container
 * @param {HTMLElement} logContent - The log content element
 * @param {Object} event - The log event
 */
function appendLogEntry(logContent, event) {
    if (!logContent || !event) return;

    var message = event.message || event.log || event.step || event.data || '';
    if (!message && typeof event === 'string') {
        message = event;
    }
    if (!message) return;

    var timestamp = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    var level = event.level || event.type || 'info';

    // Color based on level
    var colorClass = 'text-gray-300';
    if (level === 'error' || level === 'failed') {
        colorClass = 'text-red-400';
    } else if (level === 'warning' || level === 'warn') {
        colorClass = 'text-yellow-400';
    } else if (level === 'success' || level === 'completed' || level === 'done') {
        colorClass = 'text-green-400';
    } else if (level === 'progress' || level === 'step') {
        colorClass = 'text-blue-400';
    }

    var logLine = document.createElement('div');
    logLine.className = 'log-line ' + colorClass + ' whitespace-pre-wrap break-all';
    logLine.textContent = '[' + timestamp + '] ' + message;

    // Remove loading message if it's the first real log
    var loadingMsg = logContent.querySelector('.animate-pulse');
    if (loadingMsg) {
        loadingMsg.remove();
    }

    logContent.appendChild(logLine);

    // Auto-scroll to bottom
    var logContainer = logContent.closest('.log-container');
    if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Trim old entries (keep last 200 lines)
    var lines = logContent.querySelectorAll('.log-line');
    if (lines.length > 200) {
        for (var i = 0; i < lines.length - 200; i++) {
            lines[i].remove();
        }
    }
}

/**
 * Sync runs with TaskActivityPanel if available
 * @param {Array} runs - Array of run objects
 */
function syncWithTaskActivityPanel(runs) {
    if (typeof TaskActivityPanel === 'undefined') return;

    // Initialize panel if not done
    if (!taskActivityState.initialized) {
        var panelContainer = document.getElementById('task-activity-panel');
        if (panelContainer) {
            TaskActivityPanel.init('task-activity-panel');
            taskActivityState.initialized = true;
        }
    }

    // Sync each run to TaskActivityPanel
    runs.forEach(function(run) {
        var taskData = {
            id: run.id,
            name: run.plan_name || run.workflow || 'Task',
            status: mapStatusToTaskStatus(run.status),
            phase: mapStatusToPhase(run.status),
            progress: run.progress || 0,
            currentStep: run.current_step || '',
            startedAt: run.started_at,
            planId: run.plan_id,
            totalSteps: run.total_steps || 0,
            currentStepNum: run.current_step_num || 0
        };

        if (TaskActivityPanel.getTasks) {
            var existingTasks = TaskActivityPanel.getTasks();
            var exists = existingTasks.some(function(t) { return t.id === run.id; });

            if (exists) {
                TaskActivityPanel.updateTask(run.id, taskData);
            } else {
                TaskActivityPanel.addTask(taskData);
            }
        }
    });
}

/**
 * Map run status to TaskActivityPanel status
 * @param {string} status - Run status
 * @returns {string} TaskActivityPanel status
 */
function mapStatusToTaskStatus(status) {
    var statusMap = {
        planning: 'planning',
        pending: 'pending',
        running: 'running',
        building: 'running',
        completed: 'completed',
        failed: 'failed',
        error: 'failed'
    };
    return statusMap[status] || 'pending';
}

/**
 * Map run status to task phase
 * @param {string} status - Run status
 * @returns {string} Task phase
 */
function mapStatusToPhase(status) {
    var phaseMap = {
        planning: 'planning',
        pending: 'initializing',
        running: 'executing',
        building: 'executing',
        completed: 'completed',
        failed: 'failed'
    };
    return phaseMap[status] || 'initializing';
}

/**
 * Initialize TaskActivityPanel integration
 */
function initTaskActivityPanel() {
    if (typeof TaskActivityPanel === 'undefined') return;

    var panelContainer = document.getElementById('task-activity-panel');
    if (!panelContainer) {
        // Create container if it doesn't exist
        var liveBuildsSection = document.getElementById('live-builds-section');
        if (liveBuildsSection) {
            panelContainer = document.createElement('div');
            panelContainer.id = 'task-activity-panel';
            panelContainer.className = 'mt-6';
            liveBuildsSection.parentNode.insertBefore(panelContainer, liveBuildsSection.nextSibling);
        }
    }

    if (panelContainer) {
        TaskActivityPanel.init('task-activity-panel');
        taskActivityState.initialized = true;
    }
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

    // Cleanup log SSE connections
    Object.keys(taskActivityState.logEventSources).forEach(function(runId) {
        taskActivityState.logEventSources[runId].close();
    });
    taskActivityState.logEventSources = {};

    // Cleanup TaskActivityPanel
    if (typeof TaskActivityPanel !== 'undefined' && TaskActivityPanel.cleanup) {
        TaskActivityPanel.cleanup();
    }
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
    // Use unified status badge classes from status-theme.css
    var statusBadgeClass = plan.status === 'building'
        ? 'status-badge-building'
        : 'status-badge-stuck';

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
    initDashboard();
    initSyncRemote();
    initSyncFileListToggle();
    initLiveBuilds();
    initStuckPlans();
    initTaskActivityPanel();
    fetchSyncStatus();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    cleanupLiveBuilds();
    cleanupStuckPlans();
});
