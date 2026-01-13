"""Tests for the configuration loader module."""
import json
import pytest
from pathlib import Path

from core.config import (
    ConfigLoader,
    AgentConfig,
    TimeoutConfig,
    RetryConfig,
    ContextLimitsConfig,
    ParallelConfig,
    BudgetConfig,
    get_agent_config,
    get_budget_config,
)


class TestTimeoutConfig:
    """Tests for TimeoutConfig defaults."""

    def test_default_values(self):
        """Test default timeout values."""
        config = TimeoutConfig()
        assert config.print_mode == 300
        assert config.agentic_mode == 600
        assert config.expert_consultation == 180

    def test_custom_values(self):
        """Test custom timeout values."""
        config = TimeoutConfig(print_mode=120, agentic_mode=300, expert_consultation=60)
        assert config.print_mode == 120
        assert config.agentic_mode == 300
        assert config.expert_consultation == 60

    def test_immutable(self):
        """Test that config is frozen/immutable."""
        config = TimeoutConfig()
        with pytest.raises(Exception):  # FrozenInstanceError
            config.print_mode = 500


class TestRetryConfig:
    """Tests for RetryConfig defaults."""

    def test_default_values(self):
        """Test default retry values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.agentic_base_delay == 2.0
        assert config.backoff_multiplier == 2.0
        assert config.max_delay == 60.0

    def test_custom_values(self):
        """Test custom retry values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            agentic_base_delay=1.0,
            backoff_multiplier=1.5,
            max_delay=30.0
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5


class TestContextLimitsConfig:
    """Tests for ContextLimitsConfig."""

    def test_default_values(self):
        """Test default context limit values."""
        config = ContextLimitsConfig()
        assert config.base_codebase == 4000
        assert config.base_scout == 3500
        assert config.base_architect == 2500
        assert config.minimum == 1500


class TestParallelConfig:
    """Tests for ParallelConfig."""

    def test_default_values(self):
        """Test default parallel values."""
        config = ParallelConfig()
        assert config.max_sub_features == 3
        assert config.max_expert_workers == 3


class TestAgentConfig:
    """Tests for AgentConfig composite."""

    def test_default_construction(self):
        """Test default AgentConfig contains all defaults."""
        config = AgentConfig()
        assert config.timeouts.print_mode == 300
        assert config.retry.max_attempts == 3
        assert config.context_limits.base_codebase == 4000
        assert config.parallel.max_sub_features == 3


class TestBudgetConfig:
    """Tests for BudgetConfig."""

    def test_default_values(self):
        """Test default budget values."""
        config = BudgetConfig()
        assert config.daily_limit == 5.0
        assert config.weekly_limit == 25.0
        assert config.monthly_limit == 100.0
        assert config.per_workflow_limit is None
        assert config.warning_threshold == 0.8


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_get_agent_config_with_file(self, project_root):
        """Test loading agent config from file."""
        # Create agent.json
        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        config_data = {
            "timeouts": {"print_mode": 120, "agentic_mode": 240},
            "retry": {"max_attempts": 5},
            "context_limits": {"base_codebase": 5000},
            "parallel": {"max_sub_features": 4}
        }
        (config_dir / "agent.json").write_text(json.dumps(config_data))

        config = ConfigLoader.get_agent_config(project_root, use_cache=False)

        assert config.timeouts.print_mode == 120
        assert config.timeouts.agentic_mode == 240
        assert config.timeouts.expert_consultation == 180  # default
        assert config.retry.max_attempts == 5
        assert config.context_limits.base_codebase == 5000
        assert config.parallel.max_sub_features == 4

    def test_get_agent_config_missing_file(self, project_root):
        """Test that missing config returns defaults."""
        config = ConfigLoader.get_agent_config(project_root, use_cache=False)

        assert config.timeouts.print_mode == 300
        assert config.retry.max_attempts == 3

    def test_get_agent_config_invalid_json(self, project_root):
        """Test that invalid JSON returns defaults."""
        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "agent.json").write_text("{ invalid json }")

        config = ConfigLoader.get_agent_config(project_root, use_cache=False)

        assert config.timeouts.print_mode == 300  # default

    def test_get_agent_config_caching(self, project_root):
        """Test that config is cached."""
        ConfigLoader.clear_cache()

        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 999}}')

        config1 = ConfigLoader.get_agent_config(project_root)

        # Modify file
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 111}}')

        # Should still return cached value
        config2 = ConfigLoader.get_agent_config(project_root)
        assert config2.timeouts.print_mode == 999

    def test_get_budget_config_with_file(self, project_root):
        """Test loading budget config from file."""
        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        config_data = {
            "daily_limit": 10.0,
            "weekly_limit": 50.0,
            "monthly_limit": 200.0,
            "per_workflow_limit": 2.0,
            "warning_threshold": 0.9
        }
        (config_dir / "budget.json").write_text(json.dumps(config_data))

        config = ConfigLoader.get_budget_config(project_root, use_cache=False)

        assert config.daily_limit == 10.0
        assert config.weekly_limit == 50.0
        assert config.monthly_limit == 200.0
        assert config.per_workflow_limit == 2.0
        assert config.warning_threshold == 0.9

    def test_clear_cache(self, project_root):
        """Test cache clearing."""
        ConfigLoader.clear_cache()

        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 888}}')

        config1 = ConfigLoader.get_agent_config(project_root)
        assert config1.timeouts.print_mode == 888

        # Modify and clear cache
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 777}}')
        ConfigLoader.clear_cache()

        config2 = ConfigLoader.get_agent_config(project_root)
        assert config2.timeouts.print_mode == 777

    def test_reload(self, project_root):
        """Test force reload."""
        ConfigLoader.clear_cache()

        config_dir = project_root / ".orchestrator" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 555}}')
        (config_dir / "budget.json").write_text('{"daily_limit": 15.0}')

        # Load initially
        ConfigLoader.get_agent_config(project_root)

        # Modify files
        (config_dir / "agent.json").write_text('{"timeouts": {"print_mode": 444}}')
        (config_dir / "budget.json").write_text('{"daily_limit": 20.0}')

        # Reload
        agent_config, budget_config = ConfigLoader.reload(project_root)

        assert agent_config.timeouts.print_mode == 444
        assert budget_config.daily_limit == 20.0


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_agent_config_function(self, project_root):
        """Test get_agent_config convenience function."""
        ConfigLoader.clear_cache()
        config = get_agent_config(project_root)
        assert isinstance(config, AgentConfig)

    def test_get_budget_config_function(self, project_root):
        """Test get_budget_config convenience function."""
        ConfigLoader.clear_cache()
        config = get_budget_config(project_root)
        assert isinstance(config, BudgetConfig)
