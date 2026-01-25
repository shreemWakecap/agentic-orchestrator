"""HTML page routes for the portal UI."""
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import PlanRepository, RunRepository, KnowledgeRepository, BuildStateRepository
from portal.dependencies import (
    get_plan_repo,
    get_run_repo,
    get_knowledge_repo,
    get_build_state_repo,
    get_token_usage_service,
)
from portal.services.plan_service import PlanService
from portal.services.knowledge_service import KnowledgeService
from portal.services.token_usage_service import TokenUsageService

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
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
) -> PlanService:
    """Get plan service with injected dependencies."""
    return PlanService(plan_repo, build_state_repo)


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
    # Include planning, running, and pending statuses for real-time visibility
    active_statuses = ['planning', 'running', 'pending']
    active_runs_raw = []
    for status in active_statuses:
        active_runs_raw.extend(run_repo.list_active(status=status))
    # Sort by started_at (most recent first)
    active_runs_raw.sort(
        key=lambda r: r.get("started_at") or "",
        reverse=True
    )
    runs = _transform_runs_for_template(active_runs_raw)

    # Get completed runs (completed + failed status) for "Recent Completed" section
    completed_runs_raw = run_repo.list_active(status="completed")
    failed_runs_raw = run_repo.list_active(status="failed")
    # Combine and sort by completed_at or started_at (most recent first), limit to 5
    all_finished = completed_runs_raw + failed_runs_raw
    all_finished.sort(
        key=lambda r: r.get("completed_at") or r.get("started_at") or "",
        reverse=True
    )
    completed_runs = _transform_runs_for_template(all_finished[:5])

    # Get planning tasks (background tasks of type 'plan' that are pending/running)
    from portal.services.task_manager import get_task_manager
    task_manager = get_task_manager()
    all_tasks = task_manager.list_all_tasks() if task_manager else []
    planning_tasks = [
        {
            "id": t.get("task_id", t.get("id", "")),
            "name": t.get("name", t.get("description", "Planning workflow...")),
            "description": t.get("description", "Analyzing requirements and generating plan..."),
        }
        for t in all_tasks
        if t.get("task_type") == "plan" and t.get("status") in ["pending", "running"]
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "counts": counts,
            "recent_plans": recent_plans,
            "active_runs": runs,
            "completed_runs": completed_runs,
            "planning_tasks": planning_tasks,
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
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repo),
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

    # Get staleness status
    staleness = None
    try:
        from core.staleness_checker import get_staleness_summary
        project_root = Path(__file__).parent.parent.parent.parent
        staleness = get_staleness_summary(project_root)
    except Exception:
        pass

    # Get coding rules for display
    coding_rules = knowledge_repo.get_coding_rules()

    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "knowledge": knowledge,
            "scan_meta": scan_meta,
            "expert_count": expert_count,
            "staleness": staleness,
            "coding_rules": coding_rules,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render settings page for database configuration and system settings."""
    return templates.TemplateResponse(request, "settings.html", {})


@router.get("/token-analytics", response_class=HTMLResponse)
async def token_analytics_page(
    request: Request,
    token_usage_service: TokenUsageService = Depends(get_token_usage_service),
):
    """Render token analytics dashboard page."""
    # Get analytics data for default period (last 30 days)
    analytics = token_usage_service.get_analytics()

    # Get comparison metrics for estimated vs actual
    comparison = token_usage_service.get_comparison_metrics()

    # Get error rates
    error_rates = token_usage_service.calculate_error_rates()

    # Get usage trends
    trends = token_usage_service.get_usage_trends()

    # Get recent usage records for display
    from db.repositories.token_usage import get_token_usage_repository
    token_repo = get_token_usage_repository()
    recent_records = token_repo.get_usage_records(limit=20)

    return templates.TemplateResponse(
        request,
        "token_analytics.html",
        {
            "analytics": analytics,
            "comparison": comparison,
            "error_rates": error_rates,
            "trends": trends,
            "recent_records": recent_records,
        },
    )


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Render projects management page (multi-project mode only)."""
    from config import get_config

    config = get_config()

    # Check if multi-project mode is enabled
    if not config.is_multi_project_mode:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "is_multi_project": False,
                "projects": [],
                "active_project": None,
                "error": "Multi-project mode is not enabled. Set SDLC_ORCHESTRATOR_HOME and run 'orch init'.",
            },
        )

    # Get projects from service
    try:
        from core.project_service import get_project_service

        service = get_project_service()
        projects = service.list_projects(include_archived=True)
        active = service.get_active()

        # Convert to dict for template (handle both dict and object formats)
        projects_data = []
        for p in projects:
            if isinstance(p, dict):
                status = p.get('status', 'unknown')
                source_type = p.get('source_type', 'local')
                projects_data.append({
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "slug": p.get('slug'),
                    "path": p.get('path'),
                    "status": status.value if hasattr(status, 'value') else str(status),
                    "source_type": source_type.value if hasattr(source_type, 'value') else str(source_type),
                    "git_url": p.get('git_url'),
                    "git_branch": p.get('git_branch'),
                    "description": p.get('description'),
                    "created_at": p.get('added_at'),
                    "last_accessed_at": p.get('last_accessed'),
                    "indexed_at": p.get('indexed_at'),
                })
            else:
                projects_data.append({
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "path": p.path,
                    "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
                    "source_type": p.source_type.value if hasattr(p.source_type, 'value') else str(p.source_type),
                    "git_url": p.git_url,
                    "git_branch": p.git_branch,
                    "description": p.description,
                    "created_at": p.added_at,
                    "last_accessed_at": p.last_accessed,
                    "indexed_at": p.indexed_at,
                })

        # Handle active project (dict or object)
        active_slug = None
        if active:
            active_slug = active.get('slug') if isinstance(active, dict) else active.slug

        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "is_multi_project": True,
                "projects": projects_data,
                "active_project": active_slug,
                "error": None,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "projects.html",
            {
                "is_multi_project": True,
                "projects": [],
                "active_project": None,
                "error": str(e),
            },
        )
