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

from actions.planning import PlanningWorkflow
from actions.building import BuildingWorkflow
from actions.syncing import SyncingWorkflow
from core.cost import CostEstimator, CostReporter, BudgetManager, Budget

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

# In-memory store for active runs
active_runs: Dict[str, Dict[str, Any]] = {}


# ============== Pydantic Models ==============

class PlanRequest(BaseModel):
    """Request to create a new plan."""
    description: str


class BuildRequest(BaseModel):
    """Request to start a build."""
    plan_path: str


# ============== HTML Routes ==============

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render main dashboard."""
    specs_dir = ORCHESTRATOR_DIR / "specs"

    # Count plans by state
    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0
    }

    for state in ["pending", "in-progress", "completed", "failed"]:
        state_dir = specs_dir / state
        if state_dir.exists():
            # Count plan directories (e.g., 001_feature-name/) not .md files
            count = len([d for d in state_dir.iterdir()
                        if d.is_dir() and not d.name.startswith('.')])
            key = state.replace("-", "_")
            counts[key] = count

    # Get recent plans
    recent_plans = await _get_recent_plans(5)

    # Get active runs
    runs = list(active_runs.values())

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
    runs = list(active_runs.values())
    return templates.TemplateResponse(request, "runs.html", {
        "runs": runs
    })


@app.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Render run detail page."""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run = active_runs[run_id]
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
    """Get content of a specific file within a plan."""
    specs_dir = ORCHESTRATOR_DIR / "specs"

    for state in ["pending", "in-progress", "completed", "failed"]:
        plan_dir = specs_dir / state / plan_id
        if plan_dir.exists() and plan_dir.is_dir():
            file_path = plan_dir / filename
            if file_path.exists() and file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                return {
                    "plan_id": plan_id,
                    "filename": filename,
                    "content": content,
                    "state": state
                }
            raise HTTPException(status_code=404, detail=f"File '{filename}' not found in plan")

    raise HTTPException(status_code=404, detail="Plan not found")


@app.post("/api/workflows/plan")
async def api_create_plan(request: PlanRequest, background_tasks: BackgroundTasks):
    """Start a new planning workflow."""
    run_id = str(uuid.uuid4())[:8]

    active_runs[run_id] = {
        "id": run_id,
        "workflow": "planning",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "description": request.description,
        "progress": 0,
        "current_step": None,
        "events": [],
        "output_file": None,
        "error": None
    }

    background_tasks.add_task(_run_planning_workflow, run_id, request.description)

    return {"run_id": run_id, "status": "started"}


@app.post("/api/workflows/build")
async def api_start_build(request: BuildRequest, background_tasks: BackgroundTasks):
    """Start a build workflow."""
    run_id = str(uuid.uuid4())[:8]

    active_runs[run_id] = {
        "id": run_id,
        "workflow": "building",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "plan_path": request.plan_path,
        "progress": 0,
        "current_step": None,
        "events": [],
        "output_file": None,
        "error": None
    }

    background_tasks.add_task(_run_building_workflow, run_id, request.plan_path)

    return {"run_id": run_id, "status": "started"}


@app.post("/api/workflows/sync-remote")
async def api_sync_remote(background_tasks: BackgroundTasks):
    """Start a sync-remote workflow to commit changes and create PR."""
    run_id = str(uuid.uuid4())[:8]

    active_runs[run_id] = {
        "id": run_id,
        "workflow": "syncing",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "progress": 0,
        "current_step": None,
        "events": [],
        "output_file": None,
        "error": None
    }

    background_tasks.add_task(_run_syncing_workflow, run_id)

    return {"run_id": run_id, "status": "started"}


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str):
    """Get run status."""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return active_runs[run_id]


@app.get("/api/runs/{run_id}/events")
async def api_stream_events(run_id: str):
    """Stream events from a running workflow via SSE."""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_index = 0
        while True:
            run = active_runs.get(run_id)
            if not run:
                break

            # Send new events
            events = run.get("events", [])
            for event in events[last_index:]:
                yield f"data: {json.dumps(event)}\n\n"
            last_index = len(events)

            # Check if done
            if run["status"] in ["completed", "failed"]:
                yield f"data: {json.dumps({'type': 'done', 'status': run['status']})}\n\n"
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
    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")

    if workflow == "plan":
        estimate = estimator.estimate_planning(len(request_text or "medium request"), complexity)
    elif workflow == "build":
        path = Path(plan_path) if plan_path else ORCHESTRATOR_DIR / "dummy.md"
        estimate = estimator.estimate_building(path)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown workflow: {workflow}")

    return estimate.to_dict()


@app.get("/api/cost/summary")
async def api_cost_summary():
    """Get cost summary for dashboard."""
    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")
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
    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")
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
    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")
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
    estimator = CostEstimator(ORCHESTRATOR_DIR / "cost_history.json")
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


def _extract_plan_info(plan_dir: Path) -> Dict[str, str]:
    """Extract plan info (name, request, complexity) from plan.md headers."""
    info = {}
    plan_file = plan_dir / "plan.md"

    if not plan_file.exists():
        return info

    try:
        content = plan_file.read_text(encoding="utf-8")
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
    except IOError:
        pass

    return info


async def _get_all_plans() -> List[Dict]:
    """Get all plans across all states, sorted by numeric prefix."""
    specs_dir = ORCHESTRATOR_DIR / "specs"
    plans = []

    for state in ["pending", "in-progress", "completed", "failed"]:
        state_dir = specs_dir / state
        if state_dir.exists():
            # Look for plan directories (e.g., 001_feature-name/)
            for plan_dir in state_dir.iterdir():
                if plan_dir.is_dir() and not plan_dir.name.startswith('.'):
                    # Get list of files in the plan directory
                    files = sorted([
                        f.name for f in plan_dir.iterdir()
                        if f.is_file() and not f.name.startswith('.')
                    ])

                    plan_data = {
                        "id": plan_dir.name,
                        "name": plan_dir.name.replace("-", " ").replace("_", " ").title(),
                        "state": state,
                        "file": str(plan_dir),
                        "files": files,
                        "modified": datetime.fromtimestamp(plan_dir.stat().st_mtime).isoformat()
                    }

                    # Extract info from plan.md headers
                    plan_info = _extract_plan_info(plan_dir)
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
    """Get a specific plan by ID."""
    specs_dir = ORCHESTRATOR_DIR / "specs"

    for state in ["pending", "in-progress", "completed", "failed"]:
        # Look for plan directory matching the ID
        plan_dir = specs_dir / state / plan_id
        if plan_dir.exists() and plan_dir.is_dir():
            plan_data = {
                "id": plan_id,
                "name": plan_id.replace("-", " ").replace("_", " ").title(),
                "state": state,
                "file": str(plan_dir),
                "modified": datetime.fromtimestamp(plan_dir.stat().st_mtime).isoformat()
            }

            # Extract info from plan.md headers
            plan_info = _extract_plan_info(plan_dir)
            if plan_info.get("name"):
                plan_data["name"] = plan_info["name"]
            if plan_info.get("request"):
                plan_data["request"] = plan_info["request"]
            if plan_info.get("complexity"):
                plan_data["complexity"] = plan_info["complexity"]

            # Load plan content - try plan.md first (new format), then 00_overview.md (legacy)
            plan_file = plan_dir / "plan.md"
            overview_file = plan_dir / "00_overview.md"

            if plan_file.exists():
                plan_data["content"] = plan_file.read_text(encoding="utf-8")
            elif overview_file.exists():
                plan_data["content"] = overview_file.read_text(encoding="utf-8")
            else:
                # Fallback: concatenate all .md files
                content_parts = []
                for md_file in sorted(plan_dir.glob("*.md")):
                    content_parts.append(f"# {md_file.stem}\n\n{md_file.read_text(encoding='utf-8')}\n\n")
                plan_data["content"] = "".join(content_parts) if content_parts else ""

            # List all plan files
            plan_data["files"] = [f.name for f in plan_dir.iterdir() if f.is_file()]

            return plan_data

    return None


# ============== Background Tasks ==============

def _add_event(run_id: str, event: Dict):
    """Add event to run."""
    if run_id in active_runs:
        event["timestamp"] = datetime.now().isoformat()
        active_runs[run_id]["events"].append(event)


async def _run_planning_workflow(run_id: str, description: str):
    """Execute planning workflow."""
    run = active_runs[run_id]
    run["status"] = "running"
    _add_event(run_id, {"type": "start", "workflow": "planning"})

    try:
        workflow = PlanningWorkflow(project_root=PROJECT_ROOT)

        # Run workflow
        _add_event(run_id, {"type": "step", "step": "analyzing"})
        result = workflow.run(description)

        run["status"] = "completed" if result.success else "failed"
        run["completed_at"] = datetime.now().isoformat()
        run["output_file"] = str(result.output_file) if result.output_file else None
        run["progress"] = 100
        run["total_tokens"] = result.total_tokens

        _add_event(run_id, {
            "type": "complete",
            "success": result.success,
            "output": str(result.output_file) if result.output_file else None
        })

    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)
        _add_event(run_id, {"type": "error", "message": str(e)})


async def _run_building_workflow(run_id: str, plan_path: str):
    """Execute building workflow."""
    run = active_runs[run_id]
    run["status"] = "running"
    _add_event(run_id, {"type": "start", "workflow": "building"})

    try:
        workflow = BuildingWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run(plan_path)

        run["status"] = "completed" if result.success else "failed"
        run["completed_at"] = datetime.now().isoformat()
        run["output_file"] = str(result.output_file) if result.output_file else None
        run["progress"] = 100

        _add_event(run_id, {
            "type": "complete",
            "success": result.success,
            "steps_completed": result.steps_completed
        })

    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)
        _add_event(run_id, {"type": "error", "message": str(e)})


async def _run_syncing_workflow(run_id: str):
    """Execute syncing workflow to commit changes and create PR."""
    run = active_runs[run_id]
    run["status"] = "running"
    _add_event(run_id, {"type": "start", "workflow": "syncing"})

    try:
        workflow = SyncingWorkflow(project_root=PROJECT_ROOT)
        result = workflow.run()

        run["status"] = "completed" if result.success else "failed"
        run["completed_at"] = datetime.now().isoformat()
        run["output_file"] = str(result.output_file) if result.output_file else None
        run["progress"] = 100
        run["data"] = result.data

        _add_event(run_id, {
            "type": "complete",
            "success": result.success,
            "output": str(result.output_file) if result.output_file else None
        })

    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)
        _add_event(run_id, {"type": "error", "message": str(e)})


# ============== App Entry Point ==============

def run_portal(host: str = "127.0.0.1", port: int = 8000):
    """Run the web portal."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Alias for backward compatibility
run_server = run_portal


if __name__ == "__main__":
    run_server()
