"""Dependency injection providers for FastAPI routes.

This module provides dependency functions that can be used with FastAPI's
Depends() mechanism to inject repositories and services into route handlers.
This enables:
- Testability through dependency overrides
- Loose coupling between routes and data layer
- Consistent repository access patterns
"""
from typing import Generator
from pathlib import Path

from db import (
    get_plan_repository,
    get_build_state_repository,
    get_run_repository,
    get_cost_repository,
    get_knowledge_repository,
    get_file_knowledge_repository,
    PlanRepository,
    BuildStateRepository,
    RunRepository,
    CostRepository,
    KnowledgeRepository,
    FileKnowledgeRepository,
)
from portal.services.task_manager import TaskManager, get_task_manager as _get_task_manager
from portal.services.recovery_service import RecoveryService, get_recovery_service as _get_recovery_service
from portal.services.plan_status_service import PlanStatusService

# Project paths
PORTAL_DIR = Path(__file__).parent
ORCHESTRATOR_DIR = PORTAL_DIR.parent
PROJECT_ROOT = ORCHESTRATOR_DIR.parent


def get_plan_repo() -> PlanRepository:
    """Get plan repository instance for dependency injection."""
    return get_plan_repository()


def get_build_state_repo() -> BuildStateRepository:
    """Get build state repository instance for dependency injection."""
    return get_build_state_repository()


def get_run_repo() -> RunRepository:
    """Get run repository instance for dependency injection."""
    return get_run_repository()


def get_cost_repo() -> CostRepository:
    """Get cost repository instance for dependency injection."""
    return get_cost_repository()


def get_knowledge_repo() -> KnowledgeRepository:
    """Get knowledge repository instance for dependency injection."""
    return get_knowledge_repository()


def get_file_knowledge_repo() -> FileKnowledgeRepository:
    """Get file knowledge repository instance for dependency injection."""
    return get_file_knowledge_repository()


def get_project_root() -> Path:
    """Get project root path for dependency injection."""
    return PROJECT_ROOT


def get_orchestrator_dir() -> Path:
    """Get orchestrator directory path for dependency injection."""
    return ORCHESTRATOR_DIR


def get_task_manager() -> TaskManager:
    """Get TaskManager singleton instance for dependency injection."""
    return _get_task_manager()


def get_recovery_service() -> RecoveryService:
    """Get RecoveryService instance for dependency injection."""
    return _get_recovery_service()


def get_plan_status_service() -> PlanStatusService:
    """Get PlanStatusService instance for dependency injection.

    This service manages Plan status updates following the aggregate root pattern.
    All status changes should go through this service to ensure consistency
    between plans.status and build_states.status.
    """
    return PlanStatusService(
        plan_repo=get_plan_repository(),
        build_state_repo=get_build_state_repository(),
    )


