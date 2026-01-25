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


class IProjectContextProvider(ABC):
    """Interface for getting current project context.

    This abstraction allows different implementations for getting the
    current project ID, enabling dependency injection and testability.

    Implementations:
    - ContextVarProjectProvider: Gets from contextvar only
    - RegistryFallbackProjectProvider: Gets from contextvar, falls back to registry
    """

    @abstractmethod
    def get_project_id(self) -> Optional[str]:
        """Get the current project ID.

        Returns:
            The current project ID or None if not set.
        """
        ...

    @abstractmethod
    def require_project_id(self) -> str:
        """Get the current project ID, raising if not set.

        Returns:
            The current project ID.

        Raises:
            ProjectContextError: If no project context is available.
        """
        ...


class IFileKnowledgeRepository(ABC):
    """Interface for file-level knowledge repository operations."""

    @abstractmethod
    def save_file_knowledge(
        self,
        file_path: str,
        file_type: str,
        language: str,
        size_bytes: int,
        line_count: int,
        imports: List[str] = None,
        exports: List[str] = None,
        classes: List[Dict] = None,
        functions: List[Dict] = None,
        dependencies: List[str] = None,
        metadata: Dict = None,
        summary: str = None
    ) -> int:
        """Save or update file-level knowledge."""
        ...

    @abstractmethod
    def load_file_knowledge(self, file_path: str) -> Optional[Dict]:
        """Load knowledge for a specific file."""
        ...

    @abstractmethod
    def get_all_file_knowledge(self) -> List[Dict]:
        """Get knowledge for all scanned files."""
        ...

    @abstractmethod
    def delete_file_knowledge(self, file_path: str) -> bool:
        """Delete knowledge for a specific file."""
        ...

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if knowledge exists for a specific file."""
        ...

    @abstractmethod
    def save_file_scan(
        self,
        scan_id: str,
        file_path: str,
        scan_type: str = "single",
        trigger: str = "manual",
        started_at: str = None,
        completed_at: str = None,
        duration_seconds: float = 0,
        status: str = "completed",
        error_message: str = None,
        knowledge_id: int = None
    ) -> int:
        """Save a file scan history record."""
        ...

    @abstractmethod
    def get_file_scan_history(self, file_path: str, limit: int = 10) -> List[Dict]:
        """Get scan history for a specific file."""
        ...

    @abstractmethod
    def clear_all_file_knowledge(self) -> int:
        """Clear all file knowledge and scan history."""
        ...
