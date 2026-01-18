/**
 * Plan Detail Page Module
 *
 * Handles build/review workflow initiation and inline progress tracking.
 * Uses SSE (Server-Sent Events) for real-time progress updates.
 *
 * Dependencies:
 * - Toast (toast.js) - For notifications
 * - BuildProgress (build-progress.js) - For SSE handling
 */

const PlanDetail = (function() {
    'use strict';

    // State
    let currentRunId = null;
    let eventSource = null;
    let buildStartTime = null;
    let steps = [];
    let stepStartTimes = {};
    let expandedSteps = new Set();

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
    }

    /**
     * Initialize the module
     */
    function init() {
        cacheElements();

        // Check if there's an active build for this plan
        if (window.PLAN_DATA && window.PLAN_DATA.state === 'in-progress') {
            checkForActiveRun();
        }
    }

    /**
     * Check for an active run for this plan
     */
    async function checkForActiveRun() {
        try {
            const response = await fetch('/api/runs?status=running');
            const data = await response.json();

            if (data.runs && data.runs.length > 0) {
                const planRun = data.runs.find(function(r) {
                    return r.plan_path === window.PLAN_DATA.file;
                });

                if (planRun) {
                    currentRunId = planRun.id;
                    showProgressSection();
                    startEventStream(planRun.id);
                }
            }
        } catch (error) {
            console.error('Error checking for active run:', error);
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

            const response = await fetch('/api/plans/' + encodeURIComponent(planId) + '/start-build', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resume: true,
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
     * Start SSE event stream for real-time updates
     * @param {string} runId - The run ID to stream events from
     */
    function startEventStream(runId) {
        if (eventSource) {
            eventSource.close();
        }

        const url = '/api/runs/' + runId + '/events';
        eventSource = new EventSource(url);

        eventSource.onopen = function() {
            addLogEntry('Connected to build stream', 'info');
        };

        eventSource.onmessage = function(e) {
            try {
                const event = JSON.parse(e.data);
                handleEvent(event);
            } catch (error) {
                console.error('Error parsing event:', error);
            }
        };

        eventSource.onerror = function() {
            console.log('SSE connection closed');
            stopEventStream();
        };
    }

    /**
     * Stop SSE event stream
     */
    function stopEventStream() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
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
        }

        // Update current step
        if (event.step) {
            updateCurrentStep(event.step);
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
            return;
        }

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
        });
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
     * Render a step element with full visual checklist styling
     * @param {Object} stepData - Step data object
     * @param {number} index - Step index
     */
    function renderStepElement(stepData, index) {
        if (!elements.stepsList) return;

        const stepEl = document.createElement('div');
        stepEl.id = 'step-' + stepData.id;
        stepEl.className = 'step-item';
        stepEl.dataset.stepId = stepData.id;

        updateStepElementContent(stepEl, stepData, index);
        elements.stepsList.appendChild(stepEl);
    }

    /**
     * Update step element content
     * @param {HTMLElement} stepEl - Step DOM element
     * @param {Object} stepData - Step data object
     * @param {number} index - Step index
     */
    function updateStepElementContent(stepEl, stepData, index) {
        const statusConfig = getStepStatusConfig(stepData.status);
        const isExpanded = expandedSteps.has(stepData.id);
        const hasDetails = stepData.description || stepData.output || stepData.duration;
        const stepNumber = index + 1;

        // Build connector line (not for first step)
        const connector = index > 0 ?
            '<div class="step-connector absolute left-3 -top-2 w-0.5 h-2 ' +
            (stepData.status === 'completed' ? 'bg-green-400' :
             stepData.status === 'running' ? 'bg-blue-400' : 'bg-gray-300') + '"></div>' : '';

        stepEl.className = 'step-item relative ' + (stepData.status === 'running' ? 'step-running' : '');

        stepEl.innerHTML = [
            connector,
            '<div class="step-header flex items-start p-3 rounded-lg transition-all duration-200 ' +
                (stepData.status === 'running' ? 'bg-blue-50 border border-blue-200' :
                 stepData.status === 'completed' ? 'bg-green-50 border border-green-200' :
                 stepData.status === 'failed' ? 'bg-red-50 border border-red-200' :
                 'bg-gray-50 border border-gray-200') +
                (hasDetails ? ' cursor-pointer hover:shadow-sm' : '') + '">',

            // Status indicator
            '  <div class="step-status flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full ' + statusConfig.bgClass + '">',
            '    ' + statusConfig.icon,
            '  </div>',

            // Step content
            '  <div class="step-content flex-1 ml-3 min-w-0">',
            '    <div class="flex items-center justify-between">',
            '      <div class="flex items-center min-w-0">',
            '        <span class="step-number text-xs font-medium text-gray-500 mr-2">#' + stepNumber + '</span>',
            '        <span class="step-label text-sm font-medium ' + statusConfig.textClass + ' truncate">' + escapeHtml(stepData.label) + '</span>',
            '      </div>',
            '      <div class="flex items-center ml-2">',
                   stepData.duration ? '<span class="step-duration text-xs text-gray-500 mr-2">' + stepData.duration + '</span>' : '',
                   hasDetails ? '<svg class="step-chevron w-4 h-4 text-gray-400 transition-transform duration-200 ' +
                     (isExpanded ? 'rotate-180' : '') + '" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                     '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>' : '',
            '      </div>',
            '    </div>',

            // Status label for running/failed
            stepData.status === 'running' ?
                '<div class="step-status-label mt-1 text-xs text-blue-600 animate-pulse">In progress...</div>' : '',
            stepData.status === 'failed' && stepData.error ?
                '<div class="step-status-label mt-1 text-xs text-red-600">' + escapeHtml(stepData.error) + '</div>' : '',

            '  </div>',
            '</div>',

            // Expandable details section
            hasDetails ? [
                '<div class="step-details overflow-hidden transition-all duration-300 ' + (isExpanded ? 'max-h-96' : 'max-h-0') + '">',
                '  <div class="ml-10 mt-2 p-3 bg-gray-100 rounded-lg text-sm">',
                     stepData.description ? '<div class="step-description text-gray-700 mb-2">' + escapeHtml(stepData.description) + '</div>' : '',
                     stepData.output ? [
                         '<div class="step-output">',
                         '  <div class="text-xs font-medium text-gray-500 mb-1">Output:</div>',
                         '  <pre class="text-xs text-gray-600 bg-white p-2 rounded border overflow-x-auto max-h-32 overflow-y-auto">' + escapeHtml(stepData.output) + '</pre>',
                         '</div>'
                     ].join('') : '',
                '  </div>',
                '</div>'
            ].join('') : ''
        ].join('');

        // Add click handler for expandable steps
        if (hasDetails) {
            const header = stepEl.querySelector('.step-header');
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
        if ((status === 'completed' || status === 'failed') && stepStartTimes[stepId]) {
            duration = formatDuration(new Date() - stepStartTimes[stepId]);
        }

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
            renderStepElement(stepData, stepIndex);
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
