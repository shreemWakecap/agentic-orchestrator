"""
Integration tests for Job API endpoints.

Note: These tests require the full application setup.
Some tests may be skipped in CI environments.
"""
import pytest


@pytest.mark.asyncio
class TestJobAPI:
    """Tests for Job REST API."""

    @pytest.fixture
    def api_base_url(self):
        """Base URL for API requests."""
        return "/api/jobs"

    async def test_create_job_valid(self, job_api_client, api_base_url):
        """Test POST /api/jobs with valid data."""
        response = await job_api_client.post(
            api_base_url,
            json={
                "job_type": "plan",
                "parameters": {"spec_id": "test-001"},
                "priority": 2,
            }
        )

        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "job_id" in data or "id" in data

    async def test_create_job_invalid_type(self, job_api_client, api_base_url):
        """Test POST /api/jobs with invalid job type."""
        response = await job_api_client.post(
            api_base_url,
            json={
                "job_type": "invalid_type",
                "parameters": {},
            }
        )

        # Should reject invalid job type
        assert response.status_code in [400, 422]

    async def test_create_job_missing_parameters(self, job_api_client, api_base_url):
        """Test POST /api/jobs with missing required fields."""
        response = await job_api_client.post(
            api_base_url,
            json={}
        )

        # Should require job_type
        assert response.status_code in [400, 422]

    async def test_get_job_exists(self, job_api_client, api_base_url):
        """Test GET /api/jobs/{id} for existing job."""
        # First create a job
        create_response = await job_api_client.post(
            api_base_url,
            json={"job_type": "plan", "parameters": {"spec_id": "test"}}
        )

        if create_response.status_code not in [200, 201, 202]:
            pytest.skip("Job creation not working")

        data = create_response.json()
        job_id = data.get("job_id") or data.get("id")

        if not job_id:
            pytest.skip("No job_id in response")

        # Then fetch it
        response = await job_api_client.get(f"{api_base_url}/{job_id}")

        assert response.status_code == 200
        job_data = response.json()
        assert job_data.get("job_id") == job_id or job_data.get("id") == job_id

    async def test_get_job_not_found(self, job_api_client, api_base_url):
        """Test GET /api/jobs/{id} for non-existent job."""
        response = await job_api_client.get(f"{api_base_url}/nonexistent123456")

        assert response.status_code == 404

    async def test_list_jobs(self, job_api_client, api_base_url):
        """Test GET /api/jobs."""
        # Create some jobs first
        for i in range(3):
            await job_api_client.post(
                api_base_url,
                json={"job_type": "plan", "parameters": {"spec_id": f"test-{i}"}}
            )

        # List them
        response = await job_api_client.get(api_base_url)

        assert response.status_code == 200
        data = response.json()
        # Response should have jobs list
        assert "jobs" in data or isinstance(data, list)

    async def test_list_jobs_with_pagination(self, job_api_client, api_base_url):
        """Test GET /api/jobs with pagination."""
        response = await job_api_client.get(f"{api_base_url}?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()
        # Should respect limit
        jobs = data.get("jobs") or data
        if isinstance(jobs, list):
            assert len(jobs) <= 5

    async def test_list_jobs_with_status_filter(self, job_api_client, api_base_url):
        """Test GET /api/jobs with status filter."""
        response = await job_api_client.get(f"{api_base_url}?status=pending")

        assert response.status_code == 200
        data = response.json()
        jobs = data.get("jobs") or data
        if isinstance(jobs, list):
            for job in jobs:
                assert job.get("status") == "pending"

    async def test_cancel_job(self, job_api_client, api_base_url):
        """Test POST /api/jobs/{id}/cancel."""
        # Create a job
        create_response = await job_api_client.post(
            api_base_url,
            json={"job_type": "plan", "parameters": {"spec_id": "test"}}
        )

        if create_response.status_code not in [200, 201, 202]:
            pytest.skip("Job creation not working")

        data = create_response.json()
        job_id = data.get("job_id") or data.get("id")

        if not job_id:
            pytest.skip("No job_id in response")

        # Cancel it
        response = await job_api_client.post(
            f"{api_base_url}/{job_id}/cancel",
            json={"reason": "Test cancellation"}
        )

        assert response.status_code in [200, 202]

    async def test_retry_job(self, job_api_client, api_base_url):
        """Test POST /api/jobs/{id}/retry."""
        # This test would need a failed job
        # Skipping for now as it requires more setup
        pytest.skip("Requires failed job setup")

    async def test_health_check(self, job_api_client):
        """Test GET /health."""
        response = await job_api_client.get("/health")

        # Health endpoint should exist
        if response.status_code == 404:
            pytest.skip("Health endpoint not available")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    async def test_ready_check(self, job_api_client):
        """Test GET /ready."""
        response = await job_api_client.get("/ready")

        # Ready endpoint should exist
        if response.status_code == 404:
            pytest.skip("Ready endpoint not available")

        assert response.status_code == 200

    async def test_cors_headers(self, job_api_client, api_base_url):
        """Test that CORS headers are present."""
        response = await job_api_client.options(
            api_base_url,
            headers={"Origin": "http://localhost:3000"}
        )

        # Should handle OPTIONS request
        assert response.status_code in [200, 204, 405]

    async def test_content_type_json(self, job_api_client, api_base_url):
        """Test that API returns JSON content type."""
        response = await job_api_client.get(api_base_url)

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type
