/**
 * Plan List Module
 *
 * Handles plan list interactions including:
 * - Expand/collapse plan items to show files
 * - Open files in side popup
 * - Batch expand/collapse all plans
 *
 * Dependencies:
 * - SidePopup (from side-popup.js) for file viewing
 *
 * DOM Requirements:
 * - .plan-item elements with data-plan-id attributes
 * - #files-{planId} containers for expandable content
 * - #expand-icon-{planId} icons for expand indicators
 */

const PlanList = (function() {
    'use strict';

    // Track which plans are currently expanded
    const expandedPlans = new Set();

    /**
     * Toggle expand/collapse state of a plan
     * @param {string} planId - The plan identifier
     */
    function togglePlan(planId) {
        const filesEl = document.getElementById('files-' + planId);
        const iconEl = document.getElementById('expand-icon-' + planId);

        if (!filesEl || !iconEl) {
            console.warn('Plan elements not found for:', planId);
            return;
        }

        if (expandedPlans.has(planId)) {
            // Collapse
            filesEl.classList.remove('expanded');
            iconEl.classList.remove('rotated');
            expandedPlans.delete(planId);
        } else {
            // Expand
            filesEl.classList.add('expanded');
            iconEl.classList.add('rotated');
            expandedPlans.add(planId);
        }
    }

    /**
     * Open a file in the side popup
     * @param {string} planId - The plan identifier
     * @param {string} filename - The file to open
     */
    function openFile(planId, filename) {
        if (typeof SidePopup === 'undefined') {
            console.error('SidePopup is not loaded');
            alert('Unable to open file viewer');
            return;
        }

        const url = '/api/plans/' + encodeURIComponent(planId) + '/files/' + encodeURIComponent(filename);
        SidePopup.loadUrl(filename, url, {
            contentClass: 'side-popup-content markdown-content'
        });
    }

    /**
     * Expand all plans in the list
     */
    function expandAll() {
        const planItems = document.querySelectorAll('.plan-item');
        planItems.forEach(function(item) {
            const planId = item.dataset.planId;
            if (planId && !expandedPlans.has(planId)) {
                togglePlan(planId);
            }
        });
    }

    /**
     * Collapse all plans in the list
     */
    function collapseAll() {
        const planItems = document.querySelectorAll('.plan-item');
        planItems.forEach(function(item) {
            const planId = item.dataset.planId;
            if (planId && expandedPlans.has(planId)) {
                togglePlan(planId);
            }
        });
    }

    /**
     * Check if a plan is expanded
     * @param {string} planId - The plan identifier
     * @returns {boolean} True if expanded
     */
    function isExpanded(planId) {
        return expandedPlans.has(planId);
    }

    /**
     * Get all currently expanded plan IDs
     * @returns {string[]} Array of expanded plan IDs
     */
    function getExpandedPlans() {
        return Array.from(expandedPlans);
    }

    /**
     * Reset all expanded state
     */
    function reset() {
        expandedPlans.clear();
    }

    // Status polling for building plans
    let statusPollInterval = null;
    const STATUS_POLL_INTERVAL_MS = 15000; // Poll every 15 seconds

    /**
     * Start polling for status updates when there are building plans
     * This ensures the UI updates when builds complete
     */
    function startStatusPolling() {
        // Check if there are any building plans on the page
        const buildingPlans = document.querySelectorAll('[data-plan-state="building"], [data-plan-state="in-progress"]');
        if (buildingPlans.length === 0) {
            return; // No building plans, no need to poll
        }

        // Clear any existing interval
        stopStatusPolling();

        statusPollInterval = setInterval(async function() {
            try {
                const response = await fetch('/api/plans');
                if (!response.ok) return;

                const data = await response.json();

                // Check if any building plan completed
                let shouldRefresh = false;
                document.querySelectorAll('.plan-item[data-plan-id]').forEach(function(item) {
                    const planId = item.dataset.planId;
                    const currentState = item.dataset.planState;

                    if (currentState === 'building' || currentState === 'in-progress') {
                        // Find this plan in the response
                        const planData = data.plans ? data.plans.find(function(p) { return p.id === planId; }) : null;
                        if (planData && (planData.state === 'completed' || planData.state === 'failed')) {
                            shouldRefresh = true;
                        }
                    }
                });

                if (shouldRefresh) {
                    stopStatusPolling();
                    if (typeof Toast !== 'undefined') {
                        Toast.success('Build status updated! Refreshing...');
                    }
                    setTimeout(function() {
                        window.location.reload();
                    }, 1000);
                }
            } catch (error) {
                console.error('Status poll error:', error);
            }
        }, STATUS_POLL_INTERVAL_MS);
    }

    /**
     * Stop status polling
     */
    function stopStatusPolling() {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
        }
    }

    /**
     * Initialize the module (call on page load)
     */
    function init() {
        // Start polling if there are building plans
        startStatusPolling();
    }

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        togglePlan: togglePlan,
        openFile: openFile,
        expandAll: expandAll,
        collapseAll: collapseAll,
        isExpanded: isExpanded,
        getExpandedPlans: getExpandedPlans,
        reset: reset,
        startStatusPolling: startStatusPolling,
        stopStatusPolling: stopStatusPolling
    };
})();

// Expose functions globally for onclick handlers in templates
window.togglePlan = PlanList.togglePlan;
window.openFile = PlanList.openFile;
window.expandAll = PlanList.expandAll;
window.collapseAll = PlanList.collapseAll;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanList;
}
