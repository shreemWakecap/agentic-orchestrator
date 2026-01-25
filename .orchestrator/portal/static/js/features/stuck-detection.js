/**
 * Stuck Plan Detection Module
 *
 * Handles detection of stuck plans and provides inline recovery actions.
 * Works with plan list views to show stuck badges and recovery buttons.
 *
 * Features:
 * - Automatic detection of plans that haven't updated in 5+ minutes
 * - Warning state for plans approaching stuck threshold (2+ minutes)
 * - Elapsed time display updates
 * - Inline recovery actions (resume/restart)
 * - Real-time updates every second
 *
 * Dependencies:
 * - CoreUtils (core/utils.js) - for formatElapsedTime
 * - Toast (toast.js) - for notifications
 * - PlanManager (plan-manager.js) - for recovery actions
 *
 * DOM Requirements:
 * - .plan-item elements with data-plan-id, data-plan-state, data-updated
 * - .elapsed-time-item elements with data-updated
 * - #stuck-badge-{planId} for stuck badges
 * - #recovery-actions-{planId} for recovery action buttons
 *
 * @module StuckDetection
 */

const StuckDetection = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        stuckThresholdMs: 5 * 60 * 1000,    // 5 minutes = stuck
        warningThresholdMs: 2 * 60 * 1000,   // 2 minutes = warning
        updateIntervalMs: 1000               // Update every second
    };

    // =========================================================================
    // State
    // =========================================================================

    let updateInterval = null;
    let isInitialized = false;

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize stuck detection for all plans
     */
    function init() {
        // Clear existing interval
        if (updateInterval) {
            clearInterval(updateInterval);
        }

        // Run immediately
        updateAllElapsedTimes();
        checkAllStuckPlans();

        // Then update every second
        updateInterval = setInterval(function() {
            updateAllElapsedTimes();
            checkAllStuckPlans();
        }, CONFIG.updateIntervalMs);

        isInitialized = true;
    }

    // =========================================================================
    // Time Formatting
    // =========================================================================

    /**
     * Format elapsed time in human-readable format
     * Uses CoreUtils if available, otherwise uses local implementation
     *
     * @param {number} ms - Elapsed time in milliseconds
     * @returns {string} Formatted time string
     */
    function formatElapsedTime(ms) {
        // Use CoreUtils if available
        if (typeof CoreUtils !== 'undefined' && CoreUtils.formatElapsedTime) {
            return CoreUtils.formatElapsedTime(ms);
        }

        // Local implementation as fallback
        var seconds = Math.floor(ms / 1000);
        var minutes = Math.floor(seconds / 60);
        var hours = Math.floor(minutes / 60);
        var days = Math.floor(hours / 24);

        if (days > 0) {
            return days + 'd ' + (hours % 24) + 'h';
        } else if (hours > 0) {
            return hours + 'h ' + (minutes % 60) + 'm';
        } else if (minutes > 0) {
            return minutes + 'm ' + (seconds % 60) + 's';
        } else {
            return seconds + 's';
        }
    }

    // =========================================================================
    // Elapsed Time Updates
    // =========================================================================

    /**
     * Update all elapsed time displays
     */
    function updateAllElapsedTimes() {
        document.querySelectorAll('.elapsed-time-item').forEach(function(el) {
            var updated = el.dataset.updated;
            if (!updated) return;

            var elapsed = Date.now() - new Date(updated).getTime();
            var text = formatElapsedTime(elapsed);
            var textEl = el.querySelector('.elapsed-text');
            if (textEl) {
                textEl.textContent = text + ' ago';
            }

            // Add warning class if elapsed time is high
            if (elapsed > CONFIG.stuckThresholdMs) {
                el.classList.add('text-red-500');
                el.classList.remove('text-yellow-600');
            } else if (elapsed > CONFIG.warningThresholdMs) {
                el.classList.add('text-yellow-600');
                el.classList.remove('text-red-500');
            } else {
                el.classList.remove(
                    'text-red-500',
                    'text-yellow-600'
                );
            }
        });
    }

    // =========================================================================
    // Stuck Plan Detection
    // =========================================================================

    /**
     * Check all potentially stuck plans and show/hide badges
     */
    function checkAllStuckPlans() {
        document.querySelectorAll('.plan-item[data-plan-state]').forEach(function(card) {
            var state = card.dataset.planState;
            var updated = card.dataset.updated || card.dataset.created;
            var planId = card.dataset.planId;

            // Only check in-progress/building/failed plans
            if (!['in-progress', 'building', 'failed'].includes(state)) {
                return;
            }

            var elapsed = updated ? Date.now() - new Date(updated).getTime() : 0;
            var isStuck = elapsed > CONFIG.stuckThresholdMs;
            var isFailed = state === 'failed';

            // Show/hide stuck badge
            var stuckBadge = document.getElementById('stuck-badge-' + planId);
            if (stuckBadge) {
                if (isStuck && !isFailed) {
                    stuckBadge.classList.remove('hidden');
                    card.classList.add('stuck');
                } else {
                    stuckBadge.classList.add('hidden');
                    card.classList.remove('stuck');
                }
            }

            // Show/hide recovery actions
            var recoveryActions = document.getElementById('recovery-actions-' + planId);
            if (recoveryActions) {
                if (isStuck || isFailed) {
                    recoveryActions.classList.remove('hidden');
                } else {
                    recoveryActions.classList.add('hidden');
                }
            }
        });
    }

    /**
     * Check if a specific plan is stuck
     * @param {string} planId - Plan identifier
     * @returns {boolean} True if plan is stuck
     */
    function isPlanStuck(planId) {
        var card = document.querySelector('.plan-item[data-plan-id="' + planId + '"]');
        if (!card) return false;

        var state = card.dataset.planState;
        if (!['in-progress', 'building'].includes(state)) return false;

        var updated = card.dataset.updated || card.dataset.created;
        if (!updated) return false;

        var elapsed = Date.now() - new Date(updated).getTime();
        return elapsed > CONFIG.stuckThresholdMs;
    }

    // =========================================================================
    // Recovery Actions
    // =========================================================================

    /**
     * Resume a plan from the list view
     * @param {string} planId - Plan identifier
     * @param {Event} event - Click event
     */
    async function resumePlanFromList(planId, event) {
        var button = event ? event.target.closest('button') : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<svg class="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Resuming...';
        }

        try {
            showToast('Resuming plan...', 'info');

            var response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resume: true })
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to resume plan');
            }

            showToast('Plan resumed! Redirecting...', 'success');

            if (data.run_id) {
                setTimeout(function() {
                    window.location.href = '/runs/' + data.run_id;
                }, 1000);
            } else {
                window.location.reload();
            }
        } catch (error) {
            console.error('Error resuming plan:', error);
            showToast('Failed to resume: ' + error.message, 'error');
            if (button) {
                button.disabled = false;
                button.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> Resume';
            }
        }
    }

    /**
     * Restart a plan from the list view
     * @param {string} planId - Plan identifier
     * @param {Event} event - Click event
     */
    async function restartPlanFromList(planId, event) {
        var confirmed = confirm(
            'Are you sure you want to restart this plan from the beginning?\n\n' +
            'This will:\n' +
            '- Reset all step progress\n' +
            '- Clear any partial outputs\n' +
            '- Start the build from step 1\n\n' +
            'This action cannot be undone.'
        );

        if (!confirmed) return;

        var button = event ? event.target.closest('button') : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<svg class="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> Restarting...';
        }

        try {
            showToast('Restarting plan from beginning...', 'info');

            // First move plan back to pending state
            if (typeof PlanManager !== 'undefined') {
                var moveResult = await PlanManager.movePlan(planId, 'pending', button);
                if (!moveResult) {
                    throw new Error('Failed to reset plan state');
                }
            }

            // Then start fresh build
            var response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ restart: true, from_step: null })
            });

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to restart plan');
            }

            showToast('Plan restarted! Redirecting...', 'success');

            if (data.run_id) {
                setTimeout(function() {
                    window.location.href = '/runs/' + data.run_id;
                }, 1000);
            } else {
                window.location.reload();
            }
        } catch (error) {
            console.error('Error restarting plan:', error);
            showToast('Failed to restart: ' + error.message, 'error');
            if (button) {
                button.disabled = false;
                button.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Restart';
            }
        }
    }

    // =========================================================================
    // Toast Helper
    // =========================================================================

    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (info, success, error, warning)
     */
    function showToast(message, type) {
        if (typeof Toast !== 'undefined') {
            Toast.show(message, type);
        } else {
            console.log('[' + type.toUpperCase() + ']', message);
        }
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    /**
     * Stop stuck detection and clean up resources
     */
    function destroy() {
        if (updateInterval) {
            clearInterval(updateInterval);
            updateInterval = null;
        }
        isInitialized = false;
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM already loaded
        init();
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        destroy: destroy,
        checkAllStuckPlans: checkAllStuckPlans,
        updateAllElapsedTimes: updateAllElapsedTimes,
        isPlanStuck: isPlanStuck,
        resumePlanFromList: resumePlanFromList,
        restartPlanFromList: restartPlanFromList,
        CONFIG: CONFIG
    };
})();

// Expose globally
window.StuckDetection = StuckDetection;

// Expose functions globally for onclick handlers in HTML
window.initStuckDetection = function() {
    return StuckDetection.init();
};

window.resumePlanFromList = function(planId, event) {
    return StuckDetection.resumePlanFromList(planId, event);
};

window.restartPlanFromList = function(planId, event) {
    return StuckDetection.restartPlanFromList(planId, event);
};

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StuckDetection;
}
