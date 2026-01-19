"""
Database Connection Manager.

Thread-safe SQLite database connection with configurable settings.
All database files are stored in the db/ folder.
"""
import json
import sqlite3
import threading
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Generator

from .config import DatabaseConfig

logger = logging.getLogger(__name__)


class Database:
    """
    Thread-safe SQLite database manager.

    Usage:
        from db import get_database

        db = get_database()

        # Single query
        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM plans WHERE status = ?", ("pending",))
            rows = cursor.fetchall()

        # Transaction
        with db.transaction() as conn:
            conn.execute("INSERT INTO plans ...")
            conn.execute("INSERT INTO plan_steps ...")
            # Auto-commits on success, auto-rollback on exception
    """

    _local = threading.local()
    _init_lock = threading.Lock()
    _initialized: bool = False
    _instance: Optional["Database"] = None

    def __init__(self, config: DatabaseConfig = None):
        """
        Initialize database manager.

        Args:
            config: Optional database configuration. If not provided, loads from config file or uses defaults.
        """
        self.config = config or DatabaseConfig.load()
        self.db_path = self.config.get_db_path()

        # Initialize database on first use
        with self._init_lock:
            if not Database._initialized:
                self._init_database()
                self._run_migrations()
                Database._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
            )
            conn.row_factory = sqlite3.Row

            # Apply pragmas from config
            conn.execute(f"PRAGMA foreign_keys = {int(self.config.foreign_keys)}")
            conn.execute(f"PRAGMA journal_mode = {self.config.journal_mode}")
            conn.execute(f"PRAGMA synchronous = {self.config.synchronous}")
            conn.execute(f"PRAGMA cache_size = -{self.config.cache_size_kb}")

            self._local.connection = conn
        return self._local.connection

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection (auto-managed)."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            pass  # Connection stays open for reuse

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Execute operations in a transaction.

        Auto-commits on success, auto-rollback on exception.
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        """Close thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def _init_database(self):
        """Initialize database file and directory."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create empty database file with pragmas
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        try:
            conn.execute(f"PRAGMA journal_mode = {self.config.journal_mode}")
            conn.execute(f"PRAGMA synchronous = {self.config.synchronous}")
            conn.execute(f"PRAGMA foreign_keys = {int(self.config.foreign_keys)}")
            conn.execute(f"PRAGMA cache_size = -{self.config.cache_size_kb}")
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            conn.close()

    def _run_migrations(self):
        """Run pending database migrations."""
        from .migrations import MigrationRunner
        runner = MigrationRunner(self)
        applied = runner.migrate()
        if applied:
            logger.info(f"Applied {len(applied)} migrations: {applied}")

    # ====================
    # JSON Helper Methods
    # ====================

    @staticmethod
    def to_json(value: Any) -> Optional[str]:
        """Convert Python value to JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def from_json(value: Optional[str], default: Any = None) -> Any:
        """Parse JSON string from storage to Python value."""
        if value is None:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def row_to_dict(row: sqlite3.Row) -> dict:
        """Convert sqlite3.Row to dict."""
        return dict(zip(row.keys(), row))

    # ====================
    # Query Helpers
    # ====================

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        with self.connection() as conn:
            return conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and fetch one row as dict."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return self.row_to_dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute query and fetch all rows as dicts."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return [self.row_to_dict(row) for row in cursor.fetchall()]
