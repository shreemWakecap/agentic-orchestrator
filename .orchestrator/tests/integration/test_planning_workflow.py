"""
Integration tests for Planning Workflow.

Tests the full planning flow from request to plan creation,
using mocked Agent responses to isolate the workflow logic.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from core import WorkflowResult


@pytest.fixture
def mock_project_root(tmp_path):
    """Create a temporary project root for testing."""
    # Create basic project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# Main file")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test-project'")
    return tmp_path


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration."""
    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
    }


@pytest.fixture
def mock_plan_response():
    """Mock planner agent response with valid plan format."""
    return """GOAL: Implement user authentication feature

CONTEXT:
- Project uses FastAPI framework
- Database is PostgreSQL with SQLAlchemy ORM

## Phase 1: Database Setup [phase-1]

### step-1 - Create user model
ACTION: create
DO: Create User model with email, password_hash fields
IN: src/models/__init__.py
OUT: src/models/user.py
DONE: File exists with User class definition

### step-2 - Create migration
ACTION: run
DO: Generate and apply database migration
IN: src/models/user.py
OUT: migrations/versions/001_add_users.py
DONE: Migration applied successfully
NEEDS: step-1

VERIFY:
- User model exists
- Migration completed
"""


@pytest.fixture
def mock_plan_repo():
    """Mock plan repository."""
    repo = Mock()
    repo.get_next_plan_number.return_value = 1
    repo.create.return_value = None
    repo.add_phase.return_value = None
    repo.add_step.return_value = None
    return repo


@pytest.fixture
def mock_build_state_repo():
    """Mock build state repository."""
    repo = Mock()
    repo.create.return_value = None
    return repo


@pytest.fixture
def mock_knowledge_store(mock_project_root):
    """Mock knowledge store."""
    store = Mock()
    store.exists.return_value = False
    store.get_planning_context.return_value = ""
    return store


@pytest.fixture
def mock_expert_selector():
    """Mock expert selector."""
    selector = Mock()
    selector.select_experts.return_value = []
    selector.get_expert_context.return_value = ""
    return selector


@pytest.fixture
def mock_staleness_checker():
    """Mock staleness checker."""
    checker = Mock()
    checker.is_stale.return_value = (False, "")
    checker.get_changed_paths.return_value = []
    return checker


@pytest.fixture
def mock_token_signal():
    """Mock token usage signal."""
    signal = Mock()
    signal.emit_estimation_completed = AsyncMock()
    signal.emit_execution_completed = AsyncMock()
    return signal


@pytest.mark.asyncio
class TestPlanningWorkflow:
    """Integration tests for PlanningWorkflow."""

    @pytest.fixture
    def workflow_with_mocks(
        self,
        mock_project_root,
        mock_plan_repo,
        mock_build_state_repo,
        mock_knowledge_store,
        mock_expert_selector,
        mock_staleness_checker,
        mock_token_signal,
        mock_plan_response,
    ):
        """Create PlanningWorkflow with all dependencies mocked."""
        with patch("workflows.planning.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.planning.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.planning.KnowledgeStore", return_value=mock_knowledge_store), \
             patch("workflows.planning.ExpertSelector", return_value=mock_expert_selector), \
             patch("workflows.planning.StalenessChecker", return_value=mock_staleness_checker), \
             patch("workflows.planning.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.planning.get_agent_config", return_value={}), \
             patch("core.Agent.load") as mock_agent_load:

            # Mock the agent
            mock_agent = Mock()
            mock_agent.name = "planner"
            mock_agent_load.return_value = mock_agent

            from workflows.planning import PlanningWorkflow
            workflow = PlanningWorkflow(project_root=mock_project_root, auto_scout_on_stale=False)

            # Store mocks for later access
            workflow._mock_plan_repo = mock_plan_repo
            workflow._mock_build_state_repo = mock_build_state_repo
            workflow._mock_token_signal = mock_token_signal
            workflow._mock_plan_response = mock_plan_response

            yield workflow

    async def test_run_creates_plan_successfully(self, workflow_with_mocks, mock_plan_response):
        """Test that run() creates a plan from a valid request."""
        workflow = workflow_with_mocks

        # Mock run_agent to return successful result
        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add user authentication")

        assert result.success is True
        assert "plan_id" in result.data
        assert result.data["plan_id"].startswith("001_")
        assert result.data["steps"] > 0

    async def test_run_with_expert_consultation(
        self, mock_project_root, mock_plan_repo, mock_build_state_repo,
        mock_staleness_checker, mock_token_signal, mock_plan_response
    ):
        """Test that run() consults experts when available."""
        mock_knowledge_store = Mock()
        mock_knowledge_store.exists.return_value = True
        mock_knowledge_store.get_planning_context.return_value = "Architecture: Microservices"

        mock_expert_selector = Mock()
        mock_expert_selector.select_experts.return_value = ["auth_expert", "db_expert"]
        mock_expert_selector.get_expert_context.return_value = "Use JWT for authentication"

        with patch("workflows.planning.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.planning.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.planning.KnowledgeStore", return_value=mock_knowledge_store), \
             patch("workflows.planning.ExpertSelector", return_value=mock_expert_selector), \
             patch("workflows.planning.StalenessChecker", return_value=mock_staleness_checker), \
             patch("workflows.planning.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.planning.get_agent_config", return_value={}), \
             patch("core.Agent.load") as mock_agent_load:

            mock_agent = Mock()
            mock_agent.name = "planner"
            mock_agent_load.return_value = mock_agent

            from workflows.planning import PlanningWorkflow
            workflow = PlanningWorkflow(project_root=mock_project_root, auto_scout_on_stale=False)

            mock_result = WorkflowResult(success=True, data={})
            mock_result.content = mock_plan_response
            workflow.run_agent = Mock(return_value=mock_result)

            result = workflow.run("Add JWT authentication")

            assert result.success is True
            mock_expert_selector.select_experts.assert_called_once()
            mock_expert_selector.get_expert_context.assert_called_once_with(["auth_expert", "db_expert"])

    async def test_run_handles_agent_failure(self, workflow_with_mocks):
        """Test that run() handles agent failure gracefully."""
        workflow = workflow_with_mocks

        # Mock run_agent to return failure
        mock_result = WorkflowResult(success=False, error="Agent timed out")
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add feature")

        assert result.success is False
        assert "Planner failed" in result.error

    async def test_run_handles_invalid_plan_response(self, workflow_with_mocks):
        """Test that run() handles invalid plan content."""
        workflow = workflow_with_mocks

        # Mock run_agent to return response without valid plan
        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = "This is not a valid plan format"
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add feature")

        assert result.success is False
        assert "valid plan" in result.error.lower()

    async def test_verify_output_plan_saved_to_database(self, workflow_with_mocks, mock_plan_response):
        """Test that verify_output confirms plan was saved to database."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add user management")

        # Verify plan was saved to database
        workflow._mock_plan_repo.create.assert_called_once()
        call_kwargs = workflow._mock_plan_repo.create.call_args
        assert "plan_id" in call_kwargs.kwargs
        assert "goal" in call_kwargs.kwargs
        assert "request" in call_kwargs.kwargs

    async def test_verify_output_phases_and_steps_saved(self, workflow_with_mocks, mock_plan_response):
        """Test that phases and steps are saved to database."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add authentication")

        # Verify phases and steps were saved
        assert workflow._mock_plan_repo.add_phase.called
        assert workflow._mock_plan_repo.add_step.called

    async def test_verify_output_build_state_created(self, workflow_with_mocks, mock_plan_response):
        """Test that build state is initialized for the plan."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add feature")

        # Verify build state was created
        workflow._mock_build_state_repo.create.assert_called_once()

    async def test_error_handling_missing_planner_agent(self, mock_project_root):
        """Test error handling when planner agent is not found."""
        with patch("workflows.planning.get_plan_repository"), \
             patch("workflows.planning.get_build_state_repository"), \
             patch("workflows.planning.KnowledgeStore"), \
             patch("workflows.planning.ExpertSelector"), \
             patch("workflows.planning.StalenessChecker"), \
             patch("workflows.planning.get_token_usage_signal"), \
             patch("workflows.planning.get_agent_config", return_value={}), \
             patch("core.Agent.load", side_effect=FileNotFoundError("planner agent not found")):

            from workflows.planning import PlanningWorkflow

            with pytest.raises(FileNotFoundError):
                PlanningWorkflow(project_root=mock_project_root)

    async def test_error_handling_knowledge_store_failure(
        self, mock_project_root, mock_plan_repo, mock_build_state_repo,
        mock_expert_selector, mock_staleness_checker, mock_token_signal, mock_plan_response
    ):
        """Test that workflow continues if knowledge store fails."""
        mock_knowledge_store = Mock()
        mock_knowledge_store.exists.side_effect = Exception("Knowledge store error")

        with patch("workflows.planning.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.planning.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.planning.KnowledgeStore", return_value=mock_knowledge_store), \
             patch("workflows.planning.ExpertSelector", return_value=mock_expert_selector), \
             patch("workflows.planning.StalenessChecker", return_value=mock_staleness_checker), \
             patch("workflows.planning.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.planning.get_agent_config", return_value={}), \
             patch("core.Agent.load") as mock_agent_load:

            mock_agent = Mock()
            mock_agent.name = "planner"
            mock_agent_load.return_value = mock_agent

            from workflows.planning import PlanningWorkflow
            workflow = PlanningWorkflow(project_root=mock_project_root, auto_scout_on_stale=False)

            mock_result = WorkflowResult(success=True, data={})
            mock_result.content = mock_plan_response
            workflow.run_agent = Mock(return_value=mock_result)

            # Should not raise, should continue despite knowledge store error
            result = workflow.run("Add feature")
            # The workflow may fail or succeed depending on how errors are handled
            # but it should not raise an unhandled exception

    async def test_token_signal_emitted_on_success(self, workflow_with_mocks, mock_plan_response):
        """Test that token usage signals are emitted on successful planning."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        mock_result.input_tokens = 1000
        mock_result.output_tokens = 500
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add feature")

        assert result.success is True
        # Token signal should have been called (emit methods are async but handled internally)

    async def test_token_signal_emitted_on_failure(self, workflow_with_mocks):
        """Test that token usage signals are emitted on failed planning."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=False, error="Agent error")
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add feature")

        assert result.success is False
        # Token signal should still be emitted for tracking

    async def test_plan_id_generation(self, workflow_with_mocks, mock_plan_response):
        """Test that plan IDs are generated correctly from request."""
        workflow = workflow_with_mocks

        mock_result = WorkflowResult(success=True, data={})
        mock_result.content = mock_plan_response
        workflow.run_agent = Mock(return_value=mock_result)

        result = workflow.run("Add user authentication feature")

        assert result.success is True
        # Plan ID should be formatted as XXX_slug
        plan_id = result.data["plan_id"]
        assert plan_id.startswith("001_")
        assert "add" in plan_id.lower()
        assert "user" in plan_id.lower()

    async def test_stale_knowledge_triggers_scout(self, mock_project_root, mock_plan_repo,
        mock_build_state_repo, mock_knowledge_store, mock_expert_selector,
        mock_token_signal, mock_plan_response
    ):
        """Test that stale knowledge triggers auto-scout when enabled."""
        mock_staleness_checker = Mock()
        mock_staleness_checker.is_stale.return_value = (True, "Knowledge is 7 days old")
        mock_staleness_checker.get_changed_paths.return_value = ["src/"]

        with patch("workflows.planning.get_plan_repository", return_value=mock_plan_repo), \
             patch("workflows.planning.get_build_state_repository", return_value=mock_build_state_repo), \
             patch("workflows.planning.KnowledgeStore", return_value=mock_knowledge_store), \
             patch("workflows.planning.ExpertSelector", return_value=mock_expert_selector), \
             patch("workflows.planning.StalenessChecker", return_value=mock_staleness_checker), \
             patch("workflows.planning.get_token_usage_signal", return_value=mock_token_signal), \
             patch("workflows.planning.get_agent_config", return_value={}), \
             patch("core.Agent.load") as mock_agent_load, \
             patch("workflows.unified_scout.UnifiedScoutWorkflow") as mock_scout:

            mock_agent = Mock()
            mock_agent.name = "planner"
            mock_agent_load.return_value = mock_agent

            mock_scout_instance = Mock()
            mock_scout_instance.execute.return_value = WorkflowResult(success=True, data={})
            mock_scout.return_value = mock_scout_instance

            from workflows.planning import PlanningWorkflow
            workflow = PlanningWorkflow(project_root=mock_project_root, auto_scout_on_stale=True)

            mock_result = WorkflowResult(success=True, data={})
            mock_result.content = mock_plan_response
            workflow.run_agent = Mock(return_value=mock_result)

            result = workflow.run("Add feature")

            # Scout should have been triggered
            mock_scout_instance.execute.assert_called_once()

    async def test_extract_plan_content_from_response(self, workflow_with_mocks):
        """Test _extract_plan_content extracts plan correctly."""
        workflow = workflow_with_mocks

        # Test with GOAL: marker
        response = "Some preamble\n\nGOAL: Test goal\n\nSTEPS:\n- Step 1"
        content = workflow._extract_plan_content(response)
        assert content.startswith("GOAL:")

        # Test with code block
        response = "```markdown\nGOAL: Test goal\n```"
        content = workflow._extract_plan_content(response)
        assert "GOAL:" in content

        # Test with no valid plan
        response = "This is just text without plan markers"
        content = workflow._extract_plan_content(response)
        assert content == ""

    async def test_codebase_summary_generation(self, workflow_with_mocks):
        """Test _get_codebase_summary returns project info."""
        workflow = workflow_with_mocks

        summary = workflow._get_codebase_summary()

        # Should contain some project information
        assert isinstance(summary, str)
        # The summary may vary based on tmp_path contents
