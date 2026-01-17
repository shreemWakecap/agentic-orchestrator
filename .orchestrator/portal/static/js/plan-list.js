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

    // Public API
    return {
        togglePlan: togglePlan,
        openFile: openFile,
        expandAll: expandAll,
        collapseAll: collapseAll,
        isExpanded: isExpanded,
        getExpandedPlans: getExpandedPlans,
        reset: reset
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
