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
        assert (project_root / ".orchestrator" / "specs" / "pending").exists()

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
        # Setup mock responses with proper AGENT_OUTPUT_MARKERS
        mock_run_agent.side_effect = [
            # Analyzer
            mock_agent_result(
                content='```json\n{"complexity": "simple", "needs_decomposition": false}\n```',
                agent_name="analyzer"
            ),
            # Scout - needs PROJECT_TYPE: or STRUCTURE:
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/, tests/, config/\nPATTERNS: Standard layout\nRELEVANT_FILES: src/main.py",
                agent_name="scout"
            ),
            # Architect - needs APPROACH: or FILES_TO_
            mock_agent_result(
                content="APPROACH: Modular design with separation of concerns\nFILES_TO_CREATE: src/logging.py\nFILES_TO_MODIFY: src/main.py",
                agent_name="architect"
            ),
            # Planner - needs GOAL:, STEPS:, or DO:
            mock_agent_result(
                content="GOAL: Add logging feature\nSTEPS:\n1. Create logging module\n2. Add tests\nDO: Implement step by step",
                agent_name="planner"
            ),
            # Validator - needs JSON with status and score >= 70
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 85, "summary": "Plan is valid and complete. All steps are well-defined and achievable."}\n```',
                agent_name="validator"
            ),
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
            # Simple planning agents with proper markers
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/, tests/\nPATTERNS: Standard\nRELEVANT_FILES: main.py",
                agent_name="scout"
            ),
            mock_agent_result(
                content="APPROACH: Simple modular design\nFILES_TO_CREATE: feature.py\nFILES_TO_MODIFY: None",
                agent_name="architect"
            ),
            mock_agent_result(
                content="GOAL: Add feature\nSTEPS:\n1. Create feature file\n2. Write tests\nDO: Implement",
                agent_name="planner"
            ),
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 85, "summary": "Plan is valid and complete."}\n```',
                agent_name="validator"
            ),
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
        # Call sequence for complex planning:
        # 1. analyzer, 2. global scout, 3. prelim architect, 4. decomposer,
        # 5. sub-feature scout, 6. sub-feature architect, 7. sub-feature planner,
        # 8. synthesizer, 9. validator
        mock_run_agent.side_effect = [
            # Analyzer - complex
            mock_agent_result(
                content='```json\n{"complexity": "complex", "needs_decomposition": true, "strategy": "decompose_sequential"}\n```',
                agent_name="analyzer"
            ),
            # Global scout (Phase 2a) - needs PROJECT_TYPE: or STRUCTURE:
            mock_agent_result(
                content="PROJECT_TYPE: TypeScript\nSTRUCTURE: src/, lib/, auth/\nPATTERNS: Modular auth\nRELEVANT_FILES: src/auth/index.ts",
                agent_name="scout"
            ),
            # Preliminary architect (Phase 2b) - needs APPROACH: or FILES_TO_
            mock_agent_result(
                content="APPROACH: Multi-provider auth system\nFILES_TO_CREATE: src/auth/oauth.ts, src/auth/saml.ts\nFILES_TO_MODIFY: src/config.ts",
                agent_name="architect"
            ),
            # Decomposer (Phase 2c) - needs 50+ chars
            mock_agent_result(
                content='DECOMPOSITION ANALYSIS:\n```json\n{"sub_features": [{"id": "sf1", "name": "Auth", "description": "User authentication module with OAuth2 support", "context_summary": "Authentication system integration"}]}\n```',
                agent_name="decomposer"
            ),
            # Sub-feature scout (Phase 3) - needs PROJECT_TYPE: or STRUCTURE:
            mock_agent_result(
                content="PROJECT_TYPE: TypeScript\nSTRUCTURE: auth/\nPATTERNS: OAuth flow\nRELEVANT_FILES: auth/oauth.ts",
                agent_name="scout"
            ),
            # Sub-feature architect - needs APPROACH: or FILES_TO_
            mock_agent_result(
                content="APPROACH: OAuth2 with PKCE flow\nFILES_TO_CREATE: auth/providers/oauth.ts\nFILES_TO_MODIFY: auth/index.ts",
                agent_name="architect"
            ),
            # Sub-feature planner - needs GOAL:, STEPS:, or DO:
            mock_agent_result(
                content="GOAL: Implement OAuth authentication\nSTEPS:\n1. Create OAuth provider\n2. Add callback handler\nDO: Implement incrementally",
                agent_name="planner"
            ),
            # Synthesizer (Phase 4) - needs GOAL: or STEPS:
            mock_agent_result(
                content="GOAL: Complete auth system implementation\nSTEPS:\n1. OAuth provider\n2. SAML integration\n3. 2FA setup",
                agent_name="synthesizer"
            ),
            # Validator (Phase 5) - needs JSON with status and score >= 70
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 90, "summary": "Comprehensive plan validated successfully. All sub-features are properly integrated."}\n```',
                agent_name="validator"
            ),
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
        # Call sequence: analyzer → scout → architect → decomposer (empty) → fallback to simple
        mock_run_agent.side_effect = [
            # Analyzer - complex
            mock_agent_result(
                content='{"complexity": "complex", "needs_decomposition": true}',
                agent_name="analyzer"
            ),
            # Global scout (Phase 2a) - needs PROJECT_TYPE: or STRUCTURE:
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/, tests/\nPATTERNS: Standard\nRELEVANT_FILES: main.py",
                agent_name="scout"
            ),
            # Preliminary architect (Phase 2b) - needs APPROACH: or FILES_TO_
            mock_agent_result(
                content="APPROACH: Simple modular design\nFILES_TO_CREATE: feature.py\nFILES_TO_MODIFY: main.py",
                agent_name="architect"
            ),
            # Decomposer - returns no sub_features (Phase 2c) - needs 50+ chars
            mock_agent_result(
                content='DECOMPOSITION ANALYSIS: Feature is simple enough for direct implementation.\n```json\n{"sub_features": []}\n```',
                agent_name="decomposer"
            ),
            # Falls back to simple planning: scout → architect → planner → validator
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/\nPATTERNS: Standard\nRELEVANT_FILES: main.py",
                agent_name="scout"
            ),
            mock_agent_result(
                content="APPROACH: Direct implementation\nFILES_TO_CREATE: feature.py\nFILES_TO_MODIFY: None",
                agent_name="architect"
            ),
            mock_agent_result(
                content="GOAL: Add feature\nSTEPS:\n1. Create module\n2. Add tests\nDO: Implement",
                agent_name="planner"
            ),
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 85, "summary": "Plan is valid and complete."}\n```',
                agent_name="validator"
            ),
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
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/\nPATTERNS: Standard\nRELEVANT_FILES: main.py",
                agent_name="scout"
            ),
            mock_agent_result(
                content="APPROACH: Add logging module\nFILES_TO_CREATE: src/logging.py\nFILES_TO_MODIFY: None",
                agent_name="architect"
            ),
            mock_agent_result(
                content="GOAL: Add logging\nSTEPS:\n1. Create logger\n2. Configure output\nDO: Implement",
                agent_name="planner"
            ),
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 85, "summary": "Plan is valid and complete."}\n```',
                agent_name="validator"
            ),
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
            mock_agent_result(
                content="PROJECT_TYPE: Python\nSTRUCTURE: src/, tests/\nPATTERNS: Standard layout\nRELEVANT_FILES: src/main.py",
                agent_name="scout"
            ),
            mock_agent_result(
                content="APPROACH: Modular architecture\nFILES_TO_CREATE: src/feature.py\nFILES_TO_MODIFY: src/main.py",
                agent_name="architect"
            ),
            mock_agent_result(
                content="GOAL: Add feature\nSTEPS:\n1. Step one\n2. Step two\nDO: Implement incrementally",
                agent_name="planner"
            ),
            mock_agent_result(
                content='```json\n{"status": "approved", "score": 85, "summary": "Plan validated successfully."}\n```',
                agent_name="validator"
            ),
        ]

        workflow = PlanningWorkflow(project_root=project_root)
        result = workflow.run("Add feature")

        # output_file is now a folder, plan is inside as plan.md
        plan_file = result.output_file / "plan.md"
        plan_content = plan_file.read_text()

        # New plan format has Goal, Context, Steps, Verify sections
        assert "# Plan" in plan_content
        assert "## Goal" in plan_content
        assert "## Context" in plan_content
        assert "## Steps" in plan_content
