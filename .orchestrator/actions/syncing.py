"""
Syncing Workflow: Commits changes and creates PRs with AI-generated messages.

Steps:
1. Check prerequisites (git, gh CLI)
2. Check for changes
3. Create feature branch
4. Generate commit message via syncer agent
5. Commit and push
6. Generate PR description and create PR
7. Merge PR and delete remote branch
8. Pull changes to base branch
"""
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core import Agent, Workflow, WorkflowResult, get_agent_config
from core.symbols import CHECK, CROSS, WARNING


@dataclass
class SyncResult:
    """Result from a sync operation."""
    branch_name: str
    commit_hash: str
    commit_message: str
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    files_changed: list[str] = field(default_factory=list)


class SyncingWorkflow(Workflow):
    """
    Syncing workflow for committing changes and creating PRs.

    Uses the syncer agent to generate properly formatted commit messages
    following conventional commits format and structured PR descriptions.
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Optional[Path] = None,
    ):
        self.project_root = project_root
        self._config = get_agent_config(project_root)
        output_dir = output_dir or project_root / ".orchestrator" / "sync-logs"
        output_dir.mkdir(parents=True, exist_ok=True)

        super().__init__(name="Syncing Workflow", output_dir=output_dir)
        self._load_agents()

    def _load_agents(self) -> None:
        """Load the syncer agent."""
        try:
            self.register_agent(Agent.load("syncer", self.project_root))
        except FileNotFoundError:
            self.console.print(f"[yellow]{WARNING} Agent 'syncer' not found - will use fallback messages[/yellow]")

    def _run_git(self, cmd: list[str], capture: bool = True, check: bool = True) -> str:
        """Run a git command and return output."""
        result = subprocess.run(
            ["git"] + cmd,
            cwd=self.project_root,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(cmd)}\n{result.stderr}")
        return result.stdout.strip() if capture else ""

    def _run_gh(self, cmd: list[str], capture: bool = True, check: bool = True) -> str:
        """Run a GitHub CLI command and return output."""
        result = subprocess.run(
            ["gh"] + cmd,
            cwd=self.project_root,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"GitHub CLI failed: gh {' '.join(cmd)}\n{result.stderr}")
        return result.stdout.strip() if capture else ""

    def _pull_changes(self, base_branch: str) -> str:
        """Pull changes from remote into the local base branch.

        Args:
            base_branch: The branch to pull changes into (e.g., 'main', 'developmet')

        Returns:
            Output from the git pull command
        """
        return self._run_git(["pull", "origin", base_branch])

    def _merge_pr(self, pr_number: int) -> str:
        """Merge a pull request and delete the remote branch.

        Args:
            pr_number: The PR number to merge

        Returns:
            Output from the gh pr merge command
        """
        return self._run_gh([
            "pr", "merge", str(pr_number),
            "--merge",
            "--delete-branch"
        ])

    def _check_prerequisites(self) -> tuple[bool, str]:
        """Verify git and gh CLI are available and configured."""
        # Check git
        if not shutil.which("git"):
            return False, "Git CLI not found"

        # Check gh
        if not shutil.which("gh"):
            return False, "GitHub CLI not found. Install: https://cli.github.com/"

        # Check gh authentication
        try:
            self._run_gh(["auth", "status"], capture=True, check=True)
        except RuntimeError:
            return False, "GitHub CLI not authenticated. Run: gh auth login"

        # Check we're in a git repo
        try:
            self._run_git(["rev-parse", "--git-dir"])
        except RuntimeError:
            return False, "Not in a git repository"

        return True, ""

    def _get_changes(self) -> tuple[list[str], str, str]:
        """Get changed files, diff stats, and diff content."""
        status = self._run_git(["status", "--porcelain"])

        if not status:
            return [], "", ""

        changed_files = [line.split()[-1] for line in status.split("\n") if line]

        # Stage all to get proper diff
        self._run_git(["add", "-A"])

        diff_stats = self._run_git(["diff", "--cached", "--stat"])
        diff_content = self._run_git(["diff", "--cached"])

        # Truncate diff content if too large
        if len(diff_content) > 8000:
            diff_content = diff_content[:8000] + "\n... (truncated)"

        # Unstage (we'll stage again during commit)
        self._run_git(["reset", "HEAD"], check=False)

        return changed_files, diff_stats, diff_content

    def _parse_json_from_response(self, response: str) -> dict:
        """Extract JSON from agent response."""
        # Try to find JSON in code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {}

    def _parse_key_value(self, content: str) -> dict:
        """Parse KEY: VALUE format from agent response."""
        result = {}
        current_key = None
        current_value_lines = []

        for line in content.split('\n'):
            stripped = line.strip()
            if ':' in stripped and not stripped.startswith('-'):
                # Save previous value if any
                if current_key:
                    result[current_key] = '\n'.join(current_value_lines).strip()
                    current_value_lines = []
                # New key
                key, value = stripped.split(':', 1)
                current_key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                if value:
                    current_value_lines.append(value)
            elif current_key:
                current_value_lines.append(line.rstrip())

        # Save final value
        if current_key:
            result[current_key] = '\n'.join(current_value_lines).strip()

        return result

    def _get_fallback_commit_message(self, changed_files: list[str]) -> str:
        """Generate fallback commit message when agent unavailable."""
        return f"chore: sync changes ({len(changed_files)} files)"

    def _get_fallback_pr_description(self, diff_stats: str) -> str:
        """Generate fallback PR description when agent unavailable."""
        return f"""## Summary
Synced local changes to remote.

## Changes
```
{diff_stats}
```

## Testing
- Review the diff for correctness

## Breaking Changes
None
"""

    def _generate_commit_message(
        self,
        diff_stats: str,
        diff_content: str,
        changed_files: list[str]
    ) -> str:
        """Generate commit message via syncer agent."""
        if "syncer" not in self.agents:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Syncer agent not available, using fallback")
            return self._get_fallback_commit_message(changed_files)

        context = f"""## Diff Statistics
{diff_stats}

## Diff Content
{diff_content}

## Changed Files
{', '.join(changed_files)}
"""

        result = self.run_agent(
            "syncer",
            message="Generate a commit message following conventional commits format. Respond with COMMIT: [your commit message]",
            context=context,
            show_progress=True
        )

        if not result.success or not result.content:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Agent failed, using fallback")
            return self._get_fallback_commit_message(changed_files)

        # Parse KEY: VALUE response
        parsed = self._parse_key_value(result.content)
        commit_msg = parsed.get("commit", "").strip()

        if not commit_msg:
            self.console.print(f"  [yellow]{WARNING}[/yellow] No commit message in response, using fallback")
            return self._get_fallback_commit_message(changed_files)

        # Validate first line length
        first_line = commit_msg.split("\n")[0]
        if len(first_line) > 72:
            # Truncate to 72 chars
            commit_msg = first_line[:69] + "..." + commit_msg[len(first_line):]

        self.console.print(f"  [green]{CHECK}[/green] Generated: {first_line[:60]}...")
        return commit_msg

    def _generate_pr_description(
        self,
        commit_message: str,
        diff_stats: str,
        branch_info: dict
    ) -> str:
        """Generate PR description via syncer agent."""
        if "syncer" not in self.agents:
            return self._get_fallback_pr_description(diff_stats)

        context = f"""## Branch Info
Base: {branch_info.get('base', 'main')}
Head: {branch_info.get('head', '')}

## Commit Message
{commit_message}

## Diff Statistics
{diff_stats}
"""

        result = self.run_agent(
            "syncer",
            message="Generate a PR description. Respond with PR_SUMMARY:, PR_CHANGES:, PR_TESTING:, PR_BREAKING: sections.",
            context=context,
            show_progress=True
        )

        if not result.success or not result.content:
            return self._get_fallback_pr_description(diff_stats)

        parsed = self._parse_key_value(result.content)
        # Build PR description from parsed sections
        pr_desc = f"""## Summary
{parsed.get('pr_summary', 'Synced changes')}

## Changes
{parsed.get('pr_changes', '- See diff for details')}

## Testing
{parsed.get('pr_testing', '- Review the diff')}

## Breaking Changes
{parsed.get('pr_breaking', 'None')}
""".strip()

        if not pr_desc:
            return self._get_fallback_pr_description(diff_stats)

        return pr_desc

    def execute(self, request: str = "") -> WorkflowResult:
        """
        Execute the sync workflow.

        Args:
            request: Optional context/description (unused but required by base class)

        Returns:
            WorkflowResult with pr_url, branch_name, commit_hash in data
        """
        steps_completed = []

        self.console.print("\n[bold cyan]SYNC WORKFLOW[/bold cyan]")
        self.console.print("=" * 50)

        # Step 1: Check prerequisites
        self.console.print("\n[bold]Step 1/8:[/bold] Checking prerequisites...")
        ok, error = self._check_prerequisites()
        if not ok:
            self.console.print(f"  [red]{CROSS}[/red] {error}")
            return WorkflowResult(success=False, error=error)
        self.console.print(f"  [green]{CHECK}[/green] Git and GitHub CLI ready")
        steps_completed.append("prerequisites")

        # Step 2: Check for changes
        self.console.print("\n[bold]Step 2/8:[/bold] Checking for changes...")
        changed_files, diff_stats, diff_content = self._get_changes()
        if not changed_files:
            self.console.print(f"  [yellow]{WARNING}[/yellow] No changes to commit")
            return WorkflowResult(
                success=False,
                error="No changes to commit",
                steps_completed=steps_completed
            )
        self.console.print(f"  [green]{CHECK}[/green] Found {len(changed_files)} changed file(s)")
        steps_completed.append("check_changes")

        # Step 3: Get current branch and create feature branch
        self.console.print("\n[bold]Step 3/8:[/bold] Creating feature branch...")
        base_branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_branch = f"sync/{base_branch}/{timestamp}"
        self._run_git(["checkout", "-b", new_branch])
        self.console.print(f"  [green]{CHECK}[/green] Created: {new_branch}")
        steps_completed.append("create_branch")

        # Step 4: Generate commit message and commit
        self.console.print("\n[bold]Step 4/8:[/bold] Generating commit message...")
        self._run_git(["add", "-A"])
        commit_message = self._generate_commit_message(diff_stats, diff_content, changed_files)
        self._run_git(["commit", "-m", commit_message])
        commit_hash = self._run_git(["rev-parse", "--short", "HEAD"])
        self.console.print(f"  [green]{CHECK}[/green] Committed: {commit_hash}")
        steps_completed.append("commit")

        # Step 5: Push to remote
        self.console.print("\n[bold]Step 5/8:[/bold] Pushing to remote...")
        self._run_git(["push", "-u", "origin", new_branch])
        self.console.print(f"  [green]{CHECK}[/green] Pushed to origin/{new_branch}")
        steps_completed.append("push")

        # Step 6: Create PR
        self.console.print("\n[bold]Step 6/8:[/bold] Creating pull request...")
        branch_info = {"base": base_branch, "head": new_branch}
        pr_description = self._generate_pr_description(commit_message, diff_stats, branch_info)
        pr_title = commit_message.split("\n")[0]

        pr_url = None
        pr_number = None
        try:
            pr_url = self._run_gh([
                "pr", "create",
                "--base", base_branch,
                "--head", new_branch,
                "--title", pr_title,
                "--body", pr_description
            ])
            # Extract PR number from URL
            if pr_url:
                try:
                    pr_number = int(pr_url.rstrip("/").split("/")[-1])
                except (ValueError, IndexError):
                    pass
            self.console.print(f"  [green]{CHECK}[/green] PR created: {pr_url}")
            steps_completed.append("create_pr")
        except RuntimeError as e:
            self.console.print(f"  [red]{CROSS}[/red] PR creation failed: {e}")
            self.console.print(f"  [yellow]{WARNING}[/yellow] Manual: gh pr create --base {base_branch} --head {new_branch}")
            # Return to base branch
            self._run_git(["checkout", base_branch])
            return WorkflowResult(
                success=False,
                error=f"PR creation failed: {e}",
                steps_completed=steps_completed,
                total_tokens=self.total_tokens,
                data={
                    "branch_name": new_branch,
                    "commit_hash": commit_hash,
                    "commit_message": commit_message,
                    "files_changed": changed_files,
                }
            )

        # Step 7: Merge PR
        self.console.print("\n[bold]Step 7/8:[/bold] Merging pull request...")
        try:
            self._merge_pr(pr_number)
            self.console.print(f"  [green]{CHECK}[/green] PR #{pr_number} merged and branch deleted")
            steps_completed.append("merge_pr")
        except RuntimeError as e:
            self.console.print(f"  [red]{CROSS}[/red] PR merge failed: {e}")
            self.console.print(f"  [yellow]{WARNING}[/yellow] Manual: gh pr merge {pr_number} --merge --delete-branch")
            # Return to base branch
            self._run_git(["checkout", base_branch])
            return WorkflowResult(
                success=False,
                error=f"PR merge failed: {e}",
                steps_completed=steps_completed,
                total_tokens=self.total_tokens,
                data={
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "branch_name": new_branch,
                    "commit_hash": commit_hash,
                    "commit_message": commit_message,
                    "files_changed": changed_files,
                }
            )

        # Step 8: Pull changes to base branch
        self.console.print("\n[bold]Step 8/8:[/bold] Pulling changes to base branch...")
        # Return to base branch
        self._run_git(["checkout", base_branch])
        try:
            self._pull_changes(base_branch)
            self.console.print(f"  [green]{CHECK}[/green] Pulled latest changes to {base_branch}")
            steps_completed.append("pull")
        except RuntimeError as e:
            self.console.print(f"  [yellow]{WARNING}[/yellow] Pull failed: {e}")
            self.console.print(f"  [yellow]{WARNING}[/yellow] Manual: git pull origin {base_branch}")
            # Continue anyway - merge was successful

        self.console.print("\n" + "=" * 50)
        self.console.print("[bold green]SYNC COMPLETE[/bold green]")

        return WorkflowResult(
            success=True,
            steps_completed=steps_completed,
            total_tokens=self.total_tokens,
            data={
                "pr_url": pr_url,
                "pr_number": pr_number,
                "branch_name": new_branch,
                "commit_hash": commit_hash,
                "commit_message": commit_message,
                "files_changed": changed_files,
            }
        )


def run(args=None) -> int:
    """Run syncing action."""
    project_root = Path(__file__).parent.parent.parent

    workflow = SyncingWorkflow(project_root=project_root)
    result = workflow.run("")
    if result.success:
        print(f"\nPR: {result.data.get('pr_url')}")
    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(run(sys.argv[1:]))
