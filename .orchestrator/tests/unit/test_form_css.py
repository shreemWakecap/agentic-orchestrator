"""Tests for form element CSS classes in HTML templates."""

import pytest
from fastapi.testclient import TestClient

from server.app import app


class TestFormCSSClasses:
    """Validate form inputs and buttons have correct Tailwind CSS classes."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastAPI app."""
        return TestClient(app)

    def test_input_fields_have_tailwind_classes(self, client):
        """Verify input fields render with expected Tailwind CSS classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Tailwind classes used for form inputs in dashboard.html
        assert "border" in html
        assert "border-gray-300" in html
        assert "rounded-md" in html
        assert "shadow-sm" in html

    def test_buttons_have_tailwind_classes(self, client):
        """Verify buttons render with expected Tailwind CSS classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Tailwind classes used for buttons in dashboard.html
        assert "bg-blue-600" in html
        assert "hover:bg-blue-700" in html
        assert "text-white" in html
        assert "font-medium" in html

    def test_input_has_focus_ring_classes(self, client):
        """Verify input fields have focus ring styling for accessibility."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Focus ring classes for input accessibility
        assert "focus:ring-2" in html
        assert "focus:ring-blue-500" in html
        assert "focus:outline-none" in html

    def test_button_has_focus_ring_classes(self, client):
        """Verify buttons have focus ring styling for accessibility."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Focus ring classes for button accessibility
        assert "focus:ring-offset-2" in html

    def test_form_has_flex_layout(self, client):
        """Verify form uses flex layout for proper alignment."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Flex layout classes
        assert "flex" in html
        assert "gap-4" in html

    def test_input_has_padding_classes(self, client):
        """Verify input has proper padding for visual appearance."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Padding classes for input
        assert "px-4" in html
        assert "py-2" in html

    def test_button_has_inline_flex_display(self, client):
        """Verify button uses inline-flex for icon alignment."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert "inline-flex" in html
        assert "items-center" in html

    def test_input_has_responsive_text_size(self, client):
        """Verify input has responsive text size classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert "sm:text-sm" in html

    def test_button_has_transparent_border(self, client):
        """Verify button has transparent border for consistent sizing."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert "border-transparent" in html
