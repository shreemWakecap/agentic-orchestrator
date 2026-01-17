"""Background workflow execution service.

Handles running workflows in background tasks with proper
database state management and event logging.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from db import get_run_repository, RunRepository

# Project paths
PORTAL_DIR = Path(__file__).parent.parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

logger = logging.getLogger(__name__)


def _get_run_repo() -> RunRepository:
    """Get run repository instance."""
    return get_run_repository()


def _add_event(run_id: str, event_type: str, data: Dict = None):
    """Add event to run in database."""
    run_repo = _get_run_repo()
    run_repo.add_event(run_id, event_type, data or {})


async def run_planning_workflow(run_id: str, description: str):
    """Execute planning workflow in background."""
    from workflows.planning import PlanningWorkflow

    run_repo = _get_run_repo()

    run_repo.update(run_id, status="running")
    _add_event(run_id, "start", {"workflow": "planning"})

    try:
        workflow = PlanningWorkflow(project_root=PROJECT_ROOT)

        # Run workflow
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
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


async def run_building_workflow(run_id: str, plan_id: str):
    """Execute building workflow in background."""
    from workflows.building import BuildingWorkflow

    run_repo = _get_run_repo()

    run_repo.update(run_id, status="running")
    _add_event(run_id, "start", {"workflow": "building", "plan_id": plan_id})

    try:
        workflow = BuildingWorkflow(project_root=PROJECT_ROOT)
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
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


async def run_syncing_workflow(run_id: str):
    """Execute syncing workflow to commit changes and create PR."""
    from workflows.syncing import SyncingWorkflow

    run_repo = _get_run_repo()

    run_repo.update(run_id, status="running")
    _add_event(run_id, "start", {"workflow": "syncing"})

    try:
        workflow = SyncingWorkflow(project_root=PROJECT_ROOT)
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
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


async def run_scouting_workflow(
    run_id: str,
    scan_type: str = "full",
    target_paths: list = None,
    target_keywords: list = None,
    target_tech: list = None,
    generate_experts: bool = False,
):
    """Execute scouting workflow in background.

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

        # Run workflow
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
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})
