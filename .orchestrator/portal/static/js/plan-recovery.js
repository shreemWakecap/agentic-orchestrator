/**
 * Plan Recovery Module
 *
 * Handles recovery options for stuck or failed plans including:
 * - Show recovery options UI with status indicator
 * - Resume plan from current step
 * - Restart plan from beginning
 * - Display elapsed time since last update
 * - Confirmation dialogs for destructive actions
 *
 * Dependencies:
 * - Toast (toast.js) - For notifications
 *
 * DOM Requirements:
 * - #recovery-options container for recovery UI
 * - Plan data available via window.PLAN_DATA
 */

const PlanRecovery = (function() {
    'use strict';

    // Configuration
    const STUCK_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes without update = stuck
    const UPDATE_INTERVAL_MS = 1000; // Update elapsed time every second

    // State
    let updateInterval = null;
    let lastUpdateTime = null;
    let currentPlanId = null;
    let resumeShortcutId = null;

    // DOM element cache
    const elements = {};

    /**
     * Cache DOM elements for performance
     */
    function cacheElements() {
        elements.recoverySection = document.getElementById('recovery-options');
        elements.recoveryStatus = document.getElementById('recovery-status');
        elements.recoveryIndicator = document.getElementById('recovery-indicator');
        elements.elapsedTime = document.getElementById('recovery-elapsed-time');
        elements.resumeBtn = document.getElementById('recovery-resume-btn');
        elements.restartBtn = document.getElementById('recovery-restart-btn');
        elements.lastStep = document.getElementById('recovery-last-step');
    }

    /**
     * Initialize the module
     * @param {string} planId - The plan identifier
     * @param {Object} options - Configuration options
     */
    function init(planId, options) {
        options = options || {};
        currentPlanId = planId;

        cacheElements();

        // Get last update time from plan data
        if (window.PLAN_DATA && window.PLAN_DATA.lastUpdate) {
            lastUpdateTime = new Date(window.PLAN_DATA.lastUpdate);
        } else if (options.lastUpdate) {
            lastUpdateTime = new Date(options.lastUpdate);
        }

        // Check if plan is in a recoverable state
        if (isPlanRecoverable()) {
            showRecoveryOptions();
        }
    }

    /**
     * Check if the plan is in a recoverable state
     * @returns {boolean} True if plan can be recovered
     */
    function isPlanRecoverable() {
        if (!window.PLAN_DATA) return false;

        const recoverableStates = ['in-progress', 'building', 'failed', 'stuck', 'paused'];
        return recoverableStates.includes(window.PLAN_DATA.state);
    }

    /**
     * Check if the plan appears to be stuck
     * @returns {boolean} True if plan seems stuck
     */
    function isPlanStuck() {
        if (!lastUpdateTime) return false;

        const elapsed = Date.now() - lastUpdateTime.getTime();
        return elapsed > STUCK_THRESHOLD_MS;
    }

    /**
     * Show recovery options UI
     * @param {Object} options - Display options
     */
    function showRecoveryOptions(options) {
        options = options || {};

        // Create recovery UI if it doesn't exist
        if (!elements.recoverySection) {
            createRecoveryUI();
            cacheElements();
        }

        if (!elements.recoverySection) {
            console.error('Failed to create recovery UI');
            return;
        }

        // Show the section
        elements.recoverySection.classList.remove('hidden');

        // Update status indicator
        updateStatusIndicator();

        // Update last step info
        updateLastStepInfo();

        // Start elapsed time updates
        startElapsedTimeUpdates();

        // Set up event listeners
        setupEventListeners();

        // Register keyboard shortcut for resume (Ctrl+R / Cmd+R)
        registerResumeShortcut();
    }

    /**
     * Create the recovery UI dynamically
     */
    function createRecoveryUI() {
        const container = document.getElementById('build-section') ||
                         document.querySelector('.plan-detail-container') ||
                         document.querySelector('main');

        if (!container) {
            console.error('No container found for recovery UI');
            return;
        }

        const recoveryHtml = [
            '<div id="recovery-options" class="recovery-section bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4 hidden">',
            '  <div class="flex items-start justify-between">',
            '    <div class="flex items-start">',
            '      <div id="recovery-indicator" class="flex-shrink-0 w-10 h-10 rounded-full bg-yellow-100 flex items-center justify-center mr-3">',
            '        <svg class="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>',
            '        </svg>',
            '      </div>',
            '      <div>',
            '        <h3 id="recovery-status" class="text-lg font-semibold text-yellow-800">Plan Recovery Required</h3>',
            '        <p class="text-sm text-yellow-700 mt-1">',
            '          <span id="recovery-last-step">The plan appears to be stuck or has encountered an issue.</span>',
            '        </p>',
            '        <p id="recovery-elapsed-time" class="text-xs text-yellow-600 mt-1">',
            '          Last update: calculating...',
            '        </p>',
            '      </div>',
            '    </div>',
            '    <div class="flex space-x-2">',
            '      <button id="recovery-resume-btn" class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors">',
            '        <svg class="w-4 h-4 inline-block mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '        </svg>',
            '        Resume',
            '      </button>',
            '      <button id="recovery-restart-btn" class="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors">',
            '        <svg class="w-4 h-4 inline-block mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>',
            '        </svg>',
            '        Restart',
            '      </button>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('\n');

        // Insert at the beginning of the container
        container.insertAdjacentHTML('afterbegin', recoveryHtml);
    }

    /**
     * Update the status indicator based on plan state
     */
    function updateStatusIndicator() {
        if (!elements.recoveryIndicator || !elements.recoveryStatus) return;

        const isStuck = isPlanStuck();
        const state = window.PLAN_DATA ? window.PLAN_DATA.state : 'unknown';

        let indicatorClass, iconHtml, statusText, sectionClass;

        if (state === 'failed') {
            indicatorClass = 'bg-red-100';
            sectionClass = 'bg-red-50 border-red-200';
            iconHtml = '<svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
            statusText = 'Build Failed';
            elements.recoveryStatus.className = 'text-lg font-semibold text-red-800';
        } else if (isStuck) {
            indicatorClass = 'bg-orange-100';
            sectionClass = 'bg-orange-50 border-orange-200';
            iconHtml = '<svg class="w-6 h-6 text-orange-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
            statusText = 'Plan Appears Stuck';
            elements.recoveryStatus.className = 'text-lg font-semibold text-orange-800';
        } else {
            indicatorClass = 'bg-yellow-100';
            sectionClass = 'bg-yellow-50 border-yellow-200';
            iconHtml = '<svg class="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>';
            statusText = 'Recovery Options Available';
            elements.recoveryStatus.className = 'text-lg font-semibold text-yellow-800';
        }

        elements.recoveryIndicator.className = 'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center mr-3 ' + indicatorClass;
        elements.recoveryIndicator.innerHTML = iconHtml;
        elements.recoveryStatus.textContent = statusText;

        if (elements.recoverySection) {
            elements.recoverySection.className = 'recovery-section rounded-lg p-4 mb-4 border ' + sectionClass;
        }
    }

    /**
     * Update last step info display
     */
    function updateLastStepInfo() {
        if (!elements.lastStep) return;

        let stepInfo = 'The plan appears to be stuck or has encountered an issue.';

        if (window.PLAN_DATA) {
            if (window.PLAN_DATA.failedStep) {
                stepInfo = 'Failed at step: ' + escapeHtml(window.PLAN_DATA.failedStep);
            } else if (window.PLAN_DATA.currentStep) {
                stepInfo = 'Last active step: ' + escapeHtml(window.PLAN_DATA.currentStep);
            } else if (window.PLAN_DATA.completedSteps) {
                stepInfo = 'Completed ' + window.PLAN_DATA.completedSteps + ' steps before issue.';
            }
        }

        elements.lastStep.textContent = stepInfo;
    }

    /**
     * Start updating elapsed time display
     */
    function startElapsedTimeUpdates() {
        // Clear any existing interval
        stopElapsedTimeUpdates();

        // Update immediately
        updateElapsedTime();

        // Then update every second
        updateInterval = setInterval(updateElapsedTime, UPDATE_INTERVAL_MS);
    }

    /**
     * Stop updating elapsed time display
     */
    function stopElapsedTimeUpdates() {
        if (updateInterval) {
            clearInterval(updateInterval);
            updateInterval = null;
        }
    }

    /**
     * Update the elapsed time display
     */
    function updateElapsedTime() {
        if (!elements.elapsedTime || !lastUpdateTime) {
            if (elements.elapsedTime) {
                elements.elapsedTime.textContent = 'Last update: unknown';
            }
            return;
        }

        const elapsed = Date.now() - lastUpdateTime.getTime();
        const formattedTime = formatElapsedTime(elapsed);

        elements.elapsedTime.textContent = 'Last update: ' + formattedTime + ' ago';

        // Update status indicator if plan becomes stuck
        if (isPlanStuck()) {
            updateStatusIndicator();
        }
    }

    /**
     * Format elapsed time in human-readable format
     * @param {number} ms - Elapsed time in milliseconds
     * @returns {string} Formatted time string
     */
    function formatElapsedTime(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) {
            return days + ' day' + (days > 1 ? 's' : '') + ', ' + (hours % 24) + 'h';
        } else if (hours > 0) {
            return hours + 'h ' + (minutes % 60) + 'm';
        } else if (minutes > 0) {
            return minutes + 'm ' + (seconds % 60) + 's';
        } else {
            return seconds + 's';
        }
    }

    /**
     * Set up event listeners for recovery buttons
     */
    function setupEventListeners() {
        if (elements.resumeBtn) {
            elements.resumeBtn.onclick = function() {
                resumePlan(currentPlanId);
            };
        }

        if (elements.restartBtn) {
            elements.restartBtn.onclick = function() {
                showRestartConfirmation(currentPlanId);
            };
        }
    }

    /**
     * Register keyboard shortcut for resume action
     * Uses Ctrl+R (Windows/Linux) or Cmd+R (Mac)
     */
    function registerResumeShortcut() {
        // Unregister any existing shortcut first
        unregisterResumeShortcut();

        // Only register if KeyboardShortcuts module is available
        if (typeof KeyboardShortcuts === 'undefined') {
            console.warn('KeyboardShortcuts module not available for resume shortcut');
            return;
        }

        // Register Ctrl+R / Cmd+R shortcut
        // Returns true to prevent browser refresh when plan is resumable
        resumeShortcutId = KeyboardShortcuts.registerShortcut('ctrl+r', function(event) {
            // Only handle if plan is recoverable
            if (!isPlanRecoverable()) {
                return false; // Let browser handle (refresh)
            }

            // Don't trigger if resume button is disabled or not visible
            if (elements.resumeBtn && (elements.resumeBtn.disabled ||
                elements.recoverySection.classList.contains('hidden'))) {
                return false;
            }

            // Trigger resume
            resumePlan(currentPlanId);

            // Return true to prevent browser refresh
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Update button to show shortcut hint
        updateResumeButtonHint();
    }

    /**
     * Unregister the resume keyboard shortcut
     */
    function unregisterResumeShortcut() {
        if (resumeShortcutId && typeof KeyboardShortcuts !== 'undefined') {
            KeyboardShortcuts.unregisterShortcut(resumeShortcutId);
            resumeShortcutId = null;
        }
    }

    /**
     * Update resume button to show keyboard shortcut hint
     */
    function updateResumeButtonHint() {
        if (!elements.resumeBtn) return;

        // Detect Mac for proper modifier display
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0 ||
                      navigator.userAgent.toUpperCase().indexOf('MAC') >= 0;
        const shortcutKey = isMac ? '⌘R' : 'Ctrl+R';

        // Store original HTML for restore
        elements.resumeBtn.dataset.originalHtml = elements.resumeBtn.innerHTML;

        // Update button with shortcut hint
        elements.resumeBtn.innerHTML = [
            '<svg class="w-4 h-4 inline-block mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>',
            '  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '</svg>',
            'Resume ',
            '<kbd class="ml-1 px-1.5 py-0.5 text-xs font-mono bg-blue-700 rounded opacity-75">' + shortcutKey + '</kbd>'
        ].join('');
    }

    /**
     * Resume plan from current step
     * @param {string} planId - The plan identifier
     * @returns {Promise<boolean>} True if resume started successfully
     */
    async function resumePlan(planId) {
        planId = planId || currentPlanId;

        if (!planId) {
            showToast('error', 'No plan ID provided');
            return false;
        }

        try {
            disableButton(elements.resumeBtn, 'Resuming...');
            showToast('info', 'Resuming plan...');

            const fromStep = window.PLAN_DATA ?
                (window.PLAN_DATA.failedStep || window.PLAN_DATA.currentStep) : null;

            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resume: true,
                    from_step: fromStep
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to resume plan');
            }

            showToast('success', 'Plan resumed successfully');

            // Hide recovery options
            hideRecoveryOptions();

            // Stop elapsed time updates
            stopElapsedTimeUpdates();

            // Trigger page refresh or event for UI update
            if (typeof PlanDetail !== 'undefined' && data.run_id) {
                window.location.reload();
            }

            return true;
        } catch (error) {
            console.error('Error resuming plan:', error);
            showToast('error', 'Failed to resume: ' + error.message);
            enableButton(elements.resumeBtn, 'Resume');
            return false;
        }
    }

    /**
     * Show restart confirmation dialog
     * @param {string} planId - The plan identifier
     */
    function showRestartConfirmation(planId) {
        planId = planId || currentPlanId;

        const confirmed = confirm(
            'Are you sure you want to restart this plan from the beginning?\n\n' +
            'This will:\n' +
            '• Reset all step progress\n' +
            '• Clear any partial outputs\n' +
            '• Start the build from step 1\n\n' +
            'This action cannot be undone.'
        );

        if (confirmed) {
            restartPlan(planId);
        }
    }

    /**
     * Restart plan from the beginning
     * @param {string} planId - The plan identifier
     * @returns {Promise<boolean>} True if restart started successfully
     */
    async function restartPlan(planId) {
        planId = planId || currentPlanId;

        if (!planId) {
            showToast('error', 'No plan ID provided');
            return false;
        }

        try {
            disableButton(elements.restartBtn, 'Restarting...');
            showToast('info', 'Restarting plan from beginning...');

            // First, cancel any existing run
            if (window.PLAN_DATA && window.PLAN_DATA.runId) {
                try {
                    await fetch('/api/runs/' + window.PLAN_DATA.runId + '/cancel', {
                        method: 'POST'
                    });
                } catch (e) {
                    // Ignore cancel errors - run may already be stopped
                    console.warn('Could not cancel existing run:', e);
                }
            }

            // Reset plan state
            const resetResponse = await fetch('/api/plans/' + encodeURIComponent(planId) + '/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!resetResponse.ok) {
                // Reset endpoint might not exist, continue anyway
                console.warn('Reset endpoint returned error, continuing with restart');
            }

            // Start fresh build
            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    restart: true,
                    from_step: null // Start from beginning
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to restart plan');
            }

            showToast('success', 'Plan restarted successfully');

            // Hide recovery options
            hideRecoveryOptions();

            // Stop elapsed time updates
            stopElapsedTimeUpdates();

            // Refresh the page to show new build progress
            window.location.reload();

            return true;
        } catch (error) {
            console.error('Error restarting plan:', error);
            showToast('error', 'Failed to restart: ' + error.message);
            enableButton(elements.restartBtn, 'Restart');
            return false;
        }
    }

    /**
     * Hide recovery options UI
     */
    function hideRecoveryOptions() {
        if (elements.recoverySection) {
            elements.recoverySection.classList.add('hidden');
        }
        stopElapsedTimeUpdates();
        unregisterResumeShortcut();
    }

    /**
     * Show a toast notification
     * @param {string} type - Toast type (info, success, error, warning)
     * @param {string} message - Toast message
     */
    function showToast(type, message) {
        if (typeof Toast !== 'undefined') {
            Toast[type](message);
        } else {
            console.log('[' + type.toUpperCase() + ']', message);
        }
    }

    /**
     * Disable a button and show loading state
     * @param {HTMLElement} btn - Button element
     * @param {string} text - Loading text
     */
    function disableButton(btn, text) {
        if (!btn) return;
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.innerHTML = '<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline-block" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>' + text;
    }

    /**
     * Enable a button and restore text
     * @param {HTMLElement} btn - Button element
     * @param {string} text - Button text
     */
    function enableButton(btn, text) {
        if (!btn) return;
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalHtml || text;
    }

    /**
     * Escape HTML to prevent XSS
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
     * Clean up module resources
     */
    function destroy() {
        stopElapsedTimeUpdates();
        unregisterResumeShortcut();
        if (elements.recoverySection) {
            elements.recoverySection.remove();
        }
        currentPlanId = null;
        lastUpdateTime = null;
    }

    // Public API
    return {
        init: init,
        showRecoveryOptions: showRecoveryOptions,
        hideRecoveryOptions: hideRecoveryOptions,
        resumePlan: resumePlan,
        restartPlan: restartPlan,
        isPlanStuck: isPlanStuck,
        isPlanRecoverable: isPlanRecoverable,
        setLastUpdateTime: function(time) {
            lastUpdateTime = time instanceof Date ? time : new Date(time);
            updateElapsedTime();
        },
        getElapsedTime: function() {
            return lastUpdateTime ? Date.now() - lastUpdateTime.getTime() : null;
        },
        destroy: destroy
    };
})();

// Expose globally for onclick handlers
window.PlanRecovery = PlanRecovery;

// Convenience global functions
window.resumePlan = function(planId) {
    return PlanRecovery.resumePlan(planId);
};

window.restartPlan = function(planId) {
    return PlanRecovery.restartPlan(planId);
};

window.showRecoveryOptions = function(options) {
    return PlanRecovery.showRecoveryOptions(options);
};

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanRecovery;
}
