/**
 * Toast Notification Module
 *
 * Lightweight toast notification component for showing success/error messages.
 * Positioned bottom-right with auto-dismiss after 3 seconds.
 *
 * Usage:
 *   Toast.show('Operation successful', 'success');
 *   Toast.show('Something went wrong', 'error');
 *   Toast.show('Please note...', 'info');
 *   Toast.show('Warning message', 'warning');
 */

const Toast = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const config = {
        defaultDuration: 3000,
        animationDuration: 300,
        maxToasts: 5,
        containerPosition: 'bottom-right'
    };

    const typeConfig = {
        success: {
            bgClass: 'bg-green-500',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        },
        error: {
            bgClass: 'bg-red-500',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
        },
        warning: {
            bgClass: 'bg-yellow-500',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>'
        },
        info: {
            bgClass: 'bg-blue-500',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
        }
    };

    let container = null;
    let toastQueue = [];

    // =========================================================================
    // CSS Injection
    // =========================================================================

    function injectStyles() {
        if (document.getElementById('toast-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'toast-styles';
        styles.textContent = `
            .toast-container {
                position: fixed;
                bottom: 1rem;
                right: 1rem;
                z-index: 9999;
                display: flex;
                flex-direction: column-reverse;
                gap: 0.5rem;
                pointer-events: none;
            }

            .toast {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                padding: 0.75rem 1rem;
                border-radius: 0.5rem;
                color: white;
                font-size: 0.875rem;
                font-weight: 500;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                pointer-events: auto;
                max-width: 24rem;
                opacity: 0;
                transform: translateX(100%);
                transition: opacity ${config.animationDuration}ms ease, transform ${config.animationDuration}ms ease;
            }

            .toast.toast-visible {
                opacity: 1;
                transform: translateX(0);
            }

            .toast.toast-hiding {
                opacity: 0;
                transform: translateX(100%);
            }

            .toast-icon {
                flex-shrink: 0;
            }

            .toast-message {
                flex: 1;
                word-break: break-word;
            }

            .toast-close {
                flex-shrink: 0;
                padding: 0.25rem;
                margin: -0.25rem;
                margin-left: 0.5rem;
                border-radius: 0.25rem;
                opacity: 0.7;
                cursor: pointer;
                transition: opacity 0.2s ease;
            }

            .toast-close:hover {
                opacity: 1;
            }
        `;
        document.head.appendChild(styles);
    }

    // =========================================================================
    // Container Management
    // =========================================================================

    function getContainer() {
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'true');
            document.body.appendChild(container);
        }
        return container;
    }

    // =========================================================================
    // Toast Creation
    // =========================================================================

    function createToastElement(message, type) {
        const typeSettings = typeConfig[type] || typeConfig.info;

        const toast = document.createElement('div');
        toast.className = 'toast ' + typeSettings.bgClass;
        toast.setAttribute('role', 'alert');

        const iconSpan = document.createElement('span');
        iconSpan.className = 'toast-icon';
        iconSpan.innerHTML = typeSettings.icon;

        const messageSpan = document.createElement('span');
        messageSpan.className = 'toast-message';
        messageSpan.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('aria-label', 'Dismiss');
        closeBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';

        toast.appendChild(iconSpan);
        toast.appendChild(messageSpan);
        toast.appendChild(closeBtn);

        return toast;
    }

    // =========================================================================
    // Toast Lifecycle
    // =========================================================================

    function removeToast(toast, id) {
        toast.classList.remove('toast-visible');
        toast.classList.add('toast-hiding');

        setTimeout(function() {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            toastQueue = toastQueue.filter(function(t) { return t.id !== id; });
        }, config.animationDuration);
    }

    function enforceMaxToasts() {
        while (toastQueue.length >= config.maxToasts) {
            const oldest = toastQueue.shift();
            if (oldest && oldest.element) {
                clearTimeout(oldest.timeout);
                removeToast(oldest.element, oldest.id);
            }
        }
    }

    // =========================================================================
    // Public API
    // =========================================================================

    /**
     * Show a toast notification
     * @param {string} message - Message to display
     * @param {string} [type='info'] - Toast type: 'success', 'error', 'warning', 'info'
     * @param {Object} [options] - Optional configuration
     * @param {number} [options.duration] - Duration in ms before auto-dismiss (default: 3000)
     * @returns {string} Toast ID for manual dismissal
     */
    function show(message, type, options) {
        injectStyles();
        enforceMaxToasts();

        type = type || 'info';
        options = options || {};
        var duration = options.duration !== undefined ? options.duration : config.defaultDuration;

        var toastContainer = getContainer();
        var toast = createToastElement(message, type);
        var id = 'toast_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

        toastContainer.appendChild(toast);

        // Trigger animation on next frame
        requestAnimationFrame(function() {
            toast.classList.add('toast-visible');
        });

        // Setup close button
        var closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', function() {
            clearTimeout(timeoutId);
            removeToast(toast, id);
        });

        // Auto-dismiss
        var timeoutId = setTimeout(function() {
            removeToast(toast, id);
        }, duration);

        toastQueue.push({
            id: id,
            element: toast,
            timeout: timeoutId
        });

        return id;
    }

    /**
     * Show a success toast
     * @param {string} message - Message to display
     * @param {Object} [options] - Optional configuration
     * @returns {string} Toast ID
     */
    function success(message, options) {
        return show(message, 'success', options);
    }

    /**
     * Show an error toast
     * @param {string} message - Message to display
     * @param {Object} [options] - Optional configuration
     * @returns {string} Toast ID
     */
    function error(message, options) {
        return show(message, 'error', options);
    }

    /**
     * Show a warning toast
     * @param {string} message - Message to display
     * @param {Object} [options] - Optional configuration
     * @returns {string} Toast ID
     */
    function warning(message, options) {
        return show(message, 'warning', options);
    }

    /**
     * Show an info toast
     * @param {string} message - Message to display
     * @param {Object} [options] - Optional configuration
     * @returns {string} Toast ID
     */
    function info(message, options) {
        return show(message, 'info', options);
    }

    /**
     * Dismiss a specific toast by ID
     * @param {string} id - Toast ID to dismiss
     */
    function dismiss(id) {
        var toastEntry = toastQueue.find(function(t) { return t.id === id; });
        if (toastEntry) {
            clearTimeout(toastEntry.timeout);
            removeToast(toastEntry.element, id);
        }
    }

    /**
     * Dismiss all toasts
     */
    function dismissAll() {
        toastQueue.forEach(function(entry) {
            clearTimeout(entry.timeout);
            if (entry.element && entry.element.parentNode) {
                entry.element.parentNode.removeChild(entry.element);
            }
        });
        toastQueue = [];
    }

    return {
        show: show,
        success: success,
        error: error,
        warning: warning,
        info: info,
        dismiss: dismiss,
        dismissAll: dismissAll
    };
})();

// Expose globally for use by other modules
window.Toast = Toast;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Toast;
}
