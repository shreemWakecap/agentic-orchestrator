"""
Git Manager: Git operations for project management.

Handles git operations like clone, fetch, pull, status for projects.
"""
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str = ""
    tracking_branch: str = ""
    is_clean: bool = True
    ahead: int = 0
    behind: int = 0
    staged_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    commit_hash: str = ""
    commit_message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "tracking_branch": self.tracking_branch,
            "is_clean": self.is_clean,
            "ahead": self.ahead,
            "behind": self.behind,
            "staged_files": self.staged_files,
            "modified_files": self.modified_files,
            "untracked_files": self.untracked_files,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "error": self.error,
        }


@dataclass
class GitCloneResult:
    """Result of a git clone operation."""
    success: bool
    path: Optional[Path] = None
    branch: str = ""
    commit_hash: str = ""
    error: Optional[str] = None


@dataclass
class GitOperationResult:
    """Result of a git operation (fetch, pull, etc.)."""
    success: bool
    output: str = ""
    error: Optional[str] = None
    changed_files: List[str] = field(default_factory=list)


class GitManager:
    """
    Manages git operations for projects.

    Usage:
        manager = GitManager()

        # Clone a repository
        result = manager.clone("https://github.com/user/repo", "/path/to/dest")

        # Get status
        status = manager.status("/path/to/repo")

        # Fetch updates
        result = manager.fetch("/path/to/repo")

        # Pull changes
        result = manager.pull("/path/to/repo")
    """

    def __init__(self, timeout: int = 120):
        """
        Initialize GitManager.

        Args:
            timeout: Default timeout for git operations in seconds.
        """
        self.timeout = timeout

    def _run_git(
        self,
        args: List[str],
        cwd: Path = None,
        timeout: int = None,
        capture_output: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run a git command.

        Args:
            args: Git command arguments (without 'git').
            cwd: Working directory.
            timeout: Command timeout in seconds.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            CompletedProcess result.
        """
        cmd = ["git"] + args
        timeout = timeout or self.timeout

        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )

    def is_git_repository(self, path: Path) -> bool:
        """Check if a path is a git repository."""
        git_dir = path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def clone(
        self,
        url: str,
        destination: Path,
        branch: str = None,
        depth: int = None,
        timeout: int = 300
    ) -> GitCloneResult:
        """
        Clone a git repository.

        Args:
            url: Repository URL.
            destination: Local destination path.
            branch: Branch to clone (default: repository default).
            depth: Shallow clone depth (default: full clone).
            timeout: Clone timeout in seconds.

        Returns:
            GitCloneResult with status and details.
        """
        args = ["clone", url, str(destination)]

        if branch:
            args.extend(["--branch", branch])

        if depth:
            args.extend(["--depth", str(depth)])

        try:
            result = self._run_git(args, timeout=timeout)

            if result.returncode != 0:
                return GitCloneResult(
                    success=False,
                    error=result.stderr.strip() or "Clone failed"
                )

            # Get the cloned branch and commit
            status = self.status(destination)

            return GitCloneResult(
                success=True,
                path=destination,
                branch=status.branch,
                commit_hash=status.commit_hash,
            )

        except subprocess.TimeoutExpired:
            return GitCloneResult(
                success=False,
                error=f"Clone timed out after {timeout} seconds"
            )
        except Exception as e:
            return GitCloneResult(success=False, error=str(e))

    def status(self, path: Path) -> GitStatus:
        """
        Get git repository status.

        Args:
            path: Repository path.

        Returns:
            GitStatus with current state.
        """
        if not self.is_git_repository(path):
            return GitStatus(error="Not a git repository")

        status = GitStatus()

        try:
            # Get current branch
            result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
            if result.returncode == 0:
                status.branch = result.stdout.strip()

            # Get tracking branch
            result = self._run_git(
                ["rev-parse", "--abbrev-ref", f"{status.branch}@{{upstream}}"],
                cwd=path
            )
            if result.returncode == 0:
                status.tracking_branch = result.stdout.strip()

            # Get ahead/behind count
            if status.tracking_branch:
                result = self._run_git(
                    ["rev-list", "--left-right", "--count", f"{status.tracking_branch}...HEAD"],
                    cwd=path
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split()
                    if len(parts) == 2:
                        status.behind = int(parts[0])
                        status.ahead = int(parts[1])

            # Get current commit
            result = self._run_git(["rev-parse", "HEAD"], cwd=path)
            if result.returncode == 0:
                status.commit_hash = result.stdout.strip()[:8]

            # Get commit message
            result = self._run_git(["log", "-1", "--format=%s"], cwd=path)
            if result.returncode == 0:
                status.commit_message = result.stdout.strip()

            # Get status (staged, modified, untracked)
            result = self._run_git(["status", "--porcelain"], cwd=path)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    status_code = line[:2]
                    file_path = line[3:]

                    if status_code[0] in "MADRC":
                        status.staged_files.append(file_path)
                    if status_code[1] in "MD":
                        status.modified_files.append(file_path)
                    if status_code == "??":
                        status.untracked_files.append(file_path)

            status.is_clean = (
                not status.staged_files and
                not status.modified_files and
                not status.untracked_files
            )

        except subprocess.TimeoutExpired:
            status.error = "Status command timed out"
        except Exception as e:
            status.error = str(e)

        return status

    def fetch(self, path: Path, remote: str = "origin", all_remotes: bool = False) -> GitOperationResult:
        """
        Fetch updates from remote.

        Args:
            path: Repository path.
            remote: Remote name (default: origin).
            all_remotes: Fetch from all remotes.

        Returns:
            GitOperationResult with status.
        """
        if not self.is_git_repository(path):
            return GitOperationResult(success=False, error="Not a git repository")

        try:
            args = ["fetch"]
            if all_remotes:
                args.append("--all")
            else:
                args.append(remote)

            result = self._run_git(args, cwd=path)

            if result.returncode != 0:
                return GitOperationResult(
                    success=False,
                    error=result.stderr.strip() or "Fetch failed"
                )

            return GitOperationResult(
                success=True,
                output=result.stdout.strip() or result.stderr.strip()
            )

        except subprocess.TimeoutExpired:
            return GitOperationResult(success=False, error="Fetch timed out")
        except Exception as e:
            return GitOperationResult(success=False, error=str(e))

    def pull(
        self,
        path: Path,
        remote: str = "origin",
        branch: str = None,
        rebase: bool = False
    ) -> GitOperationResult:
        """
        Pull changes from remote.

        Args:
            path: Repository path.
            remote: Remote name (default: origin).
            branch: Branch to pull (default: current tracking branch).
            rebase: Use rebase instead of merge.

        Returns:
            GitOperationResult with status and changed files.
        """
        if not self.is_git_repository(path):
            return GitOperationResult(success=False, error="Not a git repository")

        try:
            args = ["pull"]
            if rebase:
                args.append("--rebase")
            args.append(remote)
            if branch:
                args.append(branch)

            # Get current commit before pull
            before_result = self._run_git(["rev-parse", "HEAD"], cwd=path)
            before_commit = before_result.stdout.strip() if before_result.returncode == 0 else ""

            result = self._run_git(args, cwd=path)

            if result.returncode != 0:
                return GitOperationResult(
                    success=False,
                    error=result.stderr.strip() or "Pull failed"
                )

            # Get changed files
            changed_files = []
            if before_commit:
                diff_result = self._run_git(
                    ["diff", "--name-only", before_commit, "HEAD"],
                    cwd=path
                )
                if diff_result.returncode == 0:
                    changed_files = [f for f in diff_result.stdout.strip().split("\n") if f]

            return GitOperationResult(
                success=True,
                output=result.stdout.strip() or "Already up to date.",
                changed_files=changed_files
            )

        except subprocess.TimeoutExpired:
            return GitOperationResult(success=False, error="Pull timed out")
        except Exception as e:
            return GitOperationResult(success=False, error=str(e))

    def get_remote_url(self, path: Path, remote: str = "origin") -> Optional[str]:
        """Get the URL of a remote."""
        if not self.is_git_repository(path):
            return None

        try:
            result = self._run_git(["remote", "get-url", remote], cwd=path)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        return None

    def get_current_branch(self, path: Path) -> Optional[str]:
        """Get the current branch name."""
        if not self.is_git_repository(path):
            return None

        try:
            result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        return None

    def has_uncommitted_changes(self, path: Path) -> bool:
        """Check if there are uncommitted changes."""
        status = self.status(path)
        return not status.is_clean


# Singleton instance
_git_manager: Optional[GitManager] = None


def get_git_manager() -> GitManager:
    """Get the git manager singleton."""
    global _git_manager
    if _git_manager is None:
        _git_manager = GitManager()
    return _git_manager
