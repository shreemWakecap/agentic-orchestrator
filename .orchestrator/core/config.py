"""
Configuration loader for orchestrator settings.

Loads configuration from .orchestrator/config/*.json files.
Provides typed access with sensible defaults if files are missing.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout settings in seconds."""
    print_mode: int = 300
    agentic_mode: int = 600
    expert_consultation: int = 180


@dataclass(frozen=True)
class RetryConfig:
    """Retry behavior settings."""
    max_attempts: int = 3
    base_delay: float = 1.0
    agentic_base_delay: float = 2.0
    backoff_multiplier: float = 2.0
    max_delay: float = 60.0


@dataclass(frozen=True)
class ContextLimitsConfig:
    """Context size limits for agents."""
    base_codebase: int = 4000
    base_scout: int = 3500
    base_architect: int = 2500
    minimum: int = 1500


@dataclass(frozen=True)
class ParallelConfig:
    """Parallelism settings."""
    max_sub_features: int = 3
    max_expert_workers: int = 3
    max_build_workers: int = 3  # Max parallel builder agents
    overlap_build_test: bool = True  # Run tests async while building next phase
    simple_build_parallel: bool = True  # Enable parallelization for simple builds


@dataclass(frozen=True)
class AgentConfig:
    """Complete agent configuration."""
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    context_limits: ContextLimitsConfig = field(default_factory=ContextLimitsConfig)
    parallel: ParallelConfig = field(default_factory=ParallelConfig)


@dataclass(frozen=True)
class BudgetConfig:
    """Budget settings for cost management."""
    daily_limit: float = 5.0
    weekly_limit: float = 25.0
    monthly_limit: float = 100.0
    per_workflow_limit: Optional[float] = None
    warning_threshold: float = 0.8


class ConfigLoader:
    """
    Loads and caches configuration from .orchestrator/config/.

    Usage:
        config = ConfigLoader.get_agent_config(project_root)
        timeout = config.timeouts.print_mode
    """

    _agent_cache: dict[Path, AgentConfig] = {}
    _budget_cache: dict[Path, BudgetConfig] = {}

    @classmethod
    def _load_json(cls, path: Path) -> dict:
        """Load JSON file, returning empty dict if missing or invalid."""
        if not path.exists():
            logger.debug(f"Config file not found: {path}")
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {path}: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Error reading {path}: {e}")
            return {}

    @classmethod
    def get_agent_config(cls, project_root: Path, use_cache: bool = True) -> AgentConfig:
        """
        Load agent configuration from .orchestrator/config/agent.json.

        Args:
            project_root: Project root directory
            use_cache: Whether to use cached config (default True)

        Returns:
            AgentConfig with loaded or default values
        """
        resolved = project_root.resolve()

        if use_cache and resolved in cls._agent_cache:
            return cls._agent_cache[resolved]

        config_path = resolved / ".orchestrator" / "config" / "agent.json"
        data = cls._load_json(config_path)

        timeouts_data = data.get("timeouts", {})
        retry_data = data.get("retry", {})
        context_data = data.get("context_limits", {})
        parallel_data = data.get("parallel", {})

        config = AgentConfig(
            timeouts=TimeoutConfig(
                print_mode=timeouts_data.get("print_mode", 300),
                agentic_mode=timeouts_data.get("agentic_mode", 600),
                expert_consultation=timeouts_data.get("expert_consultation", 180),
            ),
            retry=RetryConfig(
                max_attempts=retry_data.get("max_attempts", 3),
                base_delay=retry_data.get("base_delay", 1.0),
                agentic_base_delay=retry_data.get("agentic_base_delay", 2.0),
                backoff_multiplier=retry_data.get("backoff_multiplier", 2.0),
                max_delay=retry_data.get("max_delay", 60.0),
            ),
            context_limits=ContextLimitsConfig(
                base_codebase=context_data.get("base_codebase", 4000),
                base_scout=context_data.get("base_scout", 3500),
                base_architect=context_data.get("base_architect", 2500),
                minimum=context_data.get("minimum", 1500),
            ),
            parallel=ParallelConfig(
                max_sub_features=parallel_data.get("max_sub_features", 3),
                max_expert_workers=parallel_data.get("max_expert_workers", 3),
                max_build_workers=parallel_data.get("max_build_workers", 3),
                overlap_build_test=parallel_data.get("overlap_build_test", True),
                simple_build_parallel=parallel_data.get("simple_build_parallel", True),
            ),
        )

        if use_cache:
            cls._agent_cache[resolved] = config

        return config

    @classmethod
    def get_budget_config(cls, project_root: Path, use_cache: bool = True) -> BudgetConfig:
        """
        Load budget configuration from .orchestrator/config/budget.json.

        Args:
            project_root: Project root directory
            use_cache: Whether to use cached config (default True)

        Returns:
            BudgetConfig with loaded or default values
        """
        resolved = project_root.resolve()

        if use_cache and resolved in cls._budget_cache:
            return cls._budget_cache[resolved]

        config_path = resolved / ".orchestrator" / "config" / "budget.json"
        data = cls._load_json(config_path)

        config = BudgetConfig(
            daily_limit=data.get("daily_limit", 5.0),
            weekly_limit=data.get("weekly_limit", 25.0),
            monthly_limit=data.get("monthly_limit", 100.0),
            per_workflow_limit=data.get("per_workflow_limit"),
            warning_threshold=data.get("warning_threshold", 0.8),
        )

        if use_cache:
            cls._budget_cache[resolved] = config

        return config

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached configurations."""
        cls._agent_cache.clear()
        cls._budget_cache.clear()

    @classmethod
    def reload(cls, project_root: Path) -> tuple[AgentConfig, BudgetConfig]:
        """Force reload all configurations for a project."""
        resolved = project_root.resolve()
        cls._agent_cache.pop(resolved, None)
        cls._budget_cache.pop(resolved, None)
        return (
            cls.get_agent_config(project_root),
            cls.get_budget_config(project_root),
        )


# Convenience functions for direct access
def get_agent_config(project_root: Path) -> AgentConfig:
    """Get agent configuration for a project."""
    return ConfigLoader.get_agent_config(project_root)


def get_budget_config(project_root: Path) -> BudgetConfig:
    """Get budget configuration for a project."""
    return ConfigLoader.get_budget_config(project_root)
