"""Abstract base classes defining service contracts for dependency injection.

This module contains interface definitions (abstract base classes) that define
the contracts for services used throughout the orchestrator server. These
interfaces enable loose coupling and facilitate testing through dependency
injection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any


class PlanState(Enum):
    """Enumeration of possible plan states."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Plan:
    """Data class representing a plan.

    Attributes:
        id: Unique identifier for the plan (e.g., '001_feature-name')
        name: Human-readable name of the plan
        state: Current state of the plan (pending, in-progress, completed, failed)
        file: Path to the plan directory
        files: List of filenames in the plan directory
        modified: ISO format timestamp of last modification
        content: Optional full content of the plan
        request: Optional original request text
        complexity: Optional complexity level (low, medium, high)
    """
    id: str
    name: str
    state: PlanState
    file: str
    files: List[str]
    modified: str
    content: Optional[str] = None
    request: Optional[str] = None
    complexity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary representation."""
        result = {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "file": self.file,
            "files": self.files,
            "modified": self.modified,
        }
        if self.content is not None:
            result["content"] = self.content
        if self.request is not None:
            result["request"] = self.request
        if self.complexity is not None:
            result["complexity"] = self.complexity
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create a Plan instance from a dictionary."""
        state_value = data.get("state", "pending")
        if isinstance(state_value, PlanState):
            state = state_value
        else:
            state = PlanState(state_value)

        return cls(
            id=data["id"],
            name=data["name"],
            state=state,
            file=data["file"],
            files=data.get("files", []),
            modified=data.get("modified", datetime.now().isoformat()),
            content=data.get("content"),
            request=data.get("request"),
            complexity=data.get("complexity"),
        )


class IPlanRegistry(ABC):
    """Abstract base class defining the plan registry service contract.

    The plan registry is responsible for managing plans in the orchestrator,
    including listing, retrieving, and updating plan states. Implementations
    may use file-based storage, databases, or other backends.
    """

    @abstractmethod
    def list_plans(self) -> List[Plan]:
        """List all plans across all states.

        Returns:
            List of Plan objects sorted by numeric prefix (e.g., 001_, 002_).
            The list includes plans from all states: pending, in-progress,
            completed, and failed.
        """
        pass

    @abstractmethod
    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a specific plan by its ID.

        Args:
            plan_id: The unique identifier of the plan (e.g., '001_feature-name')

        Returns:
            The Plan object if found, None otherwise. When found, the Plan
            includes full content loaded from the plan files.
        """
        pass

    @abstractmethod
    def update_status(self, plan_id: str, status: PlanState) -> bool:
        """Update the state of a plan.

        This method changes a plan's state by moving it to the appropriate
        state directory (e.g., from pending/ to in-progress/).

        Args:
            plan_id: The unique identifier of the plan
            status: The new state to set for the plan

        Returns:
            True if the status was successfully updated, False otherwise
            (e.g., if the plan was not found or the move failed).
        """
        pass


class IFileService(ABC):
    """Abstract base class defining the file service contract.

    The file service provides an abstraction over file system operations,
    enabling loose coupling from the actual file system and facilitating
    testing through mock implementations.
    """

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read the contents of a file.

        Args:
            path: The path to the file to read. Can be absolute or relative
                to the configured base directory.

        Returns:
            The contents of the file as a string.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read due to permissions.
            IOError: If an I/O error occurs during reading.
        """
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file.

        Creates the file if it doesn't exist, or overwrites it if it does.
        Also creates any necessary parent directories.

        Args:
            path: The path to the file to write. Can be absolute or relative
                to the configured base directory.
            content: The content to write to the file.

        Returns:
            True if the file was successfully written, False otherwise.

        Raises:
            PermissionError: If the file cannot be written due to permissions.
            IOError: If an I/O error occurs during writing.
        """
        pass

    @abstractmethod
    def move_file(self, src: str, dest: str) -> bool:
        """Move a file from source to destination.

        Moves a file (or directory) from the source path to the destination
        path. Creates any necessary parent directories for the destination.

        Args:
            src: The source path of the file to move.
            dest: The destination path where the file should be moved.

        Returns:
            True if the file was successfully moved, False otherwise
            (e.g., if the source file doesn't exist).

        Raises:
            FileNotFoundError: If the source file does not exist.
            PermissionError: If the operation is denied due to permissions.
            IOError: If an I/O error occurs during the move.
        """
        pass


@dataclass
class BudgetConfig:
    """Configuration for budget limits.

    Attributes:
        daily_limit: Maximum daily spending limit
        weekly_limit: Maximum weekly spending limit
        monthly_limit: Maximum monthly spending limit
        per_workflow_limit: Optional limit per workflow (None if unlimited)
        warning_threshold: Percentage threshold for budget warnings (0.0-1.0)
    """
    daily_limit: float
    weekly_limit: float
    monthly_limit: float
    per_workflow_limit: Optional[float]
    warning_threshold: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetConfig":
        """Create a BudgetConfig instance from a dictionary."""
        return cls(
            daily_limit=data.get("daily_limit", 5.0),
            weekly_limit=data.get("weekly_limit", 25.0),
            monthly_limit=data.get("monthly_limit", 100.0),
            per_workflow_limit=data.get("per_workflow_limit"),
            warning_threshold=data.get("warning_threshold", 0.8),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "daily_limit": self.daily_limit,
            "weekly_limit": self.weekly_limit,
            "monthly_limit": self.monthly_limit,
            "per_workflow_limit": self.per_workflow_limit,
            "warning_threshold": self.warning_threshold,
        }


@dataclass
class TimeoutConfig:
    """Configuration for operation timeouts.

    Attributes:
        print_mode: Timeout for print mode operations in seconds
        agentic_mode: Timeout for agentic mode operations in seconds
        expert_consultation: Timeout for expert consultation in seconds
    """
    print_mode: int
    agentic_mode: int
    expert_consultation: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeoutConfig":
        """Create a TimeoutConfig instance from a dictionary."""
        return cls(
            print_mode=data.get("print_mode", 300),
            agentic_mode=data.get("agentic_mode", 600),
            expert_consultation=data.get("expert_consultation", 180),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "print_mode": self.print_mode,
            "agentic_mode": self.agentic_mode,
            "expert_consultation": self.expert_consultation,
        }


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        agentic_base_delay: Base delay for agentic mode retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay between retries in seconds
    """
    max_attempts: int
    base_delay: float
    agentic_base_delay: float
    backoff_multiplier: float
    max_delay: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryConfig":
        """Create a RetryConfig instance from a dictionary."""
        return cls(
            max_attempts=data.get("max_attempts", 3),
            base_delay=data.get("base_delay", 1.0),
            agentic_base_delay=data.get("agentic_base_delay", 2.0),
            backoff_multiplier=data.get("backoff_multiplier", 2.0),
            max_delay=data.get("max_delay", 60.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "agentic_base_delay": self.agentic_base_delay,
            "backoff_multiplier": self.backoff_multiplier,
            "max_delay": self.max_delay,
        }


@dataclass
class ContextLimitsConfig:
    """Configuration for context size limits.

    Attributes:
        base_codebase: Base context limit for codebase operations
        base_scout: Base context limit for scout operations
        base_architect: Base context limit for architect operations
        minimum: Minimum context size
    """
    base_codebase: int
    base_scout: int
    base_architect: int
    minimum: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextLimitsConfig":
        """Create a ContextLimitsConfig instance from a dictionary."""
        return cls(
            base_codebase=data.get("base_codebase", 4000),
            base_scout=data.get("base_scout", 3500),
            base_architect=data.get("base_architect", 2500),
            minimum=data.get("minimum", 1500),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "base_codebase": self.base_codebase,
            "base_scout": self.base_scout,
            "base_architect": self.base_architect,
            "minimum": self.minimum,
        }


@dataclass
class ParallelConfig:
    """Configuration for parallel execution.

    Attributes:
        max_sub_features: Maximum number of parallel sub-feature workers
        max_expert_workers: Maximum number of parallel expert workers
    """
    max_sub_features: int
    max_expert_workers: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParallelConfig":
        """Create a ParallelConfig instance from a dictionary."""
        return cls(
            max_sub_features=data.get("max_sub_features", 3),
            max_expert_workers=data.get("max_expert_workers", 3),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "max_sub_features": self.max_sub_features,
            "max_expert_workers": self.max_expert_workers,
        }


@dataclass
class AgentConfig:
    """Configuration for agent behavior.

    Attributes:
        timeouts: Timeout configuration
        retry: Retry behavior configuration
        context_limits: Context size limits configuration
        parallel: Parallel execution configuration
    """
    timeouts: TimeoutConfig
    retry: RetryConfig
    context_limits: ContextLimitsConfig
    parallel: ParallelConfig

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """Create an AgentConfig instance from a dictionary."""
        return cls(
            timeouts=TimeoutConfig.from_dict(data.get("timeouts", {})),
            retry=RetryConfig.from_dict(data.get("retry", {})),
            context_limits=ContextLimitsConfig.from_dict(data.get("context_limits", {})),
            parallel=ParallelConfig.from_dict(data.get("parallel", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timeouts": self.timeouts.to_dict(),
            "retry": self.retry.to_dict(),
            "context_limits": self.context_limits.to_dict(),
            "parallel": self.parallel.to_dict(),
        }


@dataclass
class OrchestratorConfig:
    """Top-level configuration for the orchestrator.

    This class aggregates all configuration sections (budget, agent settings)
    into a single unified configuration object.

    Attributes:
        budget: Budget limits and thresholds configuration
        agent: Agent behavior configuration (timeouts, retry, context, parallel)
    """
    budget: BudgetConfig
    agent: AgentConfig

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestratorConfig":
        """Create an OrchestratorConfig instance from a dictionary."""
        return cls(
            budget=BudgetConfig.from_dict(data.get("budget", {})),
            agent=AgentConfig.from_dict(data.get("agent", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "budget": self.budget.to_dict(),
            "agent": self.agent.to_dict(),
        }


class IConfigService(ABC):
    """Abstract base class defining the configuration service contract.

    The config service is responsible for loading and providing access to
    orchestrator configuration settings from JSON files or other sources.
    This includes budget limits, agent settings, timeouts, and other
    operational parameters.
    """

    @abstractmethod
    def load_config(self) -> OrchestratorConfig:
        """Load and return the complete orchestrator configuration.

        Loads configuration from all config sources (budget.json, agent.json)
        and returns a unified OrchestratorConfig object. Configuration may
        be cached for performance.

        Returns:
            OrchestratorConfig object containing all configuration settings.

        Raises:
            FileNotFoundError: If required config files are missing.
            json.JSONDecodeError: If config files contain invalid JSON.
            IOError: If an I/O error occurs during config loading.
        """
        pass

    @abstractmethod
    def get_setting(self, key: str) -> Optional[Any]:
        """Get a specific configuration setting by key.

        Retrieves a configuration value using dot notation for nested keys.
        For example, 'budget.daily_limit' or 'agent.timeouts.print_mode'.

        Args:
            key: The configuration key in dot notation (e.g., 'budget.daily_limit')

        Returns:
            The configuration value if found, None if the key doesn't exist.
            The return type depends on the setting (int, float, str, dict, etc.)
        """
        pass
