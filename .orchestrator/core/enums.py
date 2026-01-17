"""Enumerations for the orchestrator.

Using enums instead of magic strings provides:
- Type safety
- IDE autocomplete
- Runtime validation
- Clear documentation of valid values
"""
from enum import Enum


class PlanStatus(str, Enum):
    """Status values for plans.

    Plans progress through: pending -> building -> completed/failed
    """

    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class WorkflowType(str, Enum):
    """Types of workflows that can be executed."""

    PLANNING = "planning"
    BUILDING = "building"
    SYNCING = "syncing"
    SCOUTING = "scouting"

    def __str__(self) -> str:
        return self.value


class BuildStepStatus(str, Enum):
    """Status values for individual build steps."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    def __str__(self) -> str:
        return self.value


class RunStatus(str, Enum):
    """Status values for workflow runs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


class AgentType(str, Enum):
    """Types of agents available in the system."""

    PLANNER = "planner"
    BUILDER = "builder"
    SCOUT = "scout"
    SYNCER = "syncer"
    VERIFIER = "verifier"

    def __str__(self) -> str:
        return self.value


class EventType(str, Enum):
    """Types of events emitted during workflow execution."""

    START = "start"
    STEP = "step"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"
    WARNING = "warning"

    def __str__(self) -> str:
        return self.value


class Complexity(str, Enum):
    """Complexity levels for plans and tasks."""

    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

    def __str__(self) -> str:
        return self.value
