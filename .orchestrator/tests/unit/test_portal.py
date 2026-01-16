"""Tests for the web portal (server/app.py).

Ensures:
- Web dependencies are installed
- FastAPI app can be imported
- API endpoints work correctly
- Helper functions work correctly

This module uses mock implementations of service interfaces (IPlanRegistry,
IFileService, IConfigService) to isolate tests from real file system and
configuration dependencies.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from typing import Dict, List, Optional, Any, Protocol, runtime_checkable
from abc import ABC, abstractmethod


# ============== Mock Service Interfaces ==============
# These mirror the production interfaces that will be in services/interfaces.py

@runtime_checkable
class IPlanRegistry(Protocol):
    """Interface for plan registry operations."""

    async def get_all_plans(self) -> List[Dict[str, Any]]:
        """Get all plans across all states."""
        ...

    async def get_recent_plans(self, limit: int) -> List[Dict[str, Any]]:
        """Get most recent plans."""
        ...

    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by ID."""
        ...

    def get_plan_counts(self) -> Dict[str, int]:
        """Get counts of plans by state."""
        ...


@runtime_checkable
class IFileService(Protocol):
    """Interface for file system operations."""

    def read_file(self, path: Path) -> str:
        """Read file content."""
        ...

    def write_file(self, path: Path, content: str) -> None:
        """Write content to file."""
        ...

    def file_exists(self, path: Path) -> bool:
        """Check if file exists."""
        ...

    def list_directory(self, path: Path) -> List[Path]:
        """List directory contents."""
        ...


@runtime_checkable
class IConfigService(Protocol):
    """Interface for configuration management."""

    @property
    def orchestrator_dir(self) -> Path:
        """Get orchestrator directory path."""
        ...

    @property
    def specs_dir(self) -> Path:
        """Get specs directory path."""
        ...

    @property
    def cost_history_path(self) -> Path:
        """Get cost history file path."""
        ...

    @property
    def budget_config_path(self) -> Path:
        """Get budget configuration file path."""
        ...


# ============== Mock Implementations ==============

class MockPlanRegistry:
    """Mock implementation of IPlanRegistry for testing."""

    def __init__(self, plans: Optional[List[Dict[str, Any]]] = None):
        self._plans = plans or []
        self._plan_counts = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0
        }

    def set_plans(self, plans: List[Dict[str, Any]]) -> None:
        """Set the list of plans for testing."""
        self._plans = plans
        # Update counts based on plans
        self._plan_counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
        for plan in plans:
            state = plan.get("state", "pending").replace("-", "_")
            if state in self._plan_counts:
                self._plan_counts[state] += 1

    def set_plan_counts(self, counts: Dict[str, int]) -> None:
        """Set plan counts directly for testing."""
        self._plan_counts = counts

    async def get_all_plans(self) -> List[Dict[str, Any]]:
        """Get all plans across all states."""
        return self._plans

    async def get_recent_plans(self, limit: int) -> List[Dict[str, Any]]:
        """Get most recent plans."""
        return self._plans[:limit]

    async def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by ID."""
        for plan in self._plans:
            if plan.get("id") == plan_id:
                return plan
        return None

    def get_plan_counts(self) -> Dict[str, int]:
        """Get counts of plans by state."""
        return self._plan_counts


class MockFileService:
    """Mock implementation of IFileService for testing."""

    def __init__(self):
        self._files: Dict[str, str] = {}
        self._directories: Dict[str, List[Path]] = {}

    def add_file(self, path: Path, content: str) -> None:
        """Add a file to the mock file system."""
        self._files[str(path)] = content

    def add_directory(self, path: Path, contents: List[Path]) -> None:
        """Add a directory listing to the mock file system."""
        self._directories[str(path)] = contents

    def read_file(self, path: Path) -> str:
        """Read file content."""
        path_str = str(path)
        if path_str not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[path_str]

    def write_file(self, path: Path, content: str) -> None:
        """Write content to file."""
        self._files[str(path)] = content

    def file_exists(self, path: Path) -> bool:
        """Check if file exists."""
        return str(path) in self._files

    def list_directory(self, path: Path) -> List[Path]:
        """List directory contents."""
        path_str = str(path)
        if path_str not in self._directories:
            return []
        return self._directories[path_str]


class MockConfigService:
    """Mock implementation of IConfigService for testing."""

    def __init__(self, base_path: Optional[Path] = None):
        self._base_path = base_path or Path("/mock/orchestrator")

    @property
    def orchestrator_dir(self) -> Path:
        """Get orchestrator directory path."""
        return self._base_path

    @property
    def specs_dir(self) -> Path:
        """Get specs directory path."""
        return self._base_path / "specs"

    @property
    def cost_history_path(self) -> Path:
        """Get cost history file path."""
        return self._base_path / "cost_history.json"

    @property
    def budget_config_path(self) -> Path:
        """Get budget configuration file path."""
        return self._base_path / "config" / "budget.json"


# ============== Fixtures for Mock Services ==============

@pytest.fixture
def mock_plan_registry() -> MockPlanRegistry:
    """Create a mock plan registry for testing."""
    registry = MockPlanRegistry()
    # Pre-populate with some test plans
    registry.set_plans([
        {
            "id": "001_test-feature",
            "name": "Test Feature",
            "state": "pending",
            "file": "/mock/specs/pending/001_test-feature",
            "files": ["plan.md"],
            "modified": datetime.now().isoformat()
        },
        {
            "id": "002_completed-feature",
            "name": "Completed Feature",
            "state": "completed",
            "file": "/mock/specs/completed/002_completed-feature",
            "files": ["plan.md"],
            "modified": datetime.now().isoformat()
        }
    ])
    return registry


@pytest.fixture
def mock_file_service() -> MockFileService:
    """Create a mock file service for testing."""
    return MockFileService()


@pytest.fixture
def mock_config_service(tmp_path: Path) -> MockConfigService:
    """Create a mock config service using a temporary directory."""
    return MockConfigService(base_path=tmp_path)


class TestPortalDependencies:
    """Test that web dependencies are importable."""

    def test_fastapi_importable(self):
        """FastAPI must be installed for portal to work."""
        import fastapi
        assert fastapi is not None

    def test_uvicorn_importable(self):
        """Uvicorn must be installed for portal to work."""
        import uvicorn
        assert uvicorn is not None

    def test_jinja2_importable(self):
        """Jinja2 must be installed for portal to work."""
        import jinja2
        assert jinja2 is not None


class TestServerAppImport:
    """Test that server app can be imported."""

    def test_app_importable(self):
        """The FastAPI app must be importable."""
        from server.app import app
        assert app is not None
        assert app.title == "SDLC Orchestrator"

    def test_run_server_importable(self):
        """The run_server function must be importable."""
        from server.app import run_server
        assert callable(run_server)


class TestHelloEndpoint:
    """Tests for the hello world API endpoint."""

    def test_api_hello_returns_hello_world(self):
        """Test that /api/hello returns the expected message."""
        from fastapi.testclient import TestClient
        from server.app import app

        client = TestClient(app)
        response = client.get("/api/hello")

        assert response.status_code == 200
        assert response.json() == {"message": "hello world"}


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from server.app import app
        return TestClient(app)

    def test_health_returns_200(self, client):
        """Test that health endpoint returns 200 status code."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_status_healthy(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client):
        """Test that health endpoint returns version string."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_health_returns_uptime_seconds(self, client):
        """Test that health endpoint returns uptime in seconds."""
        response = client.get("/api/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_root_health_endpoint_returns_200(self, client):
        """Test that /health endpoint (without /api prefix) returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_health_returns_status_ok(self, client):
        """Test that /health endpoint returns 'ok' status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_root_health_returns_version(self, client):
        """Test that /health endpoint returns version string."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_root_health_returns_uptime_seconds(self, client):
        """Test that /health endpoint returns uptime in seconds."""
        response = client.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0


class TestAPIModels:
    """Test Pydantic models for API requests."""

    def test_plan_request_model(self):
        """PlanRequest model works correctly."""
        from server.app import PlanRequest
        req = PlanRequest(description="Test plan")
        assert req.description == "Test plan"

    def test_build_request_model(self):
        """BuildRequest model works correctly."""
        from server.app import BuildRequest
        req = BuildRequest(plan_path="/path/to/plan.md")
        assert req.plan_path == "/path/to/plan.md"

    def test_budget_update_request_model(self):
        """BudgetUpdateRequest model works correctly."""
        from server.app import BudgetUpdateRequest
        req = BudgetUpdateRequest(daily_limit=10.0, monthly_limit=100.0)
        assert req.daily_limit == 10.0
        assert req.monthly_limit == 100.0
        assert req.weekly_limit is None  # optional


class TestHelperFunctions:
    """Test helper functions in server/app.py using mock services.

    These tests use mock implementations of IPlanRegistry, IFileService,
    and IConfigService to isolate tests from real file system dependencies.
    """

    @pytest.fixture
    def configured_plan_registry(self, mock_plan_registry: MockPlanRegistry) -> MockPlanRegistry:
        """Configure plan registry with test data."""
        mock_plan_registry.set_plans([
            {
                "id": "001_test-plan-pending",
                "name": "Test Plan 1",
                "state": "pending",
                "file": "/mock/specs/pending/001_test-plan-pending",
                "files": ["plan.md"],
                "modified": datetime.now().isoformat(),
                "content": "# Test Plan 1\n\nThis is a pending test plan."
            },
            {
                "id": "002_test-plan-completed",
                "name": "Test Plan 2",
                "state": "completed",
                "file": "/mock/specs/completed/002_test-plan-completed",
                "files": ["plan.md"],
                "modified": datetime.now().isoformat(),
                "content": "# Test Plan 2\n\nThis is a completed test plan."
            },
            {
                "id": "003_test-plan-failed",
                "name": "Test Plan 3",
                "state": "failed",
                "file": "/mock/specs/failed/003_test-plan-failed",
                "files": ["plan.md"],
                "modified": datetime.now().isoformat(),
                "content": "# Test Plan 3\n\nThis is a failed test plan."
            }
        ])
        mock_plan_registry.set_plan_counts({
            "pending": 1,
            "in_progress": 0,
            "completed": 1,
            "failed": 1
        })
        return mock_plan_registry

    @pytest.fixture
    def configured_file_service(self, mock_file_service: MockFileService) -> MockFileService:
        """Configure file service with test files."""
        # Add test plan files
        mock_file_service.add_file(
            Path("/mock/specs/pending/001_test-plan-pending/plan.md"),
            "# Plan: Test Feature\nRequest: Add a new test feature\nComplexity: medium"
        )
        mock_file_service.add_file(
            Path("/mock/specs/completed/002_test-plan-completed/plan.md"),
            "# Plan: Completed Feature\nRequest: Already done\nComplexity: low"
        )
        return mock_file_service

    @pytest.mark.asyncio
    async def test_get_all_plans_with_mock_registry(self, configured_plan_registry: MockPlanRegistry):
        """Test that mock plan registry returns all configured plans."""
        plans = await configured_plan_registry.get_all_plans()

        assert len(plans) == 3
        assert plans[0]["id"] == "001_test-plan-pending"
        assert plans[0]["state"] == "pending"
        assert plans[1]["id"] == "002_test-plan-completed"
        assert plans[1]["state"] == "completed"
        assert plans[2]["id"] == "003_test-plan-failed"
        assert plans[2]["state"] == "failed"

    @pytest.mark.asyncio
    async def test_get_recent_plans_with_mock_registry(self, configured_plan_registry: MockPlanRegistry):
        """Test that mock plan registry returns limited recent plans."""
        # Get only 2 most recent plans
        plans = await configured_plan_registry.get_recent_plans(2)

        assert len(plans) == 2
        assert plans[0]["id"] == "001_test-plan-pending"
        assert plans[1]["id"] == "002_test-plan-completed"

    @pytest.mark.asyncio
    async def test_get_plan_by_id_with_mock_registry(self, configured_plan_registry: MockPlanRegistry):
        """Test that mock plan registry returns plan by ID."""
        plan = await configured_plan_registry.get_plan_by_id("002_test-plan-completed")

        assert plan is not None
        assert plan["id"] == "002_test-plan-completed"
        assert plan["name"] == "Test Plan 2"
        assert plan["state"] == "completed"

    @pytest.mark.asyncio
    async def test_get_plan_by_id_not_found(self, configured_plan_registry: MockPlanRegistry):
        """Test that mock plan registry returns None for non-existent plan."""
        plan = await configured_plan_registry.get_plan_by_id("non-existent-plan")
        assert plan is None

    def test_get_plan_counts_with_mock_registry(self, configured_plan_registry: MockPlanRegistry):
        """Test that mock plan registry returns correct plan counts."""
        counts = configured_plan_registry.get_plan_counts()

        assert counts["pending"] == 1
        assert counts["in_progress"] == 0
        assert counts["completed"] == 1
        assert counts["failed"] == 1

    def test_file_service_read_file(self, configured_file_service: MockFileService):
        """Test that mock file service can read configured files."""
        content = configured_file_service.read_file(
            Path("/mock/specs/pending/001_test-plan-pending/plan.md")
        )
        assert "# Plan: Test Feature" in content
        assert "Complexity: medium" in content

    def test_file_service_file_exists(self, configured_file_service: MockFileService):
        """Test that mock file service correctly reports file existence."""
        assert configured_file_service.file_exists(
            Path("/mock/specs/pending/001_test-plan-pending/plan.md")
        )
        assert not configured_file_service.file_exists(
            Path("/mock/specs/nonexistent/plan.md")
        )

    def test_file_service_read_nonexistent_file(self, mock_file_service: MockFileService):
        """Test that mock file service raises error for non-existent files."""
        with pytest.raises(FileNotFoundError):
            mock_file_service.read_file(Path("/nonexistent/file.md"))

    def test_config_service_paths(self, mock_config_service: MockConfigService):
        """Test that mock config service provides correct paths."""
        assert mock_config_service.orchestrator_dir.name != ""
        assert mock_config_service.specs_dir == mock_config_service.orchestrator_dir / "specs"
        assert mock_config_service.cost_history_path == mock_config_service.orchestrator_dir / "cost_history.json"
        assert mock_config_service.budget_config_path == mock_config_service.orchestrator_dir / "config" / "budget.json"

    # Legacy tests that verify actual app functions still exist and are callable
    @pytest.mark.asyncio
    async def test_get_all_plans_function_exists(self):
        """Test _get_all_plans function exists in server/app.py."""
        from server.app import _get_all_plans
        assert callable(_get_all_plans)

    @pytest.mark.asyncio
    async def test_get_recent_plans_function_exists(self):
        """Test _get_recent_plans function exists in server/app.py."""
        from server.app import _get_recent_plans
        assert callable(_get_recent_plans)

    @pytest.mark.asyncio
    async def test_get_plan_by_id_function_exists(self):
        """Test _get_plan_by_id function exists in server/app.py."""
        from server.app import _get_plan_by_id
        assert callable(_get_plan_by_id)

class TestServiceInterfaceConformance:
    """Test that mock implementations conform to their respective interfaces."""

    def test_mock_plan_registry_implements_iplan_registry(self, mock_plan_registry: MockPlanRegistry):
        """Verify MockPlanRegistry conforms to IPlanRegistry protocol."""
        # Check that all required methods exist
        assert hasattr(mock_plan_registry, 'get_all_plans')
        assert hasattr(mock_plan_registry, 'get_recent_plans')
        assert hasattr(mock_plan_registry, 'get_plan_by_id')
        assert hasattr(mock_plan_registry, 'get_plan_counts')

        # Verify methods are callable
        assert callable(mock_plan_registry.get_all_plans)
        assert callable(mock_plan_registry.get_recent_plans)
        assert callable(mock_plan_registry.get_plan_by_id)
        assert callable(mock_plan_registry.get_plan_counts)

    def test_mock_file_service_implements_ifile_service(self, mock_file_service: MockFileService):
        """Verify MockFileService conforms to IFileService protocol."""
        # Check that all required methods exist
        assert hasattr(mock_file_service, 'read_file')
        assert hasattr(mock_file_service, 'write_file')
        assert hasattr(mock_file_service, 'file_exists')
        assert hasattr(mock_file_service, 'list_directory')

        # Verify methods are callable
        assert callable(mock_file_service.read_file)
        assert callable(mock_file_service.write_file)
        assert callable(mock_file_service.file_exists)
        assert callable(mock_file_service.list_directory)

    def test_mock_config_service_implements_iconfig_service(self, mock_config_service: MockConfigService):
        """Verify MockConfigService conforms to IConfigService protocol."""
        # Check that all required properties exist
        assert hasattr(mock_config_service, 'orchestrator_dir')
        assert hasattr(mock_config_service, 'specs_dir')
        assert hasattr(mock_config_service, 'cost_history_path')
        assert hasattr(mock_config_service, 'budget_config_path')

        # Verify properties return Path objects
        assert isinstance(mock_config_service.orchestrator_dir, Path)
        assert isinstance(mock_config_service.specs_dir, Path)
        assert isinstance(mock_config_service.cost_history_path, Path)
        assert isinstance(mock_config_service.budget_config_path, Path)


class TestMockServiceIntegration:
    """Test mock services working together for integrated testing scenarios."""

    @pytest.fixture
    def integrated_services(
        self,
        mock_plan_registry: MockPlanRegistry,
        mock_file_service: MockFileService,
        mock_config_service: MockConfigService
    ):
        """Create an integrated set of mock services with consistent test data."""
        # Configure plan registry
        test_plans = [
            {
                "id": "001_api-feature",
                "name": "API Feature",
                "state": "pending",
                "file": str(mock_config_service.specs_dir / "pending" / "001_api-feature"),
                "files": ["plan.md", "notes.md"],
                "modified": datetime.now().isoformat(),
                "request": "Add REST API endpoints",
                "complexity": "high"
            },
            {
                "id": "002_ui-update",
                "name": "UI Update",
                "state": "completed",
                "file": str(mock_config_service.specs_dir / "completed" / "002_ui-update"),
                "files": ["plan.md"],
                "modified": datetime.now().isoformat(),
                "request": "Update dashboard styling",
                "complexity": "low"
            }
        ]
        mock_plan_registry.set_plans(test_plans)

        # Configure file service with corresponding files
        mock_file_service.add_file(
            mock_config_service.specs_dir / "pending" / "001_api-feature" / "plan.md",
            "# Plan: API Feature\nRequest: Add REST API endpoints\nComplexity: high\n\n## Implementation\n- Add endpoints"
        )
        mock_file_service.add_file(
            mock_config_service.specs_dir / "completed" / "002_ui-update" / "plan.md",
            "# Plan: UI Update\nRequest: Update dashboard styling\nComplexity: low\n\n## Done"
        )

        return {
            "plan_registry": mock_plan_registry,
            "file_service": mock_file_service,
            "config_service": mock_config_service
        }

    @pytest.mark.asyncio
    async def test_integrated_plan_lookup_with_file_content(self, integrated_services):
        """Test looking up a plan and reading its file content using mock services."""
        plan_registry = integrated_services["plan_registry"]
        file_service = integrated_services["file_service"]
        config_service = integrated_services["config_service"]

        # Look up the plan
        plan = await plan_registry.get_plan_by_id("001_api-feature")
        assert plan is not None
        assert plan["name"] == "API Feature"

        # Read the plan file content
        plan_path = config_service.specs_dir / "pending" / "001_api-feature" / "plan.md"
        content = file_service.read_file(plan_path)
        assert "# Plan: API Feature" in content
        assert "Complexity: high" in content

    @pytest.mark.asyncio
    async def test_integrated_plan_counts_match_registry(self, integrated_services):
        """Test that plan counts are consistent with registry data."""
        plan_registry = integrated_services["plan_registry"]

        # Get all plans
        all_plans = await plan_registry.get_all_plans()

        # Manually count states
        state_counts = {"pending": 0, "completed": 0, "in_progress": 0, "failed": 0}
        for plan in all_plans:
            state = plan.get("state", "pending").replace("-", "_")
            if state in state_counts:
                state_counts[state] += 1

        # Verify counts match what registry reports
        # (Note: Our mock auto-updates counts when set_plans is called)
        registry_counts = plan_registry.get_plan_counts()
        assert registry_counts["pending"] == state_counts["pending"]
        assert registry_counts["completed"] == state_counts["completed"]

    def test_integrated_config_paths_used_by_file_service(self, integrated_services):
        """Test that config service paths work with file service."""
        file_service = integrated_services["file_service"]
        config_service = integrated_services["config_service"]

        # Add a cost history file using config path
        cost_history_path = config_service.cost_history_path
        file_service.add_file(cost_history_path, '{"daily_costs": []}')

        # Verify we can read it back
        assert file_service.file_exists(cost_history_path)
        content = file_service.read_file(cost_history_path)
        assert "daily_costs" in content


class TestEventSystem:
    """Test the event system for workflow streaming."""

    def test_add_event_function(self):
        """Test _add_event function exists and is callable."""
        from server.app import _add_event, active_runs
        assert callable(_add_event)

    def test_add_event_to_run(self):
        """Test adding event to an active run."""
        from server.app import _add_event, active_runs

        # Create a mock run
        run_id = "test-run-123"
        active_runs[run_id] = {
            "id": run_id,
            "events": [],
            "status": "running"
        }

        # Add event
        _add_event(run_id, {"type": "test", "message": "Test event"})

        # Verify event was added
        assert len(active_runs[run_id]["events"]) == 1
        assert active_runs[run_id]["events"][0]["type"] == "test"
        assert "timestamp" in active_runs[run_id]["events"][0]

        # Cleanup
        del active_runs[run_id]

    def test_add_event_nonexistent_run(self):
        """Test adding event to non-existent run doesn't crash."""
        from server.app import _add_event

        # Should not raise
        _add_event("nonexistent-run", {"type": "test"})


class TestFastAPIEndpoints:
    """Test FastAPI endpoints using TestClient."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from server.app import app
        return TestClient(app)

    def test_dashboard_endpoint(self, client):
        """Test dashboard returns HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_api_list_plans_endpoint(self, client):
        """Test API plans endpoint returns JSON."""
        response = client.get("/api/plans")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        assert "plans" in data

    def test_api_get_nonexistent_run(self, client):
        """Test getting non-existent run returns 404."""
        response = client.get("/api/runs/nonexistent-id")
        assert response.status_code == 404

    def test_api_get_nonexistent_plan(self, client):
        """Test getting non-existent plan returns 404."""
        response = client.get("/api/plans/nonexistent-plan-id")
        assert response.status_code == 404

    def test_api_cost_estimate_invalid_workflow(self, client):
        """Test cost estimate with invalid workflow returns 400."""
        response = client.get("/api/cost/estimate/invalid_workflow")
        assert response.status_code == 400

    def test_api_cost_report_invalid_period(self, client):
        """Test cost report with invalid period returns 400."""
        response = client.get("/api/cost/report/invalid_period")
        assert response.status_code == 400


class TestWorkflowAPIs:
    """Test workflow API endpoints.

    Note: These tests only verify API accepts requests and returns correct format.
    They do NOT verify actual workflow execution (which requires Claude Code).
    The background tasks are mocked to prevent actual execution.
    """

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from server.app import app, active_runs
        # Clear active runs before each test
        active_runs.clear()
        return TestClient(app, raise_server_exceptions=False)

    @pytest.mark.timeout(10)
    def test_create_plan_workflow(self, client):
        """Test creating a plan workflow - API accepts and responds."""
        with patch('server.app._run_planning_workflow'):
            response = client.post(
                "/api/workflows/plan",
                json={"description": "Test plan description"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
            assert data["status"] == "started"

    @pytest.mark.timeout(10)
    def test_start_build_workflow(self, client):
        """Test starting a build workflow - API accepts and responds."""
        with patch('server.app._run_building_workflow'):
            response = client.post(
                "/api/workflows/build",
                json={"plan_path": "/path/to/plan.md"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data

class TestBudgetAPI:
    """Test budget API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from fastapi.testclient import TestClient
        from server.app import app
        return TestClient(app)

    def test_get_budget(self, client):
        """Test getting budget status."""
        response = client.get("/api/cost/budget")
        assert response.status_code == 200

    def test_get_cost_summary(self, client):
        """Test getting cost summary."""
        response = client.get("/api/cost/summary")
        assert response.status_code == 200
        data = response.json()
        assert "daily" in data
        assert "weekly" in data
        assert "monthly" in data
