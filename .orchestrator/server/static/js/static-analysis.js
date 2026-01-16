/**
 * Static Analysis Module
 *
 * Provides functionality for displaying and interacting with static analysis results.
 * Includes:
 * - Analysis result display and formatting
 * - Copy-to-clipboard functionality for analysis data
 * - Collapsible sections for detailed findings
 * - Export capabilities
 *
 * DOM Requirements:
 * - #analysis-container for main analysis display
 * - [data-analysis-section] for collapsible sections
 * - [data-copy-target] for elements with copyable content
 */

const StaticAnalysis = (function() {
    'use strict';

    // Configuration
    const config = {
        animationDuration: 300,
        copySuccessTimeout: 2000,
        maxDisplayItems: 100
    };

    // State
    const state = {
        expandedSections: new Set(),
        analysisData: null,
        copyTimeouts: new Map()
    };

    // DOM Elements cache
    let elements = {
        container: null,
        sections: [],
        copyButtons: []
    };

    /**
     * Initialize the static analysis module
     * @param {Object} options - Configuration options
     * @param {string} [options.containerId='analysis-container'] - ID of main container
     * @param {Object} [options.data] - Initial analysis data to display
     */
    function init(options = {}) {
        cacheElements(options.containerId || 'analysis-container');
        bindEvents();

        if (options.data) {
            state.analysisData = options.data;
            render(options.data);
        }
    }

    /**
     * Cache DOM element references
     * @param {string} containerId - ID of the main container
     */
    function cacheElements(containerId) {
        elements.container = document.getElementById(containerId);
        elements.sections = document.querySelectorAll('[data-analysis-section]');
        elements.copyButtons = document.querySelectorAll('[data-copy-target]');
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        // Section toggle handlers
        elements.sections.forEach(function(section) {
            const header = section.querySelector('[data-section-header]');
            if (header) {
                header.addEventListener('click', function() {
                    toggleSection(section.dataset.analysisSection);
                });
            }
        });

        // Copy button handlers
        elements.copyButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                const targetId = button.dataset.copyTarget;
                copyToClipboard(targetId, button);
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + C on selected analysis item
            if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
                const selectedItem = document.querySelector('[data-analysis-item].selected');
                if (selectedItem) {
                    copyElementContent(selectedItem);
                }
            }

            // Escape to collapse all sections
            if (e.key === 'Escape') {
                collapseAll();
            }
        });
    }

    /**
     * Toggle a collapsible section
     * @param {string} sectionId - The section identifier
     */
    function toggleSection(sectionId) {
        const section = document.querySelector(`[data-analysis-section="${sectionId}"]`);
        if (!section) {
            console.warn('Section not found:', sectionId);
            return;
        }

        const content = section.querySelector('[data-section-content]');
        const icon = section.querySelector('[data-section-icon]');

        if (!content) return;

        if (state.expandedSections.has(sectionId)) {
            // Collapse
            content.style.maxHeight = content.scrollHeight + 'px';
            // Force reflow
            content.offsetHeight;
            content.style.maxHeight = '0';
            content.classList.remove('expanded');
            if (icon) icon.classList.remove('rotated');
            state.expandedSections.delete(sectionId);
        } else {
            // Expand
            content.style.maxHeight = content.scrollHeight + 'px';
            content.classList.add('expanded');
            if (icon) icon.classList.add('rotated');
            state.expandedSections.add(sectionId);

            // Remove max-height after transition for dynamic content
            setTimeout(function() {
                if (state.expandedSections.has(sectionId)) {
                    content.style.maxHeight = 'none';
                }
            }, config.animationDuration);
        }
    }

    /**
     * Expand a specific section
     * @param {string} sectionId - The section identifier
     */
    function expandSection(sectionId) {
        if (!state.expandedSections.has(sectionId)) {
            toggleSection(sectionId);
        }
    }

    /**
     * Collapse a specific section
     * @param {string} sectionId - The section identifier
     */
    function collapseSection(sectionId) {
        if (state.expandedSections.has(sectionId)) {
            toggleSection(sectionId);
        }
    }

    /**
     * Expand all sections
     */
    function expandAll() {
        elements.sections.forEach(function(section) {
            const sectionId = section.dataset.analysisSection;
            if (sectionId && !state.expandedSections.has(sectionId)) {
                toggleSection(sectionId);
            }
        });
    }

    /**
     * Collapse all sections
     */
    function collapseAll() {
        const expandedIds = Array.from(state.expandedSections);
        expandedIds.forEach(function(sectionId) {
            toggleSection(sectionId);
        });
    }

    /**
     * Copy content to clipboard
     * @param {string} targetId - ID of element containing content to copy
     * @param {HTMLElement} [triggerButton] - Button that triggered the copy
     */
    function copyToClipboard(targetId, triggerButton) {
        const targetElement = document.getElementById(targetId);
        if (!targetElement) {
            console.warn('Copy target not found:', targetId);
            return;
        }

        copyElementContent(targetElement, triggerButton);
    }

    /**
     * Copy element's content to clipboard
     * @param {HTMLElement} element - Element containing content to copy
     * @param {HTMLElement} [triggerButton] - Button that triggered the copy
     */
    function copyElementContent(element, triggerButton) {
        // Get text content, preferring data-copy-value if present
        const content = element.dataset.copyValue || element.textContent || element.innerText;

        if (!content) {
            console.warn('No content to copy');
            return;
        }

        // Use modern clipboard API with fallback
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(content.trim())
                .then(function() {
                    showCopySuccess(triggerButton || element);
                })
                .catch(function(err) {
                    console.error('Clipboard write failed:', err);
                    fallbackCopy(content.trim(), triggerButton || element);
                });
        } else {
            fallbackCopy(content.trim(), triggerButton || element);
        }
    }

    /**
     * Fallback copy method for older browsers
     * @param {string} text - Text to copy
     * @param {HTMLElement} feedbackElement - Element to show feedback on
     */
    function fallbackCopy(text, feedbackElement) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();

        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showCopySuccess(feedbackElement);
            } else {
                showCopyError(feedbackElement);
            }
        } catch (err) {
            console.error('Fallback copy failed:', err);
            showCopyError(feedbackElement);
        }

        document.body.removeChild(textarea);
    }

    /**
     * Show copy success feedback
     * @param {HTMLElement} element - Element to show feedback on
     */
    function showCopySuccess(element) {
        if (!element) return;

        // Clear any existing timeout
        const existingTimeout = state.copyTimeouts.get(element);
        if (existingTimeout) {
            clearTimeout(existingTimeout);
        }

        // Store original content
        const originalContent = element.innerHTML;
        const originalTitle = element.title;

        // Show success state
        element.classList.add('copy-success');
        if (element.dataset.copyText) {
            element.innerHTML = element.dataset.copySuccessText || 'Copied!';
        }
        element.title = 'Copied to clipboard';

        // Reset after timeout
        const timeout = setTimeout(function() {
            element.classList.remove('copy-success');
            if (element.dataset.copyText) {
                element.innerHTML = originalContent;
            }
            element.title = originalTitle;
            state.copyTimeouts.delete(element);
        }, config.copySuccessTimeout);

        state.copyTimeouts.set(element, timeout);
    }

    /**
     * Show copy error feedback
     * @param {HTMLElement} element - Element to show feedback on
     */
    function showCopyError(element) {
        if (!element) return;

        element.classList.add('copy-error');
        element.title = 'Failed to copy';

        setTimeout(function() {
            element.classList.remove('copy-error');
        }, config.copySuccessTimeout);
    }

    /**
     * Render analysis data to the container
     * @param {Object} data - Analysis data to render
     */
    function render(data) {
        if (!elements.container) {
            console.warn('Analysis container not found');
            return;
        }

        state.analysisData = data;

        // Clear existing content
        elements.container.innerHTML = '';

        if (!data || Object.keys(data).length === 0) {
            elements.container.innerHTML = '<div class="text-gray-500 text-center py-8">No analysis data available</div>';
            return;
        }

        // Render each analysis category
        Object.keys(data).forEach(function(category) {
            const categoryData = data[category];
            const section = createSection(category, categoryData);
            elements.container.appendChild(section);
        });

        // Re-cache sections after render
        elements.sections = elements.container.querySelectorAll('[data-analysis-section]');
        bindEvents();
    }

    /**
     * Create a collapsible section element
     * @param {string} title - Section title
     * @param {Object|Array} data - Section data
     * @returns {HTMLElement} Section element
     */
    function createSection(title, data) {
        const section = document.createElement('div');
        section.className = 'analysis-section border rounded-lg mb-4';
        section.dataset.analysisSection = slugify(title);

        const itemCount = Array.isArray(data) ? data.length : Object.keys(data).length;

        section.innerHTML = `
            <div class="flex items-center justify-between px-4 py-3 bg-gray-50 cursor-pointer hover:bg-gray-100 rounded-t-lg" data-section-header>
                <div class="flex items-center">
                    <svg class="w-4 h-4 mr-2 transition-transform" data-section-icon viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
                    </svg>
                    <span class="font-medium text-gray-900">${escapeHtml(formatTitle(title))}</span>
                </div>
                <div class="flex items-center">
                    <span class="text-sm text-gray-500 mr-2">${itemCount} item${itemCount !== 1 ? 's' : ''}</span>
                    <button class="p-1 hover:bg-gray-200 rounded" data-copy-target="${slugify(title)}-content" title="Copy section content">
                        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="overflow-hidden transition-all duration-300" style="max-height: 0;" data-section-content>
                <div class="px-4 py-3 border-t" id="${slugify(title)}-content" data-copy-value="${escapeHtml(JSON.stringify(data, null, 2))}">
                    ${renderSectionContent(data)}
                </div>
            </div>
        `;

        return section;
    }

    /**
     * Render section content based on data type
     * @param {Object|Array} data - Data to render
     * @returns {string} HTML string
     */
    function renderSectionContent(data) {
        if (Array.isArray(data)) {
            return renderList(data);
        } else if (typeof data === 'object' && data !== null) {
            return renderObject(data);
        } else {
            return `<span class="text-gray-700">${escapeHtml(String(data))}</span>`;
        }
    }

    /**
     * Render an array as a list
     * @param {Array} items - Items to render
     * @returns {string} HTML string
     */
    function renderList(items) {
        if (items.length === 0) {
            return '<span class="text-gray-500">No items</span>';
        }

        const displayItems = items.slice(0, config.maxDisplayItems);
        const hasMore = items.length > config.maxDisplayItems;

        let html = '<ul class="space-y-2">';
        displayItems.forEach(function(item, index) {
            html += `<li class="flex items-start" data-analysis-item data-index="${index}">`;
            html += '<span class="text-gray-400 mr-2">•</span>';
            if (typeof item === 'object' && item !== null) {
                html += `<div class="flex-1">${renderObject(item)}</div>`;
            } else {
                html += `<span class="text-gray-700">${escapeHtml(String(item))}</span>`;
            }
            html += '</li>';
        });
        html += '</ul>';

        if (hasMore) {
            html += `<div class="mt-2 text-sm text-gray-500">... and ${items.length - config.maxDisplayItems} more items</div>`;
        }

        return html;
    }

    /**
     * Render an object as key-value pairs
     * @param {Object} obj - Object to render
     * @returns {string} HTML string
     */
    function renderObject(obj) {
        const keys = Object.keys(obj);
        if (keys.length === 0) {
            return '<span class="text-gray-500">Empty object</span>';
        }

        let html = '<dl class="space-y-1">';
        keys.forEach(function(key) {
            const value = obj[key];
            html += '<div class="flex flex-wrap">';
            html += `<dt class="font-medium text-gray-600 mr-2">${escapeHtml(key)}:</dt>`;
            if (typeof value === 'object' && value !== null) {
                html += `<dd class="text-gray-700 w-full mt-1 ml-4">${renderSectionContent(value)}</dd>`;
            } else {
                html += `<dd class="text-gray-700">${escapeHtml(String(value))}</dd>`;
            }
            html += '</div>';
        });
        html += '</dl>';

        return html;
    }

    /**
     * Format a title string for display
     * @param {string} title - Title to format
     * @returns {string} Formatted title
     */
    function formatTitle(title) {
        return title
            .replace(/([A-Z])/g, ' $1')
            .replace(/[_-]/g, ' ')
            .replace(/\s+/g, ' ')
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
        return text
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get current analysis data
     * @returns {Object|null} Current analysis data
     */
    function getData() {
        return state.analysisData;
    }

    /**
     * Export analysis data as JSON
     * @returns {string} JSON string
     */
    function exportAsJson() {
        return JSON.stringify(state.analysisData, null, 2);
    }

    /**
     * Check if a section is expanded
     * @param {string} sectionId - Section identifier
     * @returns {boolean} True if expanded
     */
    function isSectionExpanded(sectionId) {
        return state.expandedSections.has(sectionId);
    }

    /**
     * Get all expanded section IDs
     * @returns {string[]} Array of expanded section IDs
     */
    function getExpandedSections() {
        return Array.from(state.expandedSections);
    }

    /**
     * Reset module state
     */
    function reset() {
        state.expandedSections.clear();
        state.analysisData = null;
        state.copyTimeouts.forEach(function(timeout) {
            clearTimeout(timeout);
        });
        state.copyTimeouts.clear();
    }

    // Public API
    return {
        init: init,
        render: render,
        toggleSection: toggleSection,
        expandSection: expandSection,
        collapseSection: collapseSection,
        expandAll: expandAll,
        collapseAll: collapseAll,
        copyToClipboard: copyToClipboard,
        getData: getData,
        exportAsJson: exportAsJson,
        isSectionExpanded: isSectionExpanded,
        getExpandedSections: getExpandedSections,
        reset: reset,
        // Expose utilities for external use
        escapeHtml: escapeHtml,
        formatTitle: formatTitle,
        slugify: slugify
    };
})();

// Auto-initialize from data attributes on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('analysis-container') || document.querySelector('[data-analysis-init]');

    if (container) {
        const containerId = container.id || 'analysis-container';

        // Check for inline data
        let initialData = null;
        const dataElement = document.getElementById('analysis-data');
        if (dataElement) {
            try {
                initialData = JSON.parse(dataElement.textContent);
            } catch (e) {
                console.warn('Failed to parse analysis data:', e);
            }
        }

        StaticAnalysis.init({
            containerId: containerId,
            data: initialData
        });
    }
});

// Expose globally for onclick handlers and external access
window.StaticAnalysis = StaticAnalysis;

// Expose convenience functions globally
window.toggleAnalysisSection = StaticAnalysis.toggleSection;
window.expandAllAnalysis = StaticAnalysis.expandAll;
window.collapseAllAnalysis = StaticAnalysis.collapseAll;
window.copyAnalysisContent = StaticAnalysis.copyToClipboard;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StaticAnalysis;
}
