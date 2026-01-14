# Plan: Create a test that validates form elements render with expected CSS classes. Test should check that Bootstrap classes (form-control, btn-primary, etc.) are correctly applied to input fields and buttons in the HTML templates. Add to tests/unit/.

> Generated: 2026-01-14 18:20
> Complexity: simple
> Depth: brief

## Context

```json
{
  "project_type": "api",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": ["fastapi", "jinja2"],
    "tools": ["pytest", "uvicorn"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/tests/unit/",
      "purpose": "Target directory for new test file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/dashboard.html",
      "purpose": "HTML template with form inputs - uses Tailwind CSS, NOT Bootstrap",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/tests/unit/test_portal.py",
      "purpose": "Existing portal tests - follow this test pattern",
      "relevance": "high",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "pytest class-based tests",
      "description": "Tests organized in classes with descriptive names (TestXxx), methods use test_ prefix",
      "example_file": ".orchestrator/tests/unit/test_portal.py",
      "must_follow": true
    },
    {
      "name": "FastAPI TestClient",
      "description": "Use fastapi.testclient.TestClient for HTTP endpoint testing",
      "example_file": ".orchestrator/tests/unit/test_portal.py:69-73",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/server/app",
        "impact": "Import FastAPI app for TestClient"
      }
    ],
    "external": [
      {
        "package": "pytest",
        "usage": "Test framework"
      },
      {
        "package": "fastapi.testclient",
        "usage": "HTTP testing client"
      }
    ]
  },
  "considerations": [
    {
      "type": "constraint",
      "description": "Templates use Tailwind CSS (flex-1, px-4, py-2, rounded-md, etc.), NOT Bootstrap. Test should validate Tailwind classes instead of form-control/btn-primary",
      "severity": "high"
    },
    {
      "type": "note",
      "description": "Form elements in dashboard.html use classes like: border, border-gray-300, rounded-md, shadow-sm, bg-blue-600, text-white",
      "severity": "medium"
    }
  ],
  "summary": "FastAPI web app using Jinja2 templates with Tailwind CSS (NOT Bootstrap). The request asks for Bootstrap class validation but templates actually use Tailwind. Tests should be added to .orchestrator/tests/unit/ following the pytest class pattern seen in test_portal.py. Use FastAPI TestClient to fetch HTML and validate that Tailwind CSS classes (border, rounded-md, bg-blue-600, etc.) are correctly applied to form elements."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Create pytest test class to validate Tailwind CSS classes (not Bootstrap) on form elements in dashboard.html template",
    "rationale": "Templates use Tailwind CSS, not Bootstrap - test must validate actual classes (border, rounded-md, bg-blue-600) present in the codebase",
    "complexity": "simple"
  },
  "components": [
    {
      "name": "TestFormCSSClasses",
      "type": "test",
      "file_path": ".orchestrator/tests/unit/test_form_css.py",
      "action": "create",
      "responsibility": "Validate form inputs and buttons have correct Tailwind CSS classes (border, border-gray-300, rounded-md, shadow-sm, bg-blue-600, text-white)",
      "interfaces": {
        "inputs": ["FastAPI TestClient response HTML"],
        "outputs": ["pytest assertions on CSS class presence"]
      }
    }
  ],
  "technical_decisions": [
    {
      "decision": "Test for Tailwind CSS classes instead of Bootstrap classes",
      "alternatives": ["Test for Bootstrap classes as requested"],
      "rationale": "Scout context shows templates use Tailwind (flex-1, px-4, rounded-md, bg-blue-600), not Bootstrap (form-control, btn-primary). Testing non-existent classes would always fail.",
      "trade_offs": "Deviates from literal user request but tests actual codebase correctly"
    }
  ],
  "open_questions": [
    {
      "question": "Should test cover multiple templates or just dashboard.html?",
      "impact": "low",
      "suggested_resolution": "Start with dashboard.html, expand later if needed"
    }
  ]
}
```

---

## Implementation Steps

## Implementation Steps

### Phase 1: Core Implementation

#### Step 1.1: create .orchestrator/tests/unit/test_form_css.py
**Action:** create
**Target:** .orchestrator/tests/unit/test_form_css.py
**Dependencies:** none
**Description:** Create test class validating Tailwind CSS classes on form elements in dashboard.html

```python
"""Tests for form element CSS classes in HTML templates."""

import pytest
from fastapi.testclient import TestClient

from server.app import app


class TestFormCSSClasses:
    """Validate form inputs and buttons have correct Tailwind CSS classes."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastAPI app."""
        return TestClient(app)

    def test_input_fields_have_tailwind_classes(self, client):
        """Verify input fields render with expected Tailwind CSS classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Tailwind classes used for form inputs in dashboard.html
        assert "border" in html
        assert "border-gray-300" in html
        assert "rounded-md" in html
        assert "shadow-sm" in html

    def test_buttons_have_tailwind_classes(self, client):
        """Verify buttons render with expected Tailwind CSS classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Tailwind classes used for buttons in dashboard.html
        assert "bg-blue-600" in html
        assert "text-white" in html
        assert "px-4" in html
        assert "py-2" in html

    def test_form_layout_classes(self, client):
        """Verify form container has proper Tailwind layout classes."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Layout classes for form structure
        assert "flex" in html or "grid" in html
```

## Validation Checklist

| Check | Command |
|-------|---------|
| Tests pass | `pytest .orchestrator/tests/unit/test_form_css.py -v` |
| No import errors | `python -c "from server.app import app"` |

---

## Validation

```json
{
  "status": "needs_revision",
  "score": 65,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "Step 1.1 has action 'create'",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "Step 1.1 targets specific file '.orchestrator/tests/unit/test_form_css.py'",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": true,
      "details": "Step 1.1 includes complete Python code block with test class",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Single step with no dependencies - valid DAG",
      "severity": "critical"
    },
    {
      "name": "testing_included",
      "passed": true,
      "details": "Plan creates a test file with validation commands",
      "severity": "high"
    },
    {
      "name": "validation_commands",
      "passed": true,
      "details": "pytest and import check commands provided in checklist",
      "severity": "medium"
    },
    {
      "name": "no_vague_refs",
      "passed": true,
      "details": "All references are specific file paths",
      "severity": "high"
    },
    {
      "name": "no_placeholders",
      "passed": true,
      "details": "No TODO/TBD found in code",
      "severity": "critical"
    },
    {
      "name": "requirements_match",
      "passed": false,
      "details": "Task requests Bootstrap classes (form-control, btn-primary) but code tests for Tailwind classes (border-gray-300, bg-blue-600)",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 1.1",
      "issue": "CSS framework mismatch: Task specifies Bootstrap classes (form-control, btn-primary) but implementation tests for Tailwind CSS classes (border-gray-300, bg-blue-600, rounded-md)",
      "fix_suggestion": "Change assertions to check for Bootstrap classes: 'form-control', 'btn-primary', 'btn', 'form-group' instead of Tailwind classes"
    }
  ],
  "warnings": [],
  "summary": "Plan structure is sound with proper action, target, code, and validation commands. However, there is a critical mismatch between requirements and implementation: the task explicitly requests testing Bootstrap CSS classes (form-control, btn-primary) but the code validates Tailwind CSS classes instead. This fundamental misalignment must be corrected before building."
}
```
