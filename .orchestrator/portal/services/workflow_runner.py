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

from db import get_run_repository, get_plan_repository, get_build_state_repository, RunRepository

# Project paths
PORTAL_DIR = Path(__file__).parent.parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

logger = logging.getLogger(__name__)


def _get_project_path(project_id: Optional[str]) -> Path:
    """Resolve project path from project_id.

    Args:
        project_id: The project ID to resolve. If None, returns PROJECT_ROOT
                   (legacy single-project mode).

    Returns:
        Path to the project directory.

    Raises:
        ProjectNotFoundError: If project_id is provided but project not found.
        ProjectPathError: If project exists but path is invalid.
    """
    from core.exceptions import ProjectNotFoundError, ProjectPathError

    if not project_id:
        # Legacy mode: no project context, use default
        logger.warning("No project_id provided, using PROJECT_ROOT (legacy mode)")
        return PROJECT_ROOT

    from db.repositories.project import get_project_repository
    repo = get_project_repository()
    # Use as_dict=True to avoid DetachedInstanceError
    project = repo.get_by_slug_or_id(project_id, as_dict=True)

    if not project:
        raise ProjectNotFoundError(project_id)

    path_str = project.get("path")
    if not path_str:
        raise ProjectPathError(project_id, reason="Project has no path configured")

    project_path = Path(path_str)
    if not project_path.exists():
        raise ProjectPathError(
            project_id,
            path=path_str,
            reason="Path does not exist on filesystem"
        )

    if not project_path.is_dir():
        raise ProjectPathError(
            project_id,
            path=path_str,
            reason="Path is not a directory"
        )

    return project_path


# =============================================================================
# Workflow Phase Constants
# =============================================================================

# Planning workflow phases with progress ranges and display info
PLANNING_PHASES = {
    "analyzing": {
        "name": "Analyzing",
        "description": "Parsing request and analyzing codebase",
        "progress_start": 0,
        "progress_end": 25,
        "order": 1,
    },
    "consulting": {
        "name": "Consulting",
        "description": "Consulting domain experts for recommendations",
        "progress_start": 25,
        "progress_end": 50,
        "order": 2,
    },
    "generating": {
        "name": "Generating",
        "description": "Generating implementation plan",
        "progress_start": 50,
        "progress_end": 85,
        "order": 3,
    },
    "saving": {
        "name": "Saving",
        "description": "Saving plan to database",
        "progress_start": 85,
        "progress_end": 100,
        "order": 4,
    },
}

# Building workflow phases with progress ranges and display info
BUILDING_PHASES = {
    "loading": {
        "name": "Loading",
        "description": "Loading plan and preparing build environment",
        "progress_start": 0,
        "progress_end": 10,
        "order": 1,
    },
    "executing": {
        "name": "Executing",
        "description": "Executing build steps",
        "progress_start": 10,
        "progress_end": 90,
        "order": 2,
    },
    "verifying": {
        "name": "Verifying",
        "description": "Verifying build results",
        "progress_start": 90,
        "progress_end": 100,
        "order": 3,
    },
}

# All workflow types and their phases
WORKFLOW_PHASES = {
    "planning": PLANNING_PHASES,
    "building": BUILDING_PHASES,
}


def get_phase_info(workflow_type: str, phase_name: str) -> Optional[Dict]:
    """Get phase information for a workflow type and phase name.

    Args:
        workflow_type: The workflow type ('planning' or 'building')
        phase_name: The phase name

    Returns:
        Phase info dict with name, description, progress range, and order,
        or None if not found
    """
    phases = WORKFLOW_PHASES.get(workflow_type, {})
    return phases.get(phase_name)


def get_phases_for_workflow(workflow_type: str) -> Dict:
    """Get all phases for a workflow type.

    Args:
        workflow_type: The workflow type ('planning' or 'building')

    Returns:
        Dict of phase name to phase info, or empty dict if workflow not found
    """
    return WORKFLOW_PHASES.get(workflow_type, {})


def get_phase_display_name(workflow_type: str, phase_name: str) -> str:
    """Get human-readable display name for a phase.

    Args:
        workflow_type: The workflow type ('planning' or 'building')
        phase_name: The phase name

    Returns:
        Human-readable phase name, or the phase_name if not found
    """
    phase_info = get_phase_info(workflow_type, phase_name)
    if phase_info:
        return phase_info["name"]
    return phase_name.replace("_", " ").title()


def calculate_phase_progress(workflow_type: str, phase_name: str, phase_progress: float) -> int:
    """Calculate overall progress based on phase and progress within phase.

    Args:
        workflow_type: The workflow type ('planning' or 'building')
        phase_name: Current phase name
        phase_progress: Progress within the phase (0.0 to 1.0)

    Returns:
        Overall progress percentage (0-100)
    """
    phase_info = get_phase_info(workflow_type, phase_name)
    if not phase_info:
        return 0

    start = phase_info["progress_start"]
    end = phase_info["progress_end"]
    return int(start + (end - start) * phase_progress)


# =============================================================================
# Thread-local Storage
# =============================================================================

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


def _mark_run_failed(run_id: str, error: Exception, plan_id: str = None):
    """Mark a run as failed with proper error handling.

    Also updates plan status to 'failed' if plan_id is provided.

    Args:
        run_id: The run ID to mark as failed
        error: The exception that caused the failure
        plan_id: Optional plan ID to also mark as failed
    """
    try:
        run_repo = _get_run_repo()
        run_repo.update(run_id, status="failed", error=str(error))
        _add_event(run_id, "error", {"message": str(error)})

        # Also update plan status to failed
        if plan_id:
            _sync_plan_status(plan_id, "failed", str(error))
    except Exception as update_error:
        logger.error(f"Failed to mark run {run_id} as failed: {update_error}")


def _sync_plan_status(plan_id: str, status: str, error: str = None):
    """Sync plan and build_state status after workflow completion.

    This ensures Plan.status and BuildState.status stay in sync
    when a workflow completes or fails.

    Delegates to PlanStatusService for centralized status management.

    Args:
        plan_id: The plan ID to update
        status: New status ('completed', 'failed', 'building', etc.)
        error: Optional error message for failed builds
    """
    try:
        from portal.services.plan_status_service import PlanStatusService

        plan_repo = get_plan_repository()
        build_state_repo = get_build_state_repository()

        # Use centralized PlanStatusService for status updates
        status_service = PlanStatusService(plan_repo, build_state_repo)

        if error:
            status_service.fail(plan_id, error=error)
        else:
            status_service.update_status(plan_id, status)

        logger.info(f"Plan {plan_id} status synced to '{status}'")

    except Exception as e:
        logger.error(f"Failed to sync plan {plan_id} status to '{status}': {e}")


def _emit_phase_event(run_id: str, phase: str, progress: int, message: str = None):
    """Emit a phase transition event with progress update.

    Args:
        run_id: The run ID to emit event for
        phase: Phase name (analyzing, consulting_experts, generating_plan, saving)
        progress: Progress percentage (0-100)
        message: Optional human-readable message
    """
    _add_event(run_id, "phase_transition", {
        "phase": phase,
        "progress": progress,
        "message": message or f"Phase: {phase}",
    })
    _safe_update_run(run_id, progress=progress)

    # Broadcast via WebSocket (non-blocking)
    try:
        from portal.streaming.websocket import get_websocket_manager
        import asyncio

        manager = get_websocket_manager()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast_run_progress(run_id, phase, progress, message))
    except Exception as ws_error:
        logger.debug(f"WebSocket progress broadcast skipped: {ws_error}")


def _add_activity_log(run_id: str, activity: str, details: Dict = None):
    """Add an activity log entry to the run record.

    Args:
        run_id: The run ID to add activity for
        activity: Activity description
        details: Optional additional details
    """
    _add_event(run_id, "activity_log", {
        "activity": activity,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    })


def _fail_run_with_validation_error(
    run_id: str,
    error: Exception,
    error_code: str,
    plan_id: str = None,
):
    """Mark run as failed due to project validation error.

    Provides structured error information for UI display.

    Args:
        run_id: The run ID to mark as failed
        error: The validation exception
        error_code: Error code for categorization (PROJECT_NOT_FOUND, PROJECT_ARCHIVED, etc.)
        plan_id: Optional plan ID to also mark as failed
    """
    run_repo = _get_run_repo()

    run_repo.update(
        run_id,
        status="failed",
        completed_at=datetime.now().isoformat(),
        error=str(error),
        data={
            "error_code": error_code,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
    )

    _add_event(run_id, "error", {
        "code": error_code,
        "type": type(error).__name__,
        "message": str(error),
    })

    _add_activity_log(run_id, f"Validation failed: {error_code}", {
        "error": str(error),
    })

    # Also update plan status if provided
    if plan_id:
        _sync_plan_status(plan_id, "failed", str(error))


def run_planning_workflow(run_id: str, description: str, project_id: Optional[str] = None):
    """Execute planning workflow in background thread.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Emits granular phase events:
    - analyzing (0-25%): Parsing request and analyzing codebase
    - consulting_experts (25-50%): Consulting domain experts
    - generating_plan (50-85%): Generating implementation plan
    - saving (85-100%): Saving plan to database

    Args:
        run_id: Unique identifier for this run
        description: Planning request description
        project_id: Optional project ID for scoping (passed from API route)
    """
    from workflows.planning import PlanningWorkflow
    from db.project_context import project_context
    from core.project_validation import (
        validate_for_workflow_type,
        ProjectNotFoundError,
        ProjectPathError,
        ProjectArchivedError,
    )

    run_repo = _get_run_repo()

    # Set project context for this thread if provided
    # This ensures all database operations are scoped to the correct project
    context_token = None
    if project_id:
        context_token = project_context.set_project_sync(project_id)
        logger.debug(f"Set project context for planning workflow: {project_id}")

    try:
        # VALIDATION PHASE - Validate project before any work
        project_path = PROJECT_ROOT  # Default for legacy mode

        if project_id:
            try:
                validated = validate_for_workflow_type(project_id, "planning")
                project_path = validated.path
                logger.info(f"Validated project for planning: {validated.name}")
            except ProjectNotFoundError as e:
                logger.error(f"Project not found: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_NOT_FOUND")
                return
            except ProjectArchivedError as e:
                logger.error(f"Project archived: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_ARCHIVED")
                return
            except ProjectPathError as e:
                logger.error(f"Project path error: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_PATH_ERROR")
                return

        # EXECUTION PHASE - Project validated
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "planning", "project_id": project_id})
        _add_activity_log(run_id, "Workflow started", {"workflow_type": "planning", "project_id": project_id})

        try:
            # Phase 1: Analyzing (0-25%)
            _emit_phase_event(run_id, "analyzing", 5, "Initializing planning workflow")
            _add_activity_log(run_id, "Parsing request description")

            workflow = PlanningWorkflow(project_root=project_path)

            _emit_phase_event(run_id, "analyzing", 15, "Analyzing codebase and request")
            _add_activity_log(run_id, "Analyzing codebase context", {"description_length": len(description)})

            _emit_phase_event(run_id, "analyzing", 25, "Request analysis complete")

            # Phase 2: Consulting Experts (25-50%)
            _emit_phase_event(run_id, "consulting_experts", 30, "Identifying relevant domain experts")
            _add_activity_log(run_id, "Consulting domain experts")

            _emit_phase_event(run_id, "consulting_experts", 40, "Gathering expert recommendations")

            _emit_phase_event(run_id, "consulting_experts", 50, "Expert consultation complete")

            # Phase 3: Generating Plan (50-85%)
            _emit_phase_event(run_id, "generating_plan", 55, "Synthesizing implementation strategy")
            _add_activity_log(run_id, "Generating implementation plan")

            _emit_phase_event(run_id, "generating_plan", 65, "Creating step-by-step instructions")

            _emit_phase_event(run_id, "generating_plan", 75, "Defining file changes and actions")

            # Run the actual workflow (blocking operation)
            result = workflow.run(description)

            _emit_phase_event(run_id, "generating_plan", 85, "Plan generation complete")
            _add_activity_log(run_id, "Plan generated", {
                "success": result.success,
                "total_tokens": result.total_tokens,
            })

            # Phase 4: Saving (85-100%)
            _emit_phase_event(run_id, "saving", 90, "Saving plan to database")
            _add_activity_log(run_id, "Persisting plan data")

            plan_id = result.data.get("plan_id") if result.data else None

            status = "completed" if result.success else "failed"
            run_repo.update(
                run_id,
                status=status,
                completed_at=datetime.now().isoformat(),
                progress=100,
                data={
                    "total_tokens": result.total_tokens,
                    "plan_id": plan_id,
                },
            )

            _emit_phase_event(run_id, "saving", 100, "Plan saved successfully")
            _add_activity_log(run_id, "Workflow completed", {
                "status": status,
                "plan_id": plan_id,
            })

            _add_event(
                run_id,
                "complete",
                {
                    "success": result.success,
                    "plan_id": plan_id,
                },
            )

        except Exception as e:
            logger.exception(f"Planning workflow failed: {e}")
            _add_activity_log(run_id, "Workflow failed", {"error": str(e)})
            _mark_run_failed(run_id, e)

    finally:
        # Reset project context if it was set
        if context_token:
            project_context.reset_project(context_token)
        _cleanup_thread_local()


def run_building_workflow(run_id: str, plan_id: str, project_id: Optional[str] = None):
    """Execute building workflow in background thread.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        plan_id: ID of the plan to build
        project_id: Optional project ID for scoping (passed from API route)
    """
    from workflows.building import BuildingWorkflow
    from db.project_context import project_context
    from core.project_validation import (
        validate_for_workflow_type,
        ProjectNotFoundError,
        ProjectPathError,
        ProjectArchivedError,
    )

    run_repo = _get_run_repo()

    # Set project context for this thread if provided
    context_token = None
    if project_id:
        context_token = project_context.set_project_sync(project_id)
        logger.debug(f"Set project context for building workflow: {project_id}")

    try:
        # VALIDATION PHASE - Validate project before any work
        project_path = PROJECT_ROOT  # Default for legacy mode

        if project_id:
            try:
                validated = validate_for_workflow_type(project_id, "building")
                project_path = validated.path
                logger.info(f"Validated project for building: {validated.name}")
            except ProjectNotFoundError as e:
                logger.error(f"Project not found: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_NOT_FOUND", plan_id)
                return
            except ProjectArchivedError as e:
                logger.error(f"Project archived: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_ARCHIVED", plan_id)
                return
            except ProjectPathError as e:
                logger.error(f"Project path error: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_PATH_ERROR", plan_id)
                return

        # EXECUTION PHASE - Project validated
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {"workflow": "building", "plan_id": plan_id, "project_id": project_id})

        try:
            workflow = BuildingWorkflow(project_root=project_path)
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

            # CRITICAL: Sync plan status to match run status
            _sync_plan_status(plan_id, status)

        except Exception as e:
            logger.exception(f"Building workflow failed: {e}")
            _mark_run_failed(run_id, e, plan_id=plan_id)

    finally:
        # Reset project context if it was set
        if context_token:
            project_context.reset_project(context_token)
        _cleanup_thread_local()


def run_building_workflow_resume(run_id: str, plan_id: str, from_step: Optional[str] = None, project_id: Optional[str] = None):
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
        project_id: Optional project ID for scoping (passed from API route)
    """
    from workflows.building import BuildingWorkflow
    from db.project_context import project_context
    from core.project_validation import (
        validate_for_workflow_type,
        ProjectNotFoundError,
        ProjectPathError,
        ProjectArchivedError,
    )

    run_repo = _get_run_repo()

    # Set project context for this thread if provided
    context_token = None
    if project_id:
        context_token = project_context.set_project_sync(project_id)
        logger.debug(f"Set project context for building workflow resume: {project_id}")

    try:
        # VALIDATION PHASE - Validate project before any work
        project_path = PROJECT_ROOT  # Default for legacy mode

        if project_id:
            try:
                validated = validate_for_workflow_type(project_id, "building")
                project_path = validated.path
                logger.info(f"Validated project for building resume: {validated.name}")
            except ProjectNotFoundError as e:
                logger.error(f"Project not found: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_NOT_FOUND", plan_id)
                return
            except ProjectArchivedError as e:
                logger.error(f"Project archived: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_ARCHIVED", plan_id)
                return
            except ProjectPathError as e:
                logger.error(f"Project path error: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_PATH_ERROR", plan_id)
                return

        # EXECUTION PHASE - Project validated
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {
            "workflow": "building",
            "plan_id": plan_id,
            "resume": True,
            "from_step": from_step,
            "project_id": project_id,
        })

        try:
            # BuildingWorkflow automatically resumes from existing state in DB
            # No need for resume=True flag - execute() loads state and continues
            workflow = BuildingWorkflow(project_root=project_path)
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

            # CRITICAL: Sync plan status to match run status
            _sync_plan_status(plan_id, status)

        except Exception as e:
            logger.exception(f"Building workflow resume failed: {e}")
            _mark_run_failed(run_id, e, plan_id=plan_id)

    finally:
        # Reset project context if it was set
        if context_token:
            project_context.reset_project(context_token)
        _cleanup_thread_local()


def run_syncing_workflow(run_id: str, auto_merge: bool = True, project_id: Optional[str] = None):
    """Execute syncing workflow to commit changes and create PR.

    This function runs in a ThreadPoolExecutor worker thread.
    Thread-safe execution with proper cleanup on completion or error.

    Args:
        run_id: Unique identifier for this run
        auto_merge: Whether to auto-merge the PR after creation (default: True)
        project_id: Optional project ID for scoping git operations
    """
    from workflows.syncing import SyncingWorkflow
    from db.project_context import project_context
    from core.project_validation import (
        validate_for_workflow_type,
        ProjectNotFoundError,
        ProjectPathError,
        ProjectArchivedError,
    )

    run_repo = _get_run_repo()

    # Set project context for this thread if provided
    context_token = None
    if project_id:
        context_token = project_context.set_project_sync(project_id)
        logger.debug(f"Set project context for syncing workflow: {project_id}")

    try:
        # VALIDATION PHASE - Validate project before any work
        # Syncing requires git repository
        project_path = PROJECT_ROOT  # Default for legacy mode

        if project_id:
            try:
                validated = validate_for_workflow_type(project_id, "syncing")
                project_path = validated.path
                logger.info(f"Validated project for syncing: {validated.name}")
            except ProjectNotFoundError as e:
                logger.error(f"Project not found: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_NOT_FOUND")
                return
            except ProjectArchivedError as e:
                logger.error(f"Project archived: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_ARCHIVED")
                return
            except ProjectPathError as e:
                logger.error(f"Project path error: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_PATH_ERROR")
                return

        # EXECUTION PHASE - Project validated
        run_repo.update(run_id, status="running")
        _add_event(run_id, "start", {
            "workflow": "syncing",
            "auto_merge": auto_merge,
            "project_id": project_id,
        })

        try:
            workflow = SyncingWorkflow(project_root=project_path, auto_merge=auto_merge)
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
        # Reset project context if it was set
        if context_token:
            project_context.reset_project(context_token)
        _cleanup_thread_local()


def run_scouting_workflow(
    run_id: str,
    scan_type: str = "full",
    target_paths: list = None,
    target_keywords: list = None,
    target_tech: list = None,
    generate_experts: bool = False,
    project_id: Optional[str] = None,
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
        project_id: Optional project ID for scoping (passed from API route)
    """
    from workflows.scouting import ScoutingWorkflow
    from db.project_context import project_context
    from core.project_validation import (
        validate_for_workflow_type,
        ProjectNotFoundError,
        ProjectPathError,
        ProjectArchivedError,
    )

    run_repo = _get_run_repo()

    # Set project context for this thread if provided
    context_token = None
    if project_id:
        context_token = project_context.set_project_sync(project_id)
        logger.debug(f"Set project context for scouting workflow: {project_id}")

    try:
        # VALIDATION PHASE - Validate project before any work
        project_path = PROJECT_ROOT  # Default for legacy mode

        if project_id:
            try:
                validated = validate_for_workflow_type(project_id, "scouting")
                project_path = validated.path
                logger.info(f"Validated project for scouting: {validated.name}")
            except ProjectNotFoundError as e:
                logger.error(f"Project not found: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_NOT_FOUND")
                return
            except ProjectArchivedError as e:
                logger.error(f"Project archived: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_ARCHIVED")
                return
            except ProjectPathError as e:
                logger.error(f"Project path error: {e}")
                _fail_run_with_validation_error(run_id, e, "PROJECT_PATH_ERROR")
                return

        # EXECUTION PHASE - Project validated
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
                "project_id": project_id,
            },
        )

        try:
            workflow = ScoutingWorkflow(
                project_root=project_path,
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
        # Reset project context if it was set
        if context_token:
            project_context.reset_project(context_token)
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
