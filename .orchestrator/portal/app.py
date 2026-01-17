"""Web Portal for Agentic Orchestrator.

Provides a browser-based dashboard for:
- Viewing and managing plans
- Running workflows (plan, build, sync)
- Real-time progress streaming via SSE
- Historical run tracking

This module sets up the FastAPI application and registers all route modules.
Business logic has been extracted to services/ and routes to routes/.
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Add parent directory to path for imports
PORTAL_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent

sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import routers
from portal.routes import (
    plans_router,
    runs_router,
    workflows_router,
    cost_router,
    pages_router,
    health_router,
    knowledge_router,
)
from portal.routes.health import set_version
from portal.exception_handlers import register_exception_handlers

# FastAPI app
app = FastAPI(
    title="Agentic Orchestrator Portal",
    description="Web portal for managing planning and building workflows",
    version="1.0.0",
)

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


def run_portal(host: str = "127.0.0.1", port: int = 8000):
    """Run the web portal."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


# Alias for backward compatibility
run_server = run_portal


if __name__ == "__main__":
    run_server()
