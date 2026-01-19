"""
Orchestrator Portal Package

Async job management portal for the SDLC Orchestrator.

This package provides:
- REST API for job management
- Real-time event streaming via SSE
- Worker pool for bounded concurrency
- Checkpoint-based job recovery
- Full lifecycle management

Quick Start:
    # Run the server
    python -m portal.main

    # Or with uvicorn
    uvicorn portal.main:app --reload

    # Access API docs at http://localhost:8000/api/docs
"""
from .config import config, Config, get_config, reload_config
from .lifecycle import (
    LifecycleManager,
    get_lifecycle_manager,
    set_lifecycle_manager,
    lifespan_context,
)

__version__ = "1.0.0"

__all__ = [
    # Version
    "__version__",
    # Configuration
    "config",
    "Config",
    "get_config",
    "reload_config",
    # Lifecycle
    "LifecycleManager",
    "get_lifecycle_manager",
    "set_lifecycle_manager",
    "lifespan_context",
]


def get_app():
    """
    Get the FastAPI application instance.

    Lazy import to avoid circular dependencies.
    """
    from .main import app
    return app
