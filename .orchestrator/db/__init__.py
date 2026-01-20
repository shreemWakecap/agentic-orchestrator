"""
Database Package - All persistence in one place.

This folder contains everything database-related:
- orchestrator.db     : The SQLite database file
- config.json         : Database configuration
- config.py           : DatabaseConfig class
- connection.py       : Database connection manager
- repositories/       : Repository classes for each domain
- migrations/         : Schema migrations

Usage:
    from db import get_database, get_plan_repository

    # Get database instance
    db = get_database()

    # Get repositories
    plans = get_plan_repository()
    build_state = get_build_state_repository()
    knowledge = get_knowledge_repository()
    cost = get_cost_repository()
    runs = get_run_repository()

    # Run migrations
    applied = run_migrations()

    # Check schema version
    version = get_schema_version()
"""
import threading
from pathlib import Path

from .config import DatabaseConfig
from .connection import Database
from .repositories import (
    PlanRepository,
    BuildStateRepository,
    KnowledgeRepository,
    CostRepository,
    RunRepository,
    QuestionRepository,
    FileKnowledgeRepository,
)
from .migrations import MigrationRunner

# Singleton instance
_db_instance: Database = None
_db_lock = threading.Lock()


def get_database(config: DatabaseConfig = None) -> Database:
    """
    Get or create the database instance.

    Args:
        config: Optional database configuration

    Returns:
        Database instance
    """
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = Database(config)
        return _db_instance


def get_plan_repository() -> PlanRepository:
    """Get plan repository."""
    return PlanRepository(get_database())


def get_build_state_repository() -> BuildStateRepository:
    """Get build state repository."""
    return BuildStateRepository(get_database())


def get_knowledge_repository() -> KnowledgeRepository:
    """Get knowledge repository."""
    return KnowledgeRepository(get_database())


def get_cost_repository() -> CostRepository:
    """Get cost repository."""
    return CostRepository(get_database())


def get_run_repository() -> RunRepository:
    """Get run repository."""
    return RunRepository(get_database())


def get_question_repository() -> QuestionRepository:
    """Get question repository."""
    return QuestionRepository(get_database())


def get_file_knowledge_repository() -> FileKnowledgeRepository:
    """Get file knowledge repository."""
    return FileKnowledgeRepository(get_database())


def run_migrations() -> list[str]:
    """
    Run pending migrations.

    Returns:
        List of applied migration names
    """
    db = get_database()
    runner = MigrationRunner(db)
    return runner.migrate()


def get_schema_version() -> int:
    """
    Get current schema version.

    Returns:
        Current schema version number
    """
    db = get_database()
    runner = MigrationRunner(db)
    return runner.get_current_version()


def get_applied_migrations() -> list[dict]:
    """
    Get list of all applied migrations.

    Returns:
        List of migration records with version, name, applied_at
    """
    db = get_database()
    runner = MigrationRunner(db)
    return runner.get_applied_migrations()


def get_db_path() -> Path:
    """Get path to the database file."""
    return get_database().db_path


__all__ = [
    # Config
    "DatabaseConfig",
    # Connection
    "Database",
    # Repositories
    "PlanRepository",
    "BuildStateRepository",
    "KnowledgeRepository",
    "CostRepository",
    "RunRepository",
    "QuestionRepository",
    "FileKnowledgeRepository",
    # Migrations
    "MigrationRunner",
    # Factory functions
    "get_database",
    "get_plan_repository",
    "get_build_state_repository",
    "get_knowledge_repository",
    "get_cost_repository",
    "get_run_repository",
    "get_question_repository",
    "get_file_knowledge_repository",
    # Migration utilities
    "run_migrations",
    "get_schema_version",
    "get_applied_migrations",
    "get_db_path",
]
