# Plan: Create comprehensive E2E test suite in .orchestrator/tests/e2e/. (1) Create e2e/fixtures/ with test 

Request: Create comprehensive E2E test suite in .orchestrator/tests/e2e/. (1) Create e2e/fixtures/ with test data setup and teardown helpers. (2) Create e2e/workflows/plan-lifecycle.spec.ts testing full plan create-build-review cycle. (3) Create e2e/workflows/expert-management.spec.ts testing expert listing and creation. (4) Create e2e/workflows/cost-tracking.spec.ts testing cost estimation display. (5) Create e2e/error-handling.spec.ts testing error states: invalid plan, failed build, network errors. (6) Create e2e/navigation.spec.ts testing all navigation links and breadcrumbs. (7) Create e2e/accessibility.spec.ts with basic a11y checks using @axe-core/playwright. (8) Add shared test utilities in e2e/utils/. (9) Ensure proper test isolation and cleanup between tests.
Complexity: complex

## Goal

Create comprehensive E2E test suite with fixtures, workflow tests, error handling, navigation, accessibility checks, and shared utilities.

## Context

- Existing E2E patterns in test_plan_flows.py use pytest-playwright sync API with live_server fixture
- Routes: `/` (dashboard), `/plans`, `/plan/{id}`, `/runs`, `/run/{id}`
- Cost API routes exist at /api/cost/* (estimate, summary, report, budget)
- Expert management has NO server routes - only ExpertLoader in core module (integration tests)
- Need function-scoped isolation to avoid state conflicts with session-scoped fixtures
- Python package is `axe-playwright-python` for accessibility testing

## Steps

1. Add axe-playwright-python dependency
   DO: Add `axe-playwright-python` to dev dependencies section in pyproject.toml
   IN: .orchestrator/pyproject.toml
   OUT: .orchestrator/pyproject.toml (modified)
   DONE: `pip install -e ".[dev]"` succeeds and `from axe_playwright_python import Axe` works
   NEEDS: none

## Verify

- pip install -e ".[dev]" completes without errors (axe-playwright-python installed)
- python -c "from orchestrator.tests.e2e.fixtures import create_plan; print(create_plan())" outputs valid dict
- python -c "from orchestrator.tests.e2e.utils import assert_element_visible, isolated_directory" imports without error
- pytest .orchestrator/tests/e2e/ --collect-only shows 30+ tests across all files
- pytest .orchestrator/tests/e2e/test_infrastructure.py -v passes (validates fixtures work)
- pytest .orchestrator/tests/e2e/workflows/ --collect-only shows tests in plan_lifecycle, cost_tracking, expert_management
- pytest .orchestrator/tests/e2e/test_error_handling.py -v passes (skipped tests marked)
- pytest .orchestrator/tests/e2e/test_navigation.py -v passes
- pytest .orchestrator/tests/e2e/test_accessibility.py -v runs all 5 route tests
- pytest .orchestrator/tests/e2e/ -v runs complete suite without import or isolation conflicts
