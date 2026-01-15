# Plan: d:\agentic-orchestrator\.orchestrator\specs\pending\001_health-api-endpoint-orchestratorserverapppy-

Request: d:\agentic-orchestrator\.orchestrator\specs\pending\001_health-api-endpoint-orchestratorserverapppy-endpoint\plan.md
Complexity: simple

## Goal

Add GET /health endpoint returning {"status": "ok", "version": "1.0.0", "uptime_seconds": float} alongside existing /api/health for backward compatibility.

## Context

- Existing /api/health endpoint at app.py:175-183 returns {"status": "healthy", "version", "uptime_seconds"}
- START_TIME global at line 39 tracks uptime
- User wants /health path (no /api prefix) with "ok"/"error" status values
- Existing tests in test_portal.py:65-99 cover /api/health endpoint
- Version is hardcoded "1.0.0" in FastAPI app init

## Steps

1. Add /health endpoint to app.py
   DO: Add new GET endpoint at /health path that returns {"status": "ok", "version": app.version, "uptime_seconds": calculated_uptime}. Use same uptime calculation as existing /api/health endpoint (time.time() - START_TIME). Status should be "ok" for healthy state.
   IN: .orchestrator/server/app.py
   OUT: .orchestrator/server/app.py (modified)
   DONE: Server starts without errors; GET /health returns valid JSON response
   NEEDS: none

## Verify

- pytest .orchestrator/tests/unit/test_portal.py -v passes all tests
- Manual check: GET /health returns {"status": "ok", "version": "1.0.0", "uptime_seconds": <number>}
- Manual check: GET /api/health still returns {"status": "healthy", ...} (backward compatibility)
