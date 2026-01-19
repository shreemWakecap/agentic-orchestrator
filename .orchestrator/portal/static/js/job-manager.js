/**
 * Job Manager - Core job management functionality
 *
 * Handles job submission, status polling, and provides
 * a unified interface for job operations.
 *
 * Usage:
 *   // Submit a job
 *   const job = await jobManager.submitJob('plan', { spec_id: 'feat-001' });
 *
 *   // Track job status
 *   jobManager.startPolling(job.job_id, (updatedJob) => {
 *       console.log('Job status:', updatedJob.status);
 *   });
 *
 *   // Listen for events
 *   jobManager.on('jobComplete', (job) => {
 *       console.log('Job finished:', job.job_id);
 *   });
 */

class JobManager {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || '/api/jobs';
        this.pollInterval = options.pollInterval || 2000;
        this.activePollers = new Map();
        this.eventHandlers = new Map();
    }

    // =========================================================================
    // Event Handling
    // =========================================================================

    /**
     * Register an event handler
     * @param {string} event - Event name (jobSubmitted, jobComplete, jobCancelled, error)
     * @param {Function} handler - Handler function
     * @returns {JobManager} - For chaining
     */
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
        return this;
    }

    /**
     * Remove an event handler
     * @param {string} event - Event name
     * @param {Function} handler - Handler to remove
     * @returns {JobManager} - For chaining
     */
    off(event, handler) {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
        return this;
    }

    /**
     * Emit an event to all registered handlers
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        const handlers = this.eventHandlers.get(event) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (e) {
                console.error(`Error in event handler for ${event}:`, e);
            }
        });
    }

    // =========================================================================
    // Job Submission
    // =========================================================================

    /**
     * Submit a new job
     * @param {string} jobType - Job type (plan, build, review, fix, sync, docs, experts)
     * @param {Object} parameters - Job-specific parameters
     * @param {Object} options - Additional options (priority, timeout)
     * @returns {Promise<Object>} - Submitted job details
     */
    async submitJob(jobType, parameters, options = {}) {
        const payload = {
            job_type: jobType,
            parameters: parameters,
            priority: options.priority || 3,
            timeout_seconds: options.timeout || 3600,
        };

        try {
            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to submit job');
            }

            const job = await response.json();
            this.emit('jobSubmitted', job);
            return job;
        } catch (error) {
            this.emit('error', { operation: 'submit', error });
            throw error;
        }
    }

    /**
     * Submit a plan job
     * @param {string} specId - Spec ID to plan
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} - Submitted job
     */
    async submitPlan(specId, options = {}) {
        return this.submitJob('plan', { spec_id: specId, ...options.params }, options);
    }

    /**
     * Submit a build job
     * @param {string} specId - Spec ID to build
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} - Submitted job
     */
    async submitBuild(specId, options = {}) {
        return this.submitJob('build', { spec_id: specId, ...options.params }, options);
    }

    /**
     * Submit a review job
     * @param {string} specId - Spec ID to review
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} - Submitted job
     */
    async submitReview(specId, options = {}) {
        return this.submitJob('review', { spec_id: specId, ...options.params }, options);
    }

    /**
     * Submit a sync job
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} - Submitted job
     */
    async submitSync(options = {}) {
        return this.submitJob('sync', options.params || {}, options);
    }

    // =========================================================================
    // Job Status
    // =========================================================================

    /**
     * Get job details by ID
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} - Job details
     */
    async getJob(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/${jobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error(`Job ${jobId} not found`);
                }
                throw new Error('Failed to fetch job');
            }
            return await response.json();
        } catch (error) {
            this.emit('error', { operation: 'getJob', jobId, error });
            throw error;
        }
    }

    /**
     * List jobs with optional filtering
     * @param {Object} filters - Filter options (status, job_type, limit, offset)
     * @returns {Promise<Object>} - Job list response
     */
    async listJobs(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status) params.append('status', filters.status);
        if (filters.job_type) params.append('job_type', filters.job_type);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        try {
            const url = `${this.baseUrl}?${params.toString()}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to fetch jobs');
            }
            return await response.json();
        } catch (error) {
            this.emit('error', { operation: 'listJobs', error });
            throw error;
        }
    }

    // =========================================================================
    // Job Control
    // =========================================================================

    /**
     * Cancel a running or pending job
     * @param {string} jobId - Job ID to cancel
     * @param {string} reason - Cancellation reason
     * @returns {Promise<Object>} - Updated job details
     */
    async cancelJob(jobId, reason = 'User cancelled') {
        try {
            const response = await fetch(`${this.baseUrl}/${jobId}/cancel`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ reason }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to cancel job');
            }

            const job = await response.json();
            this.emit('jobCancelled', job);
            this.stopPolling(jobId);
            return job;
        } catch (error) {
            this.emit('error', { operation: 'cancel', jobId, error });
            throw error;
        }
    }

    /**
     * Retry a failed or cancelled job
     * @param {string} jobId - Job ID to retry
     * @returns {Promise<Object>} - New job details
     */
    async retryJob(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/${jobId}/retry`, {
                method: 'POST',
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to retry job');
            }

            const newJob = await response.json();
            this.emit('jobRetried', { originalJobId: jobId, newJob });
            return newJob;
        } catch (error) {
            this.emit('error', { operation: 'retry', jobId, error });
            throw error;
        }
    }

    /**
     * Resume a job from a checkpoint
     * @param {string} jobId - Job ID to resume
     * @param {string} checkpointId - Checkpoint to resume from
     * @returns {Promise<Object>} - New job details
     */
    async resumeJob(jobId, checkpointId) {
        try {
            const response = await fetch(`${this.baseUrl}/${jobId}/resume`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ checkpoint_id: checkpointId }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to resume job');
            }

            const newJob = await response.json();
            this.emit('jobResumed', { originalJobId: jobId, checkpointId, newJob });
            return newJob;
        } catch (error) {
            this.emit('error', { operation: 'resume', jobId, error });
            throw error;
        }
    }

    // =========================================================================
    // Polling
    // =========================================================================

    /**
     * Start polling for job status updates
     * @param {string} jobId - Job ID to poll
     * @param {Function} callback - Callback for each status update
     */
    startPolling(jobId, callback) {
        if (this.activePollers.has(jobId)) {
            return; // Already polling
        }

        const poll = async () => {
            try {
                const job = await this.getJob(jobId);
                callback(job);

                // Stop polling if job is in terminal state
                if (['succeeded', 'failed', 'cancelled', 'resumable'].includes(job.status)) {
                    this.stopPolling(jobId);
                    this.emit('jobComplete', job);
                }
            } catch (error) {
                console.error(`Polling error for job ${jobId}:`, error);
            }
        };

        // Initial fetch
        poll();

        // Set up interval
        const intervalId = setInterval(poll, this.pollInterval);
        this.activePollers.set(jobId, intervalId);
    }

    /**
     * Stop polling for a specific job
     * @param {string} jobId - Job ID to stop polling
     */
    stopPolling(jobId) {
        const intervalId = this.activePollers.get(jobId);
        if (intervalId) {
            clearInterval(intervalId);
            this.activePollers.delete(jobId);
        }
    }

    /**
     * Stop all active polling
     */
    stopAllPolling() {
        this.activePollers.forEach((intervalId, jobId) => {
            clearInterval(intervalId);
        });
        this.activePollers.clear();
    }

    /**
     * Check if a job is being polled
     * @param {string} jobId - Job ID
     * @returns {boolean} - True if polling is active
     */
    isPolling(jobId) {
        return this.activePollers.has(jobId);
    }

    // =========================================================================
    // Logs
    // =========================================================================

    /**
     * Get logs for a job
     * @param {string} jobId - Job ID
     * @param {Object} options - Options (level, limit, offset)
     * @returns {Promise<Object>} - Log entries
     */
    async getLogs(jobId, options = {}) {
        const params = new URLSearchParams();
        if (options.level) params.append('level', options.level);
        if (options.limit) params.append('limit', options.limit);
        if (options.offset) params.append('offset', options.offset);

        try {
            const url = `${this.baseUrl}/${jobId}/logs?${params.toString()}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to fetch logs');
            }
            return await response.json();
        } catch (error) {
            this.emit('error', { operation: 'getLogs', jobId, error });
            throw error;
        }
    }

    // =========================================================================
    // Checkpoints
    // =========================================================================

    /**
     * Get checkpoints for a job
     * @param {string} jobId - Job ID
     * @returns {Promise<Object>} - Checkpoints response
     */
    async getCheckpoints(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/${jobId}/checkpoints`);
            if (!response.ok) {
                throw new Error('Failed to fetch checkpoints');
            }
            return await response.json();
        } catch (error) {
            this.emit('error', { operation: 'getCheckpoints', jobId, error });
            throw error;
        }
    }

    // =========================================================================
    // Worker Pool Status
    // =========================================================================

    /**
     * Get worker pool status
     * @returns {Promise<Object>} - Pool status
     */
    async getPoolStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/pool/status`);
            if (!response.ok) {
                throw new Error('Failed to fetch pool status');
            }
            return await response.json();
        } catch (error) {
            this.emit('error', { operation: 'getPoolStatus', error });
            throw error;
        }
    }

    // =========================================================================
    // Utility Methods
    // =========================================================================

    /**
     * Check if a status is terminal (job finished)
     * @param {string} status - Job status
     * @returns {boolean} - True if terminal
     */
    isTerminalStatus(status) {
        return ['succeeded', 'failed', 'cancelled', 'resumable'].includes(status);
    }

    /**
     * Check if a job can be cancelled
     * @param {Object} job - Job object
     * @returns {boolean} - True if cancellable
     */
    canCancel(job) {
        return ['pending', 'queued', 'running'].includes(job.status);
    }

    /**
     * Check if a job can be retried
     * @param {Object} job - Job object
     * @returns {boolean} - True if retryable
     */
    canRetry(job) {
        return ['failed', 'cancelled'].includes(job.status);
    }

    /**
     * Check if a job can be resumed
     * @param {Object} job - Job object
     * @returns {boolean} - True if resumable
     */
    canResume(job) {
        return job.status === 'resumable';
    }
}

// Create global instance
window.jobManager = new JobManager();
