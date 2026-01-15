# Plan: Add Playwright E2E tests for the orchestrator web UI. (1) Create .orchestrator/tests/e2e/ directory 

Request: Add Playwright E2E tests for the orchestrator web UI. (1) Create .orchestrator/tests/e2e/ directory structure. (2) Add playwright.config.ts with baseURL pointing to localhost:8000, screenshot on failure, and proper timeout settings. (3) Create tests/e2e/plans.spec.ts testing: view plan list page, verify plan items display, click on a plan to view details. (4) Create tests/e2e/plan-details.spec.ts testing: view plan detail page, verify metadata displays, verify steps are listed. (5) Create tests/e2e/build.spec.ts testing: start a build from plan detail page, verify build progress updates. (6) Add package.json with @playwright/test dependency. (7) Add npm scripts for running e2e tests.
Complexity: medium

## Goal

Add complete Playwright E2E testing infrastructure for the orchestrator web UI with tests covering plan listing, plan details, and build flows.

## Context

- Backend runs on localhost:8000 (FastAPI), frontend serves through it or port 5173
- Existing test structure at .orchestrator/tests/unit/ - E2E goes in .orchestrator/tests/e2e/
- No existing E2E infrastructure - greenfield Playwright setup
- Web UI has plan list page and plan detail page with build functionality
- Tests need seeded data or API fixtures for reliable assertions

## Steps

1. Create E2E test directory structure
   DO: Create the .orchestrator/tests/e2e/ directory for E2E test files
   IN: none
   OUT: .orchestrator/tests/e2e/ directory
   DONE: Directory exists
   NEEDS: none

## Verify

- cd .orchestrator && npm run test:e2e -- --list shows all test files discovered
- cd .orchestrator && npx playwright test --reporter=list executes without syntax/import errors
- .orchestrator/playwright.config.ts contains baseURL, screenshot, and timeout settings
