# Plan: Add a /health API endpoint to server/app.py that returns JSON with status, version, and uptime. Incl

Request: Add a /health API endpoint to server/app.py that returns JSON with status, version, and uptime. Include pytest tests in tests/unit/test_portal.py
Complexity: simple

## Goal

Verify existing health endpoint implementation meets all requirements (status, version, uptime in JSON response with pytest tests).

## Context

- Health endpoints already exist at /health and /api/health in app.py lines 175-194
- Test coverage already exists in test_portal.py lines 65-99 (TestHealthEndpoint class)
- Response includes status, version (from app.version), and uptime_seconds
- No new implementation needed - only verification required

## Steps

1. Verify health endpoint implementation
   DO: Confirm /health and /api/health endpoints return JSON with status, version, and uptime_seconds fields
   IN: .orchestrator/server/app.py:175-194
   OUT: Verification that implementation matches requirements
   DONE: Endpoints return all three required fields (status, version, uptime)
   NEEDS: none

2. Verify pytest test coverage
   DO: Confirm TestHealthEndpoint class tests all required response fields and both endpoint paths
   IN: .orchestrator/tests/unit/test_portal.py:65-99
   OUT: Verification that test coverage is complete
   DONE: Tests exist for status, version, and uptime fields on health endpoints
   NEEDS: none

3. Run existing health endpoint tests
   DO: Execute pytest on the health endpoint tests to confirm they pass
   IN: .orchestrator/tests/unit/test_portal.py
   OUT: Test execution results
   DONE: All TestHealthEndpoint tests pass with no failures
   NEEDS: 1, 2

## Verify

- pytest .orchestrator/tests/unit/test_portal.py::TestHealthEndpoint -v passes
- Manual check: GET /health returns {"status": "healthy", "version": "1.0.0", "uptime_seconds": <number>}
