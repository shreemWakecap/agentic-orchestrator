"""Thread context management for background workflows.

This module provides utilities for managing project context in background
threads where contextvars don't automatically propagate.

SOLID Revamp:
- Extracted from workflow_runner.py for reusability
- Provides clean context manager for project context in threads
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ThreadContextManager:
    """Context manager for project context in background threads.

    Handles setting and resetting project context when executing
    workflows in background threads where contextvars don't propagate.

    Usage:
        with ThreadContextManager(project_id):
            # Code here runs with project context set
            run_workflow()
        # Context is automatically reset after the block
    """

    def __init__(self, project_id: Optional[str] = None):
        """Initialize the thread context manager.

        Args:
            project_id: Optional project ID to set as context.
                       If None, no context is set.
        """
        self.project_id = project_id
        self._token = None

    def __enter__(self):
        """Set project context on entry."""
        if self.project_id:
            from db.project_context import project_context
            self._token = project_context.set_project_sync(self.project_id)
            logger.debug(f"Set thread project context: {self.project_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset project context on exit."""
        if self._token:
            from db.project_context import project_context
            project_context.reset_project(self._token)
            logger.debug(f"Reset thread project context: {self.project_id}")
        return False  # Don't suppress exceptions


def run_with_project_context(project_id: Optional[str], func, *args, **kwargs):
    """Run a function with project context set.

    Convenience function for running code with project context
    without using the context manager directly.

    Args:
        project_id: Project ID to set as context
        func: Function to call
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The return value of func
    """
    with ThreadContextManager(project_id):
        return func(*args, **kwargs)
