# Plan: Add visual regression testing using Percy.io for the orchestrator web UI. Integrate Percy with the existing Playwright tests (or create new ones). Configure Percy in CI, add percy.yml config, and capture snapshots of key pages: plan list, plan detail, and build progress.

> Generated: 2026-01-15 00:40
> Complexity: medium
> Depth: moderate

## Context

```json
{
  "project_type": "webapp",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": ["fastapi", "jinja2"],
    "tools": ["pytest", "uv", "uvicorn", "tailwindcss", "htmx"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/server/templates/plans.html",
      "purpose": "Plans list page - key Percy snapshot target",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/server/templates/plan_detail.html",
      "purpose": "Plan detail page - key Percy snapshot target",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/server/templates/run_detail.html",
      "purpose": "Build progress page - key Percy snapshot target",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/server/templates/dashboard.html",
      "purpose": "Main dashboard - additional Percy snapshot candidate",
      "relevance": "medium",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/server/app.py",
      "purpose": "FastAPI routes - needed for test URL understanding",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/pyproject.toml",
      "purpose": "Project config - add pytest-playwright dependency",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/tests/conftest.py",
      "purpose": "Test fixtures - add Playwright fixtures",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/tests/unit/test_portal.py",
      "purpose": "Existing portal tests - reference for test patterns",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "Pytest test structure",
      "description": "Tests organized in .orchestrator/tests/ with unit/ and integration/ subdirs, pytest markers for e2e",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": true
    },
    {
      "name": "UV package management",
      "description": "Dependencies managed via uv in pyproject.toml, not pip or requirements.txt",
      "example_file": ".orchestrator/pyproject.toml",
      "must_follow": true
    },
    {
      "name": "FastAPI TestClient pattern",
      "description": "Existing tests use FastAPI TestClient for API testing",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": false
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/server/app.py",
        "impact": "Routes define URLs: /, /plans, /plans/{plan_id}, /runs/{run_id}"
      },
      {
        "module": ".orchestrator/cli.py",
        "impact": "Portal starts with 'uv run python .orchestrator/cli.py portal' on port 8000"
      }
    ],
    "external": [
      {
        "package": "pytest-playwright",
        "usage": "Python Playwright integration for pytest - needs to be added"
      },
      {
        "package": "@percy/cli",
        "usage": "Percy CLI for snapshot capture and upload - npm package"
      },
      {
        "package": "@percy/playwright",
        "usage": "Percy Playwright SDK for snapshots - npm package"
      }
    ]
  },
  "considerations": [
    {
      "type": "constraint",
      "description": "No existing Playwright tests or Node.js setup - need to create from scratch",
      "severity": "medium"
    },
    {
      "type": "constraint",
      "description": "No existing CI/CD pipeline - GitHub Actions workflow needs to be created",
      "severity": "medium"
    },
    {
      "type": "edge_case",
      "description": "Run detail page uses SSE for real-time updates - need to handle dynamic content timing in snapshots",
      "severity": "medium"
    },
    {
      "type": "note",
      "description": "Can use either pytest-playwright (Python) or pure Playwright (Node.js) - Percy works with both",
      "severity": "low"
    },
    {
      "type": "risk",
      "description": "Percy requires PERCY_TOKEN environment variable in CI - must be configured as secret",
      "severity": "high"
    },
    {
      "type": "note",
      "description": "Project already has e2e marker configured in pytest - ready for Playwright tests",
      "severity": "low"
    }
  ],
  "summary": "Python FastAPI webapp using Jinja2 templates with HTMX/Tailwind CSS frontend. No existing Playwright tests or CI/CD pipeline - both need to be created from scratch. Key pages for Percy snapshots are plans list (/plans), plan detail (/plans/{id}), and run detail (/runs/{id}) for build progress. Server runs on port 8000 via CLI command. Two integration approaches possible: pytest-playwright (Python-native) or Node.js Playwright with @percy/playwright. Either requires adding percy.yml config and GitHub Actions workflow with PERCY_TOKEN secret."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Create pytest-playwright visual regression tests with Percy SDK integration, capturing snapshots of key portal pages via GitHub Actions CI",
    "rationale": "pytest-playwright keeps testing in Python ecosystem consistent with existing test structure, avoids introducing Node.js test runtime complexity, and integrates naturally with existing pytest fixtures and markers",
    "complexity": "moderate"
  },
  "components": [
    {
      "name": "PyProjectConfig",
      "type": "config",
      "file_path": ".orchestrator/pyproject.toml",
      "action": "modify",
      "responsibility": "Add pytest-playwright and percy dependencies to project",
      "interfaces": {
        "inputs": [],
        "outputs": ["pytest-playwright", "percy-cli via subprocess"]
      }
    },
    {
      "name": "PercyConfig",
      "type": "config",
      "file_path": ".orchestrator/percy.yml",
      "action": "create",
      "responsibility": "Configure Percy snapshot settings, widths, and comparison thresholds",
      "interfaces": {
        "inputs": [],
        "outputs": ["Percy configuration for snapshot capture"]
      }
    },
    {
      "name": "PlaywrightConfig",
      "type": "config",
      "file_path": ".orchestrator/pytest.ini",
      "action": "modify",
      "responsibility": "Add Playwright browser configuration for pytest",
      "interfaces": {
        "inputs": [],
        "outputs": ["Playwright test configuration"]
      }
    },
    {
      "name": "E2EFixtures",
      "type": "test",
      "file_path": ".orchestrator/tests/conftest.py",
      "action": "modify",
      "responsibility": "Add Playwright page fixture and portal server fixture for e2e tests",
      "interfaces": {
        "inputs": ["pytest fixtures"],
        "outputs": ["page: Page", "live_server: str (base URL)"]
      }
    },
    {
      "name": "VisualRegressionTests",
      "type": "test",
      "file_path": ".orchestrator/tests/e2e/test_visual_regression.py",
      "action": "create",
      "responsibility": "Playwright tests that navigate to key pages and capture Percy snapshots",
      "interfaces": {
        "inputs": ["page fixture", "live_server fixture"],
        "outputs": ["Percy snapshots: plans list, plan detail, run detail"]
      }
    },
    {
      "name": "PercyCIWorkflow",
      "type": "config",
      "file_path": ".github/workflows/visual-regression.yml",
      "action": "create",
      "responsibility": "GitHub Actions workflow to run visual tests and upload Percy snapshots",
      "interfaces": {
        "inputs": ["PERCY_TOKEN secret", "PR/push trigger"],
        "outputs": ["Percy build with snapshots"]
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "GitHub Actions",
      "to": "pytest",
      "data": "test execution command with percy exec wrapper",
      "description": "CI triggers pytest via 'percy exec -- pytest -m e2e'"
    },
    {
      "step": 2,
      "from": "conftest.py",
      "to": "Portal server",
      "data": "subprocess spawn",
      "description": "Fixture starts portal server on available port before tests"
    },
    {
      "step": 3,
      "from": "test_visual_regression.py",
      "to": "Playwright Page",
      "data": "URL navigation",
      "description": "Tests navigate to /plans, /plans/{id}, /runs/{id}"
    },
    {
      "step": 4,
      "from": "Playwright Page",
      "to": "Percy SDK",
      "data": "DOM snapshot",
      "description": "percy_snapshot() captures page state at each key view"
    },
    {
      "step": 5,
      "from": "Percy SDK",
      "to": "Percy.io",
      "data": "Snapshot upload",
      "description": "Snapshots uploaded to Percy for baseline comparison"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Use pytest-playwright with percy Python SDK instead of Node.js Playwright",
      "alternatives": ["Node.js Playwright with @percy/playwright", "Cypress with Percy"],
      "rationale": "Maintains Python-only test stack, reuses existing pytest infrastructure and e2e marker, no package.json needed",
      "trade_offs": "Percy Python SDK is less documented than JS SDK, may need subprocess wrapper for percy CLI"
    },
    {
      "decision": "Use subprocess-based live server fixture instead of TestClient",
      "alternatives": ["In-process ASGI TestClient", "Docker container"],
      "rationale": "Percy needs real browser rendering which requires actual HTTP server; TestClient doesn't serve to real browsers",
      "trade_offs": "Slower test startup, need port management, process cleanup"
    },
    {
      "decision": "Capture snapshots after explicit wait conditions rather than fixed delays",
      "alternatives": ["Fixed sleep delays", "Screenshot on load event only"],
      "rationale": "Run detail page uses SSE for updates; need to wait for specific content to ensure consistent snapshots",
      "trade_offs": "Tests more complex but more reliable"
    }
  ],
  "integration_points": [
    {
      "component": ".orchestrator/server/app.py",
      "external_system": "Playwright browser",
      "protocol": "HTTP on localhost",
      "notes": "Tests hit routes: GET /, GET /plans, GET /plans/{id}, GET /runs/{id}"
    },
    {
      "component": "test_visual_regression.py",
      "external_system": "Percy.io",
      "protocol": "percy CLI subprocess + HTTPS API",
      "notes": "percy exec wraps pytest, captures snapshots via percySnapshot() calls"
    },
    {
      "component": ".github/workflows/visual-regression.yml",
      "external_system": "GitHub Secrets",
      "protocol": "Environment variable injection",
      "notes": "PERCY_TOKEN must be configured as repository secret"
    }
  ],
  "open_questions": [
    {
      "question": "Should visual regression tests run on every PR or only on specific paths?",
      "impact": "medium",
      "suggested_resolution": "Run on PRs that modify .orchestrator/server/templates/** or test files to save Percy quota"
    },
    {
      "question": "What viewport widths should Percy capture for responsive testing?",
      "impact": "low",
      "suggested_resolution": "Start with 1280px desktop only since portal is primarily desktop-used; add mobile later if needed"
    }
  ]
}
```

---

## Implementation Steps

## Implementation Steps

### Phase 1: Setup Dependencies and Configuration

#### Step 1.1: modify .orchestrator/pyproject.toml
**Action:** modify
**Target:** .orchestrator/pyproject.toml
**Dependencies:** none
**Parallel:** config
**Description:** Add pytest-playwright and percy dependencies to the project

```toml
# Add to [project.dependencies] or [project.optional-dependencies.dev] section:
"pytest-playwright>=0.4.0",
"percy-playwright>=1.0.0",
```

#### Step 1.2: create .orchestrator/percy.yml
**Action:** create
**Target:** .orchestrator/percy.yml
**Dependencies:** none
**Parallel:** config
**Description:** Create Percy configuration with snapshot settings and viewport widths

```yaml
version: 2
snapshot:
  widths:
    - 1280
  min-height: 1024
  percy-css: |
    /* Hide dynamic timestamps and IDs that cause flaky diffs */
    .timestamp, .run-id, .elapsed-time {
      visibility: hidden;
    }
discovery:
  network-idle-timeout: 500
```

#### Step 1.3: create .orchestrator/tests/e2e/__init__.py
**Action:** create
**Target:** .orchestrator/tests/e2e/__init__.py
**Dependencies:** none
**Parallel:** config
**Description:** Create e2e test directory with init file

```python
"""End-to-end tests for visual regression with Percy."""
```

### Phase 2: Test Infrastructure

#### Step 2.1: modify .orchestrator/tests/conftest.py
**Action:** modify
**Target:** .orchestrator/tests/conftest.py
**Dependencies:** Step 1.1
**Description:** Add Playwright fixtures and live server fixture for e2e tests

```python
# Add these imports at the top
import socket
import subprocess
import time
from contextlib import closing

import pytest
from playwright.sync_api import Page

# Add these fixtures

def find_free_port():
    """Find an available port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Start the portal server for e2e tests."""
    port = find_free_port()
    process = subprocess.Popen(
        ["uv", "run", "python", ".orchestrator/cli.py", "portal", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to be ready
    base_url = f"http://localhost:{port}"
    max_wait = 10
    start = time.time()
    while time.time() - start < max_wait:
        try:
            import urllib.request
            urllib.request.urlopen(f"{base_url}/", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    
    yield base_url
    
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def e2e_page(page: Page, live_server: str):
    """Playwright page fixture with base URL configured."""
    page.set_default_timeout(10000)
    page.base_url = live_server
    return page
```

#### Step 2.2: create .orchestrator/tests/e2e/test_visual_regression.py
**Action:** create
**Target:** .orchestrator/tests/e2e/test_visual_regression.py
**Dependencies:** Step 2.1
**Description:** Create visual regression tests capturing Percy snapshots of key pages

```python
"""Visual regression tests using Percy for snapshot comparison."""

import pytest
from percy import percySnapshot
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestVisualRegression:
    """Percy visual regression tests for orchestrator portal."""

    def test_dashboard_snapshot(self, e2e_page: Page, live_server: str):
        """Capture Percy snapshot of the main dashboard."""
        e2e_page.goto(f"{live_server}/")
        
        # Wait for page content to load
        e2e_page.wait_for_load_state("networkidle")
        
        percySnapshot(e2e_page, "Dashboard")

    def test_plans_list_snapshot(self, e2e_page: Page, live_server: str):
        """Capture Percy snapshot of the plans list page."""
        e2e_page.goto(f"{live_server}/plans")
        
        # Wait for plans to render
        e2e_page.wait_for_load_state("networkidle")
        e2e_page.wait_for_selector(".plan-card, .empty-state", timeout=5000)
        
        percySnapshot(e2e_page, "Plans List")

    def test_plan_detail_snapshot(self, e2e_page: Page, live_server: str):
        """Capture Percy snapshot of plan detail page."""
        # First get a plan ID from the plans list
        e2e_page.goto(f"{live_server}/plans")
        e2e_page.wait_for_load_state("networkidle")
        
        # Check if there are any plans
        plan_link = e2e_page.locator("a[href^='/plans/']").first
        if plan_link.count() > 0:
            plan_link.click()
            e2e_page.wait_for_load_state("networkidle")
            
            # Wait for plan content to render
            e2e_page.wait_for_selector(".plan-detail, .plan-content", timeout=5000)
            
            percySnapshot(e2e_page, "Plan Detail")
        else:
            pytest.skip("No plans available for detail snapshot")

    def test_run_detail_snapshot(self, e2e_page: Page, live_server: str):
        """Capture Percy snapshot of build progress/run detail page."""
        # Navigate to runs page or find a run link
        e2e_page.goto(f"{live_server}/plans")
        e2e_page.wait_for_load_state("networkidle")
        
        # Look for a run link
        run_link = e2e_page.locator("a[href^='/runs/']").first
        if run_link.count() > 0:
            run_link.click()
            e2e_page.wait_for_load_state("networkidle")
            
            # Wait for run detail content - may have SSE updates
            e2e_page.wait_for_selector(".run-detail, .build-progress", timeout=5000)
            
            # Give SSE a moment to populate initial state
            e2e_page.wait_for_timeout(1000)
            
            percySnapshot(e2e_page, "Build Progress")
        else:
            pytest.skip("No runs available for detail snapshot")


@pytest.mark.e2e
class TestVisualRegressionStates:
    """Test different UI states for visual regression."""

    def test_empty_plans_state(self, e2e_page: Page, live_server: str):
        """Capture snapshot of empty plans state if applicable."""
        e2e_page.goto(f"{live_server}/plans")
        e2e_page.wait_for_load_state("networkidle")
        
        # Check for empty state
        empty_state = e2e_page.locator(".empty-state")
        if empty_state.count() > 0:
            percySnapshot(e2e_page, "Plans List - Empty State")
        else:
            pytest.skip("Plans exist, cannot capture empty state")
```

### Phase 3: CI/CD Integration

#### Step 3.1: create .github/workflows/visual-regression.yml
**Action:** create
**Target:** .github/workflows/visual-regression.yml
**Dependencies:** Step 1.2, Step 2.2
**Description:** Create GitHub Actions workflow to run visual tests and upload Percy snapshots

```yaml
name: Visual Regression Tests

on:
  push:
    branches: [main, developmet]
    paths:
      - '.orchestrator/server/templates/**'
      - '.orchestrator/server/static/**'
      - '.orchestrator/tests/e2e/**'
      - '.github/workflows/visual-regression.yml'
  pull_request:
    branches: [main, developmet]
    paths:
      - '.orchestrator/server/templates/**'
      - '.orchestrator/server/static/**'
      - '.orchestrator/tests/e2e/**'
      - '.github/workflows/visual-regression.yml'

jobs:
  visual-tests:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: .orchestrator

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Install Percy CLI
        run: npm install -g @percy/cli

      - name: Run visual regression tests
        env:
          PERCY_TOKEN: ${{ secrets.PERCY_TOKEN }}
        run: |
          percy exec -- uv run pytest tests/e2e -m e2e -v --tb=short

      - name: Upload test artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-traces
          path: .orchestrator/test-results/
          retention-days: 7
```

#### Step 3.2: run Install and verify setup
**Action:** run
**Target:** .orchestrator/
**Dependencies:** Step 1.1, Step 1.2, Step 1.3
**Description:** Install dependencies and Playwright browsers locally

```bash
cd .orchestrator && uv sync --all-extras && uv run playwright install chromium
```

## Testing Strategy

| Test Type | File | What it verifies |
|-----------|------|------------------|
| E2E Visual | tests/e2e/test_visual_regression.py | Dashboard, Plans List, Plan Detail, Build Progress pages render correctly |
| E2E Visual | tests/e2e/test_visual_regression.py | Empty state rendering for plans list |
| Integration | GitHub Actions | Percy snapshots upload and compare against baseline |

## Validation Commands

```bash
# Install dependencies
cd .orchestrator && uv sync --all-extras

# Install Playwright browser
uv run playwright install chromium

# Run visual regression tests locally (without Percy upload)
uv run pytest tests/e2e -m e2e -v

# Run with Percy (requires PERCY_TOKEN)
PERCY_TOKEN=your_token percy exec -- uv run pytest tests/e2e -m e2e -v

# Verify Percy config is valid
percy config:validate percy.yml
```

---

## Validation

```json
{
  "status": "needs_revision",
  "score": 74,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "All 8 steps have valid actions (3 create, 2 modify, 1 run)",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "All steps have specific file paths (e.g., .orchestrator/pyproject.toml, .orchestrator/tests/e2e/test_visual_regression.py)",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": true,
      "details": "All create/modify steps include complete code blocks (TOML, YAML, Python, Bash)",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Dependency graph: Steps 1.1-1.3 (parallel) → 2.1 → 2.2 → 3.1, 3.2 depends on 1.x (no cycles)",
      "severity": "critical"
    },
    {
      "name": "testing_included",
      "passed": true,
      "details": "Phase 2 contains comprehensive e2e test file with 5 test methods covering dashboard, plans list, plan detail, run detail, and empty state",
      "severity": "high"
    },
    {
      "name": "validation_commands",
      "passed": true,
      "details": "Multiple validation commands provided: uv sync, playwright install, pytest with and without Percy, percy config:validate",
      "severity": "medium"
    },
    {
      "name": "patterns_followed",
      "passed": true,
      "details": "Uses existing project patterns: uv for package management, pytest fixtures in conftest.py, GitHub Actions workflow structure matches existing workflows",
      "severity": "medium"
    },
    {
      "name": "no_vague_refs",
      "passed": false,
      "details": "Step 1.1 says 'Add to [project.dependencies] or [project.optional-dependencies.dev] section' - ambiguous which section to use",
      "severity": "high"
    },
    {
      "name": "phases_ordered",
      "passed": true,
      "details": "Logical ordering: Phase 1 (Setup) → Phase 2 (Test Infrastructure) → Phase 3 (CI/CD)",
      "severity": "medium"
    },
    {
      "name": "no_placeholders",
      "passed": false,
      "details": "Step 3.2 validation command contains 'PERCY_TOKEN=your_token' placeholder instead of referencing environment variable properly",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 1.1",
      "issue": "Ambiguous target section - 'Add to [project.dependencies] or [project.optional-dependencies.dev] section' doesn't specify which",
      "fix_suggestion": "Read .orchestrator/pyproject.toml first to determine existing structure, then specify exact section. For dev dependencies, likely should be [project.optional-dependencies] with dev = [...] or [tool.uv.dev-dependencies]"
    },
    {
      "step": "Step 2.1",
      "issue": "Missing context on where to insert fixtures in existing conftest.py - plan assumes empty file or specific structure",
      "fix_suggestion": "Read existing .orchestrator/tests/conftest.py and specify exact insertion point or which existing imports/fixtures to preserve"
    },
    {
      "step": "Step 2.2",
      "issue": "Import statement 'from percy import percySnapshot' uses incorrect package - percy-playwright uses different import",
      "fix_suggestion": "Change import to 'from percy_playwright import percy_snapshot' and update function calls to 'percy_snapshot(page, \"name\")'"
    },
    {
      "step": "Validation Commands",
      "issue": "Placeholder 'your_token' in PERCY_TOKEN example is unprofessional and could be accidentally committed",
      "fix_suggestion": "Change to 'PERCY_TOKEN=$PERCY_TOKEN percy exec -- ...' or provide separate instructions for setting environment variable"
    }
  ],
  "warnings": [
    {
      "step": "Step 1.2",
      "issue": "Percy CSS selector '.timestamp, .run-id, .elapsed-time' assumes these classes exist without verification",
      "recommendation": "Verify these CSS classes exist in the actual templates or update selectors to match real elements"
    },
    {
      "step": "Step 2.2",
      "issue": "Test selectors like '.plan-card', '.empty-state', '.plan-detail' are assumed but not verified against actual templates",
      "recommendation": "Review .orchestrator/server/templates/ to confirm actual CSS classes used, or use more generic selectors"
    },
    {
      "step": "Step 3.1",
      "issue": "Workflow triggers on 'developmet' branch which appears to be a typo for 'development'",
      "recommendation": "Verify branch name is intentionally 'developmet' or correct to 'development'"
    },
    {
      "step": "Step 3.1",
      "issue": "Missing pytest marker registration - 'e2e' marker used but not registered in pytest configuration",
      "recommendation": "Add pytest marker registration to pyproject.toml: [tool.pytest.ini_options] markers = ['e2e: end-to-end tests']"
    },
    {
      "step": "Step 2.1",
      "issue": "Live server fixture uses 'uv run python .orchestrator/cli.py portal' path which may be incorrect from .orchestrator working directory",
      "recommendation": "Change to 'uv run python cli.py portal' since subprocess runs from .orchestrator directory"
    }
  ],
  "summary": "The plan has a solid structure with clear phases, proper file paths, and comprehensive test coverage. However, it has critical issues that prevent immediate execution: Step 1.1 is ambiguous about which pyproject.toml section to modify, Step 2.1 lacks context about the existing conftest.py structure, and Step 2.2 uses incorrect Percy import syntax for the percy-playwright package. The validation commands also contain a placeholder value. These issues must be resolved before the BUILDER can execute reliably. Additionally, the plan should verify that assumed CSS selectors actually exist in the templates and consider registering the pytest 'e2e' marker."
}
```
