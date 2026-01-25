"""
Project Context Management using contextvars.

This module provides thread-safe project context management for
multi-project support. It uses Python's contextvars to maintain
the active project across async/sync boundaries.

Usage:
    from db.project_context import project_context, require_project_context

    # Set the active project for the current context
    with project_context.set_project(project_id):
        # All database operations within this block are scoped to project_id
        plans = plan_repo.list_all()

    # Require project context (raises if not set)
    project_id = require_project_context()

    # Get current project (returns None if not set)
    project_id = project_context.get_project_id()
"""
import contextvars
from typing import Optional, ContextManager
from contextlib import contextmanager
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ProjectContextError(Exception):
    """Raised when project context is required but not available."""
    pass


@dataclass
class ProjectContextData:
    """Holds the current project context data."""
    project_id: str
    project_slug: str
    project_path: str


# The context variable that holds the current project
_project_context: contextvars.ContextVar[Optional[ProjectContextData]] = contextvars.ContextVar(
    'project_context',
    default=None
)


class ProjectContextManager:
    """
    Manages the active project context.

    This class provides methods to set, get, and clear the active project
    context. It uses contextvars for thread-safety and async compatibility.
    """

    @staticmethod
    def get_project_id() -> Optional[str]:
        """
        Get the current project ID.

        Returns:
            The current project ID or None if not set.
        """
        ctx = _project_context.get()
        return ctx.project_id if ctx else None

    @staticmethod
    def get_project_slug() -> Optional[str]:
        """
        Get the current project slug.

        Returns:
            The current project slug or None if not set.
        """
        ctx = _project_context.get()
        return ctx.project_slug if ctx else None

    @staticmethod
    def get_project_path() -> Optional[str]:
        """
        Get the current project path.

        Returns:
            The current project path or None if not set.
        """
        ctx = _project_context.get()
        return ctx.project_path if ctx else None

    @staticmethod
    def get_context() -> Optional[ProjectContextData]:
        """
        Get the full project context data.

        Returns:
            The current project context or None if not set.
        """
        return _project_context.get()

    @staticmethod
    def is_set() -> bool:
        """
        Check if a project context is currently set.

        Returns:
            True if a project context is set, False otherwise.
        """
        return _project_context.get() is not None

    @staticmethod
    @contextmanager
    def set_project(
        project_id: str,
        project_slug: str = None,
        project_path: str = None
    ) -> ContextManager[ProjectContextData]:
        """
        Set the active project context.

        This context manager sets the active project for all operations
        within its scope. The context is automatically cleared when
        exiting the scope.

        Args:
            project_id: The project ID (UUID).
            project_slug: The project slug (optional).
            project_path: The project path (optional).

        Yields:
            The project context data.

        Example:
            with project_context.set_project("uuid-123", "my-project"):
                # All operations here are scoped to this project
                plans = plan_repo.list_all()
        """
        ctx = ProjectContextData(
            project_id=project_id,
            project_slug=project_slug or "",
            project_path=project_path or ""
        )
        token = _project_context.set(ctx)
        logger.debug(f"Set project context: {project_id}")
        try:
            yield ctx
        finally:
            _project_context.reset(token)
            logger.debug(f"Cleared project context: {project_id}")

    @staticmethod
    def set_project_sync(
        project_id: str,
        project_slug: str = None,
        project_path: str = None
    ) -> contextvars.Token:
        """
        Set the active project context without a context manager.

        Use this when you need to set the context outside of a with block.
        Remember to call reset_project() with the returned token.

        Args:
            project_id: The project ID (UUID).
            project_slug: The project slug (optional).
            project_path: The project path (optional).

        Returns:
            A token that can be used to reset the context.
        """
        ctx = ProjectContextData(
            project_id=project_id,
            project_slug=project_slug or "",
            project_path=project_path or ""
        )
        token = _project_context.set(ctx)
        logger.debug(f"Set project context (sync): {project_id}")
        return token

    @staticmethod
    def reset_project(token: contextvars.Token) -> None:
        """
        Reset the project context using a token.

        Args:
            token: The token returned from set_project_sync().
        """
        _project_context.reset(token)
        logger.debug("Reset project context")

    @staticmethod
    def clear() -> None:
        """
        Clear the current project context.

        This is equivalent to setting the context to None.
        """
        _project_context.set(None)
        logger.debug("Cleared project context")


# Singleton instance
project_context = ProjectContextManager()


def require_project_context() -> str:
    """
    Get the current project ID, raising if not set.

    Returns:
        The current project ID.

    Raises:
        ProjectContextError: If no project context is set.
    """
    project_id = project_context.get_project_id()
    if not project_id:
        raise ProjectContextError(
            "No project context set. "
            "Use 'orch project switch <name>' to select a project."
        )
    return project_id


def get_optional_project_id() -> Optional[str]:
    """
    Get the current project ID or None.

    Returns:
        The current project ID or None if not set.
    """
    return project_context.get_project_id()


def with_project_context(project_id: str, project_slug: str = None, project_path: str = None):
    """
    Decorator to run a function with a specific project context.

    Args:
        project_id: The project ID to use.
        project_slug: The project slug (optional).
        project_path: The project path (optional).

    Example:
        @with_project_context("uuid-123")
        def my_function():
            # Operations here are scoped to the project
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with project_context.set_project(project_id, project_slug, project_path):
                return func(*args, **kwargs)
        return wrapper
    return decorator


async def with_project_context_async(project_id: str, project_slug: str = None, project_path: str = None):
    """
    Async decorator to run an async function with a specific project context.

    Args:
        project_id: The project ID to use.
        project_slug: The project slug (optional).
        project_path: The project path (optional).

    Example:
        @with_project_context_async("uuid-123")
        async def my_async_function():
            # Operations here are scoped to the project
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with project_context.set_project(project_id, project_slug, project_path):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


class IProjectContextProvider:
    """Interface for getting current project context.

    This abstraction allows different implementations for getting the
    current project ID, enabling dependency injection and testability.
    """

    def get_project_id(self) -> Optional[str]:
        """Get the current project ID.

        Returns:
            The current project ID or None if not set.
        """
        raise NotImplementedError

    def require_project_id(self) -> str:
        """Get the current project ID, raising if not set.

        Returns:
            The current project ID.

        Raises:
            ProjectContextError: If no project context is available.
        """
        raise NotImplementedError


class ContextVarProjectProvider(IProjectContextProvider):
    """Gets project ID from contextvar only (set by middleware).

    This provider only reads from the contextvar and does not
    fall back to the registry. Use this when you want strict
    context enforcement.
    """

    def get_project_id(self) -> Optional[str]:
        """Get project ID from contextvar only."""
        return project_context.get_project_id()

    def require_project_id(self) -> str:
        """Get project ID from contextvar, raising if not set."""
        project_id = self.get_project_id()
        if not project_id:
            raise ProjectContextError(
                "No project context set. "
                "Use 'orch project switch <name>' to select a project."
            )
        return project_id


class DatabaseProjectProvider(IProjectContextProvider):
    """Gets project ID from contextvar, falls back to DATABASE.

    This provider first checks the contextvar (set by middleware),
    and if not set, falls back to the active project from the database.
    This is the standard provider - database is the single source of truth.
    """

    def get_project_id(self) -> Optional[str]:
        """Get project ID from contextvar, falling back to database."""
        # First try contextvar (set by middleware)
        project_id = project_context.get_project_id()
        if project_id:
            return project_id

        # Fallback to active project from DATABASE (not registry)
        try:
            from db.repositories.project import get_project_repository
            repo = get_project_repository()
            active = repo.get_active(as_dict=True)
            if active:
                logger.debug(f"Using database fallback: {active['id']}")
                return active['id']
        except Exception as e:
            logger.warning(f"Database fallback failed: {e}")

        return None

    def require_project_id(self) -> str:
        """Get project ID with database fallback, raising if not available."""
        project_id = self.get_project_id()
        if not project_id:
            raise ProjectContextError(
                "No project context available. "
                "Set X-Project-ID header or switch to an active project."
            )
        return project_id


class RegistryFallbackProjectProvider(IProjectContextProvider):
    """DEPRECATED: Use DatabaseProjectProvider instead.

    This class is kept for backward compatibility but now delegates
    to DatabaseProjectProvider internally. The database is the
    single source of truth - no registry file is used.
    """

    def __init__(self):
        self._delegate = DatabaseProjectProvider()
        logger.debug("RegistryFallbackProjectProvider is deprecated, using DatabaseProjectProvider")

    def get_project_id(self) -> Optional[str]:
        """Get project ID (delegates to DatabaseProjectProvider)."""
        return self._delegate.get_project_id()

    def require_project_id(self) -> str:
        """Get project ID, raising if not available (delegates to DatabaseProjectProvider)."""
        return self._delegate.require_project_id()


def get_project_id_for_query() -> Optional[str]:
    """
    Get project ID for database queries with fallback to database.

    This is the standard way for repositories to get the current project ID.
    Returns None only if multi-project mode is disabled or no project is active.

    Returns:
        Project ID string or None.
    """
    # Use the DatabaseProjectProvider - database is single source of truth
    provider = DatabaseProjectProvider()
    project_id = provider.get_project_id()

    # Log warning if in multi-project mode but no context
    if not project_id:
        try:
            from config import get_config
            config = get_config()
            if config.is_multi_project_mode:
                logger.warning("Multi-project mode enabled but no project context available")
        except Exception:
            pass

    return project_id
