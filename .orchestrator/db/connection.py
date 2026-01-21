"""
PostgreSQL Database Connection using SQLAlchemy ORM.

This module provides the database connection layer for synchronous operations.
For async operations, use portal.models.base.

The connection uses the unified config module for database settings.
"""
import json
import logging
import sys
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Ensure orchestrator directory is in path
ORCHESTRATOR_DIR = Path(__file__).parent.parent
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import from unified config (this also loads dotenv)
from config import get_database_config

from .models import Base

logger = logging.getLogger(__name__)


def _convert_query(query: str, params: tuple) -> tuple:
    """
    Convert ? placeholders to :param style for SQLAlchemy.

    This maintains backward compatibility with repositories that use
    SQLite-style ? placeholders.

    Args:
        query: SQL query with ? placeholders
        params: Query parameters as tuple

    Returns:
        Tuple of (converted_query, params_dict)

    Note:
        New code should use named parameters directly instead of ?.
    """
    converted_query = query
    params_dict = {}

    for i, param in enumerate(params):
        placeholder = f":p{i}"
        converted_query = converted_query.replace("?", placeholder, 1)
        params_dict[f"p{i}"] = param

    return converted_query, params_dict


def _serialize_value(value: Any) -> Any:
    """
    Serialize a value for JSON compatibility.

    Converts datetime objects to ISO format strings.
    This is needed because PostgreSQL returns datetime objects
    but our Pydantic models expect strings.

    Args:
        value: Any value from a database row

    Returns:
        JSON-serializable value
    """
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _convert_row_to_dict(row_mapping) -> dict:
    """
    Convert a row mapping to dict with proper serialization.

    Args:
        row_mapping: SQLAlchemy row mapping

    Returns:
        Dict with datetime values converted to ISO strings
    """
    return {key: _serialize_value(value) for key, value in row_mapping.items()}


class Database:
    """
    PostgreSQL database manager using SQLAlchemy ORM.

    This is a singleton class that manages the database connection pool.
    It provides both ORM session access and raw SQL query methods for
    backward compatibility with existing repositories.

    Usage:
        db = Database()

        # ORM usage
        with db.session() as session:
            plan = session.query(Plan).filter_by(plan_id="...").first()

        # Raw SQL usage (for existing repositories)
        row = db.fetchone("SELECT * FROM plans WHERE plan_id = ?", ("...",))
    """

    _engine = None
    _session_factory = None
    _lock = threading.Lock()
    _initialized = False

    def __init__(self):
        """Initialize database connection using unified config."""
        with self._lock:
            if not Database._initialized:
                self._init_engine()
                # Auto-create tables (for development)
                # In production, use Alembic migrations instead
                Base.metadata.create_all(Database._engine)
                Database._initialized = True

    def _init_engine(self):
        """Initialize SQLAlchemy engine from unified config."""
        if Database._engine is None:
            db_config = get_database_config()

            Database._engine = create_engine(
                db_config.sync_url,
                poolclass=QueuePool,
                pool_size=db_config.pool_min,
                max_overflow=db_config.pool_max - db_config.pool_min,
                pool_pre_ping=True,
                pool_recycle=db_config.pool_recycle,
                echo=db_config.echo,
            )
            Database._session_factory = sessionmaker(bind=Database._engine)
            logger.info(f"Database connected to {db_config.host}:{db_config.port}/{db_config.name}")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic commit/rollback.

        Usage:
            with db.session() as session:
                plan = Plan(plan_id="...", goal="...")
                session.add(plan)
                # Auto-commits on exit, rollbacks on exception
        """
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
        """Close the database connection pool."""
        with self._lock:
            if Database._engine:
                Database._engine.dispose()
                Database._engine = None
                Database._session_factory = None
                Database._initialized = False

    @classmethod
    def reset(cls):
        """Reset database state (useful for testing)."""
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
        """
        Context manager for raw SQL transactions.

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO plans ...", (param1, param2))
                conn.execute("UPDATE plans ...", (param3,))
                # Auto-commits on exit, rollbacks on exception
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
        """
        Execute query and return single row as dict.

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
                return _convert_row_to_dict(row._mapping)
            return None

    def fetchall(self, query: str, params: tuple = ()) -> List[dict]:
        """
        Execute query and return all rows as dicts.

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
            return [_convert_row_to_dict(row._mapping) for row in rows]

    # =========================================================================
    # JSON serialization helpers
    # =========================================================================

    @staticmethod
    def to_json(value: Any) -> str:
        """Convert Python object to JSON string for storage."""
        return json.dumps(value)

    @staticmethod
    def from_json(value: Optional[str], default: Any = None) -> Any:
        """Parse JSON string from storage to Python object."""
        if value is None:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default


class _ConnectionWrapper:
    """
    Wrapper around SQLAlchemy connection for raw SQL with ? placeholders.

    This provides backward compatibility with repositories that use
    SQLite-style ? placeholder syntax.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query: str, params: tuple = ()):
        """
        Execute a SQL query with ? placeholders.

        Args:
            query: SQL query with ? placeholders
            params: Query parameters as tuple

        Returns:
            Result wrapper with lastrowid and rowcount attributes
        """
        converted_query, converted_params = _convert_query(query, params)
        result = self._conn.execute(text(converted_query), converted_params)
        return _ResultWrapper(result)


class _ResultWrapper:
    """
    Wrapper around SQLAlchemy result for compatibility.

    Provides lastrowid and rowcount attributes similar to sqlite3.
    """

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
        """
        Get the last inserted row ID.

        Note: For PostgreSQL with raw SQL, this may return None or 0.
        Use RETURNING clause in INSERT statements for reliable ID retrieval.
        """
        return self._lastrowid or 0

    def fetchone(self):
        """Fetch one row as dict."""
        row = self._result.fetchone()
        if row:
            return _convert_row_to_dict(row._mapping)
        return None

    def fetchall(self):
        """Fetch all rows as dicts."""
        rows = self._result.fetchall()
        return [_convert_row_to_dict(row._mapping) for row in rows]


# =============================================================================
# Backward Compatibility
# =============================================================================

# Import DatabaseConfig for backward compatibility with existing code
from .config import DatabaseConfig

__all__ = ['Database', 'DatabaseConfig']
