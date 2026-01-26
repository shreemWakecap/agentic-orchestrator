/**
 * Plan Manager Module
 *
 * Handles plan lifecycle management including:
 * - Starting builds from pending plans
 * - Deleting plans with confirmation
 * - Moving plans between states
 * - Refreshing the plan list
 *
 * Dependencies:
 * - OrchestratorUtils (from common.js) for utilities
 * - Toast (from toast.js) for notifications (optional)
 *
 * DOM Requirements:
 * - .plan-item elements with data-plan-id attributes
 * - Plan list container for refreshing
 */

const PlanManager = (function() {
    'use strict';

    // API base URL
    const API_BASE = '/api/plans';

    // Valid plan states for transitions
    const PLAN_STATES = {
        PENDING: 'pending',
        BUILDING: 'building',
        RUNNING: 'running',
        COMPLETED: 'completed',
        FAILED: 'failed',
        CANCELLED: 'cancelled'
    };

    // Currently selected plan ID
    let selectedPlanId = null;

    // Keyboard shortcuts enabled flag
    let keyboardShortcutsEnabled = false;

    // Store shortcut IDs for unregistration
    let registeredShortcutIds = [];

    // =========================================================================
    // Private Helpers
    // =========================================================================

    /**
     * Show a notification message
     * @param {string} message - Message to display
     * @param {string} type - Message type: 'success', 'error', 'info'
     */
    function showNotification(message, type) {
        // Use Toast if available, otherwise fall back to alert
        if (typeof Toast !== 'undefined' && Toast.show) {
            Toast.show(message, type);
        } else if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.dispatchCustomEvent) {
            OrchestratorUtils.dispatchCustomEvent('planManager', 'notification', {
                message: message,
                type: type
            });
        } else {
            if (type === 'error') {
                console.error(message);
            } else {
                console.log(message);
            }
        }
    }

    /**
     * Make an API request with error handling
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async function apiRequest(url, options) {
        options = options || {};
        options.headers = options.headers || {};
        options.headers['Content-Type'] = 'application/json';

        try {
            var response = await fetch(url, options);
            var data;

            // Try to parse JSON response
            try {
                data = await response.json();
            } catch (e) {
                data = { message: await response.text() };
            }

            if (!response.ok) {
                throw new Error(data.error || data.message || 'Request failed with status ' + response.status);
            }

            return data;
        } catch (error) {
            console.error('API request failed:', url, error);
            throw error;
        }
    }

    /**
     * Update UI element state during operations
     * @param {HTMLElement} element - Button or element to update
     * @param {boolean} loading - Whether operation is in progress
     * @param {string} [originalText] - Original button text to restore
     */
    function setLoadingState(element, loading, originalText) {
        if (!element) return;

        if (loading) {
            element.disabled = true;
            element.dataset.originalText = element.textContent;
            element.textContent = 'Loading...';
            element.classList.add('opacity-50', 'cursor-wait');
        } else {
            element.disabled = false;
            element.textContent = originalText || element.dataset.originalText || element.textContent;
            element.classList.remove('opacity-50', 'cursor-wait');
        }
    }

    // =========================================================================
    // Confirm Dialog
    // =========================================================================

    /**
     * Show a confirmation dialog
     * @param {Object} options - Dialog options
     * @param {string} options.title - Dialog title
     * @param {string} options.message - Dialog message
     * @param {string} [options.confirmText='Confirm'] - Confirm button text
     * @param {string} [options.cancelText='Cancel'] - Cancel button text
     * @param {string} [options.confirmClass='bg-red-600'] - Confirm button CSS class
     * @returns {Promise<boolean>} Resolves to true if confirmed, false if cancelled
     */
    function showConfirmDialog(options) {
        return new Promise(function(resolve) {
            options = options || {};
            var title = options.title || 'Confirm Action';
            var message = options.message || 'Are you sure you want to proceed?';
            var confirmText = options.confirmText || 'Confirm';
            var cancelText = options.cancelText || 'Cancel';
            var confirmClass = options.confirmClass || 'bg-red-600 hover:bg-red-700';

            // Create modal overlay
            var overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            overlay.id = 'confirm-dialog-overlay';

            // Create modal content
            var escapeHtml = typeof OrchestratorUtils !== 'undefined'
                ? OrchestratorUtils.escapeHtml
                : function(t) { return t; };

            overlay.innerHTML =
                '<div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">' +
                    '<div class="px-6 py-4 border-b border-gray-200">' +
                        '<h3 class="text-lg font-semibold text-gray-900">' + escapeHtml(title) + '</h3>' +
                    '</div>' +
                    '<div class="px-6 py-4">' +
                        '<p class="text-gray-700">' + escapeHtml(message) + '</p>' +
                    '</div>' +
                    '<div class="px-6 py-4 bg-gray-50 flex justify-end space-x-3">' +
                        '<button id="confirm-dialog-cancel" class="px-4 py-2 text-gray-700 bg-gray-200 rounded hover:bg-gray-300 transition-colors">' +
                            escapeHtml(cancelText) +
                        '</button>' +
                        '<button id="confirm-dialog-confirm" class="px-4 py-2 text-white rounded transition-colors ' + confirmClass + '">' +
                            escapeHtml(confirmText) +
                        '</button>' +
                    '</div>' +
                '</div>';

            document.body.appendChild(overlay);

            // Handle button clicks
            var confirmBtn = document.getElementById('confirm-dialog-confirm');
            var cancelBtn = document.getElementById('confirm-dialog-cancel');

            // Track registered shortcut IDs for cleanup
            var escShortcutId = null;
            var resolved = false;

            // Notify KeyboardShortcuts that a modal is open (enables MODAL priority handlers)
            if (typeof KeyboardShortcuts !== 'undefined') {
                KeyboardShortcuts.modalOpened();
            }

            function cleanup() {
                // Unregister ESC shortcut if using centralized module
                if (escShortcutId && typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.unregisterShortcut(escShortcutId);
                    escShortcutId = null;
                }
                // Notify KeyboardShortcuts that modal is closed
                if (typeof KeyboardShortcuts !== 'undefined') {
                    KeyboardShortcuts.modalClosed();
                }
                overlay.remove();
            }

            function resolveDialog(result) {
                if (resolved) return;
                resolved = true;
                cleanup();
                resolve(result);
            }

            confirmBtn.addEventListener('click', function() {
                resolveDialog(true);
            });

            cancelBtn.addEventListener('click', function() {
                resolveDialog(false);
            });

            // Handle overlay click (cancel)
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    resolveDialog(false);
                }
            });

            // Handle escape key using centralized KeyboardShortcuts module
            if (typeof KeyboardShortcuts !== 'undefined') {
                escShortcutId = KeyboardShortcuts.registerShortcut('esc', function(e) {
                    resolveDialog(false);
                    return true; // Prevent default and stop propagation
                }, KeyboardShortcuts.PRIORITY.MODAL);
            } else {
                // Fallback for when KeyboardShortcuts module is not available
                function handleEscape(e) {
                    if (e.key === 'Escape') {
                        document.removeEventListener('keydown', handleEscape);
                        resolveDialog(false);
                    }
                }
                document.addEventListener('keydown', handleEscape);
            }

            // Focus confirm button
            confirmBtn.focus();
        });
    }

    // =========================================================================
    // Plan Operations
    // =========================================================================

    /**
     * Start building a plan
     * @param {string} planId - The plan identifier
     * @param {HTMLElement} [buttonElement] - Optional button element for loading state
     * @returns {Promise<Object>} API response
     */
    async function startBuild(planId, buttonElement) {
        if (!planId) {
            showNotification('No plan ID provided', 'error');
            return null;
        }

        setLoadingState(buttonElement, true);

        try {
            var result = await apiRequest(API_BASE + '/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST'
            });

            showNotification('Build started for plan: ' + planId, 'success');

            // Dispatch event for other modules to listen
            if (typeof OrchestratorUtils !== 'undefined') {
                OrchestratorUtils.dispatchCustomEvent('planManager', 'buildStarted', {
                    planId: planId,
                    result: result
                });
            }

            // Refresh the plan list to show updated status
            await refreshPlanList();

            return result;
        } catch (error) {
            showNotification('Failed to start build: ' + error.message, 'error');
            return null;
        } finally {
            setLoadingState(buttonElement, false);
        }
    }

    /**
     * Delete a plan with confirmation
     * @param {string} planId - The plan identifier
     * @param {HTMLElement} [buttonElement] - Optional button element for loading state
     * @returns {Promise<boolean>} True if deleted, false if cancelled or failed
     */
    async function deletePlan(planId, buttonElement) {
        if (!planId) {
            showNotification('No plan ID provided', 'error');
            return false;
        }

        // Fetch plan state first to determine confirmation dialog type
        var planState = null;
        try {
            var planData = await apiRequest(API_BASE + '/' + encodeURIComponent(planId), {
                method: 'GET'
            });
            planState = planData.state || planData.status || null;
        } catch (error) {
            // If we can't fetch the plan state, proceed with standard confirmation
            console.warn('Could not fetch plan state, proceeding with standard confirmation:', error.message);
        }

        // Check if plan is in an active state
        var isActivePlan = planState && PlanDeleteDialog &&
            PlanDeleteDialog.ACTIVE_STATES &&
            PlanDeleteDialog.ACTIVE_STATES.includes(planState.toLowerCase().trim());

        // Show enhanced confirmation dialog using PlanDeleteDialog if available
        var confirmed = false;
        if (typeof PlanDeleteDialog !== 'undefined' && PlanDeleteDialog.showDeleteConfirmation) {
            confirmed = await PlanDeleteDialog.showDeleteConfirmation(planId, planState);
        } else {
            // Fallback to basic confirm dialog if PlanDeleteDialog is not available
            confirmed = await showConfirmDialog({
                title: 'Delete Plan',
                message: 'Are you sure you want to delete plan "' + planId + '"? This action cannot be undone.',
                confirmText: 'Delete',
                cancelText: 'Cancel',
                confirmClass: 'bg-red-600 hover:bg-red-700'
            });
        }

        if (!confirmed) {
            return false;
        }

        setLoadingState(buttonElement, true);

        try {
            // Build delete URL with force param for active plans
            var deleteUrl = API_BASE + '/' + encodeURIComponent(planId);
            if (isActivePlan) {
                deleteUrl += '?force=true';
            }

            await apiRequest(deleteUrl, {
                method: 'DELETE'
            });

            showNotification('Plan deleted: ' + planId, 'success');

            // Dispatch event for other modules to listen
            if (typeof OrchestratorUtils !== 'undefined') {
                OrchestratorUtils.dispatchCustomEvent('planManager', 'planDeleted', {
                    planId: planId
                });
            }

            // Refresh the plan list
            await refreshPlanList();

            return true;
        } catch (error) {
            showNotification('Failed to delete plan: ' + error.message, 'error');
            return false;
        } finally {
            setLoadingState(buttonElement, false);
        }
    }

    /**
     * Move a plan to a different state
     * @param {string} planId - The plan identifier
     * @param {string} targetState - Target state (pending, building, running, completed, failed, cancelled)
     * @param {HTMLElement} [buttonElement] - Optional button element for loading state
     * @returns {Promise<Object>} API response or null on failure
     */
    async function movePlan(planId, targetState, buttonElement) {
        if (!planId) {
            showNotification('No plan ID provided', 'error');
            return null;
        }

        // Validate target state
        var validStates = Object.values(PLAN_STATES);
        if (!validStates.includes(targetState)) {
            showNotification('Invalid target state: ' + targetState, 'error');
            return null;
        }

        setLoadingState(buttonElement, true);

        try {
            var result = await apiRequest(API_BASE + '/' + encodeURIComponent(planId) + '/move', {
                method: 'PUT',
                body: JSON.stringify({ target_state: targetState })
            });

            showNotification('Plan moved to ' + targetState + ': ' + planId, 'success');

            // Dispatch event for other modules to listen
            if (typeof OrchestratorUtils !== 'undefined') {
                OrchestratorUtils.dispatchCustomEvent('planManager', 'planMoved', {
                    planId: planId,
                    targetState: targetState,
                    result: result
                });
            }

            // Refresh the plan list to show updated status
            await refreshPlanList();

            return result;
        } catch (error) {
            showNotification('Failed to move plan: ' + error.message, 'error');
            return null;
        } finally {
            setLoadingState(buttonElement, false);
        }
    }

    /**
     * Refresh the plan list by reloading the current page or fetching updated data
     * @returns {Promise<void>}
     */
    async function refreshPlanList() {
        try {
            // Check if there's a plan list container to update via AJAX
            var planListContainer = document.getElementById('plan-list-container');

            if (planListContainer) {
                // Fetch updated plan list HTML
                var response = await fetch('/api/plans/list-partial');

                if (response.ok) {
                    var html = await response.text();
                    planListContainer.innerHTML = html;

                    // Dispatch event for other modules to reinitialize if needed
                    if (typeof OrchestratorUtils !== 'undefined') {
                        OrchestratorUtils.dispatchCustomEvent('planManager', 'listRefreshed', {});
                    }

                    // Reset PlanList expanded state if available
                    if (typeof PlanList !== 'undefined' && PlanList.reset) {
                        PlanList.reset();
                    }
                } else {
                    // Fall back to page reload
                    window.location.reload();
                }
            } else {
                // No AJAX container, reload the page
                window.location.reload();
            }
        } catch (error) {
            console.error('Failed to refresh plan list:', error);
            // Fall back to page reload on error
            window.location.reload();
        }
    }

    /**
     * Get the valid plan states
     * @returns {Object} Object with state constants
     */
    function getStates() {
        return Object.assign({}, PLAN_STATES);
    }

    // =========================================================================
    // Plan Selection
    // =========================================================================

    /**
     * Select a plan by ID
     * @param {string} planId - The plan identifier to select
     */
    function selectPlan(planId) {
        // Deselect previously selected plan
        if (selectedPlanId) {
            var prevSelected = document.querySelector('.plan-item[data-plan-id="' + selectedPlanId + '"]');
            if (prevSelected) {
                prevSelected.classList.remove('plan-selected', 'ring-2', 'ring-blue-500', 'ring-offset-2');
            }
        }

        selectedPlanId = planId;

        // Highlight newly selected plan
        if (planId) {
            var planItem = document.querySelector('.plan-item[data-plan-id="' + planId + '"]');
            if (planItem) {
                planItem.classList.add('plan-selected', 'ring-2', 'ring-blue-500', 'ring-offset-2');
                // Scroll into view if needed
                planItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        // Dispatch event
        if (typeof OrchestratorUtils !== 'undefined') {
            OrchestratorUtils.dispatchCustomEvent('planManager', 'planSelected', {
                planId: planId
            });
        }
    }

    /**
     * Get the currently selected plan ID
     * @returns {string|null} The selected plan ID or null
     */
    function getSelectedPlanId() {
        return selectedPlanId;
    }

    /**
     * Get the state of the currently selected plan
     * @returns {string|null} The plan state or null if no plan selected
     */
    function getSelectedPlanState() {
        if (!selectedPlanId) return null;
        var planItem = document.querySelector('.plan-item[data-plan-id="' + selectedPlanId + '"]');
        if (!planItem) return null;
        var badge = planItem.querySelector('.rounded-full');
        if (badge) {
            return badge.textContent.trim().toLowerCase();
        }
        return null;
    }

    /**
     * Clear the current selection
     */
    function clearSelection() {
        selectPlan(null);
    }

    // =========================================================================
    // Keyboard Shortcuts
    // =========================================================================

    /**
     * Create and inject keyboard shortcuts hint UI
     */
    function createShortcutHints() {
        // Check if hints already exist
        if (document.getElementById('keyboard-shortcuts-hint')) {
            return;
        }

        // Add CSS for shortcut hint states if not already present
        if (!document.getElementById('shortcut-hint-styles')) {
            var style = document.createElement('style');
            style.id = 'shortcut-hint-styles';
            style.textContent = [
                '.shortcut-hint-active { background-color: rgba(59, 130, 246, 0.3) !important; }',
                '.shortcut-status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; transition: background-color 0.2s ease; }',
                '.shortcut-status-active { background-color: #10b981; box-shadow: 0 0 4px #10b981; }',
                '.shortcut-status-inactive { background-color: #6b7280; }',
                '@keyframes shortcut-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }',
                '.shortcut-hint-triggered { animation: shortcut-pulse 0.3s ease-out; background-color: rgba(16, 185, 129, 0.3) !important; }'
            ].join('\n');
            document.head.appendChild(style);
        }

        var hintsHtml =
            '<div id="keyboard-shortcuts-hint" class="fixed bottom-4 right-4 bg-gray-800 text-white text-xs rounded-lg shadow-lg p-3 opacity-80 hover:opacity-100 transition-opacity z-40">' +
                '<div class="flex items-center justify-between mb-2">' +
                    '<span class="font-semibold text-gray-300">Keyboard Shortcuts</span>' +
                    '<span id="shortcuts-status-label" class="text-[10px] text-green-400 ml-2">Active</span>' +
                '</div>' +
                '<div class="space-y-1">' +
                    '<div id="shortcut-hint-select" class="flex items-center justify-between gap-4 px-1 py-0.5 rounded transition-colors duration-150">' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="shortcut-status-dot shortcut-status-active" data-shortcut-key="arrows"></span>' +
                            '<span class="text-gray-400">Select plan</span>' +
                        '</div>' +
                        '<span><kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">Click</kbd> / <kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">↑</kbd><kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">↓</kbd></span>' +
                    '</div>' +
                    '<div id="shortcut-hint-build" class="flex items-center justify-between gap-4 px-1 py-0.5 rounded transition-colors duration-150">' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="shortcut-status-dot shortcut-status-active" data-shortcut-key="b"></span>' +
                            '<span class="text-gray-400">Start build</span>' +
                        '</div>' +
                        '<kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">B</kbd>' +
                    '</div>' +
                    '<div id="shortcut-hint-delete" class="flex items-center justify-between gap-4 px-1 py-0.5 rounded transition-colors duration-150">' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="shortcut-status-dot shortcut-status-active" data-shortcut-key="d"></span>' +
                            '<span class="text-gray-400">Delete plan</span>' +
                        '</div>' +
                        '<kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">D</kbd>' +
                    '</div>' +
                    '<div id="shortcut-hint-refresh" class="flex items-center justify-between gap-4 px-1 py-0.5 rounded transition-colors duration-150">' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="shortcut-status-dot shortcut-status-active" data-shortcut-key="r"></span>' +
                            '<span class="text-gray-400">Refresh list</span>' +
                        '</div>' +
                        '<kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">R</kbd>' +
                    '</div>' +
                    '<div id="shortcut-hint-escape" class="flex items-center justify-between gap-4 px-1 py-0.5 rounded transition-colors duration-150">' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="shortcut-status-dot shortcut-status-active" data-shortcut-key="esc"></span>' +
                            '<span class="text-gray-400">Clear selection</span>' +
                        '</div>' +
                        '<kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-200">Esc</kbd>' +
                    '</div>' +
                '</div>' +
            '</div>';

        var hintsContainer = document.createElement('div');
        hintsContainer.innerHTML = hintsHtml;
        document.body.appendChild(hintsContainer.firstChild);

        // Update status indicators based on actual shortcut registration
        updateShortcutStatusIndicators();
    }

    /**
     * Update the status indicators for all shortcut hints
     * Shows green dot if shortcut is registered and active, gray if not
     */
    function updateShortcutStatusIndicators() {
        if (typeof KeyboardShortcuts === 'undefined') return;

        var shortcuts = KeyboardShortcuts.getRegisteredShortcuts();
        var statusLabel = document.getElementById('shortcuts-status-label');

        // Check each shortcut key
        var keys = ['b', 'd', 'r', 'esc', 'up', 'down'];
        var activeCount = 0;

        keys.forEach(function(key) {
            var dot = document.querySelector('.shortcut-status-dot[data-shortcut-key="' + key + '"]');
            if (!dot && (key === 'up' || key === 'down')) {
                // Arrow keys share the "arrows" indicator
                dot = document.querySelector('.shortcut-status-dot[data-shortcut-key="arrows"]');
            }
            if (!dot) return;

            var isRegistered = KeyboardShortcuts.hasShortcut(key);
            if (isRegistered) {
                activeCount++;
                dot.classList.remove('shortcut-status-inactive');
                dot.classList.add('shortcut-status-active');
            } else {
                dot.classList.remove('shortcut-status-active');
                dot.classList.add('shortcut-status-inactive');
            }
        });

        // Update overall status label
        if (statusLabel) {
            if (activeCount > 0) {
                statusLabel.textContent = 'Active';
                statusLabel.className = 'text-[10px] text-green-400 ml-2';
            } else {
                statusLabel.textContent = 'Inactive';
                statusLabel.className = 'text-[10px] text-gray-500 ml-2';
            }
        }
    }

    /**
     * Highlight a shortcut hint row when the shortcut is triggered
     * @param {string} shortcutName - The shortcut name (select, build, delete, refresh, escape)
     */
    function highlightShortcutHint(shortcutName) {
        var hintElement = document.getElementById('shortcut-hint-' + shortcutName);
        if (!hintElement) return;

        // Remove any existing animation classes first
        hintElement.classList.remove('shortcut-hint-active', 'shortcut-hint-triggered');

        // Force reflow to restart animation
        void hintElement.offsetWidth;

        // Add triggered class for highlight effect with animation
        hintElement.classList.add('shortcut-hint-triggered');

        // Remove the class after animation completes
        setTimeout(function() {
            hintElement.classList.remove('shortcut-hint-triggered');
        }, 300);
    }

    /**
     * Remove keyboard shortcuts hint UI
     */
    function removeShortcutHints() {
        var hints = document.getElementById('keyboard-shortcuts-hint');
        if (hints) {
            hints.remove();
        }
    }

    /**
     * Handle keyboard events for shortcuts
     * @param {KeyboardEvent} event - The keyboard event
     */
    function handleKeyboardShortcut(event) {
        console.log('[PlanManager] Keyboard event received:', {
            key: event.key,
            code: event.code,
            target: event.target.tagName,
            ctrlKey: event.ctrlKey,
            metaKey: event.metaKey,
            altKey: event.altKey,
            shiftKey: event.shiftKey
        });

        // Ignore if typing in an input/textarea or if modifiers are pressed
        if (event.target.tagName === 'INPUT' ||
            event.target.tagName === 'TEXTAREA' ||
            event.target.isContentEditable ||
            event.ctrlKey || event.metaKey || event.altKey) {
            console.log('[PlanManager] Shortcut ignored - reason:', {
                isInput: event.target.tagName === 'INPUT',
                isTextarea: event.target.tagName === 'TEXTAREA',
                isContentEditable: event.target.isContentEditable,
                hasCtrl: event.ctrlKey,
                hasMeta: event.metaKey,
                hasAlt: event.altKey
            });
            return;
        }

        // Check if a modal/dialog is open
        if (document.getElementById('confirm-dialog-overlay')) {
            console.log('[PlanManager] Shortcut ignored - dialog is open');
            return;
        }

        var key = event.key.toLowerCase();
        console.log('Shortcut key pressed:', key);

        switch (key) {
            case 'b':
                // Start build on selected plan (if pending)
                console.log('[PlanManager] Shortcut matched: B (Start Build)', { selectedPlanId: selectedPlanId });
                highlightShortcutHint('build');
                if (selectedPlanId) {
                    var state = getSelectedPlanState();
                    console.log('[PlanManager] Selected plan state:', state);
                    if (state === 'pending') {
                        event.preventDefault();
                        event.stopPropagation();
                        event.stopImmediatePropagation();
                        console.log('[PlanManager] Executing startBuild for plan:', selectedPlanId);
                        // Trigger startBuild with the selected plan
                        if (typeof window.startBuild === 'function') {
                            window.startBuild(selectedPlanId, null);
                        } else {
                            startBuild(selectedPlanId);
                        }
                    } else {
                        showNotification('Cannot start build: plan is not in pending state', 'error');
                    }
                } else {
                    showNotification('Select a plan first (click on a plan)', 'info');
                }
                break;

            case 'd':
                // Delete selected plan
                console.log('[PlanManager] Shortcut matched: D (Delete Plan)', { selectedPlanId: selectedPlanId });
                highlightShortcutHint('delete');
                if (selectedPlanId) {
                    event.preventDefault();
                    event.stopPropagation();
                    event.stopImmediatePropagation();
                    console.log('[PlanManager] Executing deletePlan for plan:', selectedPlanId);
                    // Trigger deletePlan with the selected plan
                    if (typeof window.deletePlan === 'function') {
                        window.deletePlan(selectedPlanId, null);
                    } else {
                        deletePlan(selectedPlanId);
                    }
                } else {
                    showNotification('Select a plan first (click on a plan)', 'info');
                }
                break;

            case 'r':
                // Refresh plan list
                console.log('[PlanManager] Shortcut matched: R (Refresh List)');
                highlightShortcutHint('refresh');
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                showNotification('Refreshing plan list...', 'info');
                refreshPlanList();
                break;

            case 'escape':
                // Clear selection
                console.log('[PlanManager] Shortcut matched: Escape (Clear Selection)');
                highlightShortcutHint('escape');
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                clearSelection();
                break;

            case 'arrowdown':
                // Select next plan
                console.log('[PlanManager] Shortcut matched: ArrowDown (Select Next)');
                highlightShortcutHint('select');
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                selectNextPlan(1);
                break;

            case 'arrowup':
                // Select previous plan
                console.log('[PlanManager] Shortcut matched: ArrowUp (Select Previous)');
                highlightShortcutHint('select');
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                selectNextPlan(-1);
                break;

            default:
                console.log('[PlanManager] Key not matched to any shortcut:', key);
                break;
        }
    }

    /**
     * Select the next or previous plan in the list
     * @param {number} direction - 1 for next, -1 for previous
     */
    function selectNextPlan(direction) {
        var planItems = document.querySelectorAll('.plan-item[data-plan-id]');
        if (planItems.length === 0) return;

        var currentIndex = -1;
        if (selectedPlanId) {
            for (var i = 0; i < planItems.length; i++) {
                if (planItems[i].dataset.planId === selectedPlanId) {
                    currentIndex = i;
                    break;
                }
            }
        }

        var newIndex;
        if (currentIndex === -1) {
            // No selection, select first or last based on direction
            newIndex = direction > 0 ? 0 : planItems.length - 1;
        } else {
            newIndex = currentIndex + direction;
            // Wrap around
            if (newIndex < 0) newIndex = planItems.length - 1;
            if (newIndex >= planItems.length) newIndex = 0;
        }

        selectPlan(planItems[newIndex].dataset.planId);
    }

    // Verification flag for keyboard shortcuts initialization
    let keyboardShortcutsInitialized = false;

    /**
     * Initialize keyboard shortcuts using the centralized KeyboardShortcuts module
     */
    function initKeyboardShortcuts() {
        console.log('[PlanManager] initKeyboardShortcuts called, already enabled:', keyboardShortcutsEnabled);
        if (keyboardShortcutsEnabled) return;

        // Check if KeyboardShortcuts module is available
        if (typeof KeyboardShortcuts === 'undefined') {
            console.warn('[PlanManager] KeyboardShortcuts module not available, falling back to direct listener');
            document.addEventListener('keydown', handleKeyboardShortcut);
            keyboardShortcutsEnabled = true;
            keyboardShortcutsInitialized = true;
            createShortcutHints();
            console.log('[PlanManager] Keyboard shortcuts initialized (direct listener attached)');
            return;
        }

        console.log('[PlanManager] Registering shortcuts with KeyboardShortcuts module');

        // Use PAGE priority for plan manager shortcuts
        var priority = KeyboardShortcuts.PRIORITY.PAGE;

        // Register 'b' for start build
        var id = KeyboardShortcuts.registerShortcut('b', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: B (Start Build)', { selectedPlanId: selectedPlanId });
            highlightShortcutHint('build');
            if (!selectedPlanId) {
                showNotification('Select a plan first (click on a plan)', 'info');
                return true; // Always return true to prevent default
            }
            var state = getSelectedPlanState();
            console.log('[PlanManager] Selected plan state:', state);
            if (state !== 'pending') {
                showNotification('Cannot start build: plan is not in pending state', 'error');
                return true; // Always return true to prevent default
            }
            console.log('[PlanManager] Executing startBuild for plan:', selectedPlanId);
            if (typeof window.startBuild === 'function') {
                window.startBuild(selectedPlanId, null);
            } else {
                startBuild(selectedPlanId);
            }
            return true; // Prevent default after execution
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Register 'd' for delete plan
        id = KeyboardShortcuts.registerShortcut('d', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: D (Delete Plan)', { selectedPlanId: selectedPlanId });
            highlightShortcutHint('delete');
            if (!selectedPlanId) {
                showNotification('Select a plan first (click on a plan)', 'info');
                return true; // Always return true to prevent default
            }
            console.log('[PlanManager] Executing deletePlan for plan:', selectedPlanId);
            if (typeof window.deletePlan === 'function') {
                window.deletePlan(selectedPlanId, null);
            } else {
                deletePlan(selectedPlanId);
            }
            return true; // Prevent default after execution
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Register 'r' for refresh
        id = KeyboardShortcuts.registerShortcut('r', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: R (Refresh List)');
            highlightShortcutHint('refresh');
            showNotification('Refreshing plan list...', 'info');
            refreshPlanList();
            return true;
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Register 'esc' for clear selection
        id = KeyboardShortcuts.registerShortcut('esc', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: Escape (Clear Selection)');
            highlightShortcutHint('escape');
            clearSelection();
            return true;
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Register arrow down for next plan
        id = KeyboardShortcuts.registerShortcut('down', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: ArrowDown (Select Next)');
            highlightShortcutHint('select');
            selectNextPlan(1);
            return true;
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Register arrow up for previous plan
        id = KeyboardShortcuts.registerShortcut('up', function(event) {
            console.log('[PlanManager] Shortcut triggered via KeyboardShortcuts: ArrowUp (Select Previous)');
            highlightShortcutHint('select');
            selectNextPlan(-1);
            return true;
        }, priority);
        if (id) registeredShortcutIds.push(id);

        // Add click handlers to plan items for selection
        document.querySelectorAll('.plan-item[data-plan-id]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                // Don't select if clicking on a button or link
                if (e.target.closest('button') || e.target.closest('a')) {
                    return;
                }
                selectPlan(item.dataset.planId);
            });
        });

        // Create shortcut hints UI
        createShortcutHints();

        keyboardShortcutsEnabled = true;
        keyboardShortcutsInitialized = true;

        // Update status indicators now that all shortcuts are registered
        updateShortcutStatusIndicators();

        console.log('[PlanManager] Keyboard shortcuts initialized');
        console.log('[PlanManager] Shortcuts registered:', registeredShortcutIds);
    }

    /**
     * Test keyboard shortcuts by dispatching a synthetic keydown event
     * @param {string} key - The key to simulate (e.g., 'b', 'd', 'r')
     * @returns {boolean} True if handler responded
     */
    function testKeyboardShortcut(key) {
        if (!keyboardShortcutsInitialized) {
            console.warn('[PlanManager] testKeyboardShortcut: Shortcuts not initialized');
            return false;
        }

        console.log('[PlanManager] Testing keyboard shortcut:', key);

        var event = new KeyboardEvent('keydown', {
            key: key,
            code: 'Key' + key.toUpperCase(),
            bubbles: true,
            cancelable: true
        });

        // Track if the event was handled
        var wasHandled = false;
        var originalPreventDefault = event.preventDefault;
        event.preventDefault = function() {
            wasHandled = true;
            originalPreventDefault.call(event);
        };

        document.dispatchEvent(event);

        console.log('[PlanManager] Test shortcut dispatched, handled:', wasHandled);
        return wasHandled;
    }

    /**
     * Check if keyboard shortcuts are initialized
     * @returns {boolean} True if initialized
     */
    function isKeyboardShortcutsInitialized() {
        return keyboardShortcutsInitialized;
    }

    /**
     * Disable keyboard shortcuts
     */
    function disableKeyboardShortcuts() {
        if (!keyboardShortcutsEnabled) return;

        // Unregister from KeyboardShortcuts module if available
        if (typeof KeyboardShortcuts !== 'undefined') {
            console.log('[PlanManager] Unregistering shortcuts:', registeredShortcutIds);
            registeredShortcutIds.forEach(function(id) {
                KeyboardShortcuts.unregisterShortcut(id);
            });
            registeredShortcutIds = [];
        } else {
            // Fallback: remove direct listener
            document.removeEventListener('keydown', handleKeyboardShortcut);
        }

        removeShortcutHints();
        clearSelection();
        keyboardShortcutsEnabled = false;
        keyboardShortcutsInitialized = false;
        console.log('[PlanManager] Keyboard shortcuts disabled');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        startBuild: startBuild,
        deletePlan: deletePlan,
        movePlan: movePlan,
        refreshPlanList: refreshPlanList,
        showConfirmDialog: showConfirmDialog,
        getStates: getStates,
        STATES: PLAN_STATES,
        // Selection API
        selectPlan: selectPlan,
        getSelectedPlanId: getSelectedPlanId,
        clearSelection: clearSelection,
        // Keyboard shortcuts API
        initKeyboardShortcuts: initKeyboardShortcuts,
        disableKeyboardShortcuts: disableKeyboardShortcuts,
        testKeyboardShortcut: testKeyboardShortcut,
        isKeyboardShortcutsInitialized: isKeyboardShortcutsInitialized,
        updateShortcutStatusIndicators: updateShortcutStatusIndicators
    };
})();

// Expose functions globally for onclick handlers in templates
window.startBuild = PlanManager.startBuild;
window.deletePlan = PlanManager.deletePlan;
window.movePlan = PlanManager.movePlan;
window.refreshPlanList = PlanManager.refreshPlanList;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanManager;
}
