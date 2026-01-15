# Plan: Add form input visibility test assertions to the existing test suite in .orchestrator/tests/unit/. C

Request: Add form input visibility test assertions to the existing test suite in .orchestrator/tests/unit/. Create test_form_visibility.py that: (1) Checks that form inputs are visible and interactable before filling. (2) Uses pytest fixtures and patterns from existing tests. (3) Tests input elements have proper visibility attributes. (4) Validates that disabled/hidden inputs are properly detected.
Complexity: simple

## Goal

Test suite validates form input visibility and interactability by checking HTML attributes for hidden/disabled states.

## Context

- Tests live in .orchestrator/tests/unit/ with class-based grouping
- test_form_css.py pattern: class-scoped client fixture, HTML assertions on response.text
- FastAPI app at server.app.app tested via TestClient
- Form served at "/" endpoint returns HTML with input elements
- Visibility determined by HTML attributes: type="hidden", disabled, style containing display:none/visibility:hidden

## Steps

1. Create visibility test module
   DO: Create test file with class TestFormInputVisibility containing client fixture that yields TestClient(app) for "/" endpoint testing
   IN: .orchestrator/tests/unit/test_form_css.py (pattern reference)
   OUT: .orchestrator/tests/unit/test_form_visibility.py
   DONE: File exists with valid Python syntax, imports TestClient and app
   NEEDS: none

## Verify

- pytest .orchestrator/tests/unit/test_form_visibility.py -v shows all tests passing
- pytest .orchestrator/tests/unit/ -v confirms new tests integrate with existing suite without conflicts
