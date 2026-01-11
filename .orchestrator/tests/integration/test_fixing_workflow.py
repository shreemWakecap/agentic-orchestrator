"""Integration tests for the FixingWorkflow."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure orchestrator is in path (conftest.py also does this)
ORCHESTRATOR_DIR = Path(__file__).parent.parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.fixing import FixingWorkflow, FixState, FixInstruction, FixResult, SEVERITY_ORDER


class TestFixingWorkflowInit:
    """Tests for FixingWorkflow initialization."""

    def test_workflow_initialization(self, project_root):
        """Test FixingWorkflow can be initialized."""
        workflow = FixingWorkflow(project_root=project_root)
        assert workflow.project_root == project_root
        assert workflow.name == "Fixing Workflow"

    def test_workflow_creates_fixes_dir(self, project_root):
        """Test workflow creates fixes directory."""
        workflow = FixingWorkflow(project_root=project_root)
        assert (project_root / ".specs" / "fixes").exists()

    def test_workflow_dry_run_mode(self, project_root):
        """Test dry run mode initialization."""
        workflow = FixingWorkflow(project_root=project_root, dry_run=True)
        assert workflow.dry_run is True

    def test_workflow_min_severity(self, project_root):
        """Test min severity filtering."""
        workflow = FixingWorkflow(project_root=project_root, min_severity="high")
        assert workflow.min_severity == "high"


class TestFixState:
    """Tests for FixState dataclass."""

    def test_fix_state_creation(self):
        """Test FixState can be created."""
        state = FixState(
            review_path="/path/to/review.md",
            started_at="2024-01-15T10:00:00",
            status="in_progress"
        )
        assert state.status == "in_progress"
        assert state.fixes_completed == []

    def test_fix_state_serialization(self):
        """Test FixState can be serialized."""
        state = FixState(
            review_path="/review.md",
            started_at="2024-01-15",
            status="completed",
            fixes_completed=["fix1", "fix2"]
        )
        data = state.to_dict()

        assert data["status"] == "completed"
        assert "fix1" in data["fixes_completed"]

    def test_fix_state_save_and_load(self, tmp_path):
        """Test FixState can be saved and loaded."""
        state_file = tmp_path / "state.json"

        state = FixState(
            review_path="/review.md",
            started_at="2024-01-15",
            status="in_progress",
            fixes_completed=["fix1"]
        )
        state.save(state_file)

        loaded = FixState.load(state_file)
        assert loaded is not None
        assert loaded.status == "in_progress"
        assert "fix1" in loaded.fixes_completed


class TestFixInstruction:
    """Tests for FixInstruction dataclass."""

    def test_fix_instruction_creation(self):
        """Test FixInstruction can be created."""
        fix = FixInstruction(
            id="fix1",
            issue_reference="Missing type hints",
            severity="high",
            category="quality",
            file_path="src/main.py",
            fix_type="modify",
            description="Add type hints",
            instructions="Add type annotations to all functions"
        )
        assert fix.id == "fix1"
        assert fix.severity == "high"
        assert fix.fix_type == "modify"


class TestSeverityOrdering:
    """Tests for severity ordering."""

    def test_severity_order(self):
        """Test severity ordering is correct."""
        assert SEVERITY_ORDER["critical"] < SEVERITY_ORDER["high"]
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["medium"]
        assert SEVERITY_ORDER["medium"] < SEVERITY_ORDER["low"]


class TestFixingWorkflowHelpers:
    """Tests for helper methods."""

    def test_parse_json_from_response(self, project_root):
        """Test JSON parsing from various formats."""
        workflow = FixingWorkflow(project_root=project_root)

        # Code block format
        response = "```json\n{\"fixes\": []}\n```"
        result = workflow._parse_json_from_response(response)
        assert "fixes" in result

        # Embedded JSON
        response = "Here's the analysis: {\"key\": \"value\"} and more text"
        result = workflow._parse_json_from_response(response)
        assert result.get("key") == "value"

    def test_extract_plan_reference(self, project_root):
        """Test extracting plan reference from review content."""
        workflow = FixingWorkflow(project_root=project_root)

        content = "# Review Report: user-auth-feature\n\nSome content..."
        ref = workflow._extract_plan_reference(content)
        assert ref == "user-auth-feature"

    def test_get_codebase_context(self, project_root):
        """Test codebase context gathering."""
        # Create Python files
        src_dir = project_root / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("def main(): pass")
        (project_root / "pyproject.toml").write_text("[project]\nname='test'")

        workflow = FixingWorkflow(project_root=project_root)
        context = workflow._get_codebase_context()

        assert "app.py" in context or "src" in context
        assert "pyproject.toml" in context or "[project]" in context

    def test_should_apply_fix_severity_filter(self, project_root):
        """Test severity filtering for fix application."""
        workflow = FixingWorkflow(project_root=project_root, min_severity="high")

        critical_fix = FixInstruction(
            id="f1", issue_reference="", severity="critical",
            category="", file_path="", fix_type="modify",
            description="", instructions=""
        )
        low_fix = FixInstruction(
            id="f2", issue_reference="", severity="low",
            category="", file_path="", fix_type="modify",
            description="", instructions=""
        )

        assert workflow._should_apply_fix(critical_fix) is True
        assert workflow._should_apply_fix(low_fix) is False


class TestFixingWorkflowExecution:
    """Tests for fixing workflow execution."""

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_success(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test successful fixing workflow."""
        mock_run_agent.side_effect = [
            # Fixer agent
            mock_agent_result(
                content=json.dumps({
                    "fixes": [{
                        "id": "fix1",
                        "issue_reference": "Missing type hints",
                        "severity": "medium",
                        "category": "quality",
                        "file_path": "src/main.py",
                        "fix_type": "modify",
                        "description": "Add type hints",
                        "instructions": "Add type annotations"
                    }],
                    "unfixable": []
                }),
                agent_name="fixer"
            ),
            # Builder agent
            mock_agent_result(
                content="Applied fix",
                agent_name="builder",
                files_modified=["src/main.py"]
            ),
        ]

        workflow = FixingWorkflow(project_root=project_root)
        result = workflow.run(str(review_report))

        assert result.success
        assert result.data["fixes_applied"] >= 1

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_dry_run_mode(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test dry run mode doesn't apply fixes."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [{
                        "id": "fix1", "issue_reference": "", "severity": "high",
                        "category": "quality", "file_path": "src/main.py",
                        "fix_type": "modify", "description": "Fix issue",
                        "instructions": "Do something"
                    }],
                    "unfixable": []
                }),
                agent_name="fixer"
            ),
            # No builder call in dry run mode
        ]

        workflow = FixingWorkflow(project_root=project_root, dry_run=True)
        result = workflow.run(str(review_report))

        assert result.success
        assert result.data["dry_run"] is True

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_handles_no_fixable_issues(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test handling when no fixable issues found."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [],
                    "unfixable": [{"issue": "Complex refactoring needed", "reason": "Requires human judgment"}]
                }),
                agent_name="fixer"
            ),
        ]

        workflow = FixingWorkflow(project_root=project_root)
        result = workflow.run(str(review_report))

        assert result.success
        assert result.data["fixes_applied"] == 0
        assert result.data["unfixable"] == 1

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_handles_missing_review(self, mock_run_agent, project_root, mock_agent_result):
        """Test handling missing review file."""
        workflow = FixingWorkflow(project_root=project_root)
        result = workflow.run("nonexistent-review.md")

        assert not result.success
        assert "not found" in result.error.lower()

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_severity_filtering(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test severity-based fix filtering."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [
                        {"id": "f1", "severity": "critical", "issue_reference": "",
                         "category": "", "file_path": "a.py", "fix_type": "modify",
                         "description": "Critical fix", "instructions": "Fix it"},
                        {"id": "f2", "severity": "low", "issue_reference": "",
                         "category": "", "file_path": "b.py", "fix_type": "modify",
                         "description": "Low priority", "instructions": "Maybe fix"},
                    ],
                    "unfixable": []
                }),
                agent_name="fixer"
            ),
            # Only critical fix applied
            mock_agent_result(content="Fixed", agent_name="builder", files_modified=["a.py"]),
        ]

        workflow = FixingWorkflow(project_root=project_root, min_severity="high")
        result = workflow.run(str(review_report))

        assert result.success
        # Only critical should be applied (low is below high threshold)
        assert result.data["fixes_applied"] == 1


class TestFixingWorkflowResume:
    """Tests for resume capability."""

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_resume_skips_completed(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test resume skips already completed fixes."""
        # Pre-create state with completed fix
        workflow = FixingWorkflow(project_root=project_root)
        workflow.fix_state = FixState(
            review_path=str(review_report),
            started_at="2024-01-15",
            status="in_progress",
            fixes_completed=["fix1"]
        )
        state_file = workflow._get_state_file(review_report)
        workflow.fix_state.save(state_file)

        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [
                        {"id": "fix1", "severity": "high", "issue_reference": "",
                         "category": "", "file_path": "a.py", "fix_type": "modify",
                         "description": "Already done", "instructions": ""},
                        {"id": "fix2", "severity": "high", "issue_reference": "",
                         "category": "", "file_path": "b.py", "fix_type": "modify",
                         "description": "New fix", "instructions": "Fix it"},
                    ],
                    "unfixable": []
                }),
                agent_name="fixer"
            ),
            # Only fix2 applied
            mock_agent_result(content="Fixed", agent_name="builder", files_modified=["b.py"]),
        ]

        workflow2 = FixingWorkflow(project_root=project_root)
        result = workflow2.run(str(review_report))

        assert result.success


class TestFixingWorkflowOutput:
    """Tests for fix report output."""

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_report_generated(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test fix report is generated."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [{
                        "id": "fix1", "severity": "high", "issue_reference": "Issue 1",
                        "category": "security", "file_path": "src/auth.py",
                        "fix_type": "modify", "description": "Fix SQL injection",
                        "instructions": "Use parameterized queries"
                    }],
                    "unfixable": []
                }),
                agent_name="fixer"
            ),
            mock_agent_result(content="Fixed", agent_name="builder", files_modified=["src/auth.py"]),
        ]

        workflow = FixingWorkflow(project_root=project_root)
        result = workflow.run(str(review_report))

        assert result.success
        assert result.output_file is not None
        assert result.output_file.exists()
        assert "fix-" in result.output_file.name

    @patch('workflows.fixing.FixingWorkflow.run_agent')
    def test_fix_report_contains_summary(self, mock_run_agent, project_root, review_report, mock_agent_result):
        """Test fix report contains summary section."""
        mock_run_agent.side_effect = [
            mock_agent_result(
                content=json.dumps({
                    "fixes": [{
                        "id": "fix1", "severity": "medium", "issue_reference": "",
                        "category": "quality", "file_path": "main.py",
                        "fix_type": "modify", "description": "Improve code",
                        "instructions": "Refactor"
                    }],
                    "unfixable": [{"issue": "Complex", "reason": "Needs human review"}]
                }),
                agent_name="fixer"
            ),
            mock_agent_result(content="Done", agent_name="builder", files_modified=["main.py"]),
        ]

        workflow = FixingWorkflow(project_root=project_root)
        result = workflow.run(str(review_report))

        report_content = result.output_file.read_text()
        assert "Summary" in report_content
        assert "Unfixable" in report_content
