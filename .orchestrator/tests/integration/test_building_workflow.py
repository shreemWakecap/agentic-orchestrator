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
        """Test state file is created in centralized state directory."""
        workflow = BuildingWorkflow(project_root=project_root)

        state_file = workflow._get_state_file(pending_plan)

        # State files are stored in specs/state/ directory
        assert state_file.parent.name == "state"
        assert state_file.parent.parent == workflow.specs_dir
        assert ".state.json" in state_file.name


class TestBuildingWorkflowPlanOrganization:
    """Tests for plan file organization."""

    def test_archive_plan_to_completed(self, project_root, pending_plan):
        """Test plan can be archived to completed directory."""
        workflow = BuildingWorkflow(project_root=project_root)

        # Archive to completed
        new_path = workflow._archive_plan(pending_plan.parent, "completed")

        assert new_path.exists()
        assert "completed" in str(new_path.parent)
        assert not pending_plan.parent.exists()

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
