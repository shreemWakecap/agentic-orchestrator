"""
End-to-end tests for the complete plan-build-verify cycle.

Tests the full workflow from creating a plan through building and verification,
using fixtures to mock CLI interactions and agent responses.
"""
import pytest
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, MagicMock, patch


class MockAgentResult:
    """Mock result object returned by agent run methods."""

    def __init__(
        self,
        success: bool = True,
        content: str = "",
        error: str = None,
        input_tokens: int = 100,
        output_tokens: int = 200,
    ):
        self.success = success
        self.content = content
        self.error = error
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MockWorkflowResult:
    """Mock workflow result for testing."""

    def __init__(self, success: bool = True, data: Dict = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.error = error


@pytest.fixture
def mock_planning_workflow():
    """Create a mock planning workflow for e2e testing."""

    def _create_mock(project_root: Path, plan_content: str = None):
        mock_workflow = MagicMock()

        # Default plan content if none provided
        default_plan = """
GOAL: Implement test feature with proper tests

CONTEXT:
- Using pytest for testing
- Following existing project patterns

STEPS:

## Phase 1: Setup

STEP: step-1 - Create test file
ACTION: create
DO: Create a test file with basic structure
IN: tests/conftest.py
OUT: tests/test_feature.py
DONE: File exists with test class

STEP: step-2 - Add test function
ACTION: modify
DO: Add a test function to verify feature
IN: tests/test_feature.py
OUT: tests/test_feature.py
DONE: Test function exists and passes

VERIFY:
- Run pytest tests/test_feature.py
- All tests pass
"""
        plan_content = plan_content or default_plan

        mock_workflow.execute.return_value = MockWorkflowResult(
            success=True,
            data={
                "plan_id": "001_test_feature",
                "steps": 2,
                "goal": "Implement test feature with proper tests",
            },
        )

        mock_workflow.run.return_value = MockWorkflowResult(
            success=True,
            data={
                "plan_id": "001_test_feature",
                "steps": 2,
                "goal": "Implement test feature with proper tests",
            },
        )

        return mock_workflow

    return _create_mock


@pytest.fixture
def mock_building_workflow():
    """Create a mock building workflow for e2e testing."""

    def _create_mock(project_root: Path):
        mock_workflow = MagicMock()

        mock_workflow.execute.return_value = MockWorkflowResult(
            success=True,
            data={
                "plan_id": "001_test_feature",
                "completed_steps": ["step-1", "step-2"],
                "failed_steps": [],
                "files_created": ["tests/test_feature.py"],
                "files_modified": [],
                "goal_achieved": True,
            },
        )

        mock_workflow.run.return_value = MockWorkflowResult(
            success=True,
            data={
                "plan_id": "001_test_feature",
                "completed_steps": ["step-1", "step-2"],
                "failed_steps": [],
                "files_created": ["tests/test_feature.py"],
                "files_modified": [],
                "goal_achieved": True,
            },
        )

        return mock_workflow

    return _create_mock


@pytest.fixture
def e2e_project_dir(tmp_path):
    """Create a temporary project directory for e2e testing."""
    project_dir = tmp_path / "e2e_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create basic project structure
    (project_dir / "src").mkdir(exist_ok=True)
    (project_dir / "tests").mkdir(exist_ok=True)

    # Create a sample source file
    (project_dir / "src" / "main.py").write_text(
        '"""Main module."""\n\ndef main():\n    pass\n'
    )

    # Create conftest.py
    (project_dir / "tests" / "conftest.py").write_text(
        '"""Test configuration."""\nimport pytest\n'
    )

    # Create pyproject.toml
    (project_dir / "pyproject.toml").write_text(
        '[project]\nname = "test-project"\nversion = "0.1.0"\n'
    )

    return project_dir


class TestPlanBuildCycle:
    """End-to-end tests for the complete plan-build-verify cycle."""

    def test_full_cycle(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
        mock_planning_workflow,
        mock_building_workflow,
    ):
        """Test complete cycle: create plan -> execute build -> verify results.

        This test simulates the full workflow of:
        1. Creating a plan from a user request
        2. Executing the build steps
        3. Verifying the goal was achieved
        """
        # Phase 1: Create the plan
        planning_workflow = mock_planning_workflow(e2e_project_dir)
        plan_result = planning_workflow.run("Add a test feature")

        assert plan_result.success
        assert plan_result.data["plan_id"] == "001_test_feature"
        assert plan_result.data["steps"] == 2

        # Simulate plan being stored in repository
        plan_id = plan_result.data["plan_id"]
        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal=plan_result.data["goal"],
            request="Add a test feature",
            raw_content="# Plan content",
        )

        # Verify plan was created
        stored_plan = mock_plan_repo.get_by_id(plan_id)
        assert stored_plan is not None
        assert stored_plan["status"] == "pending"

        # Phase 2: Execute the build
        building_workflow = mock_building_workflow(e2e_project_dir)
        build_result = building_workflow.run(plan_id)

        assert build_result.success
        assert build_result.data["plan_id"] == plan_id
        assert "step-1" in build_result.data["completed_steps"]
        assert "step-2" in build_result.data["completed_steps"]
        assert len(build_result.data["failed_steps"]) == 0

        # Update plan status to completed
        mock_plan_repo.update_status(plan_id, "completed")

        # Phase 3: Verify results
        final_plan = mock_plan_repo.get_by_id(plan_id)
        assert final_plan["status"] == "completed"
        assert build_result.data["goal_achieved"] is True
        assert "tests/test_feature.py" in build_result.data["files_created"]

    def test_full_cycle_with_failure_and_retry(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
    ):
        """Test cycle with build failure and retry behavior."""
        # Create plan
        plan_id = "002_failing_feature"
        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal="Implement feature that fails initially",
            request="Add failing feature",
            raw_content="# Plan content",
        )

        # Simulate first build attempt failing
        mock_build_state_repo.create(plan_id=plan_id, total_steps=3)
        mock_build_state_repo.update(
            plan_id,
            status="failed",
            completed_steps=["step-1"],
            failed_steps=["step-2"],
        )
        mock_build_state_repo.set_step_state(
            plan_id, "step-2", status="failed", error="Syntax error in generated code"
        )

        # Verify failure state
        build_state = mock_build_state_repo.get(plan_id)
        assert build_state["status"] == "failed"
        assert "step-2" in build_state["failed_steps"]

        # Simulate retry with success
        mock_build_state_repo.update(
            plan_id,
            status="completed",
            completed_steps=["step-1", "step-2", "step-3"],
            failed_steps=[],
        )
        mock_build_state_repo.set_step_state(
            plan_id, "step-2", status="completed", error=None
        )

        # Verify recovery
        build_state = mock_build_state_repo.get(plan_id)
        assert build_state["status"] == "completed"
        assert len(build_state["failed_steps"]) == 0

        # Update plan to completed
        mock_plan_repo.update_status(plan_id, "completed")
        final_plan = mock_plan_repo.get_by_id(plan_id)
        assert final_plan["status"] == "completed"

    def test_full_cycle_with_parallel_steps(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
    ):
        """Test cycle with parallel step execution."""
        plan_id = "003_parallel_feature"
        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal="Implement feature with parallel steps",
            request="Add parallel feature",
            raw_content="# Plan with parallel execution",
        )

        # Create build state with parallel execution
        mock_build_state_repo.create(plan_id=plan_id, total_steps=4)

        # Simulate parallel execution of steps 2a and 2b
        mock_build_state_repo.set_step_state(
            plan_id, "step-1", status="completed"
        )
        mock_build_state_repo.set_step_state(
            plan_id, "step-2a", status="completed"
        )
        mock_build_state_repo.set_step_state(
            plan_id, "step-2b", status="completed"
        )
        mock_build_state_repo.set_step_state(
            plan_id, "step-3", status="completed"
        )

        mock_build_state_repo.update(
            plan_id,
            status="completed",
            completed_steps=["step-1", "step-2a", "step-2b", "step-3"],
        )

        # Verify all steps completed
        build_state = mock_build_state_repo.get(plan_id)
        assert build_state["status"] == "completed"
        assert len(build_state["completed_steps"]) == 4

        mock_plan_repo.update_status(plan_id, "completed")
        final_plan = mock_plan_repo.get_by_id(plan_id)
        assert final_plan["status"] == "completed"

    def test_full_cycle_goal_verification(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
    ):
        """Test that goal verification is properly tracked."""
        plan_id = "004_verified_feature"
        goal = "Create API endpoint that returns health status"

        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal=goal,
            request="Add health endpoint",
            raw_content="# Health endpoint plan",
        )

        mock_build_state_repo.create(plan_id=plan_id, total_steps=2)

        # Simulate build completion
        mock_build_state_repo.update(
            plan_id,
            status="completed",
            completed_steps=["step-1", "step-2"],
            files_created=["src/routes/health.py"],
        )

        # Verify files were created
        build_state = mock_build_state_repo.get(plan_id)
        assert "src/routes/health.py" in build_state["files_created"]

        # Mark plan as completed
        mock_plan_repo.update_status(plan_id, "completed")
        final_plan = mock_plan_repo.get_by_id(plan_id)

        assert final_plan["status"] == "completed"
        assert final_plan["goal"] == goal

    def test_cycle_cancellation(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
    ):
        """Test that a cycle can be properly cancelled mid-execution."""
        plan_id = "005_cancelled_feature"
        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal="Feature that gets cancelled",
            request="Add cancellable feature",
            raw_content="# Plan content",
        )

        mock_build_state_repo.create(plan_id=plan_id, total_steps=5)

        # Simulate partial execution before cancellation
        mock_build_state_repo.update(
            plan_id,
            status="building",
            completed_steps=["step-1", "step-2"],
        )

        # Simulate cancellation
        mock_build_state_repo.update(
            plan_id,
            status="cancelled",
        )
        mock_plan_repo.update_status(plan_id, "cancelled")

        # Verify cancelled state
        build_state = mock_build_state_repo.get(plan_id)
        assert build_state["status"] == "cancelled"
        assert len(build_state["completed_steps"]) == 2  # Partial progress

        plan = mock_plan_repo.get_by_id(plan_id)
        assert plan["status"] == "cancelled"

    def test_cycle_with_file_modifications(
        self,
        e2e_project_dir,
        mock_plan_repo,
        mock_build_state_repo,
    ):
        """Test tracking of file creations and modifications."""
        plan_id = "006_file_tracking"
        mock_plan_repo.create(
            plan_id=plan_id,
            status="pending",
            goal="Modify existing files and create new ones",
            request="Add feature with file changes",
            raw_content="# Plan content",
        )

        mock_build_state_repo.create(plan_id=plan_id, total_steps=3)

        # Simulate file operations
        mock_build_state_repo.update(
            plan_id,
            status="completed",
            completed_steps=["step-1", "step-2", "step-3"],
            files_created=["src/new_module.py", "tests/test_new_module.py"],
            files_modified=["src/main.py", "src/config.py"],
        )

        build_state = mock_build_state_repo.get(plan_id)
        assert len(build_state["files_created"]) == 2
        assert len(build_state["files_modified"]) == 2
        assert "src/new_module.py" in build_state["files_created"]
        assert "src/main.py" in build_state["files_modified"]

        mock_plan_repo.update_status(plan_id, "completed")
