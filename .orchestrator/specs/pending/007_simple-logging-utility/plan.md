# Plan: Add a simple logging utility

> Generated: 2026-01-15 10:21
> Complexity: simple
> Depth: brief

## Context

```json
{
  "project_type": "cli",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": [],
    "tools": ["uv", "claude-code-cli", "pytest"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/core/config.py",
      "purpose": "Configuration module - already has logging pattern to follow",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/core/__init__.py",
      "purpose": "Core module init - add logging utility export here",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/core/agent.py",
      "purpose": "Existing logging usage - reference for integration",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "Standard library logging",
      "description": "Uses Python's built-in logging module with logger = logging.getLogger(__name__)",
      "example_file": ".orchestrator/core/config.py",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/core",
        "impact": "New logging utility should live in core/ and be exported from __init__.py"
      }
    ],
    "external": [
      {
        "package": "logging (stdlib)",
        "usage": "Already in use throughout codebase"
      }
    ]
  },
  "considerations": [
    {
      "type": "note",
      "description": "Codebase already uses logging.getLogger(__name__) pattern - utility should configure handlers/formatters",
      "severity": "medium"
    },
    {
      "type": "constraint",
      "description": "Keep simple - just provide easy setup for console/file logging with sensible defaults",
      "severity": "low"
    }
  ],
  "summary": "Python CLI project using standard library logging with getLogger(__name__) pattern. A logging utility should be added to .orchestrator/core/ to provide centralized configuration (handlers, formatters, levels). Follow existing pattern in config.py. Export from core/__init__.py."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Add a logging utility module to core/ that provides centralized handler/formatter configuration while preserving existing getLogger(__name__) pattern",
    "rationale": "Follows established stdlib logging pattern, centralizes configuration, minimal changes needed",
    "complexity": "simple"
  },
  "components": [
    {
      "name": "LoggingUtility",
      "type": "util",
      "file_path": ".orchestrator/core/logging.py",
      "action": "create",
      "responsibility": "Provide setup_logging() function to configure handlers, formatters, and levels",
      "interfaces": {
        "inputs": ["level: str", "log_file: Optional[str]"],
        "outputs": ["None (configures root logger)"]
      }
    },
    {
      "name": "CoreInit",
      "type": "config",
      "file_path": ".orchestrator/core/__init__.py",
      "action": "modify",
      "responsibility": "Export setup_logging from logging module",
      "interfaces": {
        "inputs": [],
        "outputs": ["setup_logging function"]
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "Application entry point",
      "to": "setup_logging()",
      "data": "level, optional file path",
      "description": "Configure logging at startup"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Configure root logger with sensible defaults",
      "alternatives": ["Return configured logger instance", "Use logging.config.dictConfig"],
      "rationale": "Simplest approach that works with existing getLogger(__name__) calls throughout codebase",
      "trade_offs": "Less granular control, but matches current usage"
    }
  ],
  "integration_points": [],
  "open_questions": []
}
```

---

## Implementation Steps

# Plan: Simple Logging Utility

## Goal
Add a centralized logging configuration utility to core/ that sets up handlers and formatters while preserving the existing `getLogger(__name__)` pattern.

## Steps
1. Create `.orchestrator/core/logging_utils.py` with a `setup_logging(level="INFO", log_file=None)` function that configures the root logger with console handler, optional file handler, and a standard format `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

2. Export `setup_logging` from `.orchestrator/core/__init__.py` by adding the import and including it in `__all__`

3. Call `setup_logging()` at the entry point of the CLI (typically in `__main__.py` or main entry function) before any other code runs

## Verification
- Import and call `setup_logging()` then verify `logging.getLogger(__name__).info("test")` outputs formatted message to console
- Call `setup_logging(log_file="test.log")` and verify log file is created with entries
- Existing modules using `getLogger(__name__)` continue to work without modification

---

## Validation

```json
{
  "status": "needs_revision",
  "score": 58,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "All 3 steps have clear actions (create, export/modify, call/modify)",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "Step 1: .orchestrator/core/logging_utils.py, Step 2: .orchestrator/core/__init__.py, Step 3: __main__.py (slightly vague but acceptable)",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": false,
      "details": "No steps include actual code snippets - only descriptions of what code should do",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Linear dependency: Step 1 → Step 2 → Step 3 (no cycles)",
      "severity": "critical"
    },
    {
      "name": "no_placeholders",
      "passed": true,
      "details": "No TODO/TBD placeholders found",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 1",
      "issue": "Missing code block for logging_utils.py implementation",
      "fix_suggestion": "Add complete Python code for setup_logging() function with handlers and formatters"
    },
    {
      "step": "Step 2",
      "issue": "Missing code showing the exact import and __all__ modification",
      "fix_suggestion": "Add code snippet showing: from .logging_utils import setup_logging and __all__ update"
    },
    {
      "step": "Step 3",
      "issue": "Vague target 'typically in __main__.py or main entry function' - needs exact path",
      "fix_suggestion": "Specify exact file path like .orchestrator/__main__.py or .orchestrator/cli.py"
    }
  ],
  "warnings": [],
  "summary": "Plan has clear structure and valid dependencies but fails the critical 'steps_have_code' requirement. All three steps describe what to do but provide no actual code snippets for the builder to execute. Step 3 also has a vague target. Must add complete code blocks and specify exact entry point path before approval."
}
```
