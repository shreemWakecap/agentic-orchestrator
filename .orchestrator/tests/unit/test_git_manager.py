"""
Unit tests for GitManager.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from core.git_manager import GitManager, GitStatus, GitCloneResult, GitOperationResult, get_git_manager


class TestGitManagerInit:
    """Tests for GitManager initialization."""

    def test_default_timeout(self):
        """Test default timeout is set."""
        manager = GitManager()
        assert manager.timeout == 120

    def test_custom_timeout(self):
        """Test custom timeout is set."""
        manager = GitManager(timeout=60)
        assert manager.timeout == 60


class TestGitManagerStatus:
    """Tests for GitManager.status() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    def test_status_not_git_repository(self, manager, tmp_path):
        """Test status returns error for non-git directory."""
        status = manager.status(tmp_path)

        assert status.error == "Not a git repository"
        assert status.branch == ""

    @patch('subprocess.run')
    def test_status_gets_branch(self, mock_subprocess, manager, git_repo):
        """Test status retrieves current branch."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd and "HEAD" in cmd:
                result.stdout = "main"
            elif "rev-parse" in cmd and "HEAD" in cmd:
                result.stdout = "abc123def456"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = ""
            elif "log" in cmd:
                result.stdout = "Initial commit"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert status.branch == "main"
        assert status.commit_hash == "abc123de"
        assert status.error is None

    @patch('subprocess.run')
    def test_status_gets_tracking_branch(self, mock_subprocess, manager, git_repo):
        """Test status retrieves tracking branch."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd and "HEAD" in cmd:
                result.stdout = "feature"
            elif "@{upstream}" in str(cmd):
                result.stdout = "origin/feature"
            elif "rev-list" in cmd and "--left-right" in cmd:
                result.stdout = "2\t3"  # 2 behind, 3 ahead
            elif "rev-parse" in cmd and "HEAD" in cmd:
                result.stdout = "abc123def456"
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = ""
            elif "log" in cmd:
                result.stdout = "Feature commit"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert status.tracking_branch == "origin/feature"
        assert status.ahead == 3
        assert status.behind == 2

    @patch('subprocess.run')
    def test_status_parses_staged_files(self, mock_subprocess, manager, git_repo):
        """Test status correctly parses staged files."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123def456"
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = "A  src/new_file.py\nM  src/modified.py"
            elif "log" in cmd:
                result.stdout = "Commit message"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert "src/new_file.py" in status.staged_files
        assert "src/modified.py" in status.staged_files
        assert status.is_clean is False

    @patch('subprocess.run')
    def test_status_parses_modified_files(self, mock_subprocess, manager, git_repo):
        """Test status correctly parses modified files."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123def456"
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = " M src/modified.py\n D src/deleted.py"
            elif "log" in cmd:
                result.stdout = "Commit message"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert "src/modified.py" in status.modified_files
        assert "src/deleted.py" in status.modified_files
        assert status.is_clean is False

    @patch('subprocess.run')
    def test_status_parses_untracked_files(self, mock_subprocess, manager, git_repo):
        """Test status correctly parses untracked files."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123def456"
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = "?? src/untracked.py\n?? docs/readme.md"
            elif "log" in cmd:
                result.stdout = "Commit message"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert "src/untracked.py" in status.untracked_files
        assert "docs/readme.md" in status.untracked_files
        assert status.is_clean is False

    @patch('subprocess.run')
    def test_status_clean_repository(self, mock_subprocess, manager, git_repo):
        """Test status for clean repository."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123def456"
            elif "status" in cmd and "--porcelain" in cmd:
                result.stdout = ""
            elif "log" in cmd:
                result.stdout = "Commit message"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        status = manager.status(git_repo)

        assert status.is_clean is True
        assert len(status.staged_files) == 0
        assert len(status.modified_files) == 0
        assert len(status.untracked_files) == 0

    @patch('subprocess.run')
    def test_status_handles_timeout(self, mock_subprocess, manager, git_repo):
        """Test status handles subprocess timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=120)

        status = manager.status(git_repo)

        assert status.error == "Status command timed out"

    @patch('subprocess.run')
    def test_status_handles_exception(self, mock_subprocess, manager, git_repo):
        """Test status handles general exceptions."""
        mock_subprocess.side_effect = Exception("Git command failed")

        status = manager.status(git_repo)

        assert "Git command failed" in status.error


class TestGitManagerGetBranch:
    """Tests for GitManager.get_current_branch() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    def test_get_branch_not_git_repository(self, manager, tmp_path):
        """Test get_current_branch returns None for non-git directory."""
        result = manager.get_current_branch(tmp_path)
        assert result is None

    @patch('subprocess.run')
    def test_get_branch_success(self, mock_subprocess, manager, git_repo):
        """Test get_current_branch returns branch name."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="feature-branch\n")

        result = manager.get_current_branch(git_repo)

        assert result == "feature-branch"

    @patch('subprocess.run')
    def test_get_branch_failure(self, mock_subprocess, manager, git_repo):
        """Test get_current_branch returns None on failure."""
        mock_subprocess.return_value = Mock(returncode=1, stdout="")

        result = manager.get_current_branch(git_repo)

        assert result is None

    @patch('subprocess.run')
    def test_get_branch_handles_exception(self, mock_subprocess, manager, git_repo):
        """Test get_current_branch handles exceptions."""
        mock_subprocess.side_effect = Exception("Git error")

        result = manager.get_current_branch(git_repo)

        assert result is None


class TestGitManagerClone:
    """Tests for GitManager.clone() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @patch('subprocess.run')
    def test_clone_success(self, mock_subprocess, manager, tmp_path):
        """Test successful clone operation."""
        dest = tmp_path / "repo"

        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            # Create .git dir to simulate clone
            if "clone" in cmd:
                dest.mkdir(exist_ok=True)
                (dest / ".git").mkdir(exist_ok=True)
            elif "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "rev-parse" in cmd and "HEAD" in cmd:
                result.stdout = "abc123def456"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
            elif "status" in cmd:
                result.stdout = ""
            elif "log" in cmd:
                result.stdout = "Initial commit"
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.clone("https://github.com/user/repo.git", dest)

        assert result.success is True
        assert result.path == dest
        assert result.branch == "main"

    @patch('subprocess.run')
    def test_clone_with_branch(self, mock_subprocess, manager, tmp_path):
        """Test clone with specific branch."""
        dest = tmp_path / "repo"
        mock_subprocess.return_value = Mock(returncode=1, stderr="Clone failed")

        result = manager.clone(
            "https://github.com/user/repo.git",
            dest,
            branch="develop"
        )

        # Verify --branch argument was passed
        call_args = mock_subprocess.call_args[0][0]
        assert "--branch" in call_args
        assert "develop" in call_args

    @patch('subprocess.run')
    def test_clone_with_depth(self, mock_subprocess, manager, tmp_path):
        """Test shallow clone with depth."""
        dest = tmp_path / "repo"
        mock_subprocess.return_value = Mock(returncode=1, stderr="Clone failed")

        result = manager.clone(
            "https://github.com/user/repo.git",
            dest,
            depth=1
        )

        call_args = mock_subprocess.call_args[0][0]
        assert "--depth" in call_args
        assert "1" in call_args

    @patch('subprocess.run')
    def test_clone_failure(self, mock_subprocess, manager, tmp_path):
        """Test clone failure."""
        dest = tmp_path / "repo"
        mock_subprocess.return_value = Mock(
            returncode=128,
            stdout="",
            stderr="fatal: repository not found"
        )

        result = manager.clone("https://github.com/user/nonexistent.git", dest)

        assert result.success is False
        assert "repository not found" in result.error

    @patch('subprocess.run')
    def test_clone_timeout(self, mock_subprocess, manager, tmp_path):
        """Test clone timeout."""
        dest = tmp_path / "repo"
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=300)

        result = manager.clone("https://github.com/user/repo.git", dest)

        assert result.success is False
        assert "timed out" in result.error


class TestGitManagerFetch:
    """Tests for GitManager.fetch() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    def test_fetch_not_git_repository(self, manager, tmp_path):
        """Test fetch returns error for non-git directory."""
        result = manager.fetch(tmp_path)

        assert result.success is False
        assert result.error == "Not a git repository"

    @patch('subprocess.run')
    def test_fetch_success(self, mock_subprocess, manager, git_repo):
        """Test successful fetch operation."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="From github.com:user/repo\n * [new branch] main -> origin/main"
        )

        result = manager.fetch(git_repo)

        assert result.success is True

    @patch('subprocess.run')
    def test_fetch_all_remotes(self, mock_subprocess, manager, git_repo):
        """Test fetch from all remotes."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.fetch(git_repo, all_remotes=True)

        call_args = mock_subprocess.call_args[0][0]
        assert "--all" in call_args

    @patch('subprocess.run')
    def test_fetch_specific_remote(self, mock_subprocess, manager, git_repo):
        """Test fetch from specific remote."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        result = manager.fetch(git_repo, remote="upstream")

        call_args = mock_subprocess.call_args[0][0]
        assert "upstream" in call_args

    @patch('subprocess.run')
    def test_fetch_failure(self, mock_subprocess, manager, git_repo):
        """Test fetch failure."""
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: Could not read from remote repository"
        )

        result = manager.fetch(git_repo)

        assert result.success is False
        assert "Could not read" in result.error

    @patch('subprocess.run')
    def test_fetch_timeout(self, mock_subprocess, manager, git_repo):
        """Test fetch timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=120)

        result = manager.fetch(git_repo)

        assert result.success is False
        assert "timed out" in result.error


class TestGitManagerPull:
    """Tests for GitManager.pull() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    def test_pull_not_git_repository(self, manager, tmp_path):
        """Test pull returns error for non-git directory."""
        result = manager.pull(tmp_path)

        assert result.success is False
        assert result.error == "Not a git repository"

    @patch('subprocess.run')
    def test_pull_success_no_changes(self, mock_subprocess, manager, git_repo):
        """Test successful pull with no changes."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "abc123"
            elif "pull" in cmd:
                result.stdout = "Already up to date."
                result.stderr = ""
            elif "diff" in cmd and "--name-only" in cmd:
                result.stdout = ""
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.pull(git_repo)

        assert result.success is True
        assert len(result.changed_files) == 0

    @patch('subprocess.run')
    def test_pull_success_with_changes(self, mock_subprocess, manager, git_repo):
        """Test successful pull with changed files."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "abc123"
            elif "pull" in cmd:
                result.stdout = "Updating abc123..def456\nFast-forward"
                result.stderr = ""
            elif "diff" in cmd and "--name-only" in cmd:
                result.stdout = "src/file1.py\nsrc/file2.py"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.pull(git_repo)

        assert result.success is True
        assert "src/file1.py" in result.changed_files
        assert "src/file2.py" in result.changed_files

    @patch('subprocess.run')
    def test_pull_with_rebase(self, mock_subprocess, manager, git_repo):
        """Test pull with rebase option."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "abc123"
            result.stderr = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.pull(git_repo, rebase=True)

        # Find the pull command call
        pull_calls = [call for call in mock_subprocess.call_args_list if "pull" in call[0][0]]
        assert len(pull_calls) > 0
        assert "--rebase" in pull_calls[0][0][0]

    @patch('subprocess.run')
    def test_pull_specific_branch(self, mock_subprocess, manager, git_repo):
        """Test pull specific branch."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "abc123"
            result.stderr = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.pull(git_repo, branch="develop")

        pull_calls = [call for call in mock_subprocess.call_args_list if "pull" in call[0][0]]
        assert len(pull_calls) > 0
        assert "develop" in pull_calls[0][0][0]

    @patch('subprocess.run')
    def test_pull_failure(self, mock_subprocess, manager, git_repo):
        """Test pull failure."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            if "rev-parse" in cmd:
                result.returncode = 0
                result.stdout = "abc123"
            else:
                result.returncode = 1
                result.stdout = ""
                result.stderr = "error: Your local changes would be overwritten"
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.pull(git_repo)

        assert result.success is False
        assert "local changes" in result.error

    @patch('subprocess.run')
    def test_pull_timeout(self, mock_subprocess, manager, git_repo):
        """Test pull timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=120)

        result = manager.pull(git_repo)

        assert result.success is False
        assert "timed out" in result.error


class TestGitManagerGetRemoteUrl:
    """Tests for GitManager.get_remote_url() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    def test_get_remote_url_not_git_repository(self, manager, tmp_path):
        """Test get_remote_url returns None for non-git directory."""
        result = manager.get_remote_url(tmp_path)
        assert result is None

    @patch('subprocess.run')
    def test_get_remote_url_success(self, mock_subprocess, manager, git_repo):
        """Test successful remote URL retrieval."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="https://github.com/user/repo.git\n"
        )

        result = manager.get_remote_url(git_repo)

        assert result == "https://github.com/user/repo.git"

    @patch('subprocess.run')
    def test_get_remote_url_specific_remote(self, mock_subprocess, manager, git_repo):
        """Test get remote URL for specific remote."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="https://github.com/upstream/repo.git\n"
        )

        result = manager.get_remote_url(git_repo, remote="upstream")

        call_args = mock_subprocess.call_args[0][0]
        assert "upstream" in call_args

    @patch('subprocess.run')
    def test_get_remote_url_failure(self, mock_subprocess, manager, git_repo):
        """Test get_remote_url returns None on failure."""
        mock_subprocess.return_value = Mock(returncode=1, stdout="")

        result = manager.get_remote_url(git_repo)

        assert result is None


class TestGitManagerHasUncommittedChanges:
    """Tests for GitManager.has_uncommitted_changes() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a fake git repository directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    @patch('subprocess.run')
    def test_has_uncommitted_changes_true(self, mock_subprocess, manager, git_repo):
        """Test returns True when there are uncommitted changes."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "status" in cmd and "--porcelain" in cmd:
                result.stdout = "M  src/file.py"
            elif "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123"
            elif "log" in cmd:
                result.stdout = "Commit"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.has_uncommitted_changes(git_repo)

        assert result is True

    @patch('subprocess.run')
    def test_has_uncommitted_changes_false(self, mock_subprocess, manager, git_repo):
        """Test returns False when working directory is clean."""
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "status" in cmd and "--porcelain" in cmd:
                result.stdout = ""
            elif "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "@{upstream}" in str(cmd):
                result.returncode = 1
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123"
            elif "log" in cmd:
                result.stdout = "Commit"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_run

        result = manager.has_uncommitted_changes(git_repo)

        assert result is False


class TestGitManagerIsGitRepository:
    """Tests for GitManager.is_git_repository() method."""

    @pytest.fixture
    def manager(self):
        """Create a GitManager instance."""
        return GitManager()

    def test_is_git_repository_true(self, manager, tmp_path):
        """Test returns True for git repository."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        result = manager.is_git_repository(tmp_path)

        assert result is True

    def test_is_git_repository_false_no_git_dir(self, manager, tmp_path):
        """Test returns False when .git doesn't exist."""
        result = manager.is_git_repository(tmp_path)

        assert result is False

    def test_is_git_repository_false_git_is_file(self, manager, tmp_path):
        """Test returns False when .git is a file not directory."""
        git_file = tmp_path / ".git"
        git_file.touch()

        result = manager.is_git_repository(tmp_path)

        assert result is False


class TestGitStatusDataclass:
    """Tests for GitStatus dataclass."""

    def test_default_values(self):
        """Test GitStatus default values."""
        status = GitStatus()

        assert status.branch == ""
        assert status.tracking_branch == ""
        assert status.is_clean is True
        assert status.ahead == 0
        assert status.behind == 0
        assert status.staged_files == []
        assert status.modified_files == []
        assert status.untracked_files == []
        assert status.commit_hash == ""
        assert status.commit_message == ""
        assert status.error is None

    def test_to_dict(self):
        """Test GitStatus.to_dict() method."""
        status = GitStatus(
            branch="main",
            is_clean=False,
            staged_files=["file.py"],
            commit_hash="abc123"
        )

        result = status.to_dict()

        assert result["branch"] == "main"
        assert result["is_clean"] is False
        assert result["staged_files"] == ["file.py"]
        assert result["commit_hash"] == "abc123"


class TestGetGitManagerSingleton:
    """Tests for get_git_manager() singleton function."""

    def test_returns_git_manager_instance(self):
        """Test returns GitManager instance."""
        manager = get_git_manager()

        assert isinstance(manager, GitManager)

    def test_returns_same_instance(self):
        """Test returns same singleton instance."""
        manager1 = get_git_manager()
        manager2 = get_git_manager()

        assert manager1 is manager2
