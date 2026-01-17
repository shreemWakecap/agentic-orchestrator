"""Route modules for the portal API.

Each module defines an APIRouter with related endpoints.
These are registered in app.py.
"""
from .plans import router as plans_router
from .runs import router as runs_router
from .workflows import router as workflows_router
from .cost import router as cost_router
from .pages import router as pages_router
from .health import router as health_router
from .knowledge import router as knowledge_router

__all__ = [
    "plans_router",
    "runs_router",
    "workflows_router",
    "cost_router",
    "pages_router",
    "health_router",
    "knowledge_router",
]
