# Codebase Context

> Part of plan: Add a /health API endpoint to the orchestrator server (server/app.py). The endpoint should return JSON with status, version, and uptime. Include pytest tests in tests/unit/test_portal.py.

```json
{
  "project_type": "api",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": ["fastapi"],
    "tools": ["pytest", "pytest-asyncio", "uvicorn", "uv"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/server/app.py",
      "purpose": "FastAPI server - add /health endpoint here",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/tests/unit/test_portal.py",
      "purpose": "Portal tests - add health endpoint tests here",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/pyproject.toml",
      "purpose": "Project config with version 1.0.0 - use for version in health response",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "API route pattern",
      "description": "API endpoints are async functions decorated with @app.get/post under '# ============== API Routes ==============' section, return dicts directly for JSON serialization",
      "example_file": ".orchestrator/server/app.py",
      "must_follow": true
    },
    {
      "name": "Test class pattern",
      "description": "Tests organized in classes by feature (e.g., TestHelloEndpoint, TestFastAPIEndpoints), use pytest fixtures for TestClient",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": true
    },
    {
      "name": "TestClient fixture pattern",
      "description": "Create TestClient as pytest fixture, import from fastapi.testclient, instantiate with app",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": true
    },
    {
      "name": "Existing hello endpoint pattern",
      "description": "Simple GET endpoint at /api/hello returns JSON dict - /health should follow similar pattern at /api/health",
      "example_file": ".orchestrator/server/app.py",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/pyproject.toml",
        "impact": "Contains version string (1.0.0) to include in health response"
      },
      {
        "module": "app global variables",
        "impact": "Need to track server start time for uptime calculation - add module-level variable"
      }
    ],
    "external": [
      {
        "package": "fastapi",
        "usage": "FastAPI app and route decorators"
      },
      {
        "package": "datetime",
        "usage": "Already imported - use for calculating uptime"
      }
    ]
  },
  "considerations": [
    {
      "type": "note",
      "description": "Server already imports datetime - can reuse for uptime calculation",
      "severity": "low"
    },
    {
      "type": "note",
      "description": "Version is hardcoded in FastAPI app instantiation (line 41) as '1.0.0' - can reference app.version",
      "severity": "low"
    },
    {
      "type": "constraint",
      "description": "Need to add a module-level START_TIME variable to track server startup for uptime",
      "severity": "medium"
    },
    {
      "type": "note",
      "description": "Existing test pattern uses TestClient from fastapi.testclient - follow same approach",
      "severity": "low"
    },
    {
      "type": "edge_case",
      "description": "Uptime should be returned in a human-readable format (seconds) or as structured data",
      "severity": "low"
    }
  ],
  "summary": "FastAPI-based API server at .orchestrator/server/app.py with existing pattern of simple JSON-returning endpoints (see /api/hello). Add /api/health endpoint returning status, version (from app.version='1.0.0'), and uptime (requires adding START_TIME module variable). Tests go in .orchestrator/tests/unit/test_portal.py following TestHelloEndpoint class pattern with TestClient fixture. No external dependencies needed - datetime already imported."
}
```
