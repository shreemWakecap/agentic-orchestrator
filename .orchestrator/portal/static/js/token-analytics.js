/**
 * Token Analytics Module
 *
 * This module handles token analytics dashboard functionality:
 * - Fetching token usage data from API
 * - Rendering Chart.js charts (line and bar)
 * - Date range filtering
 * - Auto-refresh functionality
 * - Dynamic stats updates
 *
 * Depends on: common.js (OrchestratorUtils), Chart.js
 */

const TokenAnalytics = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const config = {
        apiBase: '/api/token-analytics',
        refreshInterval: 60000, // 60 seconds
        chartColors: {
            inputTokens: {
                border: 'rgb(59, 130, 246)',
                background: 'rgba(59, 130, 246, 0.1)'
            },
            outputTokens: {
                border: 'rgb(99, 102, 241)',
                background: 'rgba(99, 102, 241, 0.1)'
            },
            estimated: {
                border: 'rgb(139, 92, 246)',
                background: 'rgba(139, 92, 246, 0.8)'
            },
            actual: {
                border: 'rgb(16, 185, 129)',
                background: 'rgba(16, 185, 129, 0.8)'
            }
        },
        defaultDateRange: 30 // days
    };

    // =========================================================================
    // State
    // =========================================================================

    let state = {
        initialized: false,
        refreshTimer: null,
        usageChart: null,
        comparisonChart: null,
        currentFilters: {
            dateStart: null,
            dateEnd: null,
            granularity: 'daily'
        }
    };

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the token analytics module
     */
    function init() {
        if (state.initialized) {
            console.warn('TokenAnalytics already initialized');
            return;
        }

        // Set default date range
        initializeDateFilters();

        // Setup event listeners
        setupEventListeners();

        // Fetch initial data
        fetchAllData();

        // Start auto-refresh
        startAutoRefresh();

        state.initialized = true;
        console.log('TokenAnalytics initialized');
    }

    /**
     * Initialize date filter inputs with default values
     */
    function initializeDateFilters() {
        const dateStartEl = document.getElementById('date-start');
        const dateEndEl = document.getElementById('date-end');

        if (!dateStartEl || !dateEndEl) return;

        const today = new Date();
        const defaultStart = new Date(today);
        defaultStart.setDate(defaultStart.getDate() - config.defaultDateRange);

        // Only set if not already populated (from URL params or server)
        if (!dateStartEl.value) {
            dateStartEl.value = formatDateForInput(defaultStart);
        }
        if (!dateEndEl.value) {
            dateEndEl.value = formatDateForInput(today);
        }

        // Update state
        state.currentFilters.dateStart = dateStartEl.value;
        state.currentFilters.dateEnd = dateEndEl.value;
    }

    /**
     * Setup all event listeners
     */
    function setupEventListeners() {
        // Filter apply button
        const filterApplyBtn = document.getElementById('filter-apply');
        if (filterApplyBtn) {
            filterApplyBtn.addEventListener('click', handleFilterApply);
        }

        // Filter reset button
        const filterResetBtn = document.getElementById('filter-reset');
        if (filterResetBtn) {
            filterResetBtn.addEventListener('click', handleFilterReset);
        }

        // Quick range buttons
        document.querySelectorAll('.quick-range-btn').forEach(function(btn) {
            btn.addEventListener('click', handleQuickRangeClick);
        });

        // Chart granularity selector
        const granularitySelect = document.getElementById('usage-chart-granularity');
        if (granularitySelect) {
            granularitySelect.addEventListener('change', function() {
                state.currentFilters.granularity = this.value;
                fetchUsageChartData();
            });
        }

        // Comparison chart view selector
        const comparisonViewSelect = document.getElementById('comparison-chart-view');
        if (comparisonViewSelect) {
            comparisonViewSelect.addEventListener('change', function() {
                fetchComparisonChartData(this.value);
            });
        }
    }

    // =========================================================================
    // Event Handlers
    // =========================================================================

    /**
     * Handle filter apply button click
     */
    function handleFilterApply() {
        const dateStartEl = document.getElementById('date-start');
        const dateEndEl = document.getElementById('date-end');

        if (dateStartEl && dateEndEl) {
            state.currentFilters.dateStart = dateStartEl.value;
            state.currentFilters.dateEnd = dateEndEl.value;

            // Update URL params for bookmarkability
            updateUrlParams();

            // Fetch new data
            fetchAllData();
        }
    }

    /**
     * Handle filter reset button click
     */
    function handleFilterReset() {
        const dateStartEl = document.getElementById('date-start');
        const dateEndEl = document.getElementById('date-end');

        if (dateStartEl && dateEndEl) {
            const today = new Date();
            const defaultStart = new Date(today);
            defaultStart.setDate(defaultStart.getDate() - config.defaultDateRange);

            dateStartEl.value = formatDateForInput(defaultStart);
            dateEndEl.value = formatDateForInput(today);

            state.currentFilters.dateStart = dateStartEl.value;
            state.currentFilters.dateEnd = dateEndEl.value;

            // Clear URL params
            window.history.replaceState({}, '', window.location.pathname);

            // Fetch new data
            fetchAllData();
        }
    }

    /**
     * Handle quick range button click
     * @param {Event} event - Click event
     */
    function handleQuickRangeClick(event) {
        var btn = event.currentTarget;
        var range = btn.dataset.range;
        var end = new Date();
        var start = new Date();

        // Remove active class from all quick range buttons
        document.querySelectorAll('.quick-range-btn').forEach(function(b) {
            b.classList.remove('bg-blue-500', 'text-white');
            b.classList.add('bg-gray-100', 'text-gray-700');
        });

        // Add active class to clicked button
        btn.classList.remove('bg-gray-100', 'text-gray-700');
        btn.classList.add('bg-blue-500', 'text-white');

        if (range === '7d') {
            start.setDate(end.getDate() - 7);
        } else if (range === '30d') {
            start.setDate(end.getDate() - 30);
        } else if (range === '90d') {
            start.setDate(end.getDate() - 90);
        } else if (range === 'all') {
            start = new Date('2020-01-01');
        }

        var dateStartEl = document.getElementById('date-start');
        var dateEndEl = document.getElementById('date-end');

        if (dateStartEl && dateEndEl) {
            dateStartEl.value = formatDateForInput(start);
            dateEndEl.value = formatDateForInput(end);

            state.currentFilters.dateStart = dateStartEl.value;
            state.currentFilters.dateEnd = dateEndEl.value;

            // Update URL and fetch data
            updateUrlParams();
            fetchAllData();
        }
    }

    // =========================================================================
    // Data Fetching
    // =========================================================================

    /**
     * Fetch all analytics data
     */
    function fetchAllData() {
        fetchSummaryStats();
        fetchUsageChartData();
        fetchComparisonChartData();
        fetchRecentUsage();
        fetchErrorAnalysis();
    }

    /**
     * Fetch summary statistics
     */
    async function fetchSummaryStats() {
        try {
            var url = config.apiBase + '/summary' + buildQueryString();
            var response = await fetch(url);

            if (!response.ok) {
                throw new Error('Failed to fetch summary stats: HTTP ' + response.status);
            }

            var data = await response.json();
            updateSummaryStats(data);
        } catch (error) {
            console.error('Error fetching summary stats:', error);
        }
    }

    /**
     * Fetch usage chart data
     */
    async function fetchUsageChartData() {
        showChartLoading('usage-chart-loading', true);

        try {
            var queryParams = buildQueryString();
            if (queryParams) {
                queryParams += '&granularity=' + state.currentFilters.granularity;
            } else {
                queryParams = '?granularity=' + state.currentFilters.granularity;
            }

            var url = config.apiBase + '/usage-trend' + queryParams;
            var response = await fetch(url);

            if (!response.ok) {
                throw new Error('Failed to fetch usage chart data: HTTP ' + response.status);
            }

            var data = await response.json();
            renderUsageChart(data);
        } catch (error) {
            console.error('Error fetching usage chart data:', error);
            showChartError('usage-chart-container', 'Failed to load chart data');
        } finally {
            showChartLoading('usage-chart-loading', false);
        }
    }

    /**
     * Fetch comparison chart data
     * @param {string} view - 'cost' or 'tokens'
     */
    async function fetchComparisonChartData(view) {
        view = view || 'cost';
        showChartLoading('comparison-chart-loading', true);

        try {
            var queryParams = buildQueryString();
            if (queryParams) {
                queryParams += '&view=' + view;
            } else {
                queryParams = '?view=' + view;
            }

            var url = config.apiBase + '/comparison' + queryParams;
            var response = await fetch(url);

            if (!response.ok) {
                throw new Error('Failed to fetch comparison chart data: HTTP ' + response.status);
            }

            var data = await response.json();
            renderComparisonChart(data, view);
        } catch (error) {
            console.error('Error fetching comparison chart data:', error);
            showChartError('comparison-chart-container', 'Failed to load chart data');
        } finally {
            showChartLoading('comparison-chart-loading', false);
        }
    }

    /**
     * Fetch recent usage data
     */
    async function fetchRecentUsage() {
        try {
            var url = config.apiBase + '/recent' + buildQueryString();
            var response = await fetch(url);

            if (!response.ok) {
                throw new Error('Failed to fetch recent usage: HTTP ' + response.status);
            }

            var data = await response.json();
            updateRecentUsageTable(data.records || []);
        } catch (error) {
            console.error('Error fetching recent usage:', error);
        }
    }

    /**
     * Fetch error analysis data
     */
    async function fetchErrorAnalysis() {
        try {
            var url = config.apiBase + '/error-analysis' + buildQueryString();
            var response = await fetch(url);

            if (!response.ok) {
                throw new Error('Failed to fetch error analysis: HTTP ' + response.status);
            }

            var data = await response.json();
            updateErrorAnalysis(data);
        } catch (error) {
            console.error('Error fetching error analysis:', error);
        }
    }

    // =========================================================================
    // Chart Rendering
    // =========================================================================

    /**
     * Render usage chart (line chart)
     * @param {Object} data - Chart data from API
     */
    function renderUsageChart(data) {
        var ctx = document.getElementById('usage-chart');
        if (!ctx) return;

        // Destroy existing chart if any
        if (state.usageChart) {
            state.usageChart.destroy();
        }

        var labels = data.labels || [];
        var inputData = data.input_tokens || [];
        var outputData = data.output_tokens || [];

        state.usageChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Input Tokens',
                        data: inputData,
                        borderColor: config.chartColors.inputTokens.border,
                        backgroundColor: config.chartColors.inputTokens.background,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointHoverRadius: 6
                    },
                    {
                        label: 'Output Tokens',
                        data: outputData,
                        borderColor: config.chartColors.outputTokens.border,
                        backgroundColor: config.chartColors.outputTokens.background,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointHoverRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + formatNumber(context.raw);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 0
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                return formatNumber(value);
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Render comparison chart (bar chart)
     * @param {Object} data - Chart data from API
     * @param {string} view - 'cost' or 'tokens'
     */
    function renderComparisonChart(data, view) {
        var ctx = document.getElementById('comparison-chart');
        if (!ctx) return;

        // Destroy existing chart if any
        if (state.comparisonChart) {
            state.comparisonChart.destroy();
        }

        var labels = data.labels || [];
        var estimatedData = data.estimated || [];
        var actualData = data.actual || [];
        var isCostView = view === 'cost';

        state.comparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Estimated',
                        data: estimatedData,
                        backgroundColor: config.chartColors.estimated.background,
                        borderColor: config.chartColors.estimated.border,
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        label: 'Actual',
                        data: actualData,
                        backgroundColor: config.chartColors.actual.background,
                        borderColor: config.chartColors.actual.border,
                        borderWidth: 1,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        callbacks: {
                            label: function(context) {
                                var value = context.raw;
                                if (isCostView) {
                                    return context.dataset.label + ': $' + value.toFixed(4);
                                }
                                return context.dataset.label + ': ' + formatNumber(value);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            callback: function(value) {
                                if (isCostView) {
                                    return '$' + value.toFixed(2);
                                }
                                return formatNumber(value);
                            }
                        }
                    }
                }
            }
        });
    }

    // =========================================================================
    // UI Updates
    // =========================================================================

    /**
     * Update summary statistics in the UI
     * @param {Object} data - Stats data from API
     */
    function updateSummaryStats(data) {
        updateElementText('stat-total-tokens', formatNumber(data.total_tokens || 0));
        updateElementText('stat-total-cost', '$' + (data.total_cost || 0).toFixed(2));
        updateElementText('stat-total-runs', data.total_runs || 0);
        updateElementText('stat-error-rate', (data.error_rate || 0).toFixed(1) + '%');

        // Update accuracy metrics
        updateElementText('avg-accuracy', (data.avg_accuracy || 0).toFixed(1) + '%');
        var deviation = data.avg_deviation || 0;
        updateElementText('avg-deviation', (deviation >= 0 ? '+' : '') + deviation.toFixed(1) + '%');
        updateElementText('best-accuracy', (data.best_accuracy || 0).toFixed(1) + '%');
        updateElementText('worst-accuracy', (data.worst_accuracy || 0).toFixed(1) + '%');
    }

    /**
     * Update error analysis section
     * @param {Object} data - Error analysis data from API
     */
    function updateErrorAnalysis(data) {
        // Update error rate gauge
        var errorRate = data.error_rate || 0;
        var gaugeEl = document.getElementById('error-rate-gauge');
        if (gaugeEl) {
            var dashOffset = 314 - (314 * errorRate / 100);
            gaugeEl.setAttribute('stroke-dashoffset', dashOffset);
        }

        updateElementText('error-rate-value', errorRate.toFixed(1) + '%');
        updateElementText('successful-runs', data.successful_runs || 0);
        updateElementText('failed-runs', data.failed_runs || 0);
        updateElementText('partial-failures', data.partial_failures || 0);

        // Update error trend bars
        var trendContainer = document.getElementById('error-trend-container');
        if (trendContainer && data.error_trend) {
            var bars = trendContainer.querySelectorAll('div');
            data.error_trend.forEach(function(value, index) {
                if (bars[index]) {
                    bars[index].style.height = Math.max(value * 10, 5) + '%';
                    bars[index].title = 'Day ' + (index + 1) + ': ' + value.toFixed(1) + '%';
                }
            });
        }
    }

    /**
     * Update recent usage table
     * @param {Array} records - Usage records from API
     */
    function updateRecentUsageTable(records) {
        var tableBody = document.getElementById('recent-usage-table');
        if (!tableBody) return;

        if (!records || records.length === 0) {
            tableBody.innerHTML = createEmptyTableRow();
            return;
        }

        var html = '';
        records.forEach(function(record) {
            html += createUsageTableRow(record);
        });

        tableBody.innerHTML = html;
    }

    /**
     * Create a table row for usage record
     * @param {Object} record - Usage record
     * @returns {string} HTML string
     */
    function createUsageTableRow(record) {
        var runId = record.run_id || '';
        var runType = record.run_type || 'unknown';
        var inputTokens = record.input_tokens || 0;
        var outputTokens = record.output_tokens || 0;
        var cost = record.cost || 0;
        var status = record.status || 'unknown';
        var createdAt = record.created_at || '';

        var typeClass = getRunTypeClass(runType);
        var statusClass = getStatusClass(status);

        var html = '<tr class="hover:bg-gray-50 transition-colors">';
        html += '<td class="px-4 py-3 whitespace-nowrap">';
        html += '<a href="/runs/' + escapeHtml(runId) + '" class="text-sm font-medium text-blue-600 hover:underline">';
        html += escapeHtml(runId.substring(0, 8)) + '...';
        html += '</a></td>';
        html += '<td class="px-4 py-3 whitespace-nowrap">';
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + typeClass + '">';
        html += escapeHtml(capitalize(runType));
        html += '</span></td>';
        html += '<td class="px-4 py-3 whitespace-nowrap text-sm text-primary font-mono">';
        html += formatNumber(inputTokens);
        html += '</td>';
        html += '<td class="px-4 py-3 whitespace-nowrap text-sm text-primary font-mono">';
        html += formatNumber(outputTokens);
        html += '</td>';
        html += '<td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-emerald-600">';
        html += '$' + cost.toFixed(4);
        html += '</td>';
        html += '<td class="px-4 py-3 whitespace-nowrap">';
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ' + statusClass + '">';
        html += escapeHtml(capitalize(status));
        html += '</span></td>';
        html += '<td class="px-4 py-3 whitespace-nowrap text-sm text-tertiary">';
        html += escapeHtml(formatDatetime(createdAt));
        html += '</td></tr>';

        return html;
    }

    /**
     * Create empty table row
     * @returns {string} HTML string
     */
    function createEmptyTableRow() {
        var html = '<tr><td colspan="7" class="px-4 py-8 text-center text-tertiary">';
        html += '<svg class="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">';
        html += '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>';
        html += '</svg>';
        html += '<p class="text-sm">No token usage records found for the selected date range.</p>';
        html += '</td></tr>';
        return html;
    }

    /**
     * Show/hide chart loading indicator
     * @param {string} elementId - Loading element ID
     * @param {boolean} show - Whether to show loading
     */
    function showChartLoading(elementId, show) {
        var el = document.getElementById(elementId);
        if (el) {
            el.style.display = show ? 'flex' : 'none';
        }
    }

    /**
     * Show chart error message
     * @param {string} containerId - Container element ID
     * @param {string} message - Error message
     */
    function showChartError(containerId, message) {
        var container = document.getElementById(containerId);
        if (container) {
            var loadingEl = container.querySelector('[id$="-loading"]');
            if (loadingEl) {
                loadingEl.innerHTML = '<div class="text-center"><svg class="w-8 h-8 mx-auto mb-2 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
                    '</svg><p class="text-sm text-red-500">' + escapeHtml(message) + '</p></div>';
                loadingEl.style.display = 'flex';
            }
        }
    }

    // =========================================================================
    // Auto-Refresh
    // =========================================================================

    /**
     * Start auto-refresh timer
     */
    function startAutoRefresh() {
        stopAutoRefresh(); // Clear any existing timer

        state.refreshTimer = setInterval(function() {
            fetchAllData();
        }, config.refreshInterval);
    }

    /**
     * Stop auto-refresh timer
     */
    function stopAutoRefresh() {
        if (state.refreshTimer) {
            clearInterval(state.refreshTimer);
            state.refreshTimer = null;
        }
    }

    /**
     * Manually trigger refresh
     */
    function refresh() {
        fetchAllData();
    }

    // =========================================================================
    // Utility Functions
    // =========================================================================

    /**
     * Build query string from current filters
     * @returns {string} Query string with leading '?' or empty
     */
    function buildQueryString() {
        var params = [];

        if (state.currentFilters.dateStart) {
            params.push('date_start=' + encodeURIComponent(state.currentFilters.dateStart));
        }
        if (state.currentFilters.dateEnd) {
            params.push('date_end=' + encodeURIComponent(state.currentFilters.dateEnd));
        }

        return params.length > 0 ? '?' + params.join('&') : '';
    }

    /**
     * Update URL parameters
     */
    function updateUrlParams() {
        var params = new URLSearchParams();

        if (state.currentFilters.dateStart) {
            params.set('date_start', state.currentFilters.dateStart);
        }
        if (state.currentFilters.dateEnd) {
            params.set('date_end', state.currentFilters.dateEnd);
        }

        var newUrl = window.location.pathname;
        var queryString = params.toString();
        if (queryString) {
            newUrl += '?' + queryString;
        }

        window.history.replaceState({}, '', newUrl);
    }

    /**
     * Format date for input element
     * @param {Date} date - Date object
     * @returns {string} YYYY-MM-DD format
     */
    function formatDateForInput(date) {
        return date.toISOString().split('T')[0];
    }

    /**
     * Format datetime string for display
     * @param {string} datetime - ISO datetime string
     * @returns {string} Formatted datetime
     */
    function formatDatetime(datetime) {
        if (!datetime) return '--';
        try {
            var date = new Date(datetime);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return datetime;
        }
    }

    /**
     * Format number with commas
     * @param {number} num - Number to format
     * @returns {string} Formatted number
     */
    function formatNumber(num) {
        if (typeof num !== 'number') {
            num = parseInt(num, 10) || 0;
        }
        return num.toLocaleString();
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        if (typeof OrchestratorUtils !== 'undefined' && OrchestratorUtils.escapeHtml) {
            return OrchestratorUtils.escapeHtml(text);
        }
        if (typeof text !== 'string') return '';
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Capitalize first letter
     * @param {string} str - String to capitalize
     * @returns {string} Capitalized string
     */
    function capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }

    /**
     * Update element text content
     * @param {string} elementId - Element ID
     * @param {string} text - Text content
     */
    function updateElementText(elementId, text) {
        var el = document.getElementById(elementId);
        if (el) {
            el.textContent = text;
        }
    }

    /**
     * Get CSS class for run type badge
     * @param {string} runType - Run type
     * @returns {string} CSS classes
     */
    function getRunTypeClass(runType) {
        var classes = {
            planning: 'bg-blue-100 text-blue-800',
            building: 'bg-emerald-100 text-emerald-800'
        };
        return classes[runType] || 'bg-gray-100 text-gray-800';
    }

    /**
     * Get CSS class for status badge
     * @param {string} status - Status
     * @returns {string} CSS classes
     */
    function getStatusClass(status) {
        var classes = {
            completed: 'bg-emerald-100 text-emerald-800',
            failed: 'bg-red-100 text-red-800',
            running: 'bg-blue-100 text-blue-800'
        };
        return classes[status] || 'bg-gray-100 text-gray-800';
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    /**
     * Cleanup module resources
     */
    function cleanup() {
        stopAutoRefresh();

        if (state.usageChart) {
            state.usageChart.destroy();
            state.usageChart = null;
        }

        if (state.comparisonChart) {
            state.comparisonChart.destroy();
            state.comparisonChart = null;
        }

        state.initialized = false;
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        refresh: refresh,
        fetchAllData: fetchAllData,
        fetchSummaryStats: fetchSummaryStats,
        fetchUsageChartData: fetchUsageChartData,
        fetchComparisonChartData: fetchComparisonChartData,
        fetchRecentUsage: fetchRecentUsage,
        fetchErrorAnalysis: fetchErrorAnalysis,
        startAutoRefresh: startAutoRefresh,
        stopAutoRefresh: stopAutoRefresh,
        cleanup: cleanup,
        getState: function() { return state; }
    };
})();

// Expose globally
window.TokenAnalytics = TokenAnalytics;

// Auto-initialize on DOMContentLoaded if token analytics page
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the token analytics page
    var usageChart = document.getElementById('usage-chart');
    var comparisonChart = document.getElementById('comparison-chart');

    if (usageChart || comparisonChart) {
        TokenAnalytics.init();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (typeof TokenAnalytics !== 'undefined') {
        TokenAnalytics.cleanup();
    }
});

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TokenAnalytics;
}
