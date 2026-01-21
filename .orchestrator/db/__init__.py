"""
Database Package - PostgreSQL with SQLAlchemy ORM.

Environment variables:
    ORCH_DB_HOST     - Database host (default: localhost)
    ORCH_DB_PORT     - Database port (default: 5432)
    ORCH_DB_NAME     - Database name (default: orchestrator)
    ORCH_DB_USER     - Database user (default: postgres)
    ORCH_DB_PASSWORD - Database password (default: postgres)
"""
import threading

from .config import DatabaseConfig
from .connection import Database
from .models import (
    Base,
    Plan,
    PlanStep,
    BuildState,
    Run,
    Cost,
    Knowledge,
    FileKnowledge,
    Question,
    Answer,
)
from .repositories import (
    PlanRepository,
    BuildStateRepository,
    KnowledgeRepository,
    CostRepository,
    RunRepository,
    QuestionRepository,
    FileKnowledgeRepository,
)

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


def get_question_repository() -> QuestionRepository:
    return QuestionRepository(get_database())


def get_file_knowledge_repository() -> FileKnowledgeRepository:
    return FileKnowledgeRepository(get_database())
