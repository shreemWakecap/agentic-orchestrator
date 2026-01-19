"""Cost-related API routes."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from portal.dependencies import get_project_root, get_orchestrator_dir
from portal.schemas.requests import BudgetUpdateRequest
from core.cost import CostEstimator, CostReporter, BudgetManager, Budget

router = APIRouter(prefix="/api/cost", tags=["cost"])


def _get_cost_services(
    project_root: Path = Depends(get_project_root),
    orchestrator_dir: Path = Depends(get_orchestrator_dir),
) -> tuple:
    """Get cost-related services."""
    estimator = CostEstimator(project_root)
    reporter = CostReporter(estimator)
    budget_manager = BudgetManager(orchestrator_dir / "config" / "budget.json", estimator)
    return estimator, reporter, budget_manager


@router.get("/estimate/{workflow}")
async def estimate_cost(
    workflow: str,
    request_text: str = "",
    plan_path: str = "",
    complexity: str = "medium",
    project_root: Path = Depends(get_project_root),
):
    """Get cost estimate for a workflow."""
    estimator = CostEstimator(project_root)

    if workflow == "plan":
        estimate = estimator.estimate_planning(len(request_text or "medium request"), complexity)
    elif workflow == "build":
        path = Path(plan_path) if plan_path else project_root / "dummy.md"
        estimate = estimator.estimate_building(path)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown workflow: {workflow}")

    return estimate.to_dict()


@router.get("/summary")
async def cost_summary(
    project_root: Path = Depends(get_project_root),
    orchestrator_dir: Path = Depends(get_orchestrator_dir),
):
    """Get cost summary for dashboard."""
    estimator = CostEstimator(project_root)
    reporter = CostReporter(estimator)
    budget_manager = BudgetManager(orchestrator_dir / "config" / "budget.json", estimator)

    return {
        "daily": reporter.daily_report(),
        "weekly": reporter.weekly_report(),
        "monthly": reporter.monthly_report(),
        "budget": budget_manager.get_remaining_budget(),
    }


@router.get("/report/{period}")
async def cost_report(
    period: str,
    project_root: Path = Depends(get_project_root),
):
    """Get cost report for a specific period."""
    estimator = CostEstimator(project_root)
    reporter = CostReporter(estimator)

    if period == "daily":
        return reporter.daily_report()
    elif period == "weekly":
        return reporter.weekly_report()
    elif period == "monthly":
        return reporter.monthly_report()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown period: {period}")


@router.get("/budget")
async def get_budget(
    project_root: Path = Depends(get_project_root),
    orchestrator_dir: Path = Depends(get_orchestrator_dir),
):
    """Get current budget status."""
    estimator = CostEstimator(project_root)
    budget_manager = BudgetManager(orchestrator_dir / "config" / "budget.json", estimator)
    return budget_manager.get_remaining_budget()


@router.post("/budget")
async def set_budget(
    request: BudgetUpdateRequest,
    project_root: Path = Depends(get_project_root),
    orchestrator_dir: Path = Depends(get_orchestrator_dir),
):
    """Update budget settings."""
    estimator = CostEstimator(project_root)
    budget_manager = BudgetManager(orchestrator_dir / "config" / "budget.json", estimator)

    budget = Budget(
        daily_limit=request.daily_limit,
        weekly_limit=request.weekly_limit,
        monthly_limit=request.monthly_limit,
        per_workflow_limit=request.per_workflow_limit,
    )
    budget_manager.save_budget(budget)

    return {"status": "updated", "budget": budget_manager.get_remaining_budget()}
