# Architecture Design

> Part of plan: Add a new API health check endpoint

Now I have all the information I need. Let me design the architecture for the health check endpoint.

---

# Architecture Design: API Health Check Endpoint

## Overview

Add a `/api/health` endpoint to the SDLC Orchestrator API that provides health status information for monitoring and operational purposes.

## Endpoint Specification

### `GET /api/health`

**Purpose:** Provide a standardized health check endpoint for load balancers, monitoring systems, and operational tooling.

**Response Format:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600.5,
  "timestamp": "2024-01-15T10:30:00.000000",
  "components": {
    "api": "healthy",
    "specs_directory": "healthy"
  },
  "active_runs": 2
}
```

## Implementation Details

### 1. Add Startup Time Tracking

Add a module-level variable to track when the server started:

```python
# Near line 51 (after active_runs declaration)
SERVER_START_TIME = datetime.now()
```

### 2. Add Health Response Model

Add a Pydantic model for the response (in the Pydantic Models section, around line 77):

```python
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    timestamp: str
    components: Dict[str, str]
    active_runs: int
```

### 3. Add Health Check Endpoint

Add the endpoint at the beginning of the API Routes section (line 164, after the section comment):

```python
@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """Health check endpoint for monitoring and load balancers."""
    now = datetime.now()
    uptime = (now - SERVER_START_TIME).total_seconds()
    
    # Check component health
    components = {
        "api": "healthy"
    }
    
    # Check specs directory accessibility
    specs_dir = ORCHESTRATOR_DIR / "specs"
    if specs_dir.exists() and specs_dir.is_dir():
        components["specs_directory"] = "healthy"
    else:
        components["specs_directory"] = "degraded"
    
    # Determine overall status
    overall_status = "healthy"
    if any(v != "healthy" for v in components.values()):
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=app.version,
        uptime_seconds=uptime,
        timestamp=now.isoformat(),
        components=components,
        active_runs=len(active_runs)
    )
```

### 4. Add Unit Test

Add a test in `TestFastAPIEndpoints` class (around line 231):

```python
def test_api_health_endpoint(self, client):
    """Test health check endpoint returns correct structure."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert data["version"] == "1.0.0"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], float)
    assert data["uptime_seconds"] >= 0
    assert "timestamp" in data
    assert "components" in data
    assert "api" in data["components"]
    assert "active_runs" in data
```

## File Changes Summary

| File | Change |
|------|--------|
| `server/app.py` | Add `SERVER_START_TIME` variable (line ~52) |
| `server/app.py` | Add `HealthResponse` Pydantic model (line ~77) |
| `server/app.py` | Add `/api/health` endpoint (line ~165) |
| `tests/unit/test_portal.py` | Add `test_api_health_endpoint` test (line ~231) |

## Design Rationale

1. **Placement in API Routes section:** Follows existing code organization patterns
2. **Pydantic response model:** Consistent with existing API patterns and provides OpenAPI documentation
3. **Component health checks:** Extensible for future health checks (database, external services, etc.)
4. **Uptime tracking:** Useful for monitoring restarts and stability
5. **Version from app object:** Uses existing version defined in FastAPI app initialization (DRY principle)
6. **Active runs count:** Provides operational visibility into current workload
7. **Degraded vs Unhealthy:** Uses "degraded" for non-critical issues, reserving "unhealthy" for future critical failures

## Future Extensibility

The `components` dictionary can be extended to include:
- Database connectivity (if added)
- External API availability
- Disk space checks
- Memory usage thresholds
- Claude API connectivity
