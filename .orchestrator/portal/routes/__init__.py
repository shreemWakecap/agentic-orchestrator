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
from .background_tasks import router as background_tasks_router
from .websocket import router as websocket_router
from .file_knowledge import router as file_knowledge_router
from .tasks import router as tasks_router
from .chat import router as chat_router
from .token_analytics import router as token_analytics_router
from .experts import router as experts_router
from .projects import router as projects_router
from .agent_definitions import router as agent_definitions_router
from .expert_definitions import router as expert_definitions_router
from .orchestrator_config import router as orchestrator_config_router

__all__ = [
    "plans_router",
    "runs_router",
    "workflows_router",
    "cost_router",
    "pages_router",
    "health_router",
    "knowledge_router",
    "background_tasks_router",
    "websocket_router",
    "file_knowledge_router",
    "tasks_router",
    "chat_router",
    "token_analytics_router",
    "experts_router",
    "projects_router",
    "agent_definitions_router",
    "expert_definitions_router",
    "orchestrator_config_router",
]
