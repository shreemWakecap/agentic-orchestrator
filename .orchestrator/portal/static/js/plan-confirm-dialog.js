/**
 * Plan Confirmation Dialog Module
 *
 * Provides a reusable confirmation dialog specifically for plan creation
 * that displays the full request text in a readable preview format.
 *
 * Dependencies:
 * - OrchestratorUtils (from common.js) for escapeHtml utility
 * - KeyboardShortcuts (from keyboard-shortcuts.js) for centralized keyboard handling
 *
 * Usage:
 *   const confirmed = await PlanConfirmDialog.showPlanConfirmDialog(descriptionText);
 *   if (confirmed) {
 *       // Proceed with plan creation
 *   }
 */

const PlanConfirmDialog = (function() {
    'use strict';

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
     * Convert newlines to <br> tags for display
     * @param {string} text - Text with newlines
     * @returns {string} Text with <br> tags
     */
    function nl2br(text) {
        return text.replace(/\n/g, '<br>');
    }

    /**
     * Format the description text for preview display
     * Preserves line breaks and handles special characters
     * @param {string} text - Raw description text
     * @returns {string} Formatted HTML for display
     */
    function formatDescriptionForPreview(text) {
        if (!text) return '<span class="text-gray-400 italic">No description provided</span>';

        // Escape HTML first, then convert newlines
        var escaped = escapeHtml(text);
        var formatted = nl2br(escaped);

        return formatted;
    }

    // =========================================================================
    // Main Dialog Function
    // =========================================================================

    /**
     * Show a confirmation dialog for plan creation
     * Displays the full request text in a readable preview format
     *
     * @param {string} descriptionText - The plan description/request text to preview
     * @param {Object} [options] - Optional configuration
     * @param {string} [options.title='Confirm Plan Creation'] - Dialog title
     * @param {string} [options.confirmText='Start Planning'] - Confirm button text
     * @param {string} [options.cancelText='Cancel'] - Cancel button text
     * @returns {Promise<boolean>} Resolves to true if confirmed, false if cancelled
     */
    function showPlanConfirmDialog(descriptionText, options) {
        return new Promise(function(resolve) {
            options = options || {};
            var title = options.title || 'Confirm Plan Creation';
            var confirmText = options.confirmText || 'Start Planning';
            var cancelText = options.cancelText || 'Cancel';

            // Create modal overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            overlay.id = 'plan-confirm-dialog-overlay';

            // Format the description for display
            var formattedDescription = formatDescriptionForPreview(descriptionText || '');

            // Calculate if content is long (more than 10 lines or 500 chars)
            var lineCount = (descriptionText || '').split('\n').length;
            var isLongContent = lineCount > 10 || (descriptionText || '').length > 500;
            var maxHeightClass = isLongContent ? 'max-h-80' : 'max-h-60';

            // Create modal content with larger preview area
            overlay.innerHTML =
                '<div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 overflow-hidden">' +
                    // Header
                    '<div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">' +
                        '<h3 class="text-lg font-semibold text-gray-900">' + escapeHtml(title) + '</h3>' +
                        '<button id="plan-confirm-close-btn" class="text-gray-400 hover:text-gray-600 transition-colors">' +
                            '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>' +
                            '</svg>' +
                        '</button>' +
                    '</div>' +
                    // Content
                    '<div class="px-6 py-4">' +
                        '<p class="text-sm text-gray-600 mb-3">Please review your request before starting the planning process:</p>' +
                        // Preview container
                        '<div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ' + maxHeightClass + ' overflow-y-auto">' +
                            '<div class="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap break-words font-mono">' +
                                formattedDescription +
                            '</div>' +
                        '</div>' +
                        // Character/line count info
                        '<div class="mt-2 text-xs text-gray-400 text-right">' +
                            (descriptionText ? descriptionText.length : 0) + ' characters, ' +
                            lineCount + ' line' + (lineCount !== 1 ? 's' : '') +
                        '</div>' +
                    '</div>' +
                    // Footer
                    '<div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3 border-t border-gray-200">' +
                        '<button id="plan-confirm-cancel-btn" class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium">' +
                            escapeHtml(cancelText) +
                        '</button>' +
                        '<button id="plan-confirm-submit-btn" class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center space-x-2">' +
                            '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>' +
                            '</svg>' +
                            '<span>' + escapeHtml(confirmText) + '</span>' +
                        '</button>' +
                    '</div>' +
                '</div>';

            document.body.appendChild(overlay);

            // Get button references
            var confirmBtn = document.getElementById('plan-confirm-submit-btn');
            var cancelBtn = document.getElementById('plan-confirm-cancel-btn');
            var closeBtn = document.getElementById('plan-confirm-close-btn');

            // Track if dialog has been resolved
            var resolved = false;

            // Track registered shortcut IDs for cleanup
            var escShortcutId = null;
            var ctrlEnterShortcutId = null;
            var metaEnterShortcutId = null;

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

            // Register keyboard shortcuts using centralized module with MODAL priority
            if (typeof KeyboardShortcuts !== 'undefined') {
                // Notify modal opened for priority handling
                KeyboardShortcuts.modalOpened();

                // ESC to cancel
                escShortcutId = KeyboardShortcuts.registerShortcut('esc', function(e) {
                    resolveDialog(false);
                    return true; // Explicitly return true to prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);

                // Ctrl+Enter to confirm
                ctrlEnterShortcutId = KeyboardShortcuts.registerShortcut('ctrl+enter', function(e) {
                    resolveDialog(true);
                    return true; // Explicitly return true to prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);

                // Meta+Enter (Cmd+Enter on Mac) to confirm
                metaEnterShortcutId = KeyboardShortcuts.registerShortcut('meta+enter', function(e) {
                    resolveDialog(true);
                    return true; // Explicitly return true to prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);
            }

            // Attach event listeners
            confirmBtn.addEventListener('click', function() {
                resolveDialog(true);
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

            // Focus confirm button for quick keyboard confirmation
            confirmBtn.focus();
        });
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        showPlanConfirmDialog: showPlanConfirmDialog
    };
})();

// Expose globally for use in other modules
window.showPlanConfirmDialog = PlanConfirmDialog.showPlanConfirmDialog;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanConfirmDialog;
}
