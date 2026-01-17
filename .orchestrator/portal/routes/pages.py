"""HTML page routes for the portal UI."""
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import PlanRepository, RunRepository, KnowledgeRepository
from portal.dependencies import get_plan_repo, get_run_repo, get_knowledge_repo
from portal.services.plan_service import PlanService
from portal.services.knowledge_service import KnowledgeService

# Setup templates
PORTAL_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=PORTAL_DIR / "templates")

router = APIRouter(tags=["pages"])


def _transform_run_for_template(run: Dict) -> Dict:
    """Transform run data from database format to template format.

    The database uses 'run_id' but templates expect 'id'.
    """
    return {
        "id": run.get("run_id", ""),
        "workflow": run.get("workflow", ""),
        "status": run.get("status", "pending"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "progress": run.get("progress", 0),
        "error": run.get("error"),
        "plan_id": run.get("plan_id"),
        "description": run.get("description"),
    }


def _transform_runs_for_template(runs: List[Dict]) -> List[Dict]:
    """Transform list of runs for template use."""
    return [_transform_run_for_template(r) for r in runs]


def _get_plan_service(
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> PlanService:
    """Get plan service with injected dependencies."""
    return PlanService(plan_repo)


def _get_knowledge_service(
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repo),
) -> KnowledgeService:
    """Get knowledge service with injected dependencies."""
    return KnowledgeService(knowledge_repo)


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    run_repo: RunRepository = Depends(get_run_repo),
    plan_service: PlanService = Depends(_get_plan_service),
):
    """Render main dashboard."""
    # Count plans by state from database
    counts = {
        "pending": len(plan_repo.list_by_status("pending")),
        "in_progress": len(plan_repo.list_by_status("building")),
        "completed": len(plan_repo.list_by_status("completed")),
        "failed": len(plan_repo.list_by_status("failed")),
    }

    # Get recent plans
    all_plans = await plan_service.get_all_plans()
    recent_plans = all_plans[:5]

    # Get active runs from database and transform for template
    runs = _transform_runs_for_template(run_repo.list_active())

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "counts": counts,
            "recent_plans": recent_plans,
            "active_runs": runs,
        },
    )


@router.get("/plans", response_class=HTMLResponse)
async def plans_page(
    request: Request,
    plan_service: PlanService = Depends(_get_plan_service),
):
    """Render plans list page."""
    plans = await plan_service.get_all_plans()
    return templates.TemplateResponse(request, "plans.html", {"plans": plans})


@router.get("/plans/{plan_id}", response_class=HTMLResponse)
async def plan_detail(
    request: Request,
    plan_id: str,
    plan_service: PlanService = Depends(_get_plan_service),
):
    """Render plan detail page."""
    plan = await plan_service.get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return templates.TemplateResponse(request, "plan_detail.html", {"plan": plan})


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(
    request: Request,
    run_repo: RunRepository = Depends(get_run_repo),
):
    """Render runs history page."""
    runs = _transform_runs_for_template(run_repo.list_active())
    return templates.TemplateResponse(request, "runs.html", {"runs": runs})


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(
    request: Request,
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
):
    """Render run detail page."""
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return templates.TemplateResponse(
        request, "run_detail.html", {"run": _transform_run_for_template(run)}
    )


@router.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(
    request: Request,
    knowledge_service: KnowledgeService = Depends(_get_knowledge_service),
):
    """Render knowledge management page."""
    # Get knowledge data transformed for template
    knowledge = await knowledge_service.get_knowledge_for_template()

    # Get scan metadata
    scan_meta = await knowledge_service.get_scan_history()

    # Get expert count from expert index
    expert_count = 0
    expert_index = await knowledge_service.get_expert_index()
    if expert_index:
        experts = expert_index.get("experts", [])
        expert_count = len(experts)

    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "knowledge": knowledge,
            "scan_meta": scan_meta,
            "expert_count": expert_count,
        },
    )
