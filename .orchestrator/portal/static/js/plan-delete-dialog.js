/**
 * Plan Delete Dialog Module
 *
 * Provides an enhanced delete confirmation dialog specifically for plan deletion
 * that shows different warning levels based on plan state:
 * - Pending plans: Standard confirmation
 * - Active plans (building, in-progress, running): Stronger warning about data loss
 *   and running processes, with "I understand" checkbox acknowledgment required
 *
 * Dependencies:
 * - OrchestratorUtils (from common.js) for escapeHtml utility
 * - KeyboardShortcuts (from keyboard-shortcuts.js) for centralized keyboard handling
 *
 * Usage:
 *   const confirmed = await PlanDeleteDialog.showDeleteConfirmation(planId, planState);
 *   if (confirmed) {
 *       // Proceed with plan deletion
 *   }
 */

const PlanDeleteDialog = (function() {
    'use strict';

    // =========================================================================
    // Constants
    // =========================================================================

    /**
     * Plan states that are considered "active" and require stronger warnings
     */
    const ACTIVE_STATES = ['building', 'in-progress', 'running', 'in_progress'];

    /**
     * Warning levels
     */
    const WARNING_LEVEL = {
        STANDARD: 'standard',
        HIGH: 'high'
    };

    // =========================================================================
    // Private Helpers
    // =========================================================================

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.escapeHtml) {
            return OrchestratorUtils.escapeHtml(text);
        }
        // Fallback escaping
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Determine warning level based on plan state
     * @param {string} planState - Current plan state
     * @returns {string} Warning level: 'standard' or 'high'
     */
    function getWarningLevel(planState) {
        if (!planState) return WARNING_LEVEL.STANDARD;
        var normalizedState = planState.toLowerCase().trim();
        return ACTIVE_STATES.includes(normalizedState)
            ? WARNING_LEVEL.HIGH
            : WARNING_LEVEL.STANDARD;
    }

    /**
     * Get warning message based on plan state
     * @param {string} planState - Current plan state
     * @param {string} warningLevel - Warning level
     * @returns {Object} Object with title, message, and additional warnings
     */
    function getWarningContent(planState, warningLevel) {
        var stateDisplay = escapeHtml(planState || 'unknown');

        if (warningLevel === WARNING_LEVEL.HIGH) {
            return {
                title: 'Delete Active Plan',
                icon: 'exclamation-triangle',
                iconColor: 'text-red-600',
                headerBg: 'bg-red-50',
                headerBorder: 'border-red-200',
                message: 'This plan is currently <strong class="text-red-700">' + stateDisplay + '</strong>. ' +
                         'Deleting it may result in:',
                warnings: [
                    'Immediate termination of running processes',
                    'Loss of any unsaved progress or partial results',
                    'Potential data corruption if operations are interrupted',
                    'Resources may need manual cleanup'
                ],
                confirmText: 'Delete Active Plan',
                confirmClass: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
                requiresAcknowledgment: true,
                acknowledgmentText: 'I understand that deleting this active plan may cause data loss and interrupt running processes'
            };
        }

        return {
            title: 'Delete Plan',
            icon: 'trash',
            iconColor: 'text-gray-600',
            headerBg: 'bg-gray-50',
            headerBorder: 'border-gray-200',
            message: 'Are you sure you want to delete this plan?',
            warnings: [],
            confirmText: 'Delete Plan',
            confirmClass: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
            requiresAcknowledgment: false,
            acknowledgmentText: ''
        };
    }

    /**
     * Get SVG icon markup
     * @param {string} iconName - Icon name ('trash' or 'exclamation-triangle')
     * @returns {string} SVG markup
     */
    function getIcon(iconName) {
        if (iconName === 'exclamation-triangle') {
            return '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                   '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
                   'd="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>' +
                   '</svg>';
        }
        // Default trash icon
        return '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
               '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
               'd="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>' +
               '</svg>';
    }

    // =========================================================================
    // Main Dialog Function
    // =========================================================================

    /**
     * Show a delete confirmation dialog with appropriate warning level
     *
     * @param {string} planId - The plan identifier to display in the dialog
     * @param {string} planState - Current plan state (e.g., 'pending', 'building', 'running')
     * @returns {Promise<boolean>} Resolves to true if confirmed, false if cancelled
     */
    function showDeleteConfirmation(planId, planState) {
        return new Promise(function(resolve) {
            var warningLevel = getWarningLevel(planState);
            var content = getWarningContent(planState, warningLevel);

            // Create modal overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            overlay.id = 'plan-delete-dialog-overlay';

            // Build warnings list HTML
            var warningsHtml = '';
            if (content.warnings.length > 0) {
                warningsHtml = '<ul class="mt-3 space-y-2">';
                content.warnings.forEach(function(warning) {
                    warningsHtml +=
                        '<li class="flex items-start space-x-2">' +
                            '<svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
                            '</svg>' +
                            '<span class="text-sm text-gray-700">' + escapeHtml(warning) + '</span>' +
                        '</li>';
                });
                warningsHtml += '</ul>';
            }

            // Build acknowledgment checkbox HTML
            var acknowledgmentHtml = '';
            if (content.requiresAcknowledgment) {
                acknowledgmentHtml =
                    '<div class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">' +
                        '<label class="flex items-start space-x-3 cursor-pointer">' +
                            '<input type="checkbox" id="delete-acknowledgment-checkbox" ' +
                                   'class="mt-1 h-4 w-4 text-red-600 border-gray-300 rounded focus:ring-red-500">' +
                            '<span class="text-sm text-red-800 font-medium">' +
                                escapeHtml(content.acknowledgmentText) +
                            '</span>' +
                        '</label>' +
                    '</div>';
            }

            // Create modal content
            overlay.innerHTML =
                '<div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">' +
                    // Header
                    '<div class="px-6 py-4 border-b ' + content.headerBorder + ' ' + content.headerBg + ' flex items-center space-x-3">' +
                        '<div class="' + content.iconColor + '">' +
                            getIcon(content.icon) +
                        '</div>' +
                        '<div class="flex-1">' +
                            '<h3 class="text-lg font-semibold text-gray-900">' + escapeHtml(content.title) + '</h3>' +
                            '<p class="text-sm text-gray-500">Plan: ' + escapeHtml(planId || 'Unknown') + '</p>' +
                        '</div>' +
                        '<button id="delete-dialog-close-btn" class="text-gray-400 hover:text-gray-600 transition-colors">' +
                            '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>' +
                            '</svg>' +
                        '</button>' +
                    '</div>' +
                    // Content
                    '<div class="px-6 py-4">' +
                        '<p class="text-gray-700">' + content.message + '</p>' +
                        warningsHtml +
                        acknowledgmentHtml +
                        // Additional note about permanence
                        '<p class="mt-4 text-sm text-gray-500 italic">' +
                            'This action cannot be undone. The plan and all associated data will be permanently removed.' +
                        '</p>' +
                    '</div>' +
                    // Footer
                    '<div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3 border-t border-gray-200">' +
                        '<button id="delete-dialog-cancel-btn" class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500">' +
                            'Cancel' +
                        '</button>' +
                        '<button id="delete-dialog-confirm-btn" class="px-4 py-2 text-white rounded-lg transition-colors font-medium flex items-center space-x-2 focus:outline-none focus:ring-2 focus:ring-offset-2 ' + content.confirmClass + '"' +
                            (content.requiresAcknowledgment ? ' disabled' : '') + '>' +
                            '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>' +
                            '</svg>' +
                            '<span>' + escapeHtml(content.confirmText) + '</span>' +
                        '</button>' +
                    '</div>' +
                '</div>';

            document.body.appendChild(overlay);

            // Get element references
            var confirmBtn = document.getElementById('delete-dialog-confirm-btn');
            var cancelBtn = document.getElementById('delete-dialog-cancel-btn');
            var closeBtn = document.getElementById('delete-dialog-close-btn');
            var acknowledgmentCheckbox = document.getElementById('delete-acknowledgment-checkbox');

            // Track if dialog has been resolved
            var resolved = false;

            // Track registered shortcut IDs for cleanup
            var escShortcutId = null;
            var ctrlEnterShortcutId = null;
            var metaEnterShortcutId = null;

            /**
             * Update confirm button state based on acknowledgment
             */
            function updateConfirmButtonState() {
                if (!content.requiresAcknowledgment) return;

                if (acknowledgmentCheckbox && acknowledgmentCheckbox.checked) {
                    confirmBtn.disabled = false;
                    confirmBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                } else {
                    confirmBtn.disabled = true;
                    confirmBtn.classList.add('opacity-50', 'cursor-not-allowed');
                }
            }

            /**
             * Cleanup function to remove dialog and event listeners
             */
            function cleanup() {
                // Unregister keyboard shortcuts
                if (escShortcutId && typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.unregisterShortcut(escShortcutId);
                }
                if (ctrlEnterShortcutId && typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.unregisterShortcut(ctrlEnterShortcutId);
                }
                if (metaEnterShortcutId && typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.unregisterShortcut(metaEnterShortcutId);
                }

                // Notify modal closed
                if (typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.modalClosed();
                }

                // Remove overlay from DOM
                if (overlay.parentNode) {
                    overlay.remove();
                }
            }

            /**
             * Resolve the promise and cleanup
             * @param {boolean} result - The resolution value
             */
            function resolveDialog(result) {
                if (resolved) return;
                resolved = true;
                cleanup();
                resolve(result);
            }

            // Set up acknowledgment checkbox listener if required
            if (acknowledgmentCheckbox) {
                acknowledgmentCheckbox.addEventListener('change', updateConfirmButtonState);
                // Initialize button state
                updateConfirmButtonState();
            }

            // Register keyboard shortcuts using centralized module with MODAL priority
            if (typeof KeyboardShortcuts !== 'undefined') {
                // Notify modal opened for priority handling
                KeyboardShortcuts.modalOpened();

                // ESC to cancel
                escShortcutId = KeyboardShortcuts.registerShortcut('esc', function(e) {
                    resolveDialog(false);
                    return true; // Prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);

                // Ctrl+Enter to confirm (only if button is enabled)
                ctrlEnterShortcutId = KeyboardShortcuts.registerShortcut('ctrl+enter', function(e) {
                    if (!confirmBtn.disabled) {
                        resolveDialog(true);
                    }
                    return true; // Prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);

                // Meta+Enter (Cmd+Enter on Mac) to confirm
                metaEnterShortcutId = KeyboardShortcuts.registerShortcut('meta+enter', function(e) {
                    if (!confirmBtn.disabled) {
                        resolveDialog(true);
                    }
                    return true; // Prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);
            }

            // Attach event listeners
            confirmBtn.addEventListener('click', function() {
                if (!confirmBtn.disabled) {
                    resolveDialog(true);
                }
            });

            cancelBtn.addEventListener('click', function() {
                resolveDialog(false);
            });

            closeBtn.addEventListener('click', function() {
                resolveDialog(false);
            });

            // Handle overlay click (cancel)
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    resolveDialog(false);
                }
            });

            // Focus appropriate element
            if (content.requiresAcknowledgment && acknowledgmentCheckbox) {
                // Focus checkbox for active plans
                acknowledgmentCheckbox.focus();
            } else {
                // Focus cancel button for standard confirmations (safer default)
                cancelBtn.focus();
            }
        });
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        showDeleteConfirmation: showDeleteConfirmation,
        // Expose constants for testing
        ACTIVE_STATES: ACTIVE_STATES,
        WARNING_LEVEL: WARNING_LEVEL
    };
})();

// Expose globally for use in other modules
window.PlanDeleteDialog = PlanDeleteDialog;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanDeleteDialog;
}
