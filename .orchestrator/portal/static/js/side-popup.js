/**
 * Side Popup Component
 * A reusable slide-in panel for displaying content
 *
 * Uses centralized KeyboardShortcuts for ESC handling with proper priority
 */

const SidePopup = {
    overlay: null,
    popup: null,
    titleEl: null,
    contentEl: null,
    escShortcutId: null,

    init() {
        this.overlay = document.getElementById('side-popup-overlay');
        this.popup = document.getElementById('side-popup');
        this.titleEl = document.getElementById('side-popup-title');
        this.contentEl = document.getElementById('side-popup-content');

        // ESC handler is now registered/unregistered dynamically when popup opens/closes
        // This ensures proper priority handling through the centralized KeyboardShortcuts module
    },

    /**
     * Register ESC shortcut with centralized keyboard manager
     * Uses PAGE priority (10) - will yield to MODAL priority (100) dialogs
     */
    _registerEscHandler() {
        if (this.escShortcutId) {
            // Already registered
            return;
        }

        // Use PAGE priority - confirm dialogs use MODAL priority so they take precedence
        this.escShortcutId = KeyboardShortcuts.registerShortcut('esc', (event) => {
            // Only handle if popup is actually open
            if (!this.isOpen()) {
                return false; // Pass to next handler
            }

            // Check if PlanManager's confirm dialog is visible (extra safety check)
            const confirmDialog = document.getElementById('confirm-dialog-overlay');
            if (confirmDialog && confirmDialog.classList.contains('active')) {
                return false; // Let confirm dialog handle it
            }

            this.close();
            return true; // Handled - prevent default and stop propagation
        }, KeyboardShortcuts.PRIORITY.PAGE);
    },

    /**
     * Unregister ESC shortcut from centralized keyboard manager
     */
    _unregisterEscHandler() {
        if (this.escShortcutId) {
            KeyboardShortcuts.unregisterShortcut(this.escShortcutId);
            this.escShortcutId = null;
        }
    },

    /**
     * Check if the popup is currently open
     */
    isOpen() {
        return this.overlay && this.overlay.classList.contains('active');
    },

    open(title, content, options = {}) {
        this.titleEl.textContent = title;

        if (typeof content === 'string') {
            this.contentEl.innerHTML = content;
        } else if (content instanceof HTMLElement) {
            this.contentEl.innerHTML = '';
            this.contentEl.appendChild(content);
        }

        // Apply optional custom class
        if (options.contentClass) {
            this.contentEl.className = 'side-popup-content ' + options.contentClass;
        } else {
            this.contentEl.className = 'side-popup-content';
        }

        this.overlay.classList.add('active');
        this.popup.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Register ESC handler when popup opens
        this._registerEscHandler();
    },

    close() {
        this.overlay.classList.remove('active');
        this.popup.classList.remove('active');
        document.body.style.overflow = '';

        // Unregister ESC handler when popup closes
        this._unregisterEscHandler();
    },

    async loadUrl(title, url, options = {}) {
        this.open(title, '<div class="flex items-center justify-center py-12"><svg class="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>', options);

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load content');
            const data = await response.json();

            if (options.transform) {
                this.contentEl.innerHTML = options.transform(data);
            } else if (data.content) {
                this.contentEl.innerHTML = '<pre class="whitespace-pre-wrap text-sm text-gray-800 font-mono">' + this.escapeHtml(data.content) + '</pre>';
            } else {
                this.contentEl.innerHTML = '<pre class="text-sm text-gray-800">' + JSON.stringify(data, null, 2) + '</pre>';
            }
        } catch (error) {
            this.contentEl.innerHTML = '<div class="text-red-600 text-center py-8"><svg class="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg><p>Error loading content</p><p class="text-sm mt-2">' + error.message + '</p></div>';
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => SidePopup.init());
