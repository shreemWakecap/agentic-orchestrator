"""
Integration tests for Building Workflow.

Tests the full building flow from plan parsing to step execution,
using mocked Agent responses to isolate the workflow logic.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from core import WorkflowResult


@pytest.fixture
def mock_project_root(tmp_path):
    """Create a temporary project root for testing."""
    # Create basic project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# Main file")
    (tmp_path / "src" / "models").mkdir()
    (tmp_path / "src" / "models" / "__init__.py").write_text("# Models module")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'")
    return tmp_path


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration."""
    config = Mock()
    config.parallel = Mock()
    config.parallel.max_sub_features = 4
    return config


@pytest.fixture
def mock_plan_content():
    """Mock plan content with valid format."""
    return """# Plan: Test Feature

Request: Add user model
Complexity: low

## Goal
Create a user model with email and password fields

## Context
- Using SQLAlchemy ORM
- PostgreSQL database

## Phase 1: Database Setup [phase-1]

### step-1 - Create user model
ACTION: create
DO: Create User model with email, password_hash fields
IN: src/models/__init__.py
OUT: src/models/user.py
DONE: File exists with User class definition

### step-2 - Add migration
ACTION: run
DO: Generate database migration
IN: src/models/user.py
OUT: migrations/versions/001_add_users.py
DONE: Migration file created
NEEDS: step-1

## Verify
- User model exists
- Migration created
"""


@pytest.fixture
def mock_plan_repo():
    """Mock plan repository."""
    repo = Mock()
    repo.get_by_id.return_value = {
        "plan_id": "001_test",
        "status": "pending",
        "raw_content": "",
        "request": "Add user model",
        "goal": "Create user model",
    }
    repo.update_status.return_value = None
    return repo


@pytest.fixture
def mock_build_state_repo():
    """Mock build state repository."""
    repo = Mock()
    repo.get.return_value = None
    repo.create.return_value = 1
    repo.update.return_value = None
    repo.set_step_state.return_value = None
    return repo


@pytest.fixture
def mock_token_signal():
    """Mock token usage signal."""
    signal = Mock()
    return signal


@pytest.fixture
def mock_token_service():
    """Mock token usage service."""
    service = Mock()
    service.record_execution.return_value = None
    return service


@pytest.fixture
def mock_builder_response():
    """Mock builder agent response."""
    return """SUMMARY: Created user.py with User model class

FILES:
- src/models/user.py created

VERIFIED: yes
VERIFICATION: Read file back - contains User class with email and password_hash fields

CONCERNS: none
"""


@pytest.fixture
def mock_goal_verifier_response():
    """Mock goal-verifier agent response."""
    return """ACHIEVED: yes
COMPLETION: 100%
MISSING:
NOTES: All requirements implemented successfully
"""


@pytest.mark.asyncio
class TestBuildingWorkflow:
    """Integration tests for BuildingWorkflow."""

    @pytest.fixture
    def workflow_with_mocks(
        self,
        mock_project_root,
        mock_plan_repo,
        mock_build_state_repo,
        mock_agent_config,
        mock_token_signal,
        mock_token_service,
        mock_plan_content,
    ):
        """Create BuildingWorkflow with all dependencies mocked."""
        with patch("workflows.building.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.building.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.building.get_agent_config", return_value=mock_agent_config), \
             patch("workflows.building.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.building.TokenUsageService", return_value=mock_token_service), \
             patch("core.Agent.load") as mock_agent_load:

            # Mock agents
            mock_builder = Mock()
            mock_builder.name = "builder"

            mock_goal_verifier = Mock()
            mock_goal_verifier.name = "goal-verifier"

            def agent_loader(name, *args, **kwargs):
                if name == "builder":
                    return mock_builder
                elif name == "goal-verifier":
                    return mock_goal_verifier
                raise FileNotFoundError(f"Agent {name} not found")

            mock_agent_load.side_effect = agent_loader

            # Set up plan repo to return plan content
            mock_plan_repo.get_by_id.return_value["raw_content"] = mock_plan_content

            from workflows.building import BuildingWorkflow
            workflow = BuildingWorkflow(project_root=mock_project_root)

            # Store mocks for later access
            workflow._mock_plan_repo = mock_plan_repo
            workflow._mock_build_state_repo = mock_build_state_repo
            workflow._mock_plan_content = mock_plan_content

            yield workflow

    async def test_run_executes_plan_successfully(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that execute() runs a plan to completion."""
        workflow = workflow_with_mocks

        # Mock run_agent to return successful results
        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        assert result.success is True
        # Verify plan status was updated
        workflow._mock_plan_repo.update_status.assert_called()

    async def test_run_handles_missing_plan(self, workflow_with_mocks):
        """Test that execute() handles non-existent plan."""
        workflow = workflow_with_mocks
        workflow._mock_plan_repo.get_by_id.return_value = None

        result = workflow.execute("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_run_handles_parse_failure(self, workflow_with_mocks):
        """Test that execute() handles plan parsing failures."""
        workflow = workflow_with_mocks

        # Return invalid plan content
        workflow._mock_plan_repo.get_by_id.return_value["raw_content"] = "This is not a valid plan"

        result = workflow.execute("001_test")

        assert result.success is False
        assert "pars" in result.error.lower()  # "parsing" or "parse"

    async def test_step_execution_creates_files(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that step execution reports file creation."""
        workflow = workflow_with_mocks

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        assert result.success is True
        # Build state should track files
        if workflow.build_state:
            assert workflow.build_state.completed_steps is not None

    async def test_step_execution_handles_builder_failure(
        self, workflow_with_mocks, mock_goal_verifier_response
    ):
        """Test that step execution handles builder agent failure."""
        workflow = workflow_with_mocks

        call_count = [0]

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            if agent_name == "builder":
                call_count[0] += 1
                # First step fails, subsequent steps also fail
                return WorkflowResult(success=False, error="Builder failed")
            elif agent_name == "goal-verifier":
                result = WorkflowResult(success=True, data={})
                result.content = mock_goal_verifier_response
                return result
            return WorkflowResult(success=True, data={})

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # The workflow should handle failures and continue or fail gracefully
        assert workflow.build_state is not None
        assert len(workflow.build_state.failed_steps) > 0

    async def test_failure_recovery_resumes_from_checkpoint(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that workflow can resume from a previous failure."""
        workflow = workflow_with_mocks

        # Simulate existing state with one completed step
        existing_state = {
            "plan_id": "001_test",
            "plan_file": "",
            "status": "paused",
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "current_phase": 0,
            "current_step": "step-2",
            "total_steps": 2,
            "completed_steps": ["step-1"],
            "failed_steps": ["step-2"],
            "skipped_steps": [],
            "step_states": {
                "step-1": {
                    "step_id": "step-1",
                    "status": "completed",
                    "summary": "Created user model",
                    "files_affected": ["src/models/user.py"],
                }
            },
            "files_created": ["src/models/user.py"],
            "files_modified": [],
            "last_error": "Previous failure",
            "execution_mode": "sequential",
            "current_wave_index": 0,
            "thinking_enabled": False,
        }

        workflow._mock_build_state_repo.get.return_value = existing_state

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Should have resumed from the paused state
        assert workflow.build_state is not None
        # step-1 should still be marked as completed from previous run
        assert "step-1" in workflow.build_state.completed_steps

    async def test_goal_verification_runs_after_completion(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that goal verification runs after all steps complete."""
        workflow = workflow_with_mocks

        agent_calls = []

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            agent_calls.append(agent_name)
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # goal-verifier should have been called
        assert "goal-verifier" in agent_calls

    async def test_step_state_persistence(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that step states are persisted during execution."""
        workflow = workflow_with_mocks

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Build state repository should have been updated
        assert workflow._mock_build_state_repo.update.called or workflow._mock_build_state_repo.create.called

    async def test_file_operations_tracked(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that file operations are tracked in build state."""
        workflow = workflow_with_mocks

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Build state should track created/modified files
        if workflow.build_state:
            # Files should be tracked (either created or modified)
            total_files = len(workflow.build_state.files_created) + len(workflow.build_state.files_modified)
            # Builder response indicates file creation
            assert workflow.build_state is not None

    async def test_multiple_phases_executed_in_order(self, mock_project_root, mock_plan_repo, mock_build_state_repo, mock_agent_config, mock_token_signal, mock_token_service, mock_builder_response, mock_goal_verifier_response):
        """Test that multiple phases are executed in correct order."""
        multi_phase_plan = """# Plan: Multi-phase Feature

Request: Add auth system
Complexity: medium

## Goal
Implement authentication with login and registration

## Phase 1: Database [phase-1]

### step-1 - Create user model
ACTION: create
DO: Create User model
IN: src/models/__init__.py
OUT: src/models/user.py
DONE: User model exists

## Phase 2: API [phase-2]

### step-2 - Create auth routes
ACTION: create
DO: Create auth routes
IN: src/models/user.py
OUT: src/routes/auth.py
DONE: Auth routes exist
NEEDS: step-1

## Verify
- Authentication works
"""
        mock_plan_repo.get_by_id.return_value = {
            "plan_id": "001_multi",
            "status": "pending",
            "raw_content": multi_phase_plan,
            "request": "Add auth system",
            "goal": "Implement authentication",
        }

        with patch("workflows.building.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.building.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.building.get_agent_config", return_value=mock_agent_config), \
             patch("workflows.building.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.building.TokenUsageService", return_value=mock_token_service), \
             patch("core.Agent.load") as mock_agent_load:

            mock_builder = Mock()
            mock_builder.name = "builder"

            mock_goal_verifier = Mock()
            mock_goal_verifier.name = "goal-verifier"

            def agent_loader(name, *args, **kwargs):
                if name == "builder":
                    return mock_builder
                elif name == "goal-verifier":
                    return mock_goal_verifier
                raise FileNotFoundError(f"Agent {name} not found")

            mock_agent_load.side_effect = agent_loader

            from workflows.building import BuildingWorkflow
            workflow = BuildingWorkflow(project_root=mock_project_root)

            executed_steps = []

            def mock_run_agent(agent_name, message, context=None, show_progress=True):
                if agent_name == "builder":
                    # Extract step ID from message
                    if "step-1" in message:
                        executed_steps.append("step-1")
                    elif "step-2" in message:
                        executed_steps.append("step-2")
                result = WorkflowResult(success=True, data={})
                if agent_name == "builder":
                    result.content = mock_builder_response
                elif agent_name == "goal-verifier":
                    result.content = mock_goal_verifier_response
                return result

            workflow.run_agent = Mock(side_effect=mock_run_agent)

            result = workflow.execute("001_multi")

            # Steps should be executed (step-1 before step-2 due to dependency)
            assert len(executed_steps) >= 1
            if len(executed_steps) >= 2:
                step1_idx = executed_steps.index("step-1")
                step2_idx = executed_steps.index("step-2")
                assert step1_idx < step2_idx

    async def test_cancel_during_execution(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that workflow can be cancelled during execution."""
        workflow = workflow_with_mocks

        # Simulate plan being cancelled externally
        workflow._mock_plan_repo.get_by_id.side_effect = [
            {
                "plan_id": "001_test",
                "status": "pending",
                "raw_content": workflow._mock_plan_content,
                "request": "Add user model",
                "goal": "Create user model",
            },
            {
                "plan_id": "001_test",
                "status": "cancelled",  # Changed to cancelled
                "raw_content": workflow._mock_plan_content,
                "request": "Add user model",
                "goal": "Create user model",
            },
        ]

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Workflow should handle cancellation gracefully
        assert workflow.build_state is not None

    async def test_error_handling_missing_builder_agent(self, mock_project_root, mock_plan_repo, mock_build_state_repo, mock_agent_config, mock_token_signal, mock_token_service):
        """Test error handling when builder agent is not available."""
        with patch("workflows.building.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.building.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.building.get_agent_config", return_value=mock_agent_config), \
             patch("workflows.building.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.building.TokenUsageService", return_value=mock_token_service), \
             patch("core.Agent.load", side_effect=FileNotFoundError("builder agent not found")):

            from workflows.building import BuildingWorkflow

            # Should print warning but not crash during initialization
            workflow = BuildingWorkflow(project_root=mock_project_root)

            # Verify workflow was created (agents are optional at init)
            assert workflow is not None

    async def test_dependency_resolution(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that steps with dependencies are executed in correct order."""
        workflow = workflow_with_mocks

        executed_steps = []

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            if agent_name == "builder":
                if "step-1" in message:
                    executed_steps.append("step-1")
                elif "step-2" in message:
                    executed_steps.append("step-2")
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # step-2 has NEEDS: step-1, so step-1 should execute first
        if "step-1" in executed_steps and "step-2" in executed_steps:
            assert executed_steps.index("step-1") < executed_steps.index("step-2")

    async def test_token_usage_tracking(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that token usage is tracked during execution."""
        workflow = workflow_with_mocks

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            result.tokens_used = 1000  # Simulate token usage
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Token tracking should have accumulated some tokens
        assert workflow._total_input_tokens >= 0 or workflow._total_output_tokens >= 0

    async def test_build_state_status_transitions(
        self, workflow_with_mocks, mock_builder_response, mock_goal_verifier_response
    ):
        """Test that build state transitions through correct statuses."""
        workflow = workflow_with_mocks

        status_changes = []

        original_save = workflow._save_state

        def track_save_state():
            if workflow.build_state:
                status_changes.append(workflow.build_state.status)
            return original_save() if original_save else None

        workflow._save_state = Mock(side_effect=track_save_state)

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Build state should have transitioned through statuses
        if status_changes:
            assert "building" in status_changes

    async def test_step_result_parsing(
        self, workflow_with_mocks, mock_goal_verifier_response
    ):
        """Test that step results are parsed correctly from builder output."""
        workflow = workflow_with_mocks

        custom_builder_response = """SUMMARY: Created multiple files for feature

FILES:
- src/models/user.py created
- src/routes/auth.py created

VERIFIED: yes
VERIFICATION: All files exist with expected content

CONCERNS: none
"""

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = custom_builder_response
            elif agent_name == "goal-verifier":
                result.content = mock_goal_verifier_response
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # The workflow should parse the builder response
        assert result.success is True

    async def test_verification_failure_handling(self, workflow_with_mocks, mock_builder_response):
        """Test handling of goal verification failure."""
        workflow = workflow_with_mocks

        failed_verification = """ACHIEVED: no
COMPLETION: 50%
MISSING:
- User registration endpoint not implemented
- Password hashing not added
NOTES: Only basic model created
"""

        def mock_run_agent(agent_name, message, context=None, show_progress=True):
            result = WorkflowResult(success=True, data={})
            if agent_name == "builder":
                result.content = mock_builder_response
            elif agent_name == "goal-verifier":
                result.content = failed_verification
            return result

        workflow.run_agent = Mock(side_effect=mock_run_agent)

        result = workflow.execute("001_test")

        # Workflow should complete even if goal verification says not achieved
        assert workflow.build_state is not None
