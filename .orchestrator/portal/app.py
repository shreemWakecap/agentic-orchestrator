"""Web Portal for Agentic Orchestrator.

Provides a browser-based dashboard for:
- Viewing and managing plans
- Running workflows (plan, build, sync)
- Real-time progress streaming via SSE
- Historical run tracking

This module sets up the FastAPI application and registers all route modules.
Business logic has been extracted to services/ and routes to routes/.
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add parent directory to path for imports
PORTAL_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Note: dotenv is loaded automatically by the unified config module

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

# Import routers
from portal.routes import (
    plans_router,
    runs_router,
    workflows_router,
    cost_router,
    pages_router,
    health_router,
    knowledge_router,
    background_tasks_router,
    websocket_router,
    file_knowledge_router,
    tasks_router,
    chat_router,
    token_analytics_router,
)
from portal.routes.health import set_version
from portal.exception_handlers import register_exception_handlers
from portal.services.task_manager import (
    TaskManager,
    get_task_manager,
    shutdown_task_manager,
)
from portal.services.auto_recovery import (
    start_auto_recovery,
    stop_auto_recovery,
)
from portal.streaming.websocket import (
    init_websocket_manager,
    shutdown_websocket_manager,
)
from portal.models import init_db, close_db

logger = logging.getLogger(__name__)

# Global TaskManager instance for the application
_task_manager: TaskManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events.

    Initializes the database, TaskManager and auto-recovery task on startup,
    and gracefully shuts them down when the application stops.
    """
    global _task_manager

    # Startup: Initialize database (creates tables if they don't exist)
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")

    # Startup: Initialize TaskManager
    logger.info("Starting TaskManager...")
    _task_manager = get_task_manager(max_workers=4)
    logger.info("TaskManager initialized successfully")

    # Startup: Start auto-recovery background task
    # Checks for stale builds every 5 minutes (300 seconds)
    logger.info("Starting auto-recovery task...")
    await start_auto_recovery(
        check_interval=300,  # 5 minutes
        stale_threshold_minutes=15,
        auto_pause=True,
    )
    logger.info("Auto-recovery task started successfully")

    # Startup: Initialize WebSocket manager for real-time updates
    logger.info("Starting WebSocket manager...")
    await init_websocket_manager()
    logger.info("WebSocket manager started successfully")

    yield

    # Shutdown: Stop WebSocket manager
    logger.info("Stopping WebSocket manager...")
    await shutdown_websocket_manager()
    logger.info("WebSocket manager stopped")

    # Shutdown: Stop auto-recovery task
    logger.info("Stopping auto-recovery task...")
    await stop_auto_recovery()
    logger.info("Auto-recovery task stopped")

    # Shutdown: Gracefully close TaskManager
    logger.info("Shutting down TaskManager...")
    shutdown_task_manager(wait=True)
    _task_manager = None
    logger.info("TaskManager shutdown complete")

    # Shutdown: Close database connections
    logger.info("Closing database connections...")
    await close_db()
    logger.info("Database connections closed")


# FastAPI app
app = FastAPI(
    title="Agentic Orchestrator Portal",
    description="Web portal for managing planning and building workflows",
    version="1.0.0",
    lifespan=lifespan,
)


def get_task_manager_dependency() -> TaskManager:
    """FastAPI dependency to get the TaskManager instance.

    Returns:
        The application's TaskManager instance

    Raises:
        RuntimeError: If TaskManager hasn't been initialized
    """
    if _task_manager is None:
        raise RuntimeError("TaskManager not initialized - application not started properly")
    return _task_manager

# Set version in health module
set_version(app.version)

# Register exception handlers
register_exception_handlers(app)

# Setup static files
STATIC_DIR = PORTAL_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Register routers
app.include_router(health_router)
app.include_router(plans_router)
app.include_router(runs_router)
app.include_router(workflows_router)
app.include_router(cost_router)
app.include_router(pages_router)
app.include_router(knowledge_router)
app.include_router(background_tasks_router)
app.include_router(websocket_router)
app.include_router(file_knowledge_router)
app.include_router(tasks_router)
app.include_router(chat_router)
app.include_router(token_analytics_router)


def run_portal(host: str = "127.0.0.1", port: int = 8000):
    """Run the web portal."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


# Alias for backward compatibility
run_server = run_portal


if __name__ == "__main__":
    run_server()
