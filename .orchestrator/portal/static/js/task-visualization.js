/**
 * Task Visualization Module
 *
 * Handles visualization of Claude Task tool integration:
 * - Fetches task graph data from API
 * - Renders task nodes with status
 * - Shows dependency relationships
 * - Displays wave-based execution progress
 * - Supports real-time updates via polling
 */

const TaskVisualization = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        pollInterval: 5000,  // 5 seconds between updates
        apiBase: '/api/plans',
    };

    // State
    let currentPlanId = null;
    let pollIntervalId = null;
    let taskData = null;

    // Status icons SVG
    const STATUS_ICONS = {
        pending: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`,
        in_progress: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>`,
        completed: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`,
        failed: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>`,
        blocked: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
        </svg>`,
    };

    /**
     * Initialize task visualization for a plan
     * @param {string} planId - Plan ID to visualize
     * @param {Object} options - Configuration options
     */
    function init(planId, options = {}) {
        currentPlanId = planId;

        if (options.pollInterval) {
            CONFIG.pollInterval = options.pollInterval;
        }

        // Initial fetch
        fetchAndRender();

        // Start polling if enabled
        if (options.enablePolling !== false) {
            startPolling();
        }

        console.log('[TaskVisualization] Initialized for plan:', planId);
    }

    /**
     * Fetch task data from API and render
     */
    async function fetchAndRender() {
        if (!currentPlanId) return;

        try {
            const [statusResponse, graphResponse] = await Promise.all([
                fetch(`${CONFIG.apiBase}/${currentPlanId}/task-status`),
                fetch(`${CONFIG.apiBase}/${currentPlanId}/task-graph`)
            ]);

            if (!statusResponse.ok || !graphResponse.ok) {
                throw new Error('Failed to fetch task data');
            }

            const statusData = await statusResponse.json();
            const graphData = await graphResponse.json();

            taskData = {
                status: statusData,
                graph: graphData
            };

            render(taskData);
        } catch (error) {
            console.error('[TaskVisualization] Error fetching data:', error);
            renderError(error.message);
        }
    }

    /**
     * Render task visualization
     * @param {Object} data - Combined status and graph data
     */
    function render(data) {
        const container = document.getElementById('task-visualization-container');
        if (!container) {
            console.warn('[TaskVisualization] Container not found');
            return;
        }

        const { status, graph } = data;

        // Check if we have any tasks
        if (!graph.nodes || graph.nodes.length === 0) {
            container.innerHTML = renderEmpty();
            return;
        }

        container.innerHTML = `
            <div class="task-graph-container">
                <div class="task-graph-header">
                    <div class="task-graph-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                        </svg>
                        <span>Task Dependencies</span>
                    </div>
                    ${renderStatusSummary(status.status_counts)}
                </div>
                ${renderWaves(graph)}
            </div>
        `;
    }

    /**
     * Render status summary pills
     * @param {Object} counts - Status counts object
     */
    function renderStatusSummary(counts) {
        if (!counts) return '';

        const pills = [];

        if (counts.completed > 0) {
            pills.push(`
                <span class="task-status-pill task-status-pill-completed">
                    ${STATUS_ICONS.completed}
                    <span class="task-status-count">${counts.completed}</span>
                    <span>completed</span>
                </span>
            `);
        }

        if (counts.in_progress > 0) {
            pills.push(`
                <span class="task-status-pill task-status-pill-in-progress">
                    ${STATUS_ICONS.in_progress}
                    <span class="task-status-count">${counts.in_progress}</span>
                    <span>in progress</span>
                </span>
            `);
        }

        if (counts.pending > 0) {
            pills.push(`
                <span class="task-status-pill task-status-pill-pending">
                    ${STATUS_ICONS.pending}
                    <span class="task-status-count">${counts.pending}</span>
                    <span>pending</span>
                </span>
            `);
        }

        if (counts.blocked > 0) {
            pills.push(`
                <span class="task-status-pill task-status-pill-blocked">
                    ${STATUS_ICONS.blocked}
                    <span class="task-status-count">${counts.blocked}</span>
                    <span>blocked</span>
                </span>
            `);
        }

        if (counts.failed > 0) {
            pills.push(`
                <span class="task-status-pill task-status-pill-failed">
                    ${STATUS_ICONS.failed}
                    <span class="task-status-count">${counts.failed}</span>
                    <span>failed</span>
                </span>
            `);
        }

        return `<div class="task-status-summary">${pills.join('')}</div>`;
    }

    /**
     * Render tasks grouped by waves
     * @param {Object} graph - Graph data with waves
     */
    function renderWaves(graph) {
        if (!graph.waves || graph.waves.length === 0) {
            return renderTaskList(graph.nodes);
        }

        // Create node lookup
        const nodeMap = {};
        graph.nodes.forEach(node => {
            nodeMap[node.id] = node;
        });

        const waveHtml = graph.waves.map((waveTaskIds, index) => {
            const waveTasks = waveTaskIds.map(taskId => nodeMap[taskId]).filter(Boolean);

            return `
                <div class="task-wave">
                    <div class="task-wave-header">
                        <span class="task-wave-badge">${index}</span>
                        <span>Wave ${index}${index === 0 ? ' (No Dependencies)' : ''}</span>
                    </div>
                    <div class="task-wave-tasks">
                        ${waveTasks.map(task => renderTaskNode(task)).join('')}
                    </div>
                </div>
            `;
        }).join('');

        return `<div class="task-waves-container">${waveHtml}</div>`;
    }

    /**
     * Render flat task list (fallback)
     * @param {Array} nodes - Task nodes
     */
    function renderTaskList(nodes) {
        const tasksHtml = nodes.map(task => renderTaskNode(task)).join('');
        return `<div class="task-grid">${tasksHtml}</div>`;
    }

    /**
     * Render a single task node
     * @param {Object} task - Task node data
     */
    function renderTaskNode(task) {
        const status = task.status || 'pending';
        const statusClass = status.replace('_', '-');
        const icon = STATUS_ICONS[status] || STATUS_ICONS.pending;

        return `
            <div class="task-node task-node-${statusClass}" data-task-id="${task.id}">
                <div class="task-node-icon task-node-icon-${statusClass}">
                    ${icon}
                </div>
                <div class="task-node-content">
                    <div class="task-node-subject" title="${escapeHtml(task.subject || task.id)}">${escapeHtml(task.subject || task.id)}</div>
                    <div class="task-node-id">${task.id}</div>
                    ${task.active_form && status === 'in_progress' ? `<div class="task-node-active-form">${escapeHtml(task.active_form)}</div>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Render loading state
     */
    function renderLoading() {
        return `
            <div class="task-graph-loading">
                <div class="task-graph-loading-spinner"></div>
                <div class="task-graph-loading-text">Loading task data...</div>
            </div>
        `;
    }

    /**
     * Render empty state
     */
    function renderEmpty() {
        return `
            <div class="task-graph-empty">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
                <div class="task-graph-empty-text">
                    No task data available.<br>
                    Tasks will appear here when the build starts.
                </div>
            </div>
        `;
    }

    /**
     * Render error state
     * @param {string} message - Error message
     */
    function renderError(message) {
        const container = document.getElementById('task-visualization-container');
        if (!container) return;

        container.innerHTML = `
            <div class="task-graph-empty">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" class="text-red-400">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                <div class="task-graph-empty-text">
                    Error loading task data.<br>
                    <span class="text-sm text-gray-400">${escapeHtml(message)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Start polling for updates
     */
    function startPolling() {
        if (pollIntervalId) {
            clearInterval(pollIntervalId);
        }

        pollIntervalId = setInterval(() => {
            fetchAndRender();
        }, CONFIG.pollInterval);
    }

    /**
     * Stop polling
     */
    function stopPolling() {
        if (pollIntervalId) {
            clearInterval(pollIntervalId);
            pollIntervalId = null;
        }
    }

    /**
     * Refresh visualization manually
     */
    function refresh() {
        fetchAndRender();
    }

    /**
     * Cleanup and destroy
     */
    function destroy() {
        stopPolling();
        currentPlanId = null;
        taskData = null;

        const container = document.getElementById('task-visualization-container');
        if (container) {
            container.innerHTML = '';
        }
    }

    /**
     * Get current task data
     */
    function getData() {
        return taskData;
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     */
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Public API
    return {
        init,
        refresh,
        startPolling,
        stopPolling,
        destroy,
        getData,
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskVisualization;
}
