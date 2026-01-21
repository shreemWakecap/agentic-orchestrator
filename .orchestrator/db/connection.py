"""
PostgreSQL Database Connection using SQLAlchemy ORM.
"""
import json
import logging
import threading
from contextlib import contextmanager
from typing import Any, Generator, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import DatabaseConfig
from .models import Base

logger = logging.getLogger(__name__)


def _convert_query(query: str, params: tuple) -> tuple:
    """Convert ? placeholders to :param style for SQLAlchemy.

    Args:
        query: SQL query with ? placeholders
        params: Query parameters as tuple

    Returns:
        Tuple of (converted_query, params_dict)
    """
    converted_query = query
    params_dict = {}

    for i, param in enumerate(params):
        placeholder = f":p{i}"
        converted_query = converted_query.replace("?", placeholder, 1)
        params_dict[f"p{i}"] = param

    return converted_query, params_dict


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

    # =========================================================================
    # Raw SQL query methods (for repositories that use raw SQL)
    # =========================================================================

    @contextmanager
    def transaction(self):
        """Context manager for raw SQL transactions.

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...", (param1, param2))
        """
        with Database._engine.connect() as conn:
            trans = conn.begin()
            try:
                yield _ConnectionWrapper(conn)
                trans.commit()
            except Exception:
                trans.rollback()
                raise

    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and return single row as dict.

        Args:
            query: SQL query with ? placeholders
            params: Query parameters

        Returns:
            Row as dict or None if no results
        """
        converted_query, converted_params = _convert_query(query, params)

        with Database._engine.connect() as conn:
            result = conn.execute(text(converted_query), converted_params)
            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return None

    def fetchall(self, query: str, params: tuple = ()) -> List[dict]:
        """Execute query and return all rows as dicts.

        Args:
            query: SQL query with ? placeholders
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        converted_query, converted_params = _convert_query(query, params)

        with Database._engine.connect() as conn:
            result = conn.execute(text(converted_query), converted_params)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    # =========================================================================
    # JSON serialization helpers
    # =========================================================================

    @staticmethod
    def to_json(value: Any) -> str:
        """Convert Python object to JSON string."""
        return json.dumps(value)

    @staticmethod
    def from_json(value: Optional[str], default: Any = None) -> Any:
        """Parse JSON string to Python object."""
        if value is None:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default


class _ConnectionWrapper:
    """Wrapper around SQLAlchemy connection to handle ? placeholder conversion."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query: str, params: tuple = ()):
        """Execute a SQL query with ? placeholders.

        Args:
            query: SQL query with ? placeholders
            params: Query parameters as tuple

        Returns:
            Result proxy with lastrowid and rowcount attributes
        """
        converted_query, converted_params = _convert_query(query, params)
        result = self._conn.execute(text(converted_query), converted_params)
        return _ResultWrapper(result)


class _ResultWrapper:
    """Wrapper around SQLAlchemy result to provide lastrowid."""

    def __init__(self, result):
        self._result = result
        self.rowcount = result.rowcount
        # Cache lastrowid immediately after execution
        self._lastrowid = None
        try:
            if hasattr(result, 'lastrowid'):
                self._lastrowid = result.lastrowid
        except Exception:
            pass

    @property
    def lastrowid(self):
        """Get the last inserted row ID.

        Note: For PostgreSQL with raw SQL, this may return None or 0.
        Use RETURNING clause in INSERT statements for reliable ID retrieval.
        """
        return self._lastrowid or 0

    def fetchone(self):
        """Fetch one row as dict."""
        row = self._result.fetchone()
        if row:
            return dict(row._mapping)
        return None

    def fetchall(self):
        """Fetch all rows as dicts."""
        rows = self._result.fetchall()
        return [dict(row._mapping) for row in rows]
