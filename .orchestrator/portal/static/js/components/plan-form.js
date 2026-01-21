/**
 * Plan Form Component
 *
 * Unified component for the "Create New Plan" form section.
 * This is the SINGLE source of truth for plan form functionality
 * across Dashboard, Plans page, and any other location.
 *
 * Features:
 * - Auto-discovers form elements via data attributes
 * - Handles form submission with validation
 * - Integrates with UnifiedPlanDialog for AI enhancement
 * - Clears form after successful plan creation
 * - Works identically on all pages
 *
 * Dependencies:
 * - PlanTextarea (from plan-textarea.js)
 * - UnifiedPlanDialog (from unified-plan-dialog.js)
 *
 * Usage:
 *   // Auto-initialize all plan forms on the page
 *   PlanForm.init();
 *
 *   // Or initialize a specific form
 *   PlanForm.initForm(document.getElementById('plan-form'));
 *
 * HTML Requirements (via data attributes):
 *   <form data-plan-form>
 *     <div data-plan-textarea data-placeholder="..."></div>
 *     <button type="submit" data-plan-submit>Create Plan</button>
 *   </form>
 */

const PlanForm = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        // Selectors (using data attributes for clarity)
        selectors: {
            form: '[data-plan-form]',
            textarea: '[data-plan-textarea]',
            submit: '[data-plan-submit]'
        },

        // Default placeholder text
        defaultPlaceholder: 'Describe what you want to build...\n\nExamples:\n\u2022 Add user authentication with email/password login\n\u2022 Create a dashboard showing sales analytics\n\u2022 Implement dark mode toggle for the entire app',

        // Validation
        minChars: 10,
        maxChars: 2000
    };

    // =========================================================================
    // State
    // =========================================================================

    let isInitialized = false;
    const instances = new Map(); // form element -> instance state

    // =========================================================================
    // Private Functions
    // =========================================================================

    /**
     * Initialize a single plan form
     * @param {HTMLFormElement} form - The form element
     * @returns {Object|null} Instance state or null on failure
     */
    function initializeForm(form) {
        if (!form || instances.has(form)) {
            return instances.get(form) || null;
        }

        // Find textarea container
        const textareaContainer = form.querySelector(CONFIG.selectors.textarea);
        if (!textareaContainer) {
            console.warn('[PlanForm] No textarea container found in form');
            return null;
        }

        // Check dependencies
        if (typeof PlanTextarea === 'undefined') {
            console.error('[PlanForm] PlanTextarea module not found');
            return null;
        }

        if (typeof UnifiedPlanDialog === 'undefined') {
            console.error('[PlanForm] UnifiedPlanDialog module not found');
            return null;
        }

        // Get placeholder from data attribute or use default
        const placeholder = textareaContainer.dataset.placeholder || CONFIG.defaultPlaceholder;

        // Generate unique container ID if not present
        if (!textareaContainer.id) {
            textareaContainer.id = 'plan-textarea-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        }

        // Initialize PlanTextarea
        const textareaInstance = PlanTextarea.init(textareaContainer.id, {
            placeholder: placeholder,
            ariaLabel: 'Plan description - describe what you want to build',
            minChars: CONFIG.minChars,
            maxChars: CONFIG.maxChars,
            onSubmit: function(value) {
                // Ctrl+Enter triggers form submit
                form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            }
        });

        if (!textareaInstance) {
            console.error('[PlanForm] Failed to initialize PlanTextarea');
            return null;
        }

        // Create instance state
        const state = {
            form: form,
            textareaContainer: textareaContainer,
            textareaInstance: textareaInstance,
            isSubmitting: false
        };

        // Attach form submit handler
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            handleFormSubmit(state);
        });

        // Store instance
        instances.set(form, state);

        console.log('[PlanForm] Initialized form:', form.id || '(no id)');
        return state;
    }

    /**
     * Handle form submission
     * @param {Object} state - The form instance state
     */
    async function handleFormSubmit(state) {
        if (state.isSubmitting) {
            return; // Prevent double submission
        }

        const textareaInstance = state.textareaInstance;

        // Validate
        const validation = textareaInstance.validate();
        if (!validation.valid) {
            textareaInstance.focus();
            showValidationError(state, validation.errors[0]);
            return;
        }

        const description = textareaInstance.getValue().trim();

        // Mark as submitting
        state.isSubmitting = true;
        setSubmitButtonLoading(state, true);

        try {
            // Use UnifiedPlanDialog for AI enhancement and plan creation
            const result = await UnifiedPlanDialog.showCreatePlanDialog(description);

            if (result.created) {
                // Clear form on success (dialog handles redirect)
                textareaInstance.clear();
                showSuccessMessage(state, 'Plan created successfully!');
            }
            // If not created (user cancelled), do nothing - let them modify input
        } catch (error) {
            console.error('[PlanForm] Error creating plan:', error);
            showErrorMessage(state, 'Failed to create plan: ' + (error.message || 'Unknown error'));
        } finally {
            state.isSubmitting = false;
            setSubmitButtonLoading(state, false);
        }
    }

    /**
     * Set submit button loading state
     * @param {Object} state - Form instance state
     * @param {boolean} loading - Whether to show loading state
     */
    function setSubmitButtonLoading(state, loading) {
        const submitBtn = state.form.querySelector(CONFIG.selectors.submit);
        if (!submitBtn) return;

        if (loading) {
            submitBtn.disabled = true;
            submitBtn.dataset.originalHtml = submitBtn.innerHTML;
            submitBtn.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Creating...';
        } else {
            submitBtn.disabled = false;
            if (submitBtn.dataset.originalHtml) {
                submitBtn.innerHTML = submitBtn.dataset.originalHtml;
                delete submitBtn.dataset.originalHtml;
            }
        }
    }

    /**
     * Show validation error message
     * @param {Object} state - Form instance state
     * @param {string} message - Error message
     */
    function showValidationError(state, message) {
        // Use Toast if available
        if (typeof Toast !== 'undefined' && Toast.show) {
            Toast.show(message, 'error');
        } else {
            console.warn('[PlanForm] Validation error:', message);
        }
    }

    /**
     * Show success message
     * @param {Object} state - Form instance state
     * @param {string} message - Success message
     */
    function showSuccessMessage(state, message) {
        if (typeof Toast !== 'undefined' && Toast.show) {
            Toast.show(message, 'success');
        }
    }

    /**
     * Show error message
     * @param {Object} state - Form instance state
     * @param {string} message - Error message
     */
    function showErrorMessage(state, message) {
        if (typeof Toast !== 'undefined' && Toast.show) {
            Toast.show(message, 'error');
        } else {
            alert(message);
        }
    }

    // =========================================================================
    // Public API
    // =========================================================================

    /**
     * Initialize all plan forms on the page
     * Call this once on DOMContentLoaded
     */
    function init() {
        if (isInitialized) {
            console.warn('[PlanForm] Already initialized');
            return;
        }

        const forms = document.querySelectorAll(CONFIG.selectors.form);
        forms.forEach(function(form) {
            initializeForm(form);
        });

        isInitialized = true;
        console.log('[PlanForm] Initialized', forms.length, 'form(s)');
    }

    /**
     * Initialize a specific form element
     * @param {HTMLFormElement} form - The form to initialize
     * @returns {Object|null} Instance API or null
     */
    function initForm(form) {
        const state = initializeForm(form);
        if (!state) return null;

        // Return public API for this instance
        return {
            getValue: function() {
                return state.textareaInstance.getValue();
            },
            setValue: function(value) {
                state.textareaInstance.setValue(value);
            },
            clear: function() {
                state.textareaInstance.clear();
            },
            focus: function() {
                state.textareaInstance.focus();
            },
            validate: function() {
                return state.textareaInstance.validate();
            },
            submit: function() {
                handleFormSubmit(state);
            },
            isSubmitting: function() {
                return state.isSubmitting;
            }
        };
    }

    /**
     * Get instance for a form element
     * @param {HTMLFormElement} form - The form element
     * @returns {Object|null} Instance state or null
     */
    function getInstance(form) {
        return instances.get(form) || null;
    }

    /**
     * Destroy a form instance
     * @param {HTMLFormElement} form - The form to destroy
     */
    function destroy(form) {
        const state = instances.get(form);
        if (!state) return;

        // Destroy textarea instance
        if (state.textareaInstance && state.textareaInstance.destroy) {
            state.textareaInstance.destroy();
        }

        instances.delete(form);
    }

    /**
     * Destroy all instances
     */
    function destroyAll() {
        instances.forEach(function(state, form) {
            destroy(form);
        });
        isInitialized = false;
    }

    /**
     * Check if module is initialized
     * @returns {boolean}
     */
    function isReady() {
        return isInitialized;
    }

    /**
     * Get count of active instances
     * @returns {number}
     */
    function getInstanceCount() {
        return instances.size;
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Auto-initialize when DOM is ready
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            // DOM already ready, initialize on next tick to ensure all scripts loaded
            setTimeout(init, 0);
        }
    }

    // =========================================================================
    // Return Public API
    // =========================================================================

    return {
        init: init,
        initForm: initForm,
        getInstance: getInstance,
        destroy: destroy,
        destroyAll: destroyAll,
        isReady: isReady,
        getInstanceCount: getInstanceCount,
        CONFIG: CONFIG
    };
})();

// Expose globally
window.PlanForm = PlanForm;

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanForm;
}
