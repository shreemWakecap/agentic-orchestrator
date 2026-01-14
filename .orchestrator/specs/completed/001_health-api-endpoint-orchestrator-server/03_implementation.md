# Implementation Plan

> Part of plan: Add a /health API endpoint to the orchestrator server (server/app.py). The endpoint should return JSON with status, version, and uptime. Include pytest tests in tests/unit/test_portal.py.

## Implementation Steps

### Phase 1: Setup
> Add module-level startup time tracking

#### Step 1.1: modify .orchestrator/server/app.py
**Action:** modify
**Target:** .orchestrator/server/app.py
**Dependencies:** none
**Description:** Add START_TIME module variable near the top of the file after imports to capture server startup time

```python
# Add after the existing imports (after the last import statement)
import datetime

# Server startup time for health endpoint uptime calculation
START_TIME = datetime.datetime.now()
```

### Phase 2: Core Implementation
> Add health endpoint

#### Step 2.1: modify .orchestrator/server/app.py
**Action:** modify
**Target:** .orchestrator/server/app.py
**Dependencies:** Step 1.1
**Description:** Add /api/health endpoint in the API Routes section, following the existing /api/hello pattern

```python
# Add this endpoint in the "# ============== API Routes ==============" section
# after the existing /api/hello endpoint

@app.get("/api/health")
async def health_check():
    """Health check endpoint returning server status, version, and uptime."""
    uptime_seconds = (datetime.datetime.now() - START_TIME).total_seconds()
    return {
        "status": "healthy",
        "version": app.version,
        "uptime_seconds": round(uptime_seconds, 2)
    }
```

### Phase 3: Testing
> Add health endpoint tests

#### Step 3.1: modify .orchestrator/tests/unit/test_portal.py
**Action:** modify
**Target:** .orchestrator/tests/unit/test_portal.py
**Dependencies:** Step 2.1
**Description:** Add TestHealthEndpoint class following the existing TestHelloEndpoint pattern

```python
# Add this test class after the existing test classes (e.g., after TestHelloEndpoint or TestFastAPIEndpoints)

class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client):
        """Test that health endpoint returns 200 status code."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_status_healthy(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client):
        """Test that health endpoint returns version string."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    def test_health_returns_uptime_seconds(self, client):
        """Test that health endpoint returns uptime as positive number."""
        response = client.get("/api/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_health_response_structure(self, client):
        """Test that health endpoint returns all expected fields."""
        response = client.get("/api/health")
        data = response.json()
        expected_keys = {"status", "version", "uptime_seconds"}
        assert set(data.keys()) == expected_keys
```

## Testing Strategy

| Test Type | File | What it verifies |
|-----------|------|------------------|
| Unit | .orchestrator/tests/unit/test_portal.py | Health endpoint returns 200 with correct JSON structure |
| Unit | .orchestrator/tests/unit/test_portal.py | Response contains status="healthy", version="1.0.0", and positive uptime_seconds |
| Unit | .orchestrator/tests/unit/test_portal.py | Response structure matches expected schema |

## Validation Commands

```bash
# Run health endpoint tests specifically
pytest .orchestrator/tests/unit/test_portal.py::TestHealthEndpoint -v

# Run all portal tests to ensure no regressions
pytest .orchestrator/tests/unit/test_portal.py -v

# Manual verification (start server first with: uvicorn .orchestrator.server.app:app)
curl http://localhost:8000/api/health
```
