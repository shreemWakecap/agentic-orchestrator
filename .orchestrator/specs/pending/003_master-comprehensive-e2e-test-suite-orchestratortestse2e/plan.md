# Plan: Create comprehensive E2E test suite in .orchestrator/tests/e2e/. (1) Create e2e/fixtures/ with test 

Request: Create comprehensive E2E test suite in .orchestrator/tests/e2e/. (1) Create e2e/fixtures/ with test data setup and teardown helpers. (2) Create e2e/workflows/plan-lifecycle.spec.ts testing full plan create-build-review cycle. (3) Create e2e/workflows/expert-management.spec.ts testing expert listing and creation. (4) Create e2e/workflows/cost-tracking.spec.ts testing cost estimation display. (5) Create e2e/error-handling.spec.ts testing error states: invalid plan, failed build, network errors. (6) Create e2e/navigation.spec.ts testing all navigation links and breadcrumbs. (7) Create e2e/accessibility.spec.ts with basic a11y checks using @axe-core/playwright. (8) Add shared test utilities in e2e/utils/. (9) Ensure proper test isolation and cleanup between tests.
Complexity: complex

## Goal

Create comprehensive E2E test suite with shared infrastructure, workflow specs, error handling, navigation, and accessibility tests.

## Context

- Playwright tests in .orchestrator/tests/e2e/ using test.describe() pattern
- API routes in app.py: POST /api/workflows/{plan|build|review|fix}, GET /api/cost/{estimate|summary|budget}
- UI uses Tailwind classes for errors: text-red-600, bg-red-100, .error
- baseURL http://localhost:8000 configured in playwright.config.ts
- @axe-core/playwright needed for WCAG 2.1 AA accessibility testing
- Existing tests in plans.spec.ts, plan-details.spec.ts, build.spec.ts provide patterns

## Steps

1. Create fixtures and utils directory structure
   DO: Create empty directories for fixtures and utils under e2e/
   IN: none
   OUT: .orchestrator/tests/e2e/fixtures/, .orchestrator/tests/e2e/utils/
   DONE: Directories exist
   NEEDS: none

2. Add @axe-core/playwright dependency
   DO: Add @axe-core/playwright to devDependencies in package.json
   IN: package.json
   OUT: package.json (modified)
   DONE: npm install completes without errors
   NEEDS: none

3. Verify expert endpoints in app.py
   DO: Read app.py to confirm exact expert-related routes (GET /experts, POST /api/experts or similar)
   IN: .orchestrator/server/app.py
   OUT: Confirmed endpoint paths for expert listing and creation
   DONE: Have exact route signatures for expert endpoints
   NEEDS: none

4. Read existing test patterns
   DO: Review plans.spec.ts and build.spec.ts to extract exact import statements, describe block structure, and assertion patterns
   IN: .orchestrator/tests/e2e/plans.spec.ts, .orchestrator/tests/e2e/build.spec.ts
   OUT: Reference patterns for imports, navigation, API calls, and assertions
   DONE: Have copy-ready patterns for test structure
   NEEDS: none

5. Create selector constants module
   DO: Extract all CSS selectors from existing specs into named constants object with categories (navigation, plansList, planDetails, build, common)
   IN: .orchestrator/tests/e2e/plans.spec.ts, .orchestrator/tests/e2e/plan-details.spec.ts, .orchestrator/tests/e2e/build.spec.ts
   OUT: .orchestrator/tests/e2e/utils/selectors.ts
   DONE: File exports SELECTORS object with all extracted selectors, TypeScript compiles without errors
   NEEDS: 1, 4

6. Create wait helpers module
   DO: Create utility functions for common wait patterns: waitForNetworkIdle(page), waitForSelector(page, selector), waitForNavigation(page, url), waitForTableData(page, selector)
   IN: none
   OUT: .orchestrator/tests/e2e/utils/wait-helpers.ts
   DONE: File exports typed async functions, TypeScript compiles without errors
   NEEDS: 1

7. Create API client class
   DO: Create typed APIClient class with methods: getPlans(), getPlan(id), getRuns(), getRun(id), getWorkflows(), triggerWorkflow(name). Use Playwright's request context for HTTP calls.
   IN: none
   OUT: .orchestrator/tests/e2e/fixtures/api-client.ts
   DONE: Class exports with typed request/response interfaces, TypeScript compiles
   NEEDS: 1

8. Create mock errors fixture file
   DO: Create reusable route interception helpers with functions for: mockApiError(page, urlPattern, statusCode, message), mockNetworkFailure(page, urlPattern), mockTimeout(page, urlPattern, delayMs)
   IN: none
   OUT: .orchestrator/tests/e2e/fixtures/mock-errors.ts
   DONE: File exists with exported helper functions, valid TypeScript syntax
   NEEDS: 1

9. Create test fixtures with extended test object
   DO: Use test.extend() to create custom test with fixtures: apiClient (APIClient instance), testPlan (fetches first available plan), ensureTestData (setup hook that verifies data exists). Include beforeEach/afterEach hooks for isolation.
   IN: .orchestrator/tests/e2e/fixtures/api-client.ts
   OUT: .orchestrator/tests/e2e/fixtures/test-fixtures.ts
   DONE: Exports extended `test` and `expect` objects, TypeScript compiles
   NEEDS: 7

10. Create barrel export file
    DO: Create index.ts that re-exports test/expect from test-fixtures, APIClient from api-client, SELECTORS from selectors, mock helpers from mock-errors, and all wait helpers
    IN: .orchestrator/tests/e2e/fixtures/test-fixtures.ts, .orchestrator/tests/e2e/fixtures/api-client.ts, .orchestrator/tests/e2e/utils/selectors.ts, .orchestrator/tests/e2e/utils/wait-helpers.ts, .orchestrator/tests/e2e/fixtures/mock-errors.ts
    OUT: .orchestrator/tests/e2e/fixtures/index.ts
    DONE: Single import path works: `import { test, SELECTORS, waitForNetworkIdle, mockApiError } from './fixtures'`
    NEEDS: 5, 6, 8, 9

11. Migrate plans.spec.ts as reference example
    DO: Refactor plans.spec.ts to import from fixtures/index.ts, replace hardcoded selectors with SELECTORS constants, replace inline waits with wait helpers, use apiClient fixture for data verification
    IN: .orchestrator/tests/e2e/plans.spec.ts, .orchestrator/tests/e2e/fixtures/index.ts
    OUT: .orchestrator/tests/e2e/plans.spec.ts (modified)
    DONE: Test file uses shared infrastructure, all existing tests still pass
    NEEDS: 10

12. Create plan-lifecycle.spec.ts with full test suite
    DO: Create test file with imports and describe block "Plan Lifecycle Workflow" containing three tests: "should create new plan via workflow API" (POST /api/workflows/plan), "should trigger build for created plan" (POST /api/workflows/build), "should complete review cycle" (POST /api/workflows/review)
    IN: Pattern from step 4
    OUT: .orchestrator/tests/e2e/plan-lifecycle.spec.ts
    DONE: File has 3 tests in describe block, TypeScript compiles
    NEEDS: 4, 10

13. Create expert-management.spec.ts with full test suite
    DO: Create test file with imports and describe block "Expert Management Workflow" containing two tests: "should display expert list" (GET /experts), "should create new expert" (POST expert endpoint). Include test.skip() fallback if endpoints unavailable.
    IN: Pattern from step 4, endpoints from step 3
    OUT: .orchestrator/tests/e2e/expert-management.spec.ts
    DONE: File has 2 tests in describe block, TypeScript compiles
    NEEDS: 3, 4, 10

14. Create cost-tracking.spec.ts with full test suite
    DO: Create test file with imports and describe block "Cost Tracking Workflow" containing three tests: "should display cost estimate for workflow" (GET /api/cost/estimate/{workflow}), "should show cost summary view" (GET /api/cost/summary), "should display budget information" (GET /api/cost/budget)
    IN: Pattern from step 4
    OUT: .orchestrator/tests/e2e/cost-tracking.spec.ts
    DONE: File has 3 tests in describe block, TypeScript compiles
    NEEDS: 4, 10

15. Create error handling test file structure
    DO: Create test file with test.describe() blocks for four categories: 'API Error Responses', 'Network Failures', 'Invalid Submissions', 'Error Recovery'. Import mock helpers from fixtures.
    IN: .orchestrator/tests/e2e/fixtures/mock-errors.ts
    OUT: .orchestrator/tests/e2e/error-handling.spec.ts
    DONE: File imports correctly, npx playwright test error-handling.spec.ts --list shows test structure
    NEEDS: 10

16. Add invalid submission and API error tests
    DO: In 'Invalid Submissions' block add tests for empty plan name, missing required fields, invalid characters. In 'API Error Responses' block add tests intercepting POST /api/plans/* and POST /api/workflows/build with 400/500 status codes using mockApiError helper.
    IN: .orchestrator/tests/e2e/error-handling.spec.ts, .orchestrator/tests/e2e/fixtures/mock-errors.ts
    OUT: .orchestrator/tests/e2e/error-handling.spec.ts (modified)
    DONE: Tests for invalid submissions (3+) and API errors (3+) exist
    NEEDS: 15

17. Add network failure and timeout tests
    DO: In 'Network Failures' block add tests using mockNetworkFailure for network down during submit, during page load, and intermittent failure. Add tests using mockTimeout for extended delays verifying loading state and timeout error.
    IN: .orchestrator/tests/e2e/error-handling.spec.ts, .orchestrator/tests/e2e/fixtures/mock-errors.ts
    OUT: .orchestrator/tests/e2e/error-handling.spec.ts (modified)
    DONE: Network failure tests (3+) and timeout tests (1+) exist
    NEEDS: 16

18. Add error recovery tests
    DO: In 'Error Recovery' block add tests verifying: clicking retry button re-submits request, successful retry clears error state, form preserves user input after error
    IN: .orchestrator/tests/e2e/error-handling.spec.ts
    OUT: .orchestrator/tests/e2e/error-handling.spec.ts (modified)
    DONE: Recovery tests (3+) verify retry functionality and state preservation
    NEEDS: 17

19. Create navigation test file with nav bar tests
    DO: Create navigation.spec.ts with Playwright imports, test.describe block 'Navigation', beforeEach hook navigating to dashboard. Add test block 'Top Navigation Bar' with tests for clicking Dashboard, Plans, Runs links verifying URL changes.
    IN: plans.spec.ts (reference for import/setup pattern)
    OUT: .orchestrator/tests/e2e/navigation.spec.ts
    DONE: File exists with top nav tests (3 links), TypeScript compiles
    NEEDS: 4, 10

20. Add sidebar and list-to-detail navigation tests
    DO: Add test block 'Sidebar Navigation' testing sidebar links. Add tests for dashboard→plans, dashboard→runs, plans list→plan detail (with regex URL matcher), runs list→run detail transitions.
    IN: .orchestrator/tests/e2e/navigation.spec.ts
    OUT: .orchestrator/tests/e2e/navigation.spec.ts (modified)
    DONE: Sidebar tests and list-to-detail transition tests exist
    NEEDS: 19

21. Add breadcrumb navigation tests
    DO: Add test block 'Breadcrumb Navigation' with tests for plan detail breadcrumbs (Dashboard→/, Plans→/plans) and run detail breadcrumbs (Dashboard→/, Runs→/runs)
    IN: .orchestrator/tests/e2e/navigation.spec.ts
    OUT: .orchestrator/tests/e2e/navigation.spec.ts (modified)
    DONE: Breadcrumb tests verify clicking each segment navigates correctly (4 tests)
    NEEDS: 20

22. Add active state and browser history tests
    DO: Add test block 'Active Navigation State' verifying active CSS class on correct nav item per route. Add test for browser back button navigation (dashboard→plans→detail→back→back). Add full navigation flow integration test.
    IN: .orchestrator/tests/e2e/navigation.spec.ts
    OUT: .orchestrator/tests/e2e/navigation.spec.ts (modified)
    DONE: Active state tests, back button test, and integration test exist
    NEEDS: 21

23. Create accessibility test file with setup
    DO: Create accessibility.spec.ts with imports for @playwright/test and AxeBuilder from @axe-core/playwright, configure test.describe block for accessibility suite, add helper function for violation reporting
    IN: none
    OUT: .orchestrator/tests/e2e/accessibility.spec.ts
    DONE: File exists with valid TypeScript syntax and imports
    NEEDS: 2, 10

24. Add accessibility tests for all views
    DO: Add test cases for all five routes: dashboard (/), plans list (/plans), plan detail (/plans/{id}), runs list (/runs), run detail (/runs/{id}). Each test navigates, waits for networkidle, runs AxeBuilder with wcag21aa tag, asserts violations empty using helper for error formatting.
    IN: .orchestrator/tests/e2e/accessibility.spec.ts
    OUT: .orchestrator/tests/e2e/accessibility.spec.ts (modified)
    DONE: File has 5 test cases covering all major routes
    NEEDS: 23

25. Run TypeScript compilation check
    DO: Run tsc or npx playwright test --list to verify all specs have valid syntax
    IN: All new spec files
    OUT: Compilation success or error list
    DONE: No TypeScript compilation errors
    NEEDS: 11, 12, 13, 14, 18, 22, 24

26. Run full test suite validation
    DO: Execute npx playwright test --project=chromium to verify all tests pass or skip gracefully
    IN: .orchestrator/tests/e2e/*.spec.ts
    OUT: Test execution results
    DONE: All tests pass or show expected skips, no infrastructure errors
    NEEDS: 25

## Verify

- npm install completes with @axe-core/playwright in node_modules
- Import `{ test, SELECTORS, waitForNetworkIdle, APIClient, mockApiError }` from fixtures/index.ts resolves correctly
- npx playwright test --list shows all test suites: plans, plan-lifecycle (3), expert-management (2), cost-tracking (3), error-handling (10+), navigation (15+), accessibility (5)
- npx playwright test --project=chromium runs without infrastructure errors
- plans.spec.ts passes using new shared infrastructure
- All workflow specs pass: npx playwright test plan-lifecycle expert-management cost-tracking
- Error handling tests cover: invalid submissions, API errors, build failures, network failures, timeout, recovery
- Navigation tests cover: top nav, sidebar, list-to-detail, breadcrumbs, active state, back button, full flow
- Accessibility tests run without import/syntax errors for all 5 views
