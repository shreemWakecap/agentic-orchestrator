"""Integration tests for the BuildingWorkflow."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure orchestrator is in path (conftest.py also does this)
ORCHESTRATOR_DIR = Path(__file__).parent.parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.building import BuildingWorkflow, BuildState, BuildStep, BuildPhase, ParsedPlan


class TestBuildingWorkflowInit:
    """Tests for BuildingWorkflow initialization."""

    def test_workflow_initialization(self, project_root):
        """Test BuildingWorkflow can be initialized."""
        workflow = BuildingWorkflow(project_root=project_root)
        assert workflow.project_root == project_root
        assert workflow.name == "Smart Building Workflow"

    def test_workflow_creates_specs_structure(self, project_root):
        """Test workflow creates .specs directory structure."""
        workflow = BuildingWorkflow(project_root=project_root)

        assert (project_root / ".orchestrator" / "specs" / "pending").exists()
        assert (project_root / ".orchestrator" / "specs" / "in-progress").exists()
        assert (project_root / ".orchestrator" / "specs" / "completed").exists()
        assert (project_root / ".orchestrator" / "specs" / "failed").exists()


class TestBuildState:
    """Tests for BuildState dataclass."""

    def test_build_state_creation(self):
        """Test BuildState can be created."""
        state = BuildState(
            plan_id="test-plan",
            plan_file="/path/to/plan.md",
            status="in_progress",
            started_at="2024-01-15T10:00:00"
        )
        assert state.plan_id == "test-plan"
        assert state.status == "in_progress"
        assert state.completed_steps == []

    def test_build_state_serialization(self):
        """Test BuildState can be serialized to dict."""
        state = BuildState(
            plan_id="test",
            plan_file="/plan.md",
            status="completed",
            started_at="2024-01-15",
            completed_steps=["step1", "step2"]
        )
        data = state.to_dict()

        assert data["plan_id"] == "test"
        assert data["completed_steps"] == ["step1", "step2"]

    def test_build_state_deserialization(self):
        """Test BuildState can be loaded from dict."""
        data = {
            "plan_id": "test",
            "plan_file": "/plan.md",
            "status": "in_progress",
            "started_at": "2024-01-15",
            "current_phase": 1,
            "completed_steps": ["step1"],
            "failed_steps": [],
            "step_results": {},
            "files_created": [],
            "files_modified": []
        }
        state = BuildState.from_dict(data)

        assert state.plan_id == "test"
        assert state.current_phase == 1
        assert "step1" in state.completed_steps


class TestBuildingWorkflowStateManagement:
    """Tests for state persistence and resume."""

    def test_save_and_load_state(self, project_root, pending_plan):
        """Test state can be saved and loaded."""
        workflow = BuildingWorkflow(project_root=project_root)

        # Create state
        workflow.build_state = BuildState(
            plan_id="test",
            plan_file=str(pending_plan),
            status="in_progress",
            started_at="2024-01-15",
            completed_steps=["step1", "step2"]
        )

        # Save
        workflow._save_state(pending_plan)

        # Load
        loaded = workflow._load_state(pending_plan)

        assert loaded is not None
        assert loaded.plan_id == "test"
        assert "step1" in loaded.completed_steps

    def test_state_file_location(self, project_root, pending_plan):
        """Test state file is created next to plan."""
        workflow = BuildingWorkflow(project_root=project_root)

        state_file = workflow._get_state_file(pending_plan)

        assert state_file.parent == pending_plan.parent
        assert state_file.name.startswith(".")
        assert ".state.json" in state_file.name


class TestBuildingWorkflowExecution:
    """Tests for building workflow execution."""

    @patch('workflows.building.BuildingWorkflow.run_agent')
    def test_simple_build_success(self, mock_run_agent, project_root, pending_plan, mock_agent_result):
        """Test successful simple build."""
        # Setup mock responses
        mock_run_agent.side_effect = [
            # Parser
            mock_agent_result(
                content=json.dumps({
                    "plan_id": "test",
                    "plan_type": "simple",
                    "phases": [{
                        "id": "phase1",
                        "name": "Setup",
                        "steps": [{
                            "id": "step1",
                            "action": "create",
                            "target": "src/utils.py",
                            "description": "Create utils file"
                        }]
                    }],
                    "validation_commands": ["python -m pytest"]
                }),
                agent_name="parser"
            ),
            # Builder
            mock_agent_result(
                content="Created src/utils.py",
                agent_name="builder",
                files_created=["src/utils.py"]
            ),
            # Tester
            mock_agent_result(content="Tests passed", agent_name="tester"),
            # Reviewer
            mock_agent_result(content='{"status": "good"}', agent_name="reviewer"),
        ]

        workflow = BuildingWorkflow(project_root=project_root)
        result = workflow.run(str(pending_plan))

        assert result.success
        assert "step1" in result.steps_completed

    @patch('workflows.building.BuildingWorkflow.run_agent')
    def test_build_moves_plan_to_completed(self, mock_run_agent, project_root, pending_plan, mock_agent_result):
        """Test successful build moves plan to completed."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "plan_id": "test", "plan_type": "simple",
                    "phases": [{"id": "p1", "name": "Phase", "steps": [
                        {"id": "s1", "action": "create", "target": "README.md", "description": "Create readme"}
                    ]}],
                    "validation_commands": []
                }),
                agent_name="parser"
            ),
            # Builder for the step
            mock_agent_result(content="Created README.md", agent_name="builder", files_created=["README.md"]),
            # Tester
            mock_agent_result(content="Tests passed", agent_name="tester"),
            # Reviewer
            mock_agent_result(content='{"status": "good"}', agent_name="reviewer"),
        ]

        workflow = BuildingWorkflow(project_root=project_root)
        result = workflow.run(str(pending_plan))

        assert result.success
        # Plan should be in completed folder
        assert "completed" in str(result.output_file)

    @patch('workflows.building.BuildingWorkflow.run_agent')
    def test_build_handles_step_failure(self, mock_run_agent, project_root, pending_plan, mock_agent_result):
        """Test build handles step failure properly."""
        mock_run_agent.side_effect = [
            # Parser
            mock_agent_result(
                content=json.dumps({
                    "plan_id": "test", "plan_type": "simple",
                    "phases": [{
                        "id": "p1", "name": "Phase",
                        "steps": [{"id": "s1", "action": "create", "target": "x.py", "description": "Create"}]
                    }],
                    "validation_commands": []
                }),
                agent_name="parser"
            ),
            # Builder fails
            mock_agent_result(
                content="",
                agent_name="builder",
                success=False,
                error="Could not create file"
            ),
        ]

        workflow = BuildingWorkflow(project_root=project_root)
        result = workflow.run(str(pending_plan))

        assert not result.success
        assert "s1" in result.error

    @patch('workflows.building.BuildingWorkflow.run_agent')
    def test_build_resume_skips_completed_steps(self, mock_run_agent, project_root, pending_plan, mock_agent_result):
        """Test build resume skips already completed steps."""
        # Pre-create state with completed step
        workflow = BuildingWorkflow(project_root=project_root)
        workflow.build_state = BuildState(
            plan_id="test",
            plan_file=str(pending_plan),
            status="in_progress",
            started_at="2024-01-15",
            completed_steps=["step1"]  # Already done
        )
        workflow._save_state(pending_plan)

        # Move plan to in-progress for the test
        in_progress = project_root / ".orchestrator" / "specs" / "in-progress" / pending_plan.name
        pending_plan.rename(in_progress)
        state_file = pending_plan.parent / f".{pending_plan.stem}.state.json"
        if state_file.exists():
            state_file.rename(in_progress.parent / state_file.name)

        mock_run_agent.side_effect = [
            # Parser
            mock_agent_result(
                content=json.dumps({
                    "plan_id": "test", "plan_type": "simple",
                    "phases": [{
                        "id": "p1", "name": "Phase",
                        "steps": [
                            {"id": "step1", "action": "create", "target": "a.py", "description": "Done"},
                            {"id": "step2", "action": "create", "target": "b.py", "description": "New"}
                        ]
                    }],
                    "validation_commands": []
                }),
                agent_name="parser"
            ),
            # Only step2 builder (step1 skipped)
            mock_agent_result(content="Created b.py", agent_name="builder", files_created=["b.py"]),
            mock_agent_result(content="Tests OK", agent_name="tester"),
            mock_agent_result(content='{"status": "good"}', agent_name="reviewer"),
        ]

        workflow2 = BuildingWorkflow(project_root=project_root)
        result = workflow2.run(str(in_progress))

        # Should succeed and have skipped step1
        assert result.success


class TestBuildingWorkflowPlanOrganization:
    """Tests for plan file organization."""

    def test_move_plan_to_destination(self, project_root, pending_plan):
        """Test plan can be moved between directories."""
        workflow = BuildingWorkflow(project_root=project_root)

        # Move to in-progress
        new_path = workflow._move_plan(pending_plan, "in-progress")

        assert new_path.exists()
        assert "in-progress" in str(new_path.parent)
        assert not pending_plan.exists()

    def test_plan_not_found_returns_error(self, project_root):
        """Test workflow handles missing plan."""
        workflow = BuildingWorkflow(project_root=project_root)
        result = workflow.run("nonexistent.md")

        assert not result.success
        assert "not found" in result.error.lower()


class TestBuildingWorkflowHelpers:
    """Tests for helper methods."""

    def test_parse_json_from_response(self, project_root):
        """Test JSON parsing from various response formats."""
        workflow = BuildingWorkflow(project_root=project_root)

        # Code block format
        response = "```json\n{\"key\": \"value\"}\n```"
        result = workflow._parse_json_from_response(response)
        assert result["key"] == "value"

        # Plain JSON
        result = workflow._parse_json_from_response('{"a": 1}')
        assert result["a"] == 1

        # Invalid JSON returns empty dict
        result = workflow._parse_json_from_response("not json")
        assert result == {}

    def test_get_relevant_context_for_modify(self, project_root):
        """Test context gathering for modify operations."""
        # Create file to modify
        src_dir = project_root / "src"
        src_dir.mkdir()
        target = src_dir / "existing.py"
        target.write_text("def hello():\n    pass\n")

        workflow = BuildingWorkflow(project_root=project_root)
        step = BuildStep(
            id="s1",
            action="modify",
            target="src/existing.py",
            description="Modify file"
        )

        context = workflow._get_relevant_context(step)

        assert "def hello" in context
        assert "src/existing.py" in context

    def test_get_relevant_context_for_create(self, project_root):
        """Test context gathering for create operations."""
        # Create parent directory with siblings
        src_dir = project_root / "src"
        src_dir.mkdir()
        (src_dir / "sibling.py").write_text("pass")

        workflow = BuildingWorkflow(project_root=project_root)
        step = BuildStep(
            id="s1",
            action="create",
            target="src/new.py",
            description="Create file"
        )

        context = workflow._get_relevant_context(step)

        assert "sibling.py" in context
