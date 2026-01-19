/**
 * Job List Component
 *
 * Displays a filterable, paginated list of jobs.
 *
 * Usage:
 *   const list = new JobListComponent('#job-list', {
 *       pageSize: 20,
 *       showFilters: true,
 *       autoRefresh: true,
 *       onViewJob: (jobId) => showJobDetails(jobId),
 *   });
 *
 *   // Store reference for button handlers
 *   window.jobList = list;
 *
 *   // Later: cleanup
 *   list.destroy();
 */

class JobListComponent {
    /**
     * Create a job list component
     * @param {string|Element} container - Container selector or element
     * @param {Object} options - Component options
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        this.options = {
            pageSize: 20,
            showFilters: true,
            autoRefresh: true,
            refreshInterval: 10000,
            showActions: true,
            ...options
        };

        this.filters = {
            status: null,
            job_type: null,
        };
        this.pagination = {
            offset: 0,
            total: 0,
        };
        this.jobs = [];
        this.refreshTimer = null;
        this.elements = {};

        if (!this.container) {
            throw new Error('JobListComponent: Container not found');
        }

        this.render();
        this.loadJobs();

        if (this.options.autoRefresh) {
            this.startAutoRefresh();
        }

        // Store reference globally for inline handlers
        window.jobList = this;
    }

    /**
     * Render the component HTML
     */
    render() {
        this.container.innerHTML = `
            <div class="job-list">
                ${this.options.showFilters ? this.renderFilters() : ''}
                <div class="job-list-header">
                    <span class="job-count">Loading...</span>
                    <div class="job-list-header-actions">
                        <button class="btn btn-sm btn-secondary refresh-btn">
                            Refresh
                        </button>
                    </div>
                </div>
                <div class="job-list-items"></div>
                <div class="job-list-pagination"></div>
            </div>
        `;

        this.elements = {
            root: this.container.querySelector('.job-list'),
            filters: this.container.querySelector('.job-list-filters'),
            count: this.container.querySelector('.job-count'),
            items: this.container.querySelector('.job-list-items'),
            pagination: this.container.querySelector('.job-list-pagination'),
            refreshBtn: this.container.querySelector('.refresh-btn'),
        };

        // Event listeners
        this.elements.refreshBtn.addEventListener('click', () => this.loadJobs());

        if (this.options.showFilters) {
            this.attachFilterListeners();
        }
    }

    /**
     * Render filter controls HTML
     * @returns {string} - Filter HTML
     */
    renderFilters() {
        return `
            <div class="job-list-filters">
                <div class="filter-group">
                    <label>Status:</label>
                    <select class="filter-status">
                        <option value="">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="queued">Queued</option>
                        <option value="running">Running</option>
                        <option value="succeeded">Succeeded</option>
                        <option value="failed">Failed</option>
                        <option value="cancelled">Cancelled</option>
                        <option value="resumable">Resumable</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Type:</label>
                    <select class="filter-type">
                        <option value="">All Types</option>
                        <option value="plan">Plan</option>
                        <option value="build">Build</option>
                        <option value="review">Review</option>
                        <option value="fix">Fix</option>
                        <option value="sync">Sync</option>
                        <option value="docs">Docs</option>
                        <option value="experts">Experts</option>
                    </select>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners to filter controls
     */
    attachFilterListeners() {
        const statusFilter = this.container.querySelector('.filter-status');
        const typeFilter = this.container.querySelector('.filter-type');

        statusFilter?.addEventListener('change', (e) => {
            this.filters.status = e.target.value || null;
            this.pagination.offset = 0;
            this.loadJobs();
        });

        typeFilter?.addEventListener('change', (e) => {
            this.filters.job_type = e.target.value || null;
            this.pagination.offset = 0;
            this.loadJobs();
        });
    }

    /**
     * Load jobs from API
     */
    async loadJobs() {
        try {
            this.elements.count.textContent = 'Loading...';

            const result = await window.jobManager.listJobs({
                status: this.filters.status,
                job_type: this.filters.job_type,
                limit: this.options.pageSize,
                offset: this.pagination.offset,
            });

            this.jobs = result.jobs;
            this.pagination.total = result.total;
            this.renderJobs(result.jobs);
            this.renderPagination();
            this.elements.count.textContent = `${result.total} job${result.total !== 1 ? 's' : ''}`;

            if (this.options.onLoad) {
                this.options.onLoad(result);
            }
        } catch (error) {
            this.elements.items.innerHTML = `
                <div class="job-list-error">
                    Failed to load jobs: ${error.message}
                </div>
            `;
            this.elements.count.textContent = 'Error';
        }
    }

    /**
     * Render job list items
     * @param {Array} jobs - Array of job objects
     */
    renderJobs(jobs) {
        if (jobs.length === 0) {
            this.elements.items.innerHTML = `
                <div class="job-list-empty">
                    No jobs found
                </div>
            `;
            return;
        }

        this.elements.items.innerHTML = jobs.map(job => this.renderJobItem(job)).join('');
    }

    /**
     * Render a single job item
     * @param {Object} job - Job object
     * @returns {string} - Job item HTML
     */
    renderJobItem(job) {
        const actions = this.options.showActions ? this.renderJobActions(job) : '';

        return `
            <div class="job-list-item" data-job-id="${job.job_id}">
                <div class="job-item-main">
                    <span class="job-item-id" title="${job.job_id}">${job.job_id.substring(0, 8)}</span>
                    <span class="job-item-type job-type-${job.job_type}">${job.job_type}</span>
                    <span class="job-item-status status-${job.status}">${this.formatStatus(job.status)}</span>
                    ${job.progress ? `
                        <span class="job-item-progress">
                            <span class="job-item-progress-bar" style="width: ${job.progress.percent}%"></span>
                            <span class="job-item-progress-text">${job.progress.percent}%</span>
                        </span>
                    ` : ''}
                </div>
                <div class="job-item-meta">
                    <span class="job-item-time">${this.formatTime(job.created_at)}</span>
                    ${job.error ? `
                        <span class="job-item-error" title="${this.escapeHtml(job.error)}">
                            Error
                        </span>
                    ` : ''}
                </div>
                ${actions ? `<div class="job-item-actions">${actions}</div>` : ''}
            </div>
        `;
    }

    /**
     * Render action buttons for a job
     * @param {Object} job - Job object
     * @returns {string} - Actions HTML
     */
    renderJobActions(job) {
        const actions = [];

        actions.push(`
            <button class="btn btn-xs btn-secondary" onclick="jobList.viewJob('${job.job_id}')">
                View
            </button>
        `);

        if (window.jobManager.canRetry(job)) {
            actions.push(`
                <button class="btn btn-xs btn-primary" onclick="jobList.retryJob('${job.job_id}')">
                    Retry
                </button>
            `);
        }

        if (window.jobManager.canCancel(job)) {
            actions.push(`
                <button class="btn btn-xs btn-danger" onclick="jobList.cancelJob('${job.job_id}')">
                    Cancel
                </button>
            `);
        }

        if (window.jobManager.canResume(job)) {
            actions.push(`
                <button class="btn btn-xs btn-success" onclick="jobList.resumeJob('${job.job_id}')">
                    Resume
                </button>
            `);
        }

        return actions.join(' ');
    }

    /**
     * Render pagination controls
     */
    renderPagination() {
        const totalPages = Math.ceil(this.pagination.total / this.options.pageSize);
        const currentPage = Math.floor(this.pagination.offset / this.options.pageSize) + 1;

        if (totalPages <= 1) {
            this.elements.pagination.innerHTML = '';
            return;
        }

        const buttons = [];

        // Previous button
        if (currentPage > 1) {
            buttons.push(`
                <button class="btn btn-sm pagination-prev" onclick="jobList.goToPage(${currentPage - 1})">
                    Prev
                </button>
            `);
        }

        // Page info
        buttons.push(`<span class="pagination-info">Page ${currentPage} of ${totalPages}</span>`);

        // Next button
        if (currentPage < totalPages) {
            buttons.push(`
                <button class="btn btn-sm pagination-next" onclick="jobList.goToPage(${currentPage + 1})">
                    Next
                </button>
            `);
        }

        this.elements.pagination.innerHTML = buttons.join(' ');
    }

    /**
     * Navigate to a specific page
     * @param {number} page - Page number (1-based)
     */
    goToPage(page) {
        this.pagination.offset = (page - 1) * this.options.pageSize;
        this.loadJobs();
    }

    /**
     * View job details
     * @param {string} jobId - Job ID
     */
    viewJob(jobId) {
        if (this.options.onViewJob) {
            this.options.onViewJob(jobId);
        } else {
            window.location.href = `/jobs/${jobId}`;
        }
    }

    /**
     * Retry a job
     * @param {string} jobId - Job ID
     */
    async retryJob(jobId) {
        try {
            const newJob = await window.jobManager.retryJob(jobId);
            this.loadJobs();
            if (this.options.onRetry) {
                this.options.onRetry(newJob);
            }
        } catch (error) {
            this.showError('Failed to retry job: ' + error.message);
        }
    }

    /**
     * Cancel a job
     * @param {string} jobId - Job ID
     */
    async cancelJob(jobId) {
        if (confirm('Cancel this job?')) {
            try {
                await window.jobManager.cancelJob(jobId);
                this.loadJobs();
            } catch (error) {
                this.showError('Failed to cancel job: ' + error.message);
            }
        }
    }

    /**
     * Resume a job
     * @param {string} jobId - Job ID
     */
    async resumeJob(jobId) {
        try {
            const checkpointsData = await window.jobManager.getCheckpoints(jobId);
            const checkpoints = checkpointsData.checkpoints;

            if (checkpoints.length === 0) {
                alert('No checkpoints available for resume');
                return;
            }

            // Simple checkpoint selection
            const options = checkpoints.map(cp =>
                `${cp.id}: ${cp.phase} at ${cp.progress_percent}%`
            ).join('\n');
            const selected = prompt(`Select checkpoint:\n${options}\n\nEnter checkpoint ID:`);

            if (selected) {
                const newJob = await window.jobManager.resumeJob(jobId, selected.trim());
                this.loadJobs();
                if (this.options.onResume) {
                    this.options.onResume(newJob);
                }
            }
        } catch (error) {
            this.showError('Failed to resume job: ' + error.message);
        }
    }

    /**
     * Show error message
     * @param {string} message - Error message
     */
    showError(message) {
        if (this.options.onError) {
            this.options.onError(message);
        } else {
            alert(message);
        }
    }

    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshTimer = setInterval(() => this.loadJobs(), this.options.refreshInterval);
    }

    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    /**
     * Set filter values programmatically
     * @param {Object} filters - Filter values
     */
    setFilters(filters) {
        if (filters.status !== undefined) {
            this.filters.status = filters.status;
            const statusSelect = this.container.querySelector('.filter-status');
            if (statusSelect) statusSelect.value = filters.status || '';
        }
        if (filters.job_type !== undefined) {
            this.filters.job_type = filters.job_type;
            const typeSelect = this.container.querySelector('.filter-type');
            if (typeSelect) typeSelect.value = filters.job_type || '';
        }
        this.pagination.offset = 0;
        this.loadJobs();
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.setFilters({ status: null, job_type: null });
    }

    /**
     * Get current jobs
     * @returns {Array} - Current jobs array
     */
    getJobs() {
        return this.jobs;
    }

    /**
     * Clean up component
     */
    destroy() {
        this.stopAutoRefresh();
        this.container.innerHTML = '';
        if (window.jobList === this) {
            window.jobList = null;
        }
    }

    /**
     * Format status for display
     * @param {string} status - Raw status
     * @returns {string} - Formatted status
     */
    formatStatus(status) {
        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    /**
     * Format timestamp for display
     * @param {string} isoString - ISO timestamp
     * @returns {string} - Formatted time
     */
    formatTime(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diff = (now - date) / 1000;

        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return date.toLocaleDateString();
    }

    /**
     * Escape HTML special characters
     * @param {string} str - String to escape
     * @returns {string} - Escaped string
     */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Export
window.JobListComponent = JobListComponent;
