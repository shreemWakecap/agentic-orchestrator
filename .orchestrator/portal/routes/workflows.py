"""Workflow-related API routes."""
import uuid
from fastapi import APIRouter, Depends

from core.exceptions import GitRemoteNotConfiguredError
from db import RunRepository
from portal.dependencies import get_run_repo
from portal.schemas.requests import PlanRequest, BuildRequest, SyncRemoteRequest, ImproveRequestRequest
from portal.schemas.responses import WorkflowStartResponse, SyncStatusResponse, GitStatisticsResponse, ImproveRequestResponse, RemoteConfigResponse
from portal.services.task_manager import TaskManager, get_task_manager

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("/plan", response_model=WorkflowStartResponse)
async def create_plan(
    request: PlanRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Start a new planning workflow."""
    from portal.services.workflow_runner import run_planning_workflow_sync

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="planning", description=request.description)

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_planning_workflow_sync,
        args=(run_id, request.description),
        name=f"Planning: {request.description[:50]}..." if len(request.description) > 50 else f"Planning: {request.description}",
        task_id=run_id,
        task_type="plan",
        metadata={"run_id": run_id, "description": request.description[:100]},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.post("/build", response_model=WorkflowStartResponse)
async def start_build(
    request: BuildRequest,
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
) -> WorkflowStartResponse:
    """Start a build workflow.

    Note: plan_path is now interpreted as plan_id for database lookup.
    """
    from portal.services.workflow_runner import run_building_workflow_sync

    run_id = str(uuid.uuid4())[:8]
    plan_id = request.plan_path  # plan_path is now plan_id

    # Create run entry in database
    run_repo.create(run_id, workflow="building", plan_id=plan_id)

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_building_workflow_sync,
        args=(run_id, plan_id),
        name=f"Building: {plan_id}",
        task_id=run_id,
        task_type="build",
        metadata={"run_id": run_id, "plan_id": plan_id},
    )

    return WorkflowStartResponse(run_id=run_id, status="started", plan_id=plan_id)


@router.post("/sync-remote", response_model=WorkflowStartResponse)
async def sync_remote(
    run_repo: RunRepository = Depends(get_run_repo),
    task_manager: TaskManager = Depends(get_task_manager),
    request: SyncRemoteRequest = None,
) -> WorkflowStartResponse:
    """Start a sync-remote workflow to commit changes and create PR."""
    from portal.services.git_service import GitStatusService
    from portal.services.workflow_runner import run_syncing_workflow_sync

    # Validate git remote is configured before starting workflow
    git_service = GitStatusService()
    remote_config = git_service.validate_remote_configuration()
    if not remote_config.get("is_configured", False):
        # Get configuration help from git service for user-friendly error
        config_help = git_service.get_remote_configuration_help("origin")
        reason = remote_config.get("error") or remote_config.get("format_error")
        error = GitRemoteNotConfiguredError(remote_name="origin", reason=reason)
        # Attach configuration help to the exception details
        error.details["configuration_help"] = config_help
        raise error

    run_id = str(uuid.uuid4())[:8]
    auto_merge = request.auto_merge if request else True

    # Create run entry in database
    run_repo.create(run_id, workflow="syncing")

    # Submit to TaskManager for background execution
    task_manager.submit_task(
        func=run_syncing_workflow_sync,
        args=(run_id, auto_merge),
        name="Sync Remote",
        task_id=run_id,
        task_type="sync",
        metadata={"run_id": run_id, "auto_merge": auto_merge},
    )

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status() -> SyncStatusResponse:
    """Get current git sync status information.

    Returns readonly information about files that need to be synced,
    including counts, file lists, and diff summary.
    """
    from portal.services.git_service import GitStatusService

    git_service = GitStatusService()
    status = git_service.get_sync_status()

    # Count staged and unstaged files
    staged_count = sum(1 for f in status.get("files", []) if status.get("has_staged", False))
    unstaged_count = sum(1 for f in status.get("files", []) if status.get("has_unstaged", False))

    # If both staged and unstaged, the count reflects the state flags
    # Simplified: if has_staged, all files count as staged-relevant; same for unstaged
    if status.get("has_staged", False) and status.get("has_unstaged", False):
        staged_count = status.get("file_count", 0)
        unstaged_count = status.get("file_count", 0)
    elif status.get("has_staged", False):
        staged_count = status.get("file_count", 0)
        unstaged_count = 0
    elif status.get("has_unstaged", False):
        staged_count = 0
        unstaged_count = status.get("file_count", 0)
    else:
        staged_count = 0
        unstaged_count = 0

    return SyncStatusResponse(
        file_count=status.get("file_count", 0),
        files=status.get("files", []),
        branch=status.get("branch", ""),
        has_changes=status.get("has_changes", False),
        diff_summary=status.get("diff_summary", ""),
        staged_count=staged_count,
        unstaged_count=unstaged_count,
    )


@router.get("/remote-config", response_model=RemoteConfigResponse)
async def get_remote_config() -> RemoteConfigResponse:
    """Get remote repository configuration status.

    Returns information about whether a git remote is configured,
    allowing frontend to check configuration before attempting sync.
    """
    from portal.services.git_service import GitStatusService

    git_service = GitStatusService()
    config = git_service.validate_remote_configuration()

    is_configured = config.get("is_configured", False)
    url_valid = config.get("url_valid", False)
    format_error = config.get("format_error")
    configuration_help = None
    setup_instructions = []

    # Get setup instructions from git service help
    help_info = git_service.get_remote_configuration_help(config.get("remote_name", "origin"))

    if not is_configured or not url_valid:
        error = config.get("error", "")
        if "Not a git repository" in error:
            configuration_help = (
                "This directory is not a git repository. To initialize git and add a remote:\n\n"
                "  git init\n"
                "  git remote add origin <repository-url>\n\n"
                "Replace <repository-url> with your repository URL, for example:\n"
                "  - HTTPS: https://github.com/username/repo.git\n"
                "  - SSH: git@github.com:username/repo.git"
            )
            setup_instructions = [
                "git init",
                "git remote add origin <repository-url>",
                "git remote -v  # Verify the remote was added",
            ]
        else:
            configuration_help = (
                "No git remote is configured. To add a remote repository:\n\n"
                "  git remote add origin <repository-url>\n\n"
                "Replace <repository-url> with your repository URL, for example:\n"
                "  - HTTPS: https://github.com/username/repo.git\n"
                "  - SSH: git@github.com:username/repo.git\n\n"
                "To verify the remote was added:\n"
                "  git remote -v"
            )
            # Build setup_instructions from help_info
            if help_info.get("instructions"):
                # Use the "Add a new remote" instructions
                for section in help_info["instructions"]:
                    if section.get("title") == "Add a new remote":
                        setup_instructions = section.get("steps", [])
                        break
                # If no specific section found, use first instruction set
                if not setup_instructions and help_info["instructions"]:
                    setup_instructions = help_info["instructions"][0].get("steps", [])

    return RemoteConfigResponse(
        is_configured=is_configured,
        remote_name=config.get("remote_name", "origin"),
        fetch_url=config.get("fetch_url"),
        push_url=config.get("push_url"),
        url_valid=url_valid,
        format_error=format_error,
        error=config.get("error"),
        configuration_help=configuration_help,
        setup_instructions=setup_instructions,
    )


@router.get("/git-statistics", response_model=GitStatisticsResponse)
async def get_git_statistics() -> GitStatisticsResponse:
    """Get comprehensive git statistics including PR status.

    Returns repository statistics using only git/gh commands, no AI dependencies.
    Includes commit counts, branch info, PR status, and file statistics.
    """
    from portal.services.git_statistics_service import GitStatisticsService

    service = GitStatisticsService()
    stats = service.get_all_statistics()

    # Extract PR info
    pr_status = "none"
    pr_url = None
    pr_number = None
    if stats.pr_status and not stats.pr_status.error:
        if stats.pr_status.state:
            pr_status = stats.pr_status.state.lower()
        pr_url = stats.pr_status.url or None
        pr_number = stats.pr_status.number or None

    # Get last commit info
    last_commit_hash = None
    last_commit_message = None
    try:
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h|%s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|", 1)
            if len(parts) >= 1:
                last_commit_hash = parts[0]
            if len(parts) >= 2:
                last_commit_message = parts[1]
    except Exception:
        pass

    return GitStatisticsResponse(
        commits_ahead=stats.commit_count.ahead,
        commits_behind=stats.commit_count.behind,
        current_branch=stats.branch_info.name or "",
        remote_branch=stats.commit_count.remote_branch or None,
        pr_status=pr_status,
        pr_url=pr_url,
        pr_number=pr_number,
        last_commit_hash=last_commit_hash,
        last_commit_message=last_commit_message,
    )


@router.get("/branches")
async def list_local_branches():
    """List local sync branches (branches starting with 'sync/').

    Returns list of local branches that were created by the sync workflow,
    along with their last commit info.
    """
    import subprocess

    branches = []
    try:
        # Get all local branches
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)|%(committerdate:iso8601)|%(subject)"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line and "|" in line:
                    parts = line.split("|", 2)
                    branch_name = parts[0].strip()
                    # Only include sync/ branches
                    if branch_name.startswith("sync/"):
                        branches.append({
                            "name": branch_name,
                            "date": parts[1].strip() if len(parts) > 1 else "",
                            "message": parts[2].strip() if len(parts) > 2 else "",
                        })
    except Exception as e:
        return {"branches": [], "error": str(e)}

    return {"branches": branches}


@router.delete("/branches/{branch_name:path}")
async def delete_local_branch(branch_name: str):
    """Delete a local branch.

    Args:
        branch_name: Name of the branch to delete (must be a sync/ branch)
    """
    import subprocess

    # Safety check: only allow deleting sync/ branches
    if not branch_name.startswith("sync/"):
        return {"success": False, "error": "Can only delete sync/ branches"}

    try:
        # Force delete the branch
        result = subprocess.run(
            ["git", "branch", "-D", branch_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return {"success": True, "message": f"Deleted branch {branch_name}"}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/prs")
async def list_open_prs():
    """List open pull requests created by sync workflow.

    Returns list of open PRs with their status and merge info.
    """
    import subprocess
    import json as json_module

    prs = []
    try:
        # Get open PRs from GitHub CLI
        result = subprocess.run(
            ["gh", "pr", "list", "--json", "number,title,state,url,headRefName,baseRefName,mergeable,isDraft"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            pr_data = json_module.loads(result.stdout)
            for pr in pr_data:
                # Only include PRs from sync/ branches
                if pr.get("headRefName", "").startswith("sync/"):
                    prs.append({
                        "number": pr.get("number"),
                        "title": pr.get("title", ""),
                        "state": pr.get("state", "").lower(),
                        "url": pr.get("url", ""),
                        "head_branch": pr.get("headRefName", ""),
                        "base_branch": pr.get("baseRefName", ""),
                        "mergeable": pr.get("mergeable", "UNKNOWN"),
                        "is_draft": pr.get("isDraft", False),
                    })
    except FileNotFoundError:
        return {"prs": [], "error": "GitHub CLI not installed"}
    except Exception as e:
        return {"prs": [], "error": str(e)}

    return {"prs": prs}


@router.post("/prs/{pr_number}/merge")
async def merge_pr(pr_number: int):
    """Merge a pull request and delete its remote branch.

    Args:
        pr_number: The PR number to merge
    """
    import subprocess

    try:
        # Merge the PR with --merge flag and delete branch
        result = subprocess.run(
            ["gh", "pr", "merge", str(pr_number), "--merge", "--delete-branch"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return {"success": True, "message": f"Merged PR #{pr_number}"}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except FileNotFoundError:
        return {"success": False, "error": "GitHub CLI not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/pull-latest")
async def pull_latest():
    """Pull latest changes from remote for the current branch.

    Fetches and pulls the latest changes from origin for the current branch.
    """
    import subprocess

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if branch_result.returncode != 0:
            return {"success": False, "error": "Could not determine current branch"}

        current_branch = branch_result.stdout.strip()

        # Fetch first
        fetch_result = subprocess.run(
            ["git", "fetch", "origin"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Pull changes
        pull_result = subprocess.run(
            ["git", "pull", "origin", current_branch],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if pull_result.returncode == 0:
            return {
                "success": True,
                "message": f"Pulled latest from origin/{current_branch}",
                "output": pull_result.stdout.strip(),
            }
        else:
            return {"success": False, "error": pull_result.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_improve_request_task(draft: str) -> dict:
    """Background task function to run the request-improver agent.

    Args:
        draft: The original draft text to improve

    Returns:
        Dictionary with improved text, original text, and success status
    """
    import re
    from pathlib import Path
    from core import Agent

    # Get project root (go up from portal/routes to .orchestrator to project root)
    project_root = Path(__file__).parent.parent.parent.parent

    try:
        # Load the request-improver agent
        agent = Agent.load("request-improver", project_root)

        # Run the agent with the draft
        result = agent.run(draft)

        if not result.success or not result.content:
            return {
                "improved": draft,
                "original": draft,
                "success": False,
            }

        # Extract improved text from response
        # Agent should respond with "IMPROVED: ..." format
        content = result.content.strip()

        # Try to extract from IMPROVED: format
        improved_match = re.search(r'IMPROVED:\s*(.+)', content, re.DOTALL | re.IGNORECASE)
        if improved_match:
            improved = improved_match.group(1).strip()
        else:
            # If no IMPROVED: prefix, use the whole response
            improved = content

        # Clean up any trailing ``` or markdown artifacts
        improved = re.sub(r'```\s*$', '', improved).strip()

        return {
            "improved": improved,
            "original": draft,
            "success": True,
        }

    except FileNotFoundError:
        # Agent not found - return original
        return {
            "improved": draft,
            "original": draft,
            "success": False,
        }
    except Exception as e:
        # Log error but don't expose internals
        import logging
        logging.getLogger(__name__).exception(f"Request improvement failed: {e}")
        return {
            "improved": draft,
            "original": draft,
            "success": False,
        }


@router.post("/improve-request", response_model=ImproveRequestResponse)
async def improve_request(
    request: ImproveRequestRequest,
) -> ImproveRequestResponse:
    """Improve a draft feature request using AI.

    Takes a rough draft request and improves it using the request-improver agent.
    Returns the improved text directly.

    Returns:
    - improved: The AI-improved request text
    - original: The original draft text
    - success: Whether improvement succeeded
    """
    result = _run_improve_request_task(request.draft)
    return ImproveRequestResponse(**result)
