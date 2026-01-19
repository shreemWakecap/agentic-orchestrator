/**
 * Job Status Component
 *
 * Displays job status with progress bar, phase indicator,
 * and action buttons.
 *
 * Usage:
 *   const status = new JobStatusComponent('#job-container', 'abc123', {
 *       showActions: true,
 *       autoRefresh: true,
 *       onRetry: (newJob) => console.log('Retried:', newJob.job_id),
 *   });
 *
 *   // Later: cleanup
 *   status.destroy();
 */

class JobStatusComponent {
    /**
     * Create a job status component
     * @param {string|Element} container - Container selector or element
     * @param {string} jobId - Job ID to display
     * @param {Object} options - Component options
     */
    constructor(container, jobId, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        this.jobId = jobId;
        this.options = {
            showActions: true,
            showLogs: false,
            autoRefresh: true,
            compactMode: false,
            ...options
        };
        this.job = null;
        this.eventStream = null;
        this.elements = {};

        if (!this.container) {
            throw new Error('JobStatusComponent: Container not found');
        }

        this.render();
        if (this.options.autoRefresh) {
            this.startUpdates();
        }
    }

    /**
     * Render the component HTML
     */
    render() {
        const compactClass = this.options.compactMode ? 'job-status-compact' : '';

        this.container.innerHTML = `
            <div class="job-status ${compactClass}" data-job-id="${this.jobId}">
                <div class="job-status-header">
                    <span class="job-id" title="${this.jobId}">${this.jobId.substring(0, 8)}...</span>
                    <span class="job-type"></span>
                    <span class="job-status-badge"></span>
                </div>
                <div class="job-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                    <div class="progress-info">
                        <span class="progress-phase">Initializing...</span>
                        <span class="progress-percent">0%</span>
                    </div>
                </div>
                <div class="job-message"></div>
                <div class="job-timestamps">
                    <span class="created-at"></span>
                    <span class="duration"></span>
                </div>
                <div class="job-actions"></div>
                <div class="job-error" style="display: none;"></div>
            </div>
        `;

        this.elements = {
            root: this.container.querySelector('.job-status'),
            header: this.container.querySelector('.job-status-header'),
            type: this.container.querySelector('.job-type'),
            badge: this.container.querySelector('.job-status-badge'),
            progressBar: this.container.querySelector('.progress-bar'),
            progressFill: this.container.querySelector('.progress-fill'),
            phase: this.container.querySelector('.progress-phase'),
            percent: this.container.querySelector('.progress-percent'),
            message: this.container.querySelector('.job-message'),
            createdAt: this.container.querySelector('.created-at'),
            duration: this.container.querySelector('.duration'),
            actions: this.container.querySelector('.job-actions'),
            error: this.container.querySelector('.job-error'),
        };

        // Store component reference on DOM element
        this.elements.root.component = this;
    }

    /**
     * Update display with job data
     * @param {Object} job - Job data
     */
    update(job) {
        this.job = job;

        // Update type
        this.elements.type.textContent = job.job_type;
        this.elements.type.className = `job-type job-type-${job.job_type}`;

        // Update status badge
        this.elements.badge.textContent = this.formatStatus(job.status);
        this.elements.badge.className = `job-status-badge status-${job.status}`;

        // Update progress
        const percent = job.progress?.percent || 0;
        this.elements.progressFill.style.width = `${percent}%`;
        this.elements.phase.textContent = job.progress?.phase || this.getStatusPhase(job.status);
        this.elements.percent.textContent = `${percent}%`;

        // Update progress bar color based on status
        this.updateProgressBarColor(job.status);

        // Update message
        if (job.progress?.message) {
            this.elements.message.textContent = job.progress.message;
            this.elements.message.style.display = 'block';
        } else {
            this.elements.message.style.display = 'none';
        }

        // Update timestamps
        if (job.created_at) {
            this.elements.createdAt.textContent = `Created: ${this.formatTime(job.created_at)}`;
        }
        if (job.started_at) {
            const endTime = job.completed_at || new Date().toISOString();
            const duration = (new Date(endTime) - new Date(job.started_at)) / 1000;
            this.elements.duration.textContent = `Duration: ${this.formatDuration(duration)}`;
        }

        // Update error
        if (job.error) {
            this.elements.error.textContent = job.error;
            this.elements.error.style.display = 'block';
        } else {
            this.elements.error.style.display = 'none';
        }

        // Update actions
        if (this.options.showActions) {
            this.renderActions(job);
        }

        // Emit update event if callback provided
        if (this.options.onUpdate) {
            this.options.onUpdate(job);
        }
    }

    /**
     * Update progress bar color based on job status
     * @param {string} status - Job status
     */
    updateProgressBarColor(status) {
        const colors = {
            pending: '#ffc107',
            queued: '#17a2b8',
            running: '#007bff',
            succeeded: '#28a745',
            failed: '#dc3545',
            cancelled: '#6c757d',
            resumable: '#fd7e14',
        };
        this.elements.progressFill.style.backgroundColor = colors[status] || '#007bff';
    }

    /**
     * Get display phase based on status
     * @param {string} status - Job status
     * @returns {string} - Phase display text
     */
    getStatusPhase(status) {
        const phases = {
            pending: 'Waiting to start',
            queued: 'In queue',
            running: 'Processing',
            succeeded: 'Completed',
            failed: 'Failed',
            cancelled: 'Cancelled',
            resumable: 'Can resume',
        };
        return phases[status] || status;
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
     * Render action buttons
     * @param {Object} job - Job data
     */
    renderActions(job) {
        const actions = [];

        if (window.jobManager.canCancel(job)) {
            actions.push(`
                <button class="btn btn-danger btn-sm job-action-cancel">
                    Cancel
                </button>
            `);
        }

        if (window.jobManager.canRetry(job)) {
            actions.push(`
                <button class="btn btn-primary btn-sm job-action-retry">
                    Retry
                </button>
            `);
        }

        if (window.jobManager.canResume(job)) {
            actions.push(`
                <button class="btn btn-success btn-sm job-action-resume">
                    Resume
                </button>
            `);
        }

        actions.push(`
            <button class="btn btn-secondary btn-sm job-action-logs">
                View Logs
            </button>
        `);

        this.elements.actions.innerHTML = actions.join(' ');

        // Attach event listeners
        this.elements.actions.querySelector('.job-action-cancel')?.addEventListener('click', () => this.cancel());
        this.elements.actions.querySelector('.job-action-retry')?.addEventListener('click', () => this.retry());
        this.elements.actions.querySelector('.job-action-resume')?.addEventListener('click', () => this.showResumeDialog());
        this.elements.actions.querySelector('.job-action-logs')?.addEventListener('click', () => this.showLogs());
    }

    /**
     * Cancel the job
     */
    async cancel() {
        if (confirm('Are you sure you want to cancel this job?')) {
            try {
                const job = await window.jobManager.cancelJob(this.jobId);
                this.update(job);
            } catch (error) {
                this.showError('Failed to cancel job: ' + error.message);
            }
        }
    }

    /**
     * Retry the job
     */
    async retry() {
        try {
            const newJob = await window.jobManager.retryJob(this.jobId);
            if (this.options.onRetry) {
                this.options.onRetry(newJob);
            } else {
                alert(`Retry job created: ${newJob.job_id}`);
            }
        } catch (error) {
            this.showError('Failed to retry job: ' + error.message);
        }
    }

    /**
     * Show resume checkpoint dialog
     */
    async showResumeDialog() {
        try {
            const checkpointsData = await window.jobManager.getCheckpoints(this.jobId);
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
                const newJob = await window.jobManager.resumeJob(this.jobId, selected.trim());
                if (this.options.onResume) {
                    this.options.onResume(newJob);
                } else {
                    alert(`Resume job created: ${newJob.job_id}`);
                }
            }
        } catch (error) {
            this.showError('Failed to resume job: ' + error.message);
        }
    }

    /**
     * Show logs for the job
     */
    showLogs() {
        if (this.options.onShowLogs) {
            this.options.onShowLogs(this.jobId);
        } else {
            window.open(`/jobs/${this.jobId}/logs`, '_blank');
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
     * Start automatic status updates
     */
    startUpdates() {
        window.jobManager.startPolling(this.jobId, (job) => {
            this.update(job);
        });
    }

    /**
     * Stop automatic status updates
     */
    stopUpdates() {
        window.jobManager.stopPolling(this.jobId);
    }

    /**
     * Clean up component
     */
    destroy() {
        this.stopUpdates();
        if (this.eventStream) {
            this.eventStream.close();
        }
        this.container.innerHTML = '';
    }

    /**
     * Format ISO timestamp for display
     * @param {string} isoString - ISO timestamp
     * @returns {string} - Formatted time
     */
    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    }

    /**
     * Format duration in seconds
     * @param {number} seconds - Duration in seconds
     * @returns {string} - Formatted duration
     */
    formatDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    }

    /**
     * Manually refresh the job status
     */
    async refresh() {
        try {
            const job = await window.jobManager.getJob(this.jobId);
            this.update(job);
        } catch (error) {
            this.showError('Failed to refresh: ' + error.message);
        }
    }
}

// Export
window.JobStatusComponent = JobStatusComponent;
