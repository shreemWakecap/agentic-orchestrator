/**
 * Theme Module
 *
 * SDLC Orchestrator portal uses a light theme only.
 * This module is retained as a minimal stub for compatibility.
 *
 * Dark mode support has been removed - the application now uses
 * a consistent light theme throughout all components.
 */

const Theme = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const THEME = 'light';

    // =========================================================================
    // Public API
    // =========================================================================

    /**
     * Get the current theme
     * @returns {string} Always returns 'light'
     */
    function getTheme() {
        return THEME;
    }

    /**
     * Initialize the theme module
     * Ensures the document is set up for light theme
     */
    function init() {
        // Ensure no stale theme classes remain on the document
        document.documentElement.classList.remove('theme-transition');

        console.log('Theme: Light theme initialized');
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        getTheme: getTheme,
        init: init
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Theme;
}
