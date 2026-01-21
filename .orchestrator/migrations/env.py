"""
Alembic Migration Environment.

This file configures how Alembic runs migrations.
It uses the unified config module for database connection.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add orchestrator directory to path for imports
MIGRATIONS_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = MIGRATIONS_DIR.parent
sys.path.insert(0, str(ORCHESTRATOR_DIR))

# Import unified config (this loads dotenv automatically)
from config import get_database_config

# Import ALL models so Alembic can detect them for autogenerate
from db.models import Base as CoreBase
from db.models import (
    Plan, PlanPhase, PlanStep,
    BuildState, StepState, GoalVerificationState,
    ActiveRun, RunEvent,
    CostHistory,
    CodebaseKnowledge, Technology, ArchitectureInfo, ArchitectureModule, Domain, Pattern,
    ExpertIndex, ExpertEntry,
    ScanMetadata, FileKnowledge, FileScanHistory,
    Question, Answer,
)

# Import portal models
from portal.models.base import Base as PortalBase
from portal.models.job import Job, JobEvent, Checkpoint, QueueMetrics

# Alembic Config object
config = context.config

# Setup logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from unified config
# Note: We escape % characters for configparser interpolation
db_config = get_database_config()
db_url = db_config.sync_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", db_url)

# Combine all model metadata for autogenerate
# We use CoreBase as the primary and merge PortalBase tables into it
# This ensures both sets of models are tracked by Alembic
from sqlalchemy import MetaData

target_metadata = MetaData()

# Copy tables from both bases
for table in CoreBase.metadata.tables.values():
    table.to_metadata(target_metadata)
for table in PortalBase.metadata.tables.values():
    if table.name not in target_metadata.tables:
        table.to_metadata(target_metadata)


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter which objects to include in migrations.

    This allows us to exclude certain tables if needed.
    """
    # Include all objects by default
    return True


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to the database.
    Useful for reviewing migrations before applying them.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,  # Detect column type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    This connects to the database and applies migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,  # Detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
