"""Token usage analytics API routes."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query

from portal.dependencies import get_token_usage_service
from portal.services.token_usage_service import TokenUsageService
from portal.schemas.responses import (
    TokenUsageSummary,
    TokenUsageRecord,
    TokenComparison,
    ErrorRateMetrics,
    TokenTrendData,
    TokenAnalyticsResponse,
)

router = APIRouter(prefix="/api/token-analytics", tags=["token-analytics"])


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/summary", response_model=TokenUsageSummary)
async def get_summary(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    workflow: Optional[str] = Query(None, description="Filter by workflow type"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> TokenUsageSummary:
    """Get overall token usage summary statistics.

    Returns aggregated metrics including total tokens, costs, and breakdowns
    by agent type and model for the specified time period.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    # Default to last 30 days if no dates provided
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - timedelta(days=30)

    analytics = service.get_analytics(
        start_date=start,
        end_date=end,
        workflow=workflow
    )

    summary = analytics.get("summary", {})
    by_workflow = analytics.get("by_workflow", {})

    return TokenUsageSummary(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        total_input_tokens=summary.get("total_input_tokens", 0),
        total_output_tokens=summary.get("total_output_tokens", 0),
        total_tokens=summary.get("total_tokens", 0),
        total_cost_usd=summary.get("total_estimated_cost", 0),
        run_count=summary.get("total_executions", 0),
        plan_count=by_workflow.get("planning", {}).get("count", 0),
        average_tokens_per_run=summary.get("avg_tokens_per_execution", 0),
        average_cost_per_run=summary.get("avg_cost_per_execution", 0),
        by_agent_type=by_workflow,
        by_model={},
    )


@router.get("/usage", response_model=list[TokenUsageRecord])
async def get_usage(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    workflow: Optional[str] = Query(None, description="Filter by workflow type"),
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> list[TokenUsageRecord]:
    """Get token usage records with date range filtering.

    Returns individual usage records for runs and estimations within
    the specified date range.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    analytics = service.get_analytics(
        start_date=start,
        end_date=end,
        workflow=workflow,
        plan_id=plan_id
    )

    # Get the raw records from the repository via service
    repo = service._get_token_usage_repo()
    records = repo.get_usage_records(
        start_date=start.isoformat() if start else None,
        end_date=end.isoformat() if end else None,
        workflow=workflow,
        plan_id=plan_id
    )

    # Convert to response models with limit
    result = []
    for r in records[:limit]:
        result.append(TokenUsageRecord(
            id=r.get("id", ""),
            plan_id=r.get("plan_id"),
            run_id=r.get("run_id"),
            event_type=r.get("workflow", "execution"),
            timestamp=r.get("timestamp", ""),
            input_tokens=r.get("input_tokens", 0),
            output_tokens=r.get("output_tokens", 0),
            total_tokens=r.get("total_tokens", 0),
            cost_usd=r.get("estimated_cost", 0),
            model=r.get("metadata", {}).get("model") if r.get("metadata") else None,
            agent_type=r.get("workflow"),
            metadata=r.get("metadata") or {},
        ))

    return result


@router.get("/comparison", response_model=list[TokenComparison])
async def get_comparison(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    plan_id: Optional[str] = Query(None, description="Filter by specific plan ID"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> list[TokenComparison]:
    """Get estimated vs actual token usage comparison.

    Compares estimated token usage from planning phase against actual
    usage during execution for completed plans.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    comparison_data = service.get_comparison_metrics(
        plan_id=plan_id,
        start_date=start,
        end_date=end
    )

    comparisons = comparison_data.get("comparisons", [])

    result = []
    for c in comparisons:
        est_tokens = c.get("estimated_tokens", 0)
        actual_tokens = c.get("actual_tokens", 0)
        variance = actual_tokens - est_tokens
        variance_pct = c.get("token_error_percent", 0)

        # Determine accuracy rating
        if abs(variance_pct) <= 10:
            accuracy = "accurate"
        elif variance_pct > 10:
            accuracy = "under_estimated"
        else:
            accuracy = "over_estimated"

        result.append(TokenComparison(
            plan_id=c.get("plan_id", ""),
            plan_name=None,
            estimated_tokens=est_tokens,
            estimated_cost_usd=c.get("estimated_cost", 0),
            actual_tokens=actual_tokens,
            actual_cost_usd=c.get("actual_cost", 0),
            token_variance=variance,
            cost_variance=c.get("cost_difference", 0),
            variance_percentage=variance_pct,
            accuracy_rating=accuracy,
            completed_at=c.get("execution_timestamp"),
        ))

    return result


@router.get("/error-rates", response_model=ErrorRateMetrics)
async def get_error_rates(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> ErrorRateMetrics:
    """Get error rate calculations for token usage.

    Returns metrics about estimation accuracy including MAE, MAPE, and RMSE
    broken down by workflow type and confidence level.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    # Default period if not specified
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - timedelta(days=30)

    error_data = service.calculate_error_rates(
        start_date=start,
        end_date=end
    )

    overall = error_data.get("overall", {})
    by_workflow = error_data.get("by_workflow", {})

    # Calculate total runs and errors based on comparison data
    comparison_data = service.get_comparison_metrics(start_date=start, end_date=end)
    total_comparisons = comparison_data.get("summary", {}).get("total_comparisons", 0)

    # Count errors by workflow (high MAPE = problematic estimation)
    errors_by_agent = {}
    for wf, data in by_workflow.items():
        if data.get("mape", 0) > 25:  # More than 25% error considered significant
            errors_by_agent[wf] = data.get("samples", 0)

    return ErrorRateMetrics(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        total_runs=total_comparisons,
        successful_runs=total_comparisons,  # All matched comparisons are "successful"
        failed_runs=0,
        error_rate=0,
        error_rate_percentage=0,
        tokens_wasted_on_failures=0,
        cost_wasted_on_failures=0,
        errors_by_type={
            "mae": overall.get("mae", 0),
            "mape": overall.get("mape", 0),
            "rmse": overall.get("rmse", 0),
        },
        errors_by_agent=errors_by_agent,
    )


@router.get("/trends", response_model=list[TokenTrendData])
async def get_trends(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    granularity: str = Query("day", description="Time granularity: hour, day, week, month"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> list[TokenTrendData]:
    """Get time series trend data for token usage.

    Returns token usage aggregated over time periods for visualization
    in charts and trend analysis.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    trend_data = service.get_usage_trends(
        start_date=start,
        end_date=end,
        granularity=granularity
    )

    data_points = trend_data.get("data_points", [])

    result = []
    for dp in data_points:
        period = dp.get("period", "")
        result.append(TokenTrendData(
            timestamp=period,
            period_label=_format_period_label(period, granularity),
            total_tokens=dp.get("tokens", 0),
            total_cost_usd=dp.get("cost", 0),
            run_count=dp.get("executions", 0),
            error_count=0,
            average_tokens_per_run=dp.get("avg_tokens", 0),
        ))

    return result


@router.get("/dashboard", response_model=TokenAnalyticsResponse)
async def get_dashboard(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    service: TokenUsageService = Depends(get_token_usage_service),
) -> TokenAnalyticsResponse:
    """Get comprehensive token analytics for dashboard display.

    Combines summary, trends, comparisons, and error metrics into
    a single response for dashboard rendering.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    # Default to last 30 days if no dates provided
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - timedelta(days=30)

    # Gather all analytics data
    summary_response = await get_summary(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        workflow=None,
        service=service
    )

    trends_response = await get_trends(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        granularity="day",
        service=service
    )

    comparisons_response = await get_comparison(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        plan_id=None,
        service=service
    )

    error_response = await get_error_rates(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        service=service
    )

    # Get recent records
    recent_records = await get_usage(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        workflow=None,
        plan_id=None,
        limit=10,
        service=service
    )

    return TokenAnalyticsResponse(
        summary=summary_response,
        trends=trends_response,
        comparisons=comparisons_response,
        error_metrics=error_response,
        recent_records=recent_records,
        date_range={
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    )


def _format_period_label(period: str, granularity: str) -> str:
    """Format period string into human-readable label."""
    try:
        if granularity == "hour":
            # Format: "2025-01-15 14:00" -> "Jan 15 2pm"
            dt = datetime.fromisoformat(period.replace(" ", "T"))
            return dt.strftime("%b %d %I%p").replace(" 0", " ")
        elif granularity == "day":
            # Format: "2025-01-15" -> "Jan 15"
            dt = datetime.fromisoformat(period)
            return dt.strftime("%b %d")
        elif granularity == "week":
            # Format: "2025-01-13" (week start) -> "Week of Jan 13"
            dt = datetime.fromisoformat(period)
            return f"Week of {dt.strftime('%b %d')}"
        elif granularity == "month":
            # Format: "2025-01" -> "Jan 2025"
            dt = datetime.strptime(period, "%Y-%m")
            return dt.strftime("%b %Y")
        else:
            return period
    except (ValueError, TypeError):
        return period
