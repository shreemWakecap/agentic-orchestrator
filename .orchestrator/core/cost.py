"""Cost estimation and tracking for orchestrator workflows."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
from pathlib import Path
import json
import re


class Model(Enum):
    """Claude model identifiers."""
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku"


# Pricing per 1M tokens (as of Jan 2025)
MODEL_PRICING = {
    Model.CLAUDE_3_5_SONNET: {
        "input": 3.00,   # $3 per 1M input tokens
        "output": 15.00  # $15 per 1M output tokens
    },
    Model.CLAUDE_3_OPUS: {
        "input": 15.00,
        "output": 75.00
    },
    Model.CLAUDE_3_HAIKU: {
        "input": 0.25,
        "output": 1.25
    },
    Model.CLAUDE_3_5_HAIKU: {
        "input": 1.00,
        "output": 5.00
    }
}

DEFAULT_MODEL = Model.CLAUDE_3_5_SONNET


@dataclass
class TokenEstimate:
    """Estimated token usage."""
    input_tokens: int
    output_tokens: int
    model: Model = DEFAULT_MODEL

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Calculate estimated cost in USD."""
        pricing = MODEL_PRICING[self.model]
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 4)

    def __str__(self) -> str:
        return f"~{self.total_tokens:,} tokens (${self.estimated_cost:.4f})"


@dataclass
class CostEstimate:
    """Complete cost estimate for a workflow."""
    workflow: str
    agents: dict[str, TokenEstimate]
    total_estimate: TokenEstimate
    confidence: float  # 0-1, how confident is this estimate
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        return self.total_estimate.estimated_cost

    def to_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "total_tokens": self.total_estimate.total_tokens,
            "total_cost_usd": self.total_cost,
            "confidence": self.confidence,
            "agents": {
                name: {
                    "input": est.input_tokens,
                    "output": est.output_tokens,
                    "cost": est.estimated_cost
                }
                for name, est in self.agents.items()
            }
        }


@dataclass
class ActualCost:
    """Actual cost after workflow completion."""
    workflow: str
    run_id: str
    started_at: str  # ISO format string
    completed_at: str  # ISO format string
    agents: dict[str, int]  # agent_name -> tokens_used
    total_tokens: int
    estimated_cost: float
    actual_cost: Optional[float] = None  # If available from API

    def to_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost,
            "actual_cost_usd": self.actual_cost,
            "agents": self.agents
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActualCost":
        return cls(
            workflow=data["workflow"],
            run_id=data["run_id"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            agents=data.get("agents", {}),
            total_tokens=data["total_tokens"],
            estimated_cost=data.get("estimated_cost_usd", 0),
            actual_cost=data.get("actual_cost_usd")
        )


class CostEstimator:
    """Estimates workflow costs based on historical data and heuristics."""

    # Base token estimates per agent (conservative estimates)
    AGENT_BASE_ESTIMATES = {
        # Planning agents
        "analyzer": TokenEstimate(500, 300),
        "scout": TokenEstimate(1000, 1500),
        "architect": TokenEstimate(2000, 2000),
        "planner": TokenEstimate(3000, 4000),
        "validator": TokenEstimate(2000, 500),
        "decomposer": TokenEstimate(1500, 1000),
        "synthesizer": TokenEstimate(4000, 3000),

        # Building agents
        "parser": TokenEstimate(2000, 1000),
        "builder": TokenEstimate(3000, 5000),  # Per step
        "coordinator": TokenEstimate(1500, 1000),
        "tester": TokenEstimate(2000, 2000),
        "integrator": TokenEstimate(3000, 4000),

        # Review/Fix/Sync agents
        "reviewer": TokenEstimate(3000, 2000),
        "fixer": TokenEstimate(2500, 3000),
        "syncer": TokenEstimate(2000, 1500),

        # Expert agents (average)
        "expert": TokenEstimate(3000, 2500),
    }

    # Workflow complexity multipliers
    COMPLEXITY_MULTIPLIERS = {
        "simple": 1.0,
        "medium": 1.5,
        "complex": 2.5,
        "massive": 4.0
    }

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or Path(".orchestrator/cost_history.json")
        self.history: list[ActualCost] = []
        self._load_history()

    def _load_history(self):
        """Load historical cost data."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                self.history = [ActualCost.from_dict(item) for item in data]
            except (json.JSONDecodeError, KeyError):
                self.history = []

    def _save_history(self):
        """Save cost history."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        data = [cost.to_dict() for cost in self.history]
        self.history_file.write_text(json.dumps(data, indent=2))

    def record_actual_cost(self, cost: ActualCost):
        """Record actual cost from completed workflow."""
        self.history.append(cost)
        self._save_history()

    def estimate_planning(
        self,
        request_length: int,
        complexity: str = "medium"
    ) -> CostEstimate:
        """Estimate cost for planning workflow."""
        multiplier = self.COMPLEXITY_MULTIPLIERS.get(complexity, 1.5)

        # Base agents for simple planning
        agents = {
            "analyzer": self._scale_estimate("analyzer", multiplier * 0.5),
            "scout": self._scale_estimate("scout", multiplier),
            "architect": self._scale_estimate("architect", multiplier),
            "planner": self._scale_estimate("planner", multiplier),
            "validator": self._scale_estimate("validator", 1.0),
        }

        # Add decomposition agents for complex workflows
        if complexity in ["complex", "massive"]:
            agents["decomposer"] = self._scale_estimate("decomposer", multiplier)
            agents["synthesizer"] = self._scale_estimate("synthesizer", multiplier)

            # Add parallel sub-planning (3 parallel by default)
            for i in range(3):
                agents[f"sub_planner_{i}"] = self._scale_estimate("planner", multiplier * 0.7)

        # Calculate total
        total_input = sum(e.input_tokens for e in agents.values())
        total_output = sum(e.output_tokens for e in agents.values())

        return CostEstimate(
            workflow="planning",
            agents=agents,
            total_estimate=TokenEstimate(total_input, total_output),
            confidence=0.7 if complexity == "medium" else 0.5
        )

    def estimate_building(
        self,
        plan_path: Path,
        step_count: Optional[int] = None
    ) -> CostEstimate:
        """Estimate cost for building workflow."""
        # Parse plan to count steps if not provided
        if step_count is None:
            step_count = self._count_plan_steps(plan_path)

        agents = {
            "parser": self._scale_estimate("parser", 1.0),
            "coordinator": self._scale_estimate("coordinator", 1.0),
            "tester": self._scale_estimate("tester", 1.0),
        }

        # Add builder for each step
        for i in range(step_count):
            agents[f"builder_step_{i}"] = self._scale_estimate("builder", 1.0)

        total_input = sum(e.input_tokens for e in agents.values())
        total_output = sum(e.output_tokens for e in agents.values())

        return CostEstimate(
            workflow="building",
            agents=agents,
            total_estimate=TokenEstimate(total_input, total_output),
            confidence=0.6
        )

    def estimate_reviewing(self, plan_path: Path) -> CostEstimate:
        """Estimate cost for reviewing workflow."""
        agents = {
            "reviewer": self._scale_estimate("reviewer", 1.0),
        }

        total_input = sum(e.input_tokens for e in agents.values())
        total_output = sum(e.output_tokens for e in agents.values())

        return CostEstimate(
            workflow="reviewing",
            agents=agents,
            total_estimate=TokenEstimate(total_input, total_output),
            confidence=0.75
        )

    def _scale_estimate(self, agent: str, multiplier: float) -> TokenEstimate:
        """Scale base estimate by multiplier."""
        base = self.AGENT_BASE_ESTIMATES.get(agent, TokenEstimate(1000, 1000))
        return TokenEstimate(
            input_tokens=int(base.input_tokens * multiplier),
            output_tokens=int(base.output_tokens * multiplier)
        )

    def _count_plan_steps(self, plan_path: Path) -> int:
        """Count steps in a plan file."""
        if not plan_path.exists():
            return 3  # Default minimum
        content = plan_path.read_text()
        # Count step headers like "### Step 1.1:" or "- Step:"
        steps = re.findall(r'#{1,4}\s*Step\s+\d', content)
        return max(len(steps), 3)  # Minimum 3 steps

    def get_average_cost(self, workflow: str) -> Optional[float]:
        """Get average historical cost for a workflow type."""
        relevant = [c for c in self.history if c.workflow == workflow]
        if not relevant:
            return None
        return sum(c.estimated_cost for c in relevant) / len(relevant)

    def calculate_cost_from_tokens(self, total_tokens: int, model: Model = DEFAULT_MODEL) -> float:
        """Calculate cost from token count (assumes 40% input, 60% output)."""
        input_tokens = int(total_tokens * 0.4)
        output_tokens = int(total_tokens * 0.6)
        estimate = TokenEstimate(input_tokens, output_tokens, model)
        return estimate.estimated_cost


class CostReporter:
    """Generate cost reports from history."""

    def __init__(self, estimator: CostEstimator):
        self.estimator = estimator

    def daily_report(self, date: Optional[datetime] = None) -> dict:
        """Generate daily cost report."""
        date = date or datetime.now()
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)

        runs = [c for c in self.estimator.history
                if datetime.fromisoformat(c.started_at) >= day_start]

        return {
            "date": date.date().isoformat(),
            "total_runs": len(runs),
            "total_tokens": sum(c.total_tokens for c in runs),
            "total_cost": sum(c.estimated_cost for c in runs),
            "by_workflow": self._group_by_workflow(runs)
        }

    def weekly_report(self) -> dict:
        """Generate weekly cost report."""
        now = datetime.now()
        week_start = now - timedelta(days=7)

        runs = [c for c in self.estimator.history
                if datetime.fromisoformat(c.started_at) >= week_start]

        return {
            "period": f"{week_start.date().isoformat()} to {now.date().isoformat()}",
            "total_runs": len(runs),
            "total_tokens": sum(c.total_tokens for c in runs),
            "total_cost": sum(c.estimated_cost for c in runs),
            "by_workflow": self._group_by_workflow(runs)
        }

    def monthly_report(self) -> dict:
        """Generate monthly cost report."""
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        runs = [c for c in self.estimator.history
                if datetime.fromisoformat(c.started_at) >= month_start]

        return {
            "month": now.strftime("%Y-%m"),
            "total_runs": len(runs),
            "total_tokens": sum(c.total_tokens for c in runs),
            "total_cost": sum(c.estimated_cost for c in runs),
            "by_workflow": self._group_by_workflow(runs)
        }

    def _group_by_workflow(self, runs: list[ActualCost]) -> dict:
        """Group runs by workflow type."""
        by_workflow = {}
        for run in runs:
            if run.workflow not in by_workflow:
                by_workflow[run.workflow] = {"runs": 0, "tokens": 0, "cost": 0}
            by_workflow[run.workflow]["runs"] += 1
            by_workflow[run.workflow]["tokens"] += run.total_tokens
            by_workflow[run.workflow]["cost"] += run.estimated_cost
        return by_workflow


@dataclass
class Budget:
    """Budget configuration."""
    daily_limit: Optional[float] = None  # USD
    weekly_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_workflow_limit: Optional[float] = None
    warning_threshold: float = 0.8  # Warn at 80%


class BudgetManager:
    """Manage spending budgets."""

    def __init__(self, config_path: Path, estimator: CostEstimator):
        self.config_path = config_path
        self.estimator = estimator
        self.budget = self._load_budget()

    def _load_budget(self) -> Budget:
        """Load budget configuration."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text())
                return Budget(**data)
            except (json.JSONDecodeError, TypeError):
                return Budget()
        return Budget()

    def save_budget(self, budget: Budget):
        """Save budget configuration."""
        self.budget = budget
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({
            "daily_limit": budget.daily_limit,
            "weekly_limit": budget.weekly_limit,
            "monthly_limit": budget.monthly_limit,
            "per_workflow_limit": budget.per_workflow_limit,
            "warning_threshold": budget.warning_threshold
        }, indent=2))

    def check_budget(self, estimated_cost: float) -> tuple[bool, str]:
        """
        Check if estimated cost is within budget.

        Returns:
            (allowed, message)
        """
        reporter = CostReporter(self.estimator)

        # Check daily limit
        if self.budget.daily_limit:
            daily = reporter.daily_report()
            remaining = self.budget.daily_limit - daily["total_cost"]

            if estimated_cost > remaining:
                return False, f"Daily budget exceeded. Remaining: ${remaining:.2f}"

            if daily["total_cost"] / self.budget.daily_limit > self.budget.warning_threshold:
                return True, f"Warning: {(daily['total_cost']/self.budget.daily_limit)*100:.0f}% of daily budget used"

        # Check per-workflow limit
        if self.budget.per_workflow_limit and estimated_cost > self.budget.per_workflow_limit:
            return False, f"Exceeds per-workflow limit of ${self.budget.per_workflow_limit:.2f}"

        return True, "Within budget"

    def get_remaining_budget(self) -> dict:
        """Get remaining budget for each limit type."""
        reporter = CostReporter(self.estimator)
        daily = reporter.daily_report()
        weekly = reporter.weekly_report()
        monthly = reporter.monthly_report()

        return {
            "daily": {
                "limit": self.budget.daily_limit,
                "used": daily["total_cost"],
                "remaining": (self.budget.daily_limit - daily["total_cost"]) if self.budget.daily_limit else None
            },
            "weekly": {
                "limit": self.budget.weekly_limit,
                "used": weekly["total_cost"],
                "remaining": (self.budget.weekly_limit - weekly["total_cost"]) if self.budget.weekly_limit else None
            },
            "monthly": {
                "limit": self.budget.monthly_limit,
                "used": monthly["total_cost"],
                "remaining": (self.budget.monthly_limit - monthly["total_cost"]) if self.budget.monthly_limit else None
            }
        }
