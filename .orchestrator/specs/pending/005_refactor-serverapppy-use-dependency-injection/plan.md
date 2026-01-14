# Plan: Refactor server/app.py to use dependency injection for better testability. Extract hard-coded dependencies (file paths, plan registry) into injectable services. Create a services/ module with interfaces. Update tests to use mock services.

> Generated: 2026-01-15 00:49
> Complexity: medium
> Depth: moderate

## Context

```json
{
  "project_type": "api",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": ["fastapi", "pydantic"],
    "tools": ["pytest", "pytest-asyncio", "uvicorn", "rich"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/server/app.py",
      "purpose": "FastAPI web server with hard-coded dependencies (ORCHESTRATOR_DIR, PROJECT_ROOT, specs_dir paths, workflow instances, cost estimator paths)",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/core/plan_registry.py",
      "purpose": "PlanRegistry class - candidate for extraction to injectable service interface",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/core/config.py",
      "purpose": "ConfigLoader with existing pattern for dependency injection via project_root parameter",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/core/cost.py",
      "purpose": "CostEstimator, CostReporter, BudgetManager classes - candidates for injectable services",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/tests/unit/test_portal.py",
      "purpose": "Existing tests for server/app.py - uses unittest.mock.patch for mocking, needs update to use injected services",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/tests/conftest.py",
      "purpose": "Shared pytest fixtures including project_root, mock_agent_result - extend with service mocks",
      "relevance": "medium",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/core/__init__.py",
      "purpose": "Core module exports - will need to export new service interfaces",
      "relevance": "medium",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/core/workflow.py",
      "purpose": "Base Workflow class - reference for existing patterns (dataclasses, type hints)",
      "relevance": "medium",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/pyproject.toml",
      "purpose": "Project configuration - verify no new dependencies needed",
      "relevance": "low",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "Dataclass configuration",
      "description": "Use frozen dataclasses for configuration (TimeoutConfig, RetryConfig, etc. in core/config.py)",
      "example_file": ".orchestrator/core/config.py",
      "must_follow": true
    },
    {
      "name": "Path-based initialization",
      "description": "Classes accept project_root: Path in __init__ and derive paths internally (PlanRegistry, ConfigLoader)",
      "example_file": ".orchestrator/core/plan_registry.py",
      "must_follow": true
    },
    {
      "name": "Protocol/ABC for interfaces",
      "description": "Python typing.Protocol or abc.ABC for abstract interfaces (Workflow ABC in core/workflow.py)",
      "example_file": ".orchestrator/core/workflow.py",
      "must_follow": true
    },
    {
      "name": "unittest.mock for testing",
      "description": "Tests use unittest.mock.patch and MagicMock for mocking dependencies",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": true
    },
    {
      "name": "pytest fixtures in conftest",
      "description": "Shared fixtures defined in tests/conftest.py, test-specific fixtures in test files",
      "example_file": ".orchestrator/tests/conftest.py",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/workflows/",
        "impact": "Workflow classes (PlanningWorkflow, BuildingWorkflow, etc.) are imported and instantiated in app.py - may need factory pattern"
      },
      {
        "module": ".orchestrator/core/cost.py",
        "impact": "CostEstimator, CostReporter, BudgetManager instantiated directly in route handlers with hard-coded paths"
      },
      {
        "module": ".orchestrator/core/plan_registry.py",
        "impact": "PlanRegistry not currently used in app.py but plan-related functions read from ORCHESTRATOR_DIR/specs directly"
      }
    ],
    "external": [
      {
        "package": "fastapi",
        "usage": "Web framework - use Depends() for dependency injection pattern"
      },
      {
        "package": "pydantic",
        "usage": "Request/response models already in use"
      },
      {
        "package": "typing",
        "usage": "Protocol class for service interfaces"
      }
    ]
  },
  "considerations": [
    {
      "type": "constraint",
      "description": "FastAPI has built-in Depends() for dependency injection - should leverage this pattern for route handlers",
      "severity": "medium"
    },
    {
      "type": "risk",
      "description": "Module-level constants (ORCHESTRATOR_DIR, PROJECT_ROOT, SERVER_DIR) set at import time - need to make configurable without breaking existing usage",
      "severity": "high"
    },
    {
      "type": "constraint",
      "description": "active_runs dict is module-level state - consider extracting to RunsRepository service",
      "severity": "medium"
    },
    {
      "type": "note",
      "description": "Tests currently import from server.app and patch functions directly - new service injection will require updating test patterns",
      "severity": "medium"
    },
    {
      "type": "edge_case",
      "description": "Background tasks (_run_planning_workflow, etc.) capture references to module-level state - injection must handle async context properly",
      "severity": "high"
    },
    {
      "type": "note",
      "description": "Existing patterns use project_root: Path for initialization - services should follow same convention",
      "severity": "low"
    }
  ],
  "summary": "FastAPI application in .orchestrator/server/app.py with multiple hard-coded dependencies: file paths (ORCHESTRATOR_DIR, PROJECT_ROOT, specs directories), direct instantiation of CostEstimator/BudgetManager in route handlers, module-level active_runs state, and workflow class instantiation in background tasks. The codebase follows patterns of dataclass configs, Path-based initialization, and unittest.mock for testing. Key refactoring targets: extract FileSystemService for path operations, PlanService wrapping plan functions, CostService wrapping cost/budget classes, and RunsRepository for active_runs state. Use FastAPI's Depends() for injection in routes and typing.Protocol for interfaces. Tests in test_portal.py will need updates to inject mock services via fixtures in conftest.py."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Extract hard-coded dependencies into Protocol-based services injected via FastAPI Depends() pattern",
    "rationale": "Leverages FastAPI's native dependency injection, follows existing Protocol/ABC patterns in codebase, enables clean test mocking without monkey-patching",
    "complexity": "moderate"
  },
  "components": [
    {
      "name": "ServiceProtocols",
      "type": "util",
      "file_path": ".orchestrator/server/services/__init__.py",
      "action": "create",
      "responsibility": "Define Protocol interfaces for all injectable services",
      "interfaces": {
        "inputs": [],
        "outputs": ["FileSystemService", "PlanService", "CostService", "RunsRepository protocols"]
      }
    },
    {
      "name": "FileSystemService",
      "type": "service",
      "file_path": ".orchestrator/server/services/filesystem.py",
      "action": "create",
      "responsibility": "Encapsulate path resolution for ORCHESTRATOR_DIR, PROJECT_ROOT, specs directories",
      "interfaces": {
        "inputs": ["project_root: Path"],
        "outputs": ["orchestrator_dir", "specs_dir", "server_dir properties"]
      }
    },
    {
      "name": "PlanService",
      "type": "service",
      "file_path": ".orchestrator/server/services/plans.py",
      "action": "create",
      "responsibility": "Wrap plan listing, reading, and status operations currently done via direct file access",
      "interfaces": {
        "inputs": ["fs_service: FileSystemService"],
        "outputs": ["list_plans()", "get_plan()", "get_plan_status()"]
      }
    },
    {
      "name": "CostService",
      "type": "service",
      "file_path": ".orchestrator/server/services/cost.py",
      "action": "create",
      "responsibility": "Wrap CostEstimator, CostReporter, BudgetManager instantiation and operations",
      "interfaces": {
        "inputs": ["fs_service: FileSystemService"],
        "outputs": ["get_cost_report()", "check_budget()", "estimate_cost()"]
      }
    },
    {
      "name": "RunsRepository",
      "type": "service",
      "file_path": ".orchestrator/server/services/runs.py",
      "action": "create",
      "responsibility": "Manage active_runs state with thread-safe access",
      "interfaces": {
        "inputs": [],
        "outputs": ["get_run()", "create_run()", "update_run()", "list_runs()"]
      }
    },
    {
      "name": "Dependencies",
      "type": "util",
      "file_path": ".orchestrator/server/dependencies.py",
      "action": "create",
      "responsibility": "FastAPI Depends() factory functions for service injection",
      "interfaces": {
        "inputs": [],
        "outputs": ["get_fs_service()", "get_plan_service()", "get_cost_service()", "get_runs_repo()"]
      }
    },
    {
      "name": "AppModule",
      "type": "route",
      "file_path": ".orchestrator/server/app.py",
      "action": "modify",
      "responsibility": "Replace hard-coded dependencies with Depends() injected services",
      "interfaces": {
        "inputs": ["Injected services via Depends()"],
        "outputs": ["Same API responses"]
      }
    },
    {
      "name": "TestFixtures",
      "type": "test",
      "file_path": ".orchestrator/tests/conftest.py",
      "action": "modify",
      "responsibility": "Add mock service fixtures for all Protocol interfaces",
      "interfaces": {
        "inputs": [],
        "outputs": ["mock_fs_service", "mock_plan_service", "mock_cost_service", "mock_runs_repo fixtures"]
      }
    },
    {
      "name": "PortalTests",
      "type": "test",
      "file_path": ".orchestrator/tests/unit/test_portal.py",
      "action": "modify",
      "responsibility": "Replace patch-based mocking with dependency override injection",
      "interfaces": {
        "inputs": ["mock service fixtures"],
        "outputs": ["test results"]
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "FastAPI startup",
      "to": "dependencies.py",
      "data": "project_root configuration",
      "description": "Initialize default service instances at app startup"
    },
    {
      "step": 2,
      "from": "Route handler",
      "to": "Depends() factories",
      "data": "dependency request",
      "description": "FastAPI resolves dependencies via Depends() annotations"
    },
    {
      "step": 3,
      "from": "Route handler",
      "to": "Service instances",
      "data": "business operation request",
      "description": "Handler calls injected service methods instead of direct file/class access"
    },
    {
      "step": 4,
      "from": "Test setup",
      "to": "app.dependency_overrides",
      "data": "mock services",
      "description": "Tests override Depends() with mock implementations"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Use typing.Protocol for service interfaces instead of abc.ABC",
      "alternatives": ["abc.ABC abstract classes", "No interfaces (duck typing)"],
      "rationale": "Protocol enables structural subtyping - mocks don't need to inherit, just implement methods. Matches existing workflow.py pattern.",
      "trade_offs": "Less explicit than ABC but more flexible for testing"
    },
    {
      "decision": "Use FastAPI app.dependency_overrides for test injection",
      "alternatives": ["Constructor injection", "Module-level override functions"],
      "rationale": "Native FastAPI pattern, clean test isolation, no custom infrastructure needed",
      "trade_offs": "Tests must use TestClient or override before each test"
    },
    {
      "decision": "FileSystemService as foundation service injected into other services",
      "alternatives": ["Each service gets project_root directly", "Global config singleton"],
      "rationale": "Single source of truth for paths, easy to mock entire filesystem layer",
      "trade_offs": "Creates service dependency chain"
    }
  ],
  "integration_points": [
    {
      "component": ".orchestrator/core/cost.py",
      "external_system": "CostEstimator, BudgetManager classes",
      "protocol": "Direct instantiation within CostService",
      "notes": "CostService wraps these classes, doesn't modify them"
    },
    {
      "component": ".orchestrator/workflows/",
      "external_system": "Workflow classes",
      "protocol": "Instantiated in background tasks",
      "notes": "Consider WorkflowFactory service in future iteration - out of scope for initial refactor"
    }
  ],
  "open_questions": [
    {
      "question": "Should module-level constants (ORCHESTRATOR_DIR, etc.) be removed or kept as defaults?",
      "impact": "medium",
      "suggested_resolution": "Keep as module-level defaults, FileSystemService can override. Maintains backward compatibility."
    },
    {
      "question": "How to handle async context in background tasks that need services?",
      "impact": "high",
      "suggested_resolution": "Pass service instances explicitly to background task functions rather than using Depends() in async context"
    }
  ]
}
```

---

## Implementation Steps

## Implementation Steps

### Phase 1: Service Interfaces and Foundation

#### Step 1.1: create .orchestrator/server/services/__init__.py
**Action:** create
**Target:** .orchestrator/server/services/__init__.py
**Dependencies:** none
**Description:** Define Protocol interfaces for all injectable services

```python
"""Service protocols for dependency injection."""

from pathlib import Path
from typing import Protocol, Any, Optional
from datetime import datetime


class FileSystemServiceProtocol(Protocol):
    """Protocol for file system path resolution."""
    
    @property
    def project_root(self) -> Path: ...
    
    @property
    def orchestrator_dir(self) -> Path: ...
    
    @property
    def specs_dir(self) -> Path: ...
    
    @property
    def server_dir(self) -> Path: ...


class PlanServiceProtocol(Protocol):
    """Protocol for plan operations."""
    
    def list_plans(self) -> list[dict[str, Any]]: ...
    
    def get_plan(self, plan_id: str) -> Optional[dict[str, Any]]: ...
    
    def get_plan_status(self, plan_id: str) -> Optional[str]: ...


class CostServiceProtocol(Protocol):
    """Protocol for cost estimation and budget operations."""
    
    def get_cost_report(self, plan_id: str) -> Optional[dict[str, Any]]: ...
    
    def check_budget(self, plan_id: str) -> dict[str, Any]: ...


class RunsRepositoryProtocol(Protocol):
    """Protocol for managing active workflow runs."""
    
    def get_run(self, run_id: str) -> Optional[dict[str, Any]]: ...
    
    def create_run(self, run_id: str, plan_id: str, workflow_type: str) -> dict[str, Any]: ...
    
    def update_run(self, run_id: str, **updates: Any) -> Optional[dict[str, Any]]: ...
    
    def list_runs(self) -> list[dict[str, Any]]: ...
    
    def delete_run(self, run_id: str) -> bool: ...
```

#### Step 1.2: create .orchestrator/server/services/filesystem.py
**Action:** create
**Target:** .orchestrator/server/services/filesystem.py
**Dependencies:** Step 1.1
**Description:** Implement FileSystemService for path resolution

```python
"""File system service for path resolution."""

from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class FileSystemService:
    """Encapsulates path resolution for orchestrator directories."""
    
    _project_root: Path
    
    @property
    def project_root(self) -> Path:
        return self._project_root
    
    @property
    def orchestrator_dir(self) -> Path:
        return self._project_root / ".orchestrator"
    
    @property
    def specs_dir(self) -> Path:
        return self.orchestrator_dir / "specs"
    
    @property
    def server_dir(self) -> Path:
        return self.orchestrator_dir / "server"
    
    @classmethod
    def from_project_root(cls, project_root: Path) -> "FileSystemService":
        """Create service from project root path."""
        return cls(_project_root=project_root.resolve())
```

#### Step 1.3: create .orchestrator/server/services/runs.py
**Action:** create
**Target:** .orchestrator/server/services/runs.py
**Dependencies:** Step 1.1
**Description:** Implement RunsRepository for managing active workflow runs with thread-safe access

```python
"""Runs repository for managing active workflow runs."""

import threading
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class RunsRepository:
    """Thread-safe repository for active workflow runs."""
    
    _runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        """Get a run by ID."""
        with self._lock:
            return self._runs.get(run_id)
    
    def create_run(self, run_id: str, plan_id: str, workflow_type: str) -> dict[str, Any]:
        """Create a new run entry."""
        run_data = {
            "run_id": run_id,
            "plan_id": plan_id,
            "workflow_type": workflow_type,
            "status": "pending",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._runs[run_id] = run_data
        return run_data
    
    def update_run(self, run_id: str, **updates: Any) -> Optional[dict[str, Any]]:
        """Update a run with new data."""
        with self._lock:
            if run_id not in self._runs:
                return None
            self._runs[run_id].update(updates)
            return self._runs[run_id].copy()
    
    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs."""
        with self._lock:
            return list(self._runs.values())
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run by ID."""
        with self._lock:
            if run_id in self._runs:
                del self._runs[run_id]
                return True
            return False
```

#### Step 1.4: create .orchestrator/server/services/plans.py
**Action:** create
**Target:** .orchestrator/server/services/plans.py
**Dependencies:** Step 1.1, Step 1.2
**Description:** Implement PlanService for plan listing and reading operations

```python
"""Plan service for plan operations."""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

from .filesystem import FileSystemService


@dataclass
class PlanService:
    """Service for plan listing, reading, and status operations."""
    
    fs_service: FileSystemService
    
    def _get_pending_dir(self) -> Path:
        return self.fs_service.specs_dir / "pending"
    
    def _get_approved_dir(self) -> Path:
        return self.fs_service.specs_dir / "approved"
    
    def _get_completed_dir(self) -> Path:
        return self.fs_service.specs_dir / "completed"
    
    def list_plans(self) -> list[dict[str, Any]]:
        """List all plans across all status directories."""
        plans = []
        
        status_dirs = [
            ("pending", self._get_pending_dir()),
            ("approved", self._get_approved_dir()),
            ("completed", self._get_completed_dir()),
        ]
        
        for status, dir_path in status_dirs:
            if not dir_path.exists():
                continue
            for plan_dir in dir_path.iterdir():
                if plan_dir.is_dir():
                    plan_data = self._read_plan_from_dir(plan_dir, status)
                    if plan_data:
                        plans.append(plan_data)
        
        return plans
    
    def get_plan(self, plan_id: str) -> Optional[dict[str, Any]]:
        """Get a specific plan by ID."""
        for status, dir_path in [
            ("pending", self._get_pending_dir()),
            ("approved", self._get_approved_dir()),
            ("completed", self._get_completed_dir()),
        ]:
            plan_dir = dir_path / plan_id
            if plan_dir.exists():
                return self._read_plan_from_dir(plan_dir, status)
        return None
    
    def get_plan_status(self, plan_id: str) -> Optional[str]:
        """Get the status of a plan by ID."""
        for status, dir_path in [
            ("pending", self._get_pending_dir()),
            ("approved", self._get_approved_dir()),
            ("completed", self._get_completed_dir()),
        ]:
            if (dir_path / plan_id).exists():
                return status
        return None
    
    def _read_plan_from_dir(self, plan_dir: Path, status: str) -> Optional[dict[str, Any]]:
        """Read plan data from a plan directory."""
        spec_file = plan_dir / "spec.json"
        if not spec_file.exists():
            # Try reading from plan.md or other files
            return {
                "id": plan_dir.name,
                "status": status,
                "path": str(plan_dir),
            }
        
        try:
            with open(spec_file) as f:
                data = json.load(f)
            data["id"] = plan_dir.name
            data["status"] = status
            data["path"] = str(plan_dir)
            return data
        except (json.JSONDecodeError, IOError):
            return {
                "id": plan_dir.name,
                "status": status,
                "path": str(plan_dir),
            }
```

#### Step 1.5: create .orchestrator/server/services/cost.py
**Action:** create
**Target:** .orchestrator/server/services/cost.py
**Dependencies:** Step 1.1, Step 1.2
**Description:** Implement CostService wrapping CostEstimator and BudgetManager

```python
"""Cost service for cost estimation and budget operations."""

from typing import Any, Optional
from dataclasses import dataclass

from .filesystem import FileSystemService


@dataclass
class CostService:
    """Service for cost estimation and budget management."""
    
    fs_service: FileSystemService
    
    def get_cost_report(self, plan_id: str) -> Optional[dict[str, Any]]:
        """Get cost report for a plan."""
        from ...core.cost import CostReporter
        
        try:
            reporter = CostReporter(self.fs_service.orchestrator_dir)
            return reporter.get_report(plan_id)
        except Exception:
            return None
    
    def check_budget(self, plan_id: str) -> dict[str, Any]:
        """Check budget status for a plan."""
        from ...core.cost import BudgetManager
        
        try:
            manager = BudgetManager(self.fs_service.orchestrator_dir)
            return manager.check_budget(plan_id)
        except Exception:
            return {"status": "unknown", "error": "Failed to check budget"}
    
    def estimate_cost(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        """Estimate cost for a plan."""
        from ...core.cost import CostEstimator
        
        try:
            estimator = CostEstimator()
            return estimator.estimate(plan_data)
        except Exception:
            return {"estimated_cost": 0, "error": "Failed to estimate cost"}
```

### Phase 2: Dependencies and App Integration

#### Step 2.1: create .orchestrator/server/dependencies.py
**Action:** create
**Target:** .orchestrator/server/dependencies.py
**Dependencies:** Step 1.2, Step 1.3, Step 1.4, Step 1.5
**Description:** Create FastAPI Depends() factory functions for service injection

```python
"""FastAPI dependency injection factories."""

from pathlib import Path
from functools import lru_cache
from typing import Optional

from .services.filesystem import FileSystemService
from .services.plans import PlanService
from .services.cost import CostService
from .services.runs import RunsRepository


# Module-level default project root (can be overridden for testing)
_default_project_root: Optional[Path] = None


def set_project_root(project_root: Path) -> None:
    """Set the default project root for service initialization."""
    global _default_project_root
    _default_project_root = project_root
    # Clear cached services when root changes
    get_fs_service.cache_clear()
    get_plan_service.cache_clear()
    get_cost_service.cache_clear()


def get_project_root() -> Path:
    """Get the configured project root or detect from current directory."""
    if _default_project_root:
        return _default_project_root
    # Default: find project root by looking for .orchestrator directory
    current = Path.cwd()
    while current != current.parent:
        if (current / ".orchestrator").exists():
            return current
        current = current.parent
    return Path.cwd()


@lru_cache()
def get_fs_service() -> FileSystemService:
    """Get the FileSystemService instance."""
    return FileSystemService.from_project_root(get_project_root())


@lru_cache()
def get_plan_service() -> PlanService:
    """Get the PlanService instance."""
    return PlanService(fs_service=get_fs_service())


@lru_cache()
def get_cost_service() -> CostService:
    """Get the CostService instance."""
    return CostService(fs_service=get_fs_service())


# RunsRepository is not cached - single instance managed at module level
_runs_repository: Optional[RunsRepository] = None


def get_runs_repository() -> RunsRepository:
    """Get the RunsRepository instance."""
    global _runs_repository
    if _runs_repository is None:
        _runs_repository = RunsRepository()
    return _runs_repository


def reset_services() -> None:
    """Reset all service instances (for testing)."""
    global _runs_repository, _default_project_root
    _default_project_root = None
    _runs_repository = None
    get_fs_service.cache_clear()
    get_plan_service.cache_clear()
    get_cost_service.cache_clear()
```

#### Step 2.2: modify .orchestrator/server/app.py
**Action:** modify
**Target:** .orchestrator/server/app.py
**Dependencies:** Step 2.1
**Description:** Update app.py to use dependency injection for services. Replace hard-coded paths and direct instantiation with Depends() injected services.

```python
# At the top of the file, add new imports after existing imports:
from fastapi import Depends

from .dependencies import (
    get_fs_service,
    get_plan_service,
    get_cost_service,
    get_runs_repository,
    set_project_root,
)
from .services.filesystem import FileSystemService
from .services.plans import PlanService
from .services.cost import CostService
from .services.runs import RunsRepository

# Keep existing module-level constants for backward compatibility but mark as deprecated:
# ORCHESTRATOR_DIR, PROJECT_ROOT, SERVER_DIR - these remain for any direct usage

# Replace the active_runs dict usage with RunsRepository:
# OLD: active_runs: dict[str, dict] = {}
# NEW: Use get_runs_repository() dependency

# Update route handlers to use injected services. Example modifications:

# For plan listing endpoint - change from direct file access to PlanService:
@app.get("/api/plans")
async def list_plans(
    plan_service: PlanService = Depends(get_plan_service),
) -> list[dict]:
    """List all available plans."""
    return plan_service.list_plans()


# For single plan endpoint:
@app.get("/api/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    plan_service: PlanService = Depends(get_plan_service),
) -> dict:
    """Get a specific plan by ID."""
    plan = plan_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


# For runs endpoints - use RunsRepository:
@app.get("/api/runs")
async def list_runs(
    runs_repo: RunsRepository = Depends(get_runs_repository),
) -> list[dict]:
    """List all active runs."""
    return runs_repo.list_runs()


@app.get("/api/runs/{run_id}")
async def get_run(
    run_id: str,
    runs_repo: RunsRepository = Depends(get_runs_repository),
) -> dict:
    """Get a specific run by ID."""
    run = runs_repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


# For cost endpoints - use CostService:
@app.get("/api/plans/{plan_id}/cost")
async def get_plan_cost(
    plan_id: str,
    cost_service: CostService = Depends(get_cost_service),
) -> dict:
    """Get cost report for a plan."""
    report = cost_service.get_cost_report(plan_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Cost report for {plan_id} not found")
    return report


# For background task functions, pass services explicitly:
async def _run_planning_workflow(
    run_id: str,
    plan_id: str,
    runs_repo: RunsRepository,
    fs_service: FileSystemService,
) -> None:
    """Execute planning workflow with injected services."""
    runs_repo.update_run(run_id, status="running")
    try:
        # Use fs_service.orchestrator_dir instead of ORCHESTRATOR_DIR
        # ... workflow execution logic ...
        runs_repo.update_run(run_id, status="completed", completed_at=datetime.now().isoformat())
    except Exception as e:
        runs_repo.update_run(run_id, status="failed", error=str(e))


# Update workflow trigger endpoints to pass services to background tasks:
@app.post("/api/plans/{plan_id}/run")
async def run_plan(
    plan_id: str,
    background_tasks: BackgroundTasks,
    runs_repo: RunsRepository = Depends(get_runs_repository),
    fs_service: FileSystemService = Depends(get_fs_service),
    plan_service: PlanService = Depends(get_plan_service),
) -> dict:
    """Start a workflow run for a plan."""
    plan = plan_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    
    run_id = f"{plan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_data = runs_repo.create_run(run_id, plan_id, "planning")
    
    background_tasks.add_task(
        _run_planning_workflow,
        run_id=run_id,
        plan_id=plan_id,
        runs_repo=runs_repo,
        fs_service=fs_service,
    )
    
    return run_data
```

#### Step 2.3: modify .orchestrator/core/__init__.py
**Action:** modify
**Target:** .orchestrator/core/__init__.py
**Dependencies:** Step 1.1
**Description:** Export service protocols from core module for external use

```python
# Add to existing exports:
from ..server.services import (
    FileSystemServiceProtocol,
    PlanServiceProtocol,
    CostServiceProtocol,
    RunsRepositoryProtocol,
)

__all__ = [
    # ... existing exports ...
    "FileSystemServiceProtocol",
    "PlanServiceProtocol", 
    "CostServiceProtocol",
    "RunsRepositoryProtocol",
]
```

### Phase 3: Testing

#### Step 3.1: modify .orchestrator/tests/conftest.py
**Action:** modify
**Target:** .orchestrator/tests/conftest.py
**Dependencies:** Step 2.1
**Description:** Add mock service fixtures for dependency injection testing

```python
# Add new imports at top:
from unittest.mock import MagicMock
from pathlib import Path
import pytest

from server.services.filesystem import FileSystemService
from server.services.plans import PlanService
from server.services.cost import CostService
from server.services.runs import RunsRepository
from server.dependencies import reset_services


@pytest.fixture
def mock_fs_service(tmp_path: Path) -> FileSystemService:
    """Create a FileSystemService pointing to temp directory."""
    return FileSystemService.from_project_root(tmp_path)


@pytest.fixture
def mock_plan_service(mock_fs_service: FileSystemService) -> MagicMock:
    """Create a mock PlanService."""
    mock = MagicMock(spec=PlanService)
    mock.list_plans.return_value = [
        {"id": "test-plan-001", "status": "pending", "title": "Test Plan"}
    ]
    mock.get_plan.return_value = {
        "id": "test-plan-001",
        "status": "pending",
        "title": "Test Plan",
    }
    mock.get_plan_status.return_value = "pending"
    return mock


@pytest.fixture
def mock_cost_service() -> MagicMock:
    """Create a mock CostService."""
    mock = MagicMock(spec=CostService)
    mock.get_cost_report.return_value = {
        "total_cost": 0.50,
        "breakdown": {"tokens": 1000},
    }
    mock.check_budget.return_value = {"status": "ok", "remaining": 10.0}
    return mock


@pytest.fixture
def mock_runs_repository() -> RunsRepository:
    """Create a fresh RunsRepository for testing."""
    return RunsRepository()


@pytest.fixture(autouse=True)
def reset_service_state():
    """Reset service state before each test."""
    reset_services()
    yield
    reset_services()
```

#### Step 3.2: modify .orchestrator/tests/unit/test_portal.py
**Action:** modify
**Target:** .orchestrator/tests/unit/test_portal.py
**Dependencies:** Step 2.2, Step 3.1
**Description:** Update tests to use dependency override injection instead of patch-based mocking

```python
# Add new imports:
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from server.app import app
from server.dependencies import (
    get_fs_service,
    get_plan_service,
    get_cost_service,
    get_runs_repository,
)


@pytest.fixture
def client(
    mock_fs_service,
    mock_plan_service,
    mock_cost_service,
    mock_runs_repository,
) -> TestClient:
    """Create test client with mocked dependencies."""
    # Override dependencies with mocks
    app.dependency_overrides[get_fs_service] = lambda: mock_fs_service
    app.dependency_overrides[get_plan_service] = lambda: mock_plan_service
    app.dependency_overrides[get_cost_service] = lambda: mock_cost_service
    app.dependency_overrides[get_runs_repository] = lambda: mock_runs_repository
    
    yield TestClient(app)
    
    # Clear overrides after test
    app.dependency_overrides.clear()


class TestListPlans:
    """Tests for plan listing endpoint."""
    
    def test_list_plans_returns_plans(self, client: TestClient, mock_plan_service: MagicMock):
        """Test that list plans returns plan data from service."""
        response = client.get("/api/plans")
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "test-plan-001"
        mock_plan_service.list_plans.assert_called_once()
    
    def test_list_plans_empty(self, client: TestClient, mock_plan_service: MagicMock):
        """Test that empty plan list is handled."""
        mock_plan_service.list_plans.return_value = []
        
        response = client.get("/api/plans")
        
        assert response.status_code == 200
        assert response.json() == []


class TestGetPlan:
    """Tests for single plan endpoint."""
    
    def test_get_plan_found(self, client: TestClient, mock_plan_service: MagicMock):
        """Test getting an existing plan."""
        response = client.get("/api/plans/test-plan-001")
        
        assert response.status_code == 200
        assert response.json()["id"] == "test-plan-001"
        mock_plan_service.get_plan.assert_called_once_with("test-plan-001")
    
    def test_get_plan_not_found(self, client: TestClient, mock_plan_service: MagicMock):
        """Test 404 when plan doesn't exist."""
        mock_plan_service.get_plan.return_value = None
        
        response = client.get("/api/plans/nonexistent")
        
        assert response.status_code == 404


class TestRuns:
    """Tests for workflow run endpoints."""
    
    def test_list_runs_empty(self, client: TestClient):
        """Test listing runs when none exist."""
        response = client.get("/api/runs")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_run_not_found(self, client: TestClient):
        """Test 404 when run doesn't exist."""
        response = client.get("/api/runs/nonexistent")
        
        assert response.status_code == 404


class TestCost:
    """Tests for cost endpoints."""
    
    def test_get_plan_cost(self, client: TestClient, mock_cost_service: MagicMock):
        """Test getting cost report for a plan."""
        response = client.get("/api/plans/test-plan-001/cost")
        
        assert response.status_code == 200
        assert response.json()["total_cost"] == 0.50
        mock_cost_service.get_cost_report.assert_called_once_with("test-plan-001")
    
    def test_get_plan_cost_not_found(self, client: TestClient, mock_cost_service: MagicMock):
        """Test 404 when cost report doesn't exist."""
        mock_cost_service.get_cost_report.return_value = None
        
        response = client.get("/api/plans/nonexistent/cost")
        
        assert response.status_code == 404
```

#### Step 3.3: create .orchestrator/tests/unit/test_services.py
**Action:** create
**Target:** .orchestrator/tests/unit/test_services.py
**Dependencies:** Step 1.2, Step 1.3, Step 1.4
**Parallel:** tests
**Description:** Add unit tests for the new service implementations

```python
"""Unit tests for service implementations."""

import json
import pytest
from pathlib import Path

from server.services.filesystem import FileSystemService
from server.services.plans import PlanService
from server.services.runs import RunsRepository


class TestFileSystemService:
    """Tests for FileSystemService."""
    
    def test_from_project_root(self, tmp_path: Path):
        """Test creating service from project root."""
        service = FileSystemService.from_project_root(tmp_path)
        
        assert service.project_root == tmp_path
        assert service.orchestrator_dir == tmp_path / ".orchestrator"
        assert service.specs_dir == tmp_path / ".orchestrator" / "specs"
        assert service.server_dir == tmp_path / ".orchestrator" / "server"
    
    def test_immutability(self, tmp_path: Path):
        """Test that service is immutable (frozen dataclass)."""
        service = FileSystemService.from_project_root(tmp_path)
        
        with pytest.raises(AttributeError):
            service._project_root = Path("/other")


class TestRunsRepository:
    """Tests for RunsRepository."""
    
    def test_create_run(self):
        """Test creating a new run."""
        repo = RunsRepository()
        
        run = repo.create_run("run-001", "plan-001", "planning")
        
        assert run["run_id"] == "run-001"
        assert run["plan_id"] == "plan-001"
        assert run["status"] == "pending"
    
    def test_get_run(self):
        """Test getting an existing run."""
        repo = RunsRepository()
        repo.create_run("run-001", "plan-001", "planning")
        
        run = repo.get_run("run-001")
        
        assert run is not None
        assert run["run_id"] == "run-001"
    
    def test_get_run_not_found(self):
        """Test getting a non-existent run."""
        repo = RunsRepository()
        
        run = repo.get_run("nonexistent")
        
        assert run is None
    
    def test_update_run(self):
        """Test updating a run."""
        repo = RunsRepository()
        repo.create_run("run-001", "plan-001", "planning")
        
        updated = repo.update_run("run-001", status="running")
        
        assert updated["status"] == "running"
    
    def test_list_runs(self):
        """Test listing all runs."""
        repo = RunsRepository()
        repo.create_run("run-001", "plan-001", "planning")
        repo.create_run("run-002", "plan-002", "building")
        
        runs = repo.list_runs()
        
        assert len(runs) == 2
    
    def test_delete_run(self):
        """Test deleting a run."""
        repo = RunsRepository()
        repo.create_run("run-001", "plan-001", "planning")
        
        result = repo.delete_run("run-001")
        
        assert result is True
        assert repo.get_run("run-001") is None


class TestPlanService:
    """Tests for PlanService."""
    
    @pytest.fixture
    def plan_service(self, tmp_path: Path) -> PlanService:
        """Create PlanService with temp directory structure."""
        fs_service = FileSystemService.from_project_root(tmp_path)
        
        # Create specs directory structure
        pending_dir = tmp_path / ".orchestrator" / "specs" / "pending"
        pending_dir.mkdir(parents=True)
        
        # Create a test plan
        plan_dir = pending_dir / "test-plan-001"
        plan_dir.mkdir()
        spec_file = plan_dir / "spec.json"
        spec_file.write_text(json.dumps({"title": "Test Plan", "description": "A test"}))
        
        return PlanService(fs_service=fs_service)
    
    def test_list_plans(self, plan_service: PlanService):
        """Test listing plans."""
        plans = plan_service.list_plans()
        
        assert len(plans) == 1
        assert plans[0]["id"] == "test-plan-001"
        assert plans[0]["status"] == "pending"
    
    def test_get_plan(self, plan_service: PlanService):
        """Test getting a specific plan."""
        plan = plan_service.get_plan("test-plan-001")
        
        assert plan is not None
        assert plan["id"] == "test-plan-001"
        assert plan["title"] == "Test Plan"
    
    def test_get_plan_not_found(self, plan_service: PlanService):
        """Test getting non-existent plan."""
        plan = plan_service.get_plan("nonexistent")
        
        assert plan is None
    
    def test_get_plan_status(self, plan_service: PlanService):
        """Test getting plan status."""
        status = plan_service.get_plan_status("test-plan-001")
        
        assert status == "pending"
```

## Testing Strategy

| Test Type | File | What it verifies |
|-----------|------|------------------|
| Unit | tests/unit/test_services.py | FileSystemService path resolution, RunsRepository CRUD, PlanService file operations |
| Unit | tests/unit/test_portal.py | API endpoints use injected services correctly, proper HTTP responses |
| Integration | Manual via curl | End-to-end API functionality with real services |

## Validation Commands

```bash
# Run all tests
cd .orchestrator && python -m pytest tests/ -v

# Run only service tests
cd .orchestrator && python -m pytest tests/unit/test_services.py -v

# Run only portal/API tests
cd .orchestrator && python -m pytest tests/unit/test_portal.py -v

# Type checking (if mypy is configured)
cd .orchestrator && python -m mypy server/services/

# Start server and test manually
cd .orchestrator && python -m uvicorn server.app:app --reload
curl http://localhost:8000/api/plans
curl http://localhost:8000/api/runs
```

---

## Validation

```json
{
  "status": "needs_revision",
  "score": 74,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "All 12 steps have valid actions (6 create, 6 modify)",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "All steps have specific file paths (e.g., .orchestrator/server/services/__init__.py)",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": true,
      "details": "All create/modify steps include Python code blocks",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Dependency graph is valid: Phase 1 (1.1 → 1.2, 1.3, 1.4, 1.5) → Phase 2 (2.1 → 2.2, 2.3) → Phase 3 (3.1 → 3.2, 3.3). No cycles detected.",
      "severity": "critical"
    },
    {
      "name": "testing_included",
      "passed": true,
      "details": "Phase 3 includes comprehensive test modifications and new test file creation",
      "severity": "high"
    },
    {
      "name": "validation_commands",
      "passed": true,
      "details": "pytest, mypy, uvicorn, and curl commands provided for validation",
      "severity": "medium"
    },
    {
      "name": "patterns_followed",
      "passed": true,
      "details": "Uses Protocol-based interfaces, dataclasses, FastAPI Depends(), consistent with Python best practices",
      "severity": "medium"
    },
    {
      "name": "no_vague_refs",
      "passed": false,
      "details": "Step 2.2 contains vague code: '# ... workflow execution logic ...' and incomplete modifications",
      "severity": "high"
    },
    {
      "name": "phases_ordered",
      "passed": true,
      "details": "Logical ordering: Phase 1 (Foundation) → Phase 2 (Integration) → Phase 3 (Testing)",
      "severity": "medium"
    },
    {
      "name": "no_placeholders",
      "passed": false,
      "details": "Step 2.2 contains placeholder comment '# ... workflow execution logic ...' and Step 2.3 has '# ... existing exports ...'",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 2.2",
      "issue": "Contains placeholder '# ... workflow execution logic ...' which is not executable code",
      "fix_suggestion": "Provide complete implementation of _run_planning_workflow function body, showing actual workflow execution using fs_service paths"
    },
    {
      "step": "Step 2.2",
      "issue": "Shows only example endpoint modifications but doesn't specify which existing endpoints to modify or provide diff-style changes",
      "fix_suggestion": "Either provide the complete modified app.py file, or specify exact line numbers/code blocks to replace with diff markers (e.g., OLD: ... NEW: ...)"
    },
    {
      "step": "Step 2.3",
      "issue": "Contains placeholder '# ... existing exports ...' without specifying what exports exist",
      "fix_suggestion": "Read the actual .orchestrator/core/__init__.py file and provide the complete modified content including all existing exports"
    }
  ],
  "warnings": [
    {
      "step": "Step 1.5",
      "issue": "CostService imports from '...core.cost' but the existence and structure of CostReporter, BudgetManager, CostEstimator is assumed",
      "recommendation": "Verify these classes exist in .orchestrator/core/cost.py or add a prerequisite step to create them if they don't"
    },
    {
      "step": "Step 3.1",
      "issue": "Import path 'from server.services.filesystem import FileSystemService' assumes tests run with specific PYTHONPATH",
      "recommendation": "Use relative imports 'from ..server.services.filesystem' or document required PYTHONPATH setup"
    },
    {
      "step": "Step 3.2",
      "issue": "Test file modifications assume current test_portal.py structure without reading existing content first",
      "recommendation": "Read existing test_portal.py to understand current test structure and provide accurate modifications"
    },
    {
      "step": "Step 2.2",
      "issue": "Background task function _run_planning_workflow references undefined workflow execution logic",
      "recommendation": "Either implement complete workflow execution or reference existing workflow module"
    }
  ],
  "summary": "The plan has a solid structure with well-defined service interfaces, proper dependency injection patterns, and comprehensive testing. However, it fails critical validation due to placeholder comments in Step 2.2 ('... workflow execution logic ...') and Step 2.3 ('... existing exports ...'). The app.py modification step is particularly problematic as it shows only partial example code rather than complete, executable modifications. The BUILDER cannot execute code containing ellipsis placeholders. To pass validation, Step 2.2 needs complete implementation of all modified functions, and Step 2.3 needs to specify the actual existing exports. Additionally, the CostService assumes existence of core.cost module classes that should be verified."
}
```
