/**
 * Folder Picker Module
 *
 * Reusable module for folder selection functionality in the SDLC Orchestrator.
 * This module provides:
 * - Browse button functionality using showDirectoryPicker API
 * - Drag-and-drop folder handling
 * - Path validation via API calls
 * - Visual feedback states for validation
 *
 * Usage:
 * Include this file after common.js. Initialize with FolderPicker.init() and
 * configure the input element, validation endpoint, and callbacks.
 */

const FolderPicker = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    /**
     * Default configuration options
     */
    var defaultConfig = {
        validationEndpoint: '/api/projects/validate-path',
        debounceDelay: 300,
        cssClasses: {
            loading: 'folder-picker-loading',
            valid: 'folder-picker-valid',
            invalid: 'folder-picker-invalid',
            dropzone: 'folder-picker-dropzone',
            dragover: 'folder-picker-dragover'
        }
    };

    /**
     * Current instance configuration
     */
    var config = {};

    /**
     * Active input element reference
     */
    var inputElement = null;

    /**
     * Dropzone element reference
     */
    var dropzoneElement = null;

    /**
     * Feedback element reference
     */
    var feedbackElement = null;

    /**
     * Debounced validation function
     */
    var debouncedValidate = null;

    /**
     * Current validation state
     */
    var validationState = {
        isValidating: false,
        isValid: null,
        lastPath: '',
        lastError: ''
    };

    // =========================================================================
    // Browser Support Detection
    // =========================================================================

    /**
     * Check if the File System Access API is supported
     * @returns {boolean} Whether showDirectoryPicker is available
     */
    function isFileSystemAccessSupported() {
        return typeof window.showDirectoryPicker === 'function';
    }

    /**
     * Check if drag-and-drop with directory entries is supported
     * @returns {boolean} Whether webkitGetAsEntry is available
     */
    function isDragDropSupported() {
        return typeof DataTransferItem !== 'undefined' &&
               typeof DataTransferItem.prototype.webkitGetAsEntry === 'function';
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Initialize the folder picker
     * @param {Object} options - Configuration options
     * @param {HTMLElement|string} options.input - Input element or ID for path display
     * @param {HTMLElement|string} [options.dropzone] - Dropzone element or ID (defaults to input)
     * @param {HTMLElement|string} [options.feedback] - Element for validation feedback
     * @param {HTMLElement|string} [options.browseButton] - Browse button element or ID
     * @param {string} [options.validationEndpoint] - API endpoint for path validation
     * @param {number} [options.debounceDelay] - Debounce delay for validation in ms
     * @param {Function} [options.onPathSelected] - Callback when path is selected
     * @param {Function} [options.onValidationChange] - Callback when validation state changes
     * @param {Function} [options.onError] - Callback for errors
     * @returns {Object} FolderPicker instance for chaining
     */
    function init(options) {
        options = options || {};

        // Merge configuration
        config = Object.assign({}, defaultConfig, options);

        // Get input element
        inputElement = getElement(options.input);
        if (!inputElement) {
            console.error('FolderPicker: Input element not found');
            return FolderPicker;
        }

        // Get dropzone element (defaults to input)
        dropzoneElement = getElement(options.dropzone) || inputElement;

        // Get feedback element
        feedbackElement = getElement(options.feedback);

        // Create debounced validation function
        debouncedValidate = OrchestratorUtils.debounce(function(path) {
            validatePath(path);
        }, config.debounceDelay);

        // Set up event listeners
        setupInputListeners();
        setupDropzoneListeners();

        // Set up browse button if provided
        if (options.browseButton) {
            setupBrowseButton(options.browseButton);
        }

        return FolderPicker;
    }

    /**
     * Get element by ID or return element if already an element
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @returns {HTMLElement|null} The element or null
     */
    function getElement(elementOrId) {
        if (!elementOrId) return null;
        if (typeof elementOrId === 'string') {
            return document.getElementById(elementOrId);
        }
        return elementOrId;
    }

    // =========================================================================
    // Event Listeners Setup
    // =========================================================================

    /**
     * Set up input element event listeners
     */
    function setupInputListeners() {
        if (!inputElement) return;

        // Validate on input change
        inputElement.addEventListener('input', function(e) {
            var path = e.target.value.trim();
            if (path) {
                setValidationState('loading');
                debouncedValidate(path);
            } else {
                clearValidationState();
            }
        });

        // Validate on blur
        inputElement.addEventListener('blur', function(e) {
            var path = e.target.value.trim();
            if (path && path !== validationState.lastPath) {
                validatePath(path);
            }
        });
    }

    /**
     * Set up dropzone event listeners for drag-and-drop
     */
    function setupDropzoneListeners() {
        if (!dropzoneElement) return;

        // Add dropzone class
        dropzoneElement.classList.add(config.cssClasses.dropzone);

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function(eventName) {
            dropzoneElement.addEventListener(eventName, function(e) {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // Visual feedback on drag
        dropzoneElement.addEventListener('dragenter', function() {
            dropzoneElement.classList.add(config.cssClasses.dragover);
        });

        dropzoneElement.addEventListener('dragover', function() {
            dropzoneElement.classList.add(config.cssClasses.dragover);
        });

        dropzoneElement.addEventListener('dragleave', function(e) {
            // Only remove if leaving the dropzone entirely
            if (!dropzoneElement.contains(e.relatedTarget)) {
                dropzoneElement.classList.remove(config.cssClasses.dragover);
            }
        });

        // Handle drop
        dropzoneElement.addEventListener('drop', function(e) {
            dropzoneElement.classList.remove(config.cssClasses.dragover);
            handleDrop(e);
        });
    }

    /**
     * Set up browse button click handler
     * @param {HTMLElement|string} buttonOrId - Button element or ID
     */
    function setupBrowseButton(buttonOrId) {
        var button = getElement(buttonOrId);
        if (!button) return;

        button.addEventListener('click', function(e) {
            e.preventDefault();
            openPicker();
        });
    }

    // =========================================================================
    // Browse Functionality
    // =========================================================================

    /**
     * Open the native folder picker dialog
     * @returns {Promise<string|null>} Promise resolving to selected path or null
     */
    function openPicker() {
        if (!isFileSystemAccessSupported()) {
            var errorMsg = 'Folder picker is not supported in this browser. Please enter the path manually or use a modern browser like Chrome or Edge.';
            showError(errorMsg);
            if (config.onError) {
                config.onError(new Error(errorMsg));
            }
            return Promise.resolve(null);
        }

        return window.showDirectoryPicker({ mode: 'read' })
            .then(function(handle) {
                // Note: showDirectoryPicker returns a handle, not the full path
                // The full system path is not accessible for security reasons
                // We use the directory name as a visual indicator
                var dirName = handle.name;

                // For now, we'll use the directory name
                // In a real implementation, you might need to handle this differently
                // depending on your backend's path resolution strategy
                setInputValue(dirName);

                if (config.onPathSelected) {
                    config.onPathSelected(dirName, handle);
                }

                // Trigger validation
                setValidationState('loading');
                validatePath(dirName);

                return dirName;
            })
            .catch(function(err) {
                // User cancelled or error occurred
                if (err.name !== 'AbortError') {
                    console.error('FolderPicker: Error opening directory picker', err);
                    showError('Failed to open folder picker: ' + err.message);
                    if (config.onError) {
                        config.onError(err);
                    }
                }
                return null;
            });
    }

    // =========================================================================
    // Drag and Drop Handling
    // =========================================================================

    /**
     * Handle drop event for folder drag-and-drop
     * @param {DragEvent} event - The drop event
     * @returns {Promise<string|null>} Promise resolving to folder path or null
     */
    function handleDrop(event) {
        if (!isDragDropSupported()) {
            showError('Drag and drop is not fully supported in this browser.');
            return Promise.resolve(null);
        }

        var items = event.dataTransfer.items;
        if (!items || items.length === 0) {
            return Promise.resolve(null);
        }

        // Look for a folder in the dropped items
        for (var i = 0; i < items.length; i++) {
            var item = items[i];

            if (item.kind === 'file') {
                var entry = item.webkitGetAsEntry();

                if (entry && entry.isDirectory) {
                    var folderPath = entry.fullPath || entry.name;

                    // Remove leading slash if present (from fullPath)
                    if (folderPath.charAt(0) === '/') {
                        folderPath = folderPath.substring(1);
                    }

                    setInputValue(folderPath);

                    if (config.onPathSelected) {
                        config.onPathSelected(folderPath, entry);
                    }

                    // Trigger validation
                    setValidationState('loading');
                    validatePath(folderPath);

                    return Promise.resolve(folderPath);
                }
            }
        }

        // No folder found in dropped items
        showError('Please drop a folder, not a file.');
        return Promise.resolve(null);
    }

    // =========================================================================
    // Path Validation
    // =========================================================================

    /**
     * Validate a folder path via API call
     * @param {string} path - The path to validate
     * @returns {Promise<Object>} Promise resolving to validation result
     */
    function validatePath(path) {
        if (!path || typeof path !== 'string') {
            clearValidationState();
            return Promise.resolve({ valid: false, error: 'No path provided' });
        }

        path = path.trim();
        if (!path) {
            clearValidationState();
            return Promise.resolve({ valid: false, error: 'Path is empty' });
        }

        validationState.isValidating = true;
        validationState.lastPath = path;
        setValidationState('loading');

        return fetch(config.validationEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: path })
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            validationState.isValidating = false;

            if (data.valid) {
                validationState.isValid = true;
                validationState.lastError = '';
                setValidationState('valid', data.message || 'Path is valid');
            } else {
                validationState.isValid = false;
                validationState.lastError = data.error || 'Path is invalid';
                setValidationState('invalid', validationState.lastError);
            }

            if (config.onValidationChange) {
                config.onValidationChange({
                    path: path,
                    valid: validationState.isValid,
                    error: validationState.lastError,
                    data: data
                });
            }

            return {
                valid: validationState.isValid,
                error: validationState.lastError,
                data: data
            };
        })
        .catch(function(err) {
            validationState.isValidating = false;
            validationState.isValid = false;
            validationState.lastError = 'Validation failed: ' + err.message;

            setValidationState('invalid', validationState.lastError);

            if (config.onValidationChange) {
                config.onValidationChange({
                    path: path,
                    valid: false,
                    error: validationState.lastError
                });
            }

            if (config.onError) {
                config.onError(err);
            }

            return {
                valid: false,
                error: validationState.lastError
            };
        });
    }

    // =========================================================================
    // Visual Feedback
    // =========================================================================

    /**
     * Set validation visual state
     * @param {string} state - State: 'loading', 'valid', 'invalid', or 'clear'
     * @param {string} [message] - Optional message to display
     */
    function setValidationState(state, message) {
        if (!inputElement) return;

        // Remove all state classes
        inputElement.classList.remove(
            config.cssClasses.loading,
            config.cssClasses.valid,
            config.cssClasses.invalid
        );

        // Add appropriate class
        switch (state) {
            case 'loading':
                inputElement.classList.add(config.cssClasses.loading);
                break;
            case 'valid':
                inputElement.classList.add(config.cssClasses.valid);
                break;
            case 'invalid':
                inputElement.classList.add(config.cssClasses.invalid);
                break;
        }

        // Update feedback element if present
        if (feedbackElement) {
            updateFeedbackElement(state, message);
        }
    }

    /**
     * Update the feedback element with state and message
     * @param {string} state - Current state
     * @param {string} [message] - Message to display
     */
    function updateFeedbackElement(state, message) {
        if (!feedbackElement) return;

        // Clear previous classes
        feedbackElement.classList.remove('text-green-600', 'text-red-600', 'text-gray-500');
        feedbackElement.innerHTML = '';

        switch (state) {
            case 'loading':
                feedbackElement.classList.add('text-gray-500');
                feedbackElement.innerHTML = '<span class="animate-pulse">Validating path...</span>';
                break;
            case 'valid':
                feedbackElement.classList.add('text-green-600');
                feedbackElement.innerHTML = '<span>&#10003; ' + OrchestratorUtils.escapeHtml(message || 'Valid path') + '</span>';
                break;
            case 'invalid':
                feedbackElement.classList.add('text-red-600');
                feedbackElement.innerHTML = '<span>&#10007; ' + OrchestratorUtils.escapeHtml(message || 'Invalid path') + '</span>';
                break;
            default:
                // Clear state
                feedbackElement.innerHTML = '';
        }
    }

    /**
     * Clear validation state
     */
    function clearValidationState() {
        validationState.isValid = null;
        validationState.lastPath = '';
        validationState.lastError = '';
        setValidationState('clear');
    }

    /**
     * Show an error message
     * @param {string} message - Error message to display
     */
    function showError(message) {
        if (feedbackElement) {
            setValidationState('invalid', message);
        } else {
            console.warn('FolderPicker:', message);
        }
    }

    // =========================================================================
    // Input Helpers
    // =========================================================================

    /**
     * Set the input element value
     * @param {string} value - Value to set
     */
    function setInputValue(value) {
        if (!inputElement) return;
        inputElement.value = value;

        // Dispatch input event for any listeners
        var event = new Event('input', { bubbles: true });
        inputElement.dispatchEvent(event);
    }

    /**
     * Get the current input value
     * @returns {string} Current input value
     */
    function getInputValue() {
        return inputElement ? inputElement.value : '';
    }

    // =========================================================================
    // State Accessors
    // =========================================================================

    /**
     * Check if the current path is valid
     * @returns {boolean|null} true if valid, false if invalid, null if not validated
     */
    function isValid() {
        return validationState.isValid;
    }

    /**
     * Check if validation is in progress
     * @returns {boolean} Whether validation is currently running
     */
    function isValidating() {
        return validationState.isValidating;
    }

    /**
     * Get the current validation state
     * @returns {Object} Current validation state
     */
    function getValidationState() {
        return Object.assign({}, validationState);
    }

    // =========================================================================
    // Cleanup
    // =========================================================================

    /**
     * Destroy the folder picker instance and clean up
     */
    function destroy() {
        // Note: In a more robust implementation, we'd store and remove
        // specific event listeners. For simplicity, we just clear references.
        inputElement = null;
        dropzoneElement = null;
        feedbackElement = null;
        debouncedValidate = null;
        config = Object.assign({}, defaultConfig);
        validationState = {
            isValidating: false,
            isValid: null,
            lastPath: '',
            lastError: ''
        };
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // Initialization
        init: init,
        destroy: destroy,

        // Core functionality
        openPicker: openPicker,
        handleDrop: handleDrop,
        validatePath: validatePath,

        // State management
        setInputValue: setInputValue,
        getInputValue: getInputValue,
        clearValidationState: clearValidationState,

        // State accessors
        isValid: isValid,
        isValidating: isValidating,
        getValidationState: getValidationState,

        // Browser support checks
        isFileSystemAccessSupported: isFileSystemAccessSupported,
        isDragDropSupported: isDragDropSupported
    };
})();

// Expose globally for use by other modules
window.FolderPicker = FolderPicker;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FolderPicker;
}
