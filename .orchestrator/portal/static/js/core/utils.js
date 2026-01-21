/**
 * Core Utilities Module
 *
 * Shared utility functions used across the portal application.
 * This module provides common helpers for:
 * - HTML escaping (XSS prevention)
 * - Time formatting (elapsed time, clock format)
 * - Number formatting
 *
 * This module should be loaded FIRST in the script chain as other
 * modules depend on these utilities.
 *
 * @module CoreUtils
 */

const CoreUtils = (function() {
    'use strict';

    // =========================================================================
    // HTML Utilities
    // =========================================================================

    /**
     * Escape HTML special characters to prevent XSS attacks
     * @param {string} text - Text to escape
     * @returns {string} Escaped HTML-safe text
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Unescape HTML entities back to text
     * @param {string} html - HTML to unescape
     * @returns {string} Unescaped text
     */
    function unescapeHtml(html) {
        if (typeof html !== 'string') return '';
        var div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }

    // =========================================================================
    // Time Formatting Utilities
    // =========================================================================

    /**
     * Format elapsed time in human-readable format
     * Converts milliseconds to a readable string like "2h 30m" or "45s"
     *
     * @param {number} ms - Elapsed time in milliseconds
     * @returns {string} Formatted time string (e.g., "2d 5h", "3h 45m", "12m 30s", "45s")
     */
    function formatElapsedTime(ms) {
        if (typeof ms !== 'number' || isNaN(ms) || ms < 0) {
            return '0s';
        }

        var seconds = Math.floor(ms / 1000);
        var minutes = Math.floor(seconds / 60);
        var hours = Math.floor(minutes / 60);
        var days = Math.floor(hours / 24);

        if (days > 0) {
            return days + 'd ' + (hours % 24) + 'h';
        } else if (hours > 0) {
            return hours + 'h ' + (minutes % 60) + 'm';
        } else if (minutes > 0) {
            return minutes + 'm ' + (seconds % 60) + 's';
        } else {
            return seconds + 's';
        }
    }

    /**
     * Format seconds as a clock display (MM:SS or HH:MM:SS)
     *
     * @param {number} seconds - Time in seconds
     * @returns {string} Formatted time string (e.g., "05:30" or "1:05:30")
     */
    function formatElapsedClock(seconds) {
        if (typeof seconds !== 'number' || isNaN(seconds) || seconds < 0) {
            seconds = 0;
        }

        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor((seconds % 3600) / 60);
        var secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return hours + ':' + pad(minutes) + ':' + pad(secs);
        }
        return pad(minutes) + ':' + pad(secs);
    }

    /**
     * Pad a number with leading zero if needed
     *
     * @param {number} num - Number to pad
     * @returns {string} Padded string (e.g., "05" or "12")
     */
    function pad(num) {
        return num < 10 ? '0' + num : '' + num;
    }

    /**
     * Calculate elapsed time from an ISO date string to now
     *
     * @param {string|Date} dateStr - ISO date string or Date object
     * @returns {number} Elapsed time in milliseconds
     */
    function getElapsedSince(dateStr) {
        if (!dateStr) return 0;
        var date = dateStr instanceof Date ? dateStr : new Date(dateStr);
        if (isNaN(date.getTime())) return 0;
        return Math.max(0, Date.now() - date.getTime());
    }

    /**
     * Format a date as a relative time string (e.g., "2 minutes ago")
     *
     * @param {string|Date} dateStr - ISO date string or Date object
     * @returns {string} Relative time string
     */
    function formatRelativeTime(dateStr) {
        var elapsed = getElapsedSince(dateStr);
        return formatElapsedTime(elapsed) + ' ago';
    }

    // =========================================================================
    // DOM Utilities
    // =========================================================================

    /**
     * Safely query for an element, returning null if not found
     *
     * @param {string} selector - CSS selector
     * @param {Element} [context=document] - Context element to search within
     * @returns {Element|null} Found element or null
     */
    function $(selector, context) {
        return (context || document).querySelector(selector);
    }

    /**
     * Safely query for all matching elements
     *
     * @param {string} selector - CSS selector
     * @param {Element} [context=document] - Context element to search within
     * @returns {NodeList} List of matching elements
     */
    function $$(selector, context) {
        return (context || document).querySelectorAll(selector);
    }

    // =========================================================================
    // String Utilities
    // =========================================================================

    /**
     * Truncate a string to a maximum length, adding ellipsis if needed
     *
     * @param {string} str - String to truncate
     * @param {number} maxLength - Maximum length
     * @param {string} [suffix='...'] - Suffix to add when truncated
     * @returns {string} Truncated string
     */
    function truncate(str, maxLength, suffix) {
        if (typeof str !== 'string') return '';
        suffix = suffix || '...';
        if (str.length <= maxLength) return str;
        return str.substring(0, maxLength - suffix.length) + suffix;
    }

    /**
     * Generate a unique ID string
     *
     * @param {string} [prefix=''] - Optional prefix
     * @returns {string} Unique ID string
     */
    function uniqueId(prefix) {
        return (prefix || '') + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    }

    // =========================================================================
    // Object Utilities
    // =========================================================================

    /**
     * Deep merge objects (similar to Object.assign but recursive)
     *
     * @param {Object} target - Target object
     * @param {...Object} sources - Source objects to merge
     * @returns {Object} Merged object
     */
    function deepMerge(target) {
        var sources = Array.prototype.slice.call(arguments, 1);
        sources.forEach(function(source) {
            if (!source) return;
            Object.keys(source).forEach(function(key) {
                var sourceVal = source[key];
                var targetVal = target[key];
                if (isPlainObject(sourceVal) && isPlainObject(targetVal)) {
                    target[key] = deepMerge({}, targetVal, sourceVal);
                } else {
                    target[key] = sourceVal;
                }
            });
        });
        return target;
    }

    /**
     * Check if value is a plain object (not array, null, etc.)
     *
     * @param {*} value - Value to check
     * @returns {boolean} True if plain object
     */
    function isPlainObject(value) {
        return value !== null &&
               typeof value === 'object' &&
               Object.prototype.toString.call(value) === '[object Object]';
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // HTML utilities
        escapeHtml: escapeHtml,
        unescapeHtml: unescapeHtml,

        // Time formatting
        formatElapsedTime: formatElapsedTime,
        formatElapsedClock: formatElapsedClock,
        formatRelativeTime: formatRelativeTime,
        getElapsedSince: getElapsedSince,
        pad: pad,

        // DOM utilities
        $: $,
        $$: $$,

        // String utilities
        truncate: truncate,
        uniqueId: uniqueId,

        // Object utilities
        deepMerge: deepMerge,
        isPlainObject: isPlainObject
    };
})();

// Expose globally
window.CoreUtils = CoreUtils;

// Also expose common functions directly on window for convenience
// (maintains backwards compatibility with existing code)
window.escapeHtml = CoreUtils.escapeHtml;
window.formatElapsedTime = CoreUtils.formatElapsedTime;
window.formatElapsedClock = CoreUtils.formatElapsedClock;
window.pad = CoreUtils.pad;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CoreUtils;
}
