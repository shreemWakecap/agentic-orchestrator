/**
 * Real-Time Updates Module
 *
 * Provides unified real-time update functionality for the portal including:
 * - SSE connections with auto-reconnection and exponential backoff
 * - WebSocket connections for plan status updates
 * - Polling as fallback when SSE/WebSocket not available
 * - Visibility API integration (pause updates when tab is hidden)
 * - Dashboard stats auto-refresh
 *
 * Usage:
 *   RealTimeUpdates.init();
 *   RealTimeUpdates.subscribe('plan-status', planId, callback);
 *   RealTimeUpdates.subscribe('dashboard-stats', null, callback);
 */

const RealTimeUpdates = (function() {
    'use strict';

    // Configuration
    const config = {
        // SSE reconnection settings
        sse: {
            maxReconnectAttempts: 10,
            initialReconnectDelay: 1000,  // 1 second
            maxReconnectDelay: 30000,     // 30 seconds
            reconnectBackoffMultiplier: 1.5,
        },
        // Polling intervals (fallback)
        polling: {
            activeBuilds: 2000,           // 2 seconds for active builds
            stuckPlans: 30000,            // 30 seconds for stuck plans
            dashboardStats: 10000,        // 10 seconds for dashboard counts
            planStatus: 3000,             // 3 seconds for individual plan status
        },
        // Heartbeat detection
        heartbeat: {
            interval: 15000,              // 15 seconds between heartbeats
            timeout: 45000,               // 45 seconds before considering connection dead
        },
        // WebSocket settings
        websocket: {
            reconnectDelay: 3000,
            maxReconnectAttempts: 5,
        }
    };

    // State management
    const state = {
        // Subscriptions: { channel: { id: { callback, options } } }
        subscriptions: {},
        // SSE connections: { url: { eventSource, reconnectAttempts, reconnectTimer } }
        sseConnections: {},
        // WebSocket connection
        websocket: null,
        websocketReconnectAttempts: 0,
        websocketClientId: null,
        websocketSubscriptions: new Set(),
        // Polling timers
        pollingTimers: {},
        // Visibility state
        isVisible: true,
        // Last heartbeat received
        lastHeartbeat: Date.now(),
        // Heartbeat check timer
        heartbeatTimer: null,
        // Dashboard stats cache
        dashboardStats: null,
        // Use WebSocket when available
        useWebSocket: true,
    };

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the real-time updates module
     */
    function init() {
        // Set up visibility change listener
        setupVisibilityListener();

        // Start heartbeat monitoring
        startHeartbeatMonitoring();

        // Try WebSocket connection first for real-time updates
        if (state.useWebSocket) {
            connectWebSocket();
        }

        // Auto-start dashboard stats polling as fallback/initial load
        if (isDashboardPage()) {
            // Initial fetch
            fetchDashboardStats();
            fetchActiveBuilds();
            fetchStuckPlans();

            // Start polling as backup (WebSocket will handle real-time when connected)
            startDashboardStatsPolling();
        }

        console.log('[RealTimeUpdates] Initialized');
    }

    /**
     * Check if current page is the dashboard
     */
    function isDashboardPage() {
        return window.location.pathname === '/' ||
               window.location.pathname === '/dashboard' ||
               document.getElementById('live-builds-section') !== null;
    }

    // =========================================================================
    // Visibility API Integration
    // =========================================================================

    /**
     * Set up visibility change listener to pause/resume updates
     */
    function setupVisibilityListener() {
        document.addEventListener('visibilitychange', function() {
            const wasVisible = state.isVisible;
            state.isVisible = !document.hidden;

            if (state.isVisible && !wasVisible) {
                console.log('[RealTimeUpdates] Tab became visible, resuming updates');
                onTabBecameVisible();
            } else if (!state.isVisible && wasVisible) {
                console.log('[RealTimeUpdates] Tab became hidden, pausing non-essential updates');
                onTabBecameHidden();
            }
        });
    }

    /**
     * Handle tab becoming visible
     */
    function onTabBecameVisible() {
        // Reconnect WebSocket if needed
        if (state.useWebSocket && (!state.websocket || state.websocket.readyState !== WebSocket.OPEN)) {
            connectWebSocket();
        }

        // Immediately refresh dashboard stats
        if (isDashboardPage()) {
            fetchDashboardStats();
            fetchActiveBuilds();
            fetchStuckPlans();
        }

        // Resume all paused polling
        resumePolling();

        // Reconnect any closed SSE connections
        reconnectAllSSE();
    }

    /**
     * Handle tab becoming hidden
     */
    function onTabBecameHidden() {
        // Pause non-critical polling (keep SSE alive for important updates)
        pauseNonCriticalPolling();
    }

    // =========================================================================
    // SSE Connection Management
    // =========================================================================

    /**
     * Create or get an SSE connection with auto-reconnection
     * @param {string} url - SSE endpoint URL
     * @param {function} onMessage - Message handler callback
     * @param {object} options - Connection options
     */
    function createSSEConnection(url, onMessage, options = {}) {
        const connectionKey = url;

        // Close existing connection if any
        if (state.sseConnections[connectionKey]) {
            closeSSEConnection(connectionKey);
        }

        const connection = {
            url: url,
            onMessage: onMessage,
            options: options,
            eventSource: null,
            reconnectAttempts: 0,
            reconnectTimer: null,
            lastEventId: options.lastEventId || 0,
        };

        state.sseConnections[connectionKey] = connection;
        connectSSE(connectionKey);

        return connectionKey;
    }

    /**
     * Connect/reconnect SSE
     */
    function connectSSE(connectionKey) {
        const connection = state.sseConnections[connectionKey];
        if (!connection) return;

        // Clear any pending reconnect timer
        if (connection.reconnectTimer) {
            clearTimeout(connection.reconnectTimer);
            connection.reconnectTimer = null;
        }

        // Build URL with last event ID for replay
        let url = connection.url;
        if (connection.lastEventId > 0) {
            const separator = url.includes('?') ? '&' : '?';
            url += separator + 'last_event_id=' + connection.lastEventId;
        }

        const es = new EventSource(url);
        connection.eventSource = es;

        es.onopen = function() {
            console.log('[RealTimeUpdates] SSE connected:', connectionKey);
            connection.reconnectAttempts = 0;
            state.lastHeartbeat = Date.now();
        };

        es.onmessage = function(event) {
            state.lastHeartbeat = Date.now();

            try {
                const data = JSON.parse(event.data);

                // Track last event ID for replay on reconnect
                if (event.lastEventId) {
                    connection.lastEventId = parseInt(event.lastEventId, 10);
                } else if (data.sequence) {
                    connection.lastEventId = data.sequence;
                }

                // Call the message handler
                if (connection.onMessage) {
                    connection.onMessage(data, event);
                }
            } catch (e) {
                console.warn('[RealTimeUpdates] SSE parse error:', e);
            }
        };

        es.onerror = function(error) {
            console.warn('[RealTimeUpdates] SSE error for', connectionKey, error);
            es.close();
            connection.eventSource = null;

            // Schedule reconnection with exponential backoff
            scheduleSSEReconnect(connectionKey);
        };

        // Handle specific event types if configured
        if (connection.options.eventTypes) {
            connection.options.eventTypes.forEach(function(eventType) {
                es.addEventListener(eventType, function(event) {
                    state.lastHeartbeat = Date.now();
                    try {
                        const data = JSON.parse(event.data);
                        if (connection.onMessage) {
                            connection.onMessage(data, event);
                        }
                    } catch (e) {
                        console.warn('[RealTimeUpdates] SSE event parse error:', e);
                    }
                });
            });
        }
    }

    /**
     * Schedule SSE reconnection with exponential backoff
     */
    function scheduleSSEReconnect(connectionKey) {
        const connection = state.sseConnections[connectionKey];
        if (!connection) return;

        // Check max attempts
        if (connection.reconnectAttempts >= config.sse.maxReconnectAttempts) {
            console.error('[RealTimeUpdates] Max SSE reconnect attempts reached for', connectionKey);
            notifySubscribers('connection-lost', connectionKey, { url: connection.url });
            return;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
            config.sse.initialReconnectDelay * Math.pow(config.sse.reconnectBackoffMultiplier, connection.reconnectAttempts),
            config.sse.maxReconnectDelay
        );

        connection.reconnectAttempts++;

        console.log('[RealTimeUpdates] Scheduling SSE reconnect in', delay, 'ms (attempt', connection.reconnectAttempts, ')');

        connection.reconnectTimer = setTimeout(function() {
            if (state.isVisible) {
                connectSSE(connectionKey);
            } else {
                // If tab is hidden, wait until it becomes visible
                console.log('[RealTimeUpdates] Tab hidden, deferring SSE reconnect');
            }
        }, delay);
    }

    /**
     * Close an SSE connection
     */
    function closeSSEConnection(connectionKey) {
        const connection = state.sseConnections[connectionKey];
        if (!connection) return;

        if (connection.eventSource) {
            connection.eventSource.close();
            connection.eventSource = null;
        }

        if (connection.reconnectTimer) {
            clearTimeout(connection.reconnectTimer);
            connection.reconnectTimer = null;
        }

        delete state.sseConnections[connectionKey];
    }

    /**
     * Reconnect all SSE connections
     */
    function reconnectAllSSE() {
        Object.keys(state.sseConnections).forEach(function(key) {
            const connection = state.sseConnections[key];
            if (!connection.eventSource || connection.eventSource.readyState === EventSource.CLOSED) {
                connectSSE(key);
            }
        });
    }

    // =========================================================================
    // Polling Management
    // =========================================================================

    /**
     * Start polling for a specific channel
     */
    function startPolling(channel, fetchFn, interval) {
        stopPolling(channel);

        // Execute immediately
        fetchFn();

        // Then at interval
        state.pollingTimers[channel] = setInterval(function() {
            if (state.isVisible) {
                fetchFn();
            }
        }, interval);
    }

    /**
     * Stop polling for a specific channel
     */
    function stopPolling(channel) {
        if (state.pollingTimers[channel]) {
            clearInterval(state.pollingTimers[channel]);
            delete state.pollingTimers[channel];
        }
    }

    /**
     * Pause non-critical polling when tab is hidden
     */
    function pauseNonCriticalPolling() {
        // Keep active builds polling but at reduced rate
        // Stop dashboard stats polling completely
    }

    /**
     * Resume all polling when tab becomes visible
     */
    function resumePolling() {
        // Polling timers auto-check visibility, so just trigger immediate fetches
        if (isDashboardPage()) {
            fetchDashboardStats();
        }
    }

    // =========================================================================
    // Dashboard Stats Auto-Refresh
    // =========================================================================

    /**
     * Start dashboard stats polling
     */
    function startDashboardStatsPolling() {
        startPolling('dashboard-stats', fetchDashboardStats, config.polling.dashboardStats);
    }

    /**
     * Fetch and update dashboard stats (plan counts)
     */
    async function fetchDashboardStats() {
        try {
            const response = await fetch('/api/plans/counts');
            if (!response.ok) {
                throw new Error('Failed to fetch plan counts');
            }

            const data = await response.json();
            state.dashboardStats = data;

            // Update the dashboard UI
            updateDashboardCounts(data);

            // Notify subscribers
            notifySubscribers('dashboard-stats', null, data);
        } catch (error) {
            console.warn('[RealTimeUpdates] Failed to fetch dashboard stats:', error);
        }
    }

    /**
     * Update dashboard count elements
     */
    function updateDashboardCounts(counts) {
        // Find and update count elements by ID
        const countElements = {
            pending: document.getElementById('count-pending'),
            in_progress: document.getElementById('count-in-progress'),
            completed: document.getElementById('count-completed'),
            failed: document.getElementById('count-failed'),
        };

        Object.keys(countElements).forEach(function(key) {
            const el = countElements[key];
            if (el && counts[key] !== undefined) {
                const newValue = String(counts[key]);
                if (el.textContent !== newValue) {
                    // Animate the update with a pulse effect
                    el.style.transition = 'transform 0.2s ease, color 0.2s ease';
                    el.style.transform = 'scale(1.15)';
                    el.textContent = newValue;

                    // Flash color based on change direction
                    const oldValue = parseInt(el.dataset.lastValue || '0', 10);
                    const newValueInt = parseInt(newValue, 10);
                    if (newValueInt > oldValue) {
                        el.style.color = '#22c55e'; // green for increase
                    } else if (newValueInt < oldValue) {
                        el.style.color = '#ef4444'; // red for decrease
                    }

                    el.dataset.lastValue = newValue;

                    setTimeout(function() {
                        el.style.transform = 'scale(1)';
                        el.style.color = ''; // Reset to default
                    }, 300);
                }
            }
        });
    }

    // =========================================================================
    // Active Builds Updates
    // =========================================================================

    /**
     * Fetch active builds
     */
    async function fetchActiveBuilds() {
        try {
            const response = await fetch('/api/runs?status=running,pending&limit=10');
            if (!response.ok) return;

            const data = await response.json();
            notifySubscribers('active-builds', null, data.runs || []);
        } catch (error) {
            console.warn('[RealTimeUpdates] Failed to fetch active builds:', error);
        }
    }

    /**
     * Fetch stuck plans
     */
    async function fetchStuckPlans() {
        try {
            const response = await fetch('/api/plans/recovery/stuck');
            if (!response.ok) return;

            const data = await response.json();
            notifySubscribers('stuck-plans', null, data.plans || []);
        } catch (error) {
            console.warn('[RealTimeUpdates] Failed to fetch stuck plans:', error);
        }
    }

    // =========================================================================
    // Heartbeat Monitoring
    // =========================================================================

    /**
     * Start heartbeat monitoring
     */
    function startHeartbeatMonitoring() {
        stopHeartbeatMonitoring();

        state.heartbeatTimer = setInterval(function() {
            const timeSinceHeartbeat = Date.now() - state.lastHeartbeat;

            if (timeSinceHeartbeat > config.heartbeat.timeout) {
                console.warn('[RealTimeUpdates] Heartbeat timeout, connections may be stale');

                // Reconnect all SSE connections
                if (state.isVisible) {
                    reconnectAllSSE();
                }

                // Reset heartbeat
                state.lastHeartbeat = Date.now();
            }
        }, config.heartbeat.interval);
    }

    /**
     * Stop heartbeat monitoring
     */
    function stopHeartbeatMonitoring() {
        if (state.heartbeatTimer) {
            clearInterval(state.heartbeatTimer);
            state.heartbeatTimer = null;
        }
    }

    // =========================================================================
    // WebSocket Connection Management
    // =========================================================================

    /**
     * Connect to WebSocket server
     */
    function connectWebSocket() {
        if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/ws';

        try {
            state.websocket = new WebSocket(wsUrl);

            state.websocket.onopen = function() {
                console.log('[RealTimeUpdates] WebSocket connected');
                state.websocketReconnectAttempts = 0;
                state.lastHeartbeat = Date.now();

                // Re-subscribe to any previously subscribed channels
                state.websocketSubscriptions.forEach(function(channel) {
                    sendWebSocketMessage({ type: 'subscribe', channel: channel });
                });

                // Subscribe to dashboard if on dashboard page
                if (isDashboardPage()) {
                    wsSubscribe('dashboard');
                    wsSubscribe('builds');
                    wsSubscribe('stuck');
                }
            };

            state.websocket.onmessage = function(event) {
                state.lastHeartbeat = Date.now();

                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.warn('[RealTimeUpdates] WebSocket message parse error:', e);
                }
            };

            state.websocket.onclose = function(event) {
                console.log('[RealTimeUpdates] WebSocket closed:', event.code, event.reason);
                state.websocket = null;
                state.websocketClientId = null;

                // Reconnect with exponential backoff
                scheduleWebSocketReconnect();
            };

            state.websocket.onerror = function(error) {
                console.warn('[RealTimeUpdates] WebSocket error:', error);
            };

        } catch (e) {
            console.warn('[RealTimeUpdates] WebSocket connection failed:', e);
            state.useWebSocket = false; // Fall back to polling
        }
    }

    /**
     * Handle incoming WebSocket message
     */
    function handleWebSocketMessage(data) {
        const msgType = data.type;

        if (msgType === 'connected') {
            state.websocketClientId = data.client_id;
            console.log('[RealTimeUpdates] WebSocket client ID:', data.client_id);
            return;
        }

        if (msgType === 'ping') {
            sendWebSocketMessage({ type: 'pong' });
            return;
        }

        if (msgType === 'pong') {
            return;
        }

        if (msgType === 'subscribed' || msgType === 'unsubscribed') {
            console.log('[RealTimeUpdates] WebSocket', msgType, 'to', data.channel);
            return;
        }

        // Handle stats update for dashboard
        if (msgType === 'stats' && data.counts) {
            state.dashboardStats = data.counts;
            updateDashboardCounts(data.counts);
            notifySubscribers('dashboard-stats', null, data.counts);
            return;
        }

        // Handle plan status updates
        if (msgType === 'plan_status' || msgType === 'build_update') {
            notifySubscribers('plan-status', data.plan_id, data);
            notifySubscribers('active-builds', null, data);
            return;
        }

        // Handle build progress updates
        if (msgType === 'build_progress') {
            notifySubscribers('plan-status', data.plan_id, data);
            notifySubscribers('active-builds', null, data);
            return;
        }

        // Handle stuck alerts
        if (msgType === 'stuck_alert') {
            notifySubscribers('stuck-plans', data.plan_id, data);
            return;
        }

        // Generic channel notification
        if (data.channel) {
            notifySubscribers(data.channel, null, data);
        }
    }

    /**
     * Send a message through WebSocket
     */
    function sendWebSocketMessage(data) {
        if (state.websocket && state.websocket.readyState === WebSocket.OPEN) {
            state.websocket.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    /**
     * Subscribe to a WebSocket channel
     */
    function wsSubscribe(channel) {
        state.websocketSubscriptions.add(channel);
        if (sendWebSocketMessage({ type: 'subscribe', channel: channel })) {
            console.log('[RealTimeUpdates] Subscribing to WebSocket channel:', channel);
        }
    }

    /**
     * Unsubscribe from a WebSocket channel
     */
    function wsUnsubscribe(channel) {
        state.websocketSubscriptions.delete(channel);
        sendWebSocketMessage({ type: 'unsubscribe', channel: channel });
    }

    /**
     * Schedule WebSocket reconnection
     */
    function scheduleWebSocketReconnect() {
        if (state.websocketReconnectAttempts >= config.websocket.maxReconnectAttempts) {
            console.warn('[RealTimeUpdates] Max WebSocket reconnect attempts reached, falling back to polling');
            state.useWebSocket = false;
            // Start polling as fallback
            if (isDashboardPage()) {
                startDashboardStatsPolling();
            }
            return;
        }

        const delay = config.websocket.reconnectDelay * Math.pow(1.5, state.websocketReconnectAttempts);
        state.websocketReconnectAttempts++;

        console.log('[RealTimeUpdates] Scheduling WebSocket reconnect in', delay, 'ms');

        setTimeout(function() {
            if (state.isVisible && state.useWebSocket) {
                connectWebSocket();
            }
        }, delay);
    }

    /**
     * Close WebSocket connection
     */
    function closeWebSocket() {
        if (state.websocket) {
            state.websocket.close();
            state.websocket = null;
            state.websocketClientId = null;
        }
    }

    // =========================================================================
    // Subscription Management
    // =========================================================================

    /**
     * Subscribe to a channel
     * @param {string} channel - Channel name (e.g., 'plan-status', 'dashboard-stats', 'active-builds')
     * @param {string|null} id - Optional ID for channel-specific subscriptions
     * @param {function} callback - Callback function(data)
     * @returns {string} Subscription ID for unsubscribing
     */
    function subscribe(channel, id, callback) {
        if (!state.subscriptions[channel]) {
            state.subscriptions[channel] = {};
        }

        const subscriptionId = id || '_global_' + Date.now();
        state.subscriptions[channel][subscriptionId] = {
            callback: callback,
            createdAt: Date.now(),
        };

        // Auto-start relevant services based on channel
        if (channel === 'dashboard-stats') {
            startDashboardStatsPolling();
        } else if (channel === 'active-builds') {
            startPolling('active-builds', fetchActiveBuilds, config.polling.activeBuilds);
        } else if (channel === 'stuck-plans') {
            startPolling('stuck-plans', fetchStuckPlans, config.polling.stuckPlans);
        }

        return subscriptionId;
    }

    /**
     * Unsubscribe from a channel
     */
    function unsubscribe(channel, subscriptionId) {
        if (state.subscriptions[channel]) {
            delete state.subscriptions[channel][subscriptionId];

            // Stop services if no more subscribers
            if (Object.keys(state.subscriptions[channel]).length === 0) {
                delete state.subscriptions[channel];
                stopPolling(channel);
            }
        }
    }

    /**
     * Notify all subscribers of a channel
     */
    function notifySubscribers(channel, id, data) {
        const channelSubs = state.subscriptions[channel];
        if (!channelSubs) return;

        Object.keys(channelSubs).forEach(function(subId) {
            // If id is specified, only notify matching subscriptions
            if (id && subId !== id && subId.indexOf('_global_') !== 0) {
                return;
            }

            const sub = channelSubs[subId];
            if (sub && sub.callback) {
                try {
                    sub.callback(data);
                } catch (e) {
                    console.error('[RealTimeUpdates] Subscriber callback error:', e);
                }
            }
        });
    }

    // =========================================================================
    // Plan Status Updates
    // =========================================================================

    /**
     * Subscribe to plan status updates via SSE
     * @param {string} planId - Plan ID to subscribe to
     * @param {function} callback - Callback function(statusData)
     */
    function subscribeToPlanStatus(planId, callback) {
        const url = '/api/plans/' + planId + '/events';

        const connectionKey = createSSEConnection(url, function(data) {
            // Update local state and notify
            notifySubscribers('plan-status', planId, data);

            if (callback) {
                callback(data);
            }
        }, {
            eventTypes: ['status', 'progress', 'step', 'error', 'complete']
        });

        return connectionKey;
    }

    /**
     * Subscribe to run events via SSE
     * @param {string} runId - Run ID to subscribe to
     * @param {function} callback - Callback function(eventData)
     */
    function subscribeToRunEvents(runId, callback) {
        const url = '/api/runs/' + runId + '/events';

        const connectionKey = createSSEConnection(url, function(data) {
            notifySubscribers('run-events', runId, data);

            if (callback) {
                callback(data);
            }
        }, {
            eventTypes: ['status', 'progress', 'log', 'error', 'complete', 'done']
        });

        return connectionKey;
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    /**
     * Clean up all connections and timers
     */
    function destroy() {
        // Close WebSocket connection
        closeWebSocket();

        // Close all SSE connections
        Object.keys(state.sseConnections).forEach(closeSSEConnection);

        // Stop all polling
        Object.keys(state.pollingTimers).forEach(stopPolling);

        // Stop heartbeat monitoring
        stopHeartbeatMonitoring();

        // Clear subscriptions
        state.subscriptions = {};
        state.websocketSubscriptions.clear();

        console.log('[RealTimeUpdates] Destroyed');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        init: init,
        subscribe: subscribe,
        unsubscribe: unsubscribe,
        subscribeToPlanStatus: subscribeToPlanStatus,
        subscribeToRunEvents: subscribeToRunEvents,
        createSSEConnection: createSSEConnection,
        closeSSEConnection: closeSSEConnection,
        startPolling: startPolling,
        stopPolling: stopPolling,
        fetchDashboardStats: fetchDashboardStats,
        fetchActiveBuilds: fetchActiveBuilds,
        fetchStuckPlans: fetchStuckPlans,
        // WebSocket methods
        connectWebSocket: connectWebSocket,
        closeWebSocket: closeWebSocket,
        wsSubscribe: wsSubscribe,
        wsUnsubscribe: wsUnsubscribe,
        sendWebSocketMessage: sendWebSocketMessage,
        isWebSocketConnected: function() {
            return state.websocket && state.websocket.readyState === WebSocket.OPEN;
        },
        // State accessors
        isVisible: function() { return state.isVisible; },
        getConfig: function() { return config; },
        destroy: destroy,
    };
})();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    RealTimeUpdates.init();
});

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    RealTimeUpdates.destroy();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealTimeUpdates;
}
