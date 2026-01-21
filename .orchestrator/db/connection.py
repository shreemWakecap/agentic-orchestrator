"""
PostgreSQL Database Connection using SQLAlchemy ORM.
"""
import logging
import threading
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import DatabaseConfig
from .models import Base

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database manager using SQLAlchemy ORM."""

    _engine = None
    _session_factory = None
    _lock = threading.Lock()
    _initialized = False

    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig.load()

        with self._lock:
            if not Database._initialized:
                self._init_engine()
                Base.metadata.create_all(Database._engine)
                Database._initialized = True

    def _init_engine(self):
        """Initialize SQLAlchemy engine."""
        if Database._engine is None:
            Database._engine = create_engine(
                self.config.connection_string,
                poolclass=QueuePool,
                pool_size=self.config.pool_min,
                max_overflow=self.config.pool_max - self.config.pool_min,
                pool_pre_ping=True,
            )
            Database._session_factory = sessionmaker(bind=Database._engine)
            logger.info(f"Database connected to {self.config.host}:{self.config.port}/{self.config.name}")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session."""
        session = Database._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self):
        """Close the database connection."""
        with self._lock:
            if Database._engine:
                Database._engine.dispose()
                Database._engine = None
                Database._session_factory = None
                Database._initialized = False

    @classmethod
    def reset(cls):
        """Reset database state."""
        with cls._lock:
            if cls._engine:
                cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            cls._initialized = False
