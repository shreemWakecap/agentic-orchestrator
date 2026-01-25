"""
Project Context Middleware for FastAPI.

This middleware automatically sets the project context for requests
based on the X-Project-ID header or query parameter.

SOLID Revamp Architecture Notes:
--------------------------------
The middleware provides TWO modes of operation:

1. STRICT MODE (auto_set_active=False):
   - Only extracts project ID from request headers/params
   - Does NOT access the registry
   - Routes must use IProjectContextProvider for fallback logic
   - Recommended for API clients that always specify project

2. CONVENIENCE MODE (auto_set_active=True, default):
   - Falls back to registry's active project if no header/param
   - Provides good UX for the portal UI
   - Routes can still override with IProjectContextProvider

The registry fallback in middleware is convenient but technically
redundant with RegistryFallbackProjectProvider. Keep it for UX.

Usage:
    app = FastAPI()
    app.add_middleware(ProjectContextMiddleware)

    # Strict mode (no registry access):
    app.add_middleware(ProjectContextMiddleware, auto_set_active=False)
"""
import logging
from typing import Optional, Callable, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Header and query parameter names
PROJECT_ID_HEADER = "X-Project-ID"
PROJECT_SLUG_HEADER = "X-Project-Slug"
PROJECT_ID_QUERY = "project_id"


class ProjectContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sets project context from request headers/params.

    The project context is set from (in priority order):
    1. X-Project-ID header
    2. project_id query parameter
    3. Active project from registry (if auto_set_active=True)

    SOLID Notes:
    - The registry fallback (step 3) is optional via auto_set_active flag
    - Routes can override by using IProjectContextProvider from dependencies.py
    - Context is automatically cleared after request completes
    """

    def __init__(self, app, auto_set_active: bool = True):
        """
        Initialize middleware.

        Args:
            app: The ASGI application.
            auto_set_active: If True (default), falls back to active project
                           from registry when no header/param specified.
                           Set to False for strict mode (no registry access).
        """
        super().__init__(app)
        self.auto_set_active = auto_set_active

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with project context."""
        from config import get_config

        config = get_config()

        # Skip if not in multi-project mode
        if not config.is_multi_project_mode:
            return await call_next(request)

        # Get project ID from request
        project_id = self._get_project_id(request)
        project_slug = request.headers.get(PROJECT_SLUG_HEADER)

        # If no project specified and auto_set_active is True, use active project
        if not project_id and self.auto_set_active:
            project_id, project_slug = self._get_active_project()

        # Set project context if we have a project ID
        if project_id:
            from db.project_context import project_context

            token = project_context.set_project_sync(project_id, project_slug)
            try:
                response = await call_next(request)
            finally:
                project_context.reset_project(token)
        else:
            response = await call_next(request)

        return response

    def _get_project_id(self, request: Request) -> Optional[str]:
        """Extract project ID from request."""
        # Try header first
        project_id = request.headers.get(PROJECT_ID_HEADER)
        if project_id:
            return project_id

        # Try query parameter
        project_id = request.query_params.get(PROJECT_ID_QUERY)
        if project_id:
            return project_id

        return None

    def _get_active_project(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the active project from database.

        SOLID Note:
        This method is only called when auto_set_active=True and no
        project ID is provided in the request. It provides a fallback
        for convenience (especially for the portal UI).

        Routes can always override this by using IProjectContextProvider
        from dependencies.py, which has its own fallback logic.

        The database is the single source of truth for project data.
        """
        try:
            from db.repositories.project import get_project_repository

            repo = get_project_repository()
            active = repo.get_active(as_dict=True)
            if active:
                logger.debug(f"Middleware using active project: {active['id']}")
                return active['id'], active['slug']
        except Exception as e:
            logger.debug(f"Could not get active project: {e}")

        return None, None


def get_project_context_dependency():
    """
    FastAPI dependency that provides the current project context.

    Usage:
        @router.get("/")
        async def my_route(project_id: str = Depends(get_project_context_dependency)):
            ...
    """
    from db.project_context import get_optional_project_id
    return get_optional_project_id()


def require_project_context_dependency():
    """
    FastAPI dependency that requires a project context.

    Raises HTTPException if no project context is set.

    Usage:
        @router.get("/")
        async def my_route(project_id: str = Depends(require_project_context_dependency)):
            ...
    """
    from fastapi import HTTPException
    from db.project_context import get_optional_project_id

    project_id = get_optional_project_id()
    if not project_id:
        raise HTTPException(
            status_code=400,
            detail="No project context. Use X-Project-ID header or switch to a project."
        )
    return project_id
