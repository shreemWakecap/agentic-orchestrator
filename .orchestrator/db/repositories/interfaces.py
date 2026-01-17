"""Abstract repository interfaces.

These interfaces define the contract that repositories must implement,
enabling dependency injection and easier testing through mocking.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class IPlanRepository(ABC):
    """Interface for plan repository operations."""

    @abstractmethod
    def get_by_id(self, plan_id: str) -> Optional[Dict]:
        """Get a plan by its ID."""
        ...

    @abstractmethod
    def list_all(self) -> List[Dict]:
        """List all plans."""
        ...

    @abstractmethod
    def list_by_status(self, status: str) -> List[Dict]:
        """List plans with a specific status."""
        ...

    @abstractmethod
    def create(self, plan_id: str, **kwargs) -> int:
        """Create a new plan."""
        ...

    @abstractmethod
    def update_status(self, plan_id: str, status: str) -> None:
        """Update a plan's status."""
        ...

    @abstractmethod
    def delete(self, plan_id: str) -> None:
        """Delete a plan."""
        ...

    @abstractmethod
    def get_next_plan_number(self) -> int:
        """Get the next available plan number."""
        ...


class IBuildStateRepository(ABC):
    """Interface for build state repository operations."""

    @abstractmethod
    def get(self, plan_id: str) -> Optional[Dict]:
        """Get build state for a plan."""
        ...

    @abstractmethod
    def create(self, plan_id: str, total_steps: int = 0) -> int:
        """Create a new build state."""
        ...

    @abstractmethod
    def update(self, plan_id: str, **kwargs) -> None:
        """Update build state fields."""
        ...

    @abstractmethod
    def get_step_states(self, plan_id: str) -> List[Dict]:
        """Get all step states for a plan."""
        ...

    @abstractmethod
    def set_step_state(self, plan_id: str, step_id: str, **kwargs) -> None:
        """Set state for a specific step."""
        ...


class IRunRepository(ABC):
    """Interface for run repository operations."""

    @abstractmethod
    def get(self, run_id: str) -> Optional[Dict]:
        """Get a run by its ID."""
        ...

    @abstractmethod
    def list_active(self, status: Optional[str] = None) -> List[Dict]:
        """List active runs, optionally filtered by status."""
        ...

    @abstractmethod
    def create(self, run_id: str, workflow: str, **kwargs) -> None:
        """Create a new run."""
        ...

    @abstractmethod
    def update(self, run_id: str, **kwargs) -> None:
        """Update run fields."""
        ...

    @abstractmethod
    def add_event(self, run_id: str, event_type: str, data: Dict = None) -> None:
        """Add an event to a run."""
        ...

    @abstractmethod
    def get_events(self, run_id: str, since_id: int = 0) -> List[Dict]:
        """Get events for a run since a given event ID."""
        ...


class IKnowledgeRepository(ABC):
    """Interface for knowledge repository operations."""

    @abstractmethod
    def exists(self) -> bool:
        """Check if codebase knowledge exists."""
        ...

    @abstractmethod
    def load_knowledge(self) -> Optional[Dict]:
        """Load codebase knowledge."""
        ...

    @abstractmethod
    def save_knowledge(self, **kwargs) -> int:
        """Save codebase knowledge."""
        ...


class ICostRepository(ABC):
    """Interface for cost repository operations."""

    @abstractmethod
    def record_cost(self, **kwargs) -> None:
        """Record a cost entry."""
        ...

    @abstractmethod
    def get_history(self, days: int = 30) -> List[Dict]:
        """Get cost history for the specified number of days."""
        ...

    @abstractmethod
    def get_daily_total(self) -> float:
        """Get total cost for today."""
        ...

    @abstractmethod
    def get_weekly_total(self) -> float:
        """Get total cost for this week."""
        ...

    @abstractmethod
    def get_monthly_total(self) -> float:
        """Get total cost for this month."""
        ...
