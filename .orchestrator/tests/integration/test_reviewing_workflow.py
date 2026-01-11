"""Integration tests for the ReviewingWorkflow."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure orchestrator is in path (conftest.py also does this)
ORCHESTRATOR_DIR = Path(__file__).parent.parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.reviewing import ReviewingWorkflow, ReviewResult, TechStackInfo


class TestReviewingWorkflowInit:
    """Tests for ReviewingWorkflow initialization."""

    def test_workflow_initialization(self, project_root):
        """Test ReviewingWorkflow can be initialized."""
        workflow = ReviewingWorkflow(project_root=project_root)
        assert workflow.project_root == project_root
        assert workflow.name == "Smart Review Workflow"

    def test_workflow_creates_reviews_dir(self, project_root):
        """Test workflow creates reviews directory."""
        workflow = ReviewingWorkflow(project_root=project_root)
        assert (project_root / ".specs" / "reviews").exists()


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_review_result_creation(self):
        """Test ReviewResult can be created."""
        result = ReviewResult(
            reviewer="python_expert",
            category="tech_expert",
            score=85,
            issues=[{"type": "warning", "message": "Missing type hints"}],
            recommendations=["Add type annotations"]
        )
        assert result.reviewer == "python_expert"
        assert result.score == 85
        assert len(result.issues) == 1


class TestTechStackInfo:
    """Tests for TechStackInfo dataclass."""

    def test_tech_stack_creation(self):
        """Test TechStackInfo can be created."""
        stack = TechStackInfo(
            languages=["python", "javascript"],
            frameworks=["fastapi", "react"],
            tools=["docker", "pytest"],
            recommended_experts=["python", "javascript"]
        )
        assert "python" in stack.languages
        assert "fastapi" in stack.frameworks


class TestReviewingWorkflowHelpers:
    """Tests for helper methods."""

    def test_parse_json_from_response(self, project_root):
        """Test JSON parsing from various formats."""
        workflow = ReviewingWorkflow(project_root=project_root)

        # Code block format
        response = "```json\n{\"score\": 85}\n```"
        result = workflow._parse_json_from_response(response)
        assert result["score"] == 85

        # Plain JSON
        result = workflow._parse_json_from_response('{"key": "value"}')
        assert result["key"] == "value"

    def test_should_skip_path(self, project_root):
        """Test path skip detection."""
        workflow = ReviewingWorkflow(project_root=project_root)

        assert workflow._should_skip_path(Path("project/.git/config"))
        assert workflow._should_skip_path(Path("project/.venv/lib/site.py"))
        assert workflow._should_skip_path(Path("project/__pycache__/module.pyc"))
        assert not workflow._should_skip_path(Path("project/src/main.py"))

    def test_get_python_files(self, project_root):
        """Test Python file discovery with prioritization."""
        # Create Python files
        src_dir = project_root / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("print('main')")
        (src_dir / "utils.py").write_text("def helper(): pass")
        (src_dir / "config.py").write_text("DEBUG = True")

        tests_dir = project_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_main(): pass")

        workflow = ReviewingWorkflow(project_root=project_root)
        files = workflow._get_python_files(max_files=10)

        # Should find files
        assert len(files) >= 3

        # main.py should be prioritized (lower priority number)
        file_names = [f.name for f in files]
        main_idx = file_names.index("main.py") if "main.py" in file_names else 999
        test_idx = file_names.index("test_main.py") if "test_main.py" in file_names else -1

        # Tests should come after main files
        if main_idx != 999 and test_idx != -1:
            assert main_idx < test_idx

    def test_smart_truncate_code(self, project_root):
        """Test smart code truncation preserves imports and definitions."""
        workflow = ReviewingWorkflow(project_root=project_root)

        code = '''import os
import sys
from pathlib import Path

# Long comment section...
# More comments...

class MyClass:
    """Docstring"""
    def method(self):
        # implementation
        pass

def function():
    """Another docstring"""
    return None
''' + "# filler\n" * 100

        truncated = workflow._smart_truncate_code(code, 500)

        # Should preserve imports
        assert "import os" in truncated
        # Should try to preserve class/function definitions
        assert "class MyClass" in truncated or "def " in truncated

    def test_read_code_samples(self, project_root):
        """Test reading code samples for review."""
        # Create Python files
        src_dir = project_root / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("def hello():\n    return 'hello'\n")

        workflow = ReviewingWorkflow(project_root=project_root)
        stack_info = TechStackInfo(
            languages=["python"],
            frameworks=[],
            tools=[],
            recommended_experts=[]
        )

        samples = workflow._read_code_samples("python", stack_info, max_chars=5000)

        assert "def hello" in samples
        assert "app.py" in samples


class TestReviewingWorkflowExecution:
    """Tests for reviewing workflow execution."""

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_success(self, mock_run_agent, project_root, completed_plan, mock_agent_result):
        """Test successful review workflow."""
        # Create some source code to review
        src_dir = project_root / "src"
        src_dir.mkdir(exist_ok=True)
        (src_dir / "app.py").write_text("def main(): pass")

        mock_run_agent.side_effect = [
            # Stack detector
            mock_agent_result(
                content='```json\n{"languages": ["python"], "frameworks": [], "tools": [], "recommended_experts": ["python"]}\n```',
                agent_name="stack_detector"
            ),
            # Compliance checker
            mock_agent_result(
                content='```json\n{"compliance_score": 90, "missing_items": [], "deviations": []}\n```',
                agent_name="compliance_checker"
            ),
            # Standards checker
            mock_agent_result(
                content='```json\n{"overall_score": 85, "critical_issues": [], "recommendations": ["Add tests"]}\n```',
                agent_name="standards_checker"
            ),
            # Report generator
            mock_agent_result(
                content="# Review Report\n\nOverall: Good",
                agent_name="report_generator"
            ),
        ]

        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run(str(completed_plan))

        assert result.success
        assert result.output_file is not None
        assert "review" in result.output_file.name

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_detects_tech_stack(self, mock_run_agent, project_root, completed_plan, mock_agent_result):
        """Test review correctly detects tech stack."""
        # Create pyproject.toml
        (project_root / "pyproject.toml").write_text("""
[project]
name = "test"
dependencies = ["fastapi", "sqlalchemy"]
""")

        mock_run_agent.side_effect = [
            mock_agent_result(
                content='{"languages": ["python"], "frameworks": ["fastapi", "sqlalchemy"], "tools": ["pytest"], "recommended_experts": ["python", "sql"]}',
                agent_name="stack_detector"
            ),
            mock_agent_result(content='{"compliance_score": 80}', agent_name="compliance_checker"),
            mock_agent_result(content='{"overall_score": 75}', agent_name="standards_checker"),
            mock_agent_result(content="Report", agent_name="report_generator"),
        ]

        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run(str(completed_plan))

        assert result.success
        assert "python" in result.data["stack"]["languages"]

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_handles_missing_plan(self, mock_run_agent, project_root, mock_agent_result):
        """Test review handles missing plan file."""
        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run("nonexistent.md")

        assert not result.success
        assert "not found" in result.error.lower()

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_generates_fallback_report(self, mock_run_agent, project_root, completed_plan, mock_agent_result):
        """Test fallback report generation when report_generator fails."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content='{"languages": ["python"], "frameworks": [], "tools": [], "recommended_experts": []}',
                agent_name="stack_detector"
            ),
            mock_agent_result(content='{"compliance_score": 70}', agent_name="compliance_checker"),
            mock_agent_result(content='{"overall_score": 65}', agent_name="standards_checker"),
            # Report generator fails
            mock_agent_result(
                content="",
                agent_name="report_generator",
                success=False,
                error="Generator error"
            ),
        ]

        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run(str(completed_plan))

        # Should still succeed with fallback report
        assert result.success
        assert result.output_file.exists()


class TestReviewingWorkflowOutput:
    """Tests for review output."""

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_report_saved_to_reviews_dir(self, mock_run_agent, project_root, completed_plan, mock_agent_result):
        """Test review report is saved to reviews directory."""
        mock_run_agent.side_effect = [
            mock_agent_result(content='{"languages": ["python"]}', agent_name="stack_detector"),
            mock_agent_result(content='{"compliance_score": 80}', agent_name="compliance_checker"),
            mock_agent_result(content='{"overall_score": 75}', agent_name="standards_checker"),
            mock_agent_result(content="# Report", agent_name="report_generator"),
        ]

        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run(str(completed_plan))

        assert result.success
        assert "reviews" in str(result.output_file.parent)

    @patch('workflows.reviewing.ReviewingWorkflow.run_agent')
    def test_review_returns_scores_in_data(self, mock_run_agent, project_root, completed_plan, mock_agent_result):
        """Test review returns scores in result data."""
        mock_run_agent.side_effect = [
            mock_agent_result(content='{"languages": ["python"]}', agent_name="stack_detector"),
            mock_agent_result(content='{"compliance_score": 85}', agent_name="compliance_checker"),
            mock_agent_result(content='{"overall_score": 80}', agent_name="standards_checker"),
            mock_agent_result(content="Report", agent_name="report_generator"),
        ]

        workflow = ReviewingWorkflow(project_root=project_root)
        result = workflow.run(str(completed_plan))

        assert "compliance_score" in result.data
        assert "standards_score" in result.data
        assert result.data["compliance_score"] == 85
