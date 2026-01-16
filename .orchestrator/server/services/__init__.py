# Services module for dependency injection
# This package contains service interfaces and implementations
# for the orchestrator server's dependency injection architecture.

"""
Services Package
================

This module provides the dependency injection infrastructure for the orchestrator server.

Interfaces:
- IPlanRegistry: Abstract base class for plan management operations
- IFileService: Abstract base class for file system operations
- IConfigService: Abstract base class for configuration management

Implementations:
- PlanRegistryService: Concrete implementation of IPlanRegistry
- FileService: Concrete implementation of IFileService
- ConfigService: Concrete implementation of IConfigService

Container:
- ServiceContainer: Dependency injection container for managing service instances
"""

# Interface exports
from .interfaces import (
    IPlanRegistry,
    IFileService,
    IConfigService,
    Plan,
    PlanState,
    OrchestratorConfig,
    BudgetConfig,
    AgentConfig,
    TimeoutConfig,
    RetryConfig,
    ContextLimitsConfig,
    ParallelConfig,
)

# Implementation exports - these will be available once implementations are created
try:
    from .plan_registry import PlanRegistryService
except ImportError:
    PlanRegistryService = None

try:
    from .file_service import FileService
except ImportError:
    FileService = None

try:
    from .config_service import ConfigService
except ImportError:
    ConfigService = None

try:
    from .container import ServiceContainer
except ImportError:
    ServiceContainer = None

__all__ = [
    # Interfaces
    "IPlanRegistry",
    "IFileService",
    "IConfigService",
    # Data classes
    "Plan",
    "PlanState",
    "OrchestratorConfig",
    "BudgetConfig",
    "AgentConfig",
    "TimeoutConfig",
    "RetryConfig",
    "ContextLimitsConfig",
    "ParallelConfig",
    # Implementations
    "PlanRegistryService",
    "FileService",
    "ConfigService",
    # Container
    "ServiceContainer",
]
