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
            bgClass: 'toast-success',
            iconBg: 'toast-icon-success',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        },
        error: {
            bgClass: 'toast-error',
            iconBg: 'toast-icon-error',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
        },
        warning: {
            bgClass: 'toast-warning',
            iconBg: 'toast-icon-warning',
            icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>'
        },
        info: {
            bgClass: 'toast-info',
            iconBg: 'toast-icon-info',
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
            /* Toast Keyframe Animations */
            @keyframes toast-slide-in {
                0% {
                    opacity: 0;
                    transform: translateX(calc(100% + 1rem)) scale(0.95);
                }
                60% {
                    opacity: 1;
                    transform: translateX(-8px) scale(1.02);
                }
                100% {
                    opacity: 1;
                    transform: translateX(0) scale(1);
                }
            }

            @keyframes toast-slide-out {
                0% {
                    opacity: 1;
                    transform: translateX(0) scale(1);
                }
                100% {
                    opacity: 0;
                    transform: translateX(calc(100% + 1rem)) scale(0.95);
                }
            }

            @keyframes toast-progress {
                from { width: 100%; }
                to { width: 0%; }
            }

            .toast-container {
                position: fixed;
                bottom: 1.5rem;
                right: 1.5rem;
                z-index: 9999;
                display: flex;
                flex-direction: column-reverse;
                gap: 0.75rem;
                pointer-events: none;
            }

            .toast {
                display: flex;
                align-items: center;
                gap: 0.875rem;
                padding: 1rem 1.25rem;
                border-radius: 0.75rem;
                font-size: 0.875rem;
                font-weight: 500;
                pointer-events: auto;
                max-width: 26rem;
                min-width: 20rem;
                opacity: 0;
                transform: translateX(calc(100% + 1rem));
                position: relative;
                overflow: hidden;
                /* Glassmorphism */
                background: var(--glass-bg-strong, rgba(255, 255, 255, 0.85));
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.3));
                box-shadow:
                    0 20px 25px -5px rgba(0, 0, 0, 0.1),
                    0 8px 10px -6px rgba(0, 0, 0, 0.1),
                    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
                color: var(--text-primary, #0f172a);
            }

            .toast.toast-visible {
                opacity: 1;
                transform: translateX(0);
                animation: toast-slide-in 400ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
            }

            .toast.toast-hiding {
                animation: toast-slide-out 300ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
            }

            /* Progress bar */
            .toast::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                height: 3px;
                border-radius: 0 0 0.75rem 0.75rem;
                animation: toast-progress ${config.defaultDuration}ms linear forwards;
            }

            /* Toast type-specific styling with modern colors */
            .toast.toast-success {
                border-left: 4px solid var(--color-success-500, #10b981);
            }
            .toast.toast-success::after {
                background: linear-gradient(90deg, var(--color-success-500, #10b981), var(--color-success-400, #34d399));
            }

            .toast.toast-error {
                border-left: 4px solid var(--color-danger-500, #ef4444);
            }
            .toast.toast-error::after {
                background: linear-gradient(90deg, var(--color-danger-500, #ef4444), var(--color-danger-400, #f87171));
            }

            .toast.toast-warning {
                border-left: 4px solid var(--color-warning-500, #f59e0b);
            }
            .toast.toast-warning::after {
                background: linear-gradient(90deg, var(--color-warning-500, #f59e0b), var(--color-warning-400, #fbbf24));
            }

            .toast.toast-info {
                border-left: 4px solid var(--color-primary-500, #3b82f6);
            }
            .toast.toast-info::after {
                background: linear-gradient(90deg, var(--color-primary-500, #3b82f6), var(--color-primary-400, #60a5fa));
            }

            .toast-icon {
                flex-shrink: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 2rem;
                height: 2rem;
                border-radius: 0.5rem;
            }

            /* Icon backgrounds with subtle gradients */
            .toast-icon.toast-icon-success {
                background: linear-gradient(135deg, var(--color-success-100, #d1fae5), var(--color-success-50, #ecfdf5));
                color: var(--color-success-600, #059669);
            }
            .toast-icon.toast-icon-error {
                background: linear-gradient(135deg, var(--color-danger-100, #fee2e2), var(--color-danger-50, #fef2f2));
                color: var(--color-danger-600, #dc2626);
            }
            .toast-icon.toast-icon-warning {
                background: linear-gradient(135deg, var(--color-warning-100, #fef3c7), var(--color-warning-50, #fffbeb));
                color: var(--color-warning-600, #d97706);
            }
            .toast-icon.toast-icon-info {
                background: linear-gradient(135deg, var(--color-primary-100, #dbeafe), var(--color-primary-50, #eff6ff));
                color: var(--color-primary-600, #2563eb);
            }

            .toast-message {
                flex: 1;
                word-break: break-word;
                line-height: 1.4;
            }

            .toast-close {
                flex-shrink: 0;
                padding: 0.375rem;
                margin: -0.25rem;
                margin-left: 0.5rem;
                border-radius: 0.375rem;
                opacity: 0.5;
                cursor: pointer;
                transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
                background: transparent;
                border: none;
                color: currentColor;
            }

            .toast-close:hover {
                opacity: 1;
                background: rgba(0, 0, 0, 0.06);
            }

            /* Responsive adjustments */
            @media (max-width: 480px) {
                .toast-container {
                    right: 1rem;
                    left: 1rem;
                    bottom: 1rem;
                }
                .toast {
                    min-width: auto;
                    max-width: none;
                }
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
        iconSpan.className = 'toast-icon ' + typeSettings.iconBg;
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
