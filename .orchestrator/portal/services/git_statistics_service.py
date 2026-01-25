"""Git statistics service for repository metrics and PR status."""
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .utils.git_runner import GitRunner


@dataclass
class CommitCount:
    """Commit count statistics (ahead/behind remote)."""
    ahead: int = 0
    behind: int = 0
    total_local: int = 0
    remote_branch: str = ""
    error: Optional[str] = None


@dataclass
class BranchInfo:
    """Current branch information."""
    name: str = ""
    is_detached: bool = False
    tracking_branch: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PRStatus:
    """Pull request status from GitHub CLI."""
    number: int = 0
    title: str = ""
    state: str = ""  # OPEN, CLOSED, MERGED
    url: str = ""
    head_branch: str = ""
    base_branch: str = ""
    mergeable: Optional[str] = None
    review_decision: Optional[str] = None
    checks_status: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    error: Optional[str] = None


@dataclass
class MergeStatus:
    """Merge status information."""
    can_merge: bool = False
    has_conflicts: bool = False
    conflict_files: List[str] = field(default_factory=list)
    merge_base: str = ""
    error: Optional[str] = None


@dataclass
class RemoteInfo:
    """Remote repository information."""
    name: str = ""
    fetch_url: str = ""
    push_url: str = ""
    head_branch: str = ""
    branches: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class FileStatistics:
    """File statistics for the repository."""
    total_files: int = 0
    tracked_files: int = 0
    untracked_files: int = 0
    ignored_files: int = 0
    staged_files: int = 0
    modified_files: int = 0
    deleted_files: int = 0
    renamed_files: int = 0
    added_files: int = 0
    error: Optional[str] = None


@dataclass
class GitStatistics:
    """Comprehensive git statistics."""
    commit_count: CommitCount = field(default_factory=CommitCount)
    branch_info: BranchInfo = field(default_factory=BranchInfo)
    pr_status: Optional[PRStatus] = None
    merge_status: MergeStatus = field(default_factory=MergeStatus)
    remote_info: RemoteInfo = field(default_factory=RemoteInfo)
    file_statistics: FileStatistics = field(default_factory=FileStatistics)


class GitStatisticsService:
    """Service for git statistics using only subprocess git/gh commands.

    Provides comprehensive repository statistics without any AI dependencies.
    All data is retrieved directly from git and GitHub CLI commands.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the git statistics service.

        Args:
            project_root: Root directory of the git repository.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self._git = GitRunner(self.project_root)

    def _run_git(self, cmd: List[str], check: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """Run a git command and return output and error.

        Delegates to shared GitRunner utility.

        Args:
            cmd: Git command arguments (without 'git' prefix).
            check: If True, return None on non-zero exit code.

        Returns:
            Tuple of (stdout, stderr) as strings, or (None, error_message) if failed.
        """
        return self._git.run_with_error(cmd, check)

    def _run_gh(self, cmd: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Run a GitHub CLI command and return output and error.

        Args:
            cmd: gh command arguments (without 'gh' prefix).

        Returns:
            Tuple of (stdout, stderr) as strings, or (None, error_message) if failed.
        """
        try:
            result = subprocess.run(
                ["gh"] + cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout.strip() if result.returncode == 0 else None, result.stderr.strip()
        except FileNotFoundError:
            return None, "GitHub CLI (gh) not installed"
        except Exception as e:
            return None, str(e)

    def is_git_repository(self) -> bool:
        """Check if the project root is a git repository."""
        output, _ = self._run_git(["rev-parse", "--git-dir"])
        return output is not None

    def get_commit_count(self, remote: str = "origin") -> CommitCount:
        """Get commit count statistics (ahead/behind remote).

        Args:
            remote: Remote name to compare against (default: origin).

        Returns:
            CommitCount with ahead/behind counts and total local commits.
        """
        result = CommitCount()

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Get current branch
        branch_output, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if not branch_output or branch_output == "HEAD":
            result.error = "Detached HEAD state or no commits"
            return result

        current_branch = branch_output
        result.remote_branch = f"{remote}/{current_branch}"

        # Fetch to ensure we have latest remote info (don't fail if fetch fails)
        self._run_git(["fetch", remote, "--quiet"])

        # Get ahead/behind counts
        rev_list_output, err = self._run_git([
            "rev-list",
            "--left-right",
            "--count",
            f"{result.remote_branch}...HEAD"
        ])

        if rev_list_output:
            parts = rev_list_output.split()
            if len(parts) == 2:
                result.behind = int(parts[0])
                result.ahead = int(parts[1])
        else:
            # Remote branch might not exist
            result.error = f"Remote branch {result.remote_branch} not found"

        # Get total local commits
        total_output, _ = self._run_git(["rev-list", "--count", "HEAD"])
        if total_output:
            result.total_local = int(total_output)

        return result

    def get_current_branch(self) -> BranchInfo:
        """Get current branch information.

        Returns:
            BranchInfo with branch name, detached state, and tracking info.
        """
        result = BranchInfo()

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Get branch name
        branch_output, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if branch_output:
            if branch_output == "HEAD":
                result.is_detached = True
                # Get commit hash for detached HEAD
                hash_output, _ = self._run_git(["rev-parse", "--short", "HEAD"])
                result.name = f"detached at {hash_output}" if hash_output else "detached HEAD"
            else:
                result.name = branch_output

        # Get tracking branch
        if not result.is_detached:
            tracking_output, _ = self._run_git([
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}"
            ])
            if tracking_output:
                result.tracking_branch = tracking_output

        return result

    def get_pr_status(self, pr_number: Optional[int] = None) -> PRStatus:
        """Get pull request status using GitHub CLI.

        Args:
            pr_number: Specific PR number to check. If None, checks current branch's PR.

        Returns:
            PRStatus with PR information or error if not found.
        """
        result = PRStatus()

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Build the gh command
        if pr_number:
            cmd = [
                "pr", "view", str(pr_number),
                "--json", "number,title,state,url,headRefName,baseRefName,mergeable,reviewDecision,additions,deletions,changedFiles,statusCheckRollup"
            ]
        else:
            cmd = [
                "pr", "view",
                "--json", "number,title,state,url,headRefName,baseRefName,mergeable,reviewDecision,additions,deletions,changedFiles,statusCheckRollup"
            ]

        output, err = self._run_gh(cmd)

        if not output:
            result.error = err or "No PR found for current branch"
            return result

        # Parse JSON output
        try:
            import json
            data = json.loads(output)

            result.number = data.get("number", 0)
            result.title = data.get("title", "")
            result.state = data.get("state", "")
            result.url = data.get("url", "")
            result.head_branch = data.get("headRefName", "")
            result.base_branch = data.get("baseRefName", "")
            result.mergeable = data.get("mergeable", None)
            result.review_decision = data.get("reviewDecision", None)
            result.additions = data.get("additions", 0)
            result.deletions = data.get("deletions", 0)
            result.changed_files = data.get("changedFiles", 0)

            # Parse status checks
            status_checks = data.get("statusCheckRollup", [])
            if status_checks:
                states = [check.get("state", "").upper() for check in status_checks if check.get("state")]
                if all(s == "SUCCESS" for s in states):
                    result.checks_status = "SUCCESS"
                elif any(s == "FAILURE" for s in states):
                    result.checks_status = "FAILURE"
                elif any(s == "PENDING" for s in states):
                    result.checks_status = "PENDING"
                else:
                    result.checks_status = "UNKNOWN"

        except (json.JSONDecodeError, KeyError) as e:
            result.error = f"Failed to parse PR data: {e}"

        return result

    def get_merge_status(self, target_branch: str = "main") -> MergeStatus:
        """Get merge status for current branch against target.

        Args:
            target_branch: Branch to check merge compatibility against.

        Returns:
            MergeStatus with merge compatibility and conflict information.
        """
        result = MergeStatus()

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Get merge base
        merge_base_output, _ = self._run_git(["merge-base", "HEAD", target_branch])
        if merge_base_output:
            result.merge_base = merge_base_output[:8]  # Short hash
        else:
            result.error = f"Cannot find merge base with {target_branch}"
            return result

        # Try a dry-run merge to check for conflicts
        # First, we need to do a tree-only merge check
        merge_tree_output, err = self._run_git([
            "merge-tree",
            result.merge_base,
            "HEAD",
            target_branch
        ])

        if merge_tree_output is not None:
            # Check for conflict markers in output
            if "<<<<<<" in merge_tree_output or "======" in merge_tree_output:
                result.has_conflicts = True
                result.can_merge = False

                # Extract conflict file names
                conflict_pattern = r"changed in both\s+base\s+\d+\s+\d+\s+\S+\s+(\S+)"
                conflicts = re.findall(conflict_pattern, merge_tree_output)
                result.conflict_files = list(set(conflicts))
            else:
                result.can_merge = True
                result.has_conflicts = False
        else:
            # merge-tree might not be available, try alternative approach
            # Check if there are any differences that would conflict
            diff_output, _ = self._run_git(["diff", "--name-only", target_branch])
            if diff_output is not None:
                result.can_merge = True  # Assume mergeable if we can at least diff

        return result

    def get_remote_info(self, remote: str = "origin") -> RemoteInfo:
        """Get remote repository information.

        Args:
            remote: Remote name to get info for (default: origin).

        Returns:
            RemoteInfo with URLs and branch information.
        """
        result = RemoteInfo()
        result.name = remote

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Get fetch URL
        fetch_url_output, _ = self._run_git(["remote", "get-url", remote])
        if fetch_url_output:
            result.fetch_url = fetch_url_output

        # Get push URL
        push_url_output, _ = self._run_git(["remote", "get-url", "--push", remote])
        if push_url_output:
            result.push_url = push_url_output

        # Get remote HEAD (default branch)
        head_output, _ = self._run_git(["symbolic-ref", f"refs/remotes/{remote}/HEAD"])
        if head_output:
            # Format: refs/remotes/origin/main -> main
            result.head_branch = head_output.split("/")[-1]
        else:
            # Try alternative: check remote directly
            remote_show_output, _ = self._run_git(["remote", "show", remote])
            if remote_show_output:
                head_match = re.search(r"HEAD branch:\s*(\S+)", remote_show_output)
                if head_match:
                    result.head_branch = head_match.group(1)

        # Get remote branches
        branches_output, _ = self._run_git(["branch", "-r", "--list", f"{remote}/*"])
        if branches_output:
            for line in branches_output.split("\n"):
                branch = line.strip()
                if branch and "->" not in branch:  # Skip HEAD -> origin/main entries
                    # Remove remote prefix
                    branch_name = branch.replace(f"{remote}/", "", 1)
                    result.branches.append(branch_name)

        return result

    def get_file_statistics(self) -> FileStatistics:
        """Get file statistics for the repository.

        Returns:
            FileStatistics with counts of files in various states.
        """
        result = FileStatistics()

        if not self.is_git_repository():
            result.error = "Not a git repository"
            return result

        # Get total tracked files
        tracked_output, _ = self._run_git(["ls-files"])
        if tracked_output:
            result.tracked_files = len(tracked_output.split("\n"))
            result.total_files = result.tracked_files

        # Get status for modified/staged/etc
        status_output, _ = self._run_git(["status", "--porcelain"])
        if status_output:
            for line in status_output.split("\n"):
                if not line or len(line) < 2:
                    continue

                staged_status = line[0]
                unstaged_status = line[1]

                # Count by status type
                if staged_status == "?" and unstaged_status == "?":
                    result.untracked_files += 1
                elif staged_status == "A" or unstaged_status == "A":
                    result.added_files += 1
                elif staged_status == "D" or unstaged_status == "D":
                    result.deleted_files += 1
                elif staged_status == "R" or unstaged_status == "R":
                    result.renamed_files += 1
                elif staged_status == "M" or unstaged_status == "M":
                    result.modified_files += 1

                # Count staged files
                if staged_status not in (" ", "?"):
                    result.staged_files += 1

        # Get ignored files count
        ignored_output, _ = self._run_git(["ls-files", "--others", "--ignored", "--exclude-standard"])
        if ignored_output:
            result.ignored_files = len([f for f in ignored_output.split("\n") if f])

        # Update total to include untracked
        result.total_files = result.tracked_files + result.untracked_files

        return result

    def get_all_statistics(self, remote: str = "origin", target_branch: str = "main") -> GitStatistics:
        """Get comprehensive git statistics.

        Args:
            remote: Remote name for commit comparison.
            target_branch: Target branch for merge status check.

        Returns:
            GitStatistics with all available statistics.
        """
        stats = GitStatistics()

        stats.commit_count = self.get_commit_count(remote)
        stats.branch_info = self.get_current_branch()
        stats.pr_status = self.get_pr_status()
        stats.merge_status = self.get_merge_status(target_branch)
        stats.remote_info = self.get_remote_info(remote)
        stats.file_statistics = self.get_file_statistics()

        return stats

    def to_dict(self, stats: GitStatistics) -> dict:
        """Convert GitStatistics to dictionary for JSON serialization.

        Args:
            stats: GitStatistics object to convert.

        Returns:
            Dictionary representation of the statistics.
        """
        from dataclasses import asdict
        return asdict(stats)
