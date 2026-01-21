/**
 * Sync Section Module
 *
 * Handles the collapsible sync section functionality on the dashboard.
 * Manages collapsible state with localStorage persistence.
 *
 * Features:
 * - Toggle expand/collapse state
 * - Persist state to localStorage
 * - Initialize state from localStorage on page load
 *
 * DOM Requirements:
 * - #sync-section - Main section container
 * - #sync-section-content - Collapsible content container
 * - #sync-section-chevron - Chevron icon for visual feedback
 *
 * @module SyncSection
 */

const SyncSection = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        storageKey: 'dashboard-sync-collapsed',
        defaultCollapsed: true
    };

    // =========================================================================
    // State
    // =========================================================================

    let isInitialized = false;

    // =========================================================================
    // Core Functions
    // =========================================================================

    /**
     * Toggle the sync section expand/collapse state
     */
    function toggle() {
        var section = document.getElementById('sync-section');
        var content = document.getElementById('sync-section-content');

        if (!section || !content) return;

        var isCollapsed = section.classList.contains('collapsed');

        if (isCollapsed) {
            // Expand
            section.classList.remove('collapsed');
            content.classList.remove('collapsed');
            localStorage.setItem(CONFIG.storageKey, 'false');
        } else {
            // Collapse
            section.classList.add('collapsed');
            content.classList.add('collapsed');
            localStorage.setItem(CONFIG.storageKey, 'true');
        }

        updateChevronRotation(!isCollapsed);
    }

    /**
     * Initialize the sync section state from localStorage
     */
    function init() {
        if (isInitialized) return;

        var section = document.getElementById('sync-section');
        var content = document.getElementById('sync-section-content');

        if (!section || !content) return;

        // Check localStorage for saved state, default to collapsed
        var savedState = localStorage.getItem(CONFIG.storageKey);
        var shouldBeCollapsed = savedState === null ? CONFIG.defaultCollapsed : savedState === 'true';

        if (shouldBeCollapsed) {
            section.classList.add('collapsed');
            content.classList.add('collapsed');
        } else {
            section.classList.remove('collapsed');
            content.classList.remove('collapsed');
        }

        updateChevronRotation(shouldBeCollapsed);
        isInitialized = true;
    }

    /**
     * Update chevron rotation based on collapsed state
     * @param {boolean} isCollapsed - Whether section is collapsed
     */
    function updateChevronRotation(isCollapsed) {
        var chevron = document.getElementById('sync-section-chevron');
        if (chevron) {
            if (isCollapsed) {
                chevron.style.transform = 'rotate(0deg)';
            } else {
                chevron.style.transform = 'rotate(180deg)';
            }
        }
    }

    /**
     * Get the current collapsed state
     * @returns {boolean} True if collapsed
     */
    function isCollapsed() {
        var section = document.getElementById('sync-section');
        return section ? section.classList.contains('collapsed') : CONFIG.defaultCollapsed;
    }

    /**
     * Expand the sync section
     */
    function expand() {
        if (isCollapsed()) {
            toggle();
        }
    }

    /**
     * Collapse the sync section
     */
    function collapse() {
        if (!isCollapsed()) {
            toggle();
        }
    }

    // =========================================================================
    // Auto-initialization
    // =========================================================================

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM already loaded
        init();
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        toggle: toggle,
        expand: expand,
        collapse: collapse,
        isCollapsed: isCollapsed,
        CONFIG: CONFIG
    };
})();

// Expose globally
window.SyncSection = SyncSection;

// Expose toggle function globally for onclick handlers in HTML
window.toggleSyncSection = function() {
    return SyncSection.toggle();
};

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SyncSection;
}
