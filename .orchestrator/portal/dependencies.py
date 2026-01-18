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
    PlanRepository,
    BuildStateRepository,
    RunRepository,
    CostRepository,
    KnowledgeRepository,
)
from portal.services.task_manager import TaskManager, get_task_manager as _get_task_manager

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


def get_project_root() -> Path:
    """Get project root path for dependency injection."""
    return PROJECT_ROOT


def get_orchestrator_dir() -> Path:
    """Get orchestrator directory path for dependency injection."""
    return ORCHESTRATOR_DIR


def get_task_manager() -> TaskManager:
    """Get TaskManager singleton instance for dependency injection."""
    return _get_task_manager()
