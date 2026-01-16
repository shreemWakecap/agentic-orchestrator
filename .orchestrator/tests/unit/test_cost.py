"""Tests for cost estimation module."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from core.cost import (
    Model,
    MODEL_PRICING,
    TokenEstimate,
    CostEstimate,
    ActualCost,
    CostEstimator,
    CostReporter,
    Budget,
    BudgetManager
)


class TestTokenEstimate:
    """Tests for TokenEstimate class."""

    def test_total_tokens(self):
        estimate = TokenEstimate(input_tokens=1000, output_tokens=500)
        assert estimate.total_tokens == 1500

    def test_estimated_cost_sonnet(self):
        # 1000 input @ $3/1M + 500 output @ $15/1M = $0.003 + $0.0075 = $0.0105
        estimate = TokenEstimate(input_tokens=1000, output_tokens=500, model=Model.CLAUDE_3_5_SONNET)
        assert estimate.estimated_cost == pytest.approx(0.0105, rel=0.01)

    def test_estimated_cost_haiku(self):
        # 1000 input @ $0.25/1M + 500 output @ $1.25/1M
        # Result is rounded to 4 decimal places: 0.00025 + 0.000625 = 0.000875 -> rounds to 0.0009
        estimate = TokenEstimate(input_tokens=1000, output_tokens=500, model=Model.CLAUDE_3_HAIKU)
        assert estimate.estimated_cost == pytest.approx(0.0009, rel=0.01)

    def test_str_representation(self):
        estimate = TokenEstimate(input_tokens=1000, output_tokens=500)
        result = str(estimate)
        assert "1,500 tokens" in result
        assert "$" in result


class TestCostEstimate:
    """Tests for CostEstimate class."""

    def test_total_cost(self):
        agents = {
            "agent1": TokenEstimate(500, 300),
            "agent2": TokenEstimate(500, 200)
        }
        total = TokenEstimate(1000, 500)
        estimate = CostEstimate(
            workflow="test",
            agents=agents,
            total_estimate=total,
            confidence=0.8
        )
        assert estimate.total_cost == total.estimated_cost

    def test_to_dict(self):
        agents = {"agent1": TokenEstimate(500, 300)}
        total = TokenEstimate(500, 300)
        estimate = CostEstimate(
            workflow="test",
            agents=agents,
            total_estimate=total,
            confidence=0.8
        )
        result = estimate.to_dict()
        assert result["workflow"] == "test"
        assert result["confidence"] == 0.8
        assert "agent1" in result["agents"]


class TestActualCost:
    """Tests for ActualCost class."""

    def test_to_dict(self):
        cost = ActualCost(
            workflow="planning",
            run_id="abc123",
            started_at="2025-01-01T10:00:00",
            completed_at="2025-01-01T10:05:00",
            agents={"agent1": 1000},
            total_tokens=1000,
            estimated_cost=0.05
        )
        result = cost.to_dict()
        assert result["workflow"] == "planning"
        assert result["run_id"] == "abc123"
        assert result["total_tokens"] == 1000

    def test_from_dict(self):
        data = {
            "workflow": "building",
            "run_id": "xyz789",
            "started_at": "2025-01-01T10:00:00",
            "completed_at": "2025-01-01T10:10:00",
            "agents": {"builder": 2000},
            "total_tokens": 2000,
            "estimated_cost_usd": 0.10
        }
        cost = ActualCost.from_dict(data)
        assert cost.workflow == "building"
        assert cost.run_id == "xyz789"
        assert cost.total_tokens == 2000


class TestCostEstimator:
    """Tests for CostEstimator class."""

    @pytest.fixture
    def estimator(self, tmp_path):
        history_file = tmp_path / "cost_history.json"
        return CostEstimator(history_file)

    def test_estimate_planning_simple(self, estimator):
        estimate = estimator.estimate_planning(100, "simple")
        assert estimate.workflow == "planning"
        assert estimate.total_estimate.total_tokens > 0
        assert estimate.confidence > 0

    def test_estimate_planning_complex(self, estimator):
        simple = estimator.estimate_planning(100, "simple")
        complex_est = estimator.estimate_planning(100, "complex")
        # Complex should have more agents
        assert len(complex_est.agents) > len(simple.agents)
        # Complex should have higher token count
        assert complex_est.total_estimate.total_tokens > simple.total_estimate.total_tokens

    def test_estimate_building(self, estimator, tmp_path):
        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text("""
# Plan
## Step 1
Do something
## Step 2
Do something else
## Step 3
Final step
        """)
        estimate = estimator.estimate_building(plan_file)
        assert estimate.workflow == "building"
        assert "parser" in estimate.agents
        assert "coordinator" in estimate.agents

    def test_estimate_building_with_step_count(self, estimator, tmp_path):
        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text("Empty plan")
        estimate = estimator.estimate_building(plan_file, step_count=5)
        # Should have 5 builder steps
        builder_agents = [a for a in estimate.agents if a.startswith("builder_step_")]
        assert len(builder_agents) == 5

    def test_record_and_load_history(self, tmp_path):
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)

        cost = ActualCost(
            workflow="planning",
            run_id="test123",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            agents={"agent1": 1000},
            total_tokens=1000,
            estimated_cost=0.05
        )
        estimator.record_actual_cost(cost)

        # Create new estimator to test loading
        estimator2 = CostEstimator(history_file)
        assert len(estimator2.history) == 1
        assert estimator2.history[0].run_id == "test123"

    def test_get_average_cost(self, tmp_path):
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)

        for i in range(3):
            cost = ActualCost(
                workflow="planning",
                run_id=f"test{i}",
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                agents={},
                total_tokens=1000,
                estimated_cost=0.10 * (i + 1)
            )
            estimator.record_actual_cost(cost)

        avg = estimator.get_average_cost("planning")
        assert avg == pytest.approx(0.20, rel=0.01)  # (0.10 + 0.20 + 0.30) / 3

    def test_get_average_cost_no_history(self, estimator):
        avg = estimator.get_average_cost("nonexistent")
        assert avg is None

    def test_calculate_cost_from_tokens(self, estimator):
        # 1000 tokens with 40/60 split
        cost = estimator.calculate_cost_from_tokens(1000)
        expected = TokenEstimate(400, 600).estimated_cost
        assert cost == pytest.approx(expected, rel=0.01)


class TestCostReporter:
    """Tests for CostReporter class."""

    @pytest.fixture
    def estimator_with_history(self, tmp_path):
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)

        # Add some test data
        now = datetime.now()
        for i in range(5):
            cost = ActualCost(
                workflow="planning" if i < 3 else "building",
                run_id=f"test{i}",
                started_at=(now - timedelta(days=i)).isoformat(),
                completed_at=(now - timedelta(days=i)).isoformat(),
                agents={"agent": 1000},
                total_tokens=1000 * (i + 1),
                estimated_cost=0.05 * (i + 1)
            )
            estimator.record_actual_cost(cost)

        return estimator

    def test_daily_report(self, estimator_with_history):
        reporter = CostReporter(estimator_with_history)
        report = reporter.daily_report()
        assert "date" in report
        assert "total_runs" in report
        assert "total_tokens" in report
        assert "total_cost" in report
        assert "by_workflow" in report

    def test_weekly_report(self, estimator_with_history):
        reporter = CostReporter(estimator_with_history)
        report = reporter.weekly_report()
        assert "period" in report
        assert report["total_runs"] >= 0

    def test_monthly_report(self, estimator_with_history):
        reporter = CostReporter(estimator_with_history)
        report = reporter.monthly_report()
        assert "month" in report
        assert report["total_runs"] >= 0

    def test_group_by_workflow(self, estimator_with_history):
        reporter = CostReporter(estimator_with_history)
        report = reporter.weekly_report()
        if report["by_workflow"]:
            for wf, data in report["by_workflow"].items():
                assert "runs" in data
                assert "tokens" in data
                assert "cost" in data


class TestBudget:
    """Tests for Budget class."""

    def test_default_values(self):
        budget = Budget()
        assert budget.daily_limit is None
        assert budget.weekly_limit is None
        assert budget.monthly_limit is None
        assert budget.per_workflow_limit is None
        assert budget.warning_threshold == 0.8

    def test_custom_values(self):
        budget = Budget(
            daily_limit=10.0,
            weekly_limit=50.0,
            monthly_limit=200.0,
            per_workflow_limit=5.0,
            warning_threshold=0.9
        )
        assert budget.daily_limit == 10.0
        assert budget.warning_threshold == 0.9


class TestBudgetManager:
    """Tests for BudgetManager class."""

    @pytest.fixture
    def budget_manager(self, tmp_path):
        config_path = tmp_path / "config" / "budget.json"
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)
        return BudgetManager(config_path, estimator)

    def test_default_budget(self, budget_manager):
        assert budget_manager.budget.daily_limit is None
        assert budget_manager.budget.warning_threshold == 0.8

    def test_save_and_load_budget(self, tmp_path):
        config_path = tmp_path / "config" / "budget.json"
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)

        manager1 = BudgetManager(config_path, estimator)
        budget = Budget(daily_limit=10.0, monthly_limit=100.0)
        manager1.save_budget(budget)

        # Create new manager to test loading
        manager2 = BudgetManager(config_path, estimator)
        assert manager2.budget.daily_limit == 10.0
        assert manager2.budget.monthly_limit == 100.0

    def test_check_budget_within_limit(self, budget_manager):
        budget_manager.budget = Budget(daily_limit=10.0)
        allowed, message = budget_manager.check_budget(0.50)
        assert allowed is True
        assert "Within budget" in message

    def test_check_budget_exceeds_per_workflow(self, budget_manager):
        budget_manager.budget = Budget(per_workflow_limit=0.10)
        allowed, message = budget_manager.check_budget(0.50)
        assert allowed is False
        assert "Exceeds per-workflow limit" in message

    def test_check_budget_warning(self, tmp_path):
        config_path = tmp_path / "config" / "budget.json"
        history_file = tmp_path / "cost_history.json"
        estimator = CostEstimator(history_file)

        # Add cost to bring usage to 85%
        cost = ActualCost(
            workflow="planning",
            run_id="test",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            agents={},
            total_tokens=1000,
            estimated_cost=8.50
        )
        estimator.record_actual_cost(cost)

        manager = BudgetManager(config_path, estimator)
        manager.budget = Budget(daily_limit=10.0, warning_threshold=0.8)

        allowed, message = manager.check_budget(0.50)
        assert allowed is True
        assert "Warning" in message

    def test_get_remaining_budget(self, budget_manager):
        budget_manager.budget = Budget(
            daily_limit=10.0,
            weekly_limit=50.0,
            monthly_limit=200.0
        )
        remaining = budget_manager.get_remaining_budget()

        assert "daily" in remaining
        assert "weekly" in remaining
        assert "monthly" in remaining
        assert remaining["daily"]["limit"] == 10.0
        assert remaining["daily"]["remaining"] is not None


class TestModelPricing:
    """Tests for model pricing constants."""

    def test_all_models_have_pricing(self):
        for model in Model:
            assert model in MODEL_PRICING
            assert "input" in MODEL_PRICING[model]
            assert "output" in MODEL_PRICING[model]

    def test_pricing_values(self):
        # Verify Claude 3.5 Sonnet pricing
        sonnet = MODEL_PRICING[Model.CLAUDE_3_5_SONNET]
        assert sonnet["input"] == 3.00
        assert sonnet["output"] == 15.00

        # Verify Haiku is cheaper
        haiku = MODEL_PRICING[Model.CLAUDE_3_HAIKU]
        assert haiku["input"] < sonnet["input"]
        assert haiku["output"] < sonnet["output"]
