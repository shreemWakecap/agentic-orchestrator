"""
Database Repositories.

Repository classes for each domain in the orchestrator database.
Includes base class and interfaces for dependency injection.
"""
from .base import BaseRepository
from .interfaces import (
    IPlanRepository,
    IBuildStateRepository,
    IRunRepository,
    IKnowledgeRepository,
    ICostRepository,
)
from .plans import PlanRepository
from .build_state import BuildStateRepository
from .knowledge import KnowledgeRepository
from .cost import CostRepository
from .runs import RunRepository

__all__ = [
    # Base and interfaces
    "BaseRepository",
    "IPlanRepository",
    "IBuildStateRepository",
    "IRunRepository",
    "IKnowledgeRepository",
    "ICostRepository",
    # Implementations
    "PlanRepository",
    "BuildStateRepository",
    "KnowledgeRepository",
    "CostRepository",
    "RunRepository",
]
