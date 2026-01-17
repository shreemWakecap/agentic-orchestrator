/**
 * Dark Mode Theme Module
 *
 * Handles dark mode toggle functionality for the SDLC Orchestrator portal.
 * Features:
 * - Toggle between light and dark modes
 * - Persist preference in localStorage
 * - Detect system color scheme preference
 * - Smooth transitions on mode change
 *
 * Usage:
 * Include this file after common.js. The module auto-initializes on DOMContentLoaded.
 * Manual control is available via the global DarkMode object.
 */

const DarkMode = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const STORAGE_KEY = 'orchestrator-theme';
    const DARK_CLASS = 'dark';
    const TRANSITION_CLASS = 'theme-transition';
    const TRANSITION_DURATION = 200; // milliseconds

    // =========================================================================
    // State
    // =========================================================================

    let initialized = false;

    // =========================================================================
    // Core Functions
    // =========================================================================

    /**
     * Check if dark mode is currently enabled
     * @returns {boolean} True if dark mode is active
     */
    function isEnabled() {
        return document.documentElement.classList.contains(DARK_CLASS);
    }

    /**
     * Get the user's stored preference
     * @returns {string|null} 'dark', 'light', or null if not set
     */
    function getStoredPreference() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            console.warn('DarkMode: Unable to access localStorage:', e);
            return null;
        }
    }

    /**
     * Store the user's preference
     * @param {string} theme - 'dark' or 'light'
     */
    function setStoredPreference(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {
            console.warn('DarkMode: Unable to store preference:', e);
        }
    }

    /**
     * Detect system color scheme preference
     * @returns {boolean} True if system prefers dark mode
     */
    function getSystemPreference() {
        if (window.matchMedia) {
            return window.matchMedia('(prefers-color-scheme: dark)').matches;
        }
        return false;
    }

    /**
     * Apply theme with smooth transition
     * @param {boolean} enableDark - Whether to enable dark mode
     * @param {boolean} [animate=true] - Whether to animate the transition
     */
    function applyTheme(enableDark, animate) {
        animate = animate !== false;

        if (animate) {
            // Add transition class for smooth change
            document.documentElement.classList.add(TRANSITION_CLASS);
        }

        if (enableDark) {
            document.documentElement.classList.add(DARK_CLASS);
        } else {
            document.documentElement.classList.remove(DARK_CLASS);
        }

        if (animate) {
            // Remove transition class after animation completes
            setTimeout(function() {
                document.documentElement.classList.remove(TRANSITION_CLASS);
            }, TRANSITION_DURATION);
        }

        // Dispatch custom event for other modules to react
        if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.dispatchCustomEvent) {
            OrchestratorUtils.dispatchCustomEvent('theme', 'change', {
                dark: enableDark,
                theme: enableDark ? 'dark' : 'light'
            });
        }
    }

    /**
     * Toggle dark mode on/off
     * @returns {boolean} New state (true if dark mode is now enabled)
     */
    function toggle() {
        var newState = !isEnabled();
        applyTheme(newState);
        setStoredPreference(newState ? 'dark' : 'light');
        updateToggleButtons(newState);
        return newState;
    }

    /**
     * Set dark mode to a specific state
     * @param {boolean} enableDark - Whether to enable dark mode
     */
    function setMode(enableDark) {
        applyTheme(enableDark);
        setStoredPreference(enableDark ? 'dark' : 'light');
        updateToggleButtons(enableDark);
    }

    // =========================================================================
    // UI Binding
    // =========================================================================

    /**
     * Update all toggle button states
     * @param {boolean} isDark - Current dark mode state
     */
    function updateToggleButtons(isDark) {
        // Update buttons with data-theme-toggle attribute
        var toggleButtons = document.querySelectorAll('[data-theme-toggle]');
        toggleButtons.forEach(function(button) {
            var sunIcon = button.querySelector('[data-theme-icon="sun"]');
            var moonIcon = button.querySelector('[data-theme-icon="moon"]');

            if (sunIcon && moonIcon) {
                if (isDark) {
                    sunIcon.classList.remove('hidden');
                    moonIcon.classList.add('hidden');
                } else {
                    sunIcon.classList.add('hidden');
                    moonIcon.classList.remove('hidden');
                }
            }

            // Update aria-pressed for accessibility
            button.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            button.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        });
    }

    /**
     * Bind click handlers to toggle buttons
     */
    function bindToggleButtons() {
        var toggleButtons = document.querySelectorAll('[data-theme-toggle]');
        toggleButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                toggle();
            });
        });
    }

    /**
     * Listen for system preference changes
     */
    function listenForSystemChanges() {
        if (window.matchMedia) {
            var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

            // Handle system preference changes (only if user hasn't set a preference)
            var handler = function(e) {
                var storedPref = getStoredPreference();
                if (!storedPref) {
                    applyTheme(e.matches);
                    updateToggleButtons(e.matches);
                }
            };

            // Modern browsers
            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener('change', handler);
            } else if (mediaQuery.addListener) {
                // Older Safari
                mediaQuery.addListener(handler);
            }
        }
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the dark mode module
     * Determines initial theme based on: stored preference > system preference > light
     */
    function init() {
        if (initialized) {
            return;
        }

        // Determine initial theme
        var storedPref = getStoredPreference();
        var shouldBeDark;

        if (storedPref === 'dark') {
            shouldBeDark = true;
        } else if (storedPref === 'light') {
            shouldBeDark = false;
        } else {
            // No stored preference, use system preference
            shouldBeDark = getSystemPreference();
        }

        // Apply theme without animation on initial load
        applyTheme(shouldBeDark, false);

        // Setup UI bindings
        bindToggleButtons();
        updateToggleButtons(shouldBeDark);

        // Listen for system preference changes
        listenForSystemChanges();

        initialized = true;

        // Dispatch initialized event
        if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.dispatchCustomEvent) {
            OrchestratorUtils.dispatchCustomEvent('theme', 'initialized', {
                dark: shouldBeDark,
                theme: shouldBeDark ? 'dark' : 'light'
            });
        }
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM already ready
        init();
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        toggle: toggle,
        isEnabled: isEnabled,
        setMode: setMode,
        getSystemPreference: getSystemPreference
    };
})();

// Expose globally for use by other modules
window.DarkMode = DarkMode;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DarkMode;
}
