# Plan: Add Playwright E2E tests for the orchestrator web UI. (1) Create .orchestrator/tests/e2e/ directory 

Request: Add Playwright E2E tests for the orchestrator web UI. (1) Create .orchestrator/tests/e2e/ directory structure. (2) Add playwright.config.ts with baseURL pointing to localhost:8000, screenshot on failure, and proper timeout settings. (3) Create tests/e2e/plans.spec.ts testing: view plan list page, verify plan items display, click on a plan to view details. (4) Create tests/e2e/plan-details.spec.ts testing: view plan detail page, verify metadata displays, verify steps are listed. (5) Create tests/e2e/build.spec.ts testing: start a build from plan detail page, verify build progress updates. (6) Add package.json with @playwright/test dependency. (7) Add npm scripts for running e2e tests.
Complexity: medium

## Goal

Complete Playwright E2E test infrastructure with config, three spec files covering plans/details/builds, and package.json with test scripts.

## Context

- Tests organized under .orchestrator/tests/ hierarchy
- Web UI available at localhost:8000
- No existing Node.js or Playwright configuration
- Existing unit tests use pytest pattern in test_css_classes.py
- Need full e2e infrastructure from scratch

## Steps

1. Create e2e directory structure
   DO: Create the .orchestrator/tests/e2e/ directory to house all Playwright test files
   IN: none
   OUT: .orchestrator/tests/e2e/ directory
   DONE: Directory exists and is accessible
   NEEDS: none

2. Create Playwright configuration
   DO: Create playwright.config.ts with baseURL set to http://localhost:8000, screenshot capture on test failure, 30 second default timeout, and configure test directory to current folder
   IN: none
   OUT: .orchestrator/tests/e2e/playwright.config.ts
   DONE: File exists with valid TypeScript syntax, contains baseURL, screenshot, and timeout settings
   NEEDS: 1

3. Create plans list page tests
   DO: Create plans.spec.ts with three test cases - navigate to plan list page and verify it loads, verify plan items are displayed in a list format, click on a plan item and verify navigation to details page
   IN: none
   OUT: .orchestrator/tests/e2e/plans.spec.ts
   DONE: File exists with describe block containing three test cases for list view, item display, and click navigation
   NEEDS: 1

4. Create plan details page tests
   DO: Create plan-details.spec.ts with three test cases - navigate directly to a plan detail page and verify it loads, verify plan metadata (name, status, timestamps) displays correctly, verify steps are listed in order
   IN: none
   OUT: .orchestrator/tests/e2e/plan-details.spec.ts
   DONE: File exists with describe block containing three test cases for detail view, metadata, and steps listing
   NEEDS: 1

5. Create build execution tests
   DO: Create build.spec.ts with two test cases - locate and click start build button from plan detail page, verify build progress updates appear after starting build (status changes, progress indicators)
   IN: none
   OUT: .orchestrator/tests/e2e/build.spec.ts
   DONE: File exists with describe block containing test cases for starting build and verifying progress updates
   NEEDS: 1

6. Create package.json with Playwright dependency
   DO: Create package.json with name "orchestrator-e2e-tests", version "1.0.0", and @playwright/test as devDependency with latest stable version
   IN: none
   OUT: .orchestrator/tests/e2e/package.json
   DONE: File exists with valid JSON, contains @playwright/test in devDependencies
   NEEDS: 1

7. Add npm scripts for running tests
   DO: Modify package.json to add scripts section with "test" running playwright test, "test:headed" running playwright test --headed, and "test:debug" running playwright test --debug
   IN: .orchestrator/tests/e2e/package.json
   OUT: .orchestrator/tests/e2e/package.json (modified)
   DONE: package.json contains scripts object with test, test:headed, and test:debug commands
   NEEDS: 6

## Verify

- All files exist: playwright.config.ts, plans.spec.ts, plan-details.spec.ts, build.spec.ts, package.json
- cd .orchestrator/tests/e2e && npm install completes without errors
- npx playwright test --list shows all test cases from three spec files
