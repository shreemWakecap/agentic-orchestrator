"""Tests for API routes.

These tests use the test_client fixture which overrides dependencies
with mock repositories.
"""
import pytest


class TestHealthRoutes:
    """Tests for health check endpoints."""

    def test_health_check(self, test_client):
        """Should return healthy status."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_simple_health(self, test_client):
        """Should return ok status for simple health check."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_hello_world(self, test_client):
        """Should return hello world message."""
        response = test_client.get("/api/hello")
        assert response.status_code == 200
        assert response.json()["message"] == "hello world"


class TestPlanRoutes:
    """Tests for plan-related endpoints."""

    def test_list_plans_empty(self, test_client):
        """Should return empty list when no plans exist."""
        response = test_client.get("/api/plans")
        assert response.status_code == 200
        data = response.json()
        assert data["plans"] == []

    def test_list_plans_with_data(self, test_client, sample_plan):
        """Should return list of plans."""
        response = test_client.get("/api/plans")
        assert response.status_code == 200
        data = response.json()
        assert len(data["plans"]) == 1
        assert data["plans"][0]["id"] == sample_plan

    def test_get_plan(self, test_client, sample_plan):
        """Should return plan details."""
        response = test_client.get(f"/api/plans/{sample_plan}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_plan
        assert data["state"] == "pending"

    def test_get_plan_not_found(self, test_client):
        """Should return 404 for non-existent plan."""
        response = test_client.get("/api/plans/nonexistent")
        assert response.status_code == 404

    def test_delete_plan(self, test_client, sample_plan, mock_plan_repo):
        """Should delete plan."""
        response = test_client.delete(f"/api/plans/{sample_plan}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert mock_plan_repo.get_by_id(sample_plan) is None

    def test_move_plan(self, test_client, sample_plan):
        """Should move plan to new state."""
        response = test_client.put(
            f"/api/plans/{sample_plan}/move",
            json={"target_state": "failed"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "moved"
        assert data["new_state"] == "failed"

    def test_move_plan_invalid_state(self, test_client, sample_plan):
        """Should reject invalid target state."""
        response = test_client.put(
            f"/api/plans/{sample_plan}/move",
            json={"target_state": "invalid"},
        )
        assert response.status_code == 422  # Validation error

    def test_get_plan_state(self, test_client, sample_plan):
        """Should return plan build state."""
        response = test_client.get(f"/api/plans/{sample_plan}/state")
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == sample_plan
        assert data["status"] == "pending"


class TestRunRoutes:
    """Tests for run-related endpoints."""

    def test_list_runs_empty(self, test_client):
        """Should return empty list when no runs exist."""
        response = test_client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert all(v == 0 for v in data["counts"].values())

    def test_list_runs_with_data(self, test_client, sample_run):
        """Should return list of runs."""
        response = test_client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == sample_run

    def test_get_run(self, test_client, sample_run):
        """Should return run details."""
        response = test_client.get(f"/api/runs/{sample_run}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == sample_run
        assert data["workflow"] == "planning"

    def test_get_run_not_found(self, test_client):
        """Should return 404 for non-existent run."""
        response = test_client.get("/api/runs/nonexistent")
        assert response.status_code == 404


class TestWorkflowRoutes:
    """Tests for workflow-related endpoints."""

    def test_create_plan_workflow(self, test_client, mock_run_repo):
        """Should start planning workflow."""
        response = test_client.post(
            "/api/workflows/plan",
            json={"description": "Test feature"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "run_id" in data
        # Verify run was created
        assert len(mock_run_repo.runs) == 1

    def test_create_plan_workflow_empty_description(self, test_client):
        """Should reject empty description."""
        response = test_client.post(
            "/api/workflows/plan",
            json={"description": ""},
        )
        assert response.status_code == 422  # Validation error
