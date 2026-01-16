/**
 * Common Utilities Module
 *
 * Shared utility functions used across multiple JavaScript modules in the
 * SDLC Orchestrator. This module provides reusable functionality for:
 * - HTML escaping (XSS prevention)
 * - Copy-to-clipboard operations
 * - Custom event dispatching
 * - ID generation
 * - Text formatting utilities
 * - Debounce/throttle helpers
 *
 * Usage:
 * Include this file before other module files. Functions are exposed via
 * the global OrchestratorUtils object and can be used by any module.
 */

const OrchestratorUtils = (function() {
    'use strict';

    // =========================================================================
    // HTML Escaping
    // =========================================================================

    /**
     * Escape HTML to prevent XSS attacks
     * Uses DOM-based escaping for security
     * @param {string} text - Text to escape
     * @returns {string} Escaped text safe for HTML insertion
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Unescape HTML entities back to original text
     * @param {string} html - HTML-escaped text
     * @returns {string} Original text with entities decoded
     */
    function unescapeHtml(html) {
        if (typeof html !== 'string') return '';
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }

    // =========================================================================
    // Copy to Clipboard
    // =========================================================================

    /**
     * Configuration for clipboard operations
     */
    const clipboardConfig = {
        successTimeout: 2000,
        successClass: 'copy-success',
        errorClass: 'copy-error'
    };

    /**
     * Copy text to clipboard using modern API with fallback
     * @param {string} text - Text to copy
     * @param {Object} [options] - Optional configuration
     * @param {HTMLElement} [options.feedbackElement] - Element to show feedback on
     * @param {Function} [options.onSuccess] - Callback on successful copy
     * @param {Function} [options.onError] - Callback on failed copy
     * @returns {Promise<boolean>} Promise resolving to success status
     */
    function copyToClipboard(text, options) {
        options = options || {};

        return new Promise(function(resolve) {
            if (!text) {
                if (options.onError) options.onError(new Error('No text to copy'));
                resolve(false);
                return;
            }

            // Use modern Clipboard API if available
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text)
                    .then(function() {
                        showCopyFeedback(options.feedbackElement, true);
                        if (options.onSuccess) options.onSuccess();
                        resolve(true);
                    })
                    .catch(function(err) {
                        // Fall back to execCommand
                        var success = fallbackCopy(text);
                        showCopyFeedback(options.feedbackElement, success);
                        if (success && options.onSuccess) {
                            options.onSuccess();
                        } else if (!success && options.onError) {
                            options.onError(err);
                        }
                        resolve(success);
                    });
            } else {
                // Use fallback for older browsers
                var success = fallbackCopy(text);
                showCopyFeedback(options.feedbackElement, success);
                if (success && options.onSuccess) {
                    options.onSuccess();
                } else if (!success && options.onError) {
                    options.onError(new Error('Clipboard API not available'));
                }
                resolve(success);
            }
        });
    }

    /**
     * Fallback copy method using execCommand
     * @param {string} text - Text to copy
     * @returns {boolean} Whether copy succeeded
     */
    function fallbackCopy(text) {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '0';
        textarea.setAttribute('readonly', '');
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();

        var success = false;
        try {
            success = document.execCommand('copy');
        } catch (err) {
            console.error('Fallback copy failed:', err);
        }

        document.body.removeChild(textarea);
        return success;
    }

    /**
     * Copy content from an element to clipboard
     * @param {HTMLElement|string} elementOrId - Element or element ID to copy from
     * @param {Object} [options] - Optional configuration passed to copyToClipboard
     * @returns {Promise<boolean>} Promise resolving to success status
     */
    function copyElementContent(elementOrId, options) {
        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) {
            console.warn('Element not found for copy operation');
            return Promise.resolve(false);
        }

        // Prefer data-copy-value attribute if present
        var content = element.dataset.copyValue || element.textContent || element.innerText || '';

        options = options || {};
        options.feedbackElement = options.feedbackElement || element;

        return copyToClipboard(content.trim(), options);
    }

    /**
     * Show copy feedback on an element
     * @param {HTMLElement} element - Element to show feedback on
     * @param {boolean} success - Whether copy was successful
     */
    function showCopyFeedback(element, success) {
        if (!element) return;

        var className = success ? clipboardConfig.successClass : clipboardConfig.errorClass;

        element.classList.add(className);

        if (success) {
            element.title = 'Copied to clipboard';
        } else {
            element.title = 'Failed to copy';
        }

        setTimeout(function() {
            element.classList.remove(className);
        }, clipboardConfig.successTimeout);
    }

    // =========================================================================
    // Custom Events
    // =========================================================================

    /**
     * Dispatch a custom event on the document
     * @param {string} namespace - Event namespace (e.g., 'chat', 'logs')
     * @param {string} name - Event name (e.g., 'message', 'connected')
     * @param {Object} [detail] - Event detail data
     * @returns {boolean} Whether event was not cancelled
     */
    function dispatchCustomEvent(namespace, name, detail) {
        var eventName = namespace + ':' + name;
        var event = new CustomEvent(eventName, {
            detail: detail || {},
            bubbles: true,
            cancelable: true
        });
        return document.dispatchEvent(event);
    }

    /**
     * Listen for a custom event
     * @param {string} namespace - Event namespace
     * @param {string} name - Event name
     * @param {Function} handler - Event handler function
     * @returns {Function} Cleanup function to remove the listener
     */
    function onCustomEvent(namespace, name, handler) {
        var eventName = namespace + ':' + name;
        document.addEventListener(eventName, handler);
        return function() {
            document.removeEventListener(eventName, handler);
        };
    }

    // =========================================================================
    // ID Generation
    // =========================================================================

    /**
     * Generate a unique ID string
     * @param {string} [prefix='id'] - Prefix for the ID
     * @returns {string} Unique identifier
     */
    function generateId(prefix) {
        prefix = prefix || 'id';
        return prefix + '_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Generate a UUID v4
     * @returns {string} UUID v4 string
     */
    function generateUuid() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0;
            var v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // =========================================================================
    // Text Formatting
    // =========================================================================

    /**
     * Format a title string for display (e.g., "myTitle_name" -> "My Title Name")
     * @param {string} title - Title to format
     * @returns {string} Formatted title
     */
    function formatTitle(title) {
        if (typeof title !== 'string') return '';
        return title
            .replace(/([A-Z])/g, ' $1')   // Insert space before capitals
            .replace(/[_-]/g, ' ')         // Replace underscores/hyphens with spaces
            .replace(/\s+/g, ' ')          // Collapse multiple spaces
            .trim()
            .split(' ')
            .map(function(word) {
                return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
            })
            .join(' ');
    }

    /**
     * Convert string to URL-friendly slug
     * @param {string} text - Text to slugify
     * @returns {string} Slug
     */
    function slugify(text) {
        if (typeof text !== 'string') return '';
        return text
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    /**
     * Format a timestamp for display
     * @param {string|Date|number} timestamp - Timestamp to format
     * @param {Object} [options] - Formatting options
     * @param {boolean} [options.includeDate=false] - Include date portion
     * @param {boolean} [options.includeSeconds=false] - Include seconds
     * @returns {string} Formatted timestamp
     */
    function formatTimestamp(timestamp, options) {
        options = options || {};

        var date;
        if (timestamp instanceof Date) {
            date = timestamp;
        } else if (typeof timestamp === 'number') {
            date = new Date(timestamp);
        } else if (typeof timestamp === 'string') {
            date = new Date(timestamp);
        } else {
            date = new Date();
        }

        if (isNaN(date.getTime())) {
            return '';
        }

        var timeOptions = {
            hour: '2-digit',
            minute: '2-digit'
        };

        if (options.includeSeconds) {
            timeOptions.second = '2-digit';
        }

        if (options.includeDate) {
            timeOptions.year = 'numeric';
            timeOptions.month = 'short';
            timeOptions.day = 'numeric';
        }

        return date.toLocaleString(undefined, timeOptions);
    }

    /**
     * Format an ISO timestamp string (e.g., "2024-01-15T10:30:00" -> "10:30:00")
     * @param {string} isoString - ISO timestamp string
     * @returns {string} Time portion of the timestamp
     */
    function formatIsoTimestamp(isoString) {
        if (typeof isoString !== 'string') return '';
        // Extract time portion (handles both ISO and datetime strings)
        var timeMatch = isoString.match(/T?(\d{2}:\d{2}:\d{2})/);
        return timeMatch ? timeMatch[1] : isoString.slice(0, 19);
    }

    /**
     * Truncate text to a maximum length with ellipsis
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length
     * @param {string} [suffix='...'] - Suffix to append when truncated
     * @returns {string} Truncated text
     */
    function truncate(text, maxLength, suffix) {
        if (typeof text !== 'string') return '';
        suffix = suffix === undefined ? '...' : suffix;

        if (text.length <= maxLength) {
            return text;
        }

        return text.slice(0, maxLength - suffix.length) + suffix;
    }

    // =========================================================================
    // Function Utilities
    // =========================================================================

    /**
     * Debounce a function call
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    function debounce(func, wait) {
        var timeout;
        return function() {
            var context = this;
            var args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(context, args);
            }, wait);
        };
    }

    /**
     * Throttle a function call
     * @param {Function} func - Function to throttle
     * @param {number} limit - Minimum time between calls in milliseconds
     * @returns {Function} Throttled function
     */
    function throttle(func, limit) {
        var inThrottle;
        return function() {
            var context = this;
            var args = arguments;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(function() {
                    inThrottle = false;
                }, limit);
            }
        };
    }

    // =========================================================================
    // DOM Utilities
    // =========================================================================

    /**
     * Get an element by ID or return the element if already an element
     * @param {string|HTMLElement} elementOrId - Element or element ID
     * @returns {HTMLElement|null} The element or null
     */
    function getElement(elementOrId) {
        if (!elementOrId) return null;
        if (typeof elementOrId === 'string') {
            return document.getElementById(elementOrId);
        }
        return elementOrId;
    }

    /**
     * Safely get a data attribute value
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {string} key - Data attribute key (without 'data-' prefix)
     * @returns {string|null} Attribute value or null
     */
    function getDataAttribute(elementOrId, key) {
        var element = getElement(elementOrId);
        if (!element) return null;
        return element.dataset[key] || null;
    }

    /**
     * Scroll an element to the bottom
     * @param {HTMLElement|string} elementOrId - Element or element ID
     */
    function scrollToBottom(elementOrId) {
        var element = getElement(elementOrId);
        if (element) {
            element.scrollTop = element.scrollHeight;
        }
    }

    // =========================================================================
    // CSS Badge Classes (shared across modules)
    // =========================================================================

    /**
     * Get CSS classes for a status badge
     * @param {string} status - Status type
     * @returns {Object} Object with bg and text CSS classes
     */
    function getStatusBadgeClasses(status) {
        var classes = {
            completed: { bg: 'bg-green-100', text: 'text-green-800' },
            success: { bg: 'bg-green-100', text: 'text-green-800' },
            done: { bg: 'bg-green-100', text: 'text-green-800' },
            running: { bg: 'bg-blue-100', text: 'text-blue-800' },
            active: { bg: 'bg-blue-100', text: 'text-blue-800' },
            pending: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
            warning: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
            failed: { bg: 'bg-red-100', text: 'text-red-800' },
            error: { bg: 'bg-red-100', text: 'text-red-800' },
            info: { bg: 'bg-blue-100', text: 'text-blue-800' },
            debug: { bg: 'bg-purple-100', text: 'text-purple-800' },
            default: { bg: 'bg-gray-100', text: 'text-gray-800' }
        };
        return classes[status] || classes.default;
    }

    /**
     * Get CSS class string for a badge
     * @param {string} status - Status type
     * @returns {string} Combined CSS class string
     */
    function getBadgeClass(status) {
        var classes = getStatusBadgeClasses(status);
        return classes.bg + ' ' + classes.text;
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // HTML Escaping
        escapeHtml: escapeHtml,
        unescapeHtml: unescapeHtml,

        // Clipboard
        copyToClipboard: copyToClipboard,
        copyElementContent: copyElementContent,

        // Custom Events
        dispatchCustomEvent: dispatchCustomEvent,
        onCustomEvent: onCustomEvent,

        // ID Generation
        generateId: generateId,
        generateUuid: generateUuid,

        // Text Formatting
        formatTitle: formatTitle,
        slugify: slugify,
        formatTimestamp: formatTimestamp,
        formatIsoTimestamp: formatIsoTimestamp,
        truncate: truncate,

        // Function Utilities
        debounce: debounce,
        throttle: throttle,

        // DOM Utilities
        getElement: getElement,
        getDataAttribute: getDataAttribute,
        scrollToBottom: scrollToBottom,

        // Badge Classes
        getStatusBadgeClasses: getStatusBadgeClasses,
        getBadgeClass: getBadgeClass
    };
})();

// Expose globally for use by other modules
window.OrchestratorUtils = OrchestratorUtils;

// Also expose common utilities directly on window for convenience
window.escapeHtml = OrchestratorUtils.escapeHtml;
window.copyToClipboard = OrchestratorUtils.copyToClipboard;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OrchestratorUtils;
}
