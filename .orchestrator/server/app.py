"""Web UI backend for SDLC Orchestrator.

Provides a browser-based dashboard for:
- Viewing and managing plans
- Running workflows (plan, build, review, fix)
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
SERVER_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = SERVER_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

sys.path.insert(0, str(ORCHESTRATOR_DIR))

from workflows.planning import PlanningWorkflow
from workflows.building import BuildingWorkflow
from workflows.reviewing import ReviewingWorkflow
from workflows.fixing import FixingWorkflow
from core.cost import CostEstimator, CostReporter, BudgetManager, Budget

# FastAPI app
app = FastAPI(
    title="SDLC Orchestrator",
    description="Web UI for managing software development workflows",
    version="1.0.0"
)

# Setup templates and static files
templates = Jinja2Templates(directory=SERVER_DIR / "templates")
STATIC_DIR = SERVER_DIR / "static"
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


class ReviewRequest(BaseModel):
    """Request to start a review."""
    plan_path: str
    refresh_docs: bool = False


class FixRequest(BaseModel):
    """Request to start fixing issues."""
    review_path: str
    dry_run: bool = False
    min_severity: str = "low"


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
        "failed": 0,
        "reviews": 0
    }

    for state in ["pending", "in-progress", "completed", "failed"]:
        state_dir = specs_dir / state
        if state_dir.exists():
            count = len(list(state_dir.glob("*.md")))
            key = state.replace("-", "_")
            counts[key] = count

    reviews_dir = specs_dir / "reviews"
    if reviews_dir.exists():
        counts["reviews"] = len(list(reviews_dir.glob("*.md")))

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


# ============== API Routes ==============

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


@app.post("/api/workflows/review")
async def api_start_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Start a review workflow."""
    run_id = str(uuid.uuid4())[:8]

    active_runs[run_id] = {
        "id": run_id,
        "workflow": "reviewing",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "plan_path": request.plan_path,
        "progress": 0,
        "events": [],
        "output_file": None,
        "error": None
    }

    background_tasks.add_task(
        _run_reviewing_workflow,
        run_id,
        request.plan_path,
        request.refresh_docs
    )

    return {"run_id": run_id, "status": "started"}


@app.post("/api/workflows/fix")
async def api_start_fix(request: FixRequest, background_tasks: BackgroundTasks):
    """Start a fixing workflow."""
    run_id = str(uuid.uuid4())[:8]

    active_runs[run_id] = {
        "id": run_id,
        "workflow": "fixing",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "review_path": request.review_path,
        "dry_run": request.dry_run,
        "progress": 0,
        "events": [],
        "output_file": None,
        "error": None
    }

    background_tasks.add_task(
        _run_fixing_workflow,
        run_id,
        request.review_path,
        request.dry_run,
        request.min_severity
    )

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


@app.get("/api/reviews")
async def api_list_reviews():
    """List all review reports."""
    reviews = await _get_all_reviews()
    return {"reviews": reviews}


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
    elif workflow == "review":
        path = Path(plan_path) if plan_path else ORCHESTRATOR_DIR / "dummy.md"
        estimate = estimator.estimate_reviewing(path)
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

async def _get_all_plans() -> List[Dict]:
    """Get all plans across all states."""
    specs_dir = ORCHESTRATOR_DIR / "specs"
    plans = []

    for state in ["pending", "in-progress", "completed", "failed"]:
        state_dir = specs_dir / state
        if state_dir.exists():
            for plan_file in state_dir.glob("*.md"):
                if not plan_file.name.startswith("."):
                    plans.append({
                        "id": plan_file.stem,
                        "name": plan_file.stem.replace("-", " ").replace("_", " ").title(),
                        "state": state,
                        "file": str(plan_file),
                        "modified": datetime.fromtimestamp(plan_file.stat().st_mtime).isoformat()
                    })

    return sorted(plans, key=lambda p: p["modified"], reverse=True)


async def _get_recent_plans(limit: int) -> List[Dict]:
    """Get most recent plans."""
    all_plans = await _get_all_plans()
    return all_plans[:limit]


async def _get_plan_by_id(plan_id: str) -> Optional[Dict]:
    """Get a specific plan by ID."""
    specs_dir = ORCHESTRATOR_DIR / "specs"

    for state in ["pending", "in-progress", "completed", "failed"]:
        plan_file = specs_dir / state / f"{plan_id}.md"
        if plan_file.exists():
            return {
                "id": plan_id,
                "name": plan_id.replace("-", " ").replace("_", " ").title(),
                "state": state,
                "file": str(plan_file),
                "content": plan_file.read_text(encoding="utf-8"),
                "modified": datetime.fromtimestamp(plan_file.stat().st_mtime).isoformat()
            }

    return None


async def _get_all_reviews() -> List[Dict]:
    """Get all review reports."""
    reviews_dir = ORCHESTRATOR_DIR / "specs" / "reviews"
    reviews = []

    if reviews_dir.exists():
        for review_file in reviews_dir.glob("*.md"):
            content = review_file.read_text(encoding="utf-8")

            # Try to extract score from content
            score = None
            for line in content.split("\n"):
                if "Score:" in line or "score:" in line:
                    try:
                        score_str = line.split(":")[1].strip().replace("%", "").split()[0]
                        score = float(score_str)
                        break
                    except (ValueError, IndexError):
                        pass

            reviews.append({
                "id": review_file.stem,
                "file": str(review_file),
                "score": score,
                "modified": datetime.fromtimestamp(review_file.stat().st_mtime).isoformat()
            })

    return sorted(reviews, key=lambda r: r["modified"], reverse=True)


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


async def _run_reviewing_workflow(run_id: str, plan_path: str, refresh_docs: bool):
    """Execute reviewing workflow."""
    run = active_runs[run_id]
    run["status"] = "running"
    _add_event(run_id, {"type": "start", "workflow": "reviewing"})

    try:
        workflow = ReviewingWorkflow(project_root=PROJECT_ROOT, refresh_docs=refresh_docs)
        result = workflow.run(plan_path)

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


async def _run_fixing_workflow(run_id: str, review_path: str, dry_run: bool, min_severity: str):
    """Execute fixing workflow."""
    run = active_runs[run_id]
    run["status"] = "running"
    _add_event(run_id, {"type": "start", "workflow": "fixing"})

    try:
        workflow = FixingWorkflow(
            project_root=PROJECT_ROOT,
            dry_run=dry_run,
            min_severity=min_severity
        )
        result = workflow.run(review_path)

        run["status"] = "completed" if result.success else "failed"
        run["completed_at"] = datetime.now().isoformat()
        run["output_file"] = str(result.output_file) if result.output_file else None
        run["progress"] = 100
        run["data"] = result.data

        _add_event(run_id, {
            "type": "complete",
            "success": result.success,
            "fixes_applied": result.data.get("fixes_applied", 0) if result.data else 0
        })

    except Exception as e:
        run["status"] = "failed"
        run["error"] = str(e)
        _add_event(run_id, {"type": "error", "message": str(e)})


# ============== App Entry Point ==============

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
