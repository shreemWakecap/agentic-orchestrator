"""Tests for form input visibility on the dashboard."""

import pytest
from fastapi.testclient import TestClient

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
