"""
Repository Factory - Centralized repository creation with DI.

This module provides a factory for creating project-scoped repositories
with proper dependency injection. It ensures all repositories receive
the same project context.

SOLID Principles:
- DIP: Dependencies are injected, not created
- SRP: Factory only handles repository creation
- OCP: New repositories can be added without modifying existing code
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database
    from ..project_context import IProjectContextProvider

from .plans import PlanRepository
from .runs import RunRepository
from .knowledge import KnowledgeRepository
from .build_state import BuildStateRepository
from .cost import CostRepository
from .file_knowledge import FileKnowledgeRepository
from .token_usage import TokenUsageRepository
from .task_mapping import TaskMappingRepository


class RepositoryFactory:
    """Factory for creating project-scoped repositories.

    This factory creates repositories with consistent project context,
    enabling proper multi-project support and dependency injection.

    Args:
        db: Database connection instance
        context_provider: Optional project context provider.
                         If provided, repositories will use its project_id.
        project_id: Optional explicit project ID (takes precedence over provider)
    """

    def __init__(
        self,
        db: "Database",
        context_provider: "IProjectContextProvider" = None,
        project_id: Optional[str] = None
    ):
        self.db = db
        self._context_provider = context_provider
        self._explicit_project_id = project_id

    @property
    def project_id(self) -> Optional[str]:
        """Get the project ID for repository creation.

        Priority:
        1. Explicit project_id (if provided)
        2. Context provider's project_id (if provider exists)
        3. None (let repository fall back to contextvar)
        """
        if self._explicit_project_id:
            return self._explicit_project_id
        if self._context_provider:
            return self._context_provider.get_project_id()
        return None

    def create_plan_repository(self) -> PlanRepository:
        """Create a plan repository scoped to current project."""
        return PlanRepository(self.db, self.project_id)

    def create_run_repository(self) -> RunRepository:
        """Create a run repository scoped to current project."""
        return RunRepository(self.db, self.project_id)

    def create_knowledge_repository(self) -> KnowledgeRepository:
        """Create a knowledge repository scoped to current project."""
        return KnowledgeRepository(self.db, self.project_id)

    def create_build_state_repository(self) -> BuildStateRepository:
        """Create a build state repository scoped to current project."""
        return BuildStateRepository(self.db, self.project_id)

    def create_cost_repository(self) -> CostRepository:
        """Create a cost repository."""
        return CostRepository(self.db)

    def create_file_knowledge_repository(self) -> FileKnowledgeRepository:
        """Create a file knowledge repository scoped to current project."""
        return FileKnowledgeRepository(self.db, self.project_id)

    def create_token_usage_repository(self) -> TokenUsageRepository:
        """Create a token usage repository scoped to current project."""
        return TokenUsageRepository(self.db, self.project_id)

    def create_task_mapping_repository(self) -> TaskMappingRepository:
        """Create a task mapping repository.

        Note: TaskMapping is scoped by plan_id (which is already project-scoped),
        so explicit project_id is optional but passed for consistency.
        """
        return TaskMappingRepository(self.db, self.project_id)


def get_repository_factory(
    db: "Database" = None,
    context_provider: "IProjectContextProvider" = None,
    project_id: Optional[str] = None
) -> RepositoryFactory:
    """Get a repository factory instance.

    Args:
        db: Database connection instance. If None, gets global instance.
        context_provider: Optional project context provider
        project_id: Optional explicit project ID

    Returns:
        RepositoryFactory instance
    """
    if db is None:
        from .. import get_database
        db = get_database()

    return RepositoryFactory(db, context_provider, project_id)
