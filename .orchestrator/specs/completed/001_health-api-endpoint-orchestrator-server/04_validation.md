# Validation

> Part of plan: Add a /health API endpoint to the orchestrator server (server/app.py). The endpoint should return JSON with status, version, and uptime. Include pytest tests in tests/unit/test_portal.py.

```json
{
  "status": "needs_revision",
  "score": 78,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "All 3 steps have valid actions (3 modify)",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "All steps target specific files: .orchestrator/server/app.py (2 steps), .orchestrator/tests/unit/test_portal.py (1 step)",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": true,
      "details": "All 3 modify steps include Python code blocks with complete implementations",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Dependency graph: Step 1.1 (none) → Step 2.1 (1.1) → Step 3.1 (2.1) - valid DAG, no cycles",
      "severity": "critical"
    },
    {
      "name": "testing_included",
      "passed": true,
      "details": "Phase 3 includes comprehensive test class with 5 test methods covering status code, response fields, and structure",
      "severity": "high"
    },
    {
      "name": "validation_commands",
      "passed": true,
      "details": "pytest commands and curl command provided for verification",
      "severity": "medium"
    },
    {
      "name": "patterns_followed",
      "passed": true,
      "details": "Plan references existing patterns: /api/hello endpoint pattern, TestHelloEndpoint test class pattern",
      "severity": "medium"
    },
    {
      "name": "no_vague_refs",
      "passed": true,
      "details": "All file paths and locations are specific, code placement instructions reference exact sections",
      "severity": "high"
    },
    {
      "name": "phases_ordered",
      "passed": true,
      "details": "Logical ordering: Phase 1 (Setup) → Phase 2 (Core Implementation) → Phase 3 (Testing)",
      "severity": "medium"
    },
    {
      "name": "no_placeholders",
      "passed": true,
      "details": "No TODO/TBD placeholders found in code or descriptions",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 1.1",
      "issue": "datetime module is likely already imported or may conflict with existing imports",
      "fix_suggestion": "Verify if datetime is already imported in app.py. If so, remove the redundant import. The step should read the file first to identify the exact insertion point after existing imports."
    },
    {
      "step": "Step 2.1",
      "issue": "Code references app.version but plan doesn't verify this attribute exists on the FastAPI app instance",
      "fix_suggestion": "Verify app.version exists or hardcode version string like '1.0.0'. If app.version doesn't exist, the endpoint will raise AttributeError at runtime."
    },
    {
      "step": "Step 3.1",
      "issue": "Test assumes version is '1.0.0' but Step 2.1 uses app.version which may have different value",
      "fix_suggestion": "Either hardcode version in endpoint code to match test expectation, or make test assert isinstance(data['version'], str) instead of exact value match"
    }
  ],
  "warnings": [
    {
      "step": "Step 1.1",
      "issue": "Code comment says 'Add after the existing imports' but doesn't specify exact line number or anchor import",
      "recommendation": "Specify exact anchor like 'Add after: from fastapi import FastAPI' for precise placement"
    },
    {
      "step": "Step 2.1",
      "issue": "Code comment references '/api/hello' pattern but doesn't confirm this endpoint exists",
      "recommendation": "Scout should have verified /api/hello exists; if it doesn't, remove the pattern reference"
    },
    {
      "step": "Step 3.1",
      "issue": "Tests don't cover error scenarios or edge cases",
      "recommendation": "Consider adding test for uptime calculation accuracy or concurrent request handling"
    },
    {
      "step": "Validation Commands",
      "issue": "Manual curl command assumes server runs on localhost:8000 which may not be the configured port",
      "recommendation": "Add note about checking actual port configuration or use environment variable"
    }
  ],
  "summary": "Plan has good structure with clear phases, specific file paths, and comprehensive test coverage. However, there are three blocking issues that could cause runtime failures: (1) potential duplicate datetime import, (2) unverified app.version attribute that may not exist on the FastAPI instance, and (3) test-code mismatch where test expects hardcoded '1.0.0' but implementation uses dynamic app.version. These issues indicate the plan was created without fully reading the target files to verify existing imports and available attributes. The PLANNER should read .orchestrator/server/app.py to verify datetime import status and app.version availability before proceeding."
}
```
