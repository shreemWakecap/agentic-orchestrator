# Codebase Context

> Part of plan: Create a test module with 3 independent model files (user.py, product.py, order.py) in tests/parallel_test/models/, a registry.py that imports all models, and 2 utility files (validators.py, formatters.py) in tests/parallel_test/utils/. Each file should have a simple class or function. This tests parallel build capability.

Now I have enough context about this project. Let me produce the structured JSON output.

```json
{
  "project_type": "cli",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": [],
    "tools": ["pytest", "uv", "claude-code"]
  },
  "relevant_files": [
    {
      "path": "tests/parallel_test/models/user.py",
      "purpose": "New file - User model class",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/models/product.py",
      "purpose": "New file - Product model class",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/models/order.py",
      "purpose": "New file - Order model class",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/models/__init__.py",
      "purpose": "New file - Package init for models",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/registry.py",
      "purpose": "New file - Registry that imports all models",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/utils/validators.py",
      "purpose": "New file - Validator utility functions",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/utils/formatters.py",
      "purpose": "New file - Formatter utility functions",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/utils/__init__.py",
      "purpose": "New file - Package init for utils",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": "tests/parallel_test/__init__.py",
      "purpose": "New file - Package init for parallel_test module",
      "relevance": "high",
      "action_needed": "create"
    },
    {
      "path": ".orchestrator/tests/conftest.py",
      "purpose": "Existing test fixtures and pytest configuration",
      "relevance": "medium",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/tests/unit/test_agent.py",
      "purpose": "Example of existing unit test structure",
      "relevance": "low",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/workflows/building.py",
      "purpose": "Contains parallel build logic - this test validates it",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "Test directory structure",
      "description": "Tests are located in .orchestrator/tests/ with unit/ and integration/ subdirectories",
      "example_file": ".orchestrator/tests/unit/test_agent.py",
      "must_follow": false
    },
    {
      "name": "Python package structure",
      "description": "All Python directories include __init__.py files for proper package imports",
      "example_file": ".orchestrator/tests/__init__.py",
      "must_follow": true
    },
    {
      "name": "Simple docstrings",
      "description": "Files include brief docstrings describing purpose",
      "example_file": ".orchestrator/tests/__init__.py",
      "must_follow": false
    },
    {
      "name": "Class-based organization",
      "description": "Related functionality grouped in classes (for models) or functions (for utilities)",
      "example_file": ".orchestrator/tests/unit/test_agent.py",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": "tests/parallel_test/models",
        "impact": "registry.py must import from models/user.py, models/product.py, models/order.py"
      }
    ],
    "external": []
  },
  "considerations": [
    {
      "type": "note",
      "description": "This is a new test module at project root level (tests/), not inside .orchestrator/tests/",
      "severity": "medium"
    },
    {
      "type": "note",
      "description": "The 3 model files (user.py, product.py, order.py) are independent and can be created in parallel",
      "severity": "low"
    },
    {
      "type": "note",
      "description": "The 2 utility files (validators.py, formatters.py) are independent and can be created in parallel",
      "severity": "low"
    },
    {
      "type": "constraint",
      "description": "registry.py depends on all model files being created first since it imports them",
      "severity": "medium"
    },
    {
      "type": "note",
      "description": "Each file should contain simple, minimal code - this tests parallel creation capability not complex logic",
      "severity": "low"
    }
  ],
  "summary": "This is a Python CLI project (SDLC Orchestrator) that uses pytest for testing. The request is to create a new test module at tests/parallel_test/ (at project root, not inside .orchestrator). The module needs 3 independent model files in models/, 2 independent utility files in utils/, and a registry.py that imports all models. All new directories need __init__.py files. The 3 model files and 2 utility files can be created in parallel, but registry.py must be created after the models since it imports them. This tests the parallel build capability of the orchestrator."
}
```
