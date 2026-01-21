"""
Unit tests for StalenessChecker.
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestStalenessChecker:
    """Tests for StalenessChecker operations."""

    @pytest.fixture
    def mock_knowledge_repo(self):
        """Create a mock knowledge repository."""
        repo = Mock()
        repo.get_scan_metadata.return_value = None
        return repo

    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a temporary project root."""
        return tmp_path

    @pytest.fixture
    def staleness_checker(self, mock_project_root, mock_knowledge_repo):
        """Create a StalenessChecker with mocked dependencies."""
        with patch('core.staleness_checker.get_knowledge_repository', return_value=mock_knowledge_repo):
            from core.staleness_checker import StalenessChecker
            return StalenessChecker(mock_project_root, max_age_hours=24, commit_threshold=10)

    def test_is_stale_no_previous_scan(self, staleness_checker, mock_knowledge_repo):
        """Test that no previous scan means knowledge is stale."""
        mock_knowledge_repo.get_scan_metadata.return_value = None

        is_stale, reason = staleness_checker.is_stale()

        assert is_stale is True
        assert "No previous scan" in reason

    def test_is_stale_time_based_stale(self, staleness_checker, mock_knowledge_repo):
        """Test staleness detection based on time elapsed."""
        # Scan from 30 hours ago
        old_scan_time = (datetime.now() - timedelta(hours=30)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": old_scan_time,
            "git_commit_hash": None,
        }

        is_stale, reason = staleness_checker.is_stale()

        assert is_stale is True
        assert "hours ago" in reason

    def test_is_stale_time_based_current(self, staleness_checker, mock_knowledge_repo):
        """Test that recent scan is not stale (time-based)."""
        # Scan from 1 hour ago
        recent_scan_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": recent_scan_time,
            "git_commit_hash": None,
        }

        is_stale, reason = staleness_checker.is_stale()

        assert is_stale is False
        assert "current" in reason.lower()

    @patch('subprocess.run')
    def test_is_stale_git_commits_threshold(self, mock_subprocess, staleness_checker, mock_knowledge_repo):
        """Test staleness detection based on git commits."""
        # Recent scan but many commits since
        recent_scan_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": recent_scan_time,
            "git_commit_hash": "abc123",
        }

        # Mock git commands
        def mock_git_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd and "HEAD" in cmd:
                result.stdout = "def456"  # Different commit
            elif "rev-list" in cmd and "--count" in cmd:
                result.stdout = "15"  # 15 commits since last scan
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_git_run

        is_stale, reason = staleness_checker.is_stale()

        assert is_stale is True
        assert "commits" in reason.lower()

    @patch('subprocess.run')
    def test_is_stale_git_same_commit(self, mock_subprocess, staleness_checker, mock_knowledge_repo):
        """Test that same git commit means not stale."""
        recent_scan_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": recent_scan_time,
            "git_commit_hash": "abc123",
        }

        # Mock git to return same commit
        def mock_git_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "rev-parse" in cmd:
                result.stdout = "abc123"  # Same commit
            return result

        mock_subprocess.side_effect = mock_git_run

        is_stale, reason = staleness_checker.is_stale()

        assert is_stale is False
        assert "current" in reason.lower()

    def test_is_stale_custom_max_age(self, staleness_checker, mock_knowledge_repo):
        """Test staleness with custom max age parameter."""
        # Scan from 5 hours ago
        scan_time = (datetime.now() - timedelta(hours=5)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": scan_time,
            "git_commit_hash": None,
        }

        # Not stale with 24 hour threshold (default)
        is_stale, _ = staleness_checker.is_stale()
        assert is_stale is False

        # Stale with 4 hour threshold
        is_stale, _ = staleness_checker.is_stale(max_age_hours=4)
        assert is_stale is True

    def test_get_changed_paths_no_scan(self, staleness_checker, mock_knowledge_repo):
        """Test get_changed_paths with no previous scan."""
        mock_knowledge_repo.get_scan_metadata.return_value = None

        paths = staleness_checker.get_changed_paths()

        assert paths == []

    def test_get_changed_paths_no_commit_hash(self, staleness_checker, mock_knowledge_repo):
        """Test get_changed_paths with no commit hash in scan."""
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": datetime.now().isoformat(),
            "git_commit_hash": None,
        }

        paths = staleness_checker.get_changed_paths()

        assert paths == []

    @patch('subprocess.run')
    def test_get_changed_paths_with_changes(self, mock_subprocess, staleness_checker, mock_knowledge_repo):
        """Test get_changed_paths returns changed files."""
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": datetime.now().isoformat(),
            "git_commit_hash": "abc123",
        }

        def mock_git_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "diff" in cmd:
                result.stdout = "src/main.py\nsrc/utils.py"
            elif "ls-files" in cmd:
                result.stdout = "src/new_file.py"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_git_run

        paths = staleness_checker.get_changed_paths()

        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        assert "src/new_file.py" in paths

    @patch('subprocess.run')
    def test_get_changed_paths_filters_excluded(self, mock_subprocess, staleness_checker, mock_knowledge_repo):
        """Test that excluded paths are filtered out."""
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": datetime.now().isoformat(),
            "git_commit_hash": "abc123",
        }

        def mock_git_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if "diff" in cmd:
                result.stdout = "src/main.py\nnode_modules/pkg/index.js\n__pycache__/cache.pyc"
            else:
                result.stdout = ""
            return result

        mock_subprocess.side_effect = mock_git_run

        paths = staleness_checker.get_changed_paths()

        assert "src/main.py" in paths
        assert "node_modules/pkg/index.js" not in paths
        assert "__pycache__/cache.pyc" not in paths

    def test_get_staleness_summary_no_knowledge(self, staleness_checker, mock_knowledge_repo):
        """Test get_staleness_summary with no knowledge."""
        mock_knowledge_repo.get_scan_metadata.return_value = None

        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=0, stdout="abc123")
            summary = staleness_checker.get_staleness_summary()

        assert summary["has_knowledge"] is False
        assert summary["is_stale"] is True
        assert summary["reason"] == "No previous scan"

    @patch('subprocess.run')
    def test_get_staleness_summary_with_knowledge(self, mock_subprocess, staleness_checker, mock_knowledge_repo):
        """Test get_staleness_summary with existing knowledge."""
        recent_scan_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_knowledge_repo.get_scan_metadata.return_value = {
            "scan_time": recent_scan_time,
            "git_commit_hash": "abc123",
            "mode": "full",
            "trigger": "manual",
        }

        mock_subprocess.return_value = Mock(returncode=0, stdout="abc123")

        summary = staleness_checker.get_staleness_summary()

        assert summary["has_knowledge"] is True
        assert summary["is_stale"] is False
        assert summary["last_commit"] == "abc123"
        assert summary["scan_mode"] == "full"
        assert summary["trigger"] == "manual"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch('core.staleness_checker.StalenessChecker')
    def test_check_staleness(self, mock_checker_class):
        """Test check_staleness convenience function."""
        mock_instance = Mock()
        mock_instance.is_stale.return_value = (True, "Test reason")
        mock_checker_class.return_value = mock_instance

        from core.staleness_checker import check_staleness
        is_stale, reason = check_staleness(Path("/tmp"))

        assert is_stale is True
        assert reason == "Test reason"

    @patch('core.staleness_checker.StalenessChecker')
    def test_get_staleness_summary(self, mock_checker_class):
        """Test get_staleness_summary convenience function."""
        mock_instance = Mock()
        mock_instance.get_staleness_summary.return_value = {"is_stale": False}
        mock_checker_class.return_value = mock_instance

        from core.staleness_checker import get_staleness_summary
        summary = get_staleness_summary(Path("/tmp"))

        assert summary["is_stale"] is False
