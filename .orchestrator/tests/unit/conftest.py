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
