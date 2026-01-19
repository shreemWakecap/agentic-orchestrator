/**
 * Knowledge Management Module
 * Handles knowledge base viewing, scouting, and management operations
 */

// Toast notification state
let knowledgeToastTimeout = null;

/**
 * Initialize knowledge page event listeners
 */
function initKnowledge() {
    // Scout form submission
    const scoutForm = document.getElementById('scout-form');
    if (scoutForm) {
        scoutForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const scanType = document.getElementById('scan-type')?.value || 'full';
            const target = document.getElementById('scan-target')?.value || '';
            startScout({ scan_type: scanType, target: target });
        });
    }

    // Scout button (standalone)
    const scoutBtn = document.getElementById('scout-btn');
    if (scoutBtn) {
        scoutBtn.addEventListener('click', function() {
            const scanType = document.getElementById('scan-type')?.value || 'full';
            const target = document.getElementById('scan-target')?.value || '';
            startScout({ scan_type: scanType, target: target });
        });
    }

    // Quick scout buttons
    document.querySelectorAll('[data-scout-type]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const scanType = btn.dataset.scoutType;
            const target = btn.dataset.scoutTarget || '';
            startScout({ scan_type: scanType, target: target });
        });
    });

    // Clear knowledge button
    const clearBtn = document.getElementById('clear-knowledge-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearKnowledge);
    }

    // Refresh button
    const refreshBtn = document.getElementById('refresh-knowledge-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            const icon = refreshBtn.querySelector('svg');
            if (icon) icon.classList.add('animate-spin');
            refreshKnowledge().finally(function() {
                setTimeout(function() {
                    if (icon) icon.classList.remove('animate-spin');
                }, 500);
            });
        });
    }

    // Target path input - handle enter key
    const targetInput = document.getElementById('scan-target');
    if (targetInput) {
        targetInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const scanType = document.getElementById('scan-type')?.value || 'full';
                startScout({ scan_type: scanType, target: targetInput.value });
            }
        });
    }

    // Initialize tooltips or popovers if needed
    initKnowledgeTooltips();
}

/**
 * Initialize tooltips for knowledge items
 */
function initKnowledgeTooltips() {
    document.querySelectorAll('[data-knowledge-tooltip]').forEach(function(el) {
        el.addEventListener('mouseenter', function() {
            el.title = el.dataset.knowledgeTooltip;
        });
    });
}

/**
 * Start a scouting operation
 * @param {Object} options - Scout options
 * @param {string} options.scan_type - Type of scan (full, paths, keys, tech)
 * @param {string} [options.target] - Optional target path or pattern
 */
async function startScout(options) {
    const scoutBtn = document.getElementById('scout-btn');
    const scoutForm = document.getElementById('scout-form');
    const submitBtn = scoutForm?.querySelector('button[type="submit"]') || scoutBtn;

    if (!options.scan_type) {
        options.scan_type = 'full';
    }

    // Set loading state
    const originalText = submitBtn?.textContent || 'Start Scout';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Starting...';
    }

    try {
        const response = await fetch('/api/knowledge/scout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scan_type: options.scan_type,
                target: options.target || null
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(function() { return {}; });
            throw new Error(errorData.detail || 'HTTP ' + response.status + ': ' + response.statusText);
        }

        const data = await response.json();

        if (data.run_id) {
            showToast('Scout started successfully', 'success');
            // Small delay to show toast before redirect
            setTimeout(function() {
                window.location.href = '/runs/' + data.run_id;
            }, 500);
        } else {
            throw new Error('No run_id in response');
        }
    } catch (error) {
        console.error('Scout error:', error);
        showToast('Failed to start scout: ' + error.message, 'error');

        // Reset button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }
}

/**
 * Clear all knowledge data with confirmation
 */
async function clearKnowledge() {
    const confirmed = confirm(
        'Are you sure you want to clear all knowledge data?\n\n' +
        'This will remove all scouted information including:\n' +
        '- File paths and structure\n' +
        '- Tech stack detection\n' +
        '- Code patterns and keys\n\n' +
        'This action cannot be undone.'
    );

    if (!confirmed) {
        return;
    }

    const clearBtn = document.getElementById('clear-knowledge-btn');
    const originalText = clearBtn?.textContent || 'Clear Knowledge';

    if (clearBtn) {
        clearBtn.disabled = true;
        clearBtn.textContent = 'Clearing...';
    }

    try {
        const response = await fetch('/api/knowledge', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const errorData = await response.json().catch(function() { return {}; });
            throw new Error(errorData.detail || 'HTTP ' + response.status + ': ' + response.statusText);
        }

        showToast('Knowledge cleared successfully', 'success');

        // Refresh the page to show empty state
        setTimeout(function() {
            window.location.reload();
        }, 1000);
    } catch (error) {
        console.error('Clear knowledge error:', error);
        showToast('Failed to clear knowledge: ' + error.message, 'error');

        if (clearBtn) {
            clearBtn.disabled = false;
            clearBtn.textContent = originalText;
        }
    }
}

/**
 * Refresh knowledge overview data
 * @returns {Promise<Object|null>} Knowledge data or null on error
 */
async function refreshKnowledge() {
    const container = document.getElementById('knowledge-overview');
    const statsContainer = document.getElementById('knowledge-stats');

    try {
        const response = await fetch('/api/knowledge/overview');

        if (!response.ok) {
            throw new Error('HTTP ' + response.status + ': ' + response.statusText);
        }

        const data = await response.json();

        // Update stats if container exists
        if (statsContainer) {
            updateKnowledgeStats(data);
        }

        // Update overview content if container exists
        if (container) {
            updateKnowledgeOverview(data);
        }

        showToast('Knowledge refreshed', 'success');
        return data;
    } catch (error) {
        console.error('Refresh knowledge error:', error);
        showToast('Failed to refresh knowledge: ' + error.message, 'error');
        return null;
    }
}

/**
 * Update knowledge statistics display
 * @param {Object} data - Knowledge data from API
 */
function updateKnowledgeStats(data) {
    // Update file count
    const fileCount = document.getElementById('stat-file-count');
    if (fileCount && data.file_count !== undefined) {
        fileCount.textContent = data.file_count.toLocaleString();
    }

    // Update tech count
    const techCount = document.getElementById('stat-tech-count');
    if (techCount && data.tech_count !== undefined) {
        techCount.textContent = data.tech_count.toLocaleString();
    }

    // Update pattern count
    const patternCount = document.getElementById('stat-pattern-count');
    if (patternCount && data.pattern_count !== undefined) {
        patternCount.textContent = data.pattern_count.toLocaleString();
    }

    // Update last scout time
    const lastScout = document.getElementById('stat-last-scout');
    if (lastScout && data.last_scout) {
        lastScout.textContent = formatRelativeTime(data.last_scout);
    }
}

/**
 * Update knowledge overview content
 * @param {Object} data - Knowledge data from API
 */
function updateKnowledgeOverview(data) {
    const container = document.getElementById('knowledge-overview');
    if (!container) return;

    // Update tech stack list
    const techList = container.querySelector('#tech-stack-list');
    if (techList && data.technologies) {
        techList.innerHTML = data.technologies.map(function(tech) {
            return '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mr-2 mb-2">' +
                escapeHtml(tech) +
            '</span>';
        }).join('');
    }

    // Update paths list
    const pathsList = container.querySelector('#paths-list');
    if (pathsList && data.key_paths) {
        pathsList.innerHTML = data.key_paths.slice(0, 10).map(function(path) {
            return '<li class="text-sm text-gray-600 truncate" title="' + escapeHtml(path) + '">' +
                escapeHtml(path) +
            '</li>';
        }).join('');
    }

    // Update patterns list
    const patternsList = container.querySelector('#patterns-list');
    if (patternsList && data.patterns) {
        patternsList.innerHTML = data.patterns.slice(0, 10).map(function(pattern) {
            return '<li class="text-sm text-gray-600">' + escapeHtml(pattern.name || pattern) + '</li>';
        }).join('');
    }
}

/**
 * Format a timestamp as relative time
 * @param {string} timestamp - ISO timestamp string
 * @returns {string} Relative time string
 */
function formatRelativeTime(timestamp) {
    if (!timestamp) return 'Never';

    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) {
        return 'Just now';
    } else if (diffMins < 60) {
        return diffMins + ' minute' + (diffMins === 1 ? '' : 's') + ' ago';
    } else if (diffHours < 24) {
        return diffHours + ' hour' + (diffHours === 1 ? '' : 's') + ' ago';
    } else if (diffDays < 7) {
        return diffDays + ' day' + (diffDays === 1 ? '' : 's') + ' ago';
    } else {
        return date.toLocaleDateString();
    }
}

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Toast type: 'success', 'error', 'info', 'warning'
 */
function showToast(message, type) {
    type = type || 'info';

    // Clear any existing toast timeout
    if (knowledgeToastTimeout) {
        clearTimeout(knowledgeToastTimeout);
    }

    // Remove existing toasts
    const existingToast = document.getElementById('knowledge-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.id = 'knowledge-toast';
    toast.className = 'fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-y-2 opacity-0';

    // Set type-specific styles
    var bgColor, textColor, iconSvg;
    switch (type) {
        case 'success':
            bgColor = 'bg-green-500';
            textColor = 'text-white';
            iconSvg = '<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            break;
        case 'error':
            bgColor = 'bg-red-500';
            textColor = 'text-white';
            iconSvg = '<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
            break;
        case 'warning':
            bgColor = 'bg-yellow-500';
            textColor = 'text-white';
            iconSvg = '<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>';
            break;
        default:
            bgColor = 'bg-blue-500';
            textColor = 'text-white';
            iconSvg = '<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
    }

    toast.classList.add(bgColor, textColor);
    toast.innerHTML = '<div class="flex items-center">' + iconSvg + '<span>' + escapeHtml(message) + '</span></div>';

    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(function() {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    // Auto-remove after delay
    knowledgeToastTimeout = setTimeout(function() {
        toast.classList.add('translate-y-2', 'opacity-0');
        setTimeout(function() {
            toast.remove();
        }, 300);
    }, 3000);
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    // Use OrchestratorUtils if available, otherwise fallback
    if (window.OrchestratorUtils && window.OrchestratorUtils.escapeHtml) {
        return window.OrchestratorUtils.escapeHtml(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initKnowledge();
});
