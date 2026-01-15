# Plan: Refactor .orchestrator/server/app.py to use dependency injection. (1) Create .orchestrator/server/se

Request: Refactor .orchestrator/server/app.py to use dependency injection. (1) Create .orchestrator/server/services/ module directory. (2) Create services/interfaces.py with abstract base classes: IPlanRegistry, IFileService, IConfigService. (3) Create services/plan_registry.py implementing IPlanRegistry with methods: list_plans, get_plan, update_plan_status. (4) Create services/file_service.py implementing IFileService for file path operations. (5) Create services/config_service.py implementing IConfigService for configuration loading. (6) Create services/container.py with dependency container that provides service instances. (7) Refactor app.py routes to accept services via FastAPI Depends(). (8) Update .orchestrator/tests/unit/test_portal.py to use mock services. (9) Create test fixtures for mock services in conftest.py.
Complexity: complex

## Goal

Refactor app.py to use dependency injection with service interfaces, implementations, container, and updated tests.

## Context

- Helper functions in app.py (_get_all_plans, _get_plan_by_id, _get_recent_plans, _get_all_reviews) to be extracted into services
- Module constants (ORCHESTRATOR_DIR, PROJECT_ROOT, SPEC_DIR) to be centralized in ConfigService
- Tests currently use @patch decorators - will migrate to FastAPI dependency_overrides pattern
- Services use pathlib.Path for file operations and async patterns for I/O
- Pass paths via constructor to avoid circular imports with app.py constants

## Steps

1. Create services directory
   DO: Create empty services directory under .orchestrator/server/
   IN: none
   OUT: .orchestrator/server/services/
   DONE: Directory exists
   NEEDS: none

## Verify

- python -c "from server.services import FileService, ConfigService, PlanRegistry, Container, IPlanRegistry, IFileService, IConfigService" succeeds
- python -c "from server.app import app" succeeds without errors
- grep -r "_get_all_plans\|_get_plan_by_id\|_get_recent_plans\|_get_all_reviews\|_load_budget_config\|_load_cost_history" .orchestrator/server/app.py returns no function definitions
- grep -r "@patch.*_get_all_plans\|@patch.*_get_plan_by_id" .orchestrator/tests/ returns no matches
- pytest .orchestrator/tests/unit/test_portal.py -v passes all tests
- pytest .orchestrator/tests/unit/test_container.py -v passes all tests
- pytest .orchestrator/tests/ --tb=short passes with no failures
- Server starts and responds to health check endpoint
