"""Dependency injection providers for FastAPI routes.

This module provides dependency functions that can be used with FastAPI's
Depends() mechanism to inject repositories and services into route handlers.
This enables:
- Testability through dependency overrides
- Loose coupling between routes and data layer
- Consistent repository access patterns

SOLID Revamp:
- Added IProjectContextProvider for proper project context abstraction
- Routes should use get_project_context_provider() instead of querying registry directly
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
    get_token_usage_repository,
    PlanRepository,
    BuildStateRepository,
    RunRepository,
    CostRepository,
    KnowledgeRepository,
    FileKnowledgeRepository,
    TokenUsageRepository,
    # SOLID revamp: Project context providers (database is source of truth)
    IProjectContextProvider,
    DatabaseProjectProvider,
)
from portal.services.task_manager import TaskManager, get_task_manager as _get_task_manager
from portal.services.recovery_service import RecoveryService, get_recovery_service as _get_recovery_service
from portal.services.plan_status_service import PlanStatusService
from portal.services.token_usage_service import TokenUsageService
from portal.services.experts_service import ExpertsService
from portal.services.run_management_service import RunManagementService

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


def get_token_usage_repo() -> TokenUsageRepository:
    """Get token usage repository instance for dependency injection."""
    return get_token_usage_repository()


def get_token_usage_service() -> TokenUsageService:
    """Get TokenUsageService instance for dependency injection.

    This service tracks and analyzes token usage across workflow executions,
    providing analytics, comparison metrics, and error rate calculations.
    """
    return TokenUsageService(
        token_usage_repo=get_token_usage_repository(),
        cost_repo=get_cost_repository(),
    )


def get_experts_service() -> ExpertsService:
    """Get ExpertsService instance for dependency injection.

    This service manages expert markdown files, providing listing and
    content retrieval with token count estimation.
    """
    return ExpertsService(project_root=PROJECT_ROOT)


# =============================================================================
# SOLID Revamp: Project Context Providers
# =============================================================================

def get_project_context_provider() -> IProjectContextProvider:
    """Get project context provider for dependency injection.

    This provider is the single source of truth for getting the current
    project ID in route handlers. It:
    1. First checks the contextvar (set by middleware)
    2. Falls back to the active project from the database

    Routes should use this instead of directly accessing any registry
    to ensure consistent project context handling. The database is
    the single source of truth for project data.

    Returns:
        IProjectContextProvider: Provider that returns current project ID.
    """
    return DatabaseProjectProvider()


# =============================================================================
# SOLID Revamp: Workflow Services with Full DI
# =============================================================================

def get_workflow_submission_service():
    """Get WorkflowSubmissionService instance for dependency injection.

    This service handles business logic for submitting workflows to
    background execution, extracted from route handlers for SRP compliance.
    """
    from portal.services.workflow_submission_service import WorkflowSubmissionService

    return WorkflowSubmissionService(
        run_repo=get_run_repo(),
        task_manager=get_task_manager(),
        context_provider=get_project_context_provider(),
    )


def get_recovery_service_with_di() -> RecoveryService:
    """Get RecoveryService instance with full dependency injection.

    This version injects PlanStatusService for proper SOLID compliance,
    avoiding internal imports in the service methods.
    """
    return RecoveryService(
        build_state_repo=get_build_state_repo(),
        plan_repo=get_plan_repo(),
        plan_status_service=get_plan_status_service(),
    )


def get_run_management_service() -> RunManagementService:
    """Get RunManagementService instance for dependency injection.

    This service handles force stopping stuck workflow runs and
    cleaning up associated resources (background tasks).
    """
    return RunManagementService(
        run_repo=get_run_repo(),
    )
