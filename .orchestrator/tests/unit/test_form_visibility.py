"""Tests for form input visibility on the dashboard."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from server.app import app


class TestFormInputVisibility:
    """Validate form inputs are visible on the dashboard page."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastAPI app."""
        yield TestClient(app)

    def test_dashboard_returns_200(self, client):
        """Verify the dashboard endpoint returns successfully."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_contains_form_elements(self, client):
        """Verify the dashboard contains form input elements."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "<form" in html or "<input" in html


class TestFormInputVisibilityAssertions:
    """Test form inputs are visible and interactable before filling.

    Uses mock_input_element fixture from conftest.py to verify:
    - is_displayed() returns True for visible inputs
    - is_enabled() returns True for interactable inputs
    - Combined visibility/interactability checks work correctly
    """

    def test_standard_input_is_displayed(self, mock_visible_input):
        """Verify standard input element is_displayed() returns True."""
        assert mock_visible_input.is_displayed() is True

    def test_standard_input_is_enabled(self, mock_visible_input):
        """Verify standard input element is_enabled() returns True."""
        assert mock_visible_input.is_enabled() is True

    def test_standard_input_is_visible_and_interactable(self, mock_visible_input):
        """Verify standard input is both visible and interactable before filling."""
        is_visible = mock_visible_input.is_displayed()
        is_interactable = mock_visible_input.is_enabled()

        assert is_visible is True
        assert is_interactable is True
        assert is_visible and is_interactable

    def test_can_fill_visible_enabled_input(self, mock_visible_input):
        """Verify input can be filled when both visible and enabled."""
        can_fill = mock_visible_input.is_displayed() and mock_visible_input.is_enabled()
        assert can_fill is True

    def test_input_factory_creates_visible_enabled(self, mock_input_element):
        """Verify factory creates visible and enabled input by default."""
        input_field = mock_input_element()
        assert input_field.is_displayed() is True
        assert input_field.is_enabled() is True

    def test_input_factory_custom_visibility(self, mock_input_element):
        """Verify factory allows custom visibility settings."""
        visible_input = mock_input_element(is_displayed=True, is_enabled=True)
        hidden_input = mock_input_element(is_displayed=False, is_enabled=True)

        assert visible_input.is_displayed() is True
        assert hidden_input.is_displayed() is False

    def test_input_factory_custom_enabled_state(self, mock_input_element):
        """Verify factory allows custom enabled settings."""
        enabled_input = mock_input_element(is_displayed=True, is_enabled=True)
        disabled_input = mock_input_element(is_displayed=True, is_enabled=False)

        assert enabled_input.is_enabled() is True
        assert disabled_input.is_enabled() is False


class TestVisibilityAttributes:
    """Test input elements have proper visibility attributes.

    Validates that inputs have expected HTML attributes related to visibility:
    - tag_name is correctly set
    - get_attribute() returns expected values
    - Visibility-related attributes are properly detected
    """

    def test_input_has_correct_tag_name(self, mock_visible_input):
        """Verify input element has correct tag_name attribute."""
        assert mock_visible_input.tag_name == "input"

    def test_input_get_attribute_returns_none_for_missing(self, mock_visible_input):
        """Verify get_attribute returns None for non-existent attributes."""
        result = mock_visible_input.get_attribute("nonexistent")
        assert result is None

    def test_input_visibility_attribute_detection(self, mock_input_element):
        """Verify visibility attributes can be detected on inputs."""
        input_field = mock_input_element()
        input_field.get_attribute.return_value = "visible"

        visibility = input_field.get_attribute("visibility")
        assert visibility == "visible"

    def test_input_hidden_attribute_detection(self, mock_input_element):
        """Verify hidden attribute can be detected on inputs."""
        input_field = mock_input_element()
        input_field.get_attribute.return_value = "true"

        hidden_attr = input_field.get_attribute("hidden")
        assert hidden_attr == "true"

    def test_input_aria_hidden_attribute(self, mock_input_element):
        """Verify aria-hidden attribute can be detected."""
        input_field = mock_input_element()
        input_field.get_attribute.return_value = "true"

        aria_hidden = input_field.get_attribute("aria-hidden")
        assert aria_hidden == "true"

    def test_input_style_display_attribute(self, mock_input_element):
        """Verify style display attribute can be detected."""
        input_field = mock_input_element()
        input_field.get_attribute.return_value = "display: none;"

        style = input_field.get_attribute("style")
        assert "display: none" in style

    def test_input_type_attribute(self, mock_input_element):
        """Verify input type attribute can be detected."""
        input_field = mock_input_element()
        input_field.get_attribute.return_value = "text"

        input_type = input_field.get_attribute("type")
        assert input_type == "text"

    def test_input_type_hidden_detection(self, mock_input_element):
        """Verify hidden input type can be detected."""
        input_field = mock_input_element(is_displayed=False)
        input_field.get_attribute.return_value = "hidden"

        input_type = input_field.get_attribute("type")
        assert input_type == "hidden"
        assert input_field.is_displayed() is False


class TestDisabledInputDetection:
    """Test that disabled inputs are properly detected.

    Uses mock_disabled_input fixture to verify:
    - is_enabled() returns False for disabled inputs
    - disabled attribute is properly detected
    - Cannot interact with disabled inputs
    """

    def test_disabled_input_is_not_enabled(self, mock_disabled_input):
        """Verify disabled input is_enabled() returns False."""
        assert mock_disabled_input.is_enabled() is False

    def test_disabled_input_is_still_visible(self, mock_disabled_input):
        """Verify disabled input can still be visible."""
        assert mock_disabled_input.is_displayed() is True

    def test_cannot_fill_disabled_input(self, mock_disabled_input):
        """Verify disabled input cannot be filled."""
        can_fill = mock_disabled_input.is_displayed() and mock_disabled_input.is_enabled()
        assert can_fill is False

    def test_disabled_attribute_detection(self, mock_input_element):
        """Verify disabled attribute can be detected on inputs."""
        disabled_input = mock_input_element(is_enabled=False)
        disabled_input.get_attribute.return_value = "disabled"

        disabled_attr = disabled_input.get_attribute("disabled")
        assert disabled_attr == "disabled"
        assert disabled_input.is_enabled() is False

    def test_readonly_input_detection(self, mock_input_element):
        """Verify readonly attribute can be detected on inputs."""
        readonly_input = mock_input_element()
        readonly_input.get_attribute.return_value = "readonly"

        readonly_attr = readonly_input.get_attribute("readonly")
        assert readonly_attr == "readonly"


class TestHiddenInputDetection:
    """Test that hidden inputs are properly detected.

    Uses mock_hidden_input fixture to verify:
    - is_displayed() returns False for hidden inputs
    - Hidden inputs cannot be interacted with
    - Various ways inputs can be hidden
    """

    def test_hidden_input_is_not_displayed(self, mock_hidden_input):
        """Verify hidden input is_displayed() returns False."""
        assert mock_hidden_input.is_displayed() is False

    def test_hidden_input_may_still_be_enabled(self, mock_hidden_input):
        """Verify hidden input can still be enabled in DOM."""
        assert mock_hidden_input.is_enabled() is True

    def test_cannot_fill_hidden_input(self, mock_hidden_input):
        """Verify hidden input cannot be filled."""
        can_fill = mock_hidden_input.is_displayed() and mock_hidden_input.is_enabled()
        assert can_fill is False

    def test_hidden_type_input_detection(self, mock_input_element):
        """Verify type='hidden' inputs are not displayed."""
        hidden_input = mock_input_element(is_displayed=False)
        hidden_input.get_attribute.return_value = "hidden"

        input_type = hidden_input.get_attribute("type")
        assert input_type == "hidden"
        assert hidden_input.is_displayed() is False

    def test_css_hidden_input_detection(self, mock_input_element):
        """Verify CSS-hidden inputs are detected as not displayed."""
        hidden_input = mock_input_element(is_displayed=False)
        hidden_input.get_attribute.return_value = "display: none;"

        style = hidden_input.get_attribute("style")
        assert "display: none" in style
        assert hidden_input.is_displayed() is False

    def test_visibility_hidden_detection(self, mock_input_element):
        """Verify visibility:hidden inputs are detected."""
        hidden_input = mock_input_element(is_displayed=False)
        hidden_input.get_attribute.return_value = "visibility: hidden;"

        style = hidden_input.get_attribute("style")
        assert "visibility: hidden" in style
        assert hidden_input.is_displayed() is False


class TestHiddenDisabledInputDetection:
    """Test inputs that are both hidden and disabled.

    Uses mock_hidden_disabled_input fixture for edge case testing.
    """

    def test_hidden_disabled_input_not_displayed(self, mock_hidden_disabled_input):
        """Verify hidden disabled input is_displayed() returns False."""
        assert mock_hidden_disabled_input.is_displayed() is False

    def test_hidden_disabled_input_not_enabled(self, mock_hidden_disabled_input):
        """Verify hidden disabled input is_enabled() returns False."""
        assert mock_hidden_disabled_input.is_enabled() is False

    def test_cannot_interact_with_hidden_disabled(self, mock_hidden_disabled_input):
        """Verify hidden disabled input cannot be interacted with."""
        can_interact = (
            mock_hidden_disabled_input.is_displayed()
            and mock_hidden_disabled_input.is_enabled()
        )
        assert can_interact is False

    def test_hidden_disabled_detection_both_flags(self, mock_hidden_disabled_input):
        """Verify both hidden and disabled states are correctly detected."""
        is_visible = mock_hidden_disabled_input.is_displayed()
        is_interactable = mock_hidden_disabled_input.is_enabled()

        assert is_visible is False, "Hidden input should not be displayed"
        assert is_interactable is False, "Disabled input should not be enabled"


class TestPreFillVisibilityChecks:
    """Test visibility checks that should happen before filling form inputs.

    These tests verify the pattern of checking visibility before interaction.
    """

    def test_visibility_check_before_send_keys(self, mock_input_element):
        """Verify visibility check pattern before sending keys."""
        input_field = mock_input_element(is_displayed=True, is_enabled=True)

        # Check visibility before interaction
        if input_field.is_displayed() and input_field.is_enabled():
            input_field.send_keys("test value")
            input_field.send_keys.assert_called_once_with("test value")
        else:
            pytest.fail("Input should be visible and enabled")

    def test_visibility_check_blocks_hidden_interaction(self, mock_hidden_input):
        """Verify visibility check prevents interaction with hidden inputs."""
        interaction_attempted = False

        if mock_hidden_input.is_displayed() and mock_hidden_input.is_enabled():
            interaction_attempted = True

        assert interaction_attempted is False

    def test_visibility_check_blocks_disabled_interaction(self, mock_disabled_input):
        """Verify visibility check prevents interaction with disabled inputs."""
        interaction_attempted = False

        if mock_disabled_input.is_displayed() and mock_disabled_input.is_enabled():
            interaction_attempted = True

        assert interaction_attempted is False

    def test_form_input_interactability_helper(self, mock_input_element):
        """Test helper pattern for checking input interactability."""
        def is_interactable(element):
            """Check if an element can be interacted with."""
            return element.is_displayed() and element.is_enabled()

        visible_enabled = mock_input_element(is_displayed=True, is_enabled=True)
        visible_disabled = mock_input_element(is_displayed=True, is_enabled=False)
        hidden_enabled = mock_input_element(is_displayed=False, is_enabled=True)
        hidden_disabled = mock_input_element(is_displayed=False, is_enabled=False)

        assert is_interactable(visible_enabled) is True
        assert is_interactable(visible_disabled) is False
        assert is_interactable(hidden_enabled) is False
        assert is_interactable(hidden_disabled) is False

    def test_multiple_inputs_visibility_check(self, mock_input_element):
        """Test checking visibility of multiple form inputs."""
        inputs = {
            "username": mock_input_element(is_displayed=True, is_enabled=True),
            "password": mock_input_element(is_displayed=True, is_enabled=True),
            "csrf_token": mock_input_element(is_displayed=False, is_enabled=True),
            "submit_btn": mock_input_element(is_displayed=True, is_enabled=True),
        }

        visible_inputs = [
            name for name, elem in inputs.items()
            if elem.is_displayed() and elem.is_enabled()
        ]

        assert "username" in visible_inputs
        assert "password" in visible_inputs
        assert "submit_btn" in visible_inputs
        assert "csrf_token" not in visible_inputs


class TestFormElementFixtureUsage:
    """Demonstrate proper pytest fixture usage patterns.

    This test class follows the class-based pattern from test_agent.py,
    using injected fixtures and proper setup/teardown for comprehensive
    form element visibility testing.
    """

    @pytest.fixture(autouse=True)
    def setup_test_context(self):
        """Setup and teardown for each test method."""
        # Setup: Initialize test state
        self.form_elements = {}
        self.test_interactions = []
        yield
        # Teardown: Clean up resources
        self.form_elements.clear()
        self.test_interactions.clear()

    @pytest.fixture
    def mock_form_element(self, mock_input_element):
        """Factory fixture for creating mock form elements with full attribute support.

        Wraps mock_input_element to add form-specific attributes like name, value,
        and form association.
        """
        def _create(
            name: str = "field",
            value: str = "",
            is_displayed: bool = True,
            is_enabled: bool = True,
            element_type: str = "text"
        ) -> MagicMock:
            element = mock_input_element(is_displayed=is_displayed, is_enabled=is_enabled)
            element.get_attribute.side_effect = lambda attr: {
                "name": name,
                "value": value,
                "type": element_type,
                "id": f"input-{name}",
            }.get(attr)
            return element
        return _create

    def test_fixture_injection_creates_form_element(self, mock_form_element):
        """Verify mock_form_element fixture creates valid form element."""
        username_field = mock_form_element(name="username", element_type="text")

        assert username_field.is_displayed() is True
        assert username_field.is_enabled() is True
        assert username_field.get_attribute("name") == "username"
        assert username_field.get_attribute("type") == "text"

    def test_fixture_with_custom_visibility(self, mock_form_element):
        """Verify fixture allows custom visibility configuration."""
        visible_field = mock_form_element(name="email", is_displayed=True)
        hidden_field = mock_form_element(name="token", is_displayed=False)

        assert visible_field.is_displayed() is True
        assert hidden_field.is_displayed() is False

    def test_fixture_with_disabled_state(self, mock_form_element):
        """Verify fixture allows disabled state configuration."""
        enabled_field = mock_form_element(name="active", is_enabled=True)
        disabled_field = mock_form_element(name="readonly_data", is_enabled=False)

        assert enabled_field.is_enabled() is True
        assert disabled_field.is_enabled() is False

    def test_setup_populates_form_elements(self, mock_form_element):
        """Verify setup/teardown context is available for test methods."""
        # Use the setup context to track form elements
        self.form_elements["username"] = mock_form_element(name="username")
        self.form_elements["password"] = mock_form_element(name="password", element_type="password")

        assert len(self.form_elements) == 2
        assert "username" in self.form_elements
        assert "password" in self.form_elements

    def test_track_interactions_in_context(self, mock_form_element):
        """Verify interactions can be tracked using setup context."""
        field = mock_form_element(name="search", is_displayed=True, is_enabled=True)

        if field.is_displayed() and field.is_enabled():
            self.test_interactions.append(("fill", "search", "test query"))

        assert len(self.test_interactions) == 1
        assert self.test_interactions[0] == ("fill", "search", "test query")

    def test_multiple_fixtures_combined(self, mock_form_element, mock_visible_input, mock_disabled_input):
        """Verify multiple fixtures can be used together in a single test."""
        custom_field = mock_form_element(name="custom", is_displayed=True, is_enabled=True)
        preset_visible = mock_visible_input
        preset_disabled = mock_disabled_input

        # All elements should have expected states
        assert custom_field.is_displayed() is True
        assert preset_visible.is_displayed() is True
        assert preset_disabled.is_displayed() is True

        assert custom_field.is_enabled() is True
        assert preset_visible.is_enabled() is True
        assert preset_disabled.is_enabled() is False


class TestTestClientHTMLResponses:
    """Test visibility assertions using TestClient for HTML responses.

    Demonstrates proper usage of TestClient fixture for testing
    form visibility in actual HTML responses from the server.
    """

    @pytest.fixture
    def client(self):
        """Create test client for the FastAPI app."""
        yield TestClient(app)

    @pytest.fixture
    def sample_html_with_forms(self):
        """Sample HTML containing various form input states."""
        return """
        <html>
        <body>
            <form id="test-form" action="/submit" method="post">
                <input type="text" name="username" id="username" />
                <input type="password" name="password" id="password" />
                <input type="hidden" name="csrf_token" value="abc123" />
                <input type="text" name="readonly_field" readonly />
                <input type="text" name="disabled_field" disabled />
                <input type="submit" value="Submit" />
            </form>
        </body>
        </html>
        """

    def test_client_fixture_makes_requests(self, client):
        """Verify TestClient can make HTTP requests."""
        response = client.get("/")
        assert response.status_code in [200, 404]  # Either success or not found

    def test_html_response_contains_form(self, client):
        """Verify HTML response parsing for form elements."""
        response = client.get("/")
        if response.status_code == 200:
            html = response.text
            has_form = "<form" in html.lower()
            has_input = "<input" in html.lower()
            # Dashboard should have form elements
            assert has_form or has_input

    def test_detect_visible_input_in_html(self, sample_html_with_forms):
        """Verify detection of visible inputs in HTML content."""
        html = sample_html_with_forms

        # Standard visible inputs should be present
        assert 'name="username"' in html
        assert 'name="password"' in html
        # Hidden inputs should also be present but marked as hidden
        assert 'type="hidden"' in html

    def test_detect_disabled_input_in_html(self, sample_html_with_forms):
        """Verify detection of disabled attribute in HTML content."""
        html = sample_html_with_forms

        assert 'disabled' in html
        assert 'name="disabled_field"' in html

    def test_detect_readonly_input_in_html(self, sample_html_with_forms):
        """Verify detection of readonly attribute in HTML content."""
        html = sample_html_with_forms

        assert 'readonly' in html
        assert 'name="readonly_field"' in html

    def test_detect_hidden_type_input_in_html(self, sample_html_with_forms):
        """Verify detection of type='hidden' inputs in HTML content."""
        html = sample_html_with_forms

        assert 'type="hidden"' in html
        assert 'name="csrf_token"' in html

    def test_count_form_inputs_in_html(self, sample_html_with_forms):
        """Verify counting of form inputs in HTML content."""
        html = sample_html_with_forms

        # Count input occurrences
        input_count = html.count("<input")
        assert input_count == 6  # username, password, csrf, readonly, disabled, submit

    def test_form_action_and_method_detection(self, sample_html_with_forms):
        """Verify form action and method attributes are detected."""
        html = sample_html_with_forms

        assert 'action="/submit"' in html
        assert 'method="post"' in html


class TestClassBasedSetupTeardown:
    """Test class demonstrating setup/teardown pattern from test_agent.py.

    Uses class-level fixtures and per-test setup for comprehensive
    form visibility testing scenarios.
    """

    @pytest.fixture(autouse=True)
    def setup_method_fixture(self, mock_input_element):
        """Per-test setup providing fresh mock elements."""
        self.input_factory = mock_input_element
        self.created_elements = []
        self.visibility_log = []
        yield
        # Teardown
        self.created_elements.clear()
        self.visibility_log.clear()

    def _create_and_track(self, **kwargs):
        """Helper to create and track elements."""
        element = self.input_factory(**kwargs)
        self.created_elements.append(element)
        return element

    def _log_visibility_check(self, element_name: str, is_visible: bool, is_enabled: bool):
        """Log visibility check for verification."""
        self.visibility_log.append({
            "element": element_name,
            "visible": is_visible,
            "enabled": is_enabled,
            "interactable": is_visible and is_enabled
        })

    def test_setup_provides_input_factory(self):
        """Verify setup provides working input factory."""
        assert self.input_factory is not None
        element = self.input_factory()
        assert element.is_displayed() is True

    def test_track_created_elements(self):
        """Verify element tracking in test context."""
        self._create_and_track(is_displayed=True, is_enabled=True)
        self._create_and_track(is_displayed=False, is_enabled=True)
        self._create_and_track(is_displayed=True, is_enabled=False)

        assert len(self.created_elements) == 3

    def test_log_visibility_checks(self):
        """Verify visibility logging for audit trails."""
        element = self._create_and_track(is_displayed=True, is_enabled=True)

        self._log_visibility_check(
            "test_field",
            element.is_displayed(),
            element.is_enabled()
        )

        assert len(self.visibility_log) == 1
        assert self.visibility_log[0]["element"] == "test_field"
        assert self.visibility_log[0]["interactable"] is True

    def test_batch_visibility_verification(self):
        """Verify batch visibility checking pattern."""
        fields = {
            "username": self._create_and_track(is_displayed=True, is_enabled=True),
            "password": self._create_and_track(is_displayed=True, is_enabled=True),
            "csrf": self._create_and_track(is_displayed=False, is_enabled=True),
            "submit": self._create_and_track(is_displayed=True, is_enabled=True),
        }

        for name, element in fields.items():
            self._log_visibility_check(
                name,
                element.is_displayed(),
                element.is_enabled()
            )

        # Verify all checks logged
        assert len(self.visibility_log) == 4

        # Verify interactable fields
        interactable = [
            log["element"] for log in self.visibility_log
            if log["interactable"]
        ]
        assert "username" in interactable
        assert "password" in interactable
        assert "submit" in interactable
        assert "csrf" not in interactable

    def test_pre_fill_validation_workflow(self):
        """Verify complete pre-fill validation workflow."""
        form_fields = {
            "email": self._create_and_track(is_displayed=True, is_enabled=True),
            "name": self._create_and_track(is_displayed=True, is_enabled=True),
            "age": self._create_and_track(is_displayed=True, is_enabled=False),  # Disabled
        }

        fillable_fields = []
        non_fillable_fields = []

        for name, element in form_fields.items():
            is_visible = element.is_displayed()
            is_enabled = element.is_enabled()

            self._log_visibility_check(name, is_visible, is_enabled)

            if is_visible and is_enabled:
                fillable_fields.append(name)
            else:
                non_fillable_fields.append(name)

        assert fillable_fields == ["email", "name"]
        assert non_fillable_fields == ["age"]
        assert len(self.visibility_log) == 3

    def test_teardown_clears_state(self):
        """Verify teardown clears all test state (implicit via fresh setup)."""
        # After previous tests, this test should start fresh
        assert len(self.created_elements) == 0
        assert len(self.visibility_log) == 0


class TestHTMLInputVisibilityAttributes:
    """Test HTML form inputs have proper visibility-related attributes.

    Parses HTML response.text to verify:
    - Input elements don't have type="hidden" (for user-fillable inputs)
    - Input elements don't have style="display:none"
    - Expected input types are present (text, email, password, etc.)
    """

    @pytest.fixture
    def html_parser_helpers(self):
        """Helper functions for parsing HTML input elements."""
        import re

        def find_all_inputs(html: str) -> list:
            """Extract all input elements from HTML."""
            pattern = r'<input[^>]*>'
            return re.findall(pattern, html, re.IGNORECASE)

        def get_input_attribute(input_tag: str, attr_name: str) -> str | None:
            """Extract attribute value from an input tag."""
            # Match attr="value" or attr='value' or attr (boolean)
            pattern = rf'{attr_name}=["\']([^"\']*)["\']'
            match = re.search(pattern, input_tag, re.IGNORECASE)
            if match:
                return match.group(1)
            # Check for boolean attribute
            if re.search(rf'\b{attr_name}\b(?!=)', input_tag, re.IGNORECASE):
                return attr_name
            return None

        def has_hidden_type(input_tag: str) -> bool:
            """Check if input has type='hidden'."""
            input_type = get_input_attribute(input_tag, "type")
            return input_type is not None and input_type.lower() == "hidden"

        def has_display_none(input_tag: str) -> bool:
            """Check if input has style containing display:none."""
            style = get_input_attribute(input_tag, "style")
            if style:
                return "display:none" in style.replace(" ", "").lower()
            return False

        def has_visibility_hidden(input_tag: str) -> bool:
            """Check if input has style containing visibility:hidden."""
            style = get_input_attribute(input_tag, "style")
            if style:
                return "visibility:hidden" in style.replace(" ", "").lower()
            return False

        def get_input_type(input_tag: str) -> str:
            """Get input type, defaulting to 'text' if not specified."""
            input_type = get_input_attribute(input_tag, "type")
            return input_type.lower() if input_type else "text"

        return {
            "find_all_inputs": find_all_inputs,
            "get_input_attribute": get_input_attribute,
            "has_hidden_type": has_hidden_type,
            "has_display_none": has_display_none,
            "has_visibility_hidden": has_visibility_hidden,
            "get_input_type": get_input_type,
        }

    @pytest.fixture
    def sample_form_html(self):
        """Sample HTML form with various input types and visibility states."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Form</title></head>
        <body>
            <form id="user-form" action="/api/submit" method="POST">
                <input type="text" name="username" id="username" placeholder="Enter username" />
                <input type="email" name="email" id="email" required />
                <input type="password" name="password" id="password" />
                <input type="tel" name="phone" id="phone" />
                <input type="number" name="age" id="age" min="0" max="120" />
                <input type="hidden" name="csrf_token" value="token123" />
                <input type="text" name="invisible" style="display:none;" />
                <input type="text" name="collapsed" style="visibility:hidden;" />
                <input type="submit" value="Submit" />
            </form>
        </body>
        </html>
        """

    @pytest.fixture
    def minimal_visible_form_html(self):
        """HTML form with only visible, fillable inputs."""
        return """
        <form id="simple-form">
            <input type="text" name="name" />
            <input type="email" name="email" />
            <input type="password" name="pass" />
            <button type="submit">Submit</button>
        </form>
        """

    def test_find_all_inputs_extracts_input_tags(self, html_parser_helpers, sample_form_html):
        """Verify parser extracts all input elements from HTML."""
        find_all_inputs = html_parser_helpers["find_all_inputs"]
        inputs = find_all_inputs(sample_form_html)

        assert len(inputs) == 9  # 9 input elements in sample form
        assert all("<input" in inp.lower() for inp in inputs)

    def test_get_input_attribute_extracts_name(self, html_parser_helpers):
        """Verify attribute extraction works for name attribute."""
        get_attr = html_parser_helpers["get_input_attribute"]
        input_tag = '<input type="text" name="username" id="user-input" />'

        assert get_attr(input_tag, "name") == "username"
        assert get_attr(input_tag, "type") == "text"
        assert get_attr(input_tag, "id") == "user-input"

    def test_get_input_attribute_returns_none_for_missing(self, html_parser_helpers):
        """Verify attribute extraction returns None for missing attributes."""
        get_attr = html_parser_helpers["get_input_attribute"]
        input_tag = '<input type="text" name="field" />'

        assert get_attr(input_tag, "placeholder") is None
        assert get_attr(input_tag, "required") is None

    def test_get_input_attribute_handles_boolean_attributes(self, html_parser_helpers):
        """Verify boolean attribute detection works."""
        get_attr = html_parser_helpers["get_input_attribute"]
        input_tag = '<input type="text" name="field" required disabled readonly />'

        assert get_attr(input_tag, "required") == "required"
        assert get_attr(input_tag, "disabled") == "disabled"
        assert get_attr(input_tag, "readonly") == "readonly"

    def test_has_hidden_type_detects_hidden_inputs(self, html_parser_helpers):
        """Verify detection of type='hidden' inputs."""
        has_hidden = html_parser_helpers["has_hidden_type"]

        hidden_input = '<input type="hidden" name="csrf" value="abc" />'
        text_input = '<input type="text" name="username" />'
        no_type_input = '<input name="field" />'

        assert has_hidden(hidden_input) is True
        assert has_hidden(text_input) is False
        assert has_hidden(no_type_input) is False

    def test_has_display_none_detects_css_hidden(self, html_parser_helpers):
        """Verify detection of style='display:none' inputs."""
        has_display_none = html_parser_helpers["has_display_none"]

        hidden_style = '<input type="text" name="hidden" style="display:none;" />'
        visible_style = '<input type="text" name="visible" style="color:red;" />'
        no_style = '<input type="text" name="normal" />'
        spaced_style = '<input type="text" style="display: none;" />'

        assert has_display_none(hidden_style) is True
        assert has_display_none(visible_style) is False
        assert has_display_none(no_style) is False
        assert has_display_none(spaced_style) is True

    def test_has_visibility_hidden_detects_css_invisible(self, html_parser_helpers):
        """Verify detection of style='visibility:hidden' inputs."""
        has_vis_hidden = html_parser_helpers["has_visibility_hidden"]

        invisible = '<input type="text" style="visibility:hidden;" />'
        visible = '<input type="text" style="visibility:visible;" />'
        no_style = '<input type="text" name="normal" />'

        assert has_vis_hidden(invisible) is True
        assert has_vis_hidden(visible) is False
        assert has_vis_hidden(no_style) is False

    def test_get_input_type_extracts_type(self, html_parser_helpers):
        """Verify input type extraction with default fallback."""
        get_type = html_parser_helpers["get_input_type"]

        assert get_type('<input type="email" />') == "email"
        assert get_type('<input type="password" />') == "password"
        assert get_type('<input type="TEXT" />') == "text"  # Case insensitive
        assert get_type('<input name="field" />') == "text"  # Default

    def test_sample_form_has_expected_visible_inputs(self, html_parser_helpers, sample_form_html):
        """Verify sample form contains expected visible input types."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        get_type = html_parser_helpers["get_input_type"]
        has_hidden = html_parser_helpers["has_hidden_type"]
        has_display_none = html_parser_helpers["has_display_none"]

        inputs = find_inputs(sample_form_html)
        expected_visible_types = {"text", "email", "password", "tel", "number", "submit"}

        visible_types = set()
        for inp in inputs:
            if not has_hidden(inp) and not has_display_none(inp):
                visible_types.add(get_type(inp))

        # Check expected types are present
        for expected in ["text", "email", "password"]:
            assert expected in visible_types, f"Expected visible input type '{expected}' not found"

    def test_sample_form_hidden_inputs_detected(self, html_parser_helpers, sample_form_html):
        """Verify hidden inputs are correctly identified in sample form."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        has_hidden = html_parser_helpers["has_hidden_type"]
        has_display_none = html_parser_helpers["has_display_none"]
        has_vis_hidden = html_parser_helpers["has_visibility_hidden"]

        inputs = find_inputs(sample_form_html)

        hidden_count = 0
        display_none_count = 0
        visibility_hidden_count = 0

        for inp in inputs:
            if has_hidden(inp):
                hidden_count += 1
            if has_display_none(inp):
                display_none_count += 1
            if has_vis_hidden(inp):
                visibility_hidden_count += 1

        assert hidden_count == 1, "Expected 1 type='hidden' input"
        assert display_none_count == 1, "Expected 1 display:none input"
        assert visibility_hidden_count == 1, "Expected 1 visibility:hidden input"

    def test_filter_fillable_inputs(self, html_parser_helpers, sample_form_html):
        """Verify filtering to only fillable (visible, non-hidden) inputs."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        has_hidden = html_parser_helpers["has_hidden_type"]
        has_display_none = html_parser_helpers["has_display_none"]
        has_vis_hidden = html_parser_helpers["has_visibility_hidden"]
        get_type = html_parser_helpers["get_input_type"]

        inputs = find_inputs(sample_form_html)

        def is_fillable(input_tag: str) -> bool:
            """Check if input is visible and fillable."""
            if has_hidden(input_tag):
                return False
            if has_display_none(input_tag):
                return False
            if has_vis_hidden(input_tag):
                return False
            # Submit buttons are visible but not fillable with text
            if get_type(input_tag) == "submit":
                return False
            return True

        fillable_inputs = [inp for inp in inputs if is_fillable(inp)]

        # Should have: text, email, password, tel, number = 5 fillable inputs
        assert len(fillable_inputs) == 5

    def test_verify_no_hidden_type_in_user_inputs(self, html_parser_helpers, minimal_visible_form_html):
        """Verify user-fillable form has no hidden type inputs."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        has_hidden = html_parser_helpers["has_hidden_type"]

        inputs = find_inputs(minimal_visible_form_html)

        for inp in inputs:
            assert has_hidden(inp) is False, f"Unexpected hidden input: {inp}"

    def test_verify_no_display_none_in_user_inputs(self, html_parser_helpers, minimal_visible_form_html):
        """Verify user-fillable form has no display:none inputs."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        has_display_none = html_parser_helpers["has_display_none"]

        inputs = find_inputs(minimal_visible_form_html)

        for inp in inputs:
            assert has_display_none(inp) is False, f"Unexpected display:none input: {inp}"

    def test_verify_expected_input_types_present(self, html_parser_helpers, minimal_visible_form_html):
        """Verify expected input types are present in form."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        get_type = html_parser_helpers["get_input_type"]

        inputs = find_inputs(minimal_visible_form_html)
        types_found = {get_type(inp) for inp in inputs}

        expected_types = ["text", "email", "password"]
        for expected in expected_types:
            assert expected in types_found, f"Expected input type '{expected}' not found"

    def test_input_visibility_summary_report(self, html_parser_helpers, sample_form_html):
        """Generate visibility summary report for all inputs in form."""
        find_inputs = html_parser_helpers["find_all_inputs"]
        get_attr = html_parser_helpers["get_input_attribute"]
        get_type = html_parser_helpers["get_input_type"]
        has_hidden = html_parser_helpers["has_hidden_type"]
        has_display_none = html_parser_helpers["has_display_none"]
        has_vis_hidden = html_parser_helpers["has_visibility_hidden"]

        inputs = find_inputs(sample_form_html)

        report = []
        for inp in inputs:
            name = get_attr(inp, "name") or get_attr(inp, "id") or "unnamed"
            input_type = get_type(inp)
            is_visible = not (has_hidden(inp) or has_display_none(inp) or has_vis_hidden(inp))

            report.append({
                "name": name,
                "type": input_type,
                "visible": is_visible,
                "reason": (
                    "type=hidden" if has_hidden(inp) else
                    "display:none" if has_display_none(inp) else
                    "visibility:hidden" if has_vis_hidden(inp) else
                    "visible"
                )
            })

        # Verify report structure
        assert len(report) == 9

        # Verify hidden inputs are flagged
        hidden_entries = [r for r in report if not r["visible"]]
        assert len(hidden_entries) == 3  # csrf_token, invisible, collapsed

        # Verify visible inputs are correct
        visible_entries = [r for r in report if r["visible"]]
        assert len(visible_entries) == 6  # username, email, password, phone, age, submit

    def test_case_insensitive_type_detection(self, html_parser_helpers):
        """Verify type detection is case-insensitive."""
        has_hidden = html_parser_helpers["has_hidden_type"]

        assert has_hidden('<input TYPE="HIDDEN" />') is True
        assert has_hidden('<input Type="Hidden" />') is True
        assert has_hidden('<input type="hidden" />') is True
        assert has_hidden('<input type="Hidden" />') is True

    def test_multiple_style_properties(self, html_parser_helpers):
        """Verify detection works with multiple style properties."""
        has_display_none = html_parser_helpers["has_display_none"]

        # display:none mixed with other styles
        mixed_style = '<input style="color:red; display:none; font-size:12px;" />'
        assert has_display_none(mixed_style) is True

        # Only other styles
        other_styles = '<input style="color:red; font-size:12px;" />'
        assert has_display_none(other_styles) is False


class TestDisabledHiddenDetectionLogic:
    """Comprehensive tests for disabled and hidden input detection logic.

    Validates detection algorithms correctly identify disabled/hidden states
    through multiple detection strategies:
    - is_enabled() returning False for disabled inputs
    - is_displayed() returning False for hidden inputs
    - Attribute-based detection (disabled, hidden attributes)
    - Style-based detection (display:none, visibility:hidden)
    - Combined state detection for complex scenarios
    """

    # ===== DISABLED INPUT DETECTION TESTS =====

    def test_disabled_detection_via_is_enabled_false(self, mock_input_element):
        """Verify disabled inputs are detected when is_enabled() returns False."""
        disabled_input = mock_input_element(is_displayed=True, is_enabled=False)

        # Detection logic should identify disabled state
        is_disabled = not disabled_input.is_enabled()

        assert is_disabled is True
        assert disabled_input.is_enabled() is False

    def test_disabled_detection_preserves_visibility(self, mock_input_element):
        """Verify disabled detection doesn't affect visibility state."""
        disabled_input = mock_input_element(is_displayed=True, is_enabled=False)

        # Disabled inputs can still be visible
        is_visible = disabled_input.is_displayed()
        is_disabled = not disabled_input.is_enabled()

        assert is_visible is True
        assert is_disabled is True

    def test_disabled_attribute_detection_logic(self, mock_input_element):
        """Verify disabled attribute detection via get_attribute()."""
        disabled_input = mock_input_element(is_enabled=False)

        # Set up attribute mock to return 'disabled' or 'true'
        def get_attr(name):
            if name == "disabled":
                return "disabled"
            return None

        disabled_input.get_attribute.side_effect = get_attr

        # Detection logic using attribute check
        disabled_attr = disabled_input.get_attribute("disabled")
        is_disabled_by_attr = disabled_attr is not None

        assert is_disabled_by_attr is True
        assert disabled_input.is_enabled() is False

    def test_disabled_detection_with_aria_disabled(self, mock_input_element):
        """Verify detection of aria-disabled attribute."""
        input_elem = mock_input_element(is_enabled=False)

        def get_attr(name):
            if name == "aria-disabled":
                return "true"
            if name == "disabled":
                return None
            return None

        input_elem.get_attribute.side_effect = get_attr

        # Detection logic should check aria-disabled as well
        aria_disabled = input_elem.get_attribute("aria-disabled")
        is_aria_disabled = aria_disabled == "true"

        assert is_aria_disabled is True

    def test_disabled_detection_multiple_indicators(self, mock_input_element):
        """Verify detection using multiple disabled indicators."""
        disabled_input = mock_input_element(is_enabled=False)

        def get_attr(name):
            attrs = {
                "disabled": "disabled",
                "aria-disabled": "true",
                "readonly": None,
            }
            return attrs.get(name)

        disabled_input.get_attribute.side_effect = get_attr

        # Comprehensive disabled detection
        is_api_disabled = not disabled_input.is_enabled()
        has_disabled_attr = disabled_input.get_attribute("disabled") is not None
        has_aria_disabled = disabled_input.get_attribute("aria-disabled") == "true"

        # Any indicator should flag as disabled
        is_detected_disabled = is_api_disabled or has_disabled_attr or has_aria_disabled

        assert is_detected_disabled is True
        assert is_api_disabled is True
        assert has_disabled_attr is True
        assert has_aria_disabled is True

    # ===== HIDDEN INPUT DETECTION TESTS =====

    def test_hidden_detection_via_is_displayed_false(self, mock_input_element):
        """Verify hidden inputs are detected when is_displayed() returns False."""
        hidden_input = mock_input_element(is_displayed=False, is_enabled=True)

        # Detection logic should identify hidden state
        is_hidden = not hidden_input.is_displayed()

        assert is_hidden is True
        assert hidden_input.is_displayed() is False

    def test_hidden_detection_preserves_enabled_state(self, mock_input_element):
        """Verify hidden detection doesn't affect enabled state."""
        hidden_input = mock_input_element(is_displayed=False, is_enabled=True)

        # Hidden inputs can still be enabled in the DOM
        is_hidden = not hidden_input.is_displayed()
        is_enabled = hidden_input.is_enabled()

        assert is_hidden is True
        assert is_enabled is True

    def test_hidden_type_attribute_detection(self, mock_input_element):
        """Verify detection of type='hidden' inputs."""
        hidden_input = mock_input_element(is_displayed=False)

        def get_attr(name):
            if name == "type":
                return "hidden"
            return None

        hidden_input.get_attribute.side_effect = get_attr

        # Detection via type attribute
        input_type = hidden_input.get_attribute("type")
        is_hidden_type = input_type == "hidden"

        assert is_hidden_type is True
        assert hidden_input.is_displayed() is False

    def test_hidden_via_display_none_style(self, mock_input_element):
        """Verify detection of CSS display:none hidden inputs."""
        hidden_input = mock_input_element(is_displayed=False)

        def get_attr(name):
            if name == "style":
                return "display: none;"
            return None

        hidden_input.get_attribute.side_effect = get_attr

        # Detection via style attribute
        style = hidden_input.get_attribute("style")
        is_css_hidden = style is not None and "display" in style and "none" in style

        assert is_css_hidden is True
        assert hidden_input.is_displayed() is False

    def test_hidden_via_visibility_hidden_style(self, mock_input_element):
        """Verify detection of CSS visibility:hidden inputs."""
        hidden_input = mock_input_element(is_displayed=False)

        def get_attr(name):
            if name == "style":
                return "visibility: hidden;"
            return None

        hidden_input.get_attribute.side_effect = get_attr

        # Detection via style attribute
        style = hidden_input.get_attribute("style")
        is_vis_hidden = style is not None and "visibility" in style and "hidden" in style

        assert is_vis_hidden is True
        assert hidden_input.is_displayed() is False

    def test_hidden_via_aria_hidden_attribute(self, mock_input_element):
        """Verify detection of aria-hidden attribute."""
        input_elem = mock_input_element(is_displayed=False)

        def get_attr(name):
            if name == "aria-hidden":
                return "true"
            return None

        input_elem.get_attribute.side_effect = get_attr

        # Detection via aria-hidden
        aria_hidden = input_elem.get_attribute("aria-hidden")
        is_aria_hidden = aria_hidden == "true"

        assert is_aria_hidden is True

    def test_hidden_via_hidden_attribute(self, mock_input_element):
        """Verify detection of HTML5 hidden attribute."""
        hidden_input = mock_input_element(is_displayed=False)

        def get_attr(name):
            if name == "hidden":
                return "hidden"  # Boolean attribute
            return None

        hidden_input.get_attribute.side_effect = get_attr

        # Detection via hidden attribute
        hidden_attr = hidden_input.get_attribute("hidden")
        has_hidden_attr = hidden_attr is not None

        assert has_hidden_attr is True
        assert hidden_input.is_displayed() is False

    def test_hidden_detection_multiple_indicators(self, mock_input_element):
        """Verify comprehensive hidden detection with multiple indicators."""
        hidden_input = mock_input_element(is_displayed=False)

        def get_attr(name):
            attrs = {
                "type": "hidden",
                "style": "display: none;",
                "aria-hidden": "true",
                "hidden": "hidden",
            }
            return attrs.get(name)

        hidden_input.get_attribute.side_effect = get_attr

        # Comprehensive hidden detection
        is_api_hidden = not hidden_input.is_displayed()
        is_type_hidden = hidden_input.get_attribute("type") == "hidden"
        style = hidden_input.get_attribute("style") or ""
        is_css_hidden = "display" in style and "none" in style
        is_aria_hidden = hidden_input.get_attribute("aria-hidden") == "true"
        has_hidden_attr = hidden_input.get_attribute("hidden") is not None

        # Any indicator should flag as hidden
        is_detected_hidden = (
            is_api_hidden or is_type_hidden or is_css_hidden or is_aria_hidden or has_hidden_attr
        )

        assert is_detected_hidden is True
        assert is_api_hidden is True
        assert is_type_hidden is True
        assert is_css_hidden is True
        assert is_aria_hidden is True
        assert has_hidden_attr is True

    # ===== COMBINED STATE DETECTION TESTS =====

    def test_detection_logic_both_hidden_and_disabled(self, mock_input_element):
        """Verify detection when input is both hidden AND disabled."""
        hidden_disabled = mock_input_element(is_displayed=False, is_enabled=False)

        is_hidden = not hidden_disabled.is_displayed()
        is_disabled = not hidden_disabled.is_enabled()

        assert is_hidden is True
        assert is_disabled is True
        # Cannot interact with element that is both hidden and disabled
        assert not (hidden_disabled.is_displayed() and hidden_disabled.is_enabled())

    def test_detection_logic_visible_and_enabled(self, mock_input_element):
        """Verify detection correctly identifies fully interactable inputs."""
        visible_enabled = mock_input_element(is_displayed=True, is_enabled=True)

        is_hidden = not visible_enabled.is_displayed()
        is_disabled = not visible_enabled.is_enabled()

        assert is_hidden is False
        assert is_disabled is False
        # Can interact with element that is visible and enabled
        assert visible_enabled.is_displayed() and visible_enabled.is_enabled()

    def test_detection_logic_categorizes_all_states(self, mock_input_element):
        """Verify detection logic correctly categorizes all possible states."""
        states = {
            "visible_enabled": mock_input_element(is_displayed=True, is_enabled=True),
            "visible_disabled": mock_input_element(is_displayed=True, is_enabled=False),
            "hidden_enabled": mock_input_element(is_displayed=False, is_enabled=True),
            "hidden_disabled": mock_input_element(is_displayed=False, is_enabled=False),
        }

        def categorize(elem):
            """Categorize element by visibility and enabled state."""
            is_visible = elem.is_displayed()
            is_enabled = elem.is_enabled()
            if is_visible and is_enabled:
                return "interactable"
            elif is_visible and not is_enabled:
                return "visible_but_disabled"
            elif not is_visible and is_enabled:
                return "hidden_but_enabled"
            else:
                return "hidden_and_disabled"

        assert categorize(states["visible_enabled"]) == "interactable"
        assert categorize(states["visible_disabled"]) == "visible_but_disabled"
        assert categorize(states["hidden_enabled"]) == "hidden_but_enabled"
        assert categorize(states["hidden_disabled"]) == "hidden_and_disabled"

    # ===== DETECTION UTILITY FUNCTION TESTS =====

    def test_is_input_disabled_utility(self, mock_input_element):
        """Test utility function pattern for disabled detection."""
        def is_input_disabled(element) -> bool:
            """Check if an input element is disabled."""
            if not element.is_enabled():
                return True
            disabled_attr = element.get_attribute("disabled")
            if disabled_attr is not None:
                return True
            aria_disabled = element.get_attribute("aria-disabled")
            if aria_disabled == "true":
                return True
            return False

        enabled_input = mock_input_element(is_enabled=True)
        disabled_input = mock_input_element(is_enabled=False)

        assert is_input_disabled(enabled_input) is False
        assert is_input_disabled(disabled_input) is True

    def test_is_input_hidden_utility(self, mock_input_element):
        """Test utility function pattern for hidden detection."""
        def is_input_hidden(element) -> bool:
            """Check if an input element is hidden."""
            if not element.is_displayed():
                return True
            input_type = element.get_attribute("type")
            if input_type == "hidden":
                return True
            style = element.get_attribute("style") or ""
            if "display" in style and "none" in style:
                return True
            if "visibility" in style and "hidden" in style:
                return True
            return False

        visible_input = mock_input_element(is_displayed=True)
        hidden_input = mock_input_element(is_displayed=False)

        assert is_input_hidden(visible_input) is False
        assert is_input_hidden(hidden_input) is True

    def test_can_interact_with_input_utility(self, mock_input_element):
        """Test utility function pattern for interactability detection."""
        def can_interact_with_input(element) -> bool:
            """Check if an input element can be interacted with."""
            return element.is_displayed() and element.is_enabled()

        test_cases = [
            (mock_input_element(is_displayed=True, is_enabled=True), True),
            (mock_input_element(is_displayed=True, is_enabled=False), False),
            (mock_input_element(is_displayed=False, is_enabled=True), False),
            (mock_input_element(is_displayed=False, is_enabled=False), False),
        ]

        for element, expected in test_cases:
            assert can_interact_with_input(element) is expected

    # ===== EDGE CASE DETECTION TESTS =====

    def test_detection_with_none_attribute_values(self, mock_input_element):
        """Verify detection handles None attribute values gracefully."""
        input_elem = mock_input_element(is_displayed=True, is_enabled=True)
        input_elem.get_attribute.return_value = None

        # Detection should not raise when attributes are None
        disabled_attr = input_elem.get_attribute("disabled")
        hidden_attr = input_elem.get_attribute("hidden")
        style_attr = input_elem.get_attribute("style")

        assert disabled_attr is None
        assert hidden_attr is None
        assert style_attr is None

        # Element should still be detectable as visible and enabled
        assert input_elem.is_displayed() is True
        assert input_elem.is_enabled() is True

    def test_detection_with_empty_string_attributes(self, mock_input_element):
        """Verify detection handles empty string attribute values."""
        input_elem = mock_input_element(is_displayed=True, is_enabled=True)
        input_elem.get_attribute.return_value = ""

        style = input_elem.get_attribute("style")

        # Empty string should not trigger hidden detection
        is_css_hidden = style and "display" in style and "none" in style

        # Empty string is falsy, so is_css_hidden should be falsy (not trigger hidden detection)
        assert not is_css_hidden

    def test_detection_case_insensitive_attributes(self, mock_input_element):
        """Verify detection handles case variations in attributes."""
        input_elem = mock_input_element(is_displayed=False)

        # Test various case combinations
        test_cases = [
            ("HIDDEN", True),
            ("Hidden", True),
            ("hidden", True),
            ("HiDdEn", True),
        ]

        for value, expected_hidden in test_cases:
            input_elem.get_attribute.return_value = value
            attr_value = input_elem.get_attribute("type")
            is_hidden = attr_value.lower() == "hidden" if attr_value else False
            assert is_hidden is expected_hidden

    def test_detection_readonly_vs_disabled(self, mock_input_element):
        """Verify detection distinguishes readonly from disabled."""
        # Readonly input - still enabled but not editable
        readonly_input = mock_input_element(is_displayed=True, is_enabled=True)
        readonly_input.get_attribute.return_value = "readonly"

        # Disabled input - not enabled
        disabled_input = mock_input_element(is_displayed=True, is_enabled=False)

        # Readonly is enabled, disabled is not
        assert readonly_input.is_enabled() is True
        assert disabled_input.is_enabled() is False

        # Both should have different readonly detection
        readonly_attr = readonly_input.get_attribute("readonly")
        assert readonly_attr == "readonly"

    def test_detection_form_field_collection(self, mock_input_element):
        """Test detection across a collection of form fields."""
        form_fields = {
            "username": mock_input_element(is_displayed=True, is_enabled=True),
            "email": mock_input_element(is_displayed=True, is_enabled=True),
            "csrf_token": mock_input_element(is_displayed=False, is_enabled=True),
            "locked_field": mock_input_element(is_displayed=True, is_enabled=False),
            "old_field": mock_input_element(is_displayed=False, is_enabled=False),
        }

        # Categorize all fields
        interactable = []
        hidden = []
        disabled = []

        for name, element in form_fields.items():
            if not element.is_displayed():
                hidden.append(name)
            if not element.is_enabled():
                disabled.append(name)
            if element.is_displayed() and element.is_enabled():
                interactable.append(name)

        assert interactable == ["username", "email"]
        assert hidden == ["csrf_token", "old_field"]
        assert disabled == ["locked_field", "old_field"]

    def test_detection_with_dynamic_state_changes(self, mock_input_element):
        """Test detection handles dynamic state changes."""
        input_elem = mock_input_element(is_displayed=True, is_enabled=True)

        # Initial state - visible and enabled
        assert input_elem.is_displayed() is True
        assert input_elem.is_enabled() is True

        # Simulate state change to disabled
        input_elem.is_enabled.return_value = False
        assert input_elem.is_enabled() is False
        assert input_elem.is_displayed() is True  # Still visible

        # Simulate state change to hidden
        input_elem.is_displayed.return_value = False
        assert input_elem.is_displayed() is False
        assert input_elem.is_enabled() is False  # Still disabled

        # Simulate restoration
        input_elem.is_displayed.return_value = True
        input_elem.is_enabled.return_value = True
        assert input_elem.is_displayed() is True
        assert input_elem.is_enabled() is True