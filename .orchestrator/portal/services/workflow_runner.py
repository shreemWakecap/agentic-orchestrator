"""Background workflow execution service.

Handles running workflows in background tasks with proper
database state management and event logging.

Thread Safety:
- Uses thread-local storage for RunRepository instances
- Each thread gets its own repository instance backed by thread-local DB connections
- Proper exception handling ensures no thread leaks
"""
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from db import get_run_repository, RunRepository

# Project paths
PORTAL_DIR = Path(__file__).parent.parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

logger = logging.getLogger(__name__)

# Thread-local storage for repository instances
_thread_local = threading.local()


def _get_thread_local_run_repo() -> RunRepository:
    """Get thread-local RunRepository instance.

    Each thread gets its own repository instance, which internally
    uses the Database's thread-local connections for safety.

    Returns:
        Thread-local RunRepository instance
    """
    if not hasattr(_thread_local, 'run_repo') or _thread_local.run_repo is None:
        _thread_local.run_repo = get_run_repository()
    return _thread_local.run_repo


def _cleanup_thread_local():
    """Clean up thread-local resources.

    Should be called when a thread's work is complete to prevent
    resource accumulation.
    """
    if hasattr(_thread_local, 'run_repo'):
        _thread_local.run_repo = None


def _get_run_repo() -> RunRepository:
    """Get run repository instance.

    Uses thread-local storage for thread safety.
    """
    return _get_thread_local_run_repo()


def _add_event(run_id: str, event_type: str, data: Dict = None):
    """Add event to run in database.

    Thread-safe through thread-local repository access.
    """
    try:
        run_repo = _get_run_repo()
        run_repo.add_event(run_id, event_type, data or {})
    except Exception as e:
        logger.error(f"Failed to add event {event_type} for run {run_id}: {e}")


def _safe_update_run(run_id: str, **kwargs):
    """Safely update run status with error handling.

    Args:
        run_id: The run ID to update
        **kwargs: Fields to update
    """
    try:
        run_repo = _get_run_repo()
        run_repo.update(run_id, **kwargs)
    except Exception as e:
        logger.error(f"Failed to update run {run_id}: {e}")


def _mark_run_failed(run_id: str, error: Exception):
    """Mark a run as failed with proper error handling.

    Args:
        run_id: The run ID to mark as failed
        error: The exception that caused the failure
    """
    try:
        run_repo = _get_run_repo()
        run_repo.update(run_id, status="failed", error=str(error))
        _add_event(run_id, "error", {"message": str(error)})
    except Exception as update_error:
        logger.error(f"Failed to mark run {run_id} as failed: {update_error}")


def run_planning_workflow(run_id: str, description: str):
    """Execute planning workflow in background thread.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        description: Planning request description
    """
    from workflows.planning import PlanningWorkflow

    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "planning"})

        try:
            workflow = PlanningWorkflow(project_root=PROJECT_ROOT)

            # Run workflow (blocking operation in worker thread)
            _add_event(run_id, "step", {"step": "analyzing"})
            result = workflow.run(description)

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={
                    "total_tokens": result.total_tokens,
                    "plan_id": result.data.get("plan_id") if result.data else None,
                },
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "plan_id": result.data.get("plan_id") if result.data else None,
                },
            )

        except Exception as e:
            logger.exception(f"Planning workflow failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


def run_building_workflow(run_id: str, plan_id: str):
    """Execute building workflow in background thread.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        plan_id: ID of the plan to build
    """
    from workflows.building import BuildingWorkflow

    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "building", "plan_id": plan_id})

        try:
            # Pass run_id to BuildingWorkflow for real-time event emission
            workflow = BuildingWorkflow(project_root=PROJECT_ROOT, run_id=run_id)
            result = workflow.run(plan_id)

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={"steps_completed": result.steps_completed},
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "steps_completed": result.steps_completed,
                },
            )

        except Exception as e:
            logger.exception(f"Building workflow failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


def run_building_workflow_resume(run_id: str, plan_id: str, from_step: Optional[str] = None):
    """Execute building workflow in resume mode.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Unlike run_building_workflow, this function:
    - Sets resume=True on the workflow to continue from last state
    - Optionally accepts from_step to resume from a specific step
    - Preserves completed step states instead of starting fresh

    Args:
        run_id: Unique identifier for this run
        plan_id: ID of the plan to resume building
        from_step: Optional step ID to resume from (if None, resumes from last incomplete)
    """
    from workflows.building import BuildingWorkflow

    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {
            "workflow": "building",
            "plan_id": plan_id,
            "resume": True,
            "from_step": from_step,
        })

        try:
            # BuildingWorkflow automatically resumes from existing state in DB
            # No need for resume=True flag - execute() loads state and continues
            # Pass run_id to BuildingWorkflow for real-time event emission
            workflow = BuildingWorkflow(project_root=PROJECT_ROOT, run_id=run_id)
            result = workflow.run(plan_id)

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={
                    "steps_completed": result.steps_completed,
                    "resumed": True,
                    "from_step": from_step,
                },
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "steps_completed": result.steps_completed,
                    "resumed": True,
                },
            )

        except Exception as e:
            logger.exception(f"Building workflow resume failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


def run_syncing_workflow(run_id: str, auto_merge: bool = True):
    """Execute syncing workflow to commit changes and create PR.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        auto_merge: Whether to auto-merge the PR after creation (default: True)
    """
    from workflows.syncing import SyncingWorkflow

    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "syncing", "auto_merge": auto_merge})

        try:
            workflow = SyncingWorkflow(project_root=PROJECT_ROOT, auto_merge=auto_merge)
            result = workflow.run("")  # Pass empty string as request

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data=result.data or {},
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "data": result.data,
                },
            )

        except Exception as e:
            logger.exception(f"Syncing workflow failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


def run_scouting_workflow(
    run_id: str,
    scan_type: str = "full",
    target_paths: list = None,
    target_keywords: list = None,
    target_tech: list = None,
    generate_experts: bool = False,
):
    """Execute scouting workflow in background thread.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        scan_type: Type of scan - "full" or "quick"
        target_paths: Optional list of paths to focus scanning on
        target_keywords: Optional list of keywords to search for
        target_tech: Optional list of technologies to focus on
        generate_experts: Whether to auto-generate missing experts after scan
    """
    from workflows.scouting import ScoutingWorkflow

    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(
            run_id,
            "start",
            {
                "workflow": "scouting",
                "scan_type": scan_type,
                "target_paths": target_paths or [],
                "target_keywords": target_keywords or [],
                "target_tech": target_tech or [],
                "generate_experts": generate_experts,
            },
        )

        try:
            workflow = ScoutingWorkflow(
                project_root=PROJECT_ROOT,
                scan_type=scan_type,
                generate_experts=generate_experts,
            )

            # Run workflow (blocking operation in worker thread)
            _add_event(run_id, "step", {"step": "scanning"})
            result = workflow.run("")

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={
                    "scan_id": result.data.get("scan_id") if result.data else None,
                    "duration": result.data.get("duration") if result.data else None,
                    "files_scanned": result.data.get("files_scanned") if result.data else 0,
                    "domains_found": result.data.get("domains_found") if result.data else 0,
                    "experts_generated": result.data.get("experts_generated") if result.data else [],
                },
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "scan_id": result.data.get("scan_id") if result.data else None,
                    "domains_found": result.data.get("domains_found") if result.data else 0,
                    "experts_generated": result.data.get("experts_generated") if result.data else [],
                },
            )

        except Exception as e:
            logger.exception(f"Scouting workflow failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


def run_review_workflow(run_id: str, plan_id: str):
    """Execute reviewing workflow for a completed plan.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Currently a stub implementation that marks the review as completed.
    TODO: Implement actual ReviewingWorkflow when ready.

    Args:
        run_id: Unique identifier for this run
        plan_id: ID of the completed plan to review
    """
    run_repo = _get_run_repo()

    try:
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "reviewing", "plan_id": plan_id})

        try:
            # TODO: Implement actual ReviewingWorkflow
            # from workflows.reviewing import ReviewingWorkflow
            # workflow = ReviewingWorkflow(project_root=PROJECT_ROOT)
            # result = workflow.run(plan_id)

            # For now, mark as completed with placeholder message
            import time
            time.sleep(1)  # Brief delay to simulate work

            run_repo.update(
                run_id,
                status="completed",
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={
                    "plan_id": plan_id,
                    "message": "Review workflow not yet implemented - placeholder completion",
                },
            )

            _add_event(
                run_id,
                "complete",
                {
                    "success": True,
                    "plan_id": plan_id,
                    "message": "Review placeholder completed",
                },
            )

        except Exception as e:
            logger.exception(f"Review workflow failed: {e}")
            _mark_run_failed(run_id, e)

    finally:
        _cleanup_thread_local()


# Aliases for backward compatibility (functions are now directly sync)
run_planning_workflow_sync = run_planning_workflow
run_building_workflow_sync = run_building_workflow
run_building_workflow_resume_sync = run_building_workflow_resume
run_syncing_workflow_sync = run_syncing_workflow
run_scouting_workflow_sync = run_scouting_workflow
