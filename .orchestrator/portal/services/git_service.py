"""Git service for retrieving repository sync status information."""
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


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

    def has_remote(self, remote_name: str = "origin") -> bool:
        """Check if a git remote is configured.

        Args:
            remote_name: Name of the remote to check. Defaults to 'origin'.

        Returns:
            True if the remote exists, False otherwise.
        """
        result = self._run_git(["remote", "get-url", remote_name])
        return result is not None

    def validate_remote_url_format(self, url: str) -> Tuple[bool, Optional[str]]:
        """Validate if a URL is a valid git remote URL format.

        Checks if the URL matches common git remote patterns:
        - HTTPS: https://github.com/user/repo.git
        - SSH: git@github.com:user/repo.git
        - Git protocol: git://github.com/user/repo.git
        - File path: /path/to/repo or file:///path/to/repo

        Args:
            url: The URL string to validate.

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str]).
            If valid, returns (True, None).
            If invalid, returns (False, "error description").
        """
        if not url:
            return False, "URL is empty"

        url = url.strip()
        if not url:
            return False, "URL is empty or whitespace only"

        # HTTPS pattern: https://host/path or https://host/path.git
        https_pattern = r'^https?://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](/.*)?$'

        # SSH pattern: git@host:path or user@host:path
        ssh_pattern = r'^[a-zA-Z0-9_][-a-zA-Z0-9_.]*@[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9]:.+$'

        # Git protocol: git://host/path
        git_protocol_pattern = r'^git://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](/.*)?$'

        # File path: /absolute/path or file:///path
        file_pattern = r'^(file://)?/[^\0]+'

        # Windows file path: C:\path or file:///C:/path
        windows_file_pattern = r'^(file:///)?[a-zA-Z]:[/\\][^\0]*$'

        if re.match(https_pattern, url):
            return True, None
        if re.match(ssh_pattern, url):
            return True, None
        if re.match(git_protocol_pattern, url):
            return True, None
        if re.match(file_pattern, url):
            return True, None
        if re.match(windows_file_pattern, url):
            return True, None

        # Try to identify common issues for helpful error messages
        if url.startswith("http://") or url.startswith("https://"):
            return False, "Invalid HTTPS URL format. Expected: https://github.com/user/repo.git"
        if "@" in url and ":" in url:
            return False, "Invalid SSH URL format. Expected: git@github.com:user/repo.git"
        if url.startswith("git://"):
            return False, "Invalid git:// URL format. Expected: git://github.com/user/repo.git"

        return False, f"Unrecognized URL format: '{url}'. Expected HTTPS (https://...) or SSH (git@host:path) format"

    def get_remote_configuration_help(self, remote_name: str = "origin") -> dict:
        """Get detailed help and instructions for configuring a git remote.

        Returns comprehensive setup instructions for various scenarios.

        Args:
            remote_name: Name of the remote. Defaults to 'origin'.

        Returns:
            Dict with:
                - remote_name: The remote name
                - instructions: List of instruction sections, each with 'title' and 'steps'
                - examples: List of example commands
                - common_issues: List of common issues and solutions
        """
        return {
            "remote_name": remote_name,
            "instructions": [
                {
                    "title": "Add a new remote",
                    "steps": [
                        f"1. Get the repository URL from your git hosting service (GitHub, GitLab, etc.)",
                        f"2. Run: git remote add {remote_name} <repository-url>",
                        f"3. Verify with: git remote -v",
                    ],
                },
                {
                    "title": "Update an existing remote URL",
                    "steps": [
                        f"1. Run: git remote set-url {remote_name} <new-repository-url>",
                        f"2. Verify with: git remote get-url {remote_name}",
                    ],
                },
                {
                    "title": "Remove and re-add remote",
                    "steps": [
                        f"1. Remove: git remote remove {remote_name}",
                        f"2. Add new: git remote add {remote_name} <repository-url>",
                    ],
                },
            ],
            "examples": [
                {
                    "description": "HTTPS URL (GitHub)",
                    "command": f"git remote add {remote_name} https://github.com/username/repository.git",
                },
                {
                    "description": "SSH URL (GitHub)",
                    "command": f"git remote add {remote_name} git@github.com:username/repository.git",
                },
                {
                    "description": "HTTPS URL (GitLab)",
                    "command": f"git remote add {remote_name} https://gitlab.com/username/repository.git",
                },
                {
                    "description": "SSH URL (GitLab)",
                    "command": f"git remote add {remote_name} git@gitlab.com:username/repository.git",
                },
            ],
            "common_issues": [
                {
                    "issue": "404 Not Found error",
                    "causes": [
                        "Repository does not exist at the specified URL",
                        "Repository is private and you lack access",
                        "URL contains typos in username or repository name",
                    ],
                    "solutions": [
                        "Verify the repository exists by visiting the URL in a browser",
                        "Check for typos in the username and repository name",
                        "Ensure you have access to private repositories",
                        "For SSH: Verify your SSH key is added to your account",
                    ],
                },
                {
                    "issue": "Authentication failed",
                    "causes": [
                        "Invalid credentials",
                        "Expired access token",
                        "SSH key not configured",
                    ],
                    "solutions": [
                        "For HTTPS: Use a personal access token instead of password",
                        "For SSH: Run 'ssh -T git@github.com' to test SSH connection",
                        "Regenerate and configure new credentials",
                    ],
                },
                {
                    "issue": "Remote not configured",
                    "causes": [
                        "Repository was initialized locally without a remote",
                        "Remote was removed",
                    ],
                    "solutions": [
                        f"Add a remote: git remote add {remote_name} <url>",
                        "Clone from an existing remote repository instead",
                    ],
                },
            ],
        }

    def validate_remote_configuration(
        self, remote_name: str = "origin", test_connectivity: bool = False
    ) -> dict:
        """Validate git remote configuration and return its details.

        Checks if the specified git remote exists and retrieves its
        fetch and push URLs. Optionally tests remote connectivity.

        Args:
            remote_name: Name of the remote to validate. Defaults to 'origin'.
            test_connectivity: If True, tests if the remote is reachable using
                              `git ls-remote --exit-code`. Defaults to False.

        Returns:
            Dict with:
                - remote_name: Name of the remote checked
                - fetch_url: URL used for fetching (or None if not configured)
                - push_url: URL used for pushing (or None if not configured)
                - is_configured: True if remote exists and has valid URLs
                - url_valid: True if the URL format is valid, False otherwise
                - format_error: Error message if URL format is invalid, None otherwise
                - error: Error message if remote is not configured, None otherwise
                - connectivity_ok: True if remote is reachable (only set if test_connectivity=True)
                - connectivity_error: Error message if connectivity test failed, None otherwise
                - connectivity_error_type: Type of connectivity error ('not_found', 'auth_failed', 'timeout', 'network_error', 'unknown')
                - is_404: True if the connectivity error is specifically a 404 Not Found
        """
        result = {
            "remote_name": remote_name,
            "fetch_url": None,
            "push_url": None,
            "is_configured": False,
            "url_valid": False,
            "format_error": None,
            "error": None,
            "connectivity_ok": None,
            "connectivity_error": None,
            "connectivity_error_type": None,
            "is_404": False,
        }

        # Check if we're in a git repo first
        if not self.is_git_repository():
            result["error"] = "Not a git repository"
            return result

        # Get the fetch URL
        fetch_url = self._run_git(["remote", "get-url", remote_name])
        if fetch_url is None:
            result["error"] = f"Remote '{remote_name}' is not configured"
            result["format_error"] = "No URL configured for this remote"
            return result

        # Check for empty URL
        if not fetch_url or not fetch_url.strip():
            result["error"] = f"Remote '{remote_name}' has an empty URL"
            result["format_error"] = "URL is empty"
            return result

        result["fetch_url"] = fetch_url

        # Validate the URL format
        url_valid, format_error = self.validate_remote_url_format(fetch_url)
        result["url_valid"] = url_valid
        result["format_error"] = format_error

        if not url_valid:
            result["error"] = f"Remote '{remote_name}' has an invalid URL format"

        # Get the push URL (may be different from fetch URL)
        push_url = self._run_git(["remote", "get-url", "--push", remote_name])
        result["push_url"] = push_url if push_url else fetch_url

        # Also validate push URL if different from fetch URL
        if push_url and push_url != fetch_url:
            push_url_valid, push_format_error = self.validate_remote_url_format(push_url)
            if not push_url_valid:
                result["url_valid"] = False
                result["format_error"] = f"Push URL invalid: {push_format_error}"
                result["error"] = f"Remote '{remote_name}' has an invalid push URL format"

        result["is_configured"] = True

        # Optionally test remote connectivity
        if test_connectivity:
            connectivity_ok, connectivity_error, error_type = self._test_remote_connectivity(remote_name)
            result["connectivity_ok"] = connectivity_ok
            result["connectivity_error"] = connectivity_error
            result["connectivity_error_type"] = error_type
            result["is_404"] = error_type == "not_found"

        return result

    def _test_remote_connectivity(
        self, remote_name: str = "origin", timeout: int = 10
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Test if a remote is reachable.

        Uses `git ls-remote --exit-code <remote> HEAD` to verify the remote
        URL is not only configured but also accessible.

        Args:
            remote_name: Name of the remote to test. Defaults to 'origin'.
            timeout: Timeout in seconds for the connectivity test. Defaults to 10.

        Returns:
            Tuple of (connectivity_ok: bool, error_message: Optional[str], error_type: Optional[str]).
            error_type can be: 'not_found', 'auth_failed', 'timeout', 'network_error', 'unknown'
        """
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--exit-code", remote_name, "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if result.returncode == 0:
                return True, None, None
            elif result.returncode == 2:
                # Exit code 2 means remote was reachable but HEAD ref not found
                return True, None, None
            else:
                error_msg = result.stderr.strip() if result.stderr else ""
                error_type, formatted_error = self._parse_connectivity_error(error_msg)
                return False, formatted_error, error_type
        except subprocess.TimeoutExpired:
            return False, f"Connection timed out after {timeout} seconds", "timeout"
        except Exception as e:
            return False, f"Connectivity test failed: {str(e)}", "unknown"

    def _parse_connectivity_error(self, error_output: str) -> Tuple[str, str]:
        """Parse git ls-remote error output to identify specific error types.

        Args:
            error_output: The stderr output from git ls-remote command.

        Returns:
            Tuple of (error_type: str, formatted_message: str).
            error_type is one of: 'not_found', 'auth_failed', 'network_error', 'unknown'
        """
        error_lower = error_output.lower()

        # 404 Not Found errors - repository doesn't exist or URL is wrong
        if "404" in error_output or "not found" in error_lower:
            return (
                "not_found",
                "Repository not found (404). The repository may not exist, "
                "the URL may be incorrect, or you may not have access to a private repository."
            )

        # Repository not found patterns from various git hosts
        if "repository not found" in error_lower:
            return (
                "not_found",
                "Repository not found. Please verify the repository URL is correct "
                "and that you have access to the repository."
            )

        # Access denied / permission errors
        if "access denied" in error_lower or "permission denied" in error_lower:
            return (
                "auth_failed",
                "Access denied. You do not have permission to access this repository. "
                "Please check your credentials and repository access rights."
            )

        # Authentication failures
        if (
            "authentication failed" in error_lower
            or "invalid username or password" in error_lower
            or "could not read username" in error_lower
        ):
            return (
                "auth_failed",
                "Authentication failed. Please check your credentials. "
                "For HTTPS, use a personal access token. For SSH, verify your key is configured."
            )

        # SSH key issues
        if "host key verification failed" in error_lower:
            return (
                "auth_failed",
                "SSH host key verification failed. Run 'ssh-keyscan <host> >> ~/.ssh/known_hosts' "
                "or verify the remote host's authenticity."
            )

        if "permission denied (publickey)" in error_lower:
            return (
                "auth_failed",
                "SSH authentication failed. Your SSH key may not be added to the remote service. "
                "Run 'ssh -T git@<host>' to test your SSH connection."
            )

        # Network/DNS errors
        if (
            "could not resolve host" in error_lower
            or "name or service not known" in error_lower
            or "no such host" in error_lower
        ):
            return (
                "network_error",
                "Could not resolve host. Please check your internet connection "
                "and verify the hostname in the remote URL is correct."
            )

        if "connection refused" in error_lower:
            return (
                "network_error",
                "Connection refused. The git server may be down or blocking connections. "
                "Please try again later or check your firewall settings."
            )

        if "connection timed out" in error_lower or "timed out" in error_lower:
            return (
                "timeout",
                "Connection timed out. The server is taking too long to respond. "
                "Please check your network connection and try again."
            )

        # Fallback for unknown errors
        if error_output:
            return "unknown", f"Remote unreachable: {error_output}"

        return "unknown", "Remote unreachable: Unknown error"

    def validate_remote_connectivity(
        self, remote_name: str = "origin", timeout: int = 10
    ) -> dict:
        """Test remote connectivity and return detailed status.

        Performs a quick connectivity test using git ls-remote with a short
        timeout to detect if the remote URL exists and is accessible.

        Args:
            remote_name: Name of the remote to test. Defaults to 'origin'.
            timeout: Timeout in seconds for the test. Defaults to 10.

        Returns:
            Dict with:
                - remote_name: Name of the remote tested
                - is_reachable: True if remote is accessible
                - error_type: Type of error if failed ('not_found', 'auth_failed', 'timeout', 'network_error', 'unknown')
                - error_message: Detailed error message if failed
                - is_404: True if the error is specifically a 404 Not Found
                - help: Contextual help based on the error type
        """
        result = {
            "remote_name": remote_name,
            "is_reachable": False,
            "error_type": None,
            "error_message": None,
            "is_404": False,
            "help": None,
        }

        # First check if remote is configured
        remote_config = self.validate_remote_configuration(
            remote_name=remote_name, test_connectivity=False
        )

        if not remote_config["is_configured"]:
            result["error_type"] = "not_configured"
            result["error_message"] = remote_config["error"] or f"Remote '{remote_name}' is not configured"
            result["help"] = self.get_remote_configuration_help(remote_name)
            return result

        if not remote_config["url_valid"]:
            result["error_type"] = "invalid_url"
            result["error_message"] = remote_config["format_error"] or "Invalid remote URL format"
            result["help"] = self.get_remote_configuration_help(remote_name)
            return result

        # Test connectivity
        is_reachable, error_msg, error_type = self._test_remote_connectivity(
            remote_name, timeout=timeout
        )

        result["is_reachable"] = is_reachable
        result["error_type"] = error_type
        result["error_message"] = error_msg

        # Set is_404 flag for 404-specific handling
        if error_type == "not_found":
            result["is_404"] = True
            result["help"] = self._get_404_help(remote_name, remote_config.get("fetch_url"))

        elif error_type == "auth_failed":
            result["help"] = self._get_auth_help(remote_name, remote_config.get("fetch_url"))

        elif error_type in ("timeout", "network_error"):
            result["help"] = self._get_network_help(remote_name)

        return result

    def _get_404_help(self, remote_name: str, url: Optional[str]) -> dict:
        """Get help specific to 404 Not Found errors."""
        return {
            "title": "Repository Not Found (404)",
            "description": "The remote repository could not be found. This usually means the repository doesn't exist at the specified URL.",
            "possible_causes": [
                "The repository URL contains a typo",
                "The repository has been deleted or moved",
                "The repository is private and you don't have access",
                "The repository hasn't been created yet",
            ],
            "solutions": [
                f"Verify the repository exists by visiting: {url}" if url else "Verify the repository exists",
                "Check for typos in the username and repository name",
                "If the repository is private, ensure you have been granted access",
                f"Update the remote URL: git remote set-url {remote_name} <correct-url>",
                "Create the repository on the remote service if it doesn't exist",
            ],
            "commands": {
                "check_current_url": f"git remote get-url {remote_name}",
                "update_url": f"git remote set-url {remote_name} <new-url>",
                "list_remotes": "git remote -v",
            },
        }

    def _get_auth_help(self, remote_name: str, url: Optional[str]) -> dict:
        """Get help specific to authentication errors."""
        is_ssh = url and (url.startswith("git@") or "ssh://" in url)

        if is_ssh:
            return {
                "title": "SSH Authentication Failed",
                "description": "Could not authenticate with the remote repository using SSH.",
                "possible_causes": [
                    "SSH key is not added to your account on the remote service",
                    "SSH key passphrase is incorrect",
                    "SSH agent is not running",
                    "Wrong SSH key is being used",
                ],
                "solutions": [
                    "Test your SSH connection: ssh -T git@github.com (or appropriate host)",
                    "Add your SSH key to ssh-agent: ssh-add ~/.ssh/id_rsa",
                    "Ensure your public key is added to your account settings on the remote service",
                    "Check which key is being used: ssh -vT git@github.com",
                ],
                "commands": {
                    "test_ssh": "ssh -T git@github.com",
                    "list_keys": "ssh-add -l",
                    "add_key": "ssh-add ~/.ssh/id_rsa",
                },
            }
        else:
            return {
                "title": "HTTPS Authentication Failed",
                "description": "Could not authenticate with the remote repository using HTTPS.",
                "possible_causes": [
                    "Invalid or expired personal access token",
                    "Incorrect username or password",
                    "Two-factor authentication requires a token instead of password",
                ],
                "solutions": [
                    "Use a personal access token (PAT) instead of a password",
                    "Generate a new token with appropriate repository permissions",
                    "Configure credential helper: git config --global credential.helper store",
                    "Clear cached credentials and re-authenticate",
                ],
                "commands": {
                    "clear_credentials": "git credential reject",
                    "configure_helper": "git config --global credential.helper store",
                },
            }

    def _get_network_help(self, remote_name: str) -> dict:
        """Get help specific to network/connectivity errors."""
        return {
            "title": "Network Connectivity Issue",
            "description": "Could not establish a connection to the remote repository.",
            "possible_causes": [
                "No internet connection",
                "Firewall blocking the connection",
                "VPN or proxy configuration issues",
                "Remote server is temporarily unavailable",
            ],
            "solutions": [
                "Check your internet connection",
                "Try accessing the repository URL in a web browser",
                "Check firewall and proxy settings",
                "Try again later if the server might be down",
            ],
            "commands": {
                "check_remote": f"git remote -v",
                "test_connection": f"git ls-remote {remote_name}",
            },
        }
