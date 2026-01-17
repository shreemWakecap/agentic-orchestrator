"""Plan-related API routes."""
import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from db import PlanRepository, BuildStateRepository, RunRepository
from portal.dependencies import get_plan_repo, get_build_state_repo, get_run_repo
from portal.schemas.requests import MovePlanRequest
from portal.schemas.responses import (
    PlanResponse,
    PlanDetailResponse,
    PlanListResponse,
    PlanFileResponse,
    PlanStateResponse,
    BuildStateResponse,
    DeleteResponse,
    MoveResponse,
    WorkflowStartResponse,
)
from portal.services.plan_service import PlanService

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _get_plan_service(
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> PlanService:
    """Get plan service with injected dependencies."""
    return PlanService(plan_repo)


@router.get("", response_model=PlanListResponse)
async def list_plans(
    plan_service: PlanService = Depends(_get_plan_service),
) -> PlanListResponse:
    """List all plans."""
    plans = await plan_service.get_all_plans()
    return PlanListResponse(plans=plans)


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id: str,
    plan_service: PlanService = Depends(_get_plan_service),
) -> PlanDetailResponse:
    """Get plan details."""
    plan = await plan_service.get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanDetailResponse(**plan)


@router.get("/{plan_id}/files/{filename}", response_model=PlanFileResponse)
async def get_plan_file(
    plan_id: str,
    filename: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> PlanFileResponse:
    """Get content of a specific file within a plan.

    Plans are stored in database now, so only 'plan.md' content is available.
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if filename == "plan.md":
        return PlanFileResponse(
            plan_id=plan_id,
            filename=filename,
            content=plan.get("raw_content", ""),
            state=plan.get("status", "pending"),
        )

    raise HTTPException(status_code=404, detail=f"File '{filename}' not found in plan")


@router.post("/{plan_id}/start-build", response_model=WorkflowStartResponse)
async def start_plan_build(
    plan_id: str,
    background_tasks: BackgroundTasks,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    run_repo: RunRepository = Depends(get_run_repo),
) -> WorkflowStartResponse:
    """Start a build workflow for a specific plan.

    Validates that the plan exists and is in 'pending' state before starting.
    """
    # Import here to avoid circular imports
    from portal.services.workflow_runner import run_building_workflow

    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    if plan_state != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is in '{plan_state}' state. Only pending plans can be built.",
        )

    # Create run entry in database
    run_id = str(uuid.uuid4())[:8]
    run_repo.create(run_id, workflow="building", plan_id=plan_id)

    # Start build workflow in background
    background_tasks.add_task(run_building_workflow, run_id, plan_id)

    return WorkflowStartResponse(run_id=run_id, status="started", plan_id=plan_id)


@router.delete("/{plan_id}", response_model=DeleteResponse)
async def delete_plan(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> DeleteResponse:
    """Delete a plan from database."""
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    try:
        plan_repo.delete(plan_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")

    return DeleteResponse(status="deleted", plan_id=plan_id, previous_state=plan_state)


@router.put("/{plan_id}/move", response_model=MoveResponse)
async def move_plan(
    plan_id: str,
    request: MovePlanRequest,
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> MoveResponse:
    """Move a plan between states (pending/failed)."""
    valid_target_states = ["pending", "failed"]

    if request.target_state not in valid_target_states:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target state '{request.target_state}'. Must be one of: {valid_target_states}",
        )

    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_state = plan.get("status", "pending")

    if current_state == "building":
        raise HTTPException(
            status_code=400,
            detail="Cannot move plan in 'building' state. Wait for build to complete or fail.",
        )

    if current_state == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot move completed plans. Create a new plan instead.",
        )

    if current_state == request.target_state:
        return MoveResponse(
            status="unchanged",
            plan_id=plan_id,
            previous_state=current_state,
            new_state=current_state,
            message=f"Plan is already in '{current_state}' state",
        )

    try:
        plan_repo.update_status(plan_id, request.target_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move plan: {str(e)}")

    return MoveResponse(
        status="moved",
        plan_id=plan_id,
        previous_state=current_state,
        new_state=request.target_state,
    )


@router.get("/{plan_id}/state", response_model=PlanStateResponse)
async def get_plan_state(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> PlanStateResponse:
    """Get build state details for a plan."""
    plan = plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_status = plan.get("status", "pending")
    build_state = build_state_repo.get(plan_id)

    if not build_state:
        return PlanStateResponse(
            plan_id=plan_id,
            status="pending",
            folder_state=plan_status,
        )

    step_states = build_state_repo.get_step_states(plan_id)
    step_states_dict = {s["step_id"]: s for s in step_states}

    return PlanStateResponse(
        plan_id=plan_id,
        status=build_state.get("status", "pending"),
        folder_state=plan_status,
        started_at=build_state.get("started_at"),
        updated_at=build_state.get("updated_at"),
        current_phase=build_state.get("current_phase", 0),
        current_step=build_state.get("current_step"),
        total_steps=build_state.get("total_steps", 0),
        completed_steps=build_state.get("completed_steps", []),
        failed_steps=build_state.get("failed_steps", []),
        step_states=step_states_dict,
        files_created=build_state.get("files_created", []),
        files_modified=build_state.get("files_modified", []),
        last_error=build_state.get("last_error"),
    )


@router.get("/{plan_id}/build-state", response_model=BuildStateResponse)
async def get_plan_build_state(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> BuildStateResponse:
    """Get detailed build state for a plan including progress percentage."""
    plan = plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_status = plan.get("status", "pending")
    build_state = build_state_repo.get(plan_id)

    if not build_state:
        return BuildStateResponse(
            plan_id=plan_id,
            status="pending",
            folder_state=plan_status,
            progress_percentage=0.0,
        )

    step_states = build_state_repo.get_step_states(plan_id)
    step_states_dict = {s["step_id"]: s for s in step_states}

    # Calculate progress percentage
    total_steps = build_state.get("total_steps", 0)
    completed_steps = build_state.get("completed_steps", [])
    failed_steps = build_state.get("failed_steps", [])

    if total_steps > 0:
        processed_steps = len(completed_steps) + len(failed_steps)
        progress_percentage = round((processed_steps / total_steps) * 100, 1)
    else:
        progress_percentage = 0.0

    return BuildStateResponse(
        plan_id=plan_id,
        status=build_state.get("status", "pending"),
        folder_state=plan_status,
        started_at=build_state.get("started_at"),
        updated_at=build_state.get("updated_at"),
        current_phase=build_state.get("current_phase", 0),
        current_step=build_state.get("current_step"),
        total_steps=total_steps,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        step_states=step_states_dict,
        files_created=build_state.get("files_created", []),
        files_modified=build_state.get("files_modified", []),
        last_error=build_state.get("last_error"),
        progress_percentage=progress_percentage,
    )
