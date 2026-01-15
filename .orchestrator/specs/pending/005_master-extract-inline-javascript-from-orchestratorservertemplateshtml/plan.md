# Plan: Extract inline JavaScript from .orchestrator/server/templates/*.html into separate files and add Jes

Request: Extract inline JavaScript from .orchestrator/server/templates/*.html into separate files and add Jest tests. (1) Analyze all HTML templates for inline <script> tags. (2) Extract JavaScript into .orchestrator/server/static/js/ with meaningful names (e.g., plan-list.js, build-progress.js). (3) Update HTML templates to reference external JS files. (4) Create package.json with jest dependency if not exists, or update existing. (5) Add jest.config.js with proper configuration. (6) Create .orchestrator/server/static/js/__tests__/ directory. (7) Write Jest unit tests for each extracted JS file testing main functions and event handlers. (8) Ensure no inline scripts remain in templates.
Complexity: complex

## Goal

Extract inline JavaScript from all templates into static/js/ files and establish Jest testing infrastructure with comprehensive unit tests.

## Context

- No existing package.json or Jest configuration at .orchestrator/ level
- SidePopup is defined inline in base.html (~75 lines) and used by other templates
- 4 page templates have inline scripts: dashboard.html, plans.html, plan_detail.html, run_detail.html
- playwright/ exists at project root and must be excluded from Jest
- Jinja context (plan.id, run.id, URLs) must be passed via data-* attributes
- Script load order critical: side-popup.js must load before template-specific scripts

## Steps

1. Create package.json
   DO: Create npm package file with name "orchestrator-frontend", version "1.0.0", private true, scripts for "test": "jest" and "test:watch": "jest --watch", devDependencies for jest@^29.x, jest-environment-jsdom@^29.x, and @testing-library/dom
   IN: none
   OUT: .orchestrator/package.json
   DONE: File exists and is valid JSON syntax
   NEEDS: none

## Verify

- cd .orchestrator && npx jest --version outputs 29.x
- cd .orchestrator && npm test runs all tests with 0 failures
- .orchestrator/node_modules/jest-environment-jsdom/ directory exists
- All 5 JS files exist in .orchestrator/server/static/js/
- All 5 test files exist in .orchestrator/server/static/js/__tests__/
- No inline `<script>` blocks remain in the 5 modified templates (except external script tags)
- Each modified template has appropriate data-* attributes for Jinja context
- Browser DevTools Network tab shows all JS files loading with 200 status
- Browser console has no JavaScript errors on any page
- SidePopup, form submissions, toggle functions, build/review actions, and SSE streams all function correctly
