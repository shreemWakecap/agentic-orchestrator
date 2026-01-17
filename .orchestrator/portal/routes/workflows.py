"""Workflow-related API routes."""
import uuid
from fastapi import APIRouter, Depends, BackgroundTasks

from db import RunRepository
from portal.dependencies import get_run_repo
from portal.schemas.requests import PlanRequest, BuildRequest
from portal.schemas.responses import WorkflowStartResponse

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
) -> WorkflowStartResponse:
    """Start a sync-remote workflow to commit changes and create PR."""
    from portal.services.workflow_runner import run_syncing_workflow

    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="syncing")

    background_tasks.add_task(run_syncing_workflow, run_id)

    return WorkflowStartResponse(run_id=run_id, status="started")
