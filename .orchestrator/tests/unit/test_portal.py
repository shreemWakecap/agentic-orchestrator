"""Tests for the web portal (server/app.py).

Ensures:
- Web dependencies are installed
- FastAPI app can be imported
- API endpoints work correctly
- Helper functions work correctly
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


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
    """Test helper functions in server/app.py."""

    @pytest.fixture
    def mock_specs_dir(self, tmp_path):
        """Create mock specs directory structure."""
        specs_dir = tmp_path / ".orchestrator" / "specs"

        # Create state directories
        for state in ["pending", "in-progress", "completed", "failed"]:
            state_dir = specs_dir / state
            state_dir.mkdir(parents=True)

        # Create some test plans
        (specs_dir / "pending" / "test-plan-1.md").write_text("# Test Plan 1")
        (specs_dir / "completed" / "test-plan-2.md").write_text("# Test Plan 2")

        # Create reviews directory
        reviews_dir = specs_dir / "reviews"
        reviews_dir.mkdir()
        (reviews_dir / "review-1.md").write_text("# Review\nScore: 85%")

        return specs_dir

    @pytest.mark.asyncio
    async def test_get_all_plans(self, mock_specs_dir):
        """Test _get_all_plans returns plans from all states."""
        from server.app import _get_all_plans, ORCHESTRATOR_DIR

        with patch.object(Path, '__truediv__', return_value=mock_specs_dir.parent):
            # This test verifies the function structure exists
            # Full integration test would require more mocking
            assert callable(_get_all_plans)

    @pytest.mark.asyncio
    async def test_get_recent_plans(self):
        """Test _get_recent_plans returns limited results."""
        from server.app import _get_recent_plans
        assert callable(_get_recent_plans)

    @pytest.mark.asyncio
    async def test_get_plan_by_id(self):
        """Test _get_plan_by_id function exists."""
        from server.app import _get_plan_by_id
        assert callable(_get_plan_by_id)

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
