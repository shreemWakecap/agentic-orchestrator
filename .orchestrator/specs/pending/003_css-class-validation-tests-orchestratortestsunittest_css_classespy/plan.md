# Plan: Add CSS class validation tests in .orchestrator/tests/unit/test_css_classes.py. Tests should: (1) Pa

Request: Add CSS class validation tests in .orchestrator/tests/unit/test_css_classes.py. Tests should: (1) Parse HTML templates from .orchestrator/server/templates/. (2) Verify form inputs have 'form-control' class. (3) Verify primary buttons have 'btn btn-primary' classes. (4) Verify secondary buttons have 'btn btn-secondary' classes. (5) Verify form groups have 'mb-3' or similar spacing classes. (6) Use BeautifulSoup or similar for HTML parsing. (7) Follow existing pytest patterns from the codebase.
Complexity: simple

## Goal

Create a BeautifulSoup-based test file that validates Tailwind CSS classes on form elements across dashboard and plan_detail templates.

## Context

- Codebase uses Tailwind CSS, not Bootstrap (user request mentions Bootstrap but must adapt)
- Form inputs use: border border-gray-300 rounded-md shadow-sm focus:ring-blue-500
- Primary buttons use: bg-blue-600 hover:bg-blue-700 text-white rounded-md
- Spacing uses Tailwind classes: mb-6, mb-8, gap-4 (not Bootstrap mb-3)
- Existing test_form_css.py uses simple string matching with TestClient

## Steps

1. Check BeautifulSoup availability
   DO: Verify beautifulsoup4 is available in test dependencies; if not, note for requirements update
   IN: pyproject.toml or requirements files
   OUT: Confirmation of dependency status
   DONE: Can import bs4 in Python environment
   NEEDS: none

## Verify

- pytest .orchestrator/tests/unit/test_css_classes.py -v shows all tests passing
- Test file contains at least 4 test methods covering inputs, primary buttons, secondary buttons, and spacing
