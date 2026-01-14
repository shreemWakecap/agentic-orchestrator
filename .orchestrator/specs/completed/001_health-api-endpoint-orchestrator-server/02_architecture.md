# Architecture Design

> Part of plan: Add a /health API endpoint to the orchestrator server (server/app.py). The endpoint should return JSON with status, version, and uptime. Include pytest tests in tests/unit/test_portal.py.

```json
{
  "approach": {
    "summary": "Add /api/health endpoint to existing FastAPI server with status, version, and uptime tracking",
    "rationale": "Follows existing /api/hello pattern exactly, reuses app.version for version info, adds minimal START_TIME variable for uptime calculation - no new files or abstractions needed",
    "complexity": "simple"
  },
  "components": [
    {
      "name": "START_TIME module variable",
      "type": "config",
      "file_path": ".orchestrator/server/app.py",
      "action": "modify",
      "responsibility": "Store server startup timestamp for uptime calculation",
      "interfaces": {
        "inputs": ["datetime.datetime.now() at module load"],
        "outputs": ["START_TIME: datetime.datetime"]
      }
    },
    {
      "name": "health_check endpoint",
      "type": "route",
      "file_path": ".orchestrator/server/app.py",
      "action": "modify",
      "responsibility": "Handle GET /api/health and return status, version, uptime",
      "interfaces": {
        "inputs": ["GET request to /api/health"],
        "outputs": ["JSON dict with status, version, uptime_seconds"]
      }
    },
    {
      "name": "TestHealthEndpoint",
      "type": "test",
      "file_path": ".orchestrator/tests/unit/test_portal.py",
      "action": "modify",
      "responsibility": "Test health endpoint response structure and values",
      "interfaces": {
        "inputs": ["TestClient fixture"],
        "outputs": ["pytest test results"]
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "Client",
      "to": "health_check endpoint",
      "data": "GET /api/health",
      "description": "HTTP GET request to health endpoint"
    },
    {
      "step": 2,
      "from": "health_check endpoint",
      "to": "app.version",
      "data": "version string",
      "description": "Read version from FastAPI app instance"
    },
    {
      "step": 3,
      "from": "health_check endpoint",
      "to": "START_TIME",
      "data": "startup datetime",
      "description": "Calculate uptime from module-level START_TIME"
    },
    {
      "step": 4,
      "from": "health_check endpoint",
      "to": "Client",
      "data": "{status, version, uptime_seconds}",
      "description": "Return JSON response"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Use module-level START_TIME variable instead of app.state",
      "alternatives": ["app.state.start_time", "lifespan context manager", "startup event handler"],
      "rationale": "Simplest approach - module loads once at server start, datetime.now() captured immediately, no lifecycle complexity",
      "trade_offs": "Less elegant than lifespan pattern but matches codebase simplicity"
    },
    {
      "decision": "Return uptime as seconds (float) rather than formatted string",
      "alternatives": ["Human readable string like '2h 30m'", "ISO duration format", "Structured dict with days/hours/minutes"],
      "rationale": "Numeric value is machine-parseable, client can format as needed, consistent with standard health check patterns",
      "trade_offs": "Client must format for human display"
    },
    {
      "decision": "Use /api/health path to match existing /api/hello pattern",
      "alternatives": ["/health", "/healthz", "/_health"],
      "rationale": "Consistency with existing API route convention in codebase",
      "trade_offs": "Slightly longer path than kubernetes-style /healthz"
    },
    {
      "decision": "Hardcode status as 'healthy' for simple implementation",
      "alternatives": ["Check database connection", "Check external dependencies", "Return degraded states"],
      "rationale": "Task scope is basic health endpoint - no external dependencies to check in current architecture",
      "trade_offs": "Cannot report partial failures, but appropriate for current simple server"
    }
  ],
  "integration_points": [
    {
      "component": ".orchestrator/server/app.py",
      "external_system": "FastAPI app instance",
      "protocol": "app.version attribute",
      "notes": "Version already defined as '1.0.0' in FastAPI() constructor"
    }
  ],
  "open_questions": [
    {
      "question": "Should uptime include milliseconds precision or round to whole seconds?",
      "impact": "low",
      "suggested_resolution": "Use float with reasonable precision (2 decimal places) for sub-second accuracy without noise"
    }
  ]
}
```
