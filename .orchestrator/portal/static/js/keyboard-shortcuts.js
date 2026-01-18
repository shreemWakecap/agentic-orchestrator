/**
 * Keyboard Shortcuts Module
 *
 * Central registry for all keyboard shortcuts in the SDLC Orchestrator.
 * This module provides:
 * - Priority-based shortcut resolution (modal > input > page-level)
 * - Conflict detection and handling
 * - Registration and unregistration of shortcuts
 * - Modifier key support (Ctrl, Alt, Shift, Meta)
 * - Browser shortcut preservation (only overrides when explicitly registered)
 *
 * Priority Levels:
 *   100 - Modal dialogs (highest priority)
 *   50  - Focused inputs and form elements
 *   10  - Page-level shortcuts (default)
 *   0   - Global fallback shortcuts
 *
 * Browser Shortcut Policy:
 *   The following common browser shortcuts are PRESERVED by default and will
 *   only be overridden if an explicit handler is registered for them:
 *
 *   - Ctrl+S  : Save page (browser default)
 *   - Ctrl+P  : Print page (browser default)
 *   - Ctrl+F  : Find in page (browser default)
 *   - Ctrl+G  : Find next (browser default)
 *   - Ctrl+H  : History (browser default)
 *   - Ctrl+J  : Downloads (browser default)
 *   - Ctrl+D  : Bookmark (browser default)
 *   - Ctrl+U  : View source (browser default)
 *   - Ctrl+O  : Open file (browser default)
 *   - Ctrl+N  : New window (browser default)
 *   - Ctrl+T  : New tab (browser default)
 *   - Ctrl+W  : Close tab (browser default)
 *   - Ctrl+R  : Reload (browser default)
 *   - Ctrl+L  : Focus address bar (browser default)
 *   - F5      : Reload (browser default)
 *   - F11     : Fullscreen (browser default)
 *   - F12     : Developer tools (browser default)
 *
 *   To override any of these, register a handler that returns `true`:
 *   KeyboardShortcuts.registerShortcut('ctrl+s', function(e) {
 *       // Custom save logic
 *       return true; // Prevents browser default
 *   }, 10);
 *
 * Page-Specific Shortcuts:
 *   - Ctrl+R : Resume plan (on plan detail page when plan is resumable)
 *              Overrides browser refresh when recovery UI is active.
 *              See: plan-recovery.js
 *
 * Usage:
 * KeyboardShortcuts.registerShortcut('ctrl+s', handler, 10);
 * KeyboardShortcuts.unregisterShortcut('ctrl+s');
 */

const KeyboardShortcuts = (function() {
    'use strict';

    // =========================================================================
    // Constants
    // =========================================================================

    /**
     * Priority levels for shortcut resolution
     */
    const PRIORITY = {
        MODAL: 100,      // Modal dialogs get highest priority
        INPUT: 50,       // Focused inputs and form elements
        PAGE: 10,        // Page-level shortcuts (default)
        GLOBAL: 0        // Global fallback shortcuts
    };

    /**
     * Keys that should be ignored when an input is focused
     */
    const INPUT_FOCUSED_ALLOWED_MODIFIERS = ['ctrl', 'alt', 'meta'];

    /**
     * Common browser shortcuts that should be preserved unless explicitly overridden.
     * These shortcuts will NOT have preventDefault called unless a handler is registered
     * and that handler explicitly returns `true`.
     *
     * Format: normalized key strings (sorted modifiers + key)
     */
    const BROWSER_DEFAULT_SHORTCUTS = [
        // Save, Print, Find
        'ctrl+s',      // Save page
        'ctrl+p',      // Print
        'ctrl+f',      // Find in page
        'ctrl+g',      // Find next
        'ctrl+shift+g', // Find previous

        // Navigation/Tabs
        'ctrl+h',      // History
        'ctrl+j',      // Downloads
        'ctrl+d',      // Bookmark
        'ctrl+u',      // View source
        'ctrl+o',      // Open file
        'ctrl+n',      // New window
        'ctrl+t',      // New tab
        'ctrl+w',      // Close tab
        'ctrl+r',      // Reload
        'ctrl+l',      // Focus address bar
        'ctrl+shift+t', // Reopen closed tab

        // Function keys
        'f5',          // Reload
        'f11',         // Fullscreen
        'f12',         // Developer tools

        // Clipboard (usually browser handles these)
        'ctrl+c',      // Copy
        'ctrl+x',      // Cut
        'ctrl+v',      // Paste
        'ctrl+a',      // Select all
        'ctrl+z',      // Undo
        'ctrl+y',      // Redo
        'ctrl+shift+z' // Redo (alternative)
    ];

    // =========================================================================
    // State
    // =========================================================================

    /**
     * Registry of all registered shortcuts
     * Map of normalized key -> array of {handler, priority, id}
     */
    var shortcuts = {};

    /**
     * Counter for generating unique shortcut IDs
     */
    var shortcutIdCounter = 0;

    /**
     * Whether the module has been initialized
     */
    var initialized = false;

    /**
     * Track currently active modal count
     */
    var activeModalCount = 0;

    // =========================================================================
    // Key Normalization
    // =========================================================================

    /**
     * Normalize a key combination string for consistent comparison
     * @param {string} key - Key combination (e.g., 'Ctrl+S', 'ctrl+shift+a')
     * @returns {string} Normalized key string (lowercase, sorted modifiers)
     */
    function normalizeKey(key) {
        if (typeof key !== 'string') return '';

        var parts = key.toLowerCase().split('+').map(function(part) {
            return part.trim();
        }).filter(function(part) {
            return part.length > 0;
        });

        // Separate modifiers and main key
        var modifiers = [];
        var mainKey = '';

        parts.forEach(function(part) {
            if (part === 'ctrl' || part === 'control') {
                modifiers.push('ctrl');
            } else if (part === 'alt') {
                modifiers.push('alt');
            } else if (part === 'shift') {
                modifiers.push('shift');
            } else if (part === 'meta' || part === 'cmd' || part === 'command' || part === 'win') {
                modifiers.push('meta');
            } else {
                mainKey = part;
            }
        });

        // Sort modifiers for consistent comparison
        modifiers.sort();

        // Build normalized key string
        if (modifiers.length > 0) {
            return modifiers.join('+') + '+' + mainKey;
        }
        return mainKey;
    }

    /**
     * Build a normalized key string from a KeyboardEvent
     * @param {KeyboardEvent} event - The keyboard event
     * @returns {string} Normalized key string
     */
    function keyFromEvent(event) {
        var modifiers = [];

        if (event.ctrlKey) modifiers.push('ctrl');
        if (event.altKey) modifiers.push('alt');
        if (event.shiftKey) modifiers.push('shift');
        if (event.metaKey) modifiers.push('meta');

        modifiers.sort();

        // Normalize the key
        var key = event.key.toLowerCase();

        // Handle special keys
        if (key === ' ') key = 'space';
        if (key === 'escape') key = 'esc';
        if (key === 'arrowup') key = 'up';
        if (key === 'arrowdown') key = 'down';
        if (key === 'arrowleft') key = 'left';
        if (key === 'arrowright') key = 'right';

        if (modifiers.length > 0) {
            return modifiers.join('+') + '+' + key;
        }
        return key;
    }

    // =========================================================================
    // Input Focus Detection
    // =========================================================================

    /**
     * Check if an element is an input-like element
     * @param {HTMLElement} element - Element to check
     * @returns {boolean} Whether element is input-like
     */
    function isInputElement(element) {
        if (!element) return false;

        var tagName = element.tagName.toLowerCase();
        if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
            return true;
        }

        // Check for contenteditable
        if (element.isContentEditable) {
            return true;
        }

        return false;
    }

    /**
     * Check if shortcut should be blocked because input is focused
     * @param {KeyboardEvent} event - The keyboard event
     * @returns {boolean} Whether to block the shortcut
     */
    function shouldBlockForInput(event) {
        var activeElement = document.activeElement;

        if (!isInputElement(activeElement)) {
            return false;
        }

        // Allow shortcuts with certain modifiers even when input is focused
        var hasAllowedModifier = event.ctrlKey || event.altKey || event.metaKey;

        // Block single keys and shift-only combinations in inputs
        if (!hasAllowedModifier) {
            return true;
        }

        return false;
    }

    /**
     * Check if a normalized key is a common browser shortcut
     * @param {string} normalizedKey - Normalized key string
     * @returns {boolean} Whether this is a browser default shortcut
     */
    function isBrowserDefaultShortcut(normalizedKey) {
        return BROWSER_DEFAULT_SHORTCUTS.indexOf(normalizedKey) !== -1;
    }

    // =========================================================================
    // Shortcut Registration
    // =========================================================================

    /**
     * Register a keyboard shortcut
     * @param {string} key - Key combination (e.g., 'ctrl+s', 'esc', 'shift+?')
     * @param {Function} handler - Handler function. Receives (event) and returns true to prevent default
     * @param {number} [priority=10] - Priority level (higher = more important)
     * @returns {string} Unique shortcut ID for later removal
     */
    function registerShortcut(key, handler, priority) {
        if (typeof key !== 'string' || typeof handler !== 'function') {
            console.warn('KeyboardShortcuts: Invalid key or handler');
            return null;
        }

        priority = typeof priority === 'number' ? priority : PRIORITY.PAGE;

        var normalizedKey = normalizeKey(key);
        if (!normalizedKey) {
            console.warn('KeyboardShortcuts: Could not normalize key:', key);
            return null;
        }

        // Initialize array for this key if needed
        if (!shortcuts[normalizedKey]) {
            shortcuts[normalizedKey] = [];
        }

        // Generate unique ID
        var id = 'shortcut_' + (++shortcutIdCounter);

        // Add shortcut entry
        shortcuts[normalizedKey].push({
            id: id,
            handler: handler,
            priority: priority,
            key: key // Original key for debugging
        });

        // Sort by priority (descending)
        shortcuts[normalizedKey].sort(function(a, b) {
            return b.priority - a.priority;
        });

        // Ensure event listener is attached
        ensureInitialized();

        return id;
    }

    /**
     * Unregister a keyboard shortcut
     * @param {string} keyOrId - Key combination or shortcut ID
     * @returns {boolean} Whether shortcut was found and removed
     */
    function unregisterShortcut(keyOrId) {
        if (typeof keyOrId !== 'string') {
            return false;
        }

        // Check if it's an ID
        if (keyOrId.indexOf('shortcut_') === 0) {
            return unregisterById(keyOrId);
        }

        // It's a key - remove all shortcuts for this key
        var normalizedKey = normalizeKey(keyOrId);
        if (shortcuts[normalizedKey]) {
            delete shortcuts[normalizedKey];
            return true;
        }

        return false;
    }

    /**
     * Unregister a shortcut by its ID
     * @param {string} id - Shortcut ID
     * @returns {boolean} Whether shortcut was found and removed
     */
    function unregisterById(id) {
        for (var key in shortcuts) {
            if (shortcuts.hasOwnProperty(key)) {
                var entries = shortcuts[key];
                for (var i = 0; i < entries.length; i++) {
                    if (entries[i].id === id) {
                        entries.splice(i, 1);
                        // Clean up empty arrays
                        if (entries.length === 0) {
                            delete shortcuts[key];
                        }
                        return true;
                    }
                }
            }
        }
        return false;
    }

    // =========================================================================
    // Event Handling
    // =========================================================================

    /**
     * Handle a keydown event
     *
     * Browser Shortcut Preservation:
     * For common browser shortcuts (Ctrl+S, Ctrl+P, Ctrl+F, etc.), we only call
     * preventDefault() if a registered handler explicitly returns `true`.
     * This ensures browser defaults are preserved unless intentionally overridden.
     *
     * @param {KeyboardEvent} event - The keyboard event
     */
    function handleKeydown(event) {
        // Build the key string from the event
        var eventKey = keyFromEvent(event);

        // Check if this is a browser default shortcut
        var isBrowserShortcut = isBrowserDefaultShortcut(eventKey);

        // Check if we have any shortcuts for this key
        var entries = shortcuts[eventKey];
        if (!entries || entries.length === 0) {
            // No registered handlers - let browser handle it
            return;
        }

        // Check if input is focused and should block
        if (shouldBlockForInput(event)) {
            return;
        }

        // Find highest priority handler that wants to handle this
        for (var i = 0; i < entries.length; i++) {
            var entry = entries[i];

            // Skip modal-priority shortcuts if no modal is active
            if (entry.priority >= PRIORITY.MODAL && activeModalCount === 0) {
                continue;
            }

            try {
                var result = entry.handler(event);

                // If handler returns true, prevent default and stop propagation
                // This is the ONLY way to override browser default shortcuts
                if (result === true) {
                    event.preventDefault();
                    event.stopPropagation();
                    return;
                }

                // If handler returns false explicitly, continue to next handler
                if (result === false) {
                    continue;
                }

                // If handler returns nothing (undefined):
                // - For browser shortcuts: allow browser default (don't preventDefault)
                // - For non-browser shortcuts: assume handled, stop processing
                if (isBrowserShortcut) {
                    // Handler ran but didn't explicitly return true,
                    // so preserve browser default behavior
                    return;
                }

                // Non-browser shortcut: handler ran, stop processing
                return;
            } catch (err) {
                console.error('KeyboardShortcuts: Handler error for', eventKey, err);
            }
        }
    }

    /**
     * Ensure the module is initialized with event listener
     */
    function ensureInitialized() {
        if (initialized) return;

        document.addEventListener('keydown', handleKeydown, true);
        initialized = true;
    }

    // =========================================================================
    // Modal Management
    // =========================================================================

    /**
     * Notify that a modal has been opened
     * Call this when opening a modal to enable modal-priority shortcuts
     */
    function modalOpened() {
        activeModalCount++;
    }

    /**
     * Notify that a modal has been closed
     * Call this when closing a modal to disable modal-priority shortcuts
     */
    function modalClosed() {
        activeModalCount = Math.max(0, activeModalCount - 1);
    }

    // =========================================================================
    // Utility Methods
    // =========================================================================

    /**
     * Get all registered shortcuts (for debugging)
     * @returns {Object} Copy of shortcuts registry
     */
    function getRegisteredShortcuts() {
        var result = {};
        for (var key in shortcuts) {
            if (shortcuts.hasOwnProperty(key)) {
                result[key] = shortcuts[key].map(function(entry) {
                    return {
                        id: entry.id,
                        priority: entry.priority,
                        key: entry.key
                    };
                });
            }
        }
        return result;
    }

    /**
     * Clear all registered shortcuts
     * Primarily for testing purposes
     */
    function clearAll() {
        shortcuts = {};
        shortcutIdCounter = 0;
        activeModalCount = 0;
    }

    /**
     * Check if a shortcut is registered
     * @param {string} key - Key combination to check
     * @returns {boolean} Whether shortcut is registered
     */
    function hasShortcut(key) {
        var normalizedKey = normalizeKey(key);
        return !!(shortcuts[normalizedKey] && shortcuts[normalizedKey].length > 0);
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // Priority constants
        PRIORITY: PRIORITY,

        // Browser default shortcuts list (for reference/debugging)
        BROWSER_DEFAULT_SHORTCUTS: BROWSER_DEFAULT_SHORTCUTS,

        // Core methods
        registerShortcut: registerShortcut,
        unregisterShortcut: unregisterShortcut,
        handleKeydown: handleKeydown,

        // Modal management
        modalOpened: modalOpened,
        modalClosed: modalClosed,

        // Utility methods
        normalizeKey: normalizeKey,
        hasShortcut: hasShortcut,
        isBrowserDefaultShortcut: isBrowserDefaultShortcut,
        getRegisteredShortcuts: getRegisteredShortcuts,
        clearAll: clearAll
    };
})();

// Expose globally for use by other modules
window.KeyboardShortcuts = KeyboardShortcuts;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KeyboardShortcuts;
}
