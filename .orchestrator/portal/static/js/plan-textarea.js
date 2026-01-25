/**
 * Plan Textarea Module
 *
 * A unified, reusable textarea component for plan editing across
 * Dashboard and Plans management views. Wraps TextareaEnhancer
 * with plan-specific defaults and validation.
 *
 * Features:
 * - Consistent validation (10 char min, 2000 char max)
 * - Character counter display with visual feedback
 * - Submission handling with validation
 * - Focus state management
 * - Identical behavior across different contexts
 *
 * Dependencies:
 * - TextareaEnhancer (from textarea-enhancer.js)
 *
 * Usage:
 * const instance = PlanTextarea.init('container-id', {
 *     onSubmit: function(value) { ... },
 *     placeholder: 'Describe your plan...'
 * });
 */

const PlanTextarea = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const PLAN_DEFAULTS = {
        // Validation constraints
        minChars: 10,
        maxChars: 2000,

        // Auto-resize settings
        minHeight: 120,
        maxHeight: 400,

        // Character count display
        showCharCount: true,
        warnThreshold: 0.8,
        errorThreshold: 0.95,

        // Focus state classes
        focusClass: 'plan-textarea-focus',
        errorClass: 'plan-textarea-error',
        warnClass: 'plan-textarea-warn',

        // Placeholder
        placeholder: 'Describe your plan in detail...',

        // Accessibility
        ariaLabel: 'Plan description'
    };

    // Track active instances
    const instances = new Map();

    // =========================================================================
    // Validation
    // =========================================================================

    /**
     * Validate plan text content
     * @param {string} value - The text to validate
     * @param {Object} config - Configuration with minChars and maxChars
     * @returns {Object} Validation result { valid, errors, warnings }
     */
    function validatePlanText(value, config) {
        var result = {
            valid: true,
            errors: [],
            warnings: []
        };

        var trimmedValue = (value || '').trim();
        var length = trimmedValue.length;

        // Check minimum length
        if (length === 0) {
            result.valid = false;
            result.errors.push('Plan description is required');
        } else if (length < config.minChars) {
            result.valid = false;
            result.errors.push('Plan description must be at least ' + config.minChars + ' characters (currently ' + length + ')');
        }

        // Check maximum length
        if (length > config.maxChars) {
            result.valid = false;
            result.errors.push('Plan description must not exceed ' + config.maxChars + ' characters (currently ' + length + ')');
        }

        // Warnings for approaching limits
        var ratio = length / config.maxChars;
        if (ratio >= config.warnThreshold && ratio < config.errorThreshold) {
            result.warnings.push('Approaching character limit (' + (config.maxChars - length) + ' remaining)');
        }

        return result;
    }

    // =========================================================================
    // Instance Creation
    // =========================================================================

    /**
     * Create textarea element with plan-specific styling
     * @param {string} id - Unique ID for the textarea
     * @param {Object} config - Configuration options
     * @returns {HTMLTextAreaElement} The created textarea
     */
    function createTextareaElement(id, config) {
        var textarea = document.createElement('textarea');
        textarea.id = id;
        textarea.name = 'plan-content';
        textarea.className = 'plan-textarea w-full';
        textarea.placeholder = config.placeholder || PLAN_DEFAULTS.placeholder;
        textarea.setAttribute('aria-label', config.ariaLabel || PLAN_DEFAULTS.ariaLabel);

        return textarea;
    }

    /**
     * Create validation message container
     * @returns {HTMLElement} The validation message element
     */
    function createValidationMessageElement() {
        var msgEl = document.createElement('div');
        msgEl.className = 'plan-textarea-validation hidden text-sm mt-1 transition-all duration-200';
        msgEl.setAttribute('role', 'alert');
        msgEl.setAttribute('aria-live', 'polite');
        return msgEl;
    }

    /**
     * Update validation message display
     * @param {HTMLElement} element - The validation message element
     * @param {Object} validationResult - Result from validatePlanText
     */
    function updateValidationDisplay(element, validationResult) {
        if (!element) return;

        // Clear previous classes
        element.classList.remove(
            'text-red-600',
            'text-yellow-600',
            'text-green-600',
            'hidden'
        );

        if (validationResult.errors.length > 0) {
            element.textContent = validationResult.errors[0];
            element.classList.add('text-red-600');
        } else if (validationResult.warnings.length > 0) {
            element.textContent = validationResult.warnings[0];
            element.classList.add('text-yellow-600');
        } else {
            element.classList.add('hidden');
        }
    }

    // =========================================================================
    // Main API
    // =========================================================================

    /**
     * Initialize a PlanTextarea instance
     * @param {string} containerId - ID of the container element
     * @param {Object} [options] - Configuration options
     * @param {Function} [options.onSubmit] - Callback when valid content is submitted
     * @param {Function} [options.onChange] - Callback when content changes
     * @param {Function} [options.onValidate] - Callback when validation runs
     * @param {string} [options.placeholder] - Custom placeholder text
     * @param {string} [options.initialValue] - Initial textarea value
     * @param {number} [options.minChars] - Minimum character count (default: 10)
     * @param {number} [options.maxChars] - Maximum character count (default: 2000)
     * @returns {Object|null} Instance API object or null on failure
     */
    function init(containerId, options) {
        // Get container element
        var container;
        if (typeof containerId === 'string') {
            container = document.getElementById(containerId);
        } else if (containerId instanceof HTMLElement) {
            container = containerId;
        }

        if (!container) {
            console.warn('PlanTextarea: Container not found:', containerId);
            return null;
        }

        // Check if already initialized
        if (instances.has(containerId)) {
            console.warn('PlanTextarea: Already initialized for container:', containerId);
            return instances.get(containerId).api;
        }

        // Merge configuration
        var config = Object.assign({}, PLAN_DEFAULTS, options || {});

        // Generate unique ID for textarea
        var textareaId = 'plan-textarea-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

        // Create textarea element
        var textarea = createTextareaElement(textareaId, config);

        // Create validation message element
        var validationMsgEl = createValidationMessageElement();

        // Build DOM structure
        var wrapper = document.createElement('div');
        wrapper.className = 'plan-textarea-wrapper relative';
        wrapper.appendChild(textarea);
        wrapper.appendChild(validationMsgEl);

        container.appendChild(wrapper);

        // Check if TextareaEnhancer is available
        if (typeof TextareaEnhancer === 'undefined') {
            console.error('PlanTextarea: TextareaEnhancer module not found');
            return null;
        }

        // Initialize TextareaEnhancer with plan-specific config
        var enhancerApi = TextareaEnhancer.init(textarea, {
            minHeight: config.minHeight,
            maxHeight: config.maxHeight,
            minChars: config.minChars,
            maxChars: config.maxChars,
            showCharCount: config.showCharCount,
            warnThreshold: config.warnThreshold,
            errorThreshold: config.errorThreshold,
            focusClass: config.focusClass,
            errorClass: config.errorClass,
            warnClass: config.warnClass,
            ariaLabel: config.ariaLabel
        });

        if (!enhancerApi) {
            console.error('PlanTextarea: Failed to initialize TextareaEnhancer');
            return null;
        }

        // Set initial value if provided
        if (config.initialValue) {
            enhancerApi.setValue(config.initialValue);
        }

        // State object
        var state = {
            containerId: containerId,
            config: config,
            textarea: textarea,
            wrapper: wrapper,
            validationMsgEl: validationMsgEl,
            enhancerApi: enhancerApi,
            lastValidation: null,
            api: null
        };

        // Handle input changes
        textarea.addEventListener('input', function() {
            var value = textarea.value;
            var validationResult = validatePlanText(value, config);
            state.lastValidation = validationResult;

            // Only show validation messages if user has typed something
            if (value.length > 0) {
                updateValidationDisplay(validationMsgEl, validationResult);
            } else {
                validationMsgEl.classList.add('hidden');
            }

            // Call onChange callback if provided
            if (typeof config.onChange === 'function') {
                config.onChange(value, validationResult);
            }

            // Call onValidate callback if provided
            if (typeof config.onValidate === 'function') {
                config.onValidate(validationResult);
            }
        });

        // Handle Ctrl+Enter / Cmd+Enter for submission
        textarea.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                var validationResult = validatePlanText(textarea.value, config);
                state.lastValidation = validationResult;

                if (validationResult.valid && typeof config.onSubmit === 'function') {
                    config.onSubmit(textarea.value.trim());
                } else {
                    updateValidationDisplay(validationMsgEl, validationResult);
                    // Shake animation for invalid submission
                    textarea.classList.add('animate-shake');
                    setTimeout(function() {
                        textarea.classList.remove('animate-shake');
                    }, 500);
                }
            }
        });

        // Build public API
        state.api = {
            /**
             * Get the current textarea value
             * @returns {string} The current value
             */
            getValue: function() {
                return textarea.value;
            },

            /**
             * Set the textarea value
             * @param {string} value - The value to set
             */
            setValue: function(value) {
                enhancerApi.setValue(value || '');
                var validationResult = validatePlanText(value || '', config);
                state.lastValidation = validationResult;
                if ((value || '').length > 0) {
                    updateValidationDisplay(validationMsgEl, validationResult);
                }
            },

            /**
             * Validate the current content
             * @returns {Object} Validation result { valid, errors, warnings }
             */
            validate: function() {
                var validationResult = validatePlanText(textarea.value, config);
                state.lastValidation = validationResult;
                updateValidationDisplay(validationMsgEl, validationResult);
                return validationResult;
            },

            /**
             * Focus the textarea
             */
            focus: function() {
                textarea.focus();
            },

            /**
             * Blur the textarea
             */
            blur: function() {
                textarea.blur();
            },

            /**
             * Clear the textarea content
             */
            clear: function() {
                enhancerApi.setValue('');
                state.lastValidation = null;
                validationMsgEl.classList.add('hidden');
            },

            /**
             * Get the last validation result
             * @returns {Object|null} Last validation result or null
             */
            getLastValidation: function() {
                return state.lastValidation;
            },

            /**
             * Check if current content is valid
             * @returns {boolean} True if valid
             */
            isValid: function() {
                var result = validatePlanText(textarea.value, config);
                return result.valid;
            },

            /**
             * Get the textarea element
             * @returns {HTMLTextAreaElement} The textarea element
             */
            getElement: function() {
                return textarea;
            },

            /**
             * Get the character count info
             * @returns {Object} Character count { current, min, max, remaining }
             */
            getCharCount: function() {
                var length = textarea.value.length;
                return {
                    current: length,
                    min: config.minChars,
                    max: config.maxChars,
                    remaining: config.maxChars - length
                };
            },

            /**
             * Submit the current content (triggers validation and onSubmit)
             * @returns {boolean} True if submission was valid
             */
            submit: function() {
                var validationResult = validatePlanText(textarea.value, config);
                state.lastValidation = validationResult;
                updateValidationDisplay(validationMsgEl, validationResult);

                if (validationResult.valid && typeof config.onSubmit === 'function') {
                    config.onSubmit(textarea.value.trim());
                    return true;
                }

                return false;
            },

            /**
             * Destroy the instance and clean up
             */
            destroy: function() {
                destroy(containerId);
            },

            /**
             * Update configuration options
             * @param {Object} newOptions - New options to merge
             */
            setOptions: function(newOptions) {
                Object.assign(config, newOptions);
                if (enhancerApi && enhancerApi.setConfig) {
                    enhancerApi.setConfig({
                        minChars: config.minChars,
                        maxChars: config.maxChars
                    });
                }
            }
        };

        // Store instance
        instances.set(containerId, state);

        return state.api;
    }

    /**
     * Destroy a PlanTextarea instance
     * @param {string} containerId - ID of the container element
     */
    function destroy(containerId) {
        var state = instances.get(containerId);
        if (!state) return;

        // Destroy TextareaEnhancer
        if (state.enhancerApi && state.enhancerApi.destroy) {
            state.enhancerApi.destroy();
        }

        // Remove DOM elements
        if (state.wrapper && state.wrapper.parentNode) {
            state.wrapper.parentNode.removeChild(state.wrapper);
        }

        // Remove from instances map
        instances.delete(containerId);
    }

    /**
     * Check if a container has an initialized instance
     * @param {string} containerId - ID of the container element
     * @returns {boolean} True if initialized
     */
    function isInitialized(containerId) {
        return instances.has(containerId);
    }

    /**
     * Get an existing instance API
     * @param {string} containerId - ID of the container element
     * @returns {Object|null} Instance API or null
     */
    function getInstance(containerId) {
        var state = instances.get(containerId);
        return state ? state.api : null;
    }

    /**
     * Get all active instance IDs
     * @returns {string[]} Array of container IDs
     */
    function getActiveInstances() {
        return Array.from(instances.keys());
    }

    // =========================================================================
    // CSS Injection for shake animation
    // =========================================================================

    function injectStyles() {
        if (document.getElementById('plan-textarea-styles')) return;

        var style = document.createElement('style');
        style.id = 'plan-textarea-styles';
        style.textContent = [
            '@keyframes plan-textarea-shake {',
            '  0%, 100% { transform: translateX(0); }',
            '  10%, 30%, 50%, 70%, 90% { transform: translateX(-4px); }',
            '  20%, 40%, 60%, 80% { transform: translateX(4px); }',
            '}',
            '.animate-shake {',
            '  animation: plan-textarea-shake 0.5s ease-in-out;',
            '}',
            '.plan-textarea-focus {',
            '  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3);',
            '}',
            '.plan-textarea-error {',
            '  border-color: #ef4444 !important;',
            '  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2);',
            '}',
            '.plan-textarea-warn {',
            '  border-color: #f59e0b !important;',
            '  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    // Inject styles on module load
    if (typeof document !== 'undefined' && document.head) {
        injectStyles();
    }

    // =========================================================================
    // Convenience Methods
    // =========================================================================

    /**
     * Initialize PlanTextarea for a form with auto-wired submit behavior
     * This is a convenience method that reduces boilerplate when integrating
     * with forms that have standard submit behavior.
     *
     * Usage with data attributes:
     * <div id="plan-textarea-container"
     *      data-form-id="plan-form"
     *      data-placeholder="Describe your plan...">
     * </div>
     *
     * @param {string} containerId - ID of the container element
     * @param {string} formId - ID of the form to wire submit to
     * @param {Object} [options] - Additional configuration options
     * @returns {Object|null} Instance API object or null on failure
     */
    function initForForm(containerId, formId, options) {
        options = options || {};

        // Read data attributes from container for configuration
        var container = document.getElementById(containerId);
        if (container) {
            // Allow data attributes to override options
            if (container.dataset.formId) {
                formId = container.dataset.formId;
            }
            if (container.dataset.placeholder && !options.placeholder) {
                options.placeholder = container.dataset.placeholder;
            }
            if (container.dataset.minChars && !options.minChars) {
                options.minChars = parseInt(container.dataset.minChars, 10);
            }
            if (container.dataset.maxChars && !options.maxChars) {
                options.maxChars = parseInt(container.dataset.maxChars, 10);
            }
        }

        // Set up onSubmit to dispatch form submit event
        var mergedOptions = Object.assign({}, options, {
            onSubmit: function(value) {
                var form = document.getElementById(formId);
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                }

                // Also call original onSubmit if provided
                if (typeof options.onSubmit === 'function') {
                    options.onSubmit(value);
                }
            }
        });

        return init(containerId, mergedOptions);
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // Main API
        init: init,
        initForForm: initForForm,
        destroy: destroy,
        getInstance: getInstance,
        isInitialized: isInitialized,
        getActiveInstances: getActiveInstances,

        // Constants
        DEFAULTS: PLAN_DEFAULTS,

        // Utility (can be used standalone)
        validate: function(value) {
            return validatePlanText(value, PLAN_DEFAULTS);
        }
    };
})();

// Expose globally for use by other modules
window.PlanTextarea = PlanTextarea;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanTextarea;
}
