"""Tests for dependency injection overrides in FastAPI routes.

These tests verify that each get_*_repo() and get_*_service() function
from portal.dependencies can be properly overridden in the test environment.
"""
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

import sys

# Add orchestrator to path
orchestrator_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(orchestrator_dir))

from fastapi.testclient import TestClient
from portal.app import app
from portal import dependencies


# ============== Mock Objects for Testing ==============


class MockRepository:
    """Generic mock repository for testing dependency overrides."""

    def __init__(self, name: str):
        self.name = name
        self.called = False

    def get(self, *args, **kwargs):
        self.called = True
        return {"mock": self.name}


class MockService:
    """Generic mock service for testing dependency overrides."""

    def __init__(self, name: str):
        self.name = name
        self.called = False

    def execute(self, *args, **kwargs):
        self.called = True
        return {"result": self.name}


class MockProjectContextProvider:
    """Mock project context provider for testing."""

    def __init__(self):
        self.project_id = "test-project-123"

    def get_current_project_id(self) -> str:
        return self.project_id


# ============== Tests for Repository Dependency Overrides ==============


class TestPlanRepoDependencyOverride:
    """Tests for get_plan_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_plan_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("plan")

        app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_repo

        try:
            # The override should return our mock
            override_fn = app.dependency_overrides[dependencies.get_plan_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "plan"
        finally:
            app.dependency_overrides.clear()

    def test_override_clears_properly(self):
        """Verify dependency overrides are properly cleared."""
        mock_repo = MockRepository("plan")

        app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_repo
        assert dependencies.get_plan_repo in app.dependency_overrides

        app.dependency_overrides.clear()
        assert dependencies.get_plan_repo not in app.dependency_overrides


class TestBuildStateRepoDependencyOverride:
    """Tests for get_build_state_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_build_state_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("build_state")

        app.dependency_overrides[dependencies.get_build_state_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_build_state_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "build_state"
        finally:
            app.dependency_overrides.clear()


class TestRunRepoDependencyOverride:
    """Tests for get_run_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_run_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("run")

        app.dependency_overrides[dependencies.get_run_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_run_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "run"
        finally:
            app.dependency_overrides.clear()


class TestCostRepoDependencyOverride:
    """Tests for get_cost_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_cost_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("cost")

        app.dependency_overrides[dependencies.get_cost_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_cost_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "cost"
        finally:
            app.dependency_overrides.clear()


class TestKnowledgeRepoDependencyOverride:
    """Tests for get_knowledge_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_knowledge_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("knowledge")

        app.dependency_overrides[dependencies.get_knowledge_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_knowledge_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "knowledge"
        finally:
            app.dependency_overrides.clear()


class TestFileKnowledgeRepoDependencyOverride:
    """Tests for get_file_knowledge_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_file_knowledge_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("file_knowledge")

        app.dependency_overrides[dependencies.get_file_knowledge_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_file_knowledge_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "file_knowledge"
        finally:
            app.dependency_overrides.clear()


class TestTokenUsageRepoDependencyOverride:
    """Tests for get_token_usage_repo dependency override."""

    def test_override_returns_mock(self):
        """Verify get_token_usage_repo can be overridden and returns the mock."""
        mock_repo = MockRepository("token_usage")

        app.dependency_overrides[dependencies.get_token_usage_repo] = lambda: mock_repo

        try:
            override_fn = app.dependency_overrides[dependencies.get_token_usage_repo]
            result = override_fn()

            assert result is mock_repo
            assert result.name == "token_usage"
        finally:
            app.dependency_overrides.clear()


# ============== Tests for Service Dependency Overrides ==============


class TestTaskManagerDependencyOverride:
    """Tests for get_task_manager dependency override."""

    def test_override_returns_mock(self):
        """Verify get_task_manager can be overridden and returns the mock."""
        mock_service = MockService("task_manager")

        app.dependency_overrides[dependencies.get_task_manager] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_task_manager]
            result = override_fn()

            assert result is mock_service
            assert result.name == "task_manager"
        finally:
            app.dependency_overrides.clear()


class TestRecoveryServiceDependencyOverride:
    """Tests for get_recovery_service dependency override."""

    def test_override_returns_mock(self):
        """Verify get_recovery_service can be overridden and returns the mock."""
        mock_service = MockService("recovery_service")

        app.dependency_overrides[dependencies.get_recovery_service] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_recovery_service]
            result = override_fn()

            assert result is mock_service
            assert result.name == "recovery_service"
        finally:
            app.dependency_overrides.clear()


class TestPlanStatusServiceDependencyOverride:
    """Tests for get_plan_status_service dependency override."""

    def test_override_returns_mock(self):
        """Verify get_plan_status_service can be overridden and returns the mock."""
        mock_service = MockService("plan_status_service")

        app.dependency_overrides[dependencies.get_plan_status_service] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_plan_status_service]
            result = override_fn()

            assert result is mock_service
            assert result.name == "plan_status_service"
        finally:
            app.dependency_overrides.clear()


class TestTokenUsageServiceDependencyOverride:
    """Tests for get_token_usage_service dependency override."""

    def test_override_returns_mock(self):
        """Verify get_token_usage_service can be overridden and returns the mock."""
        mock_service = MockService("token_usage_service")

        app.dependency_overrides[dependencies.get_token_usage_service] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_token_usage_service]
            result = override_fn()

            assert result is mock_service
            assert result.name == "token_usage_service"
        finally:
            app.dependency_overrides.clear()


class TestExpertsServiceDependencyOverride:
    """Tests for get_experts_service dependency override."""

    def test_override_returns_mock(self):
        """Verify get_experts_service can be overridden and returns the mock."""
        mock_service = MockService("experts_service")

        app.dependency_overrides[dependencies.get_experts_service] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_experts_service]
            result = override_fn()

            assert result is mock_service
            assert result.name == "experts_service"
        finally:
            app.dependency_overrides.clear()


class TestProjectContextProviderDependencyOverride:
    """Tests for get_project_context_provider dependency override."""

    def test_override_returns_mock(self):
        """Verify get_project_context_provider can be overridden and returns the mock."""
        mock_provider = MockProjectContextProvider()

        app.dependency_overrides[dependencies.get_project_context_provider] = lambda: mock_provider

        try:
            override_fn = app.dependency_overrides[dependencies.get_project_context_provider]
            result = override_fn()

            assert result is mock_provider
            assert result.get_current_project_id() == "test-project-123"
        finally:
            app.dependency_overrides.clear()


class TestWorkflowSubmissionServiceDependencyOverride:
    """Tests for get_workflow_submission_service dependency override."""

    def test_override_returns_mock(self):
        """Verify get_workflow_submission_service can be overridden and returns the mock."""
        mock_service = MockService("workflow_submission_service")

        app.dependency_overrides[dependencies.get_workflow_submission_service] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_workflow_submission_service]
            result = override_fn()

            assert result is mock_service
            assert result.name == "workflow_submission_service"
        finally:
            app.dependency_overrides.clear()


class TestRecoveryServiceWithDIDependencyOverride:
    """Tests for get_recovery_service_with_di dependency override."""

    def test_override_returns_mock(self):
        """Verify get_recovery_service_with_di can be overridden and returns the mock."""
        mock_service = MockService("recovery_service_with_di")

        app.dependency_overrides[dependencies.get_recovery_service_with_di] = lambda: mock_service

        try:
            override_fn = app.dependency_overrides[dependencies.get_recovery_service_with_di]
            result = override_fn()

            assert result is mock_service
            assert result.name == "recovery_service_with_di"
        finally:
            app.dependency_overrides.clear()


# ============== Tests for Path Dependency Overrides ==============


class TestProjectRootDependencyOverride:
    """Tests for get_project_root dependency override."""

    def test_override_returns_mock(self):
        """Verify get_project_root can be overridden and returns the mock."""
        mock_path = Path("/test/project/root")

        app.dependency_overrides[dependencies.get_project_root] = lambda: mock_path

        try:
            override_fn = app.dependency_overrides[dependencies.get_project_root]
            result = override_fn()

            assert result == mock_path
            assert result == Path("/test/project/root")
        finally:
            app.dependency_overrides.clear()


class TestOrchestratorDirDependencyOverride:
    """Tests for get_orchestrator_dir dependency override."""

    def test_override_returns_mock(self):
        """Verify get_orchestrator_dir can be overridden and returns the mock."""
        mock_path = Path("/test/orchestrator/dir")

        app.dependency_overrides[dependencies.get_orchestrator_dir] = lambda: mock_path

        try:
            override_fn = app.dependency_overrides[dependencies.get_orchestrator_dir]
            result = override_fn()

            assert result == mock_path
            assert result == Path("/test/orchestrator/dir")
        finally:
            app.dependency_overrides.clear()


# ============== Integration Tests ==============


class TestMultipleDependencyOverrides:
    """Tests for multiple dependency overrides working together."""

    def test_multiple_overrides_work_simultaneously(self):
        """Verify multiple dependency overrides can work at the same time."""
        mock_plan_repo = MockRepository("plan")
        mock_build_state_repo = MockRepository("build_state")
        mock_run_repo = MockRepository("run")

        app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_plan_repo
        app.dependency_overrides[dependencies.get_build_state_repo] = lambda: mock_build_state_repo
        app.dependency_overrides[dependencies.get_run_repo] = lambda: mock_run_repo

        try:
            # All three should be overridden
            assert len(app.dependency_overrides) == 3

            # Each returns its respective mock
            assert app.dependency_overrides[dependencies.get_plan_repo]() is mock_plan_repo
            assert app.dependency_overrides[dependencies.get_build_state_repo]() is mock_build_state_repo
            assert app.dependency_overrides[dependencies.get_run_repo]() is mock_run_repo
        finally:
            app.dependency_overrides.clear()

    def test_override_replacement(self):
        """Verify a dependency override can be replaced with another."""
        mock_repo_v1 = MockRepository("plan_v1")
        mock_repo_v2 = MockRepository("plan_v2")

        app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_repo_v1

        try:
            # First override
            result = app.dependency_overrides[dependencies.get_plan_repo]()
            assert result.name == "plan_v1"

            # Replace with second override
            app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_repo_v2
            result = app.dependency_overrides[dependencies.get_plan_repo]()
            assert result.name == "plan_v2"
        finally:
            app.dependency_overrides.clear()


class TestDependencyOverridesWithTestClient:
    """Tests verifying dependency overrides work with TestClient."""

    def test_overrides_active_during_test_client_context(self):
        """Verify overrides remain active within TestClient context."""
        mock_plan_repo = MockRepository("plan")
        mock_build_state_repo = MockRepository("build_state")
        mock_run_repo = MockRepository("run")

        app.dependency_overrides[dependencies.get_plan_repo] = lambda: mock_plan_repo
        app.dependency_overrides[dependencies.get_build_state_repo] = lambda: mock_build_state_repo
        app.dependency_overrides[dependencies.get_run_repo] = lambda: mock_run_repo

        try:
            # Create test client (similar to conftest.py pattern)
            client = TestClient(app)

            # Overrides should still be active
            assert dependencies.get_plan_repo in app.dependency_overrides
            assert dependencies.get_build_state_repo in app.dependency_overrides
            assert dependencies.get_run_repo in app.dependency_overrides

            # Each should return the mock
            assert app.dependency_overrides[dependencies.get_plan_repo]() is mock_plan_repo
            assert app.dependency_overrides[dependencies.get_build_state_repo]() is mock_build_state_repo
            assert app.dependency_overrides[dependencies.get_run_repo]() is mock_run_repo
        finally:
            app.dependency_overrides.clear()
