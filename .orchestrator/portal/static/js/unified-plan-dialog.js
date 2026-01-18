/**
 * Unified Plan Dialog Module
 *
 * Combines AI improvement and plan confirmation into a single streamlined flow.
 * Shows AI improvement immediately, then allows user to review and confirm creation.
 *
 * Dependencies:
 * - OrchestratorUtils (from common.js) for escapeHtml utility
 *
 * Usage:
 *   const result = await UnifiedPlanDialog.showCreatePlanDialog(draftText);
 *   if (result.created) {
 *       // Plan was created, result.runId contains the plan run ID
 *   }
 */

const UnifiedPlanDialog = (function() {
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

    function nl2br(text) {
        return text.replace(/\n/g, '<br>');
    }

    /**
     * Typewriter effect for text
     */
    function typewriterEffect(element, text, speed) {
        speed = speed || 15;
        return new Promise(function(resolve) {
            var index = 0;
            var escaped = escapeHtml(text);
            element.innerHTML = '';

            function type() {
                if (index < escaped.length) {
                    if (escaped[index] === '&') {
                        var entityEnd = escaped.indexOf(';', index);
                        if (entityEnd !== -1) {
                            element.innerHTML += escaped.substring(index, entityEnd + 1);
                            index = entityEnd + 1;
                        } else {
                            element.innerHTML += escaped[index];
                            index++;
                        }
                    } else if (escaped[index] === '<') {
                        var tagEnd = escaped.indexOf('>', index);
                        if (tagEnd !== -1) {
                            element.innerHTML += escaped.substring(index, tagEnd + 1);
                            index = tagEnd + 1;
                        } else {
                            element.innerHTML += escaped[index];
                            index++;
                        }
                    } else {
                        element.innerHTML += escaped[index];
                        index++;
                    }
                    setTimeout(type, speed);
                } else {
                    resolve();
                }
            }
            type();
        });
    }

    /**
     * Add keyframes for animations if not present
     */
    function ensureKeyframes() {
        if (!document.getElementById('unified-plan-dialog-keyframes')) {
            var style = document.createElement('style');
            style.id = 'unified-plan-dialog-keyframes';
            style.textContent = [
                '@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }',
                '@keyframes pulse-glow { 0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); } 50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.6); } }',
                '@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }',
                '@keyframes checkmark { 0% { transform: scale(0); } 50% { transform: scale(1.2); } 100% { transform: scale(1); } }',
                '.animate-pulse-glow { animation: pulse-glow 2s infinite; }',
                '.animate-shimmer { background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); background-size: 200% 100%; animation: shimmer 1.5s infinite; }',
                '.animate-checkmark { animation: checkmark 0.4s ease-out; }'
            ].join('\n');
            document.head.appendChild(style);
        }
    }

    // =========================================================================
    // Dialog States
    // =========================================================================

    var STATE = {
        IMPROVING: 'improving',
        REVIEW: 'review',
        CREATING: 'creating',
        SUCCESS: 'success',
        ERROR: 'error'
    };

    // =========================================================================
    // Main Dialog Function
    // =========================================================================

    /**
     * Show the unified create plan dialog
     *
     * @param {string} draftText - The original draft text to improve and create plan from
     * @returns {Promise<{created: boolean, runId: string|null}>}
     */
    function showCreatePlanDialog(draftText) {
        return new Promise(function(resolve) {
            ensureKeyframes();

            // State variables
            var currentState = STATE.IMPROVING;
            var improvedText = '';
            var finalText = draftText;
            var runId = null;

            // Create overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-50 flex items-center justify-center p-4';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
            overlay.style.backdropFilter = 'blur(4px)';

            // Create dialog
            var dialog = document.createElement('div');
            dialog.className = 'glass-card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col';
            dialog.style.animation = 'fadeInUp 0.3s ease-out';

            // Build initial HTML
            dialog.innerHTML = buildDialogHTML(draftText);

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            // Get element references
            var elements = {
                closeBtn: dialog.querySelector('#unified-close-btn'),
                keepOriginalBtn: dialog.querySelector('#unified-keep-original-btn'),
                editBtn: dialog.querySelector('#unified-edit-btn'),
                useImprovedBtn: dialog.querySelector('#unified-use-improved-btn'),
                createBtn: dialog.querySelector('#unified-create-btn'),
                loadingSection: dialog.querySelector('#unified-loading'),
                reviewSection: dialog.querySelector('#unified-review'),
                creatingSection: dialog.querySelector('#unified-creating'),
                successSection: dialog.querySelector('#unified-success'),
                errorSection: dialog.querySelector('#unified-error'),
                improvedTextEl: dialog.querySelector('#unified-improved-text'),
                finalPreviewEl: dialog.querySelector('#unified-final-preview'),
                editTextarea: dialog.querySelector('#unified-edit-textarea'),
                headerTitle: dialog.querySelector('#unified-header-title'),
                headerSubtitle: dialog.querySelector('#unified-header-subtitle'),
                footerActions: dialog.querySelector('#unified-footer-actions'),
                errorMessage: dialog.querySelector('#unified-error-message'),
                retryBtn: dialog.querySelector('#unified-retry-btn')
            };

            function cleanup() {
                overlay.remove();
            }

            function close(result) {
                cleanup();
                resolve(result);
            }

            function updateState(newState) {
                currentState = newState;

                // Hide all sections
                elements.loadingSection.classList.add('hidden');
                elements.reviewSection.classList.add('hidden');
                elements.creatingSection.classList.add('hidden');
                elements.successSection.classList.add('hidden');
                elements.errorSection.classList.add('hidden');

                // Update header based on state
                switch (newState) {
                    case STATE.IMPROVING:
                        elements.headerTitle.textContent = 'AI-Enhanced Plan Creation';
                        elements.headerSubtitle.textContent = 'Improving your request with AI...';
                        elements.loadingSection.classList.remove('hidden');
                        elements.footerActions.classList.add('hidden');
                        break;

                    case STATE.REVIEW:
                        elements.headerTitle.textContent = 'Review Your Plan';
                        elements.headerSubtitle.textContent = 'Review and confirm your plan request';
                        elements.reviewSection.classList.remove('hidden');
                        elements.footerActions.classList.remove('hidden');
                        break;

                    case STATE.CREATING:
                        elements.headerTitle.textContent = 'Creating Plan';
                        elements.headerSubtitle.textContent = 'Setting up your plan...';
                        elements.creatingSection.classList.remove('hidden');
                        elements.footerActions.classList.add('hidden');
                        break;

                    case STATE.SUCCESS:
                        elements.headerTitle.textContent = 'Plan Created!';
                        elements.headerSubtitle.textContent = 'Your plan is ready';
                        elements.successSection.classList.remove('hidden');
                        elements.footerActions.classList.add('hidden');
                        break;

                    case STATE.ERROR:
                        elements.headerTitle.textContent = 'Creation Failed';
                        elements.headerSubtitle.textContent = 'There was a problem creating your plan';
                        elements.errorSection.classList.remove('hidden');
                        elements.footerActions.classList.add('hidden');
                        break;
                }
            }

            function showReviewWithText(text, isImproved) {
                finalText = text;
                improvedText = isImproved ? text : '';

                // Update the preview
                if (isImproved && elements.improvedTextEl) {
                    typewriterEffect(elements.improvedTextEl, text, 10);
                }

                // Show/hide buttons based on whether we have improvements
                if (isImproved) {
                    elements.keepOriginalBtn.classList.remove('hidden');
                    elements.useImprovedBtn.classList.remove('hidden');
                } else {
                    elements.keepOriginalBtn.classList.add('hidden');
                    elements.useImprovedBtn.classList.add('hidden');
                }

                updateState(STATE.REVIEW);
            }

            function createPlan(description) {
                updateState(STATE.CREATING);

                fetch('/api/workflows/plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ description: description })
                })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.run_id) {
                        runId = data.run_id;
                        updateState(STATE.SUCCESS);
                        // Auto-close after success and redirect
                        setTimeout(function() {
                            close({ created: true, runId: runId });
                            // Navigate to the run page to show workflow progress
                            if (typeof window !== 'undefined') {
                                window.location.href = '/runs/' + runId;
                            }
                        }, 1500);
                    } else {
                        throw new Error(data.detail || data.error || 'Failed to create plan');
                    }
                })
                .catch(function(err) {
                    console.error('Plan creation failed:', err);
                    elements.errorMessage.textContent = err.message || 'Failed to create plan. Please try again.';
                    updateState(STATE.ERROR);
                });
            }

            // Event handlers
            elements.closeBtn.addEventListener('click', function() {
                close({ created: false, runId: null });
            });

            elements.keepOriginalBtn.addEventListener('click', function() {
                finalText = draftText;
                createPlan(finalText);
            });

            elements.editBtn.addEventListener('click', function() {
                // Switch to edit mode
                elements.reviewSection.innerHTML = buildEditModeHTML(finalText);
                elements.editTextarea = dialog.querySelector('#unified-edit-textarea');
                var saveEditBtn = dialog.querySelector('#unified-save-edit-btn');
                var cancelEditBtn = dialog.querySelector('#unified-cancel-edit-btn');

                saveEditBtn.addEventListener('click', function() {
                    finalText = elements.editTextarea.value.trim();
                    if (finalText) {
                        createPlan(finalText);
                    }
                });

                cancelEditBtn.addEventListener('click', function() {
                    // Restore review mode
                    elements.reviewSection.innerHTML = buildReviewContentHTML(draftText);
                    elements.improvedTextEl = dialog.querySelector('#unified-improved-text');
                    if (improvedText) {
                        elements.improvedTextEl.textContent = improvedText;
                    }
                });
            });

            elements.useImprovedBtn.addEventListener('click', function() {
                finalText = improvedText || draftText;
                createPlan(finalText);
            });

            elements.createBtn.addEventListener('click', function() {
                createPlan(finalText);
            });

            elements.retryBtn.addEventListener('click', function() {
                createPlan(finalText);
            });

            // Handle escape key
            function handleKeydown(e) {
                if (e.key === 'Escape' && currentState !== STATE.CREATING) {
                    close({ created: false, runId: null });
                }
            }
            document.addEventListener('keydown', handleKeydown);

            // Click outside to close (only during certain states)
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay && currentState !== STATE.CREATING && currentState !== STATE.SUCCESS) {
                    close({ created: false, runId: null });
                }
            });

            // Start the AI improvement process immediately
            fetch('/api/workflows/improve-request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft: draftText })
            })
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                if (data.success && data.improved && data.improved !== draftText) {
                    improvedText = data.improved;
                    showReviewWithText(improvedText, true);
                } else {
                    // No improvement available, show original for confirmation
                    showReviewWithText(draftText, false);
                }
            })
            .catch(function(err) {
                console.error('Improvement failed:', err);
                // Fall back to showing original text
                showReviewWithText(draftText, false);
            });
        });
    }

    // =========================================================================
    // HTML Builders
    // =========================================================================

    function buildDialogHTML(draftText) {
        var escapedDraft = escapeHtml(draftText);

        return [
            // Header with gradient
            '<div class="relative px-6 py-4 border-b border-primary/10 dark:border-primary/10">',
            '  <div class="absolute inset-0 bg-gradient-to-r from-violet-500/10 via-purple-500/10 to-indigo-500/10"></div>',
            '  <div class="relative flex items-center justify-between">',
            '    <div class="flex items-center">',
            '      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mr-3 shadow-lg animate-pulse-glow">',
            '        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '        </svg>',
            '      </div>',
            '      <div>',
            '        <h2 id="unified-header-title" class="text-xl font-bold text-gradient-primary">AI-Enhanced Plan Creation</h2>',
            '        <p id="unified-header-subtitle" class="text-xs text-tertiary dark:text-tertiary">Improving your request with AI...</p>',
            '      </div>',
            '    </div>',
            '    <button id="unified-close-btn" type="button" class="p-2 text-tertiary hover:text-primary transition-colors rounded-lg hover:bg-tertiary/50">',
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>',
            '      </svg>',
            '    </button>',
            '  </div>',
            '</div>',

            // Content area
            '<div class="flex-1 overflow-y-auto p-6">',

            // Loading state (AI improvement in progress)
            '  <div id="unified-loading" class="flex flex-col items-center justify-center py-12">',
            '    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mb-6 animate-pulse-glow">',
            '      <svg class="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">',
            '        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
            '        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
            '      </svg>',
            '    </div>',
            '    <p class="text-lg font-medium text-violet-600 dark:text-violet-400 mb-2">Enhancing Your Request</p>',
            '    <p class="text-sm text-tertiary dark:text-tertiary">AI is analyzing and improving your plan description...</p>',
            '    <div class="mt-6 glass rounded-xl p-4 max-w-lg">',
            '      <p class="text-xs text-tertiary dark:text-tertiary uppercase tracking-wide mb-2">Your Draft</p>',
            '      <p class="text-sm text-secondary dark:text-secondary font-mono whitespace-pre-wrap opacity-75">' + nl2br(escapedDraft) + '</p>',
            '    </div>',
            '  </div>',

            // Review state (side-by-side comparison)
            '  <div id="unified-review" class="hidden">',
            buildReviewContentHTML(draftText),
            '  </div>',

            // Creating state
            '  <div id="unified-creating" class="hidden flex flex-col items-center justify-center py-12">',
            '    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mb-6">',
            '      <svg class="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">',
            '        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
            '        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
            '      </svg>',
            '    </div>',
            '    <p class="text-lg font-medium text-violet-600 dark:text-violet-400">Creating Your Plan</p>',
            '    <p class="text-sm text-tertiary dark:text-tertiary mt-2">Setting everything up...</p>',
            '  </div>',

            // Success state
            '  <div id="unified-success" class="hidden flex flex-col items-center justify-center py-12">',
            '    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center mb-6 animate-checkmark">',
            '      <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path>',
            '      </svg>',
            '    </div>',
            '    <p class="text-lg font-medium text-green-600 dark:text-green-400">Plan Created Successfully!</p>',
            '    <p class="text-sm text-tertiary dark:text-tertiary mt-2">Redirecting to your plan...</p>',
            '  </div>',

            // Error state
            '  <div id="unified-error" class="hidden flex flex-col items-center justify-center py-12">',
            '    <div class="w-16 h-16 rounded-full bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center mb-6">',
            '      <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>',
            '      </svg>',
            '    </div>',
            '    <p class="text-lg font-medium text-red-600 dark:text-red-400">Creation Failed</p>',
            '    <p id="unified-error-message" class="text-sm text-tertiary dark:text-tertiary mt-2">An error occurred while creating your plan.</p>',
            '    <button id="unified-retry-btn" type="button" class="mt-6 btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white">',
            '      Try Again',
            '    </button>',
            '  </div>',

            '</div>',

            // Footer with actions
            '<div id="unified-footer-actions" class="hidden px-6 py-4 border-t border-primary/10 dark:border-primary/10 bg-tertiary/30 dark:bg-tertiary/30">',
            '  <div class="flex items-center justify-end gap-3">',
            '    <button id="unified-keep-original-btn" type="button" class="hidden btn btn-secondary btn-modern">',
            '      Keep Original',
            '    </button>',
            '    <button id="unified-edit-btn" type="button" class="btn btn-secondary btn-modern">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '      </svg>',
            '      Edit',
            '    </button>',
            '    <button id="unified-use-improved-btn" type="button" class="hidden btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-violet-500/25">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '      </svg>',
            '      Use Improved',
            '    </button>',
            '    <button id="unified-create-btn" type="button" class="btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-violet-500/25">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>',
            '      </svg>',
            '      Create Plan',
            '    </button>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    function buildReviewContentHTML(draftText) {
        var escapedDraft = escapeHtml(draftText);

        return [
            '<div class="grid grid-cols-1 md:grid-cols-2 gap-6">',

            // Original draft (left)
            '  <div class="space-y-2">',
            '    <div class="flex items-center text-sm font-medium text-tertiary dark:text-tertiary">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '      </svg>',
            '      YOUR DRAFT',
            '    </div>',
            '    <div class="glass rounded-xl p-4 min-h-[200px] max-h-[300px] overflow-y-auto bg-tertiary/30 dark:bg-tertiary/30">',
            '      <p class="text-sm text-secondary dark:text-secondary font-mono whitespace-pre-wrap opacity-75">' + nl2br(escapedDraft) + '</p>',
            '    </div>',
            '  </div>',

            // Improved version (right)
            '  <div class="space-y-2">',
            '    <div class="flex items-center text-sm font-medium text-violet-600 dark:text-violet-400">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '      </svg>',
            '      AI IMPROVED',
            '    </div>',
            '    <div class="glass rounded-xl p-4 min-h-[200px] max-h-[300px] overflow-y-auto border-2 border-violet-400 dark:border-violet-600 bg-gradient-to-br from-violet-50/50 to-purple-50/50 dark:from-violet-950/30 dark:to-purple-950/30">',
            '      <p id="unified-improved-text" class="text-sm text-primary dark:text-primary font-mono whitespace-pre-wrap"></p>',
            '    </div>',
            '  </div>',

            '</div>'
        ].join('\n');
    }

    function buildEditModeHTML(currentText) {
        return [
            '<div class="space-y-4">',
            '  <div class="flex items-center text-sm font-medium text-violet-600 dark:text-violet-400">',
            '    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '    </svg>',
            '    EDIT YOUR REQUEST',
            '  </div>',
            '  <textarea id="unified-edit-textarea" class="w-full h-64 p-4 font-mono text-sm rounded-xl border-2 border-violet-400 dark:border-violet-600 bg-tertiary/30 dark:bg-tertiary/30 text-primary dark:text-primary focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none">' + escapeHtml(currentText) + '</textarea>',
            '  <div class="flex justify-end gap-3">',
            '    <button id="unified-cancel-edit-btn" type="button" class="btn btn-secondary btn-modern">',
            '      Cancel',
            '    </button>',
            '    <button id="unified-save-edit-btn" type="button" class="btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-violet-500/25">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>',
            '      </svg>',
            '      Create Plan',
            '    </button>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        showCreatePlanDialog: showCreatePlanDialog
    };

})();

// Expose globally for use in other modules
if (typeof window !== 'undefined') {
    window.UnifiedPlanDialog = UnifiedPlanDialog;
}

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UnifiedPlanDialog;
}
