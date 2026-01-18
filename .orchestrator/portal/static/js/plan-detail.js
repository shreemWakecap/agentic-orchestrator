/**
 * Plan Detail Page Module
 *
 * Handles build/review workflow initiation and inline progress tracking.
 * Uses SSE (Server-Sent Events) for real-time progress updates.
 *
 * Dependencies:
 * - Toast (toast.js) - For notifications
 * - SSEConnectionManager (sse-manager.js) - For SSE handling with reconnection
 */

const PlanDetail = (function() {
    'use strict';

    // State
    let currentRunId = null;
    let sseManager = null;
    let buildStartTime = null;
    let steps = [];
    let stepStartTimes = {};
    let expandedSteps = new Set();
    let pollingTimer = null;
    let cleanupFunctions = [];

    // Progress tracking state
    let completedStepCount = 0;
    let totalStepCount = 0;
    let stepDurations = []; // Array of step durations in milliseconds

    // LocalStorage key for persisting active build state
    const ACTIVE_BUILD_STORAGE_KEY = 'planDetail_activeBuild';

    /**
     * Save active build state to localStorage
     * @param {string} planId - The plan ID
     * @param {string} runId - The run ID
     * @param {Object} progress - Current progress state
     */
    function saveActiveBuild(planId, runId, progress) {
        if (!planId || !runId) return;
        try {
            const buildState = {
                plan_id: planId,
                run_id: runId,
                last_progress: progress || {},
                timestamp: Date.now()
            };
            localStorage.setItem(ACTIVE_BUILD_STORAGE_KEY, JSON.stringify(buildState));
        } catch (e) {
            console.warn('Failed to save active build to localStorage:', e);
        }
    }

    /**
     * Load active build state from localStorage
     * @returns {Object|null} Saved build state or null
     */
    function loadActiveBuild() {
        try {
            const stored = localStorage.getItem(ACTIVE_BUILD_STORAGE_KEY);
            if (!stored) return null;
            const buildState = JSON.parse(stored);
            // Expire after 24 hours
            if (Date.now() - buildState.timestamp > 24 * 60 * 60 * 1000) {
                clearActiveBuild();
                return null;
            }
            return buildState;
        } catch (e) {
            console.warn('Failed to load active build from localStorage:', e);
            return null;
        }
    }

    /**
     * Clear active build state from localStorage
     */
    function clearActiveBuild() {
        try {
            localStorage.removeItem(ACTIVE_BUILD_STORAGE_KEY);
        } catch (e) {
            console.warn('Failed to clear active build from localStorage:', e);
        }
    }

    /**
     * Update the stored progress for the active build
     * @param {Object} progressUpdate - Progress data to merge
     */
    function updateStoredProgress(progressUpdate) {
        const stored = loadActiveBuild();
        if (stored) {
            stored.last_progress = Object.assign({}, stored.last_progress, progressUpdate);
            stored.timestamp = Date.now();
            try {
                localStorage.setItem(ACTIVE_BUILD_STORAGE_KEY, JSON.stringify(stored));
            } catch (e) {
                console.debug('Failed to update stored progress:', e);
            }
        }
    }

    // DOM element cache
    const elements = {};

    /**
     * Cache DOM elements for performance
     */
    function cacheElements() {
        elements.buildSection = document.getElementById('build-section');
        elements.buildActions = document.getElementById('build-actions');
        elements.progressSection = document.getElementById('build-progress-section');
        elements.successSection = document.getElementById('build-success-section');
        elements.failedStepInfo = document.getElementById('failed-step-info');
        elements.progressBar = document.getElementById('progress-bar');
        elements.progressPercent = document.getElementById('progress-percent');
        elements.currentStepLabel = document.getElementById('current-step-label');
        elements.stepsList = document.getElementById('steps-list');
        elements.eventsLog = document.getElementById('events-log');
        elements.statusBadge = document.getElementById('plan-status-badge');
        elements.viewRunLink = document.getElementById('view-run-link');
        elements.buildDuration = document.getElementById('build-duration');
        elements.startBuildBtn = document.getElementById('start-build-btn');
        elements.resumeBuildBtn = document.getElementById('resume-build-btn');
        elements.pauseBuildBtn = document.getElementById('pause-build-btn');
        elements.connectionStatus = document.getElementById('connection-status');
        elements.stepsCompletedCount = document.getElementById('steps-completed-count');
        elements.estimatedTimeRemaining = document.getElementById('estimated-time-remaining') || document.getElementById('estimated-time');
    }

    /**
     * Create connection status indicator if it doesn't exist
     */
    function ensureConnectionStatusElement() {
        if (elements.connectionStatus) return;

        // Try to find a place to insert it (near current step label or progress section)
        const progressHeader = elements.progressSection ?
            elements.progressSection.querySelector('.flex.items-center') : null;

        if (progressHeader) {
            const statusEl = document.createElement('div');
            statusEl.id = 'connection-status';
            statusEl.className = 'connection-status ml-2 flex items-center text-xs';
            statusEl.innerHTML = '<span class="status-dot w-2 h-2 rounded-full bg-gray-400 mr-1"></span><span class="status-text text-gray-500">Disconnected</span>';
            progressHeader.appendChild(statusEl);
            elements.connectionStatus = statusEl;
        }
    }

    /**
     * Update connection status indicator
     * @param {string} state - Connection state from SSEConnectionManager
     * @param {boolean} isPolling - Whether using polling fallback
     */
    function updateConnectionStatus(state, isPolling) {
        ensureConnectionStatusElement();
        if (!elements.connectionStatus) return;

        const dot = elements.connectionStatus.querySelector('.status-dot');
        const text = elements.connectionStatus.querySelector('.status-text');

        if (!dot || !text) return;

        const configs = {
            connecting: { dot: 'bg-yellow-400 animate-pulse', text: 'Connecting...', label: 'Connecting' },
            connected: { dot: 'bg-green-400', text: 'text-green-600', label: isPolling ? 'Polling' : 'Live' },
            reconnecting: { dot: 'bg-yellow-400 animate-pulse', text: 'text-yellow-600', label: 'Reconnecting...' },
            disconnected: { dot: 'bg-gray-400', text: 'text-gray-500', label: 'Disconnected' },
            failed: { dot: 'bg-red-400', text: 'text-red-600', label: 'Connection failed' }
        };

        const config = configs[state] || configs.disconnected;

        // Update dot classes
        dot.className = 'status-dot w-2 h-2 rounded-full mr-1 ' + config.dot;

        // Update text
        text.className = 'status-text ' + config.text;
        text.textContent = config.label;

        elements.connectionStatus.classList.remove('hidden');
    }

    /**
     * Hide connection status indicator
     */
    function hideConnectionStatus() {
        if (elements.connectionStatus) {
            elements.connectionStatus.classList.add('hidden');
        }
    }

    /**
     * Initialize the module
     */
    function init() {
        cacheElements();

        // First, check localStorage for a persisted active build for this plan
        const currentPlanId = window.PLAN_DATA && window.PLAN_DATA.id;
        const storedBuild = loadActiveBuild();

        if (storedBuild && storedBuild.plan_id === currentPlanId && storedBuild.run_id) {
            console.log('Found persisted active build in localStorage:', storedBuild);
            // Restore from localStorage and attempt reconnection
            currentRunId = storedBuild.run_id;
            attemptBuildReconnection(storedBuild);
        } else if (window.PLAN_DATA) {
            // Check if there's an active or previous build for this plan via API
            // Trigger for any state that might have build progress to restore
            const planState = window.PLAN_DATA.state || window.PLAN_DATA.status;
            const progressStates = ['in-progress', 'building', 'in_progress', 'failed', 'paused'];
            if (progressStates.includes(planState)) {
                checkForActiveRun();
            }
        }

        // Clean up on page unload
        window.addEventListener('beforeunload', function() {
            stopEventStream();
        });

        // Clean up on visibility change (tab hidden)
        document.addEventListener('visibilitychange', function() {
            if (document.hidden && sseManager) {
                // Optionally pause connection when tab is hidden
                console.log('Tab hidden, SSE connection maintained');
            }
        });
    }

    /**
     * Attempt to reconnect to an active build from localStorage state
     * @param {Object} storedBuild - The stored build state from localStorage
     */
    async function attemptBuildReconnection(storedBuild) {
        try {
            // Show progress section immediately with cached progress
            showProgressSection();

            if (storedBuild.last_progress) {
                // Restore cached progress immediately for instant feedback
                if (storedBuild.last_progress.progress !== undefined) {
                    updateProgress(storedBuild.last_progress.progress);
                }
                if (storedBuild.last_progress.current_step) {
                    updateCurrentStep(storedBuild.last_progress.current_step);
                }
            }

            addLogEntry('Restoring build from previous session...', 'info');

            // Verify the run is still active by fetching current status
            const response = await fetch('/api/runs/' + storedBuild.run_id);
            if (!response.ok) {
                console.warn('Stored run not found, clearing localStorage');
                clearActiveBuild();
                return;
            }

            const data = await response.json();
            const run = data.run || data;

            if (run.status === 'running' || run.status === 'in_progress') {
                // Run is still active, reconnect to SSE stream
                addLogEntry('Reconnecting to active build...', 'info');
                startEventStream(storedBuild.run_id);
            } else if (run.status === 'completed') {
                // Run completed while we were away
                clearActiveBuild();
                handleBuildComplete('completed');
            } else if (run.status === 'failed') {
                // Run failed while we were away
                clearActiveBuild();
                handleBuildComplete('failed');
            } else if (run.status === 'paused' || run.status === 'cancelled') {
                // Run was paused
                clearActiveBuild();
                updateStatusBadge('paused');
                addLogEntry('Build was paused', 'warning');
            } else {
                // Unknown status, clear and fall back to normal check
                clearActiveBuild();
                checkForActiveRun();
            }
        } catch (error) {
            console.error('Failed to reconnect to active build:', error);
            clearActiveBuild();
            // Fall back to normal active run check
            checkForActiveRun();
        }
    }

    /**
     * Check for an active run for this plan and restore progress state
     */
    async function checkForActiveRun() {
        try {
            // Get plan_id from PLAN_DATA
            const planId = window.PLAN_DATA && window.PLAN_DATA.id;
            if (!planId) {
                console.warn('No plan ID available for progress check');
                return;
            }

            // Fetch build progress from the dedicated endpoint
            const progressResponse = await fetch('/api/plans/' + encodeURIComponent(planId) + '/build-progress');
            if (!progressResponse.ok) {
                console.warn('Failed to fetch build progress:', progressResponse.status);
                return;
            }

            const progressData = await progressResponse.json();

            // Check if there's actual progress to restore
            if (!progressData || progressData.status === 'pending') {
                console.log('No active build progress to restore');
                return;
            }

            // Restore run ID if available
            if (progressData.run_id) {
                currentRunId = progressData.run_id;
            }

            // Show progress section and initialize steps
            showProgressSection();

            // Initialize steps with restored status from API
            if (progressData.steps && progressData.steps.length > 0) {
                initializeStepsFromProgress(progressData.steps, progressData.current_step);
            }

            // Update overall progress bar
            if (progressData.progress_percentage !== undefined) {
                updateProgress(progressData.progress_percentage);
            }

            // Update current step label
            if (progressData.current_step) {
                updateCurrentStep(progressData.current_step);
            }

            // Add log entry about restoration
            addLogEntry('Restored build progress from previous session', 'info');

            // If build is still running, connect to SSE stream
            if (progressData.status === 'running' && progressData.run_id) {
                addLogEntry('Reconnecting to build stream...', 'info');
                startEventStream(progressData.run_id);
            } else if (progressData.status === 'completed') {
                handleBuildComplete('completed');
            } else if (progressData.status === 'failed') {
                addLogEntry('Build failed - check error details above', 'error');
                updateStatusBadge('failed');
            } else if (progressData.status === 'cancelled') {
                addLogEntry('Build was paused', 'warning');
                updateStatusBadge('paused');
            }

        } catch (error) {
            console.error('Error checking for active run:', error);
            // Fall back to legacy run check
            await checkForActiveRunLegacy();
        }
    }

    /**
     * Initialize steps from progress API response with pre-existing statuses
     * @param {Array} progressSteps - Steps from build-progress API
     * @param {string} currentStepId - ID of the currently running step
     */
    function initializeStepsFromProgress(progressSteps, currentStepId) {
        if (!elements.stepsList || !progressSteps) return;

        // Clear placeholder and existing steps
        elements.stepsList.innerHTML = '';
        steps = [];
        stepStartTimes = {};
        expandedSteps.clear();

        // Handle empty steps array
        if (progressSteps.length === 0) {
            elements.stepsList.innerHTML = '<div class="text-sm text-gray-500 italic">No steps defined in plan</div>';
            initializeProgressTracking(0, 0);
            return;
        }

        let initialCompletedCount = 0;
        progressSteps.forEach(function(step, index) {
            // Map API status to UI status
            let status = step.status || 'pending';

            // If this is the current step, mark it as running
            if (step.id === currentStepId && status === 'pending') {
                status = 'running';
            }

            const stepData = {
                id: step.id || 'step-' + (index + 1),
                label: step.label || step.title || step.name || 'Step ' + (index + 1),
                description: step.description || step.action || step.do || '',
                status: status,
                output: step.output || '',
                error: step.error || '',
                duration: step.duration || null
            };

            steps.push(stepData);
            renderStepElement(stepData, index);

            // Track start time for running steps
            if (status === 'running') {
                stepStartTimes[stepData.id] = new Date();
            }

            // Count already completed steps
            if (status === 'completed') {
                initialCompletedCount++;
            }
        });

        // Initialize progress tracking with step counts
        initializeProgressTracking(progressSteps.length, initialCompletedCount);
    }

    /**
     * Legacy fallback: Check for active run using runs API
     */
    async function checkForActiveRunLegacy() {
        try {
            const response = await fetch('/api/runs?status=running');
            const data = await response.json();

            if (data.runs && data.runs.length > 0) {
                const planRun = data.runs.find(function(r) {
                    return r.plan_path === window.PLAN_DATA.file ||
                           r.plan_id === window.PLAN_DATA.id;
                });

                if (planRun) {
                    currentRunId = planRun.id;
                    showProgressSection();
                    startEventStream(planRun.id);
                }
            }
        } catch (error) {
            console.error('Error checking for active run (legacy):', error);
        }
    }

    /**
     * Start build workflow
     * @param {string} planId - The plan identifier (folder name)
     */
    async function startBuild(planId) {
        try {
            disableButton(elements.startBuildBtn, 'Starting...');
            Toast.info('Starting build...');

            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start build');
            }

            if (data.run_id) {
                currentRunId = data.run_id;
                buildStartTime = new Date();

                // Save to localStorage for persistence across page refresh
                saveActiveBuild(planId, data.run_id, { progress: 0, current_step: 'Initializing...' });

                showProgressSection();
                hideFailedStepInfo();
                updateStatusBadge('in-progress');
                startEventStream(data.run_id);

                Toast.success('Build started');
            }
        } catch (error) {
            console.error('Error starting build:', error);
            Toast.error('Failed to start build: ' + error.message);
            enableButton(elements.startBuildBtn, 'Start Build');
        }
    }

    /**
     * Resume build workflow from failed/paused state
     * @param {string} planId - The plan identifier (folder name)
     */
    async function resumeBuild(planId) {
        try {
            disableButton(elements.resumeBuildBtn, 'Resuming...');
            Toast.info('Resuming build...');

            // Use /resume-build endpoint for plans that are in building/paused/failed state
            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/resume-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    from_step: window.PLAN_DATA.failedStep || window.PLAN_DATA.currentStep
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to resume build');
            }

            if (data.run_id) {
                currentRunId = data.run_id;
                buildStartTime = new Date();

                // Save to localStorage for persistence across page refresh
                saveActiveBuild(planId, data.run_id, { progress: 0, current_step: 'Resuming...' });

                showProgressSection();
                hideFailedStepInfo();
                updateStatusBadge('in-progress');
                startEventStream(data.run_id);

                Toast.success('Build resumed');
            }
        } catch (error) {
            console.error('Error resuming build:', error);
            Toast.error('Failed to resume build: ' + error.message);
            enableButton(elements.resumeBuildBtn, 'Resume Build');
        }
    }

    /**
     * Pause the current build
     */
    async function pauseBuild() {
        if (!currentRunId) {
            Toast.error('No active build to pause');
            return;
        }

        try {
            disableButton(elements.pauseBuildBtn, 'Pausing...');

            const response = await fetch('/api/runs/' + currentRunId + '/pause', {
                method: 'POST'
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Failed to pause build');
            }

            Toast.warning('Build paused');
            stopEventStream();

            // Clear localStorage since build is paused
            clearActiveBuild();

            updateStatusBadge('paused');
        } catch (error) {
            console.error('Error pausing build:', error);
            Toast.error('Failed to pause build: ' + error.message);
            enableButton(elements.pauseBuildBtn, 'Pause Build');
        }
    }

    /**
     * Start review workflow
     * @param {string} planId - The plan identifier (folder name)
     */
    async function startReview(planId) {
        try {
            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start review');
            }

            // Show toast only after successful API call
            Toast.info('Starting review...');

            if (data.run_id) {
                window.location.href = '/runs/' + data.run_id;
            }
        } catch (error) {
            console.error('Error starting review:', error);
            Toast.error('Failed to start review: ' + error.message);
        }
    }

    /**
     * Start SSE event stream for real-time updates using SSEConnectionManager
     * @param {string} runId - The run ID to stream events from
     */
    function startEventStream(runId) {
        // Clean up any existing connection
        stopEventStream();

        currentRunId = runId;
        const url = '/api/runs/' + runId + '/events';

        // Check if SSEConnectionManager is available
        if (typeof SSEConnectionManager === 'undefined') {
            console.warn('SSEConnectionManager not available, falling back to polling');
            startPollingFallback(runId);
            return;
        }

        // Create new SSE connection manager with configuration
        sseManager = new SSEConnectionManager(url, {
            maxReconnectAttempts: 5,
            initialReconnectDelay: 1000,
            maxReconnectDelay: 15000,
            heartbeatTimeout: 45000,
            enablePollingFallback: true,
            pollingInterval: 3000
        });

        // Set up polling fallback function
        sseManager.setPollingFallback(function() {
            return pollRunStatus(runId);
        });

        // Track cleanup functions
        cleanupFunctions = [];

        // Handle connection state changes
        var stateCleanup = sseManager.onStateChange(function(newState, oldState) {
            console.log('PlanDetail SSE state: ' + oldState + ' -> ' + newState);
            updateConnectionStatus(newState, sseManager.isPollingMode());

            if (newState === 'connected') {
                if (sseManager.isPollingMode()) {
                    addLogEntry('Using polling fallback for updates', 'warning');
                } else {
                    addLogEntry('Connected to build stream', 'info');
                }
            } else if (newState === 'reconnecting') {
                addLogEntry('Connection lost, reconnecting...', 'warning');
            } else if (newState === 'failed') {
                addLogEntry('Connection failed, using polling fallback', 'error');
            }
        });
        cleanupFunctions.push(stateCleanup);

        // Handle incoming messages
        var messageCleanup = sseManager.onMessage(function(data, event) {
            if (data && typeof data === 'object') {
                handleEvent(data);
            }
        });
        cleanupFunctions.push(messageCleanup);

        // Connect
        sseManager.connect();
        updateConnectionStatus('connecting', false);
    }

    /**
     * Stop SSE event stream and clean up
     */
    function stopEventStream() {
        // Stop polling if active
        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }

        // Clean up SSE manager
        if (sseManager) {
            sseManager.disconnect();
            sseManager = null;
        }

        // Run cleanup functions
        cleanupFunctions.forEach(function(fn) {
            try {
                fn();
            } catch (e) {
                console.debug('Cleanup error:', e);
            }
        });
        cleanupFunctions = [];

        hideConnectionStatus();
    }

    /**
     * Start polling fallback when SSE is not available
     * @param {string} runId - The run ID to poll
     */
    function startPollingFallback(runId) {
        console.log('Starting polling fallback for run:', runId);
        updateConnectionStatus('connected', true);
        addLogEntry('Using polling mode (SSE unavailable)', 'warning');

        // Initial poll
        pollRunStatus(runId);

        // Start polling interval
        pollingTimer = setInterval(function() {
            pollRunStatus(runId);
        }, 3000);
    }

    /**
     * Poll run status endpoint as fallback
     * @param {string} runId - The run ID to poll
     * @returns {Promise} Promise resolving when poll completes
     */
    async function pollRunStatus(runId) {
        try {
            const response = await fetch('/api/runs/' + runId);
            if (!response.ok) {
                throw new Error('Failed to fetch run status');
            }

            const data = await response.json();

            // Convert run status to events
            if (data.run) {
                const run = data.run;

                // Update progress if available
                if (run.progress !== undefined) {
                    handleEvent({ type: 'progress', progress: run.progress });
                }

                // Update current step
                if (run.current_step) {
                    handleEvent({ type: 'step', step: run.current_step });
                }

                // Check for completion
                if (run.status === 'completed') {
                    handleEvent({ type: 'done', status: 'completed' });
                    stopEventStream();
                } else if (run.status === 'failed') {
                    handleEvent({ type: 'error', message: run.error || 'Build failed' });
                    stopEventStream();
                } else if (run.status === 'paused') {
                    stopEventStream();
                }
            }
        } catch (error) {
            console.debug('Poll error:', error);
        }
    }

    /**
     * Handle incoming SSE event
     * @param {Object} event - The event data
     */
    function handleEvent(event) {
        // Update progress bar
        if (event.progress !== undefined) {
            updateProgress(event.progress);
            // Update stored progress for persistence
            updateStoredProgress({ progress: event.progress });
        }

        // Update current step
        if (event.step) {
            updateCurrentStep(event.step);
            // Update stored progress for persistence
            updateStoredProgress({ current_step: event.step });
        }

        // Handle steps initialization from event
        if (event.type === 'init' && event.steps) {
            initializeSteps(event.steps);
        }

        // Handle step updates with extra data
        if (event.type === 'step_start') {
            addOrUpdateStep(event.step_id || event.step, 'running', event.step, {
                description: event.description || event.action || ''
            });
        } else if (event.type === 'step_complete') {
            addOrUpdateStep(event.step_id || event.step, 'completed', event.step, {
                output: event.output || event.result || '',
                description: event.description || ''
            });
        } else if (event.type === 'step_failed') {
            addOrUpdateStep(event.step_id || event.step, 'failed', event.step, {
                error: event.error || event.message || 'Step failed',
                output: event.output || ''
            });
        } else if (event.type === 'step_output') {
            // Partial output update
            const stepIndex = steps.findIndex(function(s) {
                return s.id === (event.step_id || event.step);
            });
            if (stepIndex >= 0) {
                steps[stepIndex].output = (steps[stepIndex].output || '') + (event.output || '');
                const stepEl = document.getElementById('step-' + steps[stepIndex].id);
                if (stepEl) {
                    updateStepElementContent(stepEl, steps[stepIndex], stepIndex);
                }
            }
        }

        // Add to log
        addLogEntry(event.message || event.step || event.type, event.type);

        // Handle completion
        if (event.type === 'done' || event.type === 'complete') {
            handleBuildComplete(event.status || 'completed');
        }

        // Handle errors
        if (event.type === 'error') {
            handleBuildError(event.message || 'Unknown error');
        }
    }

    /**
     * Update progress bar
     * @param {number} progress - Progress percentage (0-100)
     */
    function updateProgress(progress) {
        const percent = Math.max(0, Math.min(100, progress));

        if (elements.progressBar) {
            elements.progressBar.style.width = percent + '%';
        }

        if (elements.progressPercent) {
            elements.progressPercent.textContent = Math.round(percent) + '%';
        }
    }

    /**
     * Update current step display
     * @param {string} step - Current step name
     */
    function updateCurrentStep(step) {
        if (elements.currentStepLabel) {
            elements.currentStepLabel.textContent = step;
        }
    }

    /**
     * Initialize steps from plan data before build starts
     * @param {Array} planSteps - Array of step objects from plan
     */
    function initializeSteps(planSteps) {
        if (!elements.stepsList || !planSteps) return;

        // Clear placeholder and existing steps
        elements.stepsList.innerHTML = '';
        steps = [];
        stepStartTimes = {};
        expandedSteps.clear();

        // Handle empty steps array
        if (planSteps.length === 0) {
            elements.stepsList.innerHTML = '<div class="text-sm text-gray-500 italic">No steps defined in plan</div>';
            initializeProgressTracking(0, 0);
            return;
        }

        let initialCompletedCount = 0;
        planSteps.forEach(function(step, index) {
            const stepData = {
                id: step.id || 'step-' + (index + 1),
                label: step.title || step.label || step.name || 'Step ' + (index + 1),
                description: step.description || step.action || step.do || '',
                status: step.status || 'pending',
                output: step.output || '',
                error: '',
                duration: null
            };
            steps.push(stepData);
            renderStepElement(stepData, index);

            // Count already completed steps
            if (stepData.status === 'completed') {
                initialCompletedCount++;
            }
        });

        // Initialize progress tracking with step counts
        initializeProgressTracking(planSteps.length, initialCompletedCount);
    }

    /**
     * Clear the placeholder from steps list
     */
    function clearStepsPlaceholder() {
        if (!elements.stepsList) return;
        var placeholder = elements.stepsList.querySelector('.step-placeholder');
        if (placeholder) {
            placeholder.remove();
        }
    }

    /**
     * Render a step element with timeline styling and connector lines
     * @param {Object} stepData - Step data object
     * @param {number} index - Step index
     */
    function renderStepElement(stepData, index) {
        if (!elements.stepsList) return;

        const stepEl = document.createElement('div');
        stepEl.id = 'step-' + stepData.id;
        stepEl.className = 'timeline-step';
        stepEl.dataset.stepId = stepData.id;

        updateStepElementContent(stepEl, stepData, index);
        elements.stepsList.appendChild(stepEl);
    }

    /**
     * Get the timeline dot class based on step status
     * @param {string} status - Step status
     * @returns {string} CSS class for the timeline dot
     */
    function getTimelineDotClass(status) {
        var dotClasses = {
            pending: 'timeline-dot-pending',
            running: 'timeline-dot-running',
            completed: 'timeline-dot-completed',
            failed: 'timeline-dot-failed'
        };
        return dotClasses[status] || dotClasses.pending;
    }

    /**
     * Get the timeline dot icon based on step status
     * @param {string} status - Step status
     * @param {number} stepNumber - Step number for display
     * @returns {string} HTML for the dot icon
     */
    function getTimelineDotIcon(status, stepNumber) {
        if (status === 'completed') {
            return '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
        } else if (status === 'running') {
            return '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';
        } else if (status === 'failed') {
            return '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
        } else {
            return '<span class="text-xs font-medium">' + stepNumber + '</span>';
        }
    }

    /**
     * Update step element content with timeline design and colored connectors
     * @param {HTMLElement} stepEl - Step DOM element
     * @param {Object} stepData - Step data object
     * @param {number} index - Step index
     */
    function updateStepElementContent(stepEl, stepData, index) {
        const statusConfig = getStepStatusConfig(stepData.status);
        const isExpanded = expandedSteps.has(stepData.id);
        const hasDetails = stepData.description || stepData.output || stepData.duration;
        const stepNumber = index + 1;
        const isLastStep = index === steps.length - 1;

        // Determine timeline step class based on status (for connector line coloring)
        var timelineStepClass = 'timeline-step';
        if (stepData.status === 'completed') {
            timelineStepClass += ' step-completed';
        } else if (stepData.status === 'running') {
            timelineStepClass += ' step-running';
        }
        // Hide connector for last step
        if (isLastStep) {
            timelineStepClass += ' last-step';
        }

        stepEl.className = timelineStepClass;

        // Get timeline dot class and icon
        var dotClass = getTimelineDotClass(stepData.status);
        var dotIcon = getTimelineDotIcon(stepData.status, stepNumber);

        // Step card class based on status
        var cardClass = 'step-card p-3';
        if (stepData.status === 'running') {
            cardClass += ' step-running';
        } else if (stepData.status === 'completed') {
            cardClass += ' step-completed';
        } else if (stepData.status === 'failed') {
            cardClass += ' step-failed';
        }
        if (hasDetails) {
            cardClass += ' cursor-pointer';
        }

        stepEl.innerHTML = [
            // Timeline dot (positioned absolutely via CSS)
            '<div class="timeline-dot ' + dotClass + '">',
            '  ' + dotIcon,
            '</div>',

            // Step card
            '<div class="' + cardClass + '">',
            '  <div class="flex items-center justify-between">',
            '    <div class="flex items-center min-w-0 flex-1">',
            '      <span class="step-number text-xs font-semibold text-gray-400 mr-2 bg-gray-100 px-1.5 py-0.5 rounded">#' + stepNumber + '</span>',
            '      <span class="step-label text-sm font-medium ' + statusConfig.textClass + ' truncate">' + escapeHtml(stepData.label) + '</span>',
            '    </div>',
            '    <div class="flex items-center ml-2 flex-shrink-0">',
                   stepData.duration ? '<span class="step-duration text-xs text-gray-500 mr-2 bg-gray-50 px-2 py-0.5 rounded">' + stepData.duration + '</span>' : '',
                   hasDetails ? '<svg class="step-chevron w-4 h-4 text-gray-400 transition-transform duration-200 ' +
                     (isExpanded ? 'rotated' : '') + '" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                     '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>' : '',
            '    </div>',
            '  </div>',

            // Status label for running/failed
            stepData.status === 'running' ?
                '<div class="step-status-label mt-2 text-xs text-blue-600 animate-pulse flex items-center">' +
                '  <span class="w-1.5 h-1.5 bg-blue-500 rounded-full mr-2 animate-ping"></span>' +
                '  In progress...' +
                '</div>' : '',
            stepData.status === 'failed' && stepData.error ?
                '<div class="step-status-label mt-2 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">' +
                '  <span class="font-medium">Error:</span> ' + escapeHtml(stepData.error) +
                '</div>' : '',

            // Expandable details section
            hasDetails ? [
                '<div class="step-details ' + (isExpanded ? 'expanded mt-3' : '') + '">',
                '  <div class="p-3 bg-gray-50 rounded-lg text-sm border border-gray-100">',
                     stepData.description ? '<div class="step-description text-gray-700 mb-2"><span class="font-medium text-gray-500 text-xs">Description:</span><br>' + escapeHtml(stepData.description) + '</div>' : '',
                     stepData.output ? [
                         '<div class="step-output mt-2">',
                         '  <div class="text-xs font-medium text-gray-500 mb-1">Output:</div>',
                         '  <pre class="text-xs text-gray-600 bg-white p-2 rounded border overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">' + escapeHtml(stepData.output) + '</pre>',
                         '</div>'
                     ].join('') : '',
                '  </div>',
                '</div>'
            ].join('') : '',

            '</div>'
        ].join('');

        // Add click handler for expandable steps
        if (hasDetails) {
            var header = stepEl.querySelector('.step-card');
            header.addEventListener('click', function() {
                toggleStepDetails(stepData.id);
            });
        }
    }

    /**
     * Toggle step details expansion
     * @param {string} stepId - Step identifier
     */
    function toggleStepDetails(stepId) {
        if (expandedSteps.has(stepId)) {
            expandedSteps.delete(stepId);
        } else {
            expandedSteps.add(stepId);
        }

        // Re-render the step
        const stepIndex = steps.findIndex(function(s) { return s.id === stepId; });
        if (stepIndex >= 0) {
            const stepEl = document.getElementById('step-' + stepId);
            if (stepEl) {
                updateStepElementContent(stepEl, steps[stepIndex], stepIndex);
            }
        }
    }

    /**
     * Add or update a step in the visualization
     * @param {string} stepId - Step identifier
     * @param {string} status - Step status (pending, running, completed, failed)
     * @param {string} label - Step label
     * @param {Object} extraData - Additional step data (description, output, error)
     */
    function addOrUpdateStep(stepId, status, label, extraData) {
        if (!elements.stepsList) return;

        // Clear placeholder on first step
        clearStepsPlaceholder();

        extraData = extraData || {};

        // Find existing step
        let stepIndex = steps.findIndex(function(s) { return s.id === stepId; });
        let stepEl = document.getElementById('step-' + stepId);

        // Track timing
        if (status === 'running' && !stepStartTimes[stepId]) {
            stepStartTimes[stepId] = new Date();
        }

        let duration = null;
        let durationMs = 0;
        if ((status === 'completed' || status === 'failed') && stepStartTimes[stepId]) {
            durationMs = new Date() - stepStartTimes[stepId];
            duration = formatDuration(durationMs);
        }

        // Check if this is a status transition to completed
        const wasCompleted = stepIndex >= 0 && steps[stepIndex].status === 'completed';
        const isBecomingCompleted = status === 'completed' && !wasCompleted;

        if (stepIndex < 0) {
            // New step - add to list
            const stepData = {
                id: stepId,
                label: label || stepId,
                description: extraData.description || '',
                status: status,
                output: extraData.output || '',
                error: extraData.error || '',
                duration: duration
            };
            steps.push(stepData);
            stepIndex = steps.length - 1;

            // Update total step count if this is a new step
            if (steps.length > totalStepCount) {
                totalStepCount = steps.length;
            }

            renderStepElement(stepData, stepIndex);

            // Record completion if new step is already completed
            if (status === 'completed') {
                recordStepCompletion(stepId, durationMs);
            }
        } else {
            // Update existing step
            steps[stepIndex].status = status;
            if (label) steps[stepIndex].label = label;
            if (extraData.description) steps[stepIndex].description = extraData.description;
            if (extraData.output) steps[stepIndex].output = extraData.output;
            if (extraData.error) steps[stepIndex].error = extraData.error;
            if (duration) steps[stepIndex].duration = duration;

            if (stepEl) {
                updateStepElementContent(stepEl, steps[stepIndex], stepIndex);
            }

            // Record completion for progress tracking
            if (isBecomingCompleted) {
                recordStepCompletion(stepId, durationMs);
            }
        }

        // Scroll the step into view if running
        if (status === 'running' && stepEl) {
            stepEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * Get step status configuration
     * @param {string} status - Step status
     * @returns {Object} Status configuration with classes and icon
     */
    function getStepStatusConfig(status) {
        var configs = {
            pending: {
                bgClass: 'bg-gray-200',
                textClass: 'text-gray-500',
                icon: '<span class="w-2 h-2 bg-gray-400 rounded-full"></span>'
            },
            running: {
                bgClass: 'bg-blue-100',
                textClass: 'text-blue-700 font-medium',
                icon: '<svg class="w-4 h-4 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>'
            },
            completed: {
                bgClass: 'bg-green-100',
                textClass: 'text-green-700',
                icon: '<svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
            },
            failed: {
                bgClass: 'bg-red-100',
                textClass: 'text-red-700 font-medium',
                icon: '<svg class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
            }
        };

        return configs[status] || configs.pending;
    }

    /**
     * Add entry to the build log
     * @param {string} message - Log message
     * @param {string} type - Event type (info, error, warning, etc.)
     */
    function addLogEntry(message, type) {
        if (!elements.eventsLog) return;

        // Remove "waiting" message on first entry
        const waitingMsg = elements.eventsLog.querySelector('.text-gray-500');
        if (waitingMsg && waitingMsg.textContent.includes('Waiting')) {
            waitingMsg.remove();
        }

        const timestamp = new Date().toLocaleTimeString();
        const typeColors = {
            error: 'text-red-400',
            warning: 'text-yellow-400',
            success: 'text-green-400',
            complete: 'text-green-400',
            done: 'text-green-400',
            step_complete: 'text-green-400',
            step_failed: 'text-red-400',
            step_start: 'text-blue-400',
            info: 'text-blue-400',
            default: 'text-gray-400'
        };

        const colorClass = typeColors[type] || typeColors.default;

        const entry = document.createElement('div');
        entry.className = 'py-0.5';
        entry.innerHTML = '<span class="text-gray-500">[' + timestamp + ']</span> <span class="' + colorClass + '">' + escapeHtml(message) + '</span>';

        elements.eventsLog.appendChild(entry);
        elements.eventsLog.scrollTop = elements.eventsLog.scrollHeight;
    }

    /**
     * Clear the build log
     */
    function clearLog() {
        if (elements.eventsLog) {
            elements.eventsLog.innerHTML = '<div class="text-gray-500">Log cleared</div>';
        }
    }

    /**
     * Handle build completion
     * @param {string} status - Final status
     */
    function handleBuildComplete(status) {
        stopEventStream();

        // Clear localStorage since build is complete
        clearActiveBuild();

        const duration = buildStartTime ? formatDuration(new Date() - buildStartTime) : '';

        if (status === 'completed' || status === 'success') {
            updateStatusBadge('completed');

            if (elements.successSection) {
                elements.successSection.classList.remove('hidden');
            }

            if (elements.buildDuration && duration) {
                elements.buildDuration.textContent = 'Completed in ' + duration;
            }

            if (elements.viewRunLink && currentRunId) {
                elements.viewRunLink.href = '/runs/' + currentRunId;
            }

            Toast.success('Build completed successfully!');
        } else {
            updateStatusBadge('failed');
            Toast.error('Build failed');
        }
    }

    /**
     * Handle build error
     * @param {string} message - Error message
     */
    function handleBuildError(message) {
        stopEventStream();

        // Clear localStorage since build has errored
        clearActiveBuild();

        updateStatusBadge('failed');
        Toast.error('Build error: ' + message);
    }

    /**
     * Show the inline progress section
     */
    function showProgressSection() {
        if (elements.progressSection) {
            elements.progressSection.classList.remove('hidden');
        }

        // Hide action buttons during build
        if (elements.startBuildBtn) {
            elements.startBuildBtn.classList.add('hidden');
        }
        if (elements.resumeBuildBtn) {
            elements.resumeBuildBtn.classList.add('hidden');
        }
    }

    /**
     * Hide the failed step info section
     */
    function hideFailedStepInfo() {
        if (elements.failedStepInfo) {
            elements.failedStepInfo.classList.add('hidden');
        }
    }

    /**
     * Update the plan status badge
     * @param {string} status - New status
     */
    function updateStatusBadge(status) {
        if (!elements.statusBadge) return;

        const statusConfig = {
            completed: { bg: 'bg-green-100', text: 'text-green-800' },
            pending: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
            'in-progress': { bg: 'bg-blue-100', text: 'text-blue-800' },
            paused: { bg: 'bg-orange-100', text: 'text-orange-800' },
            failed: { bg: 'bg-red-100', text: 'text-red-800' }
        };

        const config = statusConfig[status] || statusConfig.pending;

        // Remove existing status classes
        elements.statusBadge.className = elements.statusBadge.className.replace(/bg-\w+-100|text-\w+-800/g, '').trim();

        // Add new classes
        elements.statusBadge.classList.add(config.bg, config.text);
        elements.statusBadge.textContent = status;
    }

    /**
     * Disable a button and show loading state
     * @param {HTMLElement} btn - Button element
     * @param {string} text - Loading text
     */
    function disableButton(btn, text) {
        if (!btn) return;
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.innerHTML = '<svg class="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>' + text;
    }

    /**
     * Enable a button and restore text
     * @param {HTMLElement} btn - Button element
     * @param {string} text - Button text
     */
    function enableButton(btn, text) {
        if (!btn) return;
        btn.disabled = false;
        btn.textContent = text;
    }

    /**
     * Format duration in human-readable format
     * @param {number} ms - Duration in milliseconds
     * @returns {string} Formatted duration
     */
    function formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return hours + 'h ' + (minutes % 60) + 'm';
        } else if (minutes > 0) {
            return minutes + 'm ' + (seconds % 60) + 's';
        } else {
            return seconds + 's';
        }
    }

    /**
     * Calculate estimated time remaining based on average step duration
     * @returns {string|null} Formatted estimated time remaining or null if not calculable
     */
    function calculateEstimatedTimeRemaining() {
        if (stepDurations.length === 0 || completedStepCount >= totalStepCount) {
            return null;
        }

        // Calculate average duration of completed steps
        const totalDuration = stepDurations.reduce(function(sum, duration) {
            return sum + duration;
        }, 0);
        const avgDuration = totalDuration / stepDurations.length;

        // Calculate remaining steps
        const remainingSteps = totalStepCount - completedStepCount;

        // Estimate remaining time
        const estimatedRemainingMs = avgDuration * remainingSteps;

        return formatDuration(estimatedRemainingMs);
    }

    /**
     * Update the step count and estimated time display
     */
    function updateProgressDisplay() {
        // Ensure elements exist, create them if needed
        ensureProgressDisplayElements();

        // Update step count display
        if (elements.stepsCompletedCount) {
            elements.stepsCompletedCount.textContent = completedStepCount + ' of ' + totalStepCount + ' steps completed';
        }

        // Update estimated time remaining
        if (elements.estimatedTimeRemaining) {
            const estimatedTime = calculateEstimatedTimeRemaining();
            if (estimatedTime && completedStepCount < totalStepCount) {
                elements.estimatedTimeRemaining.textContent = 'Est. remaining: ' + estimatedTime;
                elements.estimatedTimeRemaining.classList.remove('hidden');
            } else if (completedStepCount >= totalStepCount && totalStepCount > 0) {
                elements.estimatedTimeRemaining.textContent = 'All steps completed';
                elements.estimatedTimeRemaining.classList.remove('hidden');
            } else {
                elements.estimatedTimeRemaining.textContent = '';
                elements.estimatedTimeRemaining.classList.add('hidden');
            }
        }
    }

    /**
     * Ensure progress display elements exist in the DOM
     */
    function ensureProgressDisplayElements() {
        // Find the progress section header area
        const progressHeader = elements.progressSection ?
            elements.progressSection.querySelector('.flex.items-center.justify-between') ||
            elements.progressSection.querySelector('.flex.items-center') : null;

        if (!progressHeader) return;

        // Create steps completed count element if it doesn't exist
        if (!elements.stepsCompletedCount) {
            const existingEl = document.getElementById('steps-completed-count');
            if (existingEl) {
                elements.stepsCompletedCount = existingEl;
            } else {
                const countEl = document.createElement('div');
                countEl.id = 'steps-completed-count';
                countEl.className = 'steps-completed-count text-sm font-medium text-gray-700';
                countEl.textContent = '0 of 0 steps completed';

                // Insert after progress bar area or at end of header
                const progressBarContainer = elements.progressSection.querySelector('.progress-bar-container') ||
                    elements.progressSection.querySelector('[class*="bg-gray-200"]');
                if (progressBarContainer && progressBarContainer.parentNode) {
                    progressBarContainer.parentNode.insertBefore(countEl, progressBarContainer.nextSibling);
                } else {
                    progressHeader.appendChild(countEl);
                }
                elements.stepsCompletedCount = countEl;
            }
        }

        // Create estimated time remaining element if it doesn't exist
        if (!elements.estimatedTimeRemaining) {
            // Try both ID formats for backward compatibility
            const existingEl = document.getElementById('estimated-time-remaining') || document.getElementById('estimated-time');
            if (existingEl) {
                elements.estimatedTimeRemaining = existingEl;
            } else {
                const etaEl = document.createElement('span');
                etaEl.id = 'estimated-time';
                etaEl.className = 'text-xs text-gray-500';
                etaEl.textContent = 'Calculating...';

                // Insert after steps count
                if (elements.stepsCompletedCount && elements.stepsCompletedCount.parentNode) {
                    elements.stepsCompletedCount.parentNode.insertBefore(etaEl, elements.stepsCompletedCount.nextSibling);
                }
                elements.estimatedTimeRemaining = etaEl;
            }
        }
    }

    /**
     * Record a step completion and update progress display
     * @param {string} stepId - The step ID that completed
     * @param {number} durationMs - Duration of the step in milliseconds
     */
    function recordStepCompletion(stepId, durationMs) {
        completedStepCount++;
        if (durationMs > 0) {
            stepDurations.push(durationMs);
        }
        updateProgressDisplay();
    }

    /**
     * Initialize progress tracking with total step count
     * @param {number} total - Total number of steps
     * @param {number} completed - Number of already completed steps
     */
    function initializeProgressTracking(total, completed) {
        totalStepCount = total || 0;
        completedStepCount = completed || 0;
        stepDurations = [];
        updateProgressDisplay();
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

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Public API
    return {
        init: init,
        startBuild: startBuild,
        resumeBuild: resumeBuild,
        pauseBuild: pauseBuild,
        startReview: startReview,
        clearLog: clearLog,
        initializeSteps: initializeSteps,
        toggleStepDetails: toggleStepDetails,
        getSteps: function() { return steps; },
        expandAllSteps: function() {
            steps.forEach(function(step, index) {
                expandedSteps.add(step.id);
                var stepEl = document.getElementById('step-' + step.id);
                if (stepEl) updateStepElementContent(stepEl, step, index);
            });
        },
        collapseAllSteps: function() {
            expandedSteps.clear();
            steps.forEach(function(step, index) {
                var stepEl = document.getElementById('step-' + step.id);
                if (stepEl) updateStepElementContent(stepEl, step, index);
            });
        }
    };
})();

// Expose globally for onclick handlers
window.PlanDetail = PlanDetail;

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlanDetail;
}
