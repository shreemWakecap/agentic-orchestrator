"""
FastAPI Application Entry Point

Sets up the application with proper lifecycle management:
- Database initialization
- Worker pool startup/shutdown
- Orphan recovery
- Event collector management
- SSE manager lifecycle

All configuration is loaded from environment variables via config.py.
"""
import sys
import signal
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from .config import config
from .lifecycle import lifespan_context
from .api import jobs_router

# Configure logging
logging.basicConfig(
    level=config.server.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Orchestrator Portal...")
    logger.info(f"Configuration: max_workers={config.worker.max_workers}, "
                f"database={config.database.url}")

    async with lifespan_context(
        max_workers=config.worker.max_workers,
        graceful_timeout=config.worker.graceful_timeout,
    ):
        logger.info("Orchestrator Portal started successfully")
        yield

    logger.info("Orchestrator Portal shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Orchestrator Portal",
    description="SDLC Orchestrator Web Portal - Async Job Management System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs_router)

# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# =============================================================================
# Health and Readiness Endpoints
# =============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the overall health status of the service including
    worker pool status. Suitable for load balancer health checks.
    """
    from .services import get_worker_pool
    from .lifecycle import get_lifecycle_manager

    lifecycle = get_lifecycle_manager()
    pool = get_worker_pool()

    pool_info = {}
    if pool:
        status = pool.get_status()
        pool_info = {
            "running": status.get("running", False),
            "active_workers": status.get("active_workers", 0),
            "queue_size": status.get("queue_size", 0),
        }
    else:
        pool_info = {"running": False}

    return {
        "status": "healthy",
        "version": "1.0.0",
        "started": lifecycle.is_started if lifecycle else False,
        "worker_pool": pool_info,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint.

    Indicates if the service can accept requests.
    Returns 200 if ready, or 503 with details about why not ready.
    Suitable for Kubernetes readiness probes.
    """
    from .services import get_worker_pool
    from .lifecycle import get_lifecycle_manager

    lifecycle = get_lifecycle_manager()

    if not lifecycle or not lifecycle.is_started:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Application not fully started"
            }
        )

    if lifecycle.is_shutting_down:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Application is shutting down"
            }
        )

    pool = get_worker_pool()
    if not pool or not pool.is_running:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Worker pool not running"
            }
        )

    return {"status": "ready"}


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to API documentation."""
    return RedirectResponse(url="/api/docs")


@app.get("/api", tags=["Root"])
async def api_info():
    """API information endpoint."""
    return {
        "service": "Orchestrator Portal",
        "version": "1.0.0",
        "documentation": "/api/docs",
        "health": "/health",
        "ready": "/ready",
        "jobs_endpoint": "/api/jobs",
    }


@app.get("/config", tags=["Admin"])
async def get_config_info():
    """
    Get current configuration (non-sensitive values).

    Useful for debugging and verifying configuration.
    """
    return {
        "worker": {
            "max_workers": config.worker.max_workers,
            "max_queue_size": config.worker.max_queue_size,
            "default_timeout": config.worker.default_timeout,
        },
        "streaming": {
            "max_connections_per_job": config.streaming.max_connections_per_job,
            "heartbeat_interval": config.streaming.heartbeat_interval,
            "buffer_size": config.streaming.buffer_size,
        },
        "server": {
            "host": config.server.host,
            "port": config.server.port,
            "log_level": config.server.log_level,
        },
    }


# =============================================================================
# Signal Handlers for Graceful Shutdown
# =============================================================================

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""

    def handle_signal(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating shutdown...")
        # The lifespan context manager will handle cleanup
        sys.exit(0)

    # Handle SIGTERM (docker stop, kubernetes termination)
    signal.signal(signal.SIGTERM, handle_signal)
    # Handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, handle_signal)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    setup_signal_handlers()

    uvicorn.run(
        "portal.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.reload,
        log_level=config.server.log_level.lower(),
    )
