# Architecture Design

> Part of plan: Create a test module with 3 independent model files (user.py, product.py, order.py) in tests/parallel_test/models/, a registry.py that imports all models, and 2 utility files (validators.py, formatters.py) in tests/parallel_test/utils/. Each file should have a simple class or function. This tests parallel build capability.

```json
{
  "approach": {
    "summary": "Create a parallel test module with independent model classes, utility functions, and a central registry that imports all models",
    "rationale": "Maximizes parallel creation opportunity by keeping models and utilities independent, with registry as the only dependent component that must be created after models",
    "complexity": "simple"
  },
  "components": [
    {
      "name": "User",
      "type": "model",
      "file_path": "tests/parallel_test/models/user.py",
      "action": "create",
      "responsibility": "Define a simple User model class with basic attributes",
      "interfaces": {
        "inputs": ["name: str", "email: str"],
        "outputs": ["User instance"]
      }
    },
    {
      "name": "Product",
      "type": "model",
      "file_path": "tests/parallel_test/models/product.py",
      "action": "create",
      "responsibility": "Define a simple Product model class with basic attributes",
      "interfaces": {
        "inputs": ["name: str", "price: float"],
        "outputs": ["Product instance"]
      }
    },
    {
      "name": "Order",
      "type": "model",
      "file_path": "tests/parallel_test/models/order.py",
      "action": "create",
      "responsibility": "Define a simple Order model class with basic attributes",
      "interfaces": {
        "inputs": ["order_id: str", "total: float"],
        "outputs": ["Order instance"]
      }
    },
    {
      "name": "ModelsInit",
      "type": "config",
      "file_path": "tests/parallel_test/models/__init__.py",
      "action": "create",
      "responsibility": "Package init exposing User, Product, Order classes",
      "interfaces": {
        "inputs": [],
        "outputs": ["User", "Product", "Order"]
      }
    },
    {
      "name": "validate_email",
      "type": "util",
      "file_path": "tests/parallel_test/utils/validators.py",
      "action": "create",
      "responsibility": "Provide simple validation utility functions",
      "interfaces": {
        "inputs": ["value: str"],
        "outputs": ["bool"]
      }
    },
    {
      "name": "format_currency",
      "type": "util",
      "file_path": "tests/parallel_test/utils/formatters.py",
      "action": "create",
      "responsibility": "Provide simple formatting utility functions",
      "interfaces": {
        "inputs": ["amount: float"],
        "outputs": ["str"]
      }
    },
    {
      "name": "UtilsInit",
      "type": "config",
      "file_path": "tests/parallel_test/utils/__init__.py",
      "action": "create",
      "responsibility": "Package init exposing validator and formatter functions",
      "interfaces": {
        "inputs": [],
        "outputs": ["validate_email", "format_currency"]
      }
    },
    {
      "name": "Registry",
      "type": "service",
      "file_path": "tests/parallel_test/registry.py",
      "action": "create",
      "responsibility": "Central registry that imports and exposes all model classes",
      "interfaces": {
        "inputs": [],
        "outputs": ["MODELS dict mapping names to classes"]
      }
    },
    {
      "name": "ParallelTestInit",
      "type": "config",
      "file_path": "tests/parallel_test/__init__.py",
      "action": "create",
      "responsibility": "Package init for parallel_test module",
      "interfaces": {
        "inputs": [],
        "outputs": []
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "Build System",
      "to": "models/user.py, models/product.py, models/order.py",
      "data": "file creation commands",
      "description": "Create 3 model files in parallel (no dependencies)"
    },
    {
      "step": 2,
      "from": "Build System",
      "to": "utils/validators.py, utils/formatters.py",
      "data": "file creation commands",
      "description": "Create 2 utility files in parallel (no dependencies, can run with step 1)"
    },
    {
      "step": 3,
      "from": "Build System",
      "to": "models/__init__.py, utils/__init__.py, __init__.py",
      "data": "file creation commands",
      "description": "Create package init files (can run with steps 1-2)"
    },
    {
      "step": 4,
      "from": "registry.py",
      "to": "models/user.py, models/product.py, models/order.py",
      "data": "import statements",
      "description": "Registry imports all model classes after they exist"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Use simple dataclass-style classes for models",
      "alternatives": ["Plain classes with __init__", "NamedTuples", "Pydantic models"],
      "rationale": "Minimal code, clear structure, no external dependencies needed for test",
      "trade_offs": "Less feature-rich than Pydantic but appropriate for test scope"
    },
    {
      "decision": "Registry uses a MODELS dictionary mapping class names to classes",
      "alternatives": ["List of classes", "Module-level imports only", "Registration decorator"],
      "rationale": "Dictionary provides name-based lookup and is simple to implement",
      "trade_offs": "Manual registration vs automatic discovery"
    },
    {
      "decision": "Place test module at tests/parallel_test/ (project root) not .orchestrator/tests/",
      "alternatives": ["Put in .orchestrator/tests/parallel_test/"],
      "rationale": "Scout context specifies tests/ at project root for this new test module",
      "trade_offs": "Separate from existing orchestrator tests but matches request"
    }
  ],
  "integration_points": [
    {
      "component": "tests/parallel_test/registry.py",
      "external_system": "tests/parallel_test/models/",
      "protocol": "Python imports",
      "notes": "Registry imports User, Product, Order from models package"
    }
  ],
  "open_questions": []
}
```
