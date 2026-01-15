"""
Pytest fixtures for E2E tests.

Provides:
- live_server: Starts/stops uvicorn server for E2E tests
- base_url: Base URL configuration for test server
- test_plan_data: Test plan data setup/teardown
- browser_context: Playwright browser context configuration
"""
import pytest
import subprocess
import time
import os
import shutil
import socket
from pathlib import Path
from typing import Generator

# Orchestrator directory paths
TESTS_DIR = Path(__file__).parent
E2E_DIR = TESTS_DIR
ORCHESTRATOR_DIR = TESTS_DIR.parent.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the test server."""
    return "http://127.0.0.1:8000"


def _wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    """Wait for server to be ready by checking if port is accepting connections."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def _is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


@pytest.fixture(scope="session")
def live_server(base_url: str) -> Generator[subprocess.Popen | None, None, None]:
    """
    Start the uvicorn server for E2E tests.

    This fixture:
    - Starts the FastAPI server using uvicorn
    - Waits for the server to be ready
    - Yields the server process
    - Terminates the server on cleanup
    - If server is already running, uses existing server (yields None)
    """
    host = "127.0.0.1"
    port = 8000

    # Check if server is already running (e.g., for debugging)
    if _is_port_in_use(host, port):
        # Server already running, use existing server
        yield None
        return

    # Start the server process
    server_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "server.app:app", "--host", host, "--port", str(port)],
        cwd=ORCHESTRATOR_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    # Wait for server to be ready
    if not _wait_for_server(host, port, timeout=15.0):
        # Server failed to start, capture output for debugging
        server_process.terminate()
        try:
            stdout, stderr = server_process.communicate(timeout=5)
            error_msg = f"Server failed to start.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        except subprocess.TimeoutExpired:
            server_process.kill()
            error_msg = "Server failed to start and did not terminate cleanly"
        pytest.fail(error_msg)

    yield server_process

    # Cleanup: terminate the server
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
        server_process.wait()


@pytest.fixture(scope="function")
def test_plan_data(tmp_path: Path) -> Generator[dict, None, None]:
    """
    Create test plan data for E2E tests.

    Sets up a temporary specs directory structure with sample plans
    that can be used for testing the web UI.

    Returns dict with:
    - specs_dir: Path to the temporary specs directory
    - pending_plan: Path to a sample pending plan
    - completed_plan: Path to a sample completed plan
    """
    # Create specs directory structure
    specs_dir = tmp_path / "specs"
    for state in ["pending", "in-progress", "completed", "failed", "reviews", "fixes"]:
        (specs_dir / state).mkdir(parents=True, exist_ok=True)

    # Create a sample pending plan
    pending_plan_dir = specs_dir / "pending" / "001_test-feature"
    pending_plan_dir.mkdir(parents=True, exist_ok=True)

    plan_content = """# Test Feature Plan

Request: Create a test feature for E2E testing
Complexity: simple

## Goal

Create a simple test feature for E2E testing.

## Context

- E2E test fixture
- Simple complexity

## Steps

1. Create test file
   DO: Create `src/test.py` with test function
   IN: none
   OUT: src/test.py
   DONE: File exists with test function
   NEEDS: none

2. Add tests
   DO: Create tests for the test function
   IN: src/test.py
   OUT: tests/test_feature.py
   DONE: pytest passes
   NEEDS: 1

## Verify

- Run: pytest tests/
"""
    (pending_plan_dir / "plan.md").write_text(plan_content, encoding="utf-8")

    # Create a sample completed plan
    completed_plan_dir = specs_dir / "completed" / "002_completed-feature"
    completed_plan_dir.mkdir(parents=True, exist_ok=True)

    completed_plan_content = """# Plan: Completed Feature

Request: A feature that has been completed
Complexity: medium

## Goal

Complete a feature for E2E testing.

## Context

- E2E test fixture
- Completed status

## Steps

1. Implementation complete
   DO: All code has been implemented
   IN: none
   OUT: src/completed.py
   DONE: All tests pass
   NEEDS: none

## Verify

- All tests pass
"""
    (completed_plan_dir / "plan.md").write_text(completed_plan_content, encoding="utf-8")

    yield {
        "specs_dir": specs_dir,
        "pending_plan": pending_plan_dir,
        "completed_plan": completed_plan_dir,
        "tmp_path": tmp_path,
    }

    # Cleanup is automatic with tmp_path


@pytest.fixture(scope="function")
def clean_specs_dir() -> Generator[Path, None, None]:
    """
    Provide access to real specs directory with cleanup tracking.

    This fixture allows tests to use the real specs directory but tracks
    any files created during the test for potential cleanup.

    Warning: Use with caution as this modifies real project data.
    """
    specs_dir = ORCHESTRATOR_DIR / "specs"

    # Track files before test
    files_before = set()
    for state_dir in specs_dir.iterdir():
        if state_dir.is_dir():
            for item in state_dir.iterdir():
                files_before.add(item)

    yield specs_dir

    # Track files after test (for reporting, not automatic cleanup)
    files_after = set()
    for state_dir in specs_dir.iterdir():
        if state_dir.is_dir():
            for item in state_dir.iterdir():
                files_after.add(item)

    new_files = files_after - files_before
    if new_files:
        # Log new files created during test (don't auto-delete real data)
        print(f"\nNote: Test created {len(new_files)} new items in specs directory")


@pytest.fixture(scope="session")
def browser_context_args() -> dict:
    """
    Configure Playwright browser context settings for E2E tests.

    Returns configuration dict for browser context including:
    - viewport size
    - timeout settings
    - locale
    """
    return {
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-US",
        "timezone_id": "UTC",
    }


@pytest.fixture(scope="function")
def authenticated_page(page, base_url):
    """
    Provide a page that has completed any necessary authentication.

    Currently the app has no authentication, so this just navigates
    to the base URL and waits for the page to load.
    """
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    return page


# Playwright-specific fixtures

@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    """Configure browser launch arguments."""
    return {
        "headless": True,
        "slow_mo": 0,  # Set to 100+ for debugging to see actions
    }
