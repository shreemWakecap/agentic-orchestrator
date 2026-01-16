"""
Shared pytest fixtures for unit tests.

Provides:
- mock_input_element: Mock input element with visibility/enabled methods
- mock_visible_input: Pre-configured visible and enabled input element
- mock_hidden_input: Pre-configured hidden input element
- mock_disabled_input: Pre-configured disabled input element
- template_files: Discover all HTML template files
- parsed_templates: Parse all templates with BeautifulSoup
- dashboard_template: Parsed dashboard.html template
- plan_detail_template: Parsed plan_detail.html template
"""
from pathlib import Path
from typing import Callable

import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock


# Template directory path - shared across CSS validation tests
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "server" / "templates"


@pytest.fixture
def mock_input_element() -> Callable[[bool, bool], MagicMock]:
    """
    Factory fixture for creating mock input elements with visibility methods.

    Creates a MagicMock object with is_displayed() and is_enabled() methods,
    matching the pattern used in test_agent.py TestInputVisibility class.

    Usage:
        def test_example(mock_input_element):
            # Create visible and enabled input
            input_field = mock_input_element(is_displayed=True, is_enabled=True)
            assert input_field.is_displayed() is True
            assert input_field.is_enabled() is True

            # Create hidden input
            hidden_input = mock_input_element(is_displayed=False, is_enabled=True)
            assert hidden_input.is_displayed() is False

    Args:
        is_displayed: Whether the input is visible (default: True)
        is_enabled: Whether the input is interactable (default: True)

    Returns:
        MagicMock configured with is_displayed() and is_enabled() methods
    """
    def _create(is_displayed: bool = True, is_enabled: bool = True) -> MagicMock:
        mock_input = MagicMock()
        mock_input.is_displayed.return_value = is_displayed
        mock_input.is_enabled.return_value = is_enabled
        # Add common input attributes
        mock_input.tag_name = "input"
        mock_input.get_attribute.return_value = None
        return mock_input

    return _create


@pytest.fixture
def mock_visible_input(mock_input_element) -> MagicMock:
    """
    Pre-configured mock input element that is visible and enabled.

    This fixture provides a ready-to-use input element for tests that
    need a standard visible, interactable input field.

    Returns:
        MagicMock with is_displayed()=True and is_enabled()=True
    """
    return mock_input_element(is_displayed=True, is_enabled=True)


@pytest.fixture
def mock_hidden_input(mock_input_element) -> MagicMock:
    """
    Pre-configured mock input element that is hidden (not displayed).

    This fixture provides a hidden input element for tests that need to
    verify detection of non-visible inputs.

    Returns:
        MagicMock with is_displayed()=False and is_enabled()=True
    """
    return mock_input_element(is_displayed=False, is_enabled=True)


@pytest.fixture
def mock_disabled_input(mock_input_element) -> MagicMock:
    """
    Pre-configured mock input element that is visible but disabled.

    This fixture provides a disabled input element for tests that need to
    verify detection of non-interactable inputs.

    Returns:
        MagicMock with is_displayed()=True and is_enabled()=False
    """
    return mock_input_element(is_displayed=True, is_enabled=False)


@pytest.fixture
def mock_hidden_disabled_input(mock_input_element) -> MagicMock:
    """
    Pre-configured mock input element that is both hidden and disabled.

    This fixture provides a completely non-interactable input element
    for edge case testing.

    Returns:
        MagicMock with is_displayed()=False and is_enabled()=False
    """
    return mock_input_element(is_displayed=False, is_enabled=False)


# ============================================================================
# Template Parsing Fixtures for CSS Validation Tests
# ============================================================================


@pytest.fixture
def template_files() -> list[Path]:
    """Discover all HTML template files in the templates directory.

    This fixture provides a list of all .html files found in the server/templates
    directory. Used by CSS validation tests to ensure all templates are tested.

    Returns:
        List of Path objects for each HTML template file.

    Example:
        def test_all_templates(template_files):
            for template_path in template_files:
                # Process each template
                pass
    """
    if not TEMPLATES_DIR.exists():
        return []
    return list(TEMPLATES_DIR.glob("*.html"))


@pytest.fixture
def parsed_templates(template_files: list[Path]) -> dict[str, BeautifulSoup]:
    """Parse all HTML templates using BeautifulSoup.

    This fixture provides parsed BeautifulSoup objects for all templates,
    enabling CSS class validation and DOM structure testing across all
    templates in a single test.

    Args:
        template_files: List of template file paths (injected fixture).

    Returns:
        Dictionary mapping template name (e.g., 'dashboard.html') to
        its parsed BeautifulSoup object.

    Example:
        def test_buttons_across_templates(parsed_templates):
            for template_name, soup in parsed_templates.items():
                buttons = soup.find_all('button')
                # Validate button classes
    """
    templates = {}
    for template_path in template_files:
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
            templates[template_path.name] = BeautifulSoup(content, "html.parser")
        except (FileNotFoundError, UnicodeDecodeError):
            # Skip files that can't be read
            continue
    return templates


@pytest.fixture
def dashboard_template() -> BeautifulSoup | None:
    """Parse the dashboard template specifically for form element tests.

    The dashboard template contains the main form input element and
    primary action buttons. This fixture provides direct access for
    focused testing on the dashboard's form elements.

    Returns:
        BeautifulSoup object for dashboard.html template, or None if not found.

    Example:
        def test_dashboard_input(dashboard_template):
            input_elem = dashboard_template.find('input', {'type': 'text'})
            assert 'border' in input_elem.get('class', [])
    """
    dashboard_path = TEMPLATES_DIR / "dashboard.html"
    if not dashboard_path.exists():
        return None
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
    return BeautifulSoup(content, "html.parser")


@pytest.fixture
def plan_detail_template() -> BeautifulSoup | None:
    """Parse the plan detail template for button and status tests.

    The plan_detail template contains primary action buttons (Start Build,
    Start Review) and secondary navigation buttons (Back to Plans).
    This fixture provides direct access for button styling validation.

    Returns:
        BeautifulSoup object for plan_detail.html template, or None if not found.

    Example:
        def test_plan_detail_buttons(plan_detail_template):
            buttons = plan_detail_template.find_all('button')
            for btn in buttons:
                assert 'rounded-md' in btn.get('class', [])
    """
    plan_detail_path = TEMPLATES_DIR / "plan_detail.html"
    if not plan_detail_path.exists():
        return None
    with open(plan_detail_path, "r", encoding="utf-8") as f:
        content = f.read()
    return BeautifulSoup(content, "html.parser")


@pytest.fixture
def base_template() -> BeautifulSoup | None:
    """Parse the base template for navigation and layout tests.

    The base template contains the navigation bar, common layout structure,
    and base styling that all other templates inherit from.

    Returns:
        BeautifulSoup object for base.html template, or None if not found.
    """
    base_path = TEMPLATES_DIR / "base.html"
    if not base_path.exists():
        return None
    with open(base_path, "r", encoding="utf-8") as f:
        content = f.read()
    return BeautifulSoup(content, "html.parser")


# ============================================================================
# Service Interface Mock Fixtures for Dependency Injection Tests
# ============================================================================
# These fixtures provide mock implementations of all service interfaces
# defined in .orchestrator/server/services/interfaces.py for testing
# components that depend on these services.
# ============================================================================


@pytest.fixture
def mock_plan_registry() -> MagicMock:
    """
    Mock implementation of IPlanRegistry interface for plan management.

    Provides mock methods for:
    - get_all_plans(): Returns list of all plans
    - get_plan_by_id(plan_id): Returns specific plan or None
    - get_recent_plans(limit): Returns most recent plans
    - get_plan_counts(): Returns counts by state
    - get_plan_file_content(plan_id, filename): Returns file content

    Usage:
        def test_dashboard(mock_plan_registry):
            mock_plan_registry.get_plan_counts.return_value = {
                "pending": 5, "in_progress": 2, "completed": 10, "failed": 1
            }
            # Test dashboard rendering with these counts

    Returns:
        MagicMock configured with IPlanRegistry interface methods
    """
    mock = MagicMock()

    # Default return values for plan registry methods
    mock.get_all_plans.return_value = []
    mock.get_plan_by_id.return_value = None
    mock.get_recent_plans.return_value = []
    mock.get_plan_counts.return_value = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0
    }
    mock.get_plan_file_content.return_value = None

    return mock


@pytest.fixture
def mock_plan_registry_with_data() -> MagicMock:
    """
    Mock IPlanRegistry pre-populated with sample plan data.

    Useful for tests that need realistic plan data without file system access.

    Returns:
        MagicMock with sample plans configured
    """
    mock = MagicMock()

    sample_plans = [
        {
            "id": "001_feature-auth",
            "name": "User Authentication Feature",
            "state": "completed",
            "file": "/specs/completed/001_feature-auth",
            "files": ["plan.md", "implementation.md"],
            "modified": "2024-01-15T10:30:00",
            "request": "Add user authentication",
            "complexity": "medium"
        },
        {
            "id": "002_api-refactor",
            "name": "API Refactoring",
            "state": "in-progress",
            "file": "/specs/in-progress/002_api-refactor",
            "files": ["plan.md"],
            "modified": "2024-01-16T14:00:00",
            "request": "Refactor REST API endpoints",
            "complexity": "high"
        },
        {
            "id": "003_bug-fix",
            "name": "Bug Fix for Login",
            "state": "pending",
            "file": "/specs/pending/003_bug-fix",
            "files": ["plan.md"],
            "modified": "2024-01-17T09:00:00",
            "request": "Fix login redirect issue",
            "complexity": "low"
        }
    ]

    mock.get_all_plans.return_value = sample_plans
    mock.get_plan_by_id.side_effect = lambda pid: next(
        (p for p in sample_plans if p["id"] == pid), None
    )
    mock.get_recent_plans.side_effect = lambda limit: sample_plans[:limit]
    mock.get_plan_counts.return_value = {
        "pending": 1,
        "in_progress": 1,
        "completed": 1,
        "failed": 0
    }
    mock.get_plan_file_content.return_value = "# Sample Plan Content\n\nThis is mock content."

    return mock


@pytest.fixture
def mock_file_service() -> MagicMock:
    """
    Mock implementation of IFileService interface for file operations.

    Provides mock methods for:
    - read_file(path): Read file content
    - write_file(path, content): Write content to file
    - file_exists(path): Check if file exists
    - list_directory(path): List directory contents
    - create_directory(path): Create directory
    - get_file_modified_time(path): Get file modification time

    Usage:
        def test_plan_loading(mock_file_service):
            mock_file_service.read_file.return_value = "# Plan Content"
            mock_file_service.file_exists.return_value = True
            # Test plan loading behavior

    Returns:
        MagicMock configured with IFileService interface methods
    """
    mock = MagicMock()

    # Default return values
    mock.read_file.return_value = ""
    mock.write_file.return_value = True
    mock.file_exists.return_value = False
    mock.list_directory.return_value = []
    mock.create_directory.return_value = True
    mock.get_file_modified_time.return_value = "2024-01-15T10:00:00"

    return mock


@pytest.fixture
def mock_config_service() -> MagicMock:
    """
    Mock implementation of IConfigService interface for configuration.

    Provides mock methods for:
    - get_config(key): Get configuration value
    - set_config(key, value): Set configuration value
    - get_all_config(): Get all configuration
    - get_project_root(): Get project root path
    - get_specs_dir(): Get specs directory path
    - get_templates_dir(): Get templates directory path

    Usage:
        def test_workflow_config(mock_config_service):
            mock_config_service.get_config.return_value = {"timeout": 300}
            # Test workflow with custom config

    Returns:
        MagicMock configured with IConfigService interface methods
    """
    mock = MagicMock()

    default_config = {
        "timeout": 300,
        "max_retries": 3,
        "debug": False
    }

    mock.get_config.side_effect = lambda key, default=None: default_config.get(key, default)
    mock.set_config.return_value = True
    mock.get_all_config.return_value = default_config
    mock.get_project_root.return_value = Path("/mock/project/root")
    mock.get_specs_dir.return_value = Path("/mock/project/root/.orchestrator/specs")
    mock.get_templates_dir.return_value = Path("/mock/project/root/.orchestrator/server/templates")

    return mock


@pytest.fixture
def mock_cost_service() -> MagicMock:
    """
    Mock implementation of ICostService interface for cost tracking.

    Provides mock methods for:
    - estimate_planning(request_length, complexity): Estimate planning cost
    - estimate_building(plan_path): Estimate building cost
    - get_daily_report(): Get daily cost report
    - get_weekly_report(): Get weekly cost report
    - get_monthly_report(): Get monthly cost report
    - get_cost_summary(): Get overall cost summary
    - record_cost(workflow, tokens, cost): Record actual cost

    Usage:
        def test_cost_display(mock_cost_service):
            mock_cost_service.get_cost_summary.return_value = {
                "total_cost": 15.50, "total_tokens": 500000
            }
            # Test cost summary display

    Returns:
        MagicMock configured with ICostService interface methods
    """
    mock = MagicMock()

    # Default cost estimate
    default_estimate = {
        "estimated_tokens": 10000,
        "estimated_cost": 0.50,
        "confidence": "medium",
        "breakdown": {
            "input_tokens": 8000,
            "output_tokens": 2000
        }
    }

    mock.estimate_planning.return_value = default_estimate
    mock.estimate_building.return_value = default_estimate
    mock.get_daily_report.return_value = {"total_cost": 5.00, "workflows": 10}
    mock.get_weekly_report.return_value = {"total_cost": 25.00, "workflows": 50}
    mock.get_monthly_report.return_value = {"total_cost": 100.00, "workflows": 200}
    mock.get_cost_summary.return_value = {
        "daily": {"total_cost": 5.00},
        "weekly": {"total_cost": 25.00},
        "monthly": {"total_cost": 100.00}
    }
    mock.record_cost.return_value = True

    return mock


@pytest.fixture
def mock_budget_service() -> MagicMock:
    """
    Mock implementation of IBudgetService interface for budget management.

    Provides mock methods for:
    - get_budget(): Get current budget settings
    - set_budget(budget): Update budget settings
    - get_remaining_budget(): Get remaining budget amounts
    - check_budget_available(estimated_cost): Check if budget allows operation
    - get_budget_alerts(): Get any budget warning/alerts

    Usage:
        def test_budget_check(mock_budget_service):
            mock_budget_service.check_budget_available.return_value = True
            # Test workflow proceeds when budget available

    Returns:
        MagicMock configured with IBudgetService interface methods
    """
    mock = MagicMock()

    default_budget = {
        "daily_limit": 10.00,
        "weekly_limit": 50.00,
        "monthly_limit": 200.00,
        "per_workflow_limit": 5.00
    }

    default_remaining = {
        "daily_remaining": 5.00,
        "weekly_remaining": 25.00,
        "monthly_remaining": 100.00
    }

    mock.get_budget.return_value = default_budget
    mock.set_budget.return_value = True
    mock.get_remaining_budget.return_value = default_remaining
    mock.check_budget_available.return_value = True
    mock.get_budget_alerts.return_value = []

    return mock


@pytest.fixture
def mock_run_manager() -> MagicMock:
    """
    Mock implementation of IRunManager interface for workflow run management.

    Provides mock methods for:
    - create_run(workflow_type, metadata): Create new run entry
    - get_run(run_id): Get run by ID
    - get_all_runs(): Get all runs
    - update_run_status(run_id, status): Update run status
    - add_run_event(run_id, event): Add event to run
    - complete_run(run_id, result): Mark run as complete
    - fail_run(run_id, error): Mark run as failed

    Usage:
        def test_workflow_tracking(mock_run_manager):
            mock_run_manager.create_run.return_value = "run-123"
            # Test run creation and tracking

    Returns:
        MagicMock configured with IRunManager interface methods
    """
    mock = MagicMock()

    sample_run = {
        "id": "abc12345",
        "workflow": "planning",
        "status": "running",
        "started_at": "2024-01-16T10:00:00",
        "progress": 50,
        "current_step": "analyzing",
        "events": [],
        "output_file": None,
        "error": None
    }

    mock.create_run.return_value = "abc12345"
    mock.get_run.return_value = sample_run
    mock.get_all_runs.return_value = [sample_run]
    mock.update_run_status.return_value = True
    mock.add_run_event.return_value = True
    mock.complete_run.return_value = True
    mock.fail_run.return_value = True

    return mock


@pytest.fixture
def mock_workflow_service() -> MagicMock:
    """
    Mock implementation of IWorkflowService interface for workflow execution.

    Provides mock methods for:
    - run_planning(description): Execute planning workflow
    - run_building(plan_path): Execute building workflow
    - run_syncing(): Execute syncing workflow
    - get_workflow_status(run_id): Get workflow execution status

    Usage:
        def test_planning_workflow(mock_workflow_service):
            mock_workflow_service.run_planning.return_value = {
                "success": True, "output_file": "/path/to/plan.md"
            }
            # Test planning workflow execution

    Returns:
        MagicMock configured with IWorkflowService interface methods
    """
    mock = MagicMock()

    planning_result = {
        "success": True,
        "output_file": "/specs/pending/001_new-feature/plan.md",
        "total_tokens": 15000
    }

    building_result = {
        "success": True,
        "output_file": "/specs/completed/001_new-feature/plan.md",
        "steps_completed": 5
    }

    syncing_result = {
        "success": True,
        "output_file": None,
        "data": {"pr_url": "https://github.com/org/repo/pull/123"}
    }

    mock.run_planning.return_value = planning_result
    mock.run_building.return_value = building_result
    mock.run_syncing.return_value = syncing_result
    mock.get_workflow_status.return_value = {"status": "completed", "progress": 100}

    return mock


@pytest.fixture
def mock_template_service() -> MagicMock:
    """
    Mock implementation of ITemplateService interface for template rendering.

    Provides mock methods for:
    - render_template(name, context): Render template with context
    - get_template(name): Get raw template content
    - template_exists(name): Check if template exists

    Usage:
        def test_dashboard_render(mock_template_service):
            mock_template_service.render_template.return_value = "<html>...</html>"
            # Test dashboard rendering

    Returns:
        MagicMock configured with ITemplateService interface methods
    """
    mock = MagicMock()

    mock.render_template.return_value = "<html><body>Mock Template</body></html>"
    mock.get_template.return_value = "{% block content %}{% endblock %}"
    mock.template_exists.return_value = True

    return mock


# ============================================================================
# Service Container Fixture for Full Dependency Injection Testing
# ============================================================================


@pytest.fixture
def mock_service_container(
    mock_plan_registry,
    mock_file_service,
    mock_config_service,
    mock_cost_service,
    mock_budget_service,
    mock_run_manager,
    mock_workflow_service,
    mock_template_service
) -> MagicMock:
    """
    Mock service container providing all service dependencies.

    This fixture aggregates all individual service mocks into a single
    container object, mimicking the dependency injection container used
    in the application. Use this for integration-style tests that need
    multiple services.

    Usage:
        def test_full_workflow(mock_service_container):
            container = mock_service_container
            container.plan_registry.get_all_plans.return_value = [...]
            container.cost_service.estimate_planning.return_value = {...}
            # Test with multiple services configured

    Returns:
        MagicMock with all service interfaces as attributes
    """
    container = MagicMock()

    container.plan_registry = mock_plan_registry
    container.file_service = mock_file_service
    container.config_service = mock_config_service
    container.cost_service = mock_cost_service
    container.budget_service = mock_budget_service
    container.run_manager = mock_run_manager
    container.workflow_service = mock_workflow_service
    container.template_service = mock_template_service

    # Convenience method to get service by name
    def get_service(name: str):
        return getattr(container, name, None)

    container.get_service = get_service

    return container


# ============================================================================
# Factory Fixtures for Creating Custom Service Mocks
# ============================================================================


@pytest.fixture
def create_mock_plan() -> Callable[..., dict]:
    """
    Factory fixture for creating custom mock plan dictionaries.

    Usage:
        def test_plan_processing(create_mock_plan):
            plan = create_mock_plan(
                plan_id="001_my-feature",
                state="pending",
                complexity="high"
            )
            assert plan["id"] == "001_my-feature"

    Returns:
        Factory function for creating plan dictionaries
    """
    def _create(
        plan_id: str = "001_test-plan",
        name: str = "Test Plan",
        state: str = "pending",
        complexity: str = "medium",
        request: str = "Test request",
        content: str = "# Test Plan\n\nPlan content here.",
        files: list = None
    ) -> dict:
        return {
            "id": plan_id,
            "name": name,
            "state": state,
            "file": f"/specs/{state}/{plan_id}",
            "files": files or ["plan.md"],
            "modified": "2024-01-15T10:00:00",
            "request": request,
            "complexity": complexity,
            "content": content
        }

    return _create


@pytest.fixture
def create_mock_run() -> Callable[..., dict]:
    """
    Factory fixture for creating custom mock run dictionaries.

    Usage:
        def test_run_tracking(create_mock_run):
            run = create_mock_run(
                run_id="xyz789",
                workflow="building",
                status="completed"
            )
            assert run["status"] == "completed"

    Returns:
        Factory function for creating run dictionaries
    """
    def _create(
        run_id: str = "abc12345",
        workflow: str = "planning",
        status: str = "pending",
        progress: int = 0,
        description: str = None,
        plan_path: str = None,
        error: str = None
    ) -> dict:
        run = {
            "id": run_id,
            "workflow": workflow,
            "status": status,
            "started_at": "2024-01-16T10:00:00",
            "progress": progress,
            "current_step": None,
            "events": [],
            "output_file": None,
            "error": error
        }

        if description:
            run["description"] = description
        if plan_path:
            run["plan_path"] = plan_path

        return run

    return _create


@pytest.fixture
def create_mock_cost_estimate() -> Callable[..., dict]:
    """
    Factory fixture for creating custom cost estimate dictionaries.

    Usage:
        def test_cost_estimate(create_mock_cost_estimate):
            estimate = create_mock_cost_estimate(
                tokens=50000,
                cost=2.50,
                confidence="high"
            )
            assert estimate["estimated_cost"] == 2.50

    Returns:
        Factory function for creating cost estimate dictionaries
    """
    def _create(
        tokens: int = 10000,
        cost: float = 0.50,
        confidence: str = "medium",
        input_tokens: int = None,
        output_tokens: int = None
    ) -> dict:
        input_t = input_tokens or int(tokens * 0.8)
        output_t = output_tokens or int(tokens * 0.2)

        return {
            "estimated_tokens": tokens,
            "estimated_cost": cost,
            "confidence": confidence,
            "breakdown": {
                "input_tokens": input_t,
                "output_tokens": output_t
            }
        }

    return _create
