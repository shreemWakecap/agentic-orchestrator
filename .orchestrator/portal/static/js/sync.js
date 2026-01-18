/**
 * Sync page functionality
 * Handles remote sync operations, branch management, and PR management
 */

/**
 * Initialize sync remote functionality
 * Sets up event listeners for sync button, refresh, and pull latest
 */
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
 * Fetch and display git sync status information
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

/**
 * Toggle visibility of the sync file list
 */
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

/**
 * Initialize sync file list toggle button
 */
function initSyncFileListToggle() {
    const toggleBtn = document.getElementById('sync-file-list-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleSyncFileList);
    }
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

/**
 * Update the branch list UI
 * @param {Array} branches - Array of branch objects
 */
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

/**
 * Update the PR list UI
 * @param {Array} prs - Array of PR objects
 */
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

/**
 * Delete a branch
 * @param {string} branchName - Name of the branch to delete
 */
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

/**
 * Merge a PR
 * @param {number} prNumber - PR number to merge
 */
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
 * Escape HTML special characters
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
 * Initialize sync page
 */
function initSyncPage() {
    initSyncRemote();
    initSyncFileListToggle();
    fetchSyncStatus();
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initSyncPage();
});
