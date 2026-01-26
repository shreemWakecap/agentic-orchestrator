"""
Staleness Checker for Codebase Knowledge.

Detects if codebase knowledge is stale based on:
1. Time elapsed since last scan
2. Git commits since last scan
3. Number of changed files

Used to auto-trigger scout before planning or alert users.
"""
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from db import get_knowledge_repository

logger = logging.getLogger(__name__)


class StalenessChecker:
    """
    Checks if codebase knowledge is stale and needs refreshing.

    Usage:
        checker = StalenessChecker(project_root)

        # Check if stale
        is_stale, reason = checker.is_stale()
        if is_stale:
            print(f"Knowledge is stale: {reason}")

        # Get changed paths for incremental scan
        changed = checker.get_changed_paths()
    """

    def __init__(self, project_root: Path, max_age_hours: int = 24, commit_threshold: int = 10):
        """
        Initialize the staleness checker.

        Args:
            project_root: Path to the project root
            max_age_hours: Maximum hours before knowledge is considered stale
            commit_threshold: Number of commits before knowledge is considered stale
        """
        self.project_root = project_root.resolve()
        self.max_age_hours = max_age_hours
        self.commit_threshold = commit_threshold
        self._knowledge_repo = get_knowledge_repository()

    def is_stale(self, max_age_hours: Optional[int] = None) -> tuple[bool, str]:
        """
        Check if knowledge is stale.

        Args:
            max_age_hours: Override default max age (optional)

        Returns:
            Tuple of (is_stale: bool, reason: str)
        """
        max_age = max_age_hours or self.max_age_hours

        # Get last scan metadata
        last_scan = self._knowledge_repo.get_scan_metadata()
        logger.debug(f"Staleness check - scan metadata: {last_scan}")

        if not last_scan:
            logger.info("Staleness result: is_stale=True, reason=No previous scan found")
            return True, "No previous scan found"

        # Check 1: Time-based staleness
        scan_time_str = last_scan.get("scan_time")
        if scan_time_str:
            try:
                scan_time = datetime.fromisoformat(scan_time_str)
                hours_since = (datetime.now() - scan_time).total_seconds() / 3600
                if hours_since > max_age:
                    reason = f"Last scan was {int(hours_since)} hours ago (threshold: {max_age})"
                    logger.info(f"Staleness result: is_stale=True, reason={reason}")
                    return True, reason
            except ValueError:
                pass

        # Check 2: Git-based staleness
        last_commit = last_scan.get("git_commit_hash")
        if last_commit:
            current_commit = self._get_current_commit()
            if current_commit and current_commit != last_commit:
                commits_behind = self._count_commits_since(last_commit)
                if commits_behind > 0:
                    if commits_behind >= self.commit_threshold:
                        reason = f"{commits_behind} commits since last scan (threshold: {self.commit_threshold})"
                        logger.info(f"Staleness result: is_stale=True, reason={reason}")
                        return True, reason

                    # Even with fewer commits, check if there are significant changes
                    changed_files = self.get_changed_paths()
                    if len(changed_files) > 20:
                        reason = f"{len(changed_files)} files changed in {commits_behind} commits"
                        logger.info(f"Staleness result: is_stale=True, reason={reason}")
                        return True, reason

        logger.info("Staleness result: is_stale=False, reason=Knowledge is current")
        return False, "Knowledge is current"

    def get_changed_paths(self) -> list[str]:
        """
        Get paths that have changed since the last scan.

        Returns:
            List of changed file paths relative to project root.
        """
        last_scan = self._knowledge_repo.get_scan_metadata()

        if not last_scan:
            return []

        last_commit = last_scan.get("git_commit_hash")
        if not last_commit:
            return []

        return self._get_changed_files_since_commit(last_commit)

    def get_staleness_summary(self) -> dict:
        """
        Get a summary of the knowledge staleness state.

        Returns:
            Dictionary with staleness information.
        """
        last_scan = self._knowledge_repo.get_scan_metadata()

        if not last_scan:
            return {
                "has_knowledge": False,
                "is_stale": True,
                "reason": "No previous scan",
                "last_scan_time": None,
                "last_commit": None,
                "current_commit": self._get_current_commit(),
                "commits_behind": 0,
                "changed_files_count": 0,
            }

        is_stale, reason = self.is_stale()
        last_commit = last_scan.get("git_commit_hash")
        current_commit = self._get_current_commit()

        commits_behind = 0
        if last_commit and current_commit and last_commit != current_commit:
            commits_behind = self._count_commits_since(last_commit)

        changed_files = self.get_changed_paths() if commits_behind > 0 else []

        # Parse scan time
        scan_time = None
        scan_time_str = last_scan.get("scan_time")
        if scan_time_str:
            try:
                scan_time = datetime.fromisoformat(scan_time_str)
            except ValueError:
                pass

        return {
            "has_knowledge": True,
            "is_stale": is_stale,
            "reason": reason,
            "last_scan_time": scan_time.isoformat() if scan_time else None,
            "hours_since_scan": self._hours_since_scan(scan_time) if scan_time else None,
            "last_commit": last_commit,
            "current_commit": current_commit,
            "commits_behind": commits_behind,
            "changed_files_count": len(changed_files),
            "scan_mode": last_scan.get("mode", "unknown"),
            "trigger": last_scan.get("trigger", "unknown"),
        }

    def _hours_since_scan(self, scan_time: datetime) -> float:
        """Calculate hours since last scan."""
        return (datetime.now() - scan_time).total_seconds() / 3600

    def _get_current_commit(self) -> Optional[str]:
        """Get current HEAD commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _count_commits_since(self, commit_hash: str) -> int:
        """Count commits since a specific commit."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{commit_hash}..HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _get_changed_files_since_commit(self, commit_hash: str) -> list[str]:
        """Get list of files changed since a specific commit."""
        changed_files = []

        try:
            # Get changed files (modified, added, deleted)
            result = subprocess.run(
                ["git", "diff", "--name-only", commit_hash, "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                changed_files = [
                    f.strip() for f in result.stdout.strip().split('\n')
                    if f.strip()
                ]

            # Also get untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                untracked = [
                    f.strip() for f in result.stdout.strip().split('\n')
                    if f.strip()
                ]
                changed_files.extend(untracked)
        except Exception:
            pass

        # Filter out non-source files
        return self._filter_source_files(list(set(changed_files)))

    def _filter_source_files(self, paths: list[str]) -> list[str]:
        """Filter to only include source files."""
        excluded_patterns = [
            'node_modules', '.venv', 'venv', '__pycache__',
            'dist', 'build', '.git', '.orchestrator',
            'bin', 'obj', '.vs', '.idea', 'packages',
            '.pytest_cache', '.mypy_cache', 'htmlcov',
        ]

        excluded_extensions = [
            '.pyc', '.pyo', '.egg-info', '.log', '.tmp',
            '.lock', '.sqlite', '.db',
        ]

        filtered = []
        for path in paths:
            # Skip if in excluded directory
            if any(pattern in path for pattern in excluded_patterns):
                continue

            # Skip if excluded extension
            if any(path.endswith(ext) for ext in excluded_extensions):
                continue

            filtered.append(path)

        return filtered


def check_staleness(project_root: Path = None) -> tuple[bool, str]:
    """
    Convenience function to check if knowledge is stale.

    Args:
        project_root: Path to project root (defaults to current directory parent)

    Returns:
        Tuple of (is_stale: bool, reason: str)
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    checker = StalenessChecker(project_root)
    return checker.is_stale()


def get_staleness_summary(project_root: Path = None) -> dict:
    """
    Convenience function to get staleness summary.

    Args:
        project_root: Path to project root (defaults to current directory parent)

    Returns:
        Dictionary with staleness information.
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    checker = StalenessChecker(project_root)
    return checker.get_staleness_summary()
