"""Health check routes."""
from datetime import datetime
from fastapi import APIRouter

from portal.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])

# Portal startup time for uptime calculation
START_TIME = datetime.now()

# Version (will be set from app)
VERSION = "1.0.0"


def set_version(version: str):
    """Set the version string from main app."""
    global VERSION
    VERSION = version


@router.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint returning server status, version, and uptime."""
    uptime_seconds = (datetime.now() - START_TIME).total_seconds()
    return HealthResponse(
        status="healthy",
        version=VERSION,
        uptime_seconds=round(uptime_seconds, 2),
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Simple health check endpoint at root level."""
    uptime_seconds = (datetime.now() - START_TIME).total_seconds()
    return HealthResponse(
        status="ok",
        version=VERSION,
        uptime_seconds=round(uptime_seconds, 2),
    )


@router.get("/api/hello")
async def api_hello():
    """Return a simple hello world message for testing."""
    return {"message": "hello world"}


@router.get("/hello")
async def hello():
    """Return a simple Hello World message."""
    return {"message": "Hello World"}
