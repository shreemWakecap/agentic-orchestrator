"""Integration tests for the PlanningWorkflow."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure orchestrator is in path (conftest.py also does this)
ORCHESTRATOR_DIR = Path(__file__).parent.parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.planning import PlanningWorkflow


class TestPlanningWorkflowSimple:
    """Tests for simple planning workflow."""

    def test_workflow_initialization(self, project_root):
        """Test PlanningWorkflow can be initialized."""
        workflow = PlanningWorkflow(project_root=project_root)
        assert workflow.project_root == project_root
        assert workflow.name == "Smart Planning Workflow"

    def test_workflow_creates_output_dir(self, project_root):
        """Test workflow creates output directory."""
        workflow = PlanningWorkflow(project_root=project_root)
        assert (project_root / ".specs" / "pending").exists()

    def test_generate_filename(self, project_root):
        """Test filename generation from request."""
        workflow = PlanningWorkflow(project_root=project_root)

        filename = workflow._generate_filename("Add user authentication feature")
        assert filename.endswith(".md")
        assert "add" not in filename.lower()  # Stop words removed
        assert "user" in filename or "authentication" in filename

    def test_parse_json_from_response(self, project_root):
        """Test JSON parsing from agent response."""
        workflow = PlanningWorkflow(project_root=project_root)

        # Test with JSON in code block
        response = """Here's the analysis:
```json
{"complexity": "simple", "needs_decomposition": false}
```
Additional text."""
        result = workflow._parse_json_from_response(response)
        assert result["complexity"] == "simple"
        assert result["needs_decomposition"] is False

        # Test with plain JSON
        result = workflow._parse_json_from_response('{"key": "value"}')
        assert result["key"] == "value"

    def test_get_codebase_context(self, project_root):
        """Test codebase context gathering."""
        # Create some project structure
        (project_root / "src").mkdir()
        (project_root / "src" / "main.py").write_text("print('hello')")
        (project_root / "pyproject.toml").write_text("[project]\nname='test'")

        workflow = PlanningWorkflow(project_root=project_root)
        context = workflow._get_codebase_context()

        assert "src" in context
        assert "pyproject.toml" in context

    def test_smart_truncate(self, project_root):
        """Test smart text truncation."""
        workflow = PlanningWorkflow(project_root=project_root)

        # Short text returns unchanged
        short = "Hello world"
        assert workflow._smart_truncate(short, 100) == short

        # Long text is truncated
        long_text = "Line 1\nLine 2\nLine 3\n" * 100
        truncated = workflow._smart_truncate(long_text, 100)
        assert len(truncated) <= 100
        assert "truncated" in truncated.lower()

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_simple_planning_success(self, mock_run_agent, project_root, mock_agent_result):
        """Test successful simple planning workflow."""
        # Setup mock responses
        mock_run_agent.side_effect = [
            # Analyzer
            mock_agent_result(
                content='```json\n{"complexity": "simple", "needs_decomposition": false}\n```',
                agent_name="analyzer"
            ),
            # Scout
            mock_agent_result(content="Found: src/, tests/", agent_name="scout"),
            # Architect
            mock_agent_result(content="## Architecture\nUse modular design", agent_name="architect"),
            # Planner
            mock_agent_result(content="## Steps\n1. Create file\n2. Add tests", agent_name="planner"),
            # Validator
            mock_agent_result(content="Plan is valid", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add a logging feature")

        assert result.success
        assert result.output_file is not None
        assert result.output_file.exists()

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_planning_handles_analyzer_failure(self, mock_run_agent, project_root, mock_agent_result):
        """Test planning falls back to simple when analyzer fails."""
        # Setup mock responses - analyzer fails, then simple planning succeeds
        mock_run_agent.side_effect = [
            # Analyzer fails
            mock_agent_result(
                content="",
                agent_name="analyzer",
                success=False,
                error="Analyzer timeout"
            ),
            # Simple planning agents
            mock_agent_result(content="Codebase context", agent_name="scout"),
            mock_agent_result(content="Architecture", agent_name="architect"),
            mock_agent_result(content="Plan steps", agent_name="planner"),
            mock_agent_result(content="Valid", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add feature")

        # Should still succeed via fallback
        assert result.success

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_planning_returns_error_on_critical_failure(self, mock_run_agent, project_root, mock_agent_result):
        """Test planning returns error when scout fails."""
        mock_run_agent.side_effect = [
            # Analyzer (simple)
            mock_agent_result(content='{"complexity": "simple"}', agent_name="analyzer"),
            # Scout fails
            mock_agent_result(
                content="",
                agent_name="scout",
                success=False,
                error="Scout failed"
            ),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add feature")

        assert not result.success
        assert "Scout failed" in result.error


class TestPlanningWorkflowComplex:
    """Tests for complex/decomposed planning workflow."""

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_complex_planning_triggered(self, mock_run_agent, project_root, mock_agent_result):
        """Test complex planning is triggered for complex requests."""
        # Setup: analyzer reports complex
        mock_run_agent.side_effect = [
            # Analyzer - complex
            mock_agent_result(
                content='```json\n{"complexity": "complex", "needs_decomposition": true, "strategy": "decompose_sequential"}\n```',
                agent_name="analyzer"
            ),
            # Global scout
            mock_agent_result(content="Global codebase context", agent_name="scout"),
            # Decomposer
            mock_agent_result(
                content='```json\n{"sub_features": [{"id": "sf1", "name": "Auth", "description": "User auth", "context_summary": ""}]}\n```',
                agent_name="decomposer"
            ),
            # Sub-feature scout
            mock_agent_result(content="Auth context", agent_name="scout"),
            # Sub-feature architect
            mock_agent_result(content="Auth architecture", agent_name="architect"),
            # Sub-feature planner
            mock_agent_result(content="Auth steps", agent_name="planner"),
            # Synthesizer
            mock_agent_result(content="Master plan", agent_name="synthesizer"),
            # Validator
            mock_agent_result(content="Valid", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Build complete auth system with OAuth, SAML, and 2FA")

        assert result.success
        assert result.output_file is not None
        # Complex plans get "master-" prefix
        assert "master-" in result.output_file.name

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_complex_falls_back_to_simple(self, mock_run_agent, project_root, mock_agent_result):
        """Test complex planning falls back when decomposer fails."""
        mock_run_agent.side_effect = [
            # Analyzer - complex
            mock_agent_result(
                content='{"complexity": "complex", "needs_decomposition": true}',
                agent_name="analyzer"
            ),
            # Global scout
            mock_agent_result(content="Context", agent_name="scout"),
            # Decomposer - returns no sub_features
            mock_agent_result(
                content='{"sub_features": []}',
                agent_name="decomposer"
            ),
            # Falls back to simple planning
            mock_agent_result(content="Scout", agent_name="scout"),
            mock_agent_result(content="Arch", agent_name="architect"),
            mock_agent_result(content="Plan", agent_name="planner"),
            mock_agent_result(content="Valid", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Complex feature")

        assert result.success

    def test_adaptive_context_limits(self, project_root):
        """Test context limits scale with number of sub-features."""
        workflow = PlanningWorkflow(project_root=project_root)

        # Single feature gets full context
        limits_1 = workflow._get_context_limits(1)

        # Many features get reduced context
        limits_5 = workflow._get_context_limits(5)

        assert limits_1[0] >= limits_5[0]  # Codebase limit reduced
        assert limits_1[1] >= limits_5[1]  # Scout limit reduced


class TestPlanningWorkflowOutput:
    """Tests for planning workflow output."""

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_plan_file_created_in_pending(self, mock_run_agent, project_root, mock_agent_result):
        """Test plan file is created in pending directory."""
        mock_run_agent.side_effect = [
            mock_agent_result(content='{"complexity": "simple"}', agent_name="analyzer"),
            mock_agent_result(content="Scout", agent_name="scout"),
            mock_agent_result(content="Arch", agent_name="architect"),
            mock_agent_result(content="Plan", agent_name="planner"),
            mock_agent_result(content="Valid", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add logging")

        assert result.output_file is not None
        assert "pending" in str(result.output_file.parent)

    @patch('workflows.planning.PlanningWorkflow.run_agent')
    def test_plan_contains_sections(self, mock_run_agent, project_root, mock_agent_result):
        """Test generated plan has required sections."""
        mock_run_agent.side_effect = [
            mock_agent_result(content='{"complexity": "simple"}', agent_name="analyzer"),
            mock_agent_result(content="# Context\nFound src/", agent_name="scout"),
            mock_agent_result(content="# Architecture\nModular", agent_name="architect"),
            mock_agent_result(content="# Plan\n1. Step one", agent_name="planner"),
            mock_agent_result(content="Validated", agent_name="validator"),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add feature")

        plan_content = result.output_file.read_text()

        assert "## Overview" in plan_content or "# Plan" in plan_content
        assert "Architecture" in plan_content
        assert "Plan" in plan_content or "Implementation" in plan_content
