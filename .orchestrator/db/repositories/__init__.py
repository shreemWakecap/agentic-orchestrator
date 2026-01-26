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
    IFileKnowledgeRepository,
)
from .plans import PlanRepository
from .build_state import BuildStateRepository
from .knowledge import KnowledgeRepository
from .cost import CostRepository
from .runs import RunRepository
from .file_knowledge import FileKnowledgeRepository
from .token_usage import TokenUsageRepository
from .task_mapping import TaskMappingRepository, get_task_mapping_repository
from .agent_definition import AgentDefinitionRepository, get_agent_definition_repository
from .expert_definition import ExpertDefinitionRepository, get_expert_definition_repository
from .config_repository import OrchestratorConfigRepository, get_config_repository

__all__ = [
    # Base and interfaces
    "BaseRepository",
    "IPlanRepository",
    "IBuildStateRepository",
    "IRunRepository",
    "IKnowledgeRepository",
    "ICostRepository",
    "IFileKnowledgeRepository",
    # Implementations
    "PlanRepository",
    "BuildStateRepository",
    "KnowledgeRepository",
    "CostRepository",
    "RunRepository",
    "FileKnowledgeRepository",
    "TokenUsageRepository",
    "TaskMappingRepository",
    "get_task_mapping_repository",
    # Agent/Expert/Config definitions (global, not project-scoped)
    "AgentDefinitionRepository",
    "ExpertDefinitionRepository",
    "OrchestratorConfigRepository",
    "get_agent_definition_repository",
    "get_expert_definition_repository",
    "get_config_repository",
]
