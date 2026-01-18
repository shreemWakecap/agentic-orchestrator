"""Git service for retrieving repository sync status information."""
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class GitSyncStatus:
    """Status information for git sync operations."""
    file_count: int = 0
    files: List[str] = field(default_factory=list)
    branch: str = ""
    has_changes: bool = False
    has_staged: bool = False
    has_unstaged: bool = False
    diff_summary: str = ""
    insertions: int = 0
    deletions: int = 0


class GitStatusService:
    """Service for git status operations.

    Provides methods to query git repository state for sync status
    display in the portal.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the git service.

        Args:
            project_root: Root directory of the git repository.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()

    def _run_git(self, cmd: List[str], check: bool = False) -> Optional[str]:
        """Run a git command and return output.

        Args:
            cmd: Git command arguments (without 'git' prefix).
            check: If True, raise exception on non-zero exit code.

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

    def is_git_repository(self) -> bool:
        """Check if the project root is a git repository."""
        result = self._run_git(["rev-parse", "--git-dir"])
        return result is not None

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return result or ""

    def get_sync_status(self) -> dict:
        """Get comprehensive sync status information.

        Returns a dict with:
            - file_count: Number of changed files
            - files: List of changed file paths
            - branch: Current branch name
            - has_changes: Whether there are any uncommitted changes
            - has_staged: Whether there are staged changes
            - has_unstaged: Whether there are unstaged changes
            - diff_summary: Human-readable summary of changes (e.g., "3 files, +50, -20")
            - insertions: Total lines inserted
            - deletions: Total lines deleted
        """
        status = GitSyncStatus()

        # Check if we're in a git repo
        if not self.is_git_repository():
            return self._status_to_dict(status)

        # Get current branch
        status.branch = self.get_current_branch()

        # Get status (porcelain format for parsing)
        porcelain = self._run_git(["status", "--porcelain"])
        if not porcelain:
            return self._status_to_dict(status)

        # Parse changed files
        lines = porcelain.split("\n")
        for line in lines:
            if not line:
                continue
            # Status format: XY filename
            # X = staged status, Y = unstaged status
            if len(line) >= 3:
                staged_status = line[0]
                unstaged_status = line[1]
                filename = line[3:].strip()

                # Track if file is staged or unstaged
                if staged_status != " " and staged_status != "?":
                    status.has_staged = True
                if unstaged_status != " ":
                    status.has_unstaged = True

                # Add to files list (avoid duplicates from rename)
                if " -> " in filename:
                    # Rename: old -> new
                    filename = filename.split(" -> ")[-1]
                if filename not in status.files:
                    status.files.append(filename)

        status.file_count = len(status.files)
        status.has_changes = status.file_count > 0

        # Get diff stats for a summary
        # First, stage all to get accurate stats
        if status.has_changes:
            # Get stats for all changes (staged + unstaged)
            diff_stat = self._run_git(["diff", "--stat", "HEAD"])
            if diff_stat:
                status.diff_summary = self._parse_diff_stat_summary(diff_stat)
                status.insertions, status.deletions = self._parse_insertions_deletions(diff_stat)

            # If HEAD fails (no commits yet), try without HEAD
            if not status.diff_summary:
                diff_stat = self._run_git(["diff", "--stat"])
                if diff_stat:
                    status.diff_summary = self._parse_diff_stat_summary(diff_stat)
                    status.insertions, status.deletions = self._parse_insertions_deletions(diff_stat)

            # Build fallback summary if still empty
            if not status.diff_summary:
                status.diff_summary = f"{status.file_count} file{'s' if status.file_count != 1 else ''} changed"

        return self._status_to_dict(status)

    def _parse_diff_stat_summary(self, diff_stat: str) -> str:
        """Parse git diff --stat output to extract summary line.

        The last line typically looks like:
        "3 files changed, 50 insertions(+), 20 deletions(-)"

        Returns:
            Summary string or empty string if not found.
        """
        lines = diff_stat.strip().split("\n")
        if lines:
            last_line = lines[-1].strip()
            # Check if it's a summary line (contains "changed" or "insertion" or "deletion")
            if "changed" in last_line or "insertion" in last_line or "deletion" in last_line:
                return last_line
        return ""

    def _parse_insertions_deletions(self, diff_stat: str) -> tuple:
        """Parse insertions and deletions from diff stat output.

        Returns:
            Tuple of (insertions, deletions) as integers.
        """
        insertions = 0
        deletions = 0

        lines = diff_stat.strip().split("\n")
        if not lines:
            return insertions, deletions

        last_line = lines[-1]

        # Parse "X insertions(+)"
        if "insertion" in last_line:
            import re
            match = re.search(r"(\d+)\s+insertion", last_line)
            if match:
                insertions = int(match.group(1))

        # Parse "X deletions(-)"
        if "deletion" in last_line:
            import re
            match = re.search(r"(\d+)\s+deletion", last_line)
            if match:
                deletions = int(match.group(1))

        return insertions, deletions

    def _status_to_dict(self, status: GitSyncStatus) -> dict:
        """Convert GitSyncStatus dataclass to dict."""
        return {
            "file_count": status.file_count,
            "files": status.files,
            "branch": status.branch,
            "has_changes": status.has_changes,
            "has_staged": status.has_staged,
            "has_unstaged": status.has_unstaged,
            "diff_summary": status.diff_summary,
            "insertions": status.insertions,
            "deletions": status.deletions,
        }
