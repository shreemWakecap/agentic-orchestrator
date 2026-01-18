"""Workflow-related API routes."""
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks

from db import RunRepository
from portal.dependencies import get_run_repo
from portal.schemas.requests import PlanRequest, BuildRequest, SyncRemoteRequest
from portal.schemas.responses import WorkflowStartResponse, SyncStatusResponse, GitStatisticsResponse

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("/plan", response_model=WorkflowStartResponse)
async def create_plan(
    request: PlanRequest,
    background_tasks: BackgroundTasks,
    run_repo: RunRepository = Depends(get_run_repo),
) -> WorkflowStartResponse:
    """Start a new planning workflow."""
    from portal.services.workflow_runner import run_planning_workflow

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="planning", description=request.description)

    background_tasks.add_task(run_planning_workflow, run_id, request.description)

    return WorkflowStartResponse(run_id=run_id, status="started")


@router.post("/build", response_model=WorkflowStartResponse)
async def start_build(
    request: BuildRequest,
    background_tasks: BackgroundTasks,
    run_repo: RunRepository = Depends(get_run_repo),
) -> WorkflowStartResponse:
    """Start a build workflow.

    Note: plan_path is now interpreted as plan_id for database lookup.
    """
    from portal.services.workflow_runner import run_building_workflow

    run_id = str(uuid.uuid4())[:8]
    plan_id = request.plan_path  # plan_path is now plan_id

    # Create run entry in database
    run_repo.create(run_id, workflow="building", plan_id=plan_id)

    background_tasks.add_task(run_building_workflow, run_id, plan_id)

    return WorkflowStartResponse(run_id=run_id, status="started", plan_id=plan_id)


@router.post("/sync-remote", response_model=WorkflowStartResponse)
async def sync_remote(
    background_tasks: BackgroundTasks,
    run_repo: RunRepository = Depends(get_run_repo),
    request: SyncRemoteRequest = None,
) -> WorkflowStartResponse:
    """Start a sync-remote workflow to commit changes and create PR."""
    from portal.services.workflow_runner import run_syncing_workflow

    run_id = str(uuid.uuid4())[:8]
    auto_merge = request.auto_merge if request else True

    # Create run entry in database
    run_repo.create(run_id, workflow="syncing")

    background_tasks.add_task(run_syncing_workflow, run_id, auto_merge)

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
