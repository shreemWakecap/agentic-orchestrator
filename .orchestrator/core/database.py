"""
DEPRECATED: Import from db package instead.

This module re-exports from db for backward compatibility.
All new code should import directly from db.

Example:
    # Old (deprecated):
    from core.database import get_database, PlanRepository

    # New (preferred):
    from db import get_database, PlanRepository
"""
import warnings

# Re-export everything from db package
from db import (
    # Config
    DatabaseConfig,
    # Connection
    Database,
    # Repositories
    PlanRepository,
    BuildStateRepository,
    KnowledgeRepository,
    CostRepository,
    RunRepository,
    # Migrations
    MigrationRunner,
    # Factory functions
    get_database,
    get_plan_repository,
    get_build_state_repository,
    get_knowledge_repository,
    get_cost_repository,
    get_run_repository,
    # Migration utilities
    run_migrations,
    get_schema_version,
    get_applied_migrations,
    get_db_path,
)

# Emit deprecation warning on import
warnings.warn(
    "core.database is deprecated, use db package instead",
    DeprecationWarning,
    stacklevel=2
)

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
    # Migrations
    "MigrationRunner",
    # Factory functions
    "get_database",
    "get_plan_repository",
    "get_build_state_repository",
    "get_knowledge_repository",
    "get_cost_repository",
    "get_run_repository",
    # Migration utilities
    "run_migrations",
    "get_schema_version",
    "get_applied_migrations",
    "get_db_path",
]
