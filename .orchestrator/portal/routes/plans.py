"""Plan-related API routes."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from db import PlanRepository, BuildStateRepository, RunRepository, IProjectContextProvider
from portal.dependencies import get_plan_repo, get_build_state_repo, get_run_repo, get_recovery_service, get_project_context_provider
from portal.schemas.requests import MovePlanRequest, ResumeBuildRequest, RecoverPlanRequest, UpdatePlanRequest
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
    RecoveryAction,
    RecoveryOptionsResponse,
    ResetBuildResponse,
    StuckPlansResponse,
    StuckPlanInfo,
    CancelBuildResponse,
    UpdatePlanResponse,
)
from portal.services.recovery_service import RecoveryService
from portal.services.plan_service import PlanService


router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/counts")
async def get_plan_counts(
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> Dict[str, int]:
    """Get plan counts by status for dashboard stats.

    Returns counts for: pending, in_progress, completed, failed
    Used for real-time dashboard stats updates without full page refresh.
    """
    return {
        "pending": len(plan_repo.list_by_status("pending")),
        "in_progress": len(plan_repo.list_by_status("building")),
        "completed": len(plan_repo.list_by_status("completed")),
        "failed": len(plan_repo.list_by_status("failed")),
    }


def _get_plan_service(
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> PlanService:
    """Get plan service with injected dependencies."""
    return PlanService(plan_repo, build_state_repo)


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


@router.patch("/{plan_id}", response_model=UpdatePlanResponse)
async def update_plan(
    plan_id: str,
    request: UpdatePlanRequest,
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> UpdatePlanResponse:
    """Update a plan's content (goal, request, raw_content).

    Only allowed when the plan is in 'pending' status.
    At least one field must be provided for update.
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_status = plan.get("status", "pending")

    if current_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update plan in '{current_status}' status. Only plans in 'pending' status can be edited.",
        )

    # Check if at least one field is provided
    if not any([request.goal, request.request, request.raw_content]):
        raise HTTPException(
            status_code=400,
            detail="At least one field (goal, request, or raw_content) must be provided for update.",
        )

    # Build the update values, using existing values for fields not provided
    goal = request.goal if request.goal is not None else plan.get("goal", "")
    plan_request = request.request if request.request is not None else plan.get("request", "")
    raw_content = request.raw_content if request.raw_content is not None else plan.get("raw_content", "")

    # Track which fields were updated
    updated_fields = []
    if request.goal is not None:
        updated_fields.append("goal")
    if request.request is not None:
        updated_fields.append("request")
    if request.raw_content is not None:
        updated_fields.append("raw_content")

    try:
        plan_repo.update_content(plan_id, goal, plan_request, raw_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {str(e)}")

    return UpdatePlanResponse(
        status="updated",
        plan_id=plan_id,
        updated_fields=updated_fields,
        message=f"Plan updated successfully. Updated fields: {', '.join(updated_fields)}",
    )


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
    context_provider: IProjectContextProvider = Depends(get_project_context_provider),
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
    project_id = context_provider.get_project_id()
    run_repo.create(run_id, workflow="building", plan_id=plan_id, triggered_by="manual")

    # Start build workflow in background with project context
    background_tasks.add_task(run_building_workflow, run_id, plan_id, project_id)

    return WorkflowStartResponse(run_id=run_id, status="started", plan_id=plan_id)


@router.post("/{plan_id}/resume-build", response_model=WorkflowStartResponse)
async def resume_plan_build(
    plan_id: str,
    background_tasks: BackgroundTasks,
    request: ResumeBuildRequest = None,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
    run_repo: RunRepository = Depends(get_run_repo),
    context_provider: IProjectContextProvider = Depends(get_project_context_provider),
) -> WorkflowStartResponse:
    """Resume a build workflow for a plan that is stuck or failed.

    Unlike start-build, this endpoint allows resuming plans in:
    - building: Plan stuck in building state (e.g., server crash)
    - paused: Plan was intentionally paused
    - failed: Plan build failed and needs to be resumed

    Optionally accepts from_step to resume from a specific step.
    """
    # Import here to avoid circular imports
    from portal.services.workflow_runner import run_building_workflow_resume

    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")
    resumable_states = ["building", "paused", "failed", "in_progress"]

    if plan_state not in resumable_states:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is in '{plan_state}' state. Only plans in {resumable_states} states can be resumed.",
        )

    # Get from_step from request body if provided
    from_step = None
    if request:
        from_step = request.from_step

    # Validate from_step if provided
    if from_step:
        build_state = build_state_repo.get(plan_id)
        if build_state:
            step_states = build_state_repo.get_step_states(plan_id)
            step_ids = [s["step_id"] for s in step_states]
            if from_step not in step_ids:
                # Check if it's a valid step number/index format
                valid_steps = build_state.get("completed_steps", []) + build_state.get("failed_steps", [])
                if from_step not in valid_steps and not from_step.startswith("step-"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid from_step '{from_step}'. Available steps: {step_ids or 'none recorded yet'}",
                    )

    # Update plan status to building before starting
    plan_repo.update_status(plan_id, "building")

    # Create run entry in database with resume flag
    run_id = str(uuid.uuid4())[:8]
    project_id = context_provider.get_project_id()
    run_repo.create(run_id, workflow="building", plan_id=plan_id, triggered_by="manual")

    # Start build workflow in background with resume flag and project context
    background_tasks.add_task(run_building_workflow_resume, run_id, plan_id, from_step, project_id)

    return WorkflowStartResponse(run_id=run_id, status="resumed", plan_id=plan_id)


@router.delete("/{plan_id}", response_model=DeleteResponse)
async def delete_plan(
    plan_id: str,
    force: bool = False,
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> DeleteResponse:
    """Delete a plan from database.

    Args:
        plan_id: The ID of the plan to delete
        force: If True, allows deletion of active plans (building, in_progress, running).
               Default is False.

    Returns:
        DeleteResponse with deletion status

    Raises:
        404: Plan not found
        409: Plan is active and force=False
        500: Failed to delete plan
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    # Check if plan is in an active state
    active_states = ["building", "in_progress", "running"]
    if plan_state in active_states and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Plan '{plan_id}' is currently active (status: {plan_state}). "
            f"Use force=true to delete an active plan.",
        )

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
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> PlanStateResponse:
    """Get build state details for a plan including recovery status.

    Returns additional fields:
    - is_stuck: Whether the plan is stuck in building/in-progress state
    - minutes_since_update: Minutes since last update
    - can_resume: Whether the plan can be resumed from current state
    - can_cancel: Whether the plan can be cancelled
    - recovery_options: List of available recovery actions
    """
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
            is_stuck=False,
            minutes_since_update=None,
            can_resume=False,
            can_cancel=False,
            recovery_options=[],
        )

    step_states = build_state_repo.get_step_states(plan_id)
    step_states_dict = {s["step_id"]: s for s in step_states}

    build_status = build_state.get("status", "pending")
    updated_at = build_state.get("updated_at")
    completed_steps = build_state.get("completed_steps", [])
    failed_steps = build_state.get("failed_steps", [])
    current_step = build_state.get("current_step")

    # Calculate minutes since update
    minutes_since_update = None
    if updated_at:
        try:
            updated_time = datetime.fromisoformat(updated_at)
            delta = datetime.now() - updated_time
            minutes_since_update = round(delta.total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass

    # Determine if stuck (in active build state and stale)
    is_stuck = recovery_service.is_build_stale(plan_id)

    # Determine if can resume (has progress to resume from)
    can_resume = bool(current_step or completed_steps) and build_status in [
        "building", "in_progress", "failed", "paused"
    ]

    # Determine if can cancel (in active build state)
    can_cancel = build_status in ["building", "in_progress"]

    # Determine available recovery options
    recovery_options: List[str] = []
    if build_status in ["building", "in_progress"]:
        recovery_options.append("reset")
        recovery_options.append("cancel")
        if can_resume:
            recovery_options.append("resume")
    elif build_status == "failed":
        recovery_options.append("reset")
        if can_resume:
            recovery_options.append("resume")
        if failed_steps:
            recovery_options.append("retry_step")
    elif build_status == "paused":
        recovery_options.append("reset")
        recovery_options.append("resume")

    return PlanStateResponse(
        plan_id=plan_id,
        status=build_status,
        folder_state=plan_status,
        started_at=build_state.get("started_at"),
        updated_at=updated_at,
        current_phase=build_state.get("current_phase", 0),
        current_step=current_step,
        total_steps=build_state.get("total_steps", 0),
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        step_states=step_states_dict,
        files_created=build_state.get("files_created", []),
        files_modified=build_state.get("files_modified", []),
        last_error=build_state.get("last_error"),
        is_stuck=is_stuck,
        minutes_since_update=minutes_since_update,
        can_resume=can_resume,
        can_cancel=can_cancel,
        recovery_options=recovery_options,
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


@router.post("/{plan_id}/reset-build", response_model=ResetBuildResponse)
async def reset_plan_build(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> ResetBuildResponse:
    """Reset a plan's build state to pending, allowing a fresh restart.

    This endpoint:
    - Resets the plan status from building/failed to pending
    - Clears all step states
    - Allows the build to be started fresh
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_status = plan.get("status", "pending")

    # Only allow reset for building or failed plans
    if current_status not in ["building", "failed", "in_progress"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reset plan in '{current_status}' state. Only building, in_progress, or failed plans can be reset.",
        )

    # Get current build state to count steps being cleared
    build_state = build_state_repo.get(plan_id)
    steps_cleared = 0

    if build_state:
        step_states = build_state_repo.get_step_states(plan_id)
        steps_cleared = len(step_states)

        # Clear the build state
        try:
            build_state_repo.clear(plan_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear build state: {str(e)}")

    # Reset plan status to pending
    try:
        plan_repo.update_status(plan_id, "pending")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset plan status: {str(e)}")

    return ResetBuildResponse(
        plan_id=plan_id,
        previous_status=current_status,
        new_status="pending",
        steps_cleared=steps_cleared,
        message=f"Build state reset successfully. {steps_cleared} step states cleared.",
    )


@router.get("/{plan_id}/recovery-options", response_model=RecoveryOptionsResponse)
async def get_recovery_options(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> RecoveryOptionsResponse:
    """Get available recovery actions for a plan based on its current state.

    Returns different recovery options depending on whether the plan is:
    - building: can reset or wait
    - failed: can reset, resume from last step, or retry failed step
    - in_progress: can reset
    - pending: no recovery needed
    - completed: no recovery available
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_status = plan.get("status", "pending")
    build_state = build_state_repo.get(plan_id)

    actions: List[RecoveryAction] = []
    last_error = None
    failed_step = None
    completed_steps_count = 0
    total_steps_count = 0

    if build_state:
        last_error = build_state.get("last_error")
        failed_steps = build_state.get("failed_steps", [])
        completed_steps = build_state.get("completed_steps", [])
        total_steps_count = build_state.get("total_steps", 0)
        completed_steps_count = len(completed_steps)

        if failed_steps:
            failed_step = failed_steps[-1] if failed_steps else None

    # Determine available actions based on current state
    if current_status in ["building", "in_progress"]:
        actions.append(
            RecoveryAction(
                action="reset",
                label="Reset Build",
                description="Stop current build and reset to pending state. All progress will be lost.",
                available=True,
                endpoint=f"/api/plans/{plan_id}/reset-build",
                method="POST",
            )
        )

    elif current_status == "failed":
        actions.append(
            RecoveryAction(
                action="reset",
                label="Reset Build",
                description="Clear all build state and start fresh from the beginning.",
                available=True,
                endpoint=f"/api/plans/{plan_id}/reset-build",
                method="POST",
            )
        )

        # Resume option - continue from where it left off
        if completed_steps_count > 0:
            actions.append(
                RecoveryAction(
                    action="resume",
                    label="Resume Build",
                    description=f"Continue build from step {completed_steps_count + 1}, preserving {completed_steps_count} completed steps.",
                    available=True,
                    endpoint=f"/api/plans/{plan_id}/resume-build",
                    method="POST",
                )
            )

        # Retry failed step option
        if failed_step:
            actions.append(
                RecoveryAction(
                    action="retry_step",
                    label="Retry Failed Step",
                    description=f"Retry the failed step: {failed_step}",
                    available=True,
                    endpoint=f"/api/plans/{plan_id}/retry-step",
                    method="POST",
                )
            )

    elif current_status == "pending":
        actions.append(
            RecoveryAction(
                action="start",
                label="Start Build",
                description="Start building this plan.",
                available=True,
                endpoint=f"/api/plans/{plan_id}/start-build",
                method="POST",
            )
        )

    elif current_status == "completed":
        actions.append(
            RecoveryAction(
                action="reset",
                label="Rebuild",
                description="Reset and rebuild the plan from scratch.",
                available=False,
                endpoint=f"/api/plans/{plan_id}/reset-build",
                method="POST",
            )
        )

    can_recover = any(a.available for a in actions) and current_status not in ["pending", "completed"]

    return RecoveryOptionsResponse(
        plan_id=plan_id,
        current_status=current_status,
        can_recover=can_recover,
        actions=actions,
        last_error=last_error,
        failed_step=failed_step,
        completed_steps_count=completed_steps_count,
        total_steps_count=total_steps_count,
    )


@router.get("/recovery/stuck", response_model=StuckPlansResponse)
async def list_stuck_plans(
    threshold_minutes: Optional[int] = None,
    recovery_service: RecoveryService = Depends(get_recovery_service),
) -> StuckPlansResponse:
    """List all plans that are stuck in building/in-progress state.

    Returns plans that have been in an active build state (building or in_progress)
    without updates for longer than the threshold period.

    Args:
        threshold_minutes: Optional override for stale threshold (default is 10 minutes)
    """
    recoverable = recovery_service.get_recoverable_plans(threshold_minutes)

    plans = [
        StuckPlanInfo(
            plan_id=p.get("plan_id", ""),
            status=p.get("status", "unknown"),
            minutes_stale=p.get("minutes_stale", 0),
            progress_percent=p.get("progress_percent", 0.0),
            last_error=p.get("last_error"),
            current_step=p.get("current_step"),
            can_resume=p.get("can_resume", True),
        )
        for p in recoverable
    ]

    return StuckPlansResponse(plans=plans, count=len(plans))


@router.post("/{plan_id}/recover", response_model=WorkflowStartResponse)
async def recover_plan(
    plan_id: str,
    request: RecoverPlanRequest,
    background_tasks: BackgroundTasks,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
    run_repo: RunRepository = Depends(get_run_repo),
    context_provider: IProjectContextProvider = Depends(get_project_context_provider),
) -> WorkflowStartResponse:
    """Recover a stuck plan by resuming or restarting the build.

    Args:
        plan_id: The plan to recover
        request: RecoverPlanRequest with action ('resume', 'restart', 'cancel')
                 and optional from_step for resume

    Returns:
        WorkflowStartResponse with the new run_id
    """
    action = request.action
    from_step = request.from_step

    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_status = plan.get("status", "pending")
    recoverable_states = ["building", "in_progress", "failed", "paused"]

    if current_status not in recoverable_states:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is in '{current_status}' state. Only plans in {recoverable_states} states can be recovered.",
        )

    # Handle cancel action
    if action == "cancel":
        try:
            plan_repo.update_status(plan_id, "failed")
            build_state = build_state_repo.get(plan_id)
            if build_state:
                build_state_repo.update(plan_id, status="failed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to cancel plan: {str(e)}")

        return WorkflowStartResponse(run_id="", status="cancelled", plan_id=plan_id)

    if action == "restart":
        # Reset the build state first
        try:
            build_state = build_state_repo.get(plan_id)
            if build_state:
                build_state_repo.clear(plan_id)
            plan_repo.update_status(plan_id, "pending")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reset plan: {str(e)}")

        # Import and start fresh build
        from portal.services.workflow_runner import run_building_workflow

        run_id = str(uuid.uuid4())[:8]
        project_id = context_provider.get_project_id()
        run_repo.create(run_id, workflow="building", plan_id=plan_id, triggered_by="manual")
        background_tasks.add_task(run_building_workflow, run_id, plan_id, project_id)

        return WorkflowStartResponse(run_id=run_id, status="restarted", plan_id=plan_id)

    else:  # action == "resume"
        # Update plan status to building before starting
        plan_repo.update_status(plan_id, "building")

        # Resume from current state
        from portal.services.workflow_runner import run_building_workflow_resume

        run_id = str(uuid.uuid4())[:8]
        project_id = context_provider.get_project_id()
        run_repo.create(run_id, workflow="building", plan_id=plan_id, triggered_by="manual")
        background_tasks.add_task(run_building_workflow_resume, run_id, plan_id, from_step, project_id)

        return WorkflowStartResponse(run_id=run_id, status="resumed", plan_id=plan_id)


@router.post("/{plan_id}/cancel", response_model=CancelBuildResponse)
async def cancel_plan_build(
    plan_id: str,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> CancelBuildResponse:
    """Cancel a running or stuck build and mark it as paused.

    This endpoint:
    - Changes the plan status from building/in_progress to paused
    - Preserves the build state for potential later resumption
    - Does not clear completed steps

    The plan can later be resumed with resume-build or reset with reset-build.
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_status = plan.get("status", "pending")
    cancellable_states = ["building", "in_progress"]

    if current_status not in cancellable_states:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel plan in '{current_status}' state. Only plans in {cancellable_states} states can be cancelled.",
        )

    # Get build state for progress info
    build_state = build_state_repo.get(plan_id)
    steps_completed = 0
    steps_remaining = 0

    if build_state:
        completed_steps = build_state.get("completed_steps", [])
        total_steps = build_state.get("total_steps", 0)
        steps_completed = len(completed_steps)
        steps_remaining = max(0, total_steps - steps_completed)

    # Update using aggregate root pattern:
    # 1. Update Plan first (authoritative source of truth)
    plan_repo.update_status(plan_id, "paused")
    # 2. Cascade to build_states
    if build_state:
        build_state_repo.update(plan_id, status="paused")

    return CancelBuildResponse(
        status="cancelled",
        plan_id=plan_id,
        previous_status=current_status,
        message=f"Build cancelled. {steps_completed} steps completed, {steps_remaining} steps remaining.",
        steps_completed=steps_completed,
        steps_remaining=steps_remaining,
    )


@router.post("/{plan_id}/review", response_model=WorkflowStartResponse)
async def start_plan_review(
    plan_id: str,
    background_tasks: BackgroundTasks,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    run_repo: RunRepository = Depends(get_run_repo),
) -> WorkflowStartResponse:
    """Start a review workflow for a completed plan.

    This endpoint validates that:
    - The plan exists
    - The plan is in 'completed' status

    The review workflow analyzes the completed implementation and generates
    a review report.
    """
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    if plan_state != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is in '{plan_state}' state. Only completed plans can be reviewed.",
        )

    # Create run entry in database
    run_id = str(uuid.uuid4())[:8]
    run_repo.create(run_id, workflow="reviewing", plan_id=plan_id, triggered_by="manual")

    # Start review workflow in background
    from portal.services.workflow_runner import run_review_workflow
    background_tasks.add_task(run_review_workflow, run_id, plan_id)

    return WorkflowStartResponse(run_id=run_id, status="started", plan_id=plan_id)
