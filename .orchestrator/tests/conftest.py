"""Pytest fixtures for orchestrator tests.

This module provides fixtures that enable testing without a real database
by using dependency injection overrides.
"""
import pytest
from typing import Dict, List, Optional
from fastapi.testclient import TestClient


# ============== Mock Repositories ==============


class MockPlanRepository:
    """Mock plan repository for testing."""

    def __init__(self):
        self.plans: Dict[str, Dict] = {}
        self._next_id = 1

    def get_by_id(self, plan_id: str) -> Optional[Dict]:
        return self.plans.get(plan_id)

    def list_all(self) -> List[Dict]:
        return list(self.plans.values())

    def list_by_status(self, status: str) -> List[Dict]:
        return [p for p in self.plans.values() if p.get("status") == status]

    def create(self, plan_id: str, **kwargs) -> int:
        self.plans[plan_id] = {
            "plan_id": plan_id,
            "status": kwargs.get("status", "pending"),
            "raw_content": kwargs.get("raw_content", ""),
            "request": kwargs.get("request", ""),
            "goal": kwargs.get("goal", ""),
            **kwargs,
        }
        self._next_id += 1
        return self._next_id - 1

    def update_status(self, plan_id: str, status: str) -> None:
        if plan_id in self.plans:
            self.plans[plan_id]["status"] = status

    def delete(self, plan_id: str) -> None:
        if plan_id in self.plans:
            del self.plans[plan_id]

    def get_next_plan_number(self) -> int:
        return self._next_id


class MockBuildStateRepository:
    """Mock build state repository for testing."""

    def __init__(self):
        self.states: Dict[str, Dict] = {}
        self.step_states: Dict[str, List[Dict]] = {}

    def get(self, plan_id: str) -> Optional[Dict]:
        return self.states.get(plan_id)

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        self.states[plan_id] = {
            "plan_id": plan_id,
            "status": "pending",
            "total_steps": total_steps,
            "completed_steps": [],
            "failed_steps": [],
            "files_created": [],
            "files_modified": [],
        }
        self.step_states[plan_id] = []
        return 1

    def update(self, plan_id: str, **kwargs) -> None:
        if plan_id in self.states:
            self.states[plan_id].update(kwargs)

    def get_step_states(self, plan_id: str) -> List[Dict]:
        return self.step_states.get(plan_id, [])

    def set_step_state(self, plan_id: str, step_id: str, **kwargs) -> None:
        if plan_id not in self.step_states:
            self.step_states[plan_id] = []

        # Update existing or add new
        for state in self.step_states[plan_id]:
            if state.get("step_id") == step_id:
                state.update(kwargs)
                return

        self.step_states[plan_id].append({"step_id": step_id, **kwargs})


class MockRunRepository:
    """Mock run repository for testing."""

    def __init__(self):
        self.runs: Dict[str, Dict] = {}
        self.events: Dict[str, List[Dict]] = {}

    def get(self, run_id: str) -> Optional[Dict]:
        return self.runs.get(run_id)

    def list_active(self, status: str = None) -> List[Dict]:
        runs = list(self.runs.values())
        if status:
            runs = [r for r in runs if r.get("status") == status]
        return runs

    def create(self, run_id: str, workflow: str, **kwargs) -> None:
        self.runs[run_id] = {
            "run_id": run_id,
            "workflow": workflow,
            "status": "pending",
            **kwargs,
        }
        self.events[run_id] = []

    def update(self, run_id: str, **kwargs) -> None:
        if run_id in self.runs:
            self.runs[run_id].update(kwargs)

    def add_event(self, run_id: str, event_type: str, data: Dict = None) -> None:
        if run_id not in self.events:
            self.events[run_id] = []
        self.events[run_id].append({
            "id": len(self.events[run_id]) + 1,
            "event_type": event_type,
            "data": data or {},
        })

    def get_events(self, run_id: str, since_id: int = 0) -> List[Dict]:
        events = self.events.get(run_id, [])
        return [e for e in events if e.get("id", 0) > since_id]


# ============== Fixtures ==============


@pytest.fixture
def mock_plan_repo():
    """Create a mock plan repository."""
    return MockPlanRepository()


@pytest.fixture
def mock_build_state_repo():
    """Create a mock build state repository."""
    return MockBuildStateRepository()


@pytest.fixture
def mock_run_repo():
    """Create a mock run repository."""
    return MockRunRepository()


@pytest.fixture
def test_client(mock_plan_repo, mock_build_state_repo, mock_run_repo):
    """Create a test client with mocked dependencies.

    This fixture overrides the dependency injection to use mock
    repositories instead of the real database.
    """
    import sys
    from pathlib import Path

    # Add orchestrator to path
    orchestrator_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(orchestrator_dir))

    from portal.app import app
    from portal.dependencies import get_plan_repo, get_build_state_repo, get_run_repo

    # Override dependencies
    app.dependency_overrides[get_plan_repo] = lambda: mock_plan_repo
    app.dependency_overrides[get_build_state_repo] = lambda: mock_build_state_repo
    app.dependency_overrides[get_run_repo] = lambda: mock_run_repo

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_plan(mock_plan_repo):
    """Create a sample plan in the mock repository."""
    mock_plan_repo.create(
        plan_id="001_test_plan",
        status="pending",
        raw_content="# Plan: Test Plan\n\nRequest: Test request\n\nComplexity: low",
        request="Test request",
        goal="Test goal",
    )
    return "001_test_plan"


@pytest.fixture
def sample_run(mock_run_repo):
    """Create a sample run in the mock repository."""
    mock_run_repo.create(
        run_id="test123",
        workflow="planning",
        status="running",
    )
    return "test123"
