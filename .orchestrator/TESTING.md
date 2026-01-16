# Testing Guide

Comprehensive testing documentation for the SDLC Orchestrator.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Unit Tests](#unit-tests)
- [E2E Tests](#e2e-tests)
- [Visual Regression Tests](#visual-regression-tests)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Overview

The orchestrator uses a multi-layered testing strategy:

| Layer | Framework | Location | Purpose |
|-------|-----------|----------|---------|
| Unit | pytest | `tests/unit/` | Core logic, services, utilities |
| Integration | pytest | `tests/integration/` | Component interaction |
| E2E | Playwright | `tests/e2e/` | Web portal workflows |
| Visual | Percy + Playwright | `tests/e2e/visual/` | UI regression detection |

## Test Structure

```
tests/
├── unit/                       # Python unit tests
│   ├── conftest.py             # pytest fixtures
│   ├── test_agent.py           # Agent execution tests
│   ├── test_config.py          # Configuration tests
│   ├── test_cost.py            # Cost tracking tests
│   ├── test_portal.py          # FastAPI endpoint tests
│   ├── test_system_explorer.py # Tech detection tests
│   └── test_css_classes.py     # CSS validation tests
│
├── integration/                # Integration tests
│   └── ...
│
├── fixtures/                   # Shared test data
│   └── sample_plans/           # Sample plan files
│
└── e2e/                        # Playwright E2E tests
    ├── package.json            # Node.js dependencies
    ├── playwright.config.ts    # Playwright configuration
    ├── percy.yml               # Percy visual testing config
    │
    ├── fixtures/               # Playwright fixtures
    │   ├── test-fixtures.ts    # Custom fixtures (APIClient, etc.)
    │   ├── mock-errors.ts      # Error simulation helpers
    │   └── index.ts            # Shared exports
    │
    ├── utils/                  # Test utilities
    │   ├── navigation.helpers.ts   # Navigation utilities
    │   ├── accessibility.helpers.ts # Axe-core helpers
    │   └── index.ts            # Utility exports
    │
    ├── visual/                 # Visual regression tests
    │   └── snapshots.spec.ts   # Percy snapshot tests
    │
    ├── workflows/              # Workflow-specific tests
    │   ├── plan-lifecycle.spec.ts
    │   ├── expert-management.spec.ts
    │   └── cost-tracking.spec.ts
    │
    ├── docs/                   # E2E documentation
    │   └── PERCY_SETUP.md      # Percy setup guide
    │
    ├── plans.spec.ts           # Plan listing tests
    ├── plan-details.spec.ts    # Plan detail tests
    ├── build.spec.ts           # Build workflow tests
    ├── navigation.spec.ts      # Navigation tests
    ├── accessibility.spec.ts   # A11y tests
    └── error-handling.spec.ts  # Error scenario tests
```

## Unit Tests

### Running Unit Tests

```bash
cd .orchestrator

# Run all unit tests
uv run pytest tests/unit -v

# Run with short traceback
uv run pytest tests/unit -v --tb=short

# Run specific test file
uv run pytest tests/unit/test_agent.py -v

# Run specific test class
uv run pytest tests/unit/test_agent.py::TestAgentExecution -v

# Run specific test method
uv run pytest tests/unit/test_agent.py::TestAgentExecution::test_run_print_mode_success -v

# Run tests matching pattern
uv run pytest tests/unit -k "cost" -v

# Run with coverage
uv run pytest tests/unit --cov=core --cov=server --cov-report=html

# Run in parallel
uv run pytest tests/unit -n auto
```

### Test Modules

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_agent.py` | Agent loading, execution, retries, error handling | `core/agent.py` |
| `test_config.py` | Config loading, validation, defaults | `core/config.py` |
| `test_cost.py` | Cost estimation, budget tracking, reporting | `core/cost.py` |
| `test_portal.py` | FastAPI endpoints, workflows, authentication | `server/app.py` |
| `test_system_explorer.py` | Technology detection, expert matching | `core/system_explorer.py` |
| `test_css_classes.py` | Template CSS class validation | `server/templates/` |

### Writing Unit Tests

```python
# tests/unit/test_example.py
import pytest
from core.my_module import MyClass

class TestMyClass:
    """Tests for MyClass."""

    def test_basic_functionality(self):
        """Test basic operation."""
        obj = MyClass()
        result = obj.do_something("input")
        assert result == "expected"

    def test_with_fixture(self, tmp_path):
        """Test using pytest fixtures."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": "value"}')
        obj = MyClass(config_path=config_file)
        assert obj.get_key() == "value"

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async methods."""
        obj = MyClass()
        result = await obj.async_method()
        assert result is not None

    @pytest.mark.parametrize("input,expected", [
        ("a", 1),
        ("b", 2),
        ("c", 3),
    ])
    def test_parametrized(self, input, expected):
        """Test with multiple inputs."""
        obj = MyClass()
        assert obj.process(input) == expected
```

## E2E Tests

### Setup

```bash
cd tests/e2e

# Install dependencies
npm install

# Install Playwright browsers
npx playwright install

# Verify installation
npx playwright --version
```

### Running E2E Tests

```bash
# Run all tests
npm test

# Run in headed mode (visible browser)
npm run test:headed

# Run with Playwright UI
npm run test:ui

# Run specific test file
npx playwright test plans.spec.ts

# Run specific test
npx playwright test -g "should display plan list"

# Run tests for specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit

# Debug mode
npm run test:debug

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report
```

### Test Files

| File | Description |
|------|-------------|
| `plans.spec.ts` | Plan listing, filtering, pagination |
| `plan-details.spec.ts` | Plan detail view, content display |
| `build.spec.ts` | Build workflow, progress tracking |
| `navigation.spec.ts` | Navigation links, routing |
| `accessibility.spec.ts` | WCAG compliance, keyboard nav |
| `error-handling.spec.ts` | Error states, API failures |
| `cost-tracking.spec.ts` | Cost estimates, budget display |
| `plan-lifecycle.spec.ts` | Full plan→build→review cycle |
| `expert-management.spec.ts` | Expert listing, creation |

### Writing E2E Tests

```typescript
// tests/e2e/example.spec.ts
import { test, expect } from './fixtures';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should do something', async ({ page }) => {
    // Navigate
    await page.click('[data-testid="some-button"]');

    // Wait for network
    await page.waitForLoadState('networkidle');

    // Assert
    await expect(page.locator('h1')).toHaveText('Expected Title');
  });

  test('should handle API response', async ({ page, apiClient }) => {
    // Use custom fixture
    const plans = await apiClient.getPlans();
    expect(plans.length).toBeGreaterThan(0);
  });

  test('should skip if feature unavailable', async ({ page }) => {
    const response = await page.request.get('/api/feature');
    if (response.status() === 404) {
      test.skip(true, 'Feature not implemented');
      return;
    }
    // Continue with test...
  });
});
```

### Custom Fixtures

```typescript
// tests/e2e/fixtures/test-fixtures.ts
import { test as base } from '@playwright/test';

// Extend base test with custom fixtures
export const test = base.extend<{
  apiClient: APIClient;
  testPlan: Plan | null;
}>({
  apiClient: async ({ page }, use) => {
    const client = new APIClient(page);
    await use(client);
  },

  testPlan: async ({ apiClient }, use) => {
    const { plans } = await apiClient.getPlans();
    await use(plans[0] || null);
  },
});
```

## Visual Regression Tests

### Percy Setup

1. **Create Percy Account**: Sign up at [percy.io](https://percy.io)
2. **Get Token**: Project Settings → Project Token
3. **Set Environment Variable**:

```bash
# Linux/macOS
export PERCY_TOKEN="your_token_here"

# Windows PowerShell
$env:PERCY_TOKEN="your_token_here"

# Windows CMD
set PERCY_TOKEN=your_token_here
```

### Running Visual Tests

```bash
cd tests/e2e

# Run with Percy upload
npm run test:visual

# Run locally without Percy
npx playwright test visual/

# Disable Percy temporarily
PERCY_ENABLE=0 npm run test:visual
```

### Configuration

**percy.yml:**
```yaml
version: 2
snapshot:
  widths:
    - 1280  # Desktop
    - 768   # Tablet
    - 375   # Mobile
  min-height: 1024
  percy-css: |
    [data-percy-hide] { visibility: hidden !important; }
```

### Writing Visual Tests

```typescript
// tests/e2e/visual/snapshots.spec.ts
import { test } from '@playwright/test';
import { percySnapshot } from '@percy/playwright';

test.describe('Visual Snapshots', () => {
  test('home page', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await percySnapshot(page, 'Home Page');
  });

  test('plans page', async ({ page }) => {
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');
    await percySnapshot(page, 'Plans Page');
  });
});
```

See `tests/e2e/docs/PERCY_SETUP.md` for detailed setup instructions.

## Running Tests

### All Tests

```bash
cd .orchestrator

# Run everything
uv run pytest tests/unit -v && cd tests/e2e && npm test && cd ../..

# Or use the CLI
uv run cli.py test
```

### Quick Commands Reference

| Test Type | Command |
|-----------|---------|
| All unit tests | `uv run pytest tests/unit -v` |
| Specific unit test | `uv run pytest tests/unit/test_agent.py -v` |
| With coverage | `uv run pytest tests/unit --cov=core` |
| All E2E tests | `cd tests/e2e && npm test` |
| E2E headed | `cd tests/e2e && npm run test:headed` |
| E2E UI mode | `cd tests/e2e && npm run test:ui` |
| Specific E2E | `npx playwright test plans.spec.ts` |
| Visual tests | `npm run test:visual` |
| Debug E2E | `npm run test:debug` |

## CI/CD Integration

### GitHub Actions Workflows

**Unit Tests** (`.github/workflows/test.yml`):
- Runs on every push and PR
- Python 3.11+ matrix
- pytest with coverage

**E2E Tests** (`.github/workflows/e2e.yml`):
- Runs on PR to main branches
- Starts server, runs Playwright
- Uploads test artifacts on failure

**Visual Tests** (`.github/workflows/visual-regression.yml`):
- Runs on PR
- Requires `PERCY_TOKEN` secret
- Percy comments on PR with diff links

### Adding Secrets

1. Go to Repository → Settings → Secrets
2. Add `PERCY_TOKEN` for visual tests
3. Add any other required secrets

## Troubleshooting

### Unit Tests

**Import errors:**
```bash
# Ensure you're in the right directory
cd .orchestrator
uv run pytest tests/unit -v
```

**Async test failures:**
```bash
# Ensure pytest-asyncio is installed
uv add pytest-asyncio
```

### E2E Tests

**Browser not found:**
```bash
npx playwright install
```

**Timeout errors:**
```typescript
// Increase timeout for slow operations
test.setTimeout(60000);
await page.waitForLoadState('networkidle', { timeout: 30000 });
```

**Server not running:**
```bash
# Start server before E2E tests
uv run cli.py portal &
cd tests/e2e && npm test
```

### Visual Tests

**Percy token not set:**
```
Error: PERCY_TOKEN was not provided.
```
Solution: Set `PERCY_TOKEN` environment variable.

**Flaky snapshots:**
- Add `data-percy-hide` to dynamic elements
- Wait for fonts and images to load
- Use `page.waitForLoadState('networkidle')`

### Getting Help

1. Check test output for specific error messages
2. Run with `--debug` flag for more details
3. Check CI logs for environment-specific issues
4. Review Playwright trace files in `test-results/`
