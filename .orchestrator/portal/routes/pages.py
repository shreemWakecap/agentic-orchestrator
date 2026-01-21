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
    get_codebase_explorer_service,
)
from portal.services.plan_service import PlanService
from portal.services.knowledge_service import KnowledgeService
from portal.services.codebase_explorer_service import CodebaseExplorerService

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


def _get_codebase_explorer_service(
    explorer_service: CodebaseExplorerService = Depends(get_codebase_explorer_service),
) -> CodebaseExplorerService:
    """Get codebase explorer service with injected dependencies."""
    return explorer_service


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    plan_repo: PlanRepository = Depends(get_plan_repo),
    run_repo: RunRepository = Depends(get_run_repo),
    plan_service: PlanService = Depends(_get_plan_service),
    explorer_service: CodebaseExplorerService = Depends(_get_codebase_explorer_service),
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

    # Get architecture overview for codebase exploration widget
    architecture = await explorer_service.get_architecture_overview()
    architecture_summary = {
        "project_name": architecture.project_name,
        "project_type": architecture.project_type,
        "primary_language": architecture.primary_language,
        "architecture_pattern": architecture.architecture_pattern,
        "modules_count": len(architecture.modules),
        "domains_count": len(architecture.domains),
    }

    # Get recent explorations for dashboard widget (domains and modules)
    recent_explorations = await explorer_service.get_recent_explorations(limit=4)

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
            "architecture_summary": architecture_summary,
            "recent_explorations": recent_explorations,
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


@router.get("/questions", response_class=HTMLResponse)
async def questions_page(
    request: Request,
    explorer_service: CodebaseExplorerService = Depends(_get_codebase_explorer_service),
):
    """Render codebase exploration page.

    Provides an interface for exploring and understanding the codebase
    including architecture overview, domains, modules, and patterns.
    """
    # Get architecture overview
    architecture = await explorer_service.get_architecture_overview()

    # Build architecture summary
    architecture_summary = {
        "project_name": architecture.project_name,
        "project_type": architecture.project_type,
        "primary_language": architecture.primary_language,
        "architecture_pattern": architecture.architecture_pattern,
        "entry_points": architecture.entry_points,
        "conventions": architecture.conventions,
        "technologies": architecture.technologies,
    }

    # Build domain list with details
    domain_list = [
        {
            "name": d.get("name", ""),
            "keywords": d.get("keywords", []),
            "file_count": d.get("file_count", 0),
        }
        for d in architecture.domains
    ]

    # Build module list (patterns)
    pattern_list = [
        {
            "name": m.get("name", ""),
            "path": m.get("path", ""),
            "purpose": m.get("purpose", ""),
            "depends_on": m.get("depends_on", []),
        }
        for m in architecture.modules
    ]

    # Get exploration stats
    exploration_data = await explorer_service.get_exploration_data_for_template()
    stats = exploration_data.get("stats", {})

    return templates.TemplateResponse(
        request,
        "questions.html",
        {
            "architecture_summary": architecture_summary,
            "domain_list": domain_list,
            "pattern_list": pattern_list,
            "stats": stats,
        },
    )


@router.get("/explore/{path:path}", response_class=HTMLResponse)
async def explore_file_page(
    request: Request,
    path: str,
    explorer_service: CodebaseExplorerService = Depends(_get_codebase_explorer_service),
):
    """Render file exploration detail page.

    Shows detailed analysis of a specific file including classes,
    functions, imports, dependencies, and domain/module context.
    """
    # Get file analysis
    analysis = await explorer_service.get_file_analysis(path)

    if not analysis.exists and not analysis.has_knowledge:
        raise HTTPException(status_code=404, detail=f"File '{path}' not found or not analyzed")

    return templates.TemplateResponse(
        request,
        "question_detail.html",
        {
            "file_analysis": {
                "file_path": analysis.file_path,
                "file_name": analysis.file_name,
                "exists": analysis.exists,
                "has_knowledge": analysis.has_knowledge,
                "language": analysis.language,
                "size_bytes": analysis.size_bytes,
                "line_count": analysis.line_count,
                "imports": analysis.imports,
                "exports": analysis.exports,
                "classes": analysis.classes,
                "functions": analysis.functions,
                "dependencies": analysis.dependencies,
                "domain_context": analysis.domain_context,
                "module_context": analysis.module_context,
                "related_files": analysis.related_files,
            },
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render settings page for database configuration and system settings."""
    return templates.TemplateResponse(request, "settings.html", {})
