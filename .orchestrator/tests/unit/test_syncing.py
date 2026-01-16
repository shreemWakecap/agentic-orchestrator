"""Unit tests for workflows/syncing.py module.

Tests cover:
- SyncResult dataclass
- SyncingWorkflow class methods
- JSON parsing
- Fallback message generation
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from workflows.syncing import SyncResult, SyncingWorkflow


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_create_basic(self):
        result = SyncResult(
            branch_name="feature/test",
            commit_hash="abc123",
            commit_message="test: add test"
        )
        assert result.branch_name == "feature/test"
        assert result.commit_hash == "abc123"
        assert result.commit_message == "test: add test"
        assert result.pr_url is None
        assert result.pr_number is None
        assert result.files_changed == []

    def test_create_full(self):
        result = SyncResult(
            branch_name="feature/test",
            commit_hash="abc123",
            commit_message="test: add test",
            pr_url="https://github.com/test/repo/pull/1",
            pr_number=1,
            files_changed=["file1.py", "file2.py"]
        )
        assert result.pr_url == "https://github.com/test/repo/pull/1"
        assert result.pr_number == 1
        assert result.files_changed == ["file1.py", "file2.py"]


class TestSyncingWorkflowHelpers:
    """Tests for SyncingWorkflow helper methods."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create minimal structure
            orchestrator = base / ".orchestrator"
            orchestrator.mkdir()
            agents = orchestrator / "agents"
            agents.mkdir()
            yield base

    @pytest.fixture
    def workflow(self, temp_project):
        """Create a SyncingWorkflow with mocked agents."""
        with patch('workflows.syncing.Agent') as mock_agent:
            mock_agent.load.side_effect = FileNotFoundError("Agent not found")
            wf = SyncingWorkflow(temp_project)
            return wf

    def test_get_fallback_commit_message_single_file(self, workflow):
        result = workflow._get_fallback_commit_message(["file.py"])
        assert result == "chore: sync changes (1 files)"

    def test_get_fallback_commit_message_multiple_files(self, workflow):
        result = workflow._get_fallback_commit_message(["a.py", "b.py", "c.py"])
        assert result == "chore: sync changes (3 files)"

    def test_get_fallback_pr_description(self, workflow):
        diff_stats = """
 file1.py | 10 ++++++++++
 file2.py |  5 ++---
 2 files changed, 12 insertions(+), 3 deletions(-)
"""
        result = workflow._get_fallback_pr_description(diff_stats)
        assert "## Summary" in result
        assert "## Changes" in result
        assert "file1.py" in result
        assert "## Testing" in result
        assert "## Breaking Changes" in result


class TestJsonParsing:
    """Tests for JSON parsing from agent responses."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            orchestrator = base / ".orchestrator"
            orchestrator.mkdir()
            agents = orchestrator / "agents"
            agents.mkdir()
            yield base

    @pytest.fixture
    def workflow(self, temp_project):
        """Create a SyncingWorkflow."""
        with patch('workflows.syncing.Agent') as mock_agent:
            mock_agent.load.side_effect = FileNotFoundError()
            wf = SyncingWorkflow(temp_project)
            return wf

    def test_parse_json_code_block(self, workflow):
        response = '''Here is the result:
```json
{"commit_message": "test: add feature", "type": "test"}
```
'''
        result = workflow._parse_json_from_response(response)
        assert result["commit_message"] == "test: add feature"
        assert result["type"] == "test"

    def test_parse_json_direct(self, workflow):
        response = '{"commit_message": "test: add feature"}'
        result = workflow._parse_json_from_response(response)
        assert result["commit_message"] == "test: add feature"

    def test_parse_json_embedded(self, workflow):
        response = '''Some text before
{"commit_message": "test: add feature", "type": "test"}
Some text after
'''
        result = workflow._parse_json_from_response(response)
        assert result["commit_message"] == "test: add feature"

    def test_parse_json_invalid(self, workflow):
        response = "This is not JSON at all"
        result = workflow._parse_json_from_response(response)
        assert result == {}

    def test_parse_json_malformed_code_block(self, workflow):
        response = '''```json
{not valid json}
```
'''
        # Should fall through to embedded JSON search
        result = workflow._parse_json_from_response(response)
        assert result == {}


class TestGitHelpers:
    """Tests for git/gh command helpers."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            orchestrator = base / ".orchestrator"
            orchestrator.mkdir()
            agents = orchestrator / "agents"
            agents.mkdir()
            yield base

    @pytest.fixture
    def workflow(self, temp_project):
        """Create a SyncingWorkflow."""
        with patch('workflows.syncing.Agent') as mock_agent:
            mock_agent.load.side_effect = FileNotFoundError()
            wf = SyncingWorkflow(temp_project)
            return wf

    @patch('subprocess.run')
    def test_run_git_success(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success output",
            stderr=""
        )

        result = workflow._run_git(["status"])
        assert result == "success output"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_git_failure(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error message"
        )

        with pytest.raises(RuntimeError) as excinfo:
            workflow._run_git(["status"])

        assert "Git command failed" in str(excinfo.value)

    @patch('subprocess.run')
    def test_run_git_no_check(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="output",
            stderr="error"
        )

        # Should not raise even with failure when check=False
        result = workflow._run_git(["status"], check=False)
        assert result == "output"

    @patch('subprocess.run')
    def test_run_gh_success(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="gh output",
            stderr=""
        )

        result = workflow._run_gh(["auth", "status"])
        assert result == "gh output"

    @patch('subprocess.run')
    def test_run_gh_failure(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="gh error"
        )

        with pytest.raises(RuntimeError) as excinfo:
            workflow._run_gh(["auth", "status"])

        assert "GitHub CLI failed" in str(excinfo.value)


class TestPrerequisites:
    """Tests for prerequisite checking."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            orchestrator = base / ".orchestrator"
            orchestrator.mkdir()
            agents = orchestrator / "agents"
            agents.mkdir()
            yield base

    @pytest.fixture
    def workflow(self, temp_project):
        """Create a SyncingWorkflow."""
        with patch('workflows.syncing.Agent') as mock_agent:
            mock_agent.load.side_effect = FileNotFoundError()
            wf = SyncingWorkflow(temp_project)
            return wf

    @patch('shutil.which')
    def test_git_not_found(self, mock_which, workflow):
        mock_which.return_value = None

        ok, msg = workflow._check_prerequisites()
        assert not ok
        assert "Git CLI not found" in msg

    @patch('shutil.which')
    def test_gh_not_found(self, mock_which, workflow):
        def which_side_effect(cmd):
            return "/usr/bin/git" if cmd == "git" else None
        mock_which.side_effect = which_side_effect

        ok, msg = workflow._check_prerequisites()
        assert not ok
        assert "GitHub CLI not found" in msg

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_gh_not_authenticated(self, mock_run, mock_which, workflow):
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="not authenticated"
        )

        ok, msg = workflow._check_prerequisites()
        assert not ok
        assert "not authenticated" in msg

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_not_in_git_repo(self, mock_run, mock_which, workflow):
        mock_which.return_value = "/usr/bin/tool"

        def run_side_effect(cmd, **kwargs):
            if "auth" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            elif "rev-parse" in cmd:
                return MagicMock(returncode=1, stdout="", stderr="not a git repo")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        ok, msg = workflow._check_prerequisites()
        assert not ok
        assert "Not in a git repository" in msg

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_all_prerequisites_pass(self, mock_run, mock_which, workflow):
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success",
            stderr=""
        )

        ok, msg = workflow._check_prerequisites()
        assert ok
        assert msg == ""


class TestGetChanges:
    """Tests for getting changes from git."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            orchestrator = base / ".orchestrator"
            orchestrator.mkdir()
            agents = orchestrator / "agents"
            agents.mkdir()
            yield base

    @pytest.fixture
    def workflow(self, temp_project):
        """Create a SyncingWorkflow."""
        with patch('workflows.syncing.Agent') as mock_agent:
            mock_agent.load.side_effect = FileNotFoundError()
            wf = SyncingWorkflow(temp_project)
            return wf

    @patch('subprocess.run')
    def test_no_changes(self, mock_run, workflow):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )

        files, stats, diff = workflow._get_changes()
        assert files == []
        assert stats == ""
        assert diff == ""

    @patch('subprocess.run')
    def test_with_changes(self, mock_run, workflow):
        def run_side_effect(cmd, **kwargs):
            if "status" in cmd and "--porcelain" in cmd:
                return MagicMock(returncode=0, stdout="M file1.py\nA file2.py", stderr="")
            elif "diff" in cmd and "--stat" in cmd:
                return MagicMock(returncode=0, stdout="file1.py | 2 ++", stderr="")
            elif "diff" in cmd:
                return MagicMock(returncode=0, stdout="diff content", stderr="")
            else:
                return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        files, stats, diff = workflow._get_changes()
        assert "file1.py" in files
        assert "file2.py" in files
        assert "file1.py" in stats

    @patch('subprocess.run')
    def test_truncates_large_diff(self, mock_run, workflow):
        large_diff = "x" * 10000  # Larger than 8000 char limit

        def run_side_effect(cmd, **kwargs):
            if "status" in cmd and "--porcelain" in cmd:
                return MagicMock(returncode=0, stdout="M file.py", stderr="")
            elif "diff" in cmd and "--cached" in cmd and "--stat" not in cmd:
                return MagicMock(returncode=0, stdout=large_diff, stderr="")
            else:
                return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        files, stats, diff = workflow._get_changes()
        assert len(diff) <= 8050  # 8000 + truncation message
        assert "truncated" in diff
