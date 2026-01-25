/**
 * Request Improver Dialog Module
 *
 * Provides an AI-powered dialog for improving draft feature requests.
 * Features side-by-side comparison with typewriter effect for improved text.
 *
 * Usage:
 *   const result = await RequestImproverDialog.showImproveDialog(draftText);
 *   if (result.accepted) {
 *       // Use result.text (improved or original based on user choice)
 *   }
 */

const RequestImproverDialog = (function() {
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
                    // Handle HTML entities
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
                        // Handle <br> tags
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

    // =========================================================================
    // Main Dialog Function
    // =========================================================================

    /**
     * Show the AI improvement dialog
     *
     * @param {string} draftText - The original draft text to improve
     * @returns {Promise<{accepted: boolean, text: string, wasImproved: boolean}>}
     */
    function showImproveDialog(draftText) {
        return new Promise(function(resolve) {
            // Create overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 z-50 flex items-center justify-center p-4';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
            overlay.style.backdropFilter = 'blur(4px)';

            // Create dialog
            var dialog = document.createElement('div');
            dialog.className = 'glass-card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col';
            dialog.style.animation = 'fadeInUp 0.3s ease-out';

            // State
            var improvedText = '';
            var isLoading = true;
            var hasError = false;
            var escShortcutId = null;

            // Notify keyboard shortcuts module that a modal is open
            if (typeof KeyboardShortcuts !== 'undefined') {
                KeyboardShortcuts.modalOpened();
            }

            // Build dialog HTML
            dialog.innerHTML = buildDialogHTML(draftText);

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            // Add keyframes if not present
            if (!document.getElementById('request-improver-keyframes')) {
                var style = document.createElement('style');
                style.id = 'request-improver-keyframes';
                style.textContent = [
                    '@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }',
                    '@keyframes pulse-glow { 0%, 100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.3); } 50% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.6); } }',
                    '@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }',
                    '.animate-pulse-glow { animation: pulse-glow 2s infinite; }',
                    '.animate-shimmer { background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); background-size: 200% 100%; animation: shimmer 1.5s infinite; }'
                ].join('\n');
                document.head.appendChild(style);
            }

            // Get elements
            var closeBtn = dialog.querySelector('#improve-close-btn');
            var keepOriginalBtn = dialog.querySelector('#keep-original-btn');
            var editBtn = dialog.querySelector('#edit-btn');
            var useImprovedBtn = dialog.querySelector('#use-improved-btn');
            var loadingEl = dialog.querySelector('#improve-loading');
            var resultEl = dialog.querySelector('#improve-result');
            var improvedTextEl = dialog.querySelector('#improved-text');
            var errorEl = dialog.querySelector('#improve-error');

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

            // Event handlers
            closeBtn.addEventListener('click', function() {
                close({ accepted: false, text: draftText, wasImproved: false });
            });

            keepOriginalBtn.addEventListener('click', function() {
                close({ accepted: true, text: draftText, wasImproved: false });
            });

            editBtn.addEventListener('click', function() {
                // Copy improved text to clipboard and close
                if (improvedText) {
                    navigator.clipboard.writeText(improvedText).catch(function() {});
                }
                close({ accepted: true, text: improvedText || draftText, wasImproved: true, needsEdit: true });
            });

            useImprovedBtn.addEventListener('click', function() {
                close({ accepted: true, text: improvedText || draftText, wasImproved: true });
            });

            // Handle escape key using centralized keyboard shortcuts
            if (typeof KeyboardShortcuts !== 'undefined') {
                escShortcutId = KeyboardShortcuts.registerShortcut('esc', function(e) {
                    close({ accepted: false, text: draftText, wasImproved: false });
                    return true; // Prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);
            } else {
                // Fallback for when KeyboardShortcuts is not available
                document.addEventListener('keydown', function handleKeydown(e) {
                    if (e.key === 'Escape') {
                        document.removeEventListener('keydown', handleKeydown);
                        close({ accepted: false, text: draftText, wasImproved: false });
                    }
                });
            }

            // Click outside to close
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    close({ accepted: false, text: draftText, wasImproved: false });
                }
            });

            // Call API to improve
            fetch('/api/workflows/improve-request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft: draftText })
            })
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                isLoading = false;
                loadingEl.classList.add('hidden');

                if (data.success && data.improved && data.improved !== draftText) {
                    improvedText = data.improved;
                    resultEl.classList.remove('hidden');

                    // Typewriter effect
                    typewriterEffect(improvedTextEl, improvedText, 10).then(function() {
                        useImprovedBtn.focus();
                    });
                } else {
                    // No improvement or same as original
                    hasError = true;
                    errorEl.classList.remove('hidden');
                    errorEl.querySelector('p').textContent = 'Your request is already well-formed. You can proceed with the original.';
                    keepOriginalBtn.focus();
                }
            })
            .catch(function(err) {
                console.error('Improvement failed:', err);
                isLoading = false;
                hasError = true;
                loadingEl.classList.add('hidden');
                errorEl.classList.remove('hidden');
                keepOriginalBtn.focus();
            });
        });
    }

    function buildDialogHTML(draftText) {
        var escapedDraft = escapeHtml(draftText);

        return [
            // Header with gradient
            '<div class="relative px-6 py-4 border-b border-primary/10">',
            '  <div class="absolute inset-0 bg-gradient-to-r from-violet-500/10 via-purple-500/10 to-indigo-500/10"></div>',
            '  <div class="relative flex items-center justify-between">',
            '    <div class="flex items-center">',
            '      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mr-3 shadow-lg animate-pulse-glow">',
            '        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '        </svg>',
            '      </div>',
            '      <div>',
            '        <h2 class="text-xl font-bold text-gradient-primary">AI Request Improvement</h2>',
            '        <p class="text-xs text-tertiary">Enhancing your request with AI</p>',
            '      </div>',
            '    </div>',
            '    <button id="improve-close-btn" type="button" class="p-2 text-tertiary hover:text-primary transition-colors rounded-lg hover:bg-tertiary/50">',
            '      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>',
            '      </svg>',
            '    </button>',
            '  </div>',
            '</div>',

            // Content area
            '<div class="flex-1 overflow-y-auto p-6">',
            '  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">',

            // Original draft (left)
            '    <div class="space-y-2">',
            '      <div class="flex items-center text-sm font-medium text-tertiary">',
            '        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '        </svg>',
            '        YOUR DRAFT',
            '      </div>',
            '      <div class="glass rounded-xl p-4 min-h-[200px] max-h-[300px] overflow-y-auto bg-tertiary/30">',
            '        <p class="text-sm text-secondary font-mono whitespace-pre-wrap opacity-75">' + nl2br(escapedDraft) + '</p>',
            '      </div>',
            '    </div>',

            // Arrow separator (visible on md+)
            '    <div class="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10">',
            '      <div class="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">',
            '        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>',
            '        </svg>',
            '      </div>',
            '    </div>',

            // Improved version (right)
            '    <div class="space-y-2">',
            '      <div class="flex items-center text-sm font-medium text-violet-600">',
            '        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '        </svg>',
            '        IMPROVED VERSION',
            '      </div>',

            // Loading state
            '      <div id="improve-loading" class="glass rounded-xl p-4 min-h-[200px] border-2 border-dashed border-violet-300 flex flex-col items-center justify-center">',
            '        <div class="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mb-4 animate-pulse">',
            '          <svg class="w-6 h-6 text-white animate-spin" fill="none" viewBox="0 0 24 24">',
            '            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>',
            '            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>',
            '          </svg>',
            '        </div>',
            '        <p class="text-sm font-medium text-violet-600">Enhancing your request...</p>',
            '        <p class="text-xs text-tertiary mt-1">AI is analyzing and improving</p>',
            '      </div>',

            // Result state
            '      <div id="improve-result" class="hidden glass rounded-xl p-4 min-h-[200px] max-h-[300px] overflow-y-auto border-2 border-violet-400 bg-gradient-to-br from-violet-50/50 to-purple-50/50">',
            '        <p id="improved-text" class="text-sm text-primary font-mono whitespace-pre-wrap"></p>',
            '      </div>',

            // Error state
            '      <div id="improve-error" class="hidden glass rounded-xl p-4 min-h-[200px] border-2 border-amber-300 flex flex-col items-center justify-center bg-amber-50/50">',
            '        <svg class="w-10 h-10 text-amber-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
            '        </svg>',
            '        <p class="text-sm text-amber-700 text-center">Could not improve the request at this time.</p>',
            '      </div>',

            '    </div>',
            '  </div>',
            '</div>',

            // Footer with actions
            '<div class="px-6 py-4 border-t border-primary/10 bg-tertiary/30">',
            '  <div class="flex items-center justify-end gap-3">',
            '    <button id="keep-original-btn" type="button" class="btn btn-secondary btn-modern">',
            '      Keep Original',
            '    </button>',
            '    <button id="edit-btn" type="button" class="btn btn-secondary btn-modern">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>',
            '      </svg>',
            '      Edit',
            '    </button>',
            '    <button id="use-improved-btn" type="button" class="btn btn-modern bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-violet-500/25">',
            '      <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">',
            '        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"></path>',
            '      </svg>',
            '      Use Improved',
            '    </button>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        showImproveDialog: showImproveDialog
    };

})();
