/**
 * Plans Page Action Handlers Module
 *
 * Provides action handlers for plans list page:
 * - Build start/retry functionality
 * - Plan deletion with animation
 * - Keyboard shortcuts initialization
 *
 * Note: Plan form is now handled by the unified PlanForm component
 * (see components/plan-form.js)
 *
 * Dependencies:
 * - PlanManager (plan-manager.js) - for plan operations
 * - Toast (toast.js) - for notifications
 *
 * @module PlansFormHandlers
 */

const PlansFormHandlers = (function() {
    'use strict';

    // =========================================================================
    // State
    // =========================================================================

    let isInitialized = false;

    // =========================================================================
    // Plan Actions
    // =========================================================================

    /**
     * Start a build for a plan
     * @param {string} planId - Plan identifier
     * @param {Event} event - Click event
     */
    async function startBuild(planId, event) {
        var button = event ? event.target.closest('button') : null;

        if (typeof PlanManager === 'undefined') {
            showToast('PlanManager not available', 'error');
            return;
        }

        var result = await PlanManager.startBuild(planId, button);

        // If build started successfully and result has run_id, redirect
        if (result && result.run_id) {
            showToast('Redirecting to build run...', 'info');
            setTimeout(function() {
                window.location.href = '/runs/' + result.run_id;
            }, 1000);
        }
    }

    /**
     * Retry a failed build
     * @param {string} planId - Plan identifier
     * @param {Event} event - Click event
     */
    async function retryBuild(planId, event) {
        var button = event ? event.target.closest('button') : null;

        if (typeof PlanManager === 'undefined') {
            showToast('PlanManager not available', 'error');
            return;
        }

        showToast('Preparing to retry build...', 'info');

        // First move the plan back to pending state
        var moveResult = await PlanManager.movePlan(planId, 'pending', button);

        if (!moveResult) {
            return; // movePlan shows its own error notification
        }

        // Now start the build
        var buildResult = await PlanManager.startBuild(planId, button);

        // If build started successfully and result has run_id, redirect
        if (buildResult && buildResult.run_id) {
            showToast('Retry build started! Redirecting...', 'success');
            setTimeout(function() {
                window.location.href = '/runs/' + buildResult.run_id;
            }, 1000);
        }
    }

    /**
     * Delete a plan with confirmation
     * @param {string} planId - Plan identifier
     * @param {Event} event - Click event
     */
    async function deletePlan(planId, event) {
        var button = event ? event.target.closest('button') : null;

        if (typeof PlanManager === 'undefined') {
            showToast('PlanManager not available', 'error');
            return;
        }

        var deleted = await PlanManager.deletePlan(planId, button);

        if (deleted) {
            // Remove the plan item from the DOM with fade-out animation
            var planItem = document.querySelector('[data-plan-id="' + planId + '"]');
            if (planItem) {
                // Disable pointer events during animation
                planItem.style.pointerEvents = 'none';

                // Apply fade-out animation with scale and slide effect
                planItem.style.cssText = planItem.style.cssText +
                    ';opacity: 0 !important' +
                    ';transform: translateY(-20px) scale(0.95) !important' +
                    ';transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important' +
                    ';pointer-events: none !important';

                // Remove from DOM after animation completes
                setTimeout(function() {
                    if (planItem && planItem.parentNode) {
                        planItem.remove();
                        updatePlanCount();
                    }
                }, 400);
            } else {
                updatePlanCount();
            }
        }
    }

    // =========================================================================
    // UI Helpers
    // =========================================================================

    /**
     * Update the plan count display after deletion
     */
    function updatePlanCount() {
        var plansList = document.getElementById('plans-list');
        var planItems = plansList ? plansList.querySelectorAll('.plan-item') : [];
        var countEl = document.querySelector('.text-sm.text-gray-500');

        if (countEl) {
            countEl.textContent = 'All implementation plans (' + planItems.length + ' total)';
        }

        // If no plans left, show empty state
        if (planItems.length === 0) {
            location.reload();
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type
     */
    function showToast(message, type) {
        if (typeof Toast !== 'undefined') {
            Toast.show(message, type);
        } else {
            console.log('[' + type.toUpperCase() + ']', message);
        }
    }

    // =========================================================================
    // Keyboard Shortcuts
    // =========================================================================

    /**
     * Initialize keyboard shortcuts for the plans page
     */
    function initKeyboardShortcuts() {
        if (typeof PlanManager !== 'undefined' && PlanManager.initKeyboardShortcuts) {
            PlanManager.initKeyboardShortcuts();
        }
    }

    /**
     * Re-bind click handlers after list refresh
     */
    function rebindAfterRefresh() {
        document.querySelectorAll('.plan-item[data-plan-id]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                if (!e.target.closest('button') && !e.target.closest('a')) {
                    if (typeof PlanManager !== 'undefined') {
                        PlanManager.selectPlan(item.dataset.planId);
                    }
                }
            });
        });

        // Re-initialize stuck detection after refresh
        if (typeof StuckDetection !== 'undefined') {
            StuckDetection.init();
        } else if (typeof initStuckDetection === 'function') {
            initStuckDetection();
        }
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize action handlers
     */
    function init() {
        if (isInitialized) return;

        // Note: Plan form is now auto-initialized by PlanForm module (components/plan-form.js)
        initKeyboardShortcuts();

        // Listen for list refresh events
        document.addEventListener('orchestrator:planManager:listRefreshed', rebindAfterRefresh);

        isInitialized = true;
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        initKeyboardShortcuts: initKeyboardShortcuts,
        startBuild: startBuild,
        retryBuild: retryBuild,
        deletePlan: deletePlan,
        updatePlanCount: updatePlanCount
    };
})();

// Expose globally
window.PlansFormHandlers = PlansFormHandlers;

// Expose action functions globally for onclick handlers in HTML
window.startBuild = function(planId, event) {
    return PlansFormHandlers.startBuild(planId, event);
};

window.retryBuild = function(planId, event) {
    return PlansFormHandlers.retryBuild(planId, event);
};

window.deletePlan = function(planId, event) {
    return PlansFormHandlers.deletePlan(planId, event);
};

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlansFormHandlers;
}
