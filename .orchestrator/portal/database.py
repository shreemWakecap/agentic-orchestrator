"""
Database initialization and lifecycle management.
"""
import logging
from contextlib import asynccontextmanager

from .models import init_db, close_db

logger = logging.getLogger(__name__)


async def setup_database():
    """Initialize database on application startup."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully")


async def teardown_database():
    """Clean up database connections on shutdown."""
    logger.info("Closing database connections...")
    await close_db()
    logger.info("Database connections closed")


@asynccontextmanager
async def database_lifespan():
    """Context manager for database lifecycle."""
    await setup_database()
    try:
        yield
    finally:
        await teardown_database()
