"""Token usage tracking and analytics service."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from blinker import signal

from db import get_cost_repository, CostRepository, get_token_usage_repository
from db.repositories.token_usage import TokenUsageRepository
from core.cost import CostEstimator, TokenEstimate, MODEL_PRICING, DEFAULT_MODEL


# Signals for token usage events
token_usage_recorded = signal('token-usage-recorded')
estimation_recorded = signal('estimation-recorded')


@dataclass
class TokenUsageRecord:
    """Represents a token usage record."""
    id: Optional[str]
    plan_id: str
    run_id: str
    workflow: str  # 'planning', 'building', 'execution'
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    actual_cost: Optional[float]
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "workflow": self.workflow,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class EstimationRecord:
    """Represents an estimation record for comparison."""
    id: Optional[str]
    plan_id: str
    workflow: str
    estimated_tokens: int
    estimated_cost: float
    confidence: str  # 'low', 'medium', 'high'
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "workflow": self.workflow,
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost": self.estimated_cost,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class TokenUsageService:
    """Service for tracking and analyzing token usage.

    Provides methods for:
    - Recording actual token usage from executions
    - Recording estimations for future comparison
    - Generating analytics and usage statistics
    - Comparing estimated vs actual usage
    - Calculating error rates
    - Analyzing usage trends over time
    """

    def __init__(
        self,
        token_usage_repo: Optional[TokenUsageRepository] = None,
        cost_repo: Optional[CostRepository] = None
    ):
        self._token_usage_repo = token_usage_repo
        self._cost_repo = cost_repo
        self._cost_estimator = None

    def _get_token_usage_repo(self) -> TokenUsageRepository:
        """Lazy-load token usage repository."""
        if self._token_usage_repo is None:
            self._token_usage_repo = get_token_usage_repository()
        return self._token_usage_repo

    def _get_cost_repo(self) -> CostRepository:
        """Lazy-load cost repository."""
        if self._cost_repo is None:
            self._cost_repo = get_cost_repository()
        return self._cost_repo

    def _get_cost_estimator(self) -> CostEstimator:
        """Lazy-load cost estimator."""
        if self._cost_estimator is None:
            self._cost_estimator = CostEstimator()
        return self._cost_estimator

    def record_execution(
        self,
        plan_id: str,
        run_id: str,
        workflow: str,
        input_tokens: int,
        output_tokens: int,
        actual_cost: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TokenUsageRecord:
        """Record actual token usage from a workflow execution.

        Args:
            plan_id: The plan identifier
            run_id: Unique run identifier
            workflow: Workflow type ('planning', 'building', 'execution')
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            actual_cost: Actual cost if available from API
            metadata: Additional metadata to store

        Returns:
            The created TokenUsageRecord
        """
        total_tokens = input_tokens + output_tokens

        # Calculate estimated cost from tokens
        estimated_cost = self._calculate_cost(input_tokens, output_tokens)

        timestamp = datetime.utcnow().isoformat() + "Z"

        # Store in repository
        repo = self._get_token_usage_repo()
        record_id = repo.record_usage(
            plan_id=plan_id,
            run_id=run_id,
            workflow=workflow,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            timestamp=timestamp,
            metadata=metadata
        )

        record = TokenUsageRecord(
            id=record_id,
            plan_id=plan_id,
            run_id=run_id,
            workflow=workflow,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            timestamp=timestamp,
            metadata=metadata
        )

        # Emit signal for listeners
        token_usage_recorded.send(self, record=record)

        return record

    def record_estimation(
        self,
        plan_id: str,
        workflow: str,
        estimated_tokens: int,
        estimated_cost: float,
        confidence: str = "medium",
        metadata: Optional[Dict[str, Any]] = None
    ) -> EstimationRecord:
        """Record a cost estimation for later comparison.

        Args:
            plan_id: The plan identifier
            workflow: Workflow type being estimated
            estimated_tokens: Estimated total tokens
            estimated_cost: Estimated cost in USD
            confidence: Confidence level ('low', 'medium', 'high')
            metadata: Additional metadata to store

        Returns:
            The created EstimationRecord
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Store in repository
        repo = self._get_token_usage_repo()
        record_id = repo.record_estimation(
            plan_id=plan_id,
            workflow=workflow,
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
            confidence=confidence,
            timestamp=timestamp,
            metadata=metadata
        )

        record = EstimationRecord(
            id=record_id,
            plan_id=plan_id,
            workflow=workflow,
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
            confidence=confidence,
            timestamp=timestamp,
            metadata=metadata
        )

        # Emit signal for listeners
        estimation_recorded.send(self, record=record)

        return record

    def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        workflow: Optional[str] = None,
        plan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive token usage analytics.

        Args:
            start_date: Filter from this date (inclusive)
            end_date: Filter to this date (inclusive)
            workflow: Filter by workflow type
            plan_id: Filter by specific plan

        Returns:
            Analytics dictionary with usage statistics
        """
        repo = self._get_token_usage_repo()
        records = repo.get_usage_records(
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            workflow=workflow,
            plan_id=plan_id
        )

        if not records:
            return self._empty_analytics()

        # Calculate statistics
        total_tokens = sum(r.get("total_tokens", 0) for r in records)
        total_input = sum(r.get("input_tokens", 0) for r in records)
        total_output = sum(r.get("output_tokens", 0) for r in records)
        total_estimated_cost = sum(r.get("estimated_cost", 0) for r in records)
        total_actual_cost = sum(r.get("actual_cost", 0) or 0 for r in records)

        # Group by workflow
        by_workflow = {}
        for r in records:
            wf = r.get("workflow", "unknown")
            if wf not in by_workflow:
                by_workflow[wf] = {
                    "count": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "estimated_cost": 0,
                    "actual_cost": 0
                }
            by_workflow[wf]["count"] += 1
            by_workflow[wf]["total_tokens"] += r.get("total_tokens", 0)
            by_workflow[wf]["input_tokens"] += r.get("input_tokens", 0)
            by_workflow[wf]["output_tokens"] += r.get("output_tokens", 0)
            by_workflow[wf]["estimated_cost"] += r.get("estimated_cost", 0)
            by_workflow[wf]["actual_cost"] += r.get("actual_cost", 0) or 0

        # Group by day for trend data
        daily_usage = self._group_by_day(records)

        return {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "summary": {
                "total_executions": len(records),
                "total_tokens": total_tokens,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_estimated_cost": round(total_estimated_cost, 4),
                "total_actual_cost": round(total_actual_cost, 4),
                "avg_tokens_per_execution": round(total_tokens / len(records), 0) if records else 0,
                "avg_cost_per_execution": round(total_estimated_cost / len(records), 4) if records else 0,
            },
            "by_workflow": by_workflow,
            "daily_usage": daily_usage,
        }

    def get_comparison_metrics(
        self,
        plan_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comparison metrics between estimated and actual usage.

        Args:
            plan_id: Filter by specific plan
            start_date: Filter from this date
            end_date: Filter to this date

        Returns:
            Comparison metrics showing estimated vs actual values
        """
        repo = self._get_token_usage_repo()

        # Get estimations
        estimations = repo.get_estimations(
            plan_id=plan_id,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None
        )

        # Get actual usage
        actuals = repo.get_usage_records(
            plan_id=plan_id,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None
        )

        # Match estimations to actuals by plan_id and workflow
        comparisons = []
        matched_actuals = set()

        for est in estimations:
            est_plan = est.get("plan_id")
            est_workflow = est.get("workflow")

            # Find matching actual
            matching_actual = None
            for actual in actuals:
                if (actual.get("plan_id") == est_plan and
                    actual.get("workflow") == est_workflow and
                    actual.get("run_id") not in matched_actuals):
                    matching_actual = actual
                    matched_actuals.add(actual.get("run_id"))
                    break

            if matching_actual:
                est_tokens = est.get("estimated_tokens", 0)
                actual_tokens = matching_actual.get("total_tokens", 0)
                est_cost = est.get("estimated_cost", 0)
                actual_cost = matching_actual.get("estimated_cost", 0)

                token_diff = actual_tokens - est_tokens
                cost_diff = actual_cost - est_cost
                token_error_pct = (token_diff / est_tokens * 100) if est_tokens > 0 else 0
                cost_error_pct = (cost_diff / est_cost * 100) if est_cost > 0 else 0

                comparisons.append({
                    "plan_id": est_plan,
                    "workflow": est_workflow,
                    "estimated_tokens": est_tokens,
                    "actual_tokens": actual_tokens,
                    "token_difference": token_diff,
                    "token_error_percent": round(token_error_pct, 2),
                    "estimated_cost": round(est_cost, 4),
                    "actual_cost": round(actual_cost, 4),
                    "cost_difference": round(cost_diff, 4),
                    "cost_error_percent": round(cost_error_pct, 2),
                    "confidence": est.get("confidence", "medium"),
                    "estimation_timestamp": est.get("timestamp"),
                    "execution_timestamp": matching_actual.get("timestamp"),
                })

        # Calculate aggregate comparison metrics
        if comparisons:
            avg_token_error = sum(c["token_error_percent"] for c in comparisons) / len(comparisons)
            avg_cost_error = sum(c["cost_error_percent"] for c in comparisons) / len(comparisons)
            total_estimated = sum(c["estimated_tokens"] for c in comparisons)
            total_actual = sum(c["actual_tokens"] for c in comparisons)
        else:
            avg_token_error = 0
            avg_cost_error = 0
            total_estimated = 0
            total_actual = 0

        return {
            "summary": {
                "total_comparisons": len(comparisons),
                "avg_token_error_percent": round(avg_token_error, 2),
                "avg_cost_error_percent": round(avg_cost_error, 2),
                "total_estimated_tokens": total_estimated,
                "total_actual_tokens": total_actual,
                "accuracy_rating": self._get_accuracy_rating(abs(avg_token_error)),
            },
            "comparisons": comparisons,
            "unmatched_estimations": len(estimations) - len(comparisons),
            "unmatched_actuals": len(actuals) - len(matched_actuals),
        }

    def calculate_error_rates(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Calculate error rates for estimations.

        Args:
            start_date: Filter from this date
            end_date: Filter to this date

        Returns:
            Error rate statistics by workflow and confidence level
        """
        comparison = self.get_comparison_metrics(
            start_date=start_date,
            end_date=end_date
        )

        comparisons = comparison.get("comparisons", [])

        if not comparisons:
            return {
                "overall": {"mae": 0, "mape": 0, "rmse": 0},
                "by_workflow": {},
                "by_confidence": {},
                "total_samples": 0
            }

        # Overall error metrics
        token_errors = [c["token_difference"] for c in comparisons]
        token_pct_errors = [abs(c["token_error_percent"]) for c in comparisons]

        mae = sum(abs(e) for e in token_errors) / len(token_errors)
        mape = sum(token_pct_errors) / len(token_pct_errors)
        rmse = (sum(e**2 for e in token_errors) / len(token_errors)) ** 0.5

        # Group by workflow
        by_workflow = {}
        for c in comparisons:
            wf = c["workflow"]
            if wf not in by_workflow:
                by_workflow[wf] = []
            by_workflow[wf].append(c)

        workflow_errors = {}
        for wf, items in by_workflow.items():
            wf_errors = [i["token_difference"] for i in items]
            wf_pct = [abs(i["token_error_percent"]) for i in items]
            workflow_errors[wf] = {
                "samples": len(items),
                "mae": round(sum(abs(e) for e in wf_errors) / len(wf_errors), 0),
                "mape": round(sum(wf_pct) / len(wf_pct), 2),
            }

        # Group by confidence level
        by_confidence = {}
        for c in comparisons:
            conf = c.get("confidence", "medium")
            if conf not in by_confidence:
                by_confidence[conf] = []
            by_confidence[conf].append(c)

        confidence_errors = {}
        for conf, items in by_confidence.items():
            conf_pct = [abs(i["token_error_percent"]) for i in items]
            confidence_errors[conf] = {
                "samples": len(items),
                "mape": round(sum(conf_pct) / len(conf_pct), 2),
            }

        return {
            "overall": {
                "mae": round(mae, 0),
                "mape": round(mape, 2),
                "rmse": round(rmse, 0),
            },
            "by_workflow": workflow_errors,
            "by_confidence": confidence_errors,
            "total_samples": len(comparisons),
        }

    def get_usage_trends(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "day"
    ) -> Dict[str, Any]:
        """Get token usage trends over time.

        Args:
            start_date: Start of trend period
            end_date: End of trend period
            granularity: 'hour', 'day', 'week', 'month'

        Returns:
            Trend data with usage over time periods
        """
        # Default to last 30 days if no dates provided
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        repo = self._get_token_usage_repo()
        records = repo.get_usage_records(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        if not records:
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "granularity": granularity,
                },
                "data_points": [],
                "summary": {
                    "total_tokens": 0,
                    "total_cost": 0,
                    "total_executions": 0,
                    "trend_direction": "stable",
                    "change_percent": 0,
                }
            }

        # Group records by time period
        grouped = self._group_by_period(records, granularity)

        # Sort by period
        sorted_periods = sorted(grouped.keys())
        data_points = []

        for period in sorted_periods:
            items = grouped[period]
            data_points.append({
                "period": period,
                "tokens": sum(r.get("total_tokens", 0) for r in items),
                "cost": round(sum(r.get("estimated_cost", 0) for r in items), 4),
                "executions": len(items),
                "avg_tokens": round(sum(r.get("total_tokens", 0) for r in items) / len(items), 0),
            })

        # Calculate trend direction
        trend_direction, change_percent = self._calculate_trend(data_points)

        total_tokens = sum(r.get("total_tokens", 0) for r in records)
        total_cost = sum(r.get("estimated_cost", 0) for r in records)

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "granularity": granularity,
            },
            "data_points": data_points,
            "summary": {
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "total_executions": len(records),
                "trend_direction": trend_direction,
                "change_percent": round(change_percent, 2),
            }
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost from input and output tokens."""
        pricing = MODEL_PRICING[DEFAULT_MODEL]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 4)

    def _empty_analytics(self) -> Dict[str, Any]:
        """Return empty analytics structure."""
        return {
            "period": {"start": None, "end": None},
            "summary": {
                "total_executions": 0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_estimated_cost": 0,
                "total_actual_cost": 0,
                "avg_tokens_per_execution": 0,
                "avg_cost_per_execution": 0,
            },
            "by_workflow": {},
            "daily_usage": [],
        }

    def _group_by_day(self, records: List[Dict]) -> List[Dict]:
        """Group records by day."""
        daily = {}
        for r in records:
            ts = r.get("timestamp", "")
            if ts:
                day = ts[:10]  # YYYY-MM-DD
                if day not in daily:
                    daily[day] = {"date": day, "tokens": 0, "cost": 0, "executions": 0}
                daily[day]["tokens"] += r.get("total_tokens", 0)
                daily[day]["cost"] += r.get("estimated_cost", 0)
                daily[day]["executions"] += 1

        # Sort by date and round costs
        result = sorted(daily.values(), key=lambda x: x["date"])
        for item in result:
            item["cost"] = round(item["cost"], 4)
        return result

    def _group_by_period(self, records: List[Dict], granularity: str) -> Dict[str, List[Dict]]:
        """Group records by time period based on granularity."""
        grouped = {}
        for r in records:
            ts = r.get("timestamp", "")
            if not ts:
                continue

            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue

            if granularity == "hour":
                period = dt.strftime("%Y-%m-%d %H:00")
            elif granularity == "day":
                period = dt.strftime("%Y-%m-%d")
            elif granularity == "week":
                # Start of week (Monday)
                week_start = dt - timedelta(days=dt.weekday())
                period = week_start.strftime("%Y-%m-%d")
            elif granularity == "month":
                period = dt.strftime("%Y-%m")
            else:
                period = dt.strftime("%Y-%m-%d")

            if period not in grouped:
                grouped[period] = []
            grouped[period].append(r)

        return grouped

    def _calculate_trend(self, data_points: List[Dict]) -> tuple[str, float]:
        """Calculate trend direction and percentage change."""
        if len(data_points) < 2:
            return "stable", 0.0

        # Compare first half to second half
        mid = len(data_points) // 2
        first_half = data_points[:mid]
        second_half = data_points[mid:]

        first_avg = sum(d["tokens"] for d in first_half) / len(first_half) if first_half else 0
        second_avg = sum(d["tokens"] for d in second_half) / len(second_half) if second_half else 0

        if first_avg == 0:
            if second_avg > 0:
                return "increasing", 100.0
            return "stable", 0.0

        change_pct = ((second_avg - first_avg) / first_avg) * 100

        if change_pct > 10:
            direction = "increasing"
        elif change_pct < -10:
            direction = "decreasing"
        else:
            direction = "stable"

        return direction, change_pct

    def _get_accuracy_rating(self, mape: float) -> str:
        """Get accuracy rating based on mean absolute percentage error."""
        if mape <= 10:
            return "excellent"
        elif mape <= 25:
            return "good"
        elif mape <= 50:
            return "fair"
        else:
            return "poor"
