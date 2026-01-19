/**
 * Keyboard Shortcuts Test Utility
 *
 * Provides testing utilities for the KeyboardShortcuts module.
 * Simulates keyboard events and verifies handler execution.
 *
 * Usage:
 *   // Run all tests
 *   KeyboardShortcutsTest.runAll();
 *
 *   // Run specific test
 *   KeyboardShortcutsTest.testSingleKey();
 *   KeyboardShortcutsTest.testModifierCombination();
 *   KeyboardShortcutsTest.testModalPriority();
 *   KeyboardShortcutsTest.testInputFieldBlocking();
 *
 * Note: Run these tests in the browser console on any page where
 * KeyboardShortcuts module is loaded.
 */

const KeyboardShortcutsTest = (function() {
    'use strict';

    // Test results tracking
    var results = {
        passed: 0,
        failed: 0,
        tests: []
    };

    /**
     * Log a test result
     * @param {string} testName - Name of the test
     * @param {boolean} passed - Whether the test passed
     * @param {string} [message] - Optional message
     */
    function logResult(testName, passed, message) {
        var status = passed ? 'PASS' : 'FAIL';
        var color = passed ? '#10b981' : '#ef4444';
        var icon = passed ? '✓' : '✗';

        results.tests.push({
            name: testName,
            passed: passed,
            message: message || ''
        });

        if (passed) {
            results.passed++;
        } else {
            results.failed++;
        }

        console.log(
            '%c' + icon + ' ' + status + ': ' + testName,
            'color: ' + color + '; font-weight: bold;',
            message ? '- ' + message : ''
        );
    }

    /**
     * Create a synthetic keyboard event
     * @param {string} key - The key value
     * @param {Object} [options] - Additional options
     * @returns {KeyboardEvent}
     */
    function createKeyboardEvent(key, options) {
        options = options || {};

        var eventInit = {
            key: key,
            code: options.code || 'Key' + key.toUpperCase(),
            keyCode: options.keyCode || key.charCodeAt(0),
            which: options.which || key.charCodeAt(0),
            bubbles: true,
            cancelable: true,
            ctrlKey: options.ctrlKey || false,
            altKey: options.altKey || false,
            shiftKey: options.shiftKey || false,
            metaKey: options.metaKey || false
        };

        return new KeyboardEvent('keydown', eventInit);
    }

    /**
     * Dispatch a keyboard event and check if it was handled
     * @param {KeyboardEvent} event - The event to dispatch
     * @returns {boolean} Whether preventDefault was called
     */
    function dispatchAndCheck(event) {
        var wasHandled = false;
        var originalPreventDefault = event.preventDefault.bind(event);

        event.preventDefault = function() {
            wasHandled = true;
            originalPreventDefault();
        };

        document.dispatchEvent(event);
        return wasHandled;
    }

    /**
     * Test single key shortcuts
     */
    function testSingleKey() {
        console.group('Test: Single Key Shortcuts');

        var handlerCalled = false;
        var testKey = 'z'; // Use an uncommon key for testing

        // Register a test shortcut
        var id = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            handlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        if (!id) {
            logResult('Register single key shortcut', false, 'Failed to register shortcut');
            console.groupEnd();
            return;
        }

        logResult('Register single key shortcut', true, 'ID: ' + id);

        // Dispatch the key event
        var event = createKeyboardEvent(testKey);
        var wasHandled = dispatchAndCheck(event);

        logResult('Handler executed', handlerCalled, handlerCalled ? 'Handler was called' : 'Handler was NOT called');
        logResult('Event prevented', wasHandled, wasHandled ? 'preventDefault was called' : 'preventDefault was NOT called');

        // Cleanup
        var unregistered = KeyboardShortcuts.unregisterShortcut(id);
        logResult('Unregister shortcut', unregistered, unregistered ? 'Successfully unregistered' : 'Failed to unregister');

        console.groupEnd();
    }

    /**
     * Test modifier key combinations
     */
    function testModifierCombination() {
        console.group('Test: Modifier Key Combinations');

        var ctrlHandlerCalled = false;
        var altHandlerCalled = false;
        var shiftHandlerCalled = false;
        var multiModHandlerCalled = false;

        // Register Ctrl+Z
        var ctrlZId = KeyboardShortcuts.registerShortcut('ctrl+z', function(e) {
            ctrlHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register Alt+X
        var altXId = KeyboardShortcuts.registerShortcut('alt+x', function(e) {
            altHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register Shift+A (note: shift alone won't block in inputs)
        var shiftAId = KeyboardShortcuts.registerShortcut('shift+a', function(e) {
            shiftHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register Ctrl+Shift+K
        var ctrlShiftKId = KeyboardShortcuts.registerShortcut('ctrl+shift+k', function(e) {
            multiModHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        logResult('Register Ctrl+Z', !!ctrlZId);
        logResult('Register Alt+X', !!altXId);
        logResult('Register Shift+A', !!shiftAId);
        logResult('Register Ctrl+Shift+K', !!ctrlShiftKId);

        // Test Ctrl+Z
        var ctrlZEvent = createKeyboardEvent('z', { ctrlKey: true });
        dispatchAndCheck(ctrlZEvent);
        logResult('Ctrl+Z handler executed', ctrlHandlerCalled);

        // Test Alt+X
        var altXEvent = createKeyboardEvent('x', { altKey: true });
        dispatchAndCheck(altXEvent);
        logResult('Alt+X handler executed', altHandlerCalled);

        // Test Shift+A
        var shiftAEvent = createKeyboardEvent('A', { shiftKey: true });
        dispatchAndCheck(shiftAEvent);
        logResult('Shift+A handler executed', shiftHandlerCalled);

        // Test Ctrl+Shift+K
        var ctrlShiftKEvent = createKeyboardEvent('k', { ctrlKey: true, shiftKey: true });
        dispatchAndCheck(ctrlShiftKEvent);
        logResult('Ctrl+Shift+K handler executed', multiModHandlerCalled);

        // Cleanup
        KeyboardShortcuts.unregisterShortcut(ctrlZId);
        KeyboardShortcuts.unregisterShortcut(altXId);
        KeyboardShortcuts.unregisterShortcut(shiftAId);
        KeyboardShortcuts.unregisterShortcut(ctrlShiftKId);

        console.groupEnd();
    }

    /**
     * Test modal priority override
     */
    function testModalPriority() {
        console.group('Test: Modal Priority Override');

        var pageHandlerCalled = false;
        var modalHandlerCalled = false;
        var testKey = 'y';

        // Register page-level shortcut
        var pageId = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            pageHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register modal-level shortcut (higher priority)
        var modalId = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            modalHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.MODAL);

        logResult('Register page-level shortcut', !!pageId);
        logResult('Register modal-level shortcut', !!modalId);

        // Without modal open, page handler should NOT be called because modal priority is higher
        // but modal handlers are skipped when no modal is active
        var event1 = createKeyboardEvent(testKey);
        dispatchAndCheck(event1);

        // Note: Modal handlers are skipped when activeModalCount === 0
        // So the page handler should be called
        logResult('Page handler called (no modal open)', pageHandlerCalled, 'Page handler should run when no modal is open');

        // Reset
        pageHandlerCalled = false;
        modalHandlerCalled = false;

        // Open modal
        KeyboardShortcuts.modalOpened();

        var event2 = createKeyboardEvent(testKey);
        dispatchAndCheck(event2);

        logResult('Modal handler called (modal open)', modalHandlerCalled, 'Modal handler should override page handler');
        logResult('Page handler NOT called (modal open)', !pageHandlerCalled, 'Page handler should be skipped when modal handler handles event');

        // Close modal and cleanup
        KeyboardShortcuts.modalClosed();
        KeyboardShortcuts.unregisterShortcut(pageId);
        KeyboardShortcuts.unregisterShortcut(modalId);

        console.groupEnd();
    }

    /**
     * Test input field blocking
     */
    function testInputFieldBlocking() {
        console.group('Test: Input Field Blocking');

        var handlerCalled = false;
        var ctrlHandlerCalled = false;
        var testKey = 'q';

        // Create a test input element
        var input = document.createElement('input');
        input.type = 'text';
        input.id = 'keyboard-test-input';
        input.style.position = 'fixed';
        input.style.top = '-1000px';
        document.body.appendChild(input);

        // Register shortcuts
        var singleKeyId = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            handlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        var ctrlKeyId = KeyboardShortcuts.registerShortcut('ctrl+q', function(e) {
            ctrlHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        logResult('Register single key shortcut', !!singleKeyId);
        logResult('Register Ctrl+key shortcut', !!ctrlKeyId);

        // Focus the input
        input.focus();
        logResult('Input is focused', document.activeElement === input);

        // Test single key - should be blocked in input
        var singleKeyEvent = createKeyboardEvent(testKey);
        dispatchAndCheck(singleKeyEvent);
        logResult('Single key blocked in input', !handlerCalled, 'Single key shortcuts should be blocked when input is focused');

        // Reset
        handlerCalled = false;

        // Test Ctrl+key - should work even in input
        var ctrlKeyEvent = createKeyboardEvent(testKey, { ctrlKey: true });
        dispatchAndCheck(ctrlKeyEvent);
        logResult('Ctrl+key works in input', ctrlHandlerCalled, 'Modifier key combinations should work even when input is focused');

        // Cleanup
        input.blur();
        document.body.removeChild(input);
        KeyboardShortcuts.unregisterShortcut(singleKeyId);
        KeyboardShortcuts.unregisterShortcut(ctrlKeyId);

        console.groupEnd();
    }

    /**
     * Test conflict detection
     */
    function testConflictDetection() {
        console.group('Test: Conflict Detection');

        var testKey = 'w';

        // Register first shortcut
        var id1 = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register second shortcut at same priority (should warn)
        console.log('Expecting a conflict warning below:');
        var id2 = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        logResult('Both shortcuts registered', !!id1 && !!id2);

        // Check conflicts
        var conflicts = KeyboardShortcuts.getConflicts();
        var hasConflict = conflicts.some(function(c) {
            return c.normalizedKey === testKey && c.count >= 2;
        });

        logResult('Conflict detected', hasConflict, hasConflict ? 'Conflict found for key "' + testKey + '"' : 'No conflict detected');

        // Cleanup
        KeyboardShortcuts.unregisterShortcut(id1);
        KeyboardShortcuts.unregisterShortcut(id2);

        console.groupEnd();
    }

    /**
     * Test special keys (Escape, Arrow keys)
     */
    function testSpecialKeys() {
        console.group('Test: Special Keys');

        var escHandlerCalled = false;
        var upHandlerCalled = false;
        var downHandlerCalled = false;

        // Register Escape
        var escId = KeyboardShortcuts.registerShortcut('esc', function(e) {
            escHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register Arrow Up
        var upId = KeyboardShortcuts.registerShortcut('up', function(e) {
            upHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        // Register Arrow Down
        var downId = KeyboardShortcuts.registerShortcut('down', function(e) {
            downHandlerCalled = true;
            return true;
        }, KeyboardShortcuts.PRIORITY.PAGE);

        logResult('Register Escape shortcut', !!escId);
        logResult('Register Arrow Up shortcut', !!upId);
        logResult('Register Arrow Down shortcut', !!downId);

        // Test Escape
        var escEvent = createKeyboardEvent('Escape', { code: 'Escape' });
        dispatchAndCheck(escEvent);
        logResult('Escape handler executed', escHandlerCalled);

        // Test Arrow Up
        var upEvent = createKeyboardEvent('ArrowUp', { code: 'ArrowUp' });
        dispatchAndCheck(upEvent);
        logResult('Arrow Up handler executed', upHandlerCalled);

        // Test Arrow Down
        var downEvent = createKeyboardEvent('ArrowDown', { code: 'ArrowDown' });
        dispatchAndCheck(downEvent);
        logResult('Arrow Down handler executed', downHandlerCalled);

        // Cleanup
        KeyboardShortcuts.unregisterShortcut(escId);
        KeyboardShortcuts.unregisterShortcut(upId);
        KeyboardShortcuts.unregisterShortcut(downId);

        console.groupEnd();
    }

    /**
     * Test handler return values
     */
    function testReturnValues() {
        console.group('Test: Handler Return Values');

        var firstHandlerCalled = false;
        var secondHandlerCalled = false;
        var testKey = 'v';

        // Register first handler that returns false (should continue to next)
        var id1 = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            firstHandlerCalled = true;
            return false; // Explicitly pass to next handler
        }, 20); // Higher priority

        // Register second handler
        var id2 = KeyboardShortcuts.registerShortcut(testKey, function(e) {
            secondHandlerCalled = true;
            return true;
        }, 10); // Lower priority

        logResult('Register first handler (returns false)', !!id1);
        logResult('Register second handler (returns true)', !!id2);

        // Dispatch event
        var event = createKeyboardEvent(testKey);
        dispatchAndCheck(event);

        logResult('First handler called', firstHandlerCalled);
        logResult('Second handler called (after first returns false)', secondHandlerCalled, 'Handler returning false should allow next handler to run');

        // Cleanup
        KeyboardShortcuts.unregisterShortcut(id1);
        KeyboardShortcuts.unregisterShortcut(id2);

        console.groupEnd();
    }

    /**
     * Run all tests
     */
    function runAll() {
        // Reset results
        results = {
            passed: 0,
            failed: 0,
            tests: []
        };

        console.log('%c=== KeyboardShortcuts Test Suite ===', 'color: #3b82f6; font-weight: bold; font-size: 14px;');
        console.log('Starting tests...\n');

        // Check if KeyboardShortcuts module is available
        if (typeof KeyboardShortcuts === 'undefined') {
            console.error('%c✗ KeyboardShortcuts module not found!', 'color: #ef4444; font-weight: bold;');
            console.log('Make sure keyboard-shortcuts.js is loaded before running tests.');
            return results;
        }

        // Save current debug mode and enable it for detailed logs
        var wasDebugMode = KeyboardShortcuts.isDebugMode();
        // Don't enable debug mode during tests to keep output clean
        // KeyboardShortcuts.setDebugMode(true);

        // Run tests
        testSingleKey();
        testModifierCombination();
        testModalPriority();
        testInputFieldBlocking();
        testConflictDetection();
        testSpecialKeys();
        testReturnValues();

        // Restore debug mode
        if (!wasDebugMode) {
            // KeyboardShortcuts.setDebugMode(false);
        }

        // Print summary
        console.log('\n%c=== Test Summary ===', 'color: #3b82f6; font-weight: bold; font-size: 14px;');
        var passColor = results.failed === 0 ? '#10b981' : '#f59e0b';
        console.log(
            '%c' + results.passed + ' passed%c, %c' + results.failed + ' failed%c out of ' + (results.passed + results.failed) + ' tests',
            'color: #10b981; font-weight: bold;',
            'color: inherit;',
            'color: ' + (results.failed > 0 ? '#ef4444' : '#10b981') + '; font-weight: bold;',
            'color: inherit;'
        );

        if (results.failed > 0) {
            console.log('\n%cFailed tests:', 'color: #ef4444; font-weight: bold;');
            results.tests.forEach(function(test) {
                if (!test.passed) {
                    console.log('  - ' + test.name + (test.message ? ': ' + test.message : ''));
                }
            });
        }

        return results;
    }

    /**
     * Get the last test results
     * @returns {Object} Test results
     */
    function getResults() {
        return results;
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        runAll: runAll,
        getResults: getResults,
        testSingleKey: testSingleKey,
        testModifierCombination: testModifierCombination,
        testModalPriority: testModalPriority,
        testInputFieldBlocking: testInputFieldBlocking,
        testConflictDetection: testConflictDetection,
        testSpecialKeys: testSpecialKeys,
        testReturnValues: testReturnValues
    };

})();

// Expose globally
window.KeyboardShortcutsTest = KeyboardShortcutsTest;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KeyboardShortcutsTest;
}
