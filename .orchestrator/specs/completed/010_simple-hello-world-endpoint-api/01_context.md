# Codebase Context

> Part of plan: Add a simple hello world endpoint to the API

## Project Overview

This is an **AI-powered SDLC (Software Development Lifecycle) Orchestrator** built with:
- **Language:** Python 3.11+
- **Web Framework:** FastAPI (with uvicorn, jinja2 for templates)
- **Dependencies:** rich, httpx, pytest (for testing)
- **Package Manager:** UV (with pyproject.toml)
- **Purpose:** Automates software development workflows (planning, building, reviewing, fixing) using Claude Code CLI

The project already has a web API at `.orchestrator/server/app.py` and a `/api/hello` endpoint already exists.

## Relevant Files

| File | Purpose |
|------|---------|
| `.orchestrator/server/app.py:165-168` | **Existing hello endpoint** - `/api/hello` already returns `{"message": "hello world"}` |
| `.orchestrator/pyproject.toml` | Project configuration with FastAPI in optional dependencies |
| `.orchestrator/tests/unit/test_portal.py:50-62` | **Existing test** for the hello endpoint |
| `.orchestrator/cli.py` | CLI entry point with `portal` command to run the web server |

## Existing Patterns

1. **FastAPI Route Pattern:**
   ```python
   @app.get("/api/hello")
   async def api_hello():
       """Return a simple hello world message for testing."""
       return {"message": "hello world"}
   ```

2. **Test Pattern (using FastAPI TestClient):**
   ```python
   def test_api_hello_returns_hello_world(self):
       from fastapi.testclient import TestClient
       from server.app import app
       client = TestClient(app)
       response = client.get("/api/hello")
       assert response.status_code == 200
       assert response.json() == {"message": "hello world"}
   ```

3. **API routes grouped:** All API routes use `/api/` prefix
4. **Docstrings:** All endpoints have docstrings
5. **Async handlers:** All API handlers are async functions

## Dependencies

- **FastAPI** (optional dependency `[web]`)
- **uvicorn** (for running the server)
- **pytest** + **fastapi.testclient** (for testing)
- No additional dependencies needed for a hello world endpoint

## Considerations

**The hello world endpoint already exists!** 

- Location: `.orchestrator/server/app.py` at lines 165-168
- Endpoint: `GET /api/hello`
- Response: `{"message": "hello world"}`
- Test: `.orchestrator/tests/unit/test_portal.py` lines 50-62

No implementation is required - the feature is already implemented and tested. If a different type of hello world endpoint is needed (different path, different response, HTML instead of JSON), clarification would be required.
