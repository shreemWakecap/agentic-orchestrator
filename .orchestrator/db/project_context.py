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
        return ctx.slug if ctx else None

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
