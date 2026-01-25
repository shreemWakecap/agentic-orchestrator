"""Test utilities module with helper functions for creating test data and common assertions.

This module provides reusable helper functions and mock factories that can be used
across different test modules to reduce code duplication and maintain consistency.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


# ============================================================================
# Mock Data Factories
# ============================================================================


def create_mock_plan(
    plan_id: Optional[str] = None,
    status: str = "pending",
    raw_content: Optional[str] = None,
    request: str = "Test request",
    goal: str = "Test goal",
    complexity: str = "low",
    **kwargs
) -> Dict[str, Any]:
    """Create a mock plan dictionary for testing.

    Args:
        plan_id: Optional plan ID. If not provided, generates one.
        status: Plan status (pending, approved, building, completed, failed).
        raw_content: Raw markdown content. If not provided, generates default.
        request: The original user request.
        goal: The plan goal.
        complexity: Plan complexity (low, medium, high).
        **kwargs: Additional fields to include in the plan.

    Returns:
        Dictionary representing a mock plan.

    Example:
        >>> plan = create_mock_plan(status="approved")
        >>> assert plan["status"] == "approved"
    """
    if plan_id is None:
        plan_number = kwargs.pop("plan_number", 1)
        plan_id = f"{plan_number:03d}_test_plan"

    if raw_content is None:
        raw_content = f"""# Plan: Test Plan

Request: {request}

Goal: {goal}

Complexity: {complexity}

## Implementation Steps

1. Step one
2. Step two
3. Step three
"""

    return {
        "plan_id": plan_id,
        "status": status,
        "raw_content": raw_content,
        "request": request,
        "goal": goal,
        "complexity": complexity,
        "created_at": datetime.utcnow().isoformat(),
        **kwargs,
    }


def create_mock_run(
    run_id: Optional[str] = None,
    workflow: str = "planning",
    status: str = "pending",
    plan_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a mock run dictionary for testing.

    Args:
        run_id: Optional run ID. If not provided, generates a UUID.
        workflow: Workflow type (planning, building, etc.).
        status: Run status (pending, running, completed, failed).
        plan_id: Associated plan ID.
        **kwargs: Additional fields to include in the run.

    Returns:
        Dictionary representing a mock run.

    Example:
        >>> run = create_mock_run(workflow="building", status="running")
        >>> assert run["workflow"] == "building"
    """
    if run_id is None:
        run_id = uuid.uuid4().hex[:8]

    return {
        "run_id": run_id,
        "workflow": workflow,
        "status": status,
        "plan_id": plan_id,
        "started_at": datetime.utcnow().isoformat() if status != "pending" else None,
        "completed_at": None,
        "error_message": None,
        **kwargs,
    }


def create_mock_job(
    job_id: Optional[str] = None,
    job_type: str = "plan",
    status: str = "pending",
    parameters: Optional[Dict[str, Any]] = None,
    priority: int = 5,
    **kwargs
) -> Dict[str, Any]:
    """Create a mock job dictionary for testing.

    Args:
        job_id: Optional job ID. If not provided, generates a UUID.
        job_type: Job type (plan, build, etc.).
        status: Job status (pending, queued, running, succeeded, failed).
        parameters: Job parameters dictionary.
        priority: Job priority (1-10, lower is higher priority).
        **kwargs: Additional fields to include in the job.

    Returns:
        Dictionary representing a mock job.

    Example:
        >>> job = create_mock_job(job_type="build", priority=1)
        >>> assert job["priority"] == 1
    """
    if job_id is None:
        job_id = uuid.uuid4().hex

    if parameters is None:
        parameters = {"spec_id": "test-001"}

    return {
        "id": job_id,
        "job_type": job_type,
        "status": status,
        "parameters": parameters,
        "priority": priority,
        "created_at": datetime.utcnow().isoformat(),
        "queued_at": None,
        "started_at": None,
        "completed_at": None,
        "exit_code": None,
        "error_message": None,
        "retry_count": 0,
        "max_retries": 3,
        **kwargs,
    }


def create_mock_build_state(
    plan_id: str,
    status: str = "pending",
    total_steps: int = 3,
    completed_steps: Optional[List[str]] = None,
    failed_steps: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a mock build state dictionary for testing.

    Args:
        plan_id: The associated plan ID.
        status: Build status (pending, running, completed, failed).
        total_steps: Total number of steps in the build.
        completed_steps: List of completed step IDs.
        failed_steps: List of failed step IDs.
        **kwargs: Additional fields to include.

    Returns:
        Dictionary representing a mock build state.

    Example:
        >>> state = create_mock_build_state("001_test", total_steps=5)
        >>> assert state["total_steps"] == 5
    """
    return {
        "plan_id": plan_id,
        "status": status,
        "total_steps": total_steps,
        "completed_steps": completed_steps or [],
        "failed_steps": failed_steps or [],
        "files_created": [],
        "files_modified": [],
        "current_step": None,
        **kwargs,
    }


def create_mock_event(
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
    event_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a mock event dictionary for testing.

    Args:
        event_type: Type of event (start, progress, complete, error, etc.).
        data: Event data payload.
        event_id: Optional event ID.
        timestamp: Optional timestamp. Defaults to current time.
        **kwargs: Additional fields to include.

    Returns:
        Dictionary representing a mock event.

    Example:
        >>> event = create_mock_event("progress", {"percent": 50})
        >>> assert event["data"]["percent"] == 50
    """
    return {
        "id": event_id or 1,
        "event_type": event_type,
        "data": data or {},
        "timestamp": timestamp or datetime.utcnow().isoformat(),
        **kwargs,
    }


# ============================================================================
# Assertion Helpers
# ============================================================================


def assert_valid_response(
    response,
    expected_status: int = 200,
    expected_keys: Optional[List[str]] = None,
    expected_values: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assert that an HTTP response is valid and contains expected data.

    Args:
        response: The HTTP response object (from TestClient or httpx).
        expected_status: Expected HTTP status code. Defaults to 200.
        expected_keys: List of keys that must be present in the response JSON.
        expected_values: Dict of key-value pairs that must match in response.

    Returns:
        The response JSON data for further assertions.

    Raises:
        AssertionError: If any assertion fails.

    Example:
        >>> data = assert_valid_response(response, 201, ["id", "status"])
        >>> assert data["id"] is not None
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response: {response.text}"
    )

    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Response is not valid JSON: {response.text}") from e

    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Expected key '{key}' not found in response: {data}"

    if expected_values:
        for key, value in expected_values.items():
            assert key in data, f"Expected key '{key}' not found in response: {data}"
            assert data[key] == value, (
                f"Expected {key}={value}, got {key}={data[key]}"
            )

    return data


def assert_error_response(
    response,
    expected_status: int,
    expected_detail: Optional[str] = None,
    detail_contains: Optional[str] = None,
) -> Dict[str, Any]:
    """Assert that an HTTP response is an error with expected details.

    Args:
        response: The HTTP response object.
        expected_status: Expected HTTP error status code (4xx or 5xx).
        expected_detail: Exact error detail message expected.
        detail_contains: Substring that should be in the error detail.

    Returns:
        The response JSON data for further assertions.

    Raises:
        AssertionError: If any assertion fails.

    Example:
        >>> assert_error_response(response, 404, detail_contains="not found")
    """
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}. "
        f"Response: {response.text}"
    )

    try:
        data = response.json()
    except Exception:
        raise AssertionError(f"Error response is not valid JSON: {response.text}")

    if expected_detail is not None:
        assert data.get("detail") == expected_detail, (
            f"Expected detail '{expected_detail}', got '{data.get('detail')}'"
        )

    if detail_contains is not None:
        detail = data.get("detail", "")
        assert detail_contains in detail, (
            f"Expected detail to contain '{detail_contains}', got '{detail}'"
        )

    return data


def assert_list_response(
    response,
    min_items: int = 0,
    max_items: Optional[int] = None,
    item_keys: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Assert that an HTTP response contains a valid list.

    Args:
        response: The HTTP response object.
        min_items: Minimum number of items expected.
        max_items: Maximum number of items expected.
        item_keys: Keys that each item in the list must have.

    Returns:
        The list of items from the response.

    Raises:
        AssertionError: If any assertion fails.

    Example:
        >>> items = assert_list_response(response, min_items=1, item_keys=["id"])
    """
    assert response.status_code == 200, (
        f"Expected status 200, got {response.status_code}. Response: {response.text}"
    )

    data = response.json()

    # Handle both direct lists and paginated responses
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, dict) and "data" in data:
        items = data["data"]
    else:
        raise AssertionError(f"Response is not a list or paginated response: {data}")

    assert len(items) >= min_items, (
        f"Expected at least {min_items} items, got {len(items)}"
    )

    if max_items is not None:
        assert len(items) <= max_items, (
            f"Expected at most {max_items} items, got {len(items)}"
        )

    if item_keys:
        for i, item in enumerate(items):
            for key in item_keys:
                assert key in item, (
                    f"Expected key '{key}' not found in item {i}: {item}"
                )

    return items


# ============================================================================
# Test Data Generators
# ============================================================================


def generate_plan_content(
    request: str,
    goal: str,
    steps: Optional[List[str]] = None,
    complexity: str = "low",
) -> str:
    """Generate plan markdown content for testing.

    Args:
        request: The original user request.
        goal: The plan goal.
        steps: List of implementation step descriptions.
        complexity: Plan complexity (low, medium, high).

    Returns:
        Formatted plan markdown content.

    Example:
        >>> content = generate_plan_content("Add login", "Users can authenticate")
        >>> assert "Add login" in content
    """
    if steps is None:
        steps = ["Step one", "Step two", "Step three"]

    steps_content = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))

    return f"""# Plan: {goal[:50]}

Request: {request}

Goal: {goal}

Complexity: {complexity}

## Implementation Steps

{steps_content}
"""


def generate_jsonl_output(events: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Generate JSONL output lines for testing CLI output parsing.

    Args:
        events: List of event dictionaries. If not provided, generates default.

    Returns:
        List of JSONL-formatted strings.

    Example:
        >>> lines = generate_jsonl_output()
        >>> assert len(lines) > 0
    """
    import json

    if events is None:
        events = [
            {"type": "start", "phase": "init", "ts": datetime.utcnow().isoformat()},
            {"type": "progress", "phase": "analyzing", "percent": 25},
            {"type": "progress", "phase": "generating", "percent": 75},
            {"type": "complete", "exit_code": 0, "result": {}},
        ]

    return [json.dumps(event) for event in events]
