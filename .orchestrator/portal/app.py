"""Web Portal for Agentic Orchestrator.

Provides a browser-based dashboard for:
- Viewing and managing plans
- Running workflows (plan, build, sync)
- Real-time progress streaming via SSE
- Historical run tracking
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add parent directory to path for imports
PORTAL_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.planning import PlanningWorkflow
from workflows.building import BuildingWorkflow
from workflows.syncing import SyncingWorkflow
from core.cost import CostEstimator, CostReporter, BudgetManager, Budget
from core.database import (
    get_plan_repository,
    get_build_state_repository,
    get_run_repository,
    PlanRepository,
    BuildStateRepository,
    RunRepository,
)

# Portal startup time for health endpoint uptime calculation
START_TIME = datetime.now()

# FastAPI app
app = FastAPI(
    title="Agentic Orchestrator Portal",
    description="Web portal for managing planning and building workflows",
    version="1.0.0"
)

# Setup templates and static files
templates = Jinja2Templates(directory=PORTAL_DIR / "templates")
STATIC_DIR = PORTAL_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Database repositories (initialized lazily)
_plan_repo: Optional[PlanRepository] = None
_build_state_repo: Optional[BuildStateRepository] = None
_run_repo: Optional[RunRepository] = None


def _get_plan_repo() -> PlanRepository:
    """Get plan repository (lazy initialization)."""
    global _plan_repo
    if _plan_repo is None:
        _plan_repo = get_plan_repository(PROJECT_ROOT)
    return _plan_repo


def _get_build_state_repo() -> BuildStateRepository:
    """Get build state repository (lazy initialization)."""
    global _build_state_repo
    if _build_state_repo is None:
        _build_state_repo = get_build_state_repository(PROJECT_ROOT)
    return _build_state_repo


def _get_run_repo() -> RunRepository:
    """Get run repository (lazy initialization)."""
    global _run_repo
    if _run_repo is None:
        _run_repo = get_run_repository(PROJECT_ROOT)
    return _run_repo


# ============== Pydantic Models ==============

class PlanRequest(BaseModel):
    """Request to create a new plan."""
    description: str


class BuildRequest(BaseModel):
    """Request to start a build."""
    plan_path: str


class MovePlanRequest(BaseModel):
    """Request to move a plan between states."""
    target_state: str  # pending, failed


# ============== HTML Routes ==============

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render main dashboard."""
    plan_repo = _get_plan_repo()
    run_repo = _get_run_repo()

    # Count plans by state from database
    counts = {
        "pending": len(plan_repo.list_by_status("pending")),
        "in_progress": len(plan_repo.list_by_status("building")),
        "completed": len(plan_repo.list_by_status("completed")),
        "failed": len(plan_repo.list_by_status("failed"))
    }

    # Get recent plans
    recent_plans = await _get_recent_plans(5)

    # Get active runs from database
    runs = run_repo.list_active()

    return templates.TemplateResponse(request, "dashboard.html", {
        "counts": counts,
        "recent_plans": recent_plans,
        "active_runs": runs
    })


@app.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request):
    """Render plans list page."""
    plans = await _get_all_plans()
    return templates.TemplateResponse(request, "plans.html", {
        "plans": plans
    })


@app.get("/plans/{plan_id}", response_class=HTMLResponse)
async def plan_detail(request: Request, plan_id: str):
    """Render plan detail page."""
    plan = await _get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return templates.TemplateResponse(request, "plan_detail.html", {
        "plan": plan
    })


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request):
    """Render runs history page."""
    run_repo = _get_run_repo()
    runs = run_repo.list_active()
    return templates.TemplateResponse(request, "runs.html", {
        "runs": runs
    })


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Render run detail page."""
    run_repo = _get_run_repo()
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return templates.TemplateResponse(request, "run_detail.html", {
        "run": run
    })


@app.get("/hello")
async def hello():
    """Return a simple Hello World message."""
    return {"message": "Hello World"}


# ============== API Routes ==============

@app.get("/api/hello")
async def api_hello():
    """Return a simple hello world message for testing."""
    return {"message": "hello world"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint returning server status, version, and uptime."""
    uptime_seconds = (datetime.now() - START_TIME).total_seconds()
    return {
        "status": "healthy",
        "version": app.version,
        "uptime_seconds": round(uptime_seconds, 2)
    }


@app.get("/health")
async def health():
    """Simple health check endpoint at root level."""
    uptime_seconds = (datetime.now() - START_TIME).total_seconds()
    return {
        "status": "ok",
        "version": app.version,
        "uptime_seconds": round(uptime_seconds, 2)
    }


@app.get("/api/plans")
async def api_list_plans():
    """List all plans."""
    plans = await _get_all_plans()
    return {"plans": plans}


@app.get("/api/plans/{plan_id}")
async def api_get_plan(plan_id: str):
    """Get plan details."""
    plan = await _get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@app.get("/api/plans/{plan_id}/files/{filename}")
async def api_get_plan_file(plan_id: str, filename: str):
    """Get content of a specific file within a plan.

    Plans are stored in database now, so only 'plan.md' content is available.
    """
    plan_repo = _get_plan_repo()
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Plans are now in database; only the raw content (plan.md) is available
    if filename == "plan.md":
        return {
            "plan_id": plan_id,
            "filename": filename,
            "content": plan.get("raw_content", ""),
            "state": plan.get("status", "pending")
        }

    raise HTTPException(status_code=404, detail=f"File '{filename}' not found in plan")


@app.post("/api/plans/{plan_id}/start-build")
async def api_start_plan_build(plan_id: str, background_tasks: BackgroundTasks):
    """Start a build workflow for a specific plan.

    Validates that the plan exists and is in 'pending' state before starting.
    Returns run_id for progress tracking.
    """
    plan_repo = _get_plan_repo()
    run_repo = _get_run_repo()

    # Find the plan and validate its state
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    # Validate plan is in pending state
    if plan_state != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is in '{plan_state}' state. Only pending plans can be built."
        )

    # Create run entry in database
    run_id = str(uuid.uuid4())[:8]
    run_repo.create(run_id, workflow="building", plan_id=plan_id)

    # Start build workflow in background (pass plan_id, not path)
    background_tasks.add_task(_run_building_workflow, run_id, plan_id)

    return {"run_id": run_id, "status": "started", "plan_id": plan_id}


@app.delete("/api/plans/{plan_id}")
async def api_delete_plan(plan_id: str):
    """Delete a plan from database.

    Removes the plan and associated build state (cascading).
    """
    plan_repo = _get_plan_repo()

    # Find the plan
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_state = plan.get("status", "pending")

    # Delete from database (cascades to steps, phases, build state)
    try:
        plan_repo.delete(plan_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")

    return {
        "status": "deleted",
        "plan_id": plan_id,
        "previous_state": plan_state
    }


@app.put("/api/plans/{plan_id}/move")
async def api_move_plan(plan_id: str, request: MovePlanRequest):
    """Move a plan between states (pending/failed).

    Only allows moving between pending and failed states.
    Plans in building or completed states cannot be moved.
    """
    plan_repo = _get_plan_repo()

    valid_target_states = ["pending", "failed"]

    if request.target_state not in valid_target_states:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target state '{request.target_state}'. Must be one of: {valid_target_states}"
        )

    # Find the plan
    plan = plan_repo.get_by_id(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    current_state = plan.get("status", "pending")

    # Validate current state allows moving
    if current_state == "building":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move plan in 'building' state. Wait for build to complete or fail."
        )

    if current_state == "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move completed plans. Create a new plan instead."
        )

    # Already in target state
    if current_state == request.target_state:
        return {
            "status": "unchanged",
            "plan_id": plan_id,
            "state": current_state,
            "message": f"Plan is already in '{current_state}' state"
        }

    # Update status in database
    try:
        plan_repo.update_status(plan_id, request.target_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move plan: {str(e)}")

    return {
        "status": "moved",
        "plan_id": plan_id,
        "previous_state": current_state,
        "new_state": request.target_state
    }


@app.get("/api/plans/{plan_id}/state")
async def api_get_plan_state(plan_id: str):
    """Get build state details for a plan.

    Returns the BuildState from database which includes:
    - status: pending, building, completed, failed, paused
    - current_phase and current_step
    - completed_steps and failed_steps lists
    - files_created and files_modified
    - step_states with detailed per-step info
    - last_error if any
    """
    plan_repo = _get_plan_repo()
    build_state_repo = _get_build_state_repo()

    # Verify plan exists
    plan = plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_status = plan.get("status", "pending")

    # Get build state from database
    build_state = build_state_repo.get(plan_id)

    if not build_state:
        # No build state exists yet - return a default state
        return {
            "plan_id": plan_id,
            "status": "pending",
            "started_at": None,
            "updated_at": None,
            "current_phase": 0,
            "current_step": None,
            "total_steps": 0,
            "completed_steps": [],
            "failed_steps": [],
            "step_states": {},
            "files_created": [],
            "files_modified": [],
            "last_error": None,
            "folder_state": plan_status
        }

    # Get step states
    step_states = build_state_repo.get_step_states(plan_id)
    step_states_dict = {s["step_id"]: s for s in step_states}

    return {
        "plan_id": plan_id,
        "status": build_state.get("status", "pending"),
        "started_at": build_state.get("started_at"),
        "updated_at": build_state.get("updated_at"),
        "current_phase": build_state.get("current_phase", 0),
        "current_step": build_state.get("current_step"),
        "total_steps": build_state.get("total_steps", 0),
        "completed_steps": build_state.get("completed_steps", []),
        "failed_steps": build_state.get("failed_steps", []),
        "step_states": step_states_dict,
        "files_created": build_state.get("files_created", []),
        "files_modified": build_state.get("files_modified", []),
        "last_error": build_state.get("last_error"),
        "folder_state": plan_status
    }


@app.get("/api/plans/{plan_id}/build-state")
async def api_get_plan_build_state(plan_id: str):
    """Get detailed build state for a plan including step-level progress.

    Returns the full BuildState from database including:
    - status: pending, building, completed, failed, paused
    - completed_steps: List of completed step IDs
    - failed_steps: List of failed step IDs
    - step_states: Dict with detailed per-step info (status, started_at, completed_at, error)
    - progress_percentage: Calculated progress (0-100)
    - current_step: Currently executing step (if any)
    - total_steps: Total number of steps in the plan
    """
    plan_repo = _get_plan_repo()
    build_state_repo = _get_build_state_repo()

    # Verify plan exists
    plan = plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")

    plan_status = plan.get("status", "pending")

    # Get build state from database
    build_state = build_state_repo.get(plan_id)

    if not build_state:
        # No build state exists - return default structure
        return {
            "plan_id": plan_id,
            "status": "pending",
            "folder_state": plan_status,
            "started_at": None,
            "updated_at": None,
            "current_step": None,
            "total_steps": 0,
            "completed_steps": [],
            "failed_steps": [],
            "step_states": {},
            "progress_percentage": 0,
            "files_created": [],
            "files_modified": [],
            "last_error": None
        }

    # Get step states
    step_states = build_state_repo.get_step_states(plan_id)
    step_states_dict = {s["step_id"]: s for s in step_states}

    # Calculate progress percentage
    total_steps = build_state.get("total_steps", 0)
    completed_steps = build_state.get("completed_steps", [])
    failed_steps = build_state.get("failed_steps", [])

    if total_steps > 0:
        # Progress is based on completed + failed steps (both are "done" processing)
        processed_steps = len(completed_steps) + len(failed_steps)
        progress_percentage = round((processed_steps / total_steps) * 100, 1)
    else:
        progress_percentage = 0

    return {
        "plan_id": plan_id,
        "status": build_state.get("status", "pending"),
        "folder_state": plan_status,
        "started_at": build_state.get("started_at"),
        "updated_at": build_state.get("updated_at"),
        "current_step": build_state.get("current_step"),
        "current_phase": build_state.get("current_phase"),
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
        "step_states": step_states_dict,
        "progress_percentage": progress_percentage,
        "files_created": build_state.get("files_created", []),
        "files_modified": build_state.get("files_modified", []),
        "last_error": build_state.get("last_error")
    }


@app.post("/api/workflows/plan")
async def api_create_plan(request: PlanRequest, background_tasks: BackgroundTasks):
    """Start a new planning workflow."""
    run_repo = _get_run_repo()
    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="planning", description=request.description)

    background_tasks.add_task(_run_planning_workflow, run_id, request.description)

    return {"run_id": run_id, "status": "started"}


@app.post("/api/workflows/build")
async def api_start_build(request: BuildRequest, background_tasks: BackgroundTasks):
    """Start a build workflow.

    Note: plan_path is now interpreted as plan_id for database lookup.
    """
    run_repo = _get_run_repo()
    run_id = str(uuid.uuid4())[:8]

    # plan_path is now plan_id
    plan_id = request.plan_path

    # Create run entry in database
    run_repo.create(run_id, workflow="building", plan_id=plan_id)

    background_tasks.add_task(_run_building_workflow, run_id, plan_id)

    return {"run_id": run_id, "status": "started"}


@app.post("/api/workflows/sync-remote")
async def api_sync_remote(background_tasks: BackgroundTasks):
    """Start a sync-remote workflow to commit changes and create PR."""
    run_repo = _get_run_repo()
    run_id = str(uuid.uuid4())[:8]

    # Create run entry in database
    run_repo.create(run_id, workflow="syncing")

    background_tasks.add_task(_run_syncing_workflow, run_id)

    return {"run_id": run_id, "status": "started"}


@app.get("/api/runs")
async def api_list_runs(status: Optional[str] = None):
    """List all active runs with optional status filter.

    Args:
        status: Optional filter by status (pending, running, completed, failed)

    Returns:
        runs: List of run objects
        counts: Dict with running, completed, failed counts
    """
    run_repo = _get_run_repo()

    # Get runs from database
    runs = run_repo.list_active(status) if status else run_repo.list_active()

    # Calculate counts from all runs (not filtered)
    all_runs = run_repo.list_active()
    counts = {
        "running": len([r for r in all_runs if r.get("status") == "running"]),
        "completed": len([r for r in all_runs if r.get("status") == "completed"]),
        "failed": len([r for r in all_runs if r.get("status") == "failed"]),
        "pending": len([r for r in all_runs if r.get("status") == "pending"])
    }

    return {"runs": runs, "counts": counts}


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str):
    """Get run status."""
    run_repo = _get_run_repo()
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/runs/{run_id}/events")
async def api_stream_events(run_id: str):
    """Stream events from a running workflow via SSE."""
    run_repo = _get_run_repo()
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_event_id = 0
        while True:
            run = run_repo.get(run_id)
            if not run:
                break

            # Send new events from database
            events = run_repo.get_events(run_id, since_id=last_event_id)
            for event in events:
                # Update last_event_id
                if event.get("id", 0) > last_event_id:
                    last_event_id = event["id"]
                # Format event for SSE
                event_data = {
                    "type": event.get("event_type", "unknown"),
                    "timestamp": event.get("timestamp"),
                    **event.get("data", {})
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            # Check if done
            if run.get("status") in ["completed", "failed"]:
                yield f"data: {json.dumps({'type': 'done', 'status': run.get('status')})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# ============== Cost API Routes ==============

@app.get("/api/cost/estimate/{workflow}")
async def api_estimate_cost(workflow: str, request_text: str = "", plan_path: str = "", complexity: str = "medium"):
    """Get cost estimate for a workflow."""
    estimator = CostEstimator(PROJECT_ROOT)

    if workflow == "plan":
        estimate = estimator.estimate_planning(len(request_text or "medium request"), complexity)
    elif workflow == "build":
        path = Path(plan_path) if plan_path else PROJECT_ROOT / "dummy.md"
        estimate = estimator.estimate_building(path)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown workflow: {workflow}")

    return estimate.to_dict()


@app.get("/api/cost/summary")
async def api_cost_summary():
    """Get cost summary for dashboard."""
    estimator = CostEstimator(PROJECT_ROOT)
    reporter = CostReporter(estimator)
    budget_manager = BudgetManager(ORCHESTRATOR_DIR / "config" / "budget.json", estimator)

    return {
        "daily": reporter.daily_report(),
        "weekly": reporter.weekly_report(),
        "monthly": reporter.monthly_report(),
        "budget": budget_manager.get_remaining_budget()
    }


@app.get("/api/cost/report/{period}")
async def api_cost_report(period: str):
    """Get cost report for a specific period."""
    estimator = CostEstimator(PROJECT_ROOT)
    reporter = CostReporter(estimator)

    if period == "daily":
        return reporter.daily_report()
    elif period == "weekly":
        return reporter.weekly_report()
    elif period == "monthly":
        return reporter.monthly_report()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown period: {period}")


@app.get("/api/cost/budget")
async def api_get_budget():
    """Get current budget status."""
    estimator = CostEstimator(PROJECT_ROOT)
    budget_manager = BudgetManager(ORCHESTRATOR_DIR / "config" / "budget.json", estimator)
    return budget_manager.get_remaining_budget()


class BudgetUpdateRequest(BaseModel):
    """Request to update budget settings."""
    daily_limit: Optional[float] = None
    weekly_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_workflow_limit: Optional[float] = None


@app.post("/api/cost/budget")
async def api_set_budget(request: BudgetUpdateRequest):
    """Update budget settings."""
    estimator = CostEstimator(PROJECT_ROOT)
    budget_manager = BudgetManager(ORCHESTRATOR_DIR / "config" / "budget.json", estimator)

    budget = Budget(
        daily_limit=request.daily_limit,
        weekly_limit=request.weekly_limit,
        monthly_limit=request.monthly_limit,
        per_workflow_limit=request.per_workflow_limit
    )
    budget_manager.save_budget(budget)

    return {"status": "updated", "budget": budget_manager.get_remaining_budget()}


# ============== Helper Functions ==============

def _extract_plan_number(plan_id: str) -> int:
    """Extract numeric prefix from plan ID (e.g., '001_feature' -> 1)."""
    try:
        prefix = plan_id.split('_')[0]
        return int(prefix)
    except (ValueError, IndexError):
        return 999999  # Sort plans without numeric prefix at the end


def _extract_plan_info_from_content(content: str) -> Dict[str, str]:
    """Extract plan info (name, request, complexity) from plan content headers."""
    info = {}
    if not content:
        return info

    try:
        lines = content.split("\n")[:10]  # Only check first 10 lines

        for line in lines:
            line = line.strip()
            # Extract title from "# Plan: XXX"
            if line.startswith("# Plan:"):
                info["name"] = line[7:].strip()
            # Extract request from "Request: XXX"
            elif line.startswith("Request:"):
                info["request"] = line[8:].strip()
            # Extract complexity from "Complexity: XXX"
            elif line.startswith("Complexity:"):
                info["complexity"] = line[11:].strip()
    except Exception:
        pass

    return info


async def _get_all_plans() -> List[Dict]:
    """Get all plans from database, sorted by numeric prefix."""
    plan_repo = _get_plan_repo()
    db_plans = plan_repo.list_all()
    plans = []

    for db_plan in db_plans:
        plan_id = db_plan.get("plan_id", "")
        raw_content = db_plan.get("raw_content", "")

        plan_data = {
            "id": plan_id,
            "name": plan_id.replace("-", " ").replace("_", " ").title(),
            "state": db_plan.get("status", "pending"),
            "files": ["plan.md"],  # Only plan.md in database
            "modified": db_plan.get("updated_at", db_plan.get("created_at", "")),
            "request": db_plan.get("request", ""),
            "goal": db_plan.get("goal", "")
        }

        # Extract info from raw content headers
        plan_info = _extract_plan_info_from_content(raw_content)
        if plan_info.get("name"):
            plan_data["name"] = plan_info["name"]
        if plan_info.get("request"):
            plan_data["request"] = plan_info["request"]
        if plan_info.get("complexity"):
            plan_data["complexity"] = plan_info["complexity"]

        plans.append(plan_data)

    # Sort by numeric prefix (001_, 002_, etc.)
    return sorted(plans, key=lambda p: _extract_plan_number(p["id"]))


async def _get_recent_plans(limit: int) -> List[Dict]:
    """Get most recent plans."""
    all_plans = await _get_all_plans()
    return all_plans[:limit]


async def _get_plan_by_id(plan_id: str) -> Optional[Dict]:
    """Get a specific plan by ID from database."""
    plan_repo = _get_plan_repo()
    db_plan = plan_repo.get_by_id(plan_id)

    if not db_plan:
        return None

    raw_content = db_plan.get("raw_content", "")

    plan_data = {
        "id": plan_id,
        "name": plan_id.replace("-", " ").replace("_", " ").title(),
        "state": db_plan.get("status", "pending"),
        "modified": db_plan.get("updated_at", db_plan.get("created_at", "")),
        "request": db_plan.get("request", ""),
        "goal": db_plan.get("goal", ""),
        "content": raw_content,
        "files": ["plan.md"]  # Only plan.md in database
    }

    # Extract info from raw content headers
    plan_info = _extract_plan_info_from_content(raw_content)
    if plan_info.get("name"):
        plan_data["name"] = plan_info["name"]
    if plan_info.get("request"):
        plan_data["request"] = plan_info["request"]
    if plan_info.get("complexity"):
        plan_data["complexity"] = plan_info["complexity"]

    return plan_data


# ============== Background Tasks ==============

def _add_event(run_id: str, event_type: str, data: Dict = None):
    """Add event to run in database."""
    run_repo = _get_run_repo()
    run_repo.add_event(run_id, event_type, data or {})


async def _run_planning_workflow(run_id: str, description: str):
    """Execute planning workflow."""
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
            data={"total_tokens": result.total_tokens, "plan_id": result.data.get("plan_id") if result.data else None}
        )

        _add_event(run_id, "complete", {
            "success": result.success,
            "plan_id": result.data.get("plan_id") if result.data else None
        })

    except Exception as e:
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


async def _run_building_workflow(run_id: str, plan_id: str):
    """Execute building workflow."""
    run_repo = _get_run_repo()

    run_repo.update(run_id, status="running")
    _add_event(run_id, "start", {"workflow": "building", "plan_id": plan_id})

    try:
        workflow = BuildingWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run(plan_id)  # Now passes plan_id, not plan_path

        status = "completed" if result.success else "failed"
        run_repo.update(
            run_id,
            status=status,
            completed_at=datetime.now().isoformat(),
            progress=100,
            data={"steps_completed": result.steps_completed}
        )

        _add_event(run_id, "complete", {
            "success": result.success,
            "steps_completed": result.steps_completed
        })

    except Exception as e:
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


async def _run_syncing_workflow(run_id: str):
    """Execute syncing workflow to commit changes and create PR."""
    run_repo = _get_run_repo()

    run_repo.update(run_id, status="running")
    _add_event(run_id, "start", {"workflow": "syncing"})

    try:
        workflow = SyncingWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run("")  # Pass empty string as request (required by base Workflow)

        status = "completed" if result.success else "failed"
        run_repo.update(
            run_id,
            status=status,
            completed_at=datetime.now().isoformat(),
            progress=100,
            data=result.data or {}
        )

        _add_event(run_id, "complete", {
            "success": result.success,
            "data": result.data
        })

    except Exception as e:
        run_repo.update(run_id, status="failed", error=str(e))
        _add_event(run_id, "error", {"message": str(e)})


# ============== App Entry Point ==============

def run_portal(host: str = "127.0.0.1", port: int = 8000):
    """Run the web portal."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Alias for backward compatibility
run_server = run_portal


if __name__ == "__main__":
    run_server()
