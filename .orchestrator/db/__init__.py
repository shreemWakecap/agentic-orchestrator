"""
Database Package - PostgreSQL with SQLAlchemy ORM.

Environment variables:
    ORCH_DB_HOST     - Database host (default: localhost)
    ORCH_DB_PORT     - Database port (default: 5432)
    ORCH_DB_NAME     - Database name (default: orchestrator)
    ORCH_DB_USER     - Database user (default: postgres)
    ORCH_DB_PASSWORD - Database password (default: postgres)

Multi-Project Support:
    Use the project_context module to set the active project.
    Most repositories automatically filter by project_id.
"""
import threading

from .config import DatabaseConfig
from .connection import Database
from .models import (
    Base,
    # Project models (multi-project support)
    Project,
    ProjectEvent,
    ProjectStatus,
    ProjectSourceType,
    # Plans
    Plan,
    PlanPhase,
    PlanStep,
    BuildState,
    StepState,
    GoalVerificationState,
    # Runs
    ActiveRun,
    RunEvent,
    # Cost
    CostHistory,
    # Knowledge
    CodebaseKnowledge,
    Technology,
    ArchitectureInfo,
    ArchitectureModule,
    Domain,
    Pattern,
    # Experts
    ExpertIndex,
    ExpertEntry,
    # Scanning
    ScanMetadata,
    FileKnowledge,
    FileScanHistory,
)

# Aliases for backward compatibility
Run = ActiveRun
Cost = CostHistory
Knowledge = CodebaseKnowledge

from .repositories import (
    PlanRepository,
    BuildStateRepository,
    KnowledgeRepository,
    CostRepository,
    RunRepository,
    FileKnowledgeRepository,
    TokenUsageRepository,
)

# Project context for multi-project support
from .project_context import (
    project_context,
    require_project_context,
    get_optional_project_id,
    ProjectContextError,
    ProjectContextData,
    with_project_context,
    # SOLID revamp: Project context providers for dependency injection
    IProjectContextProvider,
    ContextVarProjectProvider,
    DatabaseProjectProvider,  # Primary provider - uses database as source of truth
    RegistryFallbackProjectProvider,  # Deprecated alias for backward compatibility
)

from .repositories.project import ProjectRepository, get_project_repository

_db_instance: Database = None
_db_lock = threading.Lock()


def get_database() -> Database:
    """Get database instance."""
    global _db_instance
    with _db_lock:
        if _db_instance is None:
            _db_instance = Database()
        return _db_instance


def get_plan_repository() -> PlanRepository:
    return PlanRepository(get_database())


def get_build_state_repository() -> BuildStateRepository:
    return BuildStateRepository(get_database())


def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository(get_database())


def get_cost_repository() -> CostRepository:
    return CostRepository(get_database())


def get_run_repository() -> RunRepository:
    return RunRepository(get_database())


def get_file_knowledge_repository() -> FileKnowledgeRepository:
    return FileKnowledgeRepository(get_database())


def get_token_usage_repository() -> TokenUsageRepository:
    return TokenUsageRepository(get_database())


# Project repository is special - it doesn't need the legacy Database wrapper
# since it uses pure ORM
_project_repo_instance: ProjectRepository = None
_project_repo_lock = threading.Lock()


def get_project_repo() -> ProjectRepository:
    """Get project repository instance (alias for get_project_repository)."""
    global _project_repo_instance
    with _project_repo_lock:
        if _project_repo_instance is None:
            _project_repo_instance = ProjectRepository()
        return _project_repo_instance
