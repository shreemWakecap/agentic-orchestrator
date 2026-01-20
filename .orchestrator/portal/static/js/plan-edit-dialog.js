/**
 * Plan Edit Dialog Module
 *
 * Provides a modal dialog for editing plan details including goal, request, and content.
 * Features AI improvement buttons for request text using the improve-request endpoint.
 *
 * Dependencies:
 * - OrchestratorUtils (from common.js) for escapeHtml utility
 *
 * Usage:
 *   const result = await PlanEditDialog.showEditDialog(planData);
 *   if (result.saved) {
 *       // Use result.data with updated plan fields
 *   }
 */

const PlanEditDialog = (function() {
    'use strict';

    // =========================================================================
    // Private Helpers
    // =========================================================================

    function escapeHtml(text) {
        if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.escapeHtml) {
            return OrchestratorUtils.escapeHtml(text);
        }
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Add keyframes for animations if not present
     */
    function ensureKeyframes() {
        if (!document.getElementById('plan-edit-dialog-keyframes')) {
            var style = document.createElement('style');
            style.id = 'plan-edit-dialog-keyframes';
            style.textContent = [
                '@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }',
                '@keyframes pulse-glow { 0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); } 50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.6); } }',
                '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }',
                '.animate-pulse-glow { animation: pulse-glow 2s infinite; }',
                '.animate-spin { animation: spin 1s linear infinite; }'
            ].join('\n');
            document.head.appendChild(style);
        }
    }

    // =========================================================================
    // Main Dialog Function
    // =========================================================================

    /**
     * Show the plan edit dialog
     *
     * @param {Object} planData - The plan data to edit
     * @param {string} planData.id - Plan ID
     * @param {string} planData.goal - Plan goal/title
     * @param {string} planData.request - Original request text
     * @param {string} planData.content - Plan content/steps
     * @returns {Promise<{saved: boolean, data: Object|null}>}
     */
    function showEditDialog(planData) {
        return new Promise(function(resolve) {
            ensureKeyframes();

            // State
            var isImproving = false;
            var escShortcutId = null;

            // Create overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-50 flex items-center justify-center p-4';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
            overlay.style.backdropFilter = 'blur(4px)';

            // Create dialog
            var dialog = document.createElement('div');
            dialog.className = 'glass-card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col';
            dialog.style.animation = 'fadeInUp 0.3s ease-out';

            // Notify keyboard shortcuts module that a modal is open
            if (typeof KeyboardShortcuts !== 'undefined') {
                KeyboardShortcuts.modalOpened();
            }

            // Build dialog HTML
            dialog.innerHTML = buildDialogHTML(planData);

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            // Get element references
            var elements = {
                closeBtn: dialog.querySelector('#plan-edit-close-btn'),
                cancelBtn: dialog.querySelector('#plan-edit-cancel-btn'),
                saveBtn: dialog.querySelector('#plan-edit-save-btn'),
                goalInput: dialog.querySelector('#plan-edit-goal'),
                requestTextarea: dialog.querySelector('#plan-edit-request'),
                contentTextarea: dialog.querySelector('#plan-edit-content'),
                improveRequestBtn: dialog.querySelector('#plan-edit-improve-request-btn'),
                improveContentBtn: dialog.querySelector('#plan-edit-improve-content-btn')
            };

            function cleanup() {
                // Unregister ESC shortcut
                if (escShortcutId && typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.unregisterShortcut(escShortcutId);
                    escShortcutId = null;
                }
                // Notify keyboard shortcuts module that modal is closed
                if (typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.modalClosed();
                }
                overlay.remove();
            }

            function close(result) {
                cleanup();
                resolve(result);
            }

            function setImproving(btn, improving) {
                isImproving = improving;
                if (improving) {
                    btn.disabled = true;
                    btn.innerHTML = [
                        '<svg class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">',
                        '  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
                        '  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
                        '</svg>',
                        'Improving...'
                    ].join('');
                } else {
                    btn.disabled = false;
                    btn.innerHTML = [
                        '<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
                        '  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
                        '</svg>',
                        'AI Improve'
                    ].join('');
                }
            }

            function improveText(textarea, btn) {
                var text = textarea.value.trim();
                if (!text || isImproving) return;

                setImproving(btn, true);

                fetch('/api/workflows/improve-request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ draft: text })
                })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    setImproving(btn, false);
                    if (data.success && data.improved && data.improved !== text) {
                        textarea.value = data.improved;
                        // Trigger input event to update any watchers
                        textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                })
                .catch(function(err) {
                    console.error('Improvement failed:', err);
                    setImproving(btn, false);
                });
            }

            function getFormData() {
                return {
                    id: planData.id,
                    goal: elements.goalInput.value.trim(),
                    request: elements.requestTextarea.value.trim(),
                    content: elements.contentTextarea.value.trim()
                };
            }

            function validateForm() {
                var data = getFormData();
                return data.goal.length > 0;
            }

            // Event handlers
            elements.closeBtn.addEventListener('click', function() {
                close({ saved: false, data: null });
            });

            elements.cancelBtn.addEventListener('click', function() {
                close({ saved: false, data: null });
            });

            elements.saveBtn.addEventListener('click', function() {
                if (validateForm()) {
                    close({ saved: true, data: getFormData() });
                }
            });

            elements.improveRequestBtn.addEventListener('click', function() {
                improveText(elements.requestTextarea, elements.improveRequestBtn);
            });

            elements.improveContentBtn.addEventListener('click', function() {
                improveText(elements.contentTextarea, elements.improveContentBtn);
            });

            // Handle escape key using centralized keyboard shortcuts
            if (typeof KeyboardShortcuts !== 'undefined') {
                escShortcutId = KeyboardShortcuts.registerShortcut('esc', function(e) {
                    if (!isImproving) {
                        close({ saved: false, data: null });
                        return true;
                    }
                    return false;
                }, KeyboardShortcuts.PRIORITY.MODAL);
            } else {
                // Fallback for when KeyboardShortcuts is not available
                document.addEventListener('keydown', function handleKeydown(e) {
                    if (e.key === 'Escape' && !isImproving) {
                        document.removeEventListener('keydown', handleKeydown);
                        close({ saved: false, data: null });
                    }
                });
            }

            // Click outside to close
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay && !isImproving) {
                    close({ saved: false, data: null });
                }
            });

            // Focus goal input on open
            setTimeout(function() {
                elements.goalInput.focus();
            }, 100);
        });
    }

    // =========================================================================
    // HTML Builders
    // =========================================================================

    function buildDialogHTML(planData) {
        var escapedGoal = escapeHtml(planData.goal || '');
        var escapedRequest = escapeHtml(planData.request || '');
        var escapedContent = escapeHtml(planData.content || '');

        return [
            // Header with gradient
            '<div class="relative px-6 py-4 border-b border-primary/10 dark:border-primary/10">',
            '  <div class="absolute inset-0 bg-gradient-to-r from-violet-500/10 via-purple-500/10 to-indigo-500/10"></div>',
            '  <div class="relative flex items-center justify-between">',
            '    <div class="flex items-center">',
            '      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mr-3 shadow-lg animate-pulse-glow">',
            '        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '        </svg>',
            '      </div>',
            '      <div>',
            '        <h2 class="text-xl font-bold text-gradient-primary">Edit Plan</h2>',
            '        <p class="text-xs text-tertiary dark:text-tertiary">Modify plan goal, request, and content</p>',
            '      </div>',
            '    </div>',
            '    <button id="plan-edit-close-btn" type="button" class="p-2 text-tertiary hover:text-primary transition-colors rounded-lg hover:bg-tertiary/50">',
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>',
            '      </svg>',
            '    </button>',
            '  </div>',
            '</div>',

            // Content area
            '<div class="flex-1 overflow-y-auto p-6 space-y-6">',

            // Goal input
            '  <div class="space-y-2">',
            '    <label for="plan-edit-goal" class="block text-sm font-medium text-primary dark:text-primary">',
            '      Plan Goal',
            '    </label>',
            '    <input type="text" id="plan-edit-goal" value="' + escapedGoal + '"',
            '           class="w-full px-4 py-3 rounded-xl border border-primary/20 dark:border-primary/20 bg-tertiary/30 dark:bg-tertiary/30 text-primary dark:text-primary focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"',
            '           placeholder="Enter the plan goal...">',
            '  </div>',

            // Request textarea with AI improve button
            '  <div class="space-y-2">',
            '    <div class="flex items-center justify-between">',
            '      <label for="plan-edit-request" class="block text-sm font-medium text-primary dark:text-primary">',
            '        Original Request',
            '      </label>',
            '      <button id="plan-edit-improve-request-btn" type="button" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50 transition-colors">',
            '        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '        </svg>',
            '        AI Improve',
            '      </button>',
            '    </div>',
            '    <textarea id="plan-edit-request" rows="4"',
            '              class="w-full px-4 py-3 rounded-xl border border-primary/20 dark:border-primary/20 bg-tertiary/30 dark:bg-tertiary/30 text-primary dark:text-primary focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all resize-none font-mono text-sm"',
            '              placeholder="Enter the original request...">' + escapedRequest + '</textarea>',
            '  </div>',

            // Content textarea with AI improve button
            '  <div class="space-y-2">',
            '    <div class="flex items-center justify-between">',
            '      <label for="plan-edit-content" class="block text-sm font-medium text-primary dark:text-primary">',
            '        Plan Content',
            '      </label>',
            '      <button id="plan-edit-improve-content-btn" type="button" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50 transition-colors">',
            '        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '        </svg>',
            '        AI Improve',
            '      </button>',
            '    </div>',
            '    <textarea id="plan-edit-content" rows="8"',
            '              class="w-full px-4 py-3 rounded-xl border border-primary/20 dark:border-primary/20 bg-tertiary/30 dark:bg-tertiary/30 text-primary dark:text-primary focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all resize-none font-mono text-sm"',
            '              placeholder="Enter the plan content...">' + escapedContent + '</textarea>',
            '  </div>',

            '</div>',

            // Footer with actions
            '<div class="px-6 py-4 border-t border-primary/10 dark:border-primary/10 bg-tertiary/30 dark:bg-tertiary/30">',
            '  <div class="flex items-center justify-end gap-3">',
            '    <button id="plan-edit-cancel-btn" type="button" class="btn btn-secondary btn-modern">',
            '      Cancel',
            '    </button>',
            '    <button id="plan-edit-save-btn" type="button" class="btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-violet-500/25">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>',
            '      </svg>',
            '      Save Changes',
            '    </button>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        showEditDialog: showEditDialog
    };

})();

// Expose globally for use in other modules
if (typeof window !== 'undefined') {
    window.PlanEditDialog = PlanEditDialog;
}

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanEditDialog;
}
