/**
 * Codebase Explorer Module
 * Handles codebase exploration and understanding operations
 *
 * Features:
 * - Submit exploration queries about the codebase
 * - Display exploration results with code snippets
 * - Architecture overview navigation
 * - Domain and file detail exploration
 * - Syntax highlighting for code blocks
 *
 * Usage:
 *   CodebaseExplorer.init();
 *   CodebaseExplorer.submitExploration('How does authentication work?', 'architecture');
 */

const CodebaseExplorer = (function() {
    'use strict';

    // ==========================================================================
    // CONFIGURATION
    // ==========================================================================

    const CONFIG = {
        API_BASE: '/api/explore',
        DEBOUNCE_DELAY: 300,
        ANIMATION_DURATION: 300,
        MAX_SNIPPET_LINES: 50
    };

    // ==========================================================================
    // STATE MANAGEMENT
    // ==========================================================================

    const state = {
        currentQuery: '',
        currentScope: 'all',
        explorationHistory: [],
        isLoading: false,
        architectureData: null,
        currentResults: null,
        expandedSections: new Set()
    };

    // ==========================================================================
    // DOM ELEMENT CACHE
    // ==========================================================================

    const elements = {
        // Containers
        explorerContainer: null,
        resultsContainer: null,
        architecturePanel: null,

        // Search/Query
        queryInput: null,
        scopeSelect: null,
        submitBtn: null,

        // Navigation
        domainsList: null,
        fileTree: null,

        // Results
        resultsArea: null,
        loadingIndicator: null,
        emptyState: null
    };

    // ==========================================================================
    // SYNTAX HIGHLIGHTING
    // ==========================================================================

    const SyntaxHighlighter = {
        // Language detection patterns
        languagePatterns: {
            python: /\.py$/i,
            javascript: /\.(js|mjs|cjs)$/i,
            typescript: /\.(ts|tsx)$/i,
            html: /\.(html|htm)$/i,
            css: /\.css$/i,
            json: /\.json$/i,
            yaml: /\.(yml|yaml)$/i,
            sql: /\.sql$/i,
            markdown: /\.(md|markdown)$/i,
            shell: /\.(sh|bash)$/i
        },

        // Token patterns for basic highlighting
        tokenPatterns: {
            python: {
                keyword: /\b(def|class|if|elif|else|for|while|try|except|finally|with|as|import|from|return|yield|raise|pass|break|continue|and|or|not|in|is|lambda|None|True|False|async|await|global|nonlocal)\b/g,
                string: /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
                comment: /#.*/g,
                function: /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g,
                decorator: /@[a-zA-Z_][a-zA-Z0-9_.]*/g,
                number: /\b\d+\.?\d*\b/g
            },
            javascript: {
                keyword: /\b(const|let|var|function|class|if|else|for|while|do|switch|case|break|continue|return|try|catch|finally|throw|new|typeof|instanceof|this|super|extends|import|export|from|default|async|await|yield|null|undefined|true|false)\b/g,
                string: /(`[\s\S]*?`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
                comment: /(\/\/.*|\/\*[\s\S]*?\*\/)/g,
                function: /\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(/g,
                number: /\b\d+\.?\d*\b/g
            },
            sql: {
                keyword: /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|IS|NULL|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|VIEW|DROP|ALTER|ADD|CONSTRAINT|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|DEFAULT|CASCADE|DISTINCT|UNION|ALL|EXISTS|BETWEEN|LIKE|CASE|WHEN|THEN|ELSE|END)\b/gi,
                string: /('(?:[^'\\]|\\.)*')/g,
                comment: /(--.*|\/\*[\s\S]*?\*\/)/g,
                number: /\b\d+\.?\d*\b/g
            }
        },

        /**
         * Detect language from file path
         * @param {string} filePath - File path
         * @returns {string} Language identifier
         */
        detectLanguage(filePath) {
            for (const [lang, pattern] of Object.entries(this.languagePatterns)) {
                if (pattern.test(filePath)) {
                    return lang;
                }
            }
            return 'text';
        },

        /**
         * Apply syntax highlighting to code
         * @param {string} code - Code to highlight
         * @param {string} language - Language identifier
         * @returns {string} Highlighted HTML
         */
        highlight(code, language) {
            if (!code) return '';

            // Escape HTML first
            let escaped = UI.escapeHtml(code);

            // Get patterns for this language
            const patterns = this.tokenPatterns[language];
            if (!patterns) {
                return escaped;
            }

            // Apply highlighting in specific order to avoid conflicts
            // Process strings and comments first as they may contain keywords

            // Temporarily replace strings and comments with placeholders
            const placeholders = [];
            let placeholderIndex = 0;

            if (patterns.string) {
                escaped = escaped.replace(patterns.string, (match) => {
                    const placeholder = `__PLACEHOLDER_${placeholderIndex++}__`;
                    placeholders.push({ placeholder, html: `<span class="code-string">${match}</span>` });
                    return placeholder;
                });
            }

            if (patterns.comment) {
                escaped = escaped.replace(patterns.comment, (match) => {
                    const placeholder = `__PLACEHOLDER_${placeholderIndex++}__`;
                    placeholders.push({ placeholder, html: `<span class="code-comment">${match}</span>` });
                    return placeholder;
                });
            }

            // Apply decorator highlighting (Python)
            if (patterns.decorator) {
                escaped = escaped.replace(patterns.decorator, '<span class="code-decorator">$&</span>');
            }

            // Apply keyword highlighting
            if (patterns.keyword) {
                escaped = escaped.replace(patterns.keyword, '<span class="code-keyword">$&</span>');
            }

            // Apply function highlighting
            if (patterns.function) {
                escaped = escaped.replace(patterns.function, '<span class="code-function">$1</span>(');
            }

            // Apply number highlighting
            if (patterns.number) {
                escaped = escaped.replace(patterns.number, '<span class="code-number">$&</span>');
            }

            // Restore placeholders
            for (const { placeholder, html } of placeholders) {
                escaped = escaped.replace(placeholder, html);
            }

            return escaped;
        },

        /**
         * Render a code block with highlighting and line numbers
         * @param {string} code - Code content
         * @param {string} filePath - File path for language detection
         * @param {number} startLine - Starting line number
         * @returns {string} HTML for code block
         */
        renderCodeBlock(code, filePath, startLine = 1) {
            const language = this.detectLanguage(filePath);
            const lines = code.split('\n');
            const highlightedLines = lines.map((line, index) => {
                const lineNum = startLine + index;
                const highlighted = this.highlight(line, language);
                return `<div class="code-line">` +
                    `<span class="line-number">${lineNum}</span>` +
                    `<span class="line-content">${highlighted || '&nbsp;'}</span>` +
                    `</div>`;
            }).join('');

            return `<div class="code-block" data-language="${language}" data-file="${UI.escapeHtml(filePath)}">` +
                `<div class="code-header">` +
                `<span class="code-filename">${UI.escapeHtml(filePath)}</span>` +
                `<button class="copy-code-btn" onclick="CodebaseExplorer.copyCode(this)" title="Copy code">` +
                `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">` +
                `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>` +
                `</svg>` +
                `</button>` +
                `</div>` +
                `<pre class="code-content"><code>${highlightedLines}</code></pre>` +
                `</div>`;
        }
    };

    // ==========================================================================
    // API LAYER
    // ==========================================================================

    const API = {
        /**
         * Submit an exploration query
         * @param {string} query - The exploration query
         * @param {string} scope - Query scope (all, architecture, domain, file)
         * @param {Object} options - Additional options
         * @returns {Promise<Object>} Exploration results
         */
        async submitExploration(query, scope = 'all', options = {}) {
            const response = await fetch(CONFIG.API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    scope: scope,
                    include_snippets: options.includeSnippets !== false,
                    max_results: options.maxResults || 10,
                    context: options.context || null
                })
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to submit exploration query');
            }

            return response.json();
        },

        /**
         * Get architecture overview
         * @returns {Promise<Object>} Architecture data
         */
        async getArchitectureOverview() {
            const response = await fetch(CONFIG.API_BASE + '/architecture');

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to fetch architecture overview');
            }

            return response.json();
        },

        /**
         * Get domain details
         * @param {string} domain - Domain name
         * @returns {Promise<Object>} Domain details
         */
        async getDomainDetails(domain) {
            const response = await fetch(CONFIG.API_BASE + '/domains/' + encodeURIComponent(domain));

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to fetch domain details');
            }

            return response.json();
        },

        /**
         * Get file details
         * @param {string} filePath - File path
         * @returns {Promise<Object>} File details with content
         */
        async getFileDetails(filePath) {
            const response = await fetch(CONFIG.API_BASE + '/files/' + encodeURIComponent(filePath));

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to fetch file details');
            }

            return response.json();
        },

        /**
         * Get exploration history
         * @param {number} limit - Number of items to fetch
         * @returns {Promise<Object>} Exploration history
         */
        async getHistory(limit = 20) {
            const response = await fetch(CONFIG.API_BASE + '/history?limit=' + limit);

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to fetch exploration history');
            }

            return response.json();
        },

        /**
         * Get exploration statistics
         * @returns {Promise<Object>} Statistics
         */
        async getStats() {
            const response = await fetch(CONFIG.API_BASE + '/stats');

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.error || 'Failed to fetch statistics');
            }

            return response.json();
        }
    };

    // ==========================================================================
    // UI HELPERS
    // ==========================================================================

    const UI = {
        /**
         * Show a toast notification
         * @param {string} message - Message to display
         * @param {string} type - Toast type (success, error, warning, info)
         */
        showToast(message, type) {
            if (window.Toast && typeof Toast.show === 'function') {
                Toast.show(message, type);
            } else {
                console.log('[' + type.toUpperCase() + '] ' + message);
            }
        },

        /**
         * Escape HTML to prevent XSS
         * @param {string} text - Text to escape
         * @returns {string} Escaped text
         */
        escapeHtml(text) {
            if (typeof text !== 'string') return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Set button loading state
         * @param {HTMLElement} button - Button element
         * @param {boolean} loading - Whether loading
         * @param {string} loadingText - Text to show while loading
         */
        setButtonLoading(button, loading, loadingText) {
            if (!button) return;

            if (loading) {
                button._originalContent = button.innerHTML;
                button.disabled = true;
                button.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">' +
                    '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
                    '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>' +
                    '</svg>' + (loadingText || 'Loading...');
            } else {
                button.disabled = false;
                if (button._originalContent) {
                    button.innerHTML = button._originalContent;
                    delete button._originalContent;
                }
            }
        },

        /**
         * Format relative time
         * @param {string} timestamp - ISO timestamp
         * @returns {string} Relative time string
         */
        formatRelativeTime(timestamp) {
            if (!timestamp) return 'Unknown';

            const now = new Date();
            const date = new Date(timestamp);
            const diffMs = now - date;
            const diffSecs = Math.floor(diffMs / 1000);
            const diffMins = Math.floor(diffSecs / 60);
            const diffHours = Math.floor(diffMins / 60);
            const diffDays = Math.floor(diffHours / 24);

            if (diffSecs < 60) return 'Just now';
            if (diffMins < 60) return diffMins + ' min' + (diffMins === 1 ? '' : 's') + ' ago';
            if (diffHours < 24) return diffHours + ' hour' + (diffHours === 1 ? '' : 's') + ' ago';
            if (diffDays < 7) return diffDays + ' day' + (diffDays === 1 ? '' : 's') + ' ago';

            return date.toLocaleDateString();
        },

        /**
         * Show loading state in results area
         */
        showLoading() {
            state.isLoading = true;
            if (elements.resultsArea) {
                elements.resultsArea.innerHTML = `
                    <div class="loading-state flex flex-col items-center justify-center py-12">
                        <svg class="animate-spin h-8 w-8 text-blue-500 mb-4" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <p class="text-gray-500">Exploring codebase...</p>
                    </div>
                `;
            }
        },

        /**
         * Hide loading state
         */
        hideLoading() {
            state.isLoading = false;
        },

        /**
         * Show empty state
         * @param {string} message - Message to display
         */
        showEmptyState(message) {
            if (elements.resultsArea) {
                elements.resultsArea.innerHTML = `
                    <div class="empty-state flex flex-col items-center justify-center py-12 text-center">
                        <svg class="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                        </svg>
                        <h3 class="text-lg font-medium text-gray-600 mb-2">No results found</h3>
                        <p class="text-gray-500">${UI.escapeHtml(message || 'Try a different query or adjust the scope')}</p>
                    </div>
                `;
            }
        }
    };

    // ==========================================================================
    // DISPLAY FUNCTIONS
    // ==========================================================================

    /**
     * Display exploration results
     * @param {Object} results - Exploration results from API
     */
    function displayExplorationResults(results) {
        state.currentResults = results;

        if (!elements.resultsArea) return;

        if (!results || (!results.answer && (!results.snippets || results.snippets.length === 0))) {
            UI.showEmptyState('No relevant information found for your query');
            return;
        }

        let html = '';

        // Display the main answer/explanation
        if (results.answer) {
            html += `
                <div class="exploration-answer bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <div class="flex items-start gap-3 mb-4">
                        <div class="flex-shrink-0">
                            <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                            </svg>
                        </div>
                        <div class="flex-1">
                            <h3 class="text-lg font-semibold text-gray-900 mb-2">Explanation</h3>
                            <div class="prose prose-sm max-w-none text-gray-700">
                                ${formatMarkdown(results.answer)}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Display related files
        if (results.related_files && results.related_files.length > 0) {
            html += `
                <div class="related-files bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                        </svg>
                        Related Files
                    </h3>
                    <div class="grid gap-2">
                        ${results.related_files.map(file => `
                            <button class="file-link flex items-center gap-2 p-2 rounded hover:bg-gray-50 text-left w-full transition-colors" onclick="CodebaseExplorer.loadFileDetails('${UI.escapeHtml(file.path)}')">
                                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                                <span class="text-sm text-blue-600 hover:text-blue-800 truncate">${UI.escapeHtml(file.path)}</span>
                                ${file.relevance ? `<span class="text-xs text-gray-400 ml-auto">${Math.round(file.relevance * 100)}% relevant</span>` : ''}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Display code snippets
        if (results.snippets && results.snippets.length > 0) {
            html += `
                <div class="code-snippets">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                        </svg>
                        Code Snippets
                    </h3>
                    ${results.snippets.map((snippet, index) => renderSnippet(snippet, index)).join('')}
                </div>
            `;
        }

        // Display related concepts/domains
        if (results.related_domains && results.related_domains.length > 0) {
            html += `
                <div class="related-domains bg-white rounded-lg border border-gray-200 p-6 mt-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                        </svg>
                        Related Domains
                    </h3>
                    <div class="flex flex-wrap gap-2">
                        ${results.related_domains.map(domain => `
                            <button class="domain-tag px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-sm hover:bg-blue-100 transition-colors" onclick="CodebaseExplorer.loadDomainDetails('${UI.escapeHtml(domain)}')">
                                ${UI.escapeHtml(domain)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        elements.resultsArea.innerHTML = html;
    }

    /**
     * Render a single code snippet
     * @param {Object} snippet - Snippet data
     * @param {number} index - Snippet index
     * @returns {string} HTML for snippet
     */
    function renderSnippet(snippet, index) {
        const isExpanded = state.expandedSections.has('snippet-' + index);
        const startLine = snippet.start_line || 1;

        return `
            <div class="snippet-card bg-white rounded-lg border border-gray-200 mb-4 overflow-hidden">
                <div class="snippet-header flex items-center justify-between p-4 bg-gray-50 border-b border-gray-200 cursor-pointer" onclick="CodebaseExplorer.toggleSection('snippet-${index}')">
                    <div class="flex items-center gap-3">
                        <svg class="w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}" id="snippet-arrow-${index}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                        <span class="font-medium text-gray-700">${UI.escapeHtml(snippet.file_path)}</span>
                        ${snippet.start_line ? `<span class="text-sm text-gray-400">Lines ${snippet.start_line}-${snippet.end_line || snippet.start_line}</span>` : ''}
                    </div>
                    ${snippet.description ? `<span class="text-sm text-gray-500">${UI.escapeHtml(snippet.description)}</span>` : ''}
                </div>
                <div class="snippet-content ${isExpanded ? '' : 'hidden'}" id="snippet-content-${index}">
                    ${SyntaxHighlighter.renderCodeBlock(snippet.content, snippet.file_path, startLine)}
                </div>
            </div>
        `;
    }

    /**
     * Format markdown-like text to HTML
     * @param {string} text - Text to format
     * @returns {string} Formatted HTML
     */
    function formatMarkdown(text) {
        if (!text) return '';

        let html = UI.escapeHtml(text);

        // Bold: **text** or __text__
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

        // Italic: *text* or _text_
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        // Inline code: `code`
        html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Toggle expandable section
     * @param {string} sectionId - Section identifier
     */
    function toggleSection(sectionId) {
        const contentEl = document.getElementById(sectionId + '-content') || document.getElementById(sectionId.replace('snippet-', 'snippet-content-'));
        const arrowEl = document.getElementById(sectionId + '-arrow') || document.getElementById(sectionId.replace('snippet-', 'snippet-arrow-'));

        if (contentEl) {
            const isHidden = contentEl.classList.contains('hidden');
            contentEl.classList.toggle('hidden');

            if (isHidden) {
                state.expandedSections.add(sectionId);
            } else {
                state.expandedSections.delete(sectionId);
            }
        }

        if (arrowEl) {
            arrowEl.classList.toggle('rotate-90');
        }
    }

    // ==========================================================================
    // EXPLORATION FUNCTIONS
    // ==========================================================================

    /**
     * Submit an exploration query
     * @param {string} query - Query text
     * @param {string} scope - Query scope
     */
    async function submitExploration(query, scope = 'all') {
        if (!query || !query.trim()) {
            UI.showToast('Please enter a query', 'warning');
            return;
        }

        state.currentQuery = query.trim();
        state.currentScope = scope;

        UI.showLoading();
        UI.setButtonLoading(elements.submitBtn, true, 'Exploring...');

        try {
            const results = await API.submitExploration(state.currentQuery, scope);
            displayExplorationResults(results);

            // Add to history
            state.explorationHistory.unshift({
                query: state.currentQuery,
                scope: scope,
                timestamp: new Date().toISOString()
            });

            UI.showToast('Exploration complete', 'success');
        } catch (error) {
            UI.showToast('Exploration failed: ' + error.message, 'error');
            UI.showEmptyState('Failed to explore codebase. Please try again.');
        } finally {
            UI.hideLoading();
            UI.setButtonLoading(elements.submitBtn, false);
        }
    }

    /**
     * Load architecture overview
     */
    async function loadArchitectureOverview() {
        UI.showLoading();

        try {
            const data = await API.getArchitectureOverview();
            state.architectureData = data;
            displayArchitectureOverview(data);
        } catch (error) {
            UI.showToast('Failed to load architecture: ' + error.message, 'error');
            UI.showEmptyState('Failed to load architecture overview');
        } finally {
            UI.hideLoading();
        }
    }

    /**
     * Display architecture overview
     * @param {Object} data - Architecture data
     */
    function displayArchitectureOverview(data) {
        if (!elements.resultsArea) return;

        let html = `
            <div class="architecture-overview">
                <div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                        </svg>
                        Architecture Overview
                    </h3>
                    ${data.description ? `<p class="text-gray-600 mb-4">${UI.escapeHtml(data.description)}</p>` : ''}
                </div>
        `;

        // Display domains/modules
        if (data.domains && data.domains.length > 0) {
            html += `
                <div class="domains-grid grid gap-4 md:grid-cols-2">
                    ${data.domains.map(domain => `
                        <div class="domain-card bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 transition-colors cursor-pointer" onclick="CodebaseExplorer.loadDomainDetails('${UI.escapeHtml(domain.name)}')">
                            <div class="flex items-start gap-3">
                                <div class="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                                    <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>
                                    </svg>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <h4 class="font-medium text-gray-900">${UI.escapeHtml(domain.name)}</h4>
                                    ${domain.description ? `<p class="text-sm text-gray-500 mt-1">${UI.escapeHtml(domain.description)}</p>` : ''}
                                    ${domain.file_count ? `<span class="text-xs text-gray-400 mt-2 inline-block">${domain.file_count} files</span>` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Display key files
        if (data.key_files && data.key_files.length > 0) {
            html += `
                <div class="key-files bg-white rounded-lg border border-gray-200 p-6 mt-6">
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Key Files</h3>
                    <div class="space-y-2">
                        ${data.key_files.map(file => `
                            <button class="file-link flex items-center gap-2 p-2 rounded hover:bg-gray-50 text-left w-full transition-colors" onclick="CodebaseExplorer.loadFileDetails('${UI.escapeHtml(file.path)}')">
                                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                                <span class="text-sm text-blue-600">${UI.escapeHtml(file.path)}</span>
                                ${file.description ? `<span class="text-xs text-gray-400 ml-auto">${UI.escapeHtml(file.description)}</span>` : ''}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        html += '</div>';
        elements.resultsArea.innerHTML = html;
    }

    /**
     * Load domain details
     * @param {string} domain - Domain name
     */
    async function loadDomainDetails(domain) {
        UI.showLoading();

        try {
            const data = await API.getDomainDetails(domain);
            displayDomainDetails(data);
        } catch (error) {
            UI.showToast('Failed to load domain details: ' + error.message, 'error');
            UI.showEmptyState('Failed to load domain details');
        } finally {
            UI.hideLoading();
        }
    }

    /**
     * Display domain details
     * @param {Object} data - Domain data
     */
    function displayDomainDetails(data) {
        if (!elements.resultsArea) return;

        let html = `
            <div class="domain-details">
                <div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <div class="flex items-center gap-2 mb-4">
                        <button class="text-blue-600 hover:text-blue-800 flex items-center gap-1" onclick="CodebaseExplorer.loadArchitectureOverview()">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
                            </svg>
                            Back to Architecture
                        </button>
                    </div>
                    <h3 class="text-xl font-semibold text-gray-900 mb-2">${UI.escapeHtml(data.name)}</h3>
                    ${data.description ? `<p class="text-gray-600">${UI.escapeHtml(data.description)}</p>` : ''}
                </div>
        `;

        // Display files in domain
        if (data.files && data.files.length > 0) {
            html += `
                <div class="domain-files bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <h4 class="font-semibold text-gray-900 mb-4">Files (${data.files.length})</h4>
                    <div class="space-y-2 max-h-96 overflow-y-auto">
                        ${data.files.map(file => `
                            <button class="file-link flex items-center gap-2 p-2 rounded hover:bg-gray-50 text-left w-full transition-colors" onclick="CodebaseExplorer.loadFileDetails('${UI.escapeHtml(file.path || file)}')">
                                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                                </svg>
                                <span class="text-sm text-blue-600 truncate">${UI.escapeHtml(file.path || file)}</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Display dependencies
        if (data.dependencies && data.dependencies.length > 0) {
            html += `
                <div class="domain-dependencies bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <h4 class="font-semibold text-gray-900 mb-4">Dependencies</h4>
                    <div class="flex flex-wrap gap-2">
                        ${data.dependencies.map(dep => `
                            <button class="dependency-tag px-3 py-1 rounded-full bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 transition-colors" onclick="CodebaseExplorer.loadDomainDetails('${UI.escapeHtml(dep)}')">
                                ${UI.escapeHtml(dep)}
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Display patterns
        if (data.patterns && data.patterns.length > 0) {
            html += `
                <div class="domain-patterns bg-white rounded-lg border border-gray-200 p-6">
                    <h4 class="font-semibold text-gray-900 mb-4">Patterns Used</h4>
                    <ul class="list-disc list-inside text-gray-600 space-y-1">
                        ${data.patterns.map(pattern => `<li>${UI.escapeHtml(pattern)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        html += '</div>';
        elements.resultsArea.innerHTML = html;
    }

    /**
     * Load file details
     * @param {string} filePath - File path
     */
    async function loadFileDetails(filePath) {
        UI.showLoading();

        try {
            const data = await API.getFileDetails(filePath);
            displayFileDetails(data);
        } catch (error) {
            UI.showToast('Failed to load file details: ' + error.message, 'error');
            UI.showEmptyState('Failed to load file details');
        } finally {
            UI.hideLoading();
        }
    }

    /**
     * Display file details
     * @param {Object} data - File data
     */
    function displayFileDetails(data) {
        if (!elements.resultsArea) return;

        let html = `
            <div class="file-details">
                <div class="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <div class="flex items-center gap-2 mb-4">
                        <button class="text-blue-600 hover:text-blue-800 flex items-center gap-1" onclick="CodebaseExplorer.loadArchitectureOverview()">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
                            </svg>
                            Back to Architecture
                        </button>
                    </div>
                    <h3 class="text-xl font-semibold text-gray-900 mb-2 flex items-center gap-2">
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        ${UI.escapeHtml(data.path)}
                    </h3>
                    ${data.description ? `<p class="text-gray-600">${UI.escapeHtml(data.description)}</p>` : ''}
                </div>
        `;

        // Display file metadata
        if (data.metadata) {
            html += `
                <div class="file-metadata bg-white rounded-lg border border-gray-200 p-6 mb-6">
                    <h4 class="font-semibold text-gray-900 mb-4">File Information</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        ${data.metadata.lines ? `<div><span class="text-gray-500">Lines:</span> <span class="font-medium">${data.metadata.lines}</span></div>` : ''}
                        ${data.metadata.size ? `<div><span class="text-gray-500">Size:</span> <span class="font-medium">${data.metadata.size}</span></div>` : ''}
                        ${data.metadata.language ? `<div><span class="text-gray-500">Language:</span> <span class="font-medium">${UI.escapeHtml(data.metadata.language)}</span></div>` : ''}
                        ${data.metadata.modified ? `<div><span class="text-gray-500">Modified:</span> <span class="font-medium">${UI.formatRelativeTime(data.metadata.modified)}</span></div>` : ''}
                    </div>
                </div>
            `;
        }

        // Display file content
        if (data.content) {
            html += `
                <div class="file-content-section">
                    <h4 class="font-semibold text-gray-900 mb-4">Content</h4>
                    ${SyntaxHighlighter.renderCodeBlock(data.content, data.path, 1)}
                </div>
            `;
        }

        // Display related files
        if (data.imports && data.imports.length > 0) {
            html += `
                <div class="file-imports bg-white rounded-lg border border-gray-200 p-6 mt-6">
                    <h4 class="font-semibold text-gray-900 mb-4">Imports / Dependencies</h4>
                    <div class="space-y-1">
                        ${data.imports.map(imp => `
                            <button class="file-link flex items-center gap-2 p-2 rounded hover:bg-gray-50 text-left w-full transition-colors" onclick="CodebaseExplorer.loadFileDetails('${UI.escapeHtml(imp)}')">
                                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                                </svg>
                                <span class="text-sm text-blue-600">${UI.escapeHtml(imp)}</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        html += '</div>';
        elements.resultsArea.innerHTML = html;
    }

    /**
     * Copy code to clipboard
     * @param {HTMLElement} button - Copy button element
     */
    function copyCode(button) {
        const codeBlock = button.closest('.code-block');
        if (!codeBlock) return;

        const codeEl = codeBlock.querySelector('code');
        if (!codeEl) return;

        // Extract text content from code lines
        const lines = codeEl.querySelectorAll('.line-content');
        const text = Array.from(lines).map(line => line.textContent).join('\n');

        navigator.clipboard.writeText(text).then(() => {
            // Show success feedback
            const originalHTML = button.innerHTML;
            button.innerHTML = '<svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            setTimeout(() => {
                button.innerHTML = originalHTML;
            }, 2000);
            UI.showToast('Code copied to clipboard', 'success');
        }).catch(() => {
            UI.showToast('Failed to copy code', 'error');
        });
    }

    // ==========================================================================
    // EVENT BINDING
    // ==========================================================================

    /**
     * Cache DOM element references
     */
    function cacheElements() {
        elements.explorerContainer = document.getElementById('explorer-container');
        elements.resultsArea = document.getElementById('results-area') || document.getElementById('questions-list');
        elements.queryInput = document.getElementById('query-input') || document.getElementById('search-input');
        elements.scopeSelect = document.getElementById('scope-select') || document.getElementById('source-filter');
        elements.submitBtn = document.getElementById('submit-exploration-btn') || document.getElementById('ask-question-btn');
        elements.architecturePanel = document.getElementById('architecture-panel');
        elements.domainsList = document.getElementById('domains-list');
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        // Query submission
        if (elements.submitBtn) {
            elements.submitBtn.addEventListener('click', handleSubmit);
        }

        // Enter key in query input
        if (elements.queryInput) {
            elements.queryInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSubmit();
                }
            });
        }

        // Scope change
        if (elements.scopeSelect) {
            elements.scopeSelect.addEventListener('change', function() {
                state.currentScope = this.value;
            });
        }
    }

    /**
     * Handle form submission
     */
    function handleSubmit() {
        const query = elements.queryInput ? elements.queryInput.value.trim() : '';
        const scope = elements.scopeSelect ? elements.scopeSelect.value : 'all';

        if (query) {
            submitExploration(query, scope);
        } else {
            UI.showToast('Please enter a query', 'warning');
        }
    }

    // ==========================================================================
    // INITIALIZATION
    // ==========================================================================

    /**
     * Initialize the Codebase Explorer module
     */
    function init() {
        cacheElements();
        bindEvents();

        // Load architecture overview on init if no query
        if (elements.resultsArea && !state.currentQuery) {
            loadArchitectureOverview();
        }

        console.log('[CodebaseExplorer] Initialized');
    }

    // ==========================================================================
    // PUBLIC API
    // ==========================================================================

    return {
        // Initialize
        init: init,

        // Core exploration functions
        submitExploration: submitExploration,
        displayExplorationResults: displayExplorationResults,
        loadArchitectureOverview: loadArchitectureOverview,
        loadDomainDetails: loadDomainDetails,
        loadFileDetails: loadFileDetails,

        // UI interactions
        toggleSection: toggleSection,
        copyCode: copyCode,

        // API access
        API: API,

        // Utilities
        UI: UI,
        SyntaxHighlighter: SyntaxHighlighter,

        // State access (for debugging)
        getState: function() { return state; }
    };
})();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    CodebaseExplorer.init();
});

// Expose global functions for inline onclick handlers in template
window.submitExploration = CodebaseExplorer.submitExploration;
window.loadArchitectureOverview = CodebaseExplorer.loadArchitectureOverview;
window.loadDomainDetails = CodebaseExplorer.loadDomainDetails;
window.loadFileDetails = CodebaseExplorer.loadFileDetails;
window.toggleSection = CodebaseExplorer.toggleSection;
window.copyCode = CodebaseExplorer.copyCode;

// Backward compatibility alias
window.QuestionsModule = CodebaseExplorer;
