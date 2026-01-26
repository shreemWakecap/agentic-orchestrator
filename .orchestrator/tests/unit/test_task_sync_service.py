"""
Tests for TaskSyncService.

Run with: pytest tests/unit/test_task_sync_service.py -v
"""
import json
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Import will fail until Phase 04 implements the service
# from portal.services.task_sync_service import TaskSyncService


class TestCreateTasksFromPlan:
    """Tests for TaskSyncService.create_tasks_from_plan()"""

    @pytest.fixture
    def mock_plan_repo(self):
        """Create mock plan repository."""
        return Mock()

    @pytest.fixture
    def mock_build_state_repo(self):
        """Create mock build state repository."""
        return Mock()

    @pytest.fixture
    def mock_mapping_repo(self):
        """Create mock task mapping repository."""
        return Mock()

    @pytest.fixture
    def service(self, mock_plan_repo, mock_build_state_repo, mock_mapping_repo):
        """Create TaskSyncService instance with mocks."""
        from portal.services.task_sync_service import TaskSyncService
        return TaskSyncService(mock_plan_repo, mock_build_state_repo, mock_mapping_repo)

    def test_generates_task_instructions_for_each_step(self, mock_plan_repo, mock_build_state_repo, mock_mapping_repo):
        """Should generate TaskCreate instructions for all plan steps."""
        from portal.services.task_sync_service import TaskSyncService

        # Setup
        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "src/routes/health.py",
             "description": "Create health route", "needs": []},
            {"step_id": "step-2", "action": "modify", "target": "src/main.py",
             "description": "Register health router", "needs": ["step-1"]},
        ]

        service = TaskSyncService(mock_plan_repo, mock_build_state_repo, mock_mapping_repo)

        # Execute
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        # Assert
        assert len(instructions) == 2
        assert instructions[0]["step_id"] == "step-1"
        assert instructions[1]["step_id"] == "step-2"
        assert instructions[1]["blocked_by"] == ["step-1"]

    def test_derives_subject_from_action_and_target(self, mock_plan_repo, mock_build_state_repo, mock_mapping_repo):
        """Subject should be derived from step action and target."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "src/health.py",
             "description": "Create health module", "needs": []},
        ]

        service = TaskSyncService(mock_plan_repo, mock_build_state_repo, mock_mapping_repo)
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        assert "Create" in instructions[0]["subject"]
        assert "health" in instructions[0]["subject"].lower()

    def test_derives_active_form_in_present_continuous(self, mock_plan_repo, mock_build_state_repo, mock_mapping_repo):
        """activeForm should be present continuous tense."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "src/health.py",
             "description": "Create health module", "needs": []},
        ]

        service = TaskSyncService(mock_plan_repo, mock_build_state_repo, mock_mapping_repo)
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        # "Create" -> "Creating"
        assert instructions[0]["activeForm"].startswith("Creating")

    def test_creates_task_mapping_records(self, mock_plan_repo, mock_build_state_repo, mock_mapping_repo):
        """Should create TaskMapping records in database."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "x.py",
             "description": "Test", "needs": []},
        ]

        service = TaskSyncService(mock_plan_repo, mock_build_state_repo, mock_mapping_repo)
        service.create_tasks_from_plan("plan-123", "session-abc")

        mock_mapping_repo.create.assert_called_once()
        call_args = mock_mapping_repo.create.call_args
        assert call_args.kwargs["plan_id"] == "plan-123"
        assert call_args.kwargs["step_id"] == "step-1"


class TestSyncTaskStateToDb:
    """Tests for TaskSyncService.sync_task_state_to_db()"""

    def test_updates_step_states_from_task_states(self):
        """Should update StepState status based on Task status."""
        from portal.services.task_sync_service import TaskSyncService

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = [
            {"step_id": "step-1", "session_task_id": "1"},
            {"step_id": "step-2", "session_task_id": "2"},
        ]
        mock_build_state_repo = Mock()

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)

        task_states = [
            {"id": "1", "status": "completed"},
            {"id": "2", "status": "in_progress"},
        ]

        service.sync_task_state_to_db("plan-123", task_states)

        # Verify set_step_state called for each
        assert mock_build_state_repo.set_step_state.call_count == 2

    def test_handles_missing_task_mapping(self):
        """Should handle tasks without mapping gracefully."""
        from portal.services.task_sync_service import TaskSyncService

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = [
            {"step_id": "step-1", "session_task_id": "1"},
        ]
        mock_build_state_repo = Mock()

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)

        # Task "2" has no mapping
        task_states = [
            {"id": "1", "status": "completed"},
            {"id": "2", "status": "completed"},  # No mapping for this
        ]

        # Should not raise
        service.sync_task_state_to_db("plan-123", task_states)

        # Only step-1 should be updated
        assert mock_build_state_repo.set_step_state.call_count == 1

    def test_updates_task_mapping_status(self):
        """Should update TaskMapping status when syncing."""
        from portal.services.task_sync_service import TaskSyncService

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = [
            {"step_id": "step-1", "session_task_id": "1", "plan_id": "plan-123"},
        ]
        mock_build_state_repo = Mock()

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)

        task_states = [
            {"id": "1", "status": "completed"},
        ]

        service.sync_task_state_to_db("plan-123", task_states)

        # Should also update the mapping status
        mock_mapping_repo.update_status.assert_called()


class TestRestoreTasksForResume:
    """Tests for TaskSyncService.restore_tasks_for_resume()"""

    def test_generates_resume_context_with_completed_steps(self):
        """Should generate context listing completed steps to skip."""
        from portal.services.task_sync_service import TaskSyncService

        mock_build_state_repo = Mock()
        mock_build_state_repo.get.return_value = {
            "completed_steps": ["step-1", "step-2"],
            "failed_steps": [],
        }
        mock_build_state_repo.get_step_states.return_value = [
            {"step_id": "step-1", "status": "completed"},
            {"step_id": "step-2", "status": "completed"},
            {"step_id": "step-3", "status": "pending"},
        ]

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = [
            {"step_id": "step-1", "task_subject": "Create health route", "status": "completed"},
            {"step_id": "step-2", "task_subject": "Register router", "status": "completed"},
            {"step_id": "step-3", "task_subject": "Add tests", "status": "pending"},
        ]

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)
        context = service.restore_tasks_for_resume("plan-123", "new-session")

        assert "step-1" in context
        assert "step-2" in context
        assert "completed" in context.lower() or "skip" in context.lower()

    def test_includes_failed_steps_for_retry(self):
        """Should include failed steps that may be retried."""
        from portal.services.task_sync_service import TaskSyncService

        mock_build_state_repo = Mock()
        mock_build_state_repo.get.return_value = {
            "completed_steps": ["step-1"],
            "failed_steps": ["step-2"],
        }
        mock_build_state_repo.get_step_states.return_value = []

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = [
            {"step_id": "step-1", "task_subject": "Step 1", "status": "completed"},
            {"step_id": "step-2", "task_subject": "Step 2", "status": "failed"},
        ]

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)
        context = service.restore_tasks_for_resume("plan-123", "new-session")

        assert "step-2" in context
        assert "failed" in context.lower() or "retry" in context.lower()

    def test_returns_empty_context_for_fresh_build(self):
        """Should return minimal context when no prior state exists."""
        from portal.services.task_sync_service import TaskSyncService

        mock_build_state_repo = Mock()
        mock_build_state_repo.get.return_value = None

        mock_mapping_repo = Mock()
        mock_mapping_repo.get_by_plan.return_value = []

        service = TaskSyncService(Mock(), mock_build_state_repo, mock_mapping_repo)
        context = service.restore_tasks_for_resume("plan-123", "new-session")

        # Should return some context (possibly empty or minimal)
        assert isinstance(context, str)


class TestActiveFormDerivation:
    """Tests for activeForm tense conversion."""

    @pytest.mark.parametrize("action,expected_prefix", [
        ("create", "Creating"),
        ("modify", "Modifying"),
        ("update", "Updating"),
        ("add", "Adding"),
        ("delete", "Deleting"),
        ("remove", "Removing"),
        ("run", "Running"),
        ("execute", "Executing"),
        ("implement", "Implementing"),
        ("configure", "Configuring"),
        ("register", "Registering"),
        ("test", "Testing"),
        ("write", "Writing"),
        ("read", "Reading"),
        ("fix", "Fixing"),
        ("refactor", "Refactoring"),
    ])
    def test_converts_action_to_present_continuous(self, action, expected_prefix):
        """Should convert action verb to present continuous."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo = Mock()
        mock_plan_repo.get_steps.return_value = [
            {"step_id": "1", "action": action, "target": "file.py",
             "description": f"{action.title()} something", "needs": []},
        ]

        service = TaskSyncService(mock_plan_repo, Mock(), Mock())
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        assert instructions[0]["activeForm"].startswith(expected_prefix)


class TestDependencyMapping:
    """Tests for dependency (blockedBy/blocks) handling."""

    def test_maps_needs_to_blocked_by(self):
        """Should convert step 'needs' to task 'blocked_by'."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo = Mock()
        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "a.py",
             "description": "First", "needs": []},
            {"step_id": "step-2", "action": "create", "target": "b.py",
             "description": "Second", "needs": ["step-1"]},
            {"step_id": "step-3", "action": "create", "target": "c.py",
             "description": "Third", "needs": ["step-1", "step-2"]},
        ]

        service = TaskSyncService(mock_plan_repo, Mock(), Mock())
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        assert instructions[0]["blocked_by"] == []
        assert instructions[1]["blocked_by"] == ["step-1"]
        assert set(instructions[2]["blocked_by"]) == {"step-1", "step-2"}

    def test_computes_blocks_from_blocked_by(self):
        """Should compute 'blocks' (reverse of blocked_by)."""
        from portal.services.task_sync_service import TaskSyncService

        mock_plan_repo = Mock()
        mock_plan_repo.get_steps.return_value = [
            {"step_id": "step-1", "action": "create", "target": "a.py",
             "description": "First", "needs": []},
            {"step_id": "step-2", "action": "create", "target": "b.py",
             "description": "Second", "needs": ["step-1"]},
        ]

        service = TaskSyncService(mock_plan_repo, Mock(), Mock())
        instructions = service.create_tasks_from_plan("plan-123", "session-abc")

        # step-1 blocks step-2
        assert "step-2" in instructions[0]["blocks"]
        # step-2 blocks nothing
        assert instructions[1]["blocks"] == []
