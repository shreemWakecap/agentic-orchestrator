"""
Database base configuration and engine setup for async operations.

This module provides the async SQLAlchemy engine and session factory
for the portal's job management system.

Uses the unified config module for database settings.
"""
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Ensure orchestrator directory is in path for unified config
PORTAL_DIR = Path(__file__).parent.parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import from unified config (this also loads dotenv)
from config import get_database_config

# Naming convention for constraints (helps with migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all portal models."""
    metadata = metadata


def _create_engine():
    """Create async engine using unified config."""
    db_config = get_database_config()
    return create_async_engine(
        db_config.async_url,
        echo=db_config.echo,
        pool_size=db_config.pool_min,
        max_overflow=db_config.pool_max - db_config.pool_min,
        pool_recycle=db_config.pool_recycle,
        pool_pre_ping=True,
        future=True
    )


# Create async engine (lazy initialization)
_engine = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


# For backward compatibility, expose engine as module variable
# but use lazy initialization
@property
def engine():
    return get_engine()


# Session factory (lazy initialization)
_session_maker = None


def get_session_maker():
    """Get or create the session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _session_maker


# Backward compatibility alias
async_session_maker = property(lambda self: get_session_maker())


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database sessions.

    Usage with FastAPI:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """
    Initialize database tables.

    In production, use Alembic migrations instead.
    This is mainly for development/testing.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None


def utcnow() -> datetime:
    """Get current UTC timestamp."""
    return datetime.utcnow()


# Backward compatibility: expose engine at module level
# Use get_engine() for explicit access
engine = get_engine()
async_session_maker = get_session_maker()

# Backward compatibility: expose DATABASE_URL
# New code should use get_database_config().async_url instead
DATABASE_URL = get_database_config().async_url
