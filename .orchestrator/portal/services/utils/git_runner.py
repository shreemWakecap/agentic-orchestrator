"""Git command execution utilities.

Provides a unified interface for running git commands, consolidating
duplicate implementations from git_service.py and git_statistics_service.py.
"""
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


class GitRunner:
    """Unified git command runner.

    Consolidates duplicate _run_git() implementations from:
    - git_service.py (lines 38-61)
    - git_statistics_service.py (lines 109-132)

    Usage:
        runner = GitRunner(project_root)
        output = runner.run(["status", "--porcelain"])
        output, error = runner.run_with_error(["rev-parse", "HEAD"])
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the git runner.

        Args:
            project_root: Root directory of the git repository.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()

    def run(self, cmd: List[str], check: bool = False) -> Optional[str]:
        """Run a git command and return output.

        Args:
            cmd: Git command arguments (without 'git' prefix).
            check: If True, return None on non-zero exit code.

        Returns:
            Command stdout as string, or None if command failed.
        """
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if check and result.returncode != 0:
                return None
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def run_with_error(self, cmd: List[str], check: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """Run a git command and return output and error.

        Args:
            cmd: Git command arguments (without 'git' prefix).
            check: If True, return None on non-zero exit code.

        Returns:
            Tuple of (stdout, stderr) as strings, or (None, error_message) if failed.
        """
        try:
            result = subprocess.run(
                ["git"] + cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if check and result.returncode != 0:
                return None, result.stderr.strip()
            return result.stdout.strip() if result.returncode == 0 else None, result.stderr.strip()
        except Exception as e:
            return None, str(e)

    def is_repository(self) -> bool:
        """Check if the project root is a git repository."""
        result = self.run(["rev-parse", "--git-dir"])
        return result is not None


def run_git_command(
    cmd: List[str],
    project_root: Optional[Path] = None,
    check: bool = False
) -> Optional[str]:
    """Convenience function to run a git command.

    Args:
        cmd: Git command arguments (without 'git' prefix).
        project_root: Root directory of the git repository.
        check: If True, return None on non-zero exit code.

    Returns:
        Command stdout as string, or None if command failed.
    """
    runner = GitRunner(project_root)
    return runner.run(cmd, check)
