/**
 * Markdown Viewer Component
 * A reusable component for displaying markdown content in the side popup with token count
 *
 * Wraps SidePopup to provide markdown rendering with token estimation display
 */

const MarkdownViewer = {
    /**
     * Show markdown content in the side popup with token count badge
     *
     * @param {string} title - The title to display in the popup header
     * @param {string} content - The markdown content to render
     * @param {number|null} tokenCount - Optional token count to display (null to hide badge)
     * @param {Object} options - Additional options for customization
     * @param {string} options.contentClass - Additional CSS class for the content area
     */
    show(title, content, tokenCount = null, options = {}) {
        // Build the header with optional token count badge
        const headerHtml = this._buildHeader(title, tokenCount);

        // Render markdown content
        const renderedContent = this._renderMarkdown(content);

        // Build the full content HTML
        const fullContent = `
            ${headerHtml}
            <div class="markdown-content">
                ${renderedContent}
            </div>
        `;

        // Update the side popup title with a generic label since we have our own header
        SidePopup.open(title, fullContent, {
            contentClass: options.contentClass || ''
        });
    },

    /**
     * Show markdown content with a custom header element
     *
     * @param {string} title - The title for the popup
     * @param {string} content - The markdown content
     * @param {HTMLElement|string} headerElement - Custom header HTML or element
     * @param {Object} options - Additional options
     */
    showWithCustomHeader(title, content, headerElement, options = {}) {
        const renderedContent = this._renderMarkdown(content);

        const headerHtml = typeof headerElement === 'string'
            ? headerElement
            : headerElement.outerHTML;

        const fullContent = `
            ${headerHtml}
            <div class="markdown-content">
                ${renderedContent}
            </div>
        `;

        SidePopup.open(title, fullContent, {
            contentClass: options.contentClass || ''
        });
    },

    /**
     * Build the header with token count badge
     *
     * @param {string} title - The title text
     * @param {number|null} tokenCount - Token count to display
     * @returns {string} Header HTML
     */
    _buildHeader(title, tokenCount) {
        const tokenBadge = tokenCount !== null
            ? `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800 ml-3">
                   <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                       <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path>
                   </svg>
                   ~${this._formatTokenCount(tokenCount)} tokens
               </span>`
            : '';

        return `
            <div class="flex items-center justify-between mb-4 pb-3 border-b border-gray-200">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-gray-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <span class="text-sm font-medium text-gray-600">Content Preview</span>
                    ${tokenBadge}
                </div>
            </div>
        `;
    },

    /**
     * Format token count for display
     *
     * @param {number} count - Token count
     * @returns {string} Formatted count string
     */
    _formatTokenCount(count) {
        if (count >= 1000000) {
            return (count / 1000000).toFixed(1) + 'M';
        } else if (count >= 1000) {
            return (count / 1000).toFixed(1) + 'K';
        }
        return count.toLocaleString();
    },

    /**
     * Render markdown content to HTML
     * Handles basic markdown syntax for display
     *
     * @param {string} markdown - Raw markdown content
     * @returns {string} Rendered HTML
     */
    _renderMarkdown(markdown) {
        if (!markdown) {
            return '<p class="text-gray-500 italic">No content available</p>';
        }

        // Escape HTML first to prevent XSS
        let html = this._escapeHtml(markdown);

        // Process code blocks first (before other transformations)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre class="md-code-block my-4"><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
        });

        // Process inline code
        html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');

        // Process headers (must be at line start)
        html = html.replace(/^### (.+)$/gm, '<h3 class="md-heading text-lg font-semibold mt-4 mb-2">$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2 class="md-heading text-xl font-semibold mt-5 mb-3">$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1 class="md-heading text-2xl font-bold mt-6 mb-4">$1</h1>');

        // Process bold and italic
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
        html = html.replace(/_(.+?)_/g, '<em>$1</em>');

        // Process horizontal rules
        html = html.replace(/^---$/gm, '<hr class="md-hr my-6">');
        html = html.replace(/^\*\*\*$/gm, '<hr class="md-hr my-6">');

        // Process unordered lists
        html = html.replace(/^(\s*)[-*+] (.+)$/gm, (match, indent, content) => {
            const level = Math.floor(indent.length / 2);
            const paddingClass = level > 0 ? `ml-${level * 4}` : '';
            return `<li class="md-text list-disc list-inside ${paddingClass} my-1">${content}</li>`;
        });

        // Process ordered lists
        html = html.replace(/^(\s*)\d+\. (.+)$/gm, (match, indent, content) => {
            const level = Math.floor(indent.length / 2);
            const paddingClass = level > 0 ? `ml-${level * 4}` : '';
            return `<li class="md-text list-decimal list-inside ${paddingClass} my-1">${content}</li>`;
        });

        // Process blockquotes
        html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="md-blockquote">$1</blockquote>');

        // Process links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary-600 hover:underline" target="_blank" rel="noopener noreferrer">$1</a>');

        // Process line breaks and paragraphs
        // Split by double newlines to create paragraphs
        const paragraphs = html.split(/\n\n+/);
        html = paragraphs.map(p => {
            // Skip wrapping for elements that are already block-level
            const trimmed = p.trim();
            if (trimmed.startsWith('<h') ||
                trimmed.startsWith('<pre') ||
                trimmed.startsWith('<hr') ||
                trimmed.startsWith('<blockquote') ||
                trimmed.startsWith('<li')) {
                return trimmed;
            }
            // Wrap plain text in paragraphs
            if (trimmed) {
                return `<p class="md-text my-2">${trimmed.replace(/\n/g, '<br>')}</p>`;
            }
            return '';
        }).join('\n');

        return html;
    },

    /**
     * Escape HTML special characters
     *
     * @param {string} text - Raw text
     * @returns {string} Escaped text
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Estimate token count for a given text
     * Uses a simple approximation: ~4 characters per token for English text
     *
     * @param {string} text - Text to estimate tokens for
     * @returns {number} Estimated token count
     */
    estimateTokens(text) {
        if (!text) return 0;
        // Rough approximation: ~4 characters per token for English text
        // This accounts for whitespace, punctuation, and common word lengths
        return Math.ceil(text.length / 4);
    },

    /**
     * Close the markdown viewer (delegates to SidePopup)
     */
    close() {
        SidePopup.close();
    }
};

// No DOMContentLoaded needed - this module just wraps SidePopup which handles its own initialization
