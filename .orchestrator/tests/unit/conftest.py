"""
Shared pytest fixtures for unit tests.

Provides:
- mock_input_element: Mock input element with visibility/enabled methods
- mock_visible_input: Pre-configured visible and enabled input element
- mock_hidden_input: Pre-configured hidden input element
- mock_disabled_input: Pre-configured disabled input element
"""
from typing import Callable
from unittest.mock import MagicMock

import pytest


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
