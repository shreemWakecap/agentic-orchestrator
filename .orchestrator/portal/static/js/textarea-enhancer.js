/**
 * Textarea Enhancer Module
 *
 * Provides enhanced textarea functionality including:
 * - Auto-resize on input (grows with content up to max-height)
 * - Character count display with visual feedback (green/yellow/red)
 * - Placeholder rotation/typing animation for guidance
 * - Focus/blur visual state management
 * - Keyboard accessibility (proper tab order, aria attributes)
 *
 * Usage:
 * TextareaEnhancer.init(textarea, options);
 */

const TextareaEnhancer = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const defaultConfig = {
        // Auto-resize settings
        minHeight: 100,
        maxHeight: 400,
        resizeDebounce: 16,

        // Character count settings
        showCharCount: true,
        minChars: 0,
        maxChars: 5000,
        warnThreshold: 0.8,  // Show yellow at 80% of max
        errorThreshold: 0.95, // Show red at 95% of max

        // Placeholder animation settings
        animatePlaceholder: false,
        placeholders: [],
        typingSpeed: 50,
        pauseBetween: 3000,

        // Focus state settings
        focusClass: 'textarea-enhanced-focus',
        errorClass: 'textarea-enhanced-error',
        warnClass: 'textarea-enhanced-warn',

        // Accessibility
        ariaLabel: null,
        ariaDescribedBy: null
    };

    // Track enhanced textareas
    const enhancedTextareas = new WeakMap();

    // =========================================================================
    // Auto-resize Functions
    // =========================================================================

    /**
     * Auto-resize textarea to fit content
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} [config] - Configuration options
     */
    function autoResize(textarea, config) {
        if (!textarea || textarea.tagName !== 'TEXTAREA') return;

        config = config || enhancedTextareas.get(textarea) || defaultConfig;

        // Store scroll position
        var scrollTop = window.pageYOffset;

        // Reset height to auto to get scrollHeight
        textarea.style.height = 'auto';

        // Calculate new height
        var newHeight = Math.max(
            config.minHeight,
            Math.min(textarea.scrollHeight, config.maxHeight)
        );

        textarea.style.height = newHeight + 'px';

        // Add/remove scrollbar class based on overflow
        if (textarea.scrollHeight > config.maxHeight) {
            textarea.style.overflowY = 'auto';
            textarea.classList.add('textarea-overflow');
        } else {
            textarea.style.overflowY = 'hidden';
            textarea.classList.remove('textarea-overflow');
        }

        // Restore scroll position
        window.scrollTo(0, scrollTop);
    }

    /**
     * Create debounced auto-resize function
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     * @returns {Function} Debounced resize function
     */
    function createDebouncedResize(textarea, config) {
        var timeout;
        return function() {
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                autoResize(textarea, config);
            }, config.resizeDebounce);
        };
    }

    // =========================================================================
    // Character Count Functions
    // =========================================================================

    /**
     * Update character count display and visual feedback
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {HTMLElement} [countElement] - Optional count display element
     * @param {Object} [config] - Configuration options
     * @returns {Object} Character count info { count, remaining, status }
     */
    function updateCharCount(textarea, countElement, config) {
        if (!textarea) return { count: 0, remaining: 0, status: 'ok' };

        config = config || enhancedTextareas.get(textarea) || defaultConfig;
        var state = enhancedTextareas.get(textarea);

        var count = textarea.value.length;
        var remaining = config.maxChars - count;
        var ratio = count / config.maxChars;

        // Determine status
        var status = 'ok';
        if (config.maxChars > 0) {
            if (ratio >= config.errorThreshold || count > config.maxChars) {
                status = 'error';
            } else if (ratio >= config.warnThreshold) {
                status = 'warn';
            }
        }

        // Check minimum
        if (config.minChars > 0 && count < config.minChars && count > 0) {
            status = 'warn';
        }

        // Update textarea classes
        textarea.classList.remove(config.errorClass, config.warnClass);
        if (status === 'error') {
            textarea.classList.add(config.errorClass);
        } else if (status === 'warn') {
            textarea.classList.add(config.warnClass);
        }

        // Update count element if provided or stored
        var displayElement = countElement || (state && state.charCountElement);
        if (displayElement) {
            updateCharCountDisplay(displayElement, count, remaining, config, status);
        }

        // Update ARIA
        if (status === 'error' && config.maxChars > 0 && count > config.maxChars) {
            textarea.setAttribute('aria-invalid', 'true');
        } else {
            textarea.removeAttribute('aria-invalid');
        }

        return { count: count, remaining: remaining, status: status };
    }

    /**
     * Update character count display element
     * @param {HTMLElement} element - The count display element
     * @param {number} count - Current character count
     * @param {number} remaining - Remaining characters
     * @param {Object} config - Configuration options
     * @param {string} status - Current status (ok, warn, error)
     */
    function updateCharCountDisplay(element, count, remaining, config, status) {
        // Build display text
        var displayText;
        if (config.maxChars > 0) {
            displayText = count + ' / ' + config.maxChars;
            if (remaining < 100) {
                displayText += ' (' + remaining + ' remaining)';
            }
        } else {
            displayText = count + ' characters';
        }

        element.textContent = displayText;

        // Update colors
        element.classList.remove(
            'text-green-600', 'text-yellow-600', 'text-red-600',
            'dark:text-green-400', 'dark:text-yellow-400', 'dark:text-red-400',
            'text-gray-500', 'dark:text-gray-400'
        );

        if (status === 'error') {
            element.classList.add('text-red-600', 'dark:text-red-400');
        } else if (status === 'warn') {
            element.classList.add('text-yellow-600', 'dark:text-yellow-400');
        } else if (count > 0 && config.minChars > 0 && count >= config.minChars) {
            element.classList.add('text-green-600', 'dark:text-green-400');
        } else {
            element.classList.add('text-gray-500', 'dark:text-gray-400');
        }

        // Add pulse animation for error state
        if (status === 'error') {
            element.classList.add('animate-pulse');
        } else {
            element.classList.remove('animate-pulse');
        }
    }

    /**
     * Create character count display element
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     * @returns {HTMLElement} The count display element
     */
    function createCharCountElement(textarea, config) {
        var countEl = document.createElement('div');
        countEl.className = 'textarea-char-count text-xs text-gray-500 dark:text-gray-400 mt-1 text-right transition-colors duration-200';
        countEl.setAttribute('aria-live', 'polite');
        countEl.setAttribute('aria-atomic', 'true');

        // Generate unique ID for ARIA
        var countId = 'char-count-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        countEl.id = countId;

        // Link to textarea for accessibility
        var existingDescribedBy = textarea.getAttribute('aria-describedby');
        if (existingDescribedBy) {
            textarea.setAttribute('aria-describedby', existingDescribedBy + ' ' + countId);
        } else {
            textarea.setAttribute('aria-describedby', countId);
        }

        return countEl;
    }

    // =========================================================================
    // Placeholder Animation Functions
    // =========================================================================

    /**
     * Start placeholder animation cycle
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     * @returns {Object} Animation control object with stop() method
     */
    function startPlaceholderAnimation(textarea, config) {
        if (!config.placeholders || config.placeholders.length === 0) {
            return { stop: function() {} };
        }

        var currentIndex = 0;
        var currentCharIndex = 0;
        var isTyping = true;
        var animationTimer = null;
        var pauseTimer = null;
        var stopped = false;

        function typeNextChar() {
            if (stopped || textarea.value.length > 0) {
                // Stop animation if user starts typing
                return;
            }

            var currentPlaceholder = config.placeholders[currentIndex];

            if (isTyping) {
                if (currentCharIndex <= currentPlaceholder.length) {
                    textarea.placeholder = currentPlaceholder.substring(0, currentCharIndex);
                    currentCharIndex++;
                    animationTimer = setTimeout(typeNextChar, config.typingSpeed);
                } else {
                    // Finished typing, pause before clearing
                    isTyping = false;
                    pauseTimer = setTimeout(function() {
                        currentCharIndex = currentPlaceholder.length;
                        typeNextChar();
                    }, config.pauseBetween);
                }
            } else {
                // Clearing phase
                if (currentCharIndex > 0) {
                    currentCharIndex--;
                    textarea.placeholder = config.placeholders[currentIndex].substring(0, currentCharIndex);
                    animationTimer = setTimeout(typeNextChar, config.typingSpeed / 2);
                } else {
                    // Move to next placeholder
                    currentIndex = (currentIndex + 1) % config.placeholders.length;
                    isTyping = true;
                    animationTimer = setTimeout(typeNextChar, config.typingSpeed);
                }
            }
        }

        // Start animation
        typeNextChar();

        return {
            stop: function() {
                stopped = true;
                clearTimeout(animationTimer);
                clearTimeout(pauseTimer);
            },
            restart: function() {
                stopped = false;
                currentIndex = 0;
                currentCharIndex = 0;
                isTyping = true;
                typeNextChar();
            }
        };
    }

    // =========================================================================
    // Focus State Management
    // =========================================================================

    /**
     * Handle textarea focus
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     */
    function handleFocus(textarea, config) {
        textarea.classList.add(config.focusClass);

        // Stop placeholder animation on focus
        var state = enhancedTextareas.get(textarea);
        if (state && state.placeholderAnimation) {
            state.placeholderAnimation.stop();
        }
    }

    /**
     * Handle textarea blur
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     */
    function handleBlur(textarea, config) {
        textarea.classList.remove(config.focusClass);

        // Restart placeholder animation if empty
        var state = enhancedTextareas.get(textarea);
        if (state && state.placeholderAnimation && textarea.value.length === 0) {
            state.placeholderAnimation.restart();
        }
    }

    // =========================================================================
    // Accessibility Setup
    // =========================================================================

    /**
     * Setup accessibility attributes
     * @param {HTMLTextAreaElement} textarea - The textarea element
     * @param {Object} config - Configuration options
     */
    function setupAccessibility(textarea, config) {
        // Ensure textarea has an accessible name
        if (config.ariaLabel) {
            textarea.setAttribute('aria-label', config.ariaLabel);
        }

        if (config.ariaDescribedBy) {
            var existing = textarea.getAttribute('aria-describedby');
            if (existing) {
                textarea.setAttribute('aria-describedby', existing + ' ' + config.ariaDescribedBy);
            } else {
                textarea.setAttribute('aria-describedby', config.ariaDescribedBy);
            }
        }

        // Ensure proper role
        if (!textarea.hasAttribute('role')) {
            textarea.setAttribute('role', 'textbox');
        }

        // Multiline attribute
        textarea.setAttribute('aria-multiline', 'true');

        // Tab index if not set
        if (!textarea.hasAttribute('tabindex')) {
            textarea.setAttribute('tabindex', '0');
        }
    }

    // =========================================================================
    // Main Initialization
    // =========================================================================

    /**
     * Initialize textarea enhancement
     * @param {HTMLTextAreaElement|string} textareaOrId - Textarea element or ID
     * @param {Object} [options] - Configuration options
     * @returns {Object} Enhancement control object
     */
    function init(textareaOrId, options) {
        // Get textarea element
        var textarea;
        if (typeof textareaOrId === 'string') {
            textarea = document.getElementById(textareaOrId);
        } else {
            textarea = textareaOrId;
        }

        if (!textarea || textarea.tagName !== 'TEXTAREA') {
            console.warn('TextareaEnhancer: Invalid textarea element');
            return null;
        }

        // Check if already enhanced
        if (enhancedTextareas.has(textarea)) {
            return enhancedTextareas.get(textarea).api;
        }

        // Merge configuration
        var config = Object.assign({}, defaultConfig, options || {});

        // State object
        var state = {
            config: config,
            charCountElement: null,
            placeholderAnimation: null,
            eventListeners: [],
            api: null
        };

        // Apply initial styles
        textarea.classList.add('textarea-enhanced');
        textarea.style.minHeight = config.minHeight + 'px';
        textarea.style.maxHeight = config.maxHeight + 'px';
        textarea.style.overflowY = 'hidden';
        textarea.style.resize = 'none';
        textarea.style.transition = 'height 0.15s ease-out, border-color 0.2s ease, box-shadow 0.2s ease';

        // Setup accessibility
        setupAccessibility(textarea, config);

        // Create debounced resize
        var debouncedResize = createDebouncedResize(textarea, config);

        // Setup character count
        if (config.showCharCount) {
            state.charCountElement = createCharCountElement(textarea, config);

            // Insert after textarea
            if (textarea.parentNode) {
                textarea.parentNode.insertBefore(state.charCountElement, textarea.nextSibling);
            }

            // Initial count update
            updateCharCount(textarea, state.charCountElement, config);
        }

        // Setup placeholder animation
        if (config.animatePlaceholder && config.placeholders.length > 0) {
            state.placeholderAnimation = startPlaceholderAnimation(textarea, config);
        }

        // Event listeners
        function onInput() {
            debouncedResize();
            updateCharCount(textarea, state.charCountElement, config);

            // Stop placeholder animation when typing
            if (state.placeholderAnimation && textarea.value.length > 0) {
                state.placeholderAnimation.stop();
            }
        }

        function onFocus() {
            handleFocus(textarea, config);
        }

        function onBlur() {
            handleBlur(textarea, config);
        }

        function onKeyDown(e) {
            // Allow Tab for accessibility navigation
            if (e.key === 'Tab') {
                return; // Let default behavior happen
            }

            // Ctrl/Cmd + Enter to submit (if form exists)
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                var form = textarea.closest('form');
                if (form) {
                    var submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                    form.dispatchEvent(submitEvent);
                }
            }
        }

        // Attach listeners
        textarea.addEventListener('input', onInput);
        textarea.addEventListener('focus', onFocus);
        textarea.addEventListener('blur', onBlur);
        textarea.addEventListener('keydown', onKeyDown);

        state.eventListeners = [
            { type: 'input', handler: onInput },
            { type: 'focus', handler: onFocus },
            { type: 'blur', handler: onBlur },
            { type: 'keydown', handler: onKeyDown }
        ];

        // Initial resize
        autoResize(textarea, config);

        // Build API object
        state.api = {
            autoResize: function() {
                autoResize(textarea, config);
            },
            updateCharCount: function() {
                return updateCharCount(textarea, state.charCountElement, config);
            },
            getConfig: function() {
                return Object.assign({}, config);
            },
            setConfig: function(newOptions) {
                Object.assign(config, newOptions);
            },
            destroy: function() {
                destroy(textarea);
            },
            getCharCountElement: function() {
                return state.charCountElement;
            },
            focus: function() {
                textarea.focus();
            },
            getValue: function() {
                return textarea.value;
            },
            setValue: function(value) {
                textarea.value = value;
                autoResize(textarea, config);
                updateCharCount(textarea, state.charCountElement, config);
            }
        };

        // Store state
        enhancedTextareas.set(textarea, state);

        return state.api;
    }

    /**
     * Destroy textarea enhancement and cleanup
     * @param {HTMLTextAreaElement|string} textareaOrId - Textarea element or ID
     */
    function destroy(textareaOrId) {
        var textarea;
        if (typeof textareaOrId === 'string') {
            textarea = document.getElementById(textareaOrId);
        } else {
            textarea = textareaOrId;
        }

        if (!textarea) return;

        var state = enhancedTextareas.get(textarea);
        if (!state) return;

        // Remove event listeners
        state.eventListeners.forEach(function(listener) {
            textarea.removeEventListener(listener.type, listener.handler);
        });

        // Stop placeholder animation
        if (state.placeholderAnimation) {
            state.placeholderAnimation.stop();
        }

        // Remove char count element
        if (state.charCountElement && state.charCountElement.parentNode) {
            state.charCountElement.parentNode.removeChild(state.charCountElement);
        }

        // Remove classes
        textarea.classList.remove(
            'textarea-enhanced',
            state.config.focusClass,
            state.config.errorClass,
            state.config.warnClass,
            'textarea-overflow'
        );

        // Reset styles
        textarea.style.minHeight = '';
        textarea.style.maxHeight = '';
        textarea.style.overflowY = '';
        textarea.style.resize = '';
        textarea.style.transition = '';
        textarea.style.height = '';

        // Remove from map
        enhancedTextareas.delete(textarea);
    }

    /**
     * Check if a textarea is enhanced
     * @param {HTMLTextAreaElement|string} textareaOrId - Textarea element or ID
     * @returns {boolean} Whether the textarea is enhanced
     */
    function isEnhanced(textareaOrId) {
        var textarea;
        if (typeof textareaOrId === 'string') {
            textarea = document.getElementById(textareaOrId);
        } else {
            textarea = textareaOrId;
        }

        return textarea && enhancedTextareas.has(textarea);
    }

    /**
     * Get the API for an enhanced textarea
     * @param {HTMLTextAreaElement|string} textareaOrId - Textarea element or ID
     * @returns {Object|null} The API object or null
     */
    function getApi(textareaOrId) {
        var textarea;
        if (typeof textareaOrId === 'string') {
            textarea = document.getElementById(textareaOrId);
        } else {
            textarea = textareaOrId;
        }

        if (!textarea) return null;

        var state = enhancedTextareas.get(textarea);
        return state ? state.api : null;
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // Main functions
        init: init,
        destroy: destroy,
        isEnhanced: isEnhanced,
        getApi: getApi,

        // Utility functions (can be used standalone)
        autoResize: autoResize,
        updateCharCount: updateCharCount,

        // Default configuration (for reference/override)
        defaultConfig: defaultConfig
    };
})();

// Expose globally for use by other modules
window.TextareaEnhancer = TextareaEnhancer;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TextareaEnhancer;
}
