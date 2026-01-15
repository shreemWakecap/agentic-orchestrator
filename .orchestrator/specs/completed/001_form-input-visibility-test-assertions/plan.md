# Plan: Add form input visibility test assertions to the existing test suite in .orchestrator/tests/unit/. C

Request: Add form input visibility test assertions to the existing test suite in .orchestrator/tests/unit/. Create test_form_visibility.py that: (1) Checks that form inputs are visible and interactable before filling. (2) Uses pytest fixtures and patterns from existing tests. (3) Tests input elements have proper visibility attributes. (4) Validates that disabled/hidden inputs are properly detected.
Complexity: simple

## Goal

Extend test_form_visibility.py with comprehensive visibility assertion tests covering all four requirements: visible/interactable checks, pytest fixtures, visibility attributes, and disabled/hidden detection.

## Context

- test_form_visibility.py already exists with basic dashboard tests
- test_agent.py has TestInputVisibility class (lines 379-440) using MagicMock with is_displayed()/is_enabled()
- Pattern uses TestClient(app) from server.app for HTML response testing
- conftest.py has existing fixtures (project_root, mock_subprocess_*, mock_agent_result)
- MagicMock is used for simulating element visibility states

## Steps

1. Add mock_form_element fixture to conftest.py
   DO: Create a pytest fixture that returns a MagicMock object with is_displayed() and is_enabled() methods, defaulting to True for both, matching the pattern in test_agent.py TestInputVisibility
   IN: .orchestrator/tests/unit/conftest.py, .orchestrator/tests/unit/test_agent.py (lines 379-440 for pattern reference)
   OUT: .orchestrator/tests/unit/conftest.py (modified with mock_form_element fixture)
   DONE: Fixture is importable and returns MagicMock with callable is_displayed()/is_enabled() methods
   NEEDS: none

2. Add TestFormInputVisibility class for visible/interactable checks
   DO: Create TestFormInputVisibility class in test_form_visibility.py with tests that verify form inputs are visible and interactable before filling - use mock_form_element fixture to assert is_displayed() returns True and is_enabled() returns True for standard inputs
   IN: .orchestrator/tests/unit/test_form_visibility.py, .orchestrator/tests/unit/conftest.py
   OUT: .orchestrator/tests/unit/test_form_visibility.py (modified with TestFormInputVisibility class)
   DONE: pytest .orchestrator/tests/unit/test_form_visibility.py::TestFormInputVisibility -v shows passing tests for visible/interactable assertions
   NEEDS: 1

3. Add tests using pytest fixtures and existing patterns
   DO: Add test methods that demonstrate proper pytest fixture usage - inject mock_form_element fixture, use TestClient for HTML responses, follow class-based test pattern from test_agent.py with setup/teardown if needed
   IN: .orchestrator/tests/unit/test_form_visibility.py, .orchestrator/tests/unit/test_agent.py (pattern reference)
   OUT: .orchestrator/tests/unit/test_form_visibility.py (modified with fixture-using tests)
   DONE: Tests use @pytest.fixture injection pattern and TestClient consistently with existing test files
   NEEDS: 2

4. Add visibility attribute assertion tests
   DO: Add test methods that check HTML form inputs have proper visibility-related attributes - parse response.text for input elements, verify absence of hidden type, verify absence of style="display:none", verify presence of expected input types (text, email, password, etc.)
   IN: .orchestrator/tests/unit/test_form_visibility.py, server/app (for TestClient endpoint)
   OUT: .orchestrator/tests/unit/test_form_visibility.py (modified with attribute assertion tests)
   DONE: Tests assert specific visibility attributes in HTML and pass when inputs lack hidden/display:none attributes
   NEEDS: 3

5. Add disabled/hidden input detection tests
   DO: Add test methods that validate disabled and hidden inputs are properly detected - create tests with mock elements where is_enabled() returns False for disabled inputs, is_displayed() returns False for hidden inputs, and verify detection logic correctly identifies these states
   IN: .orchestrator/tests/unit/test_form_visibility.py, .orchestrator/tests/unit/conftest.py
   OUT: .orchestrator/tests/unit/test_form_visibility.py (modified with disabled/hidden detection tests)
   DONE: pytest shows passing tests that correctly identify disabled inputs (is_enabled=False) and hidden inputs (is_displayed=False)
   NEEDS: 4

6. Run full test suite to verify integration
   DO: Execute pytest on the entire test_form_visibility.py file to ensure all new tests pass and integrate properly with existing tests, no import errors, no fixture conflicts
   IN: .orchestrator/tests/unit/test_form_visibility.py
   OUT: Test execution results showing all tests pass
   DONE: pytest .orchestrator/tests/unit/test_form_visibility.py -v shows 100% pass rate with no errors
   NEEDS: 5

## Verify

- pytest .orchestrator/tests/unit/test_form_visibility.py -v passes all tests
- pytest .orchestrator/tests/unit/test_form_visibility.py --collect-only shows TestFormInputVisibility class with tests covering all 4 requirements
- pytest .orchestrator/tests/unit/conftest.py --fixtures shows mock_form_element fixture available
