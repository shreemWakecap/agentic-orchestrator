"""
Database Migration System.

Simple SQL-based migrations with version tracking.
"""
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Simple SQL migration system.

    Migrations are SQL files in the versions/ directory named:
        NNN_description.sql

    Where NNN is a zero-padded version number (001, 002, etc.)

    Each migration is run in a transaction and tracked in schema_versions table.
    """

    VERSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_versions (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """

    def __init__(self, db: "Database"):
        """
        Initialize migration runner.

        Args:
            db: Database instance to run migrations on
        """
        self.db = db
        self.migrations_dir = Path(__file__).parent / "versions"

        # Ensure versions table exists
        self._ensure_versions_table()

    def _ensure_versions_table(self):
        """Create schema_versions table if it doesn't exist."""
        conn = sqlite3.connect(str(self.db.db_path), timeout=30.0)
        try:
            conn.execute(self.VERSIONS_TABLE)
            conn.commit()
        finally:
            conn.close()

    def get_current_version(self) -> int:
        """Get current schema version from database."""
        row = self.db.fetchone(
            "SELECT MAX(version) as version FROM schema_versions"
        )
        return row['version'] if row and row['version'] else 0

    def get_pending_migrations(self) -> list[tuple[int, str, Path]]:
        """
        Find migrations that haven't been applied.

        Returns:
            List of (version, name, path) tuples for pending migrations
        """
        if not self.migrations_dir.exists():
            return []

        current_version = self.get_current_version()
        pending = []

        # Find all SQL files in versions directory
        for sql_file in sorted(self.migrations_dir.glob("*.sql")):
            # Parse version from filename (e.g., 001_initial_schema.sql)
            match = re.match(r"(\d+)_(.+)\.sql", sql_file.name)
            if match:
                version = int(match.group(1))
                name = match.group(2)

                if version > current_version:
                    pending.append((version, name, sql_file))

        return sorted(pending, key=lambda x: x[0])

    def apply_migration(self, version: int, name: str, sql_file: Path) -> bool:
        """
        Apply a single migration in a transaction.

        Args:
            version: Migration version number
            name: Migration name (for logging)
            sql_file: Path to SQL file

        Returns:
            True if successful, False otherwise
        """
        try:
            sql_content = sql_file.read_text(encoding="utf-8")

            # Use a fresh connection for migrations
            conn = sqlite3.connect(str(self.db.db_path), timeout=30.0)
            try:
                conn.execute("BEGIN")

                # Execute migration SQL
                conn.executescript(sql_content)

                # Record migration
                now = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO schema_versions (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now)
                )

                conn.commit()
                logger.info(f"Applied migration {version:03d}_{name}")
                return True

            except Exception as e:
                conn.rollback()
                logger.error(f"Migration {version:03d}_{name} failed: {e}")
                raise
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Failed to apply migration {version:03d}_{name}: {e}")
            return False

    def migrate(self) -> list[str]:
        """
        Apply all pending migrations.

        Returns:
            List of applied migration names
        """
        pending = self.get_pending_migrations()
        if not pending:
            return []

        applied = []
        for version, name, sql_file in pending:
            if self.apply_migration(version, name, sql_file):
                applied.append(f"{version:03d}_{name}")
            else:
                # Stop on first failure
                break

        return applied

    def get_applied_migrations(self) -> list[dict]:
        """Get list of all applied migrations."""
        return self.db.fetchall(
            "SELECT version, name, applied_at FROM schema_versions ORDER BY version"
        )


__all__ = ["MigrationRunner"]
