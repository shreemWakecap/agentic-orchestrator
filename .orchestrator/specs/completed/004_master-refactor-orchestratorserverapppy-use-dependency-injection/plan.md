# Plan: Refactor .orchestrator/server/app.py to use dependency injection. (1) Create .orchestrator/server/se

Request: Refactor .orchestrator/server/app.py to use dependency injection. (1) Create .orchestrator/server/services/ module directory. (2) Create services/interfaces.py with abstract base classes: IPlanRegistry, IFileService, IConfigService. (3) Create services/plan_registry.py implementing IPlanRegistry with methods: list_plans, get_plan, update_plan_status. (4) Create services/file_service.py implementing IFileService for file path operations. (5) Create services/config_service.py implementing IConfigService for configuration loading. (6) Create services/container.py with dependency container that provides service instances. (7) Refactor app.py routes to accept services via FastAPI Depends(). (8) Update .orchestrator/tests/unit/test_portal.py to use mock services. (9) Create test fixtures for mock services in conftest.py.
Complexity: complex

## Goal

Refactor .orchestrator/server/app.py to use dependency injection with service interfaces, implementations, DI container, and updated test infrastructure.

## Context

- Plan helpers currently inline in app.py lines 492-655
- Plan states use directories: pending, in-progress, completed, failed (note hyphen in "in-progress")
- Config files are JSON format in .orchestrator/config/ (budget.json, agent.json)
- State tracking in specs/state/*.state.json
- FastAPI Depends() pattern requires callable factories returning service instances
- Existing routes: GET /plans, GET /plan/{id}, POST /plan/{id}/status, GET /config
- Tests currently in .orchestrator/tests/unit/test_portal.py hit real file system
- pytest-mock provides mocker fixture for clean mocking

## Steps

1. Create services directory
   DO: Create the services module directory at .orchestrator/server/services/
   IN: none
   OUT: .orchestrator/server/services/ (directory)
   DONE: Directory exists
   NEEDS: none

2. Create services __init__.py with initial exports
   DO: Create module init file that will export interface classes IPlanRegistry, IFileService, IConfigService
   IN: none
   OUT: .orchestrator/server/services/__init__.py
   DONE: File exists with __all__ list placeholder
   NEEDS: 1

3. Create IPlanRegistry interface
   DO: Define abstract base class IPlanRegistry with methods list_plans() returning List[Plan], get_plan(plan_id) returning Optional[Plan], and update_status(plan_id, status) returning bool
   IN: .orchestrator/server/models.py (for Plan, PlanStatus types)
   OUT: .orchestrator/server/services/interfaces.py (partial)
   DONE: Class defined with @abstractmethod decorators on all three methods
   NEEDS: 1

4. Create IFileService interface
   DO: Add abstract base class IFileService with methods read_file(path) returning str, write_file(path, content) returning bool, and move_file(src, dest) returning bool
   IN: .orchestrator/server/services/interfaces.py
   OUT: .orchestrator/server/services/interfaces.py (extended)
   DONE: Class defined with @abstractmethod decorators on all three methods
   NEEDS: 3

5. Create IConfigService interface
   DO: Add abstract base class IConfigService with methods load_config() returning OrchestratorConfig and get_setting(key) returning Optional[Any]
   IN: .orchestrator/server/services/interfaces.py, .orchestrator/server/models.py (for OrchestratorConfig type)
   OUT: .orchestrator/server/services/interfaces.py (complete)
   DONE: Class defined with @abstractmethod decorators on both methods
   NEEDS: 4

6. Add module imports and type hints to interfaces
   DO: Add necessary imports at top of interfaces.py (abc.ABC, abc.abstractmethod, typing imports, models imports) and ensure all method signatures have proper type annotations
   IN: .orchestrator/server/services/interfaces.py
   OUT: .orchestrator/server/services/interfaces.py (finalized)
   DONE: Python syntax valid, no import errors when module loaded
   NEEDS: 5

7. Create file_service.py with path operations
   DO: Create FileService class implementing IFileService with functions for plan path resolution (get_plan_dir, get_state_file_path, list_plan_dirs), state file read/write operations, and directory existence checks using pathlib. Handle hyphenated "in-progress" directory name.
   IN: app.py:26 (ORCHESTRATOR_DIR constant), specs/ directory structure, interfaces.py
   OUT: .orchestrator/server/services/file_service.py
   DONE: FileService class implements IFileService with get_plan_dir, get_state_file_path, list_plan_dirs, read_file, write_file, move_file methods
   NEEDS: 6

8. Create plan_registry.py with list_plans
   DO: Create PlanRegistry class implementing IPlanRegistry. Extract _get_all_plans logic (app.py:532-577) into list_plans method. Should iterate pending/in-progress/completed/failed directories, parse plan.md files using _extract_plan_info logic, return list of Plan objects.
   IN: app.py:532-577 (_get_all_plans), app.py:503-530 (_extract_plan_info, _extract_plan_number), interfaces.py
   OUT: .orchestrator/server/services/plan_registry.py
   DONE: PlanRegistry.list_plans() returns list of Plan objects with id, title, status, complexity fields
   NEEDS: 7

9. Add get_plan to plan_registry.py
   DO: Extract _get_plan_by_id logic (app.py:579-624) into get_plan method of PlanRegistry class. Should locate plan by ID across all status directories, parse plan.md, return full plan details including content.
   IN: app.py:579-624 (_get_plan_by_id)
   OUT: .orchestrator/server/services/plan_registry.py (modified)
   DONE: PlanRegistry.get_plan(plan_id) returns Plan object or None if not found
   NEEDS: 8

10. Add update_status to plan_registry.py
    DO: Create update_status method in PlanRegistry class that moves plan directory between status folders (pending/in-progress/completed/failed), updates state file, handles directory rename atomically using pathlib and FileService.
    IN: file_service.py, specs/ directory structure
    OUT: .orchestrator/server/services/plan_registry.py (modified)
    DONE: PlanRegistry.update_status(plan_id, new_status) moves directory and returns success boolean
    NEEDS: 9

11. Create config_service.py for JSON config loading
    DO: Create ConfigService class implementing IConfigService with load_config method that reads JSON files from .orchestrator/config/ directory. Support loading budget.json and agent.json with caching. Include get_setting convenience method.
    IN: .orchestrator/config/budget.json, .orchestrator/config/agent.json, interfaces.py
    OUT: .orchestrator/server/services/config_service.py
    DONE: ConfigService.load_config() and get_setting(key) work with JSON config files
    NEEDS: 6

12. Create dependency container
    DO: Create container.py with factory functions get_plan_registry(), get_file_service(), and get_config_service() that return service instances, suitable for use with FastAPI Depends()
    IN: .orchestrator/server/services/plan_registry.py, .orchestrator/server/services/file_service.py, .orchestrator/server/services/config_service.py
    OUT: .orchestrator/server/services/container.py
    DONE: Factory functions are callable and return correct service types
    NEEDS: 10, 11

13. Update services package exports
    DO: Update __init__.py to export container factory functions, service classes, and interface protocols
    IN: container.py, interfaces.py, plan_registry.py, file_service.py, config_service.py
    OUT: .orchestrator/server/services/__init__.py (modified)
    DONE: All services importable via from services import get_plan_registry, get_config_service, IPlanRegistry, etc.
    NEEDS: 12

14. Verify services module imports correctly
    DO: Run Python import check to ensure services module loads without errors
    IN: .orchestrator/server/services/__init__.py
    OUT: none (validation only)
    DONE: python -c "from server.services import IPlanRegistry, IFileService, IConfigService, get_plan_registry" succeeds
    NEEDS: 13

15. Update app.py imports to use services
    DO: Add import statement for services module at top of app.py. Import get_plan_registry, get_config_service from container.
    IN: app.py, services/__init__.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Import statement present, no import errors on server start
    NEEDS: 14

16. Refactor GET /plans route
    DO: Modify GET /plans endpoint to accept IPlanRegistry via Depends(get_plan_registry) and call service.list_plans() instead of inline _get_all_plans
    IN: .orchestrator/server/app.py, .orchestrator/server/services/container.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Route uses injected service, no inline Path operations remain
    NEEDS: 15

17. Refactor GET /plan/{id} route
    DO: Modify GET /plan/{id} endpoint to accept IPlanRegistry via Depends(get_plan_registry) and call service.get_plan(id)
    IN: .orchestrator/server/app.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Route uses injected service for plan retrieval
    NEEDS: 16

18. Refactor POST /plan/{id}/status route
    DO: Modify POST /plan/{id}/status endpoint to accept IPlanRegistry via Depends(get_plan_registry) and call service.update_status(id, status)
    IN: .orchestrator/server/app.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Route uses injected service for status updates
    NEEDS: 17

19. Refactor GET /config route
    DO: Modify GET /config endpoint to accept IConfigService via Depends(get_config_service) and call service.load_config()
    IN: .orchestrator/server/app.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Route uses injected service, no inline config loading remains
    NEEDS: 18

20. Remove deprecated inline helpers from app.py
    DO: Delete the inline helper functions _get_all_plans, _get_plan_by_id, _extract_plan_info, _extract_plan_number from app.py since they are now in services
    IN: app.py
    OUT: .orchestrator/server/app.py (modified)
    DONE: Inline helper functions removed, file is shorter
    NEEDS: 19

21. Check pytest-mock dependency
    DO: Verify pytest-mock is in requirements or pyproject.toml; add if missing
    IN: requirements.txt or pyproject.toml
    OUT: Updated dependency file with pytest-mock if needed
    DONE: pip install pytest-mock succeeds or already installed
    NEEDS: none

22. Create mock services factory module
    DO: Create module with MockPlanRegistry and MockConfigService classes that return configurable test data (plans list, config dict, status updates)
    IN: .orchestrator/server/models.py (Plan, Status, Config models), interfaces.py
    OUT: .orchestrator/tests/fixtures/mock_services.py
    DONE: File exists with MockPlanRegistry, MockFileService, and MockConfigService classes
    NEEDS: 6, 21

23. Read existing conftest.py
    DO: Review current fixtures to understand existing patterns and avoid conflicts
    IN: .orchestrator/tests/conftest.py
    OUT: Understanding of existing fixture structure
    DONE: Know what fixtures exist (client, temp_dir, etc.)
    NEEDS: none

24. Add mock_plan_registry fixture to conftest.py
    DO: Create pytest fixture returning MockPlanRegistry with default test plans; allow parameterization for custom data
    IN: .orchestrator/tests/fixtures/mock_services.py, .orchestrator/tests/conftest.py
    OUT: .orchestrator/tests/conftest.py (modified with mock_plan_registry fixture)
    DONE: pytest --fixtures shows mock_plan_registry available
    NEEDS: 22, 23

25. Add mock_config_service fixture to conftest.py
    DO: Create pytest fixture returning MockConfigService with default test config; support override via fixture params
    IN: .orchestrator/tests/fixtures/mock_services.py, .orchestrator/tests/conftest.py
    OUT: .orchestrator/tests/conftest.py (modified with mock_config_service fixture)
    DONE: pytest --fixtures shows mock_config_service available
    NEEDS: 22, 23

26. Create test client fixture with mock overrides
    DO: Add fixture that creates TestClient with dependency_overrides set to use mock services
    IN: .orchestrator/tests/conftest.py, .orchestrator/server/app.py, container.py
    OUT: .orchestrator/tests/conftest.py (modified with mock_client fixture)
    DONE: mock_client fixture available and returns TestClient with mocks
    NEEDS: 20, 24, 25

27. Read current test_portal.py implementation
    DO: Analyze existing tests to identify file system dependencies and service call patterns to mock
    IN: .orchestrator/tests/unit/test_portal.py
    OUT: List of functions/calls needing mock injection
    DONE: Understand which tests need refactoring
    NEEDS: none

28. Refactor test_portal.py to use mock fixtures
    DO: Update all tests to use mock_client and mock services instead of real file system; remove direct path manipulation
    IN: .orchestrator/tests/unit/test_portal.py, conftest.py fixtures
    OUT: .orchestrator/tests/unit/test_portal.py (refactored)
    DONE: Tests no longer create/read real files; use injected mocks
    NEEDS: 26, 27

29. Run all tests to verify refactor
    DO: Execute pytest on all test files to verify everything passes with new DI pattern and mock services
    IN: .orchestrator/tests/
    OUT: Test results showing pass/fail
    DONE: pytest .orchestrator/tests/ -v passes all tests
    NEEDS: 28

## Verify

- python -c "from server.services import IPlanRegistry, IFileService, IConfigService" runs without error
- python -c "from server.services import get_plan_registry, get_config_service" succeeds
- All three interface classes inherit from abc.ABC with @abstractmethod decorators
- Type hints reference models.py Pydantic classes
- Server starts without import errors: uvicorn app:app --reload
- GET /plans endpoint returns same data as before refactor
- GET /plans/{id} endpoint returns same data as before refactor
- pytest .orchestrator/tests/ -v passes all tests
- pytest --fixtures .orchestrator/tests/ shows mock_plan_registry, mock_config_service, mock_client
- No test creates files in real .orchestrator/specs/ directory during test run
