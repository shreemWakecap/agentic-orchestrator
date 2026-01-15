# Plan: Add a config file reader utility

> Generated: 2026-01-15 10:29
> Complexity: simple
> Depth: brief

## Context

```json
{
  "project_type": "cli",
  "tech_stack": {
    "languages": ["python"],
    "frameworks": [],
    "tools": ["uv", "pytest", "rich"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/core/config.py",
      "purpose": "Existing ConfigLoader - reference for patterns and potential extension point",
      "relevance": "high",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/core/__init__.py",
      "purpose": "Core module init - may need to export new utility",
      "relevance": "medium",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/config/agent.json",
      "purpose": "Example JSON config file showing existing format",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "ConfigLoader pattern",
      "description": "Use dataclasses for typed config, class-based loader with caching, _load_json helper for safe JSON parsing, convenience functions for direct access",
      "example_file": ".orchestrator/core/config.py",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/core",
        "impact": "New utility should live in core/ directory following existing structure"
      }
    ],
    "external": [
      {
        "package": "pathlib (stdlib)",
        "usage": "Path handling for config file locations"
      },
      {
        "package": "json (stdlib)",
        "usage": "JSON parsing"
      }
    ]
  },
  "considerations": [
    {
      "type": "note",
      "description": "Existing ConfigLoader in config.py handles JSON configs - new utility may overlap or should extend this pattern",
      "severity": "medium"
    },
    {
      "type": "constraint",
      "description": "Config files are stored in .orchestrator/config/ directory as JSON",
      "severity": "low"
    }
  ],
  "summary": "Python CLI project using uv for package management. Existing ConfigLoader in .orchestrator/core/config.py provides a well-established pattern: dataclasses for typed config, class with caching and _load_json helper, convenience functions. New config file reader utility should follow this pattern or potentially extend the existing ConfigLoader class. Config files live in .orchestrator/config/ as JSON."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Extend existing ConfigLoader in config.py with a generic read_config() utility function",
    "rationale": "Reuses established pattern, avoids duplication, single location for config loading logic",
    "complexity": "simple"
  },
  "components": [
    {
      "name": "read_config utility",
      "type": "util",
      "file_path": ".orchestrator/core/config.py",
      "action": "modify",
      "responsibility": "Add generic read_config(filename) function that returns parsed JSON dict with caching",
      "interfaces": {
        "inputs": ["filename: str"],
        "outputs": ["dict"]
      }
    },
    {
      "name": "core module export",
      "type": "config",
      "file_path": ".orchestrator/core/__init__.py",
      "action": "modify",
      "responsibility": "Export read_config function for external access",
      "interfaces": {
        "inputs": [],
        "outputs": ["read_config"]
      }
    }
  ],
  "technical_decisions": [
    {
      "decision": "Add function to existing config.py rather than new file",
      "alternatives": ["Create new reader.py", "Create separate ConfigReader class"],
      "rationale": "ConfigLoader already has _load_json helper and caching pattern - reuse directly",
      "trade_offs": "None significant - keeps related functionality together"
    }
  ],
  "integration_points": [],
  "open_questions": []
}
```

---

## Implementation Steps

# Plan: Config File Reader Utility

## Goal
Add a generic read_config() utility function to read and cache JSON config files.

## Steps
1. Add read_config(filename: str) function to .orchestrator/core/config.py that uses existing _load_json helper, resolves paths relative to CONFIG_DIR, and caches results
2. Add module-level _config_cache dict in config.py for caching loaded configs by filename
3. Export read_config in .orchestrator/core/__init__.py alongside existing exports

## Verification
- Calling read_config("agent.json") returns parsed dict matching .orchestrator/config/agent.json contents
- Repeated calls return cached result (same dict object)
- Invalid filename raises appropriate error

---

## Validation

## Validation Result

**Status:** Approved

## Checks
- Goal clarity: **Pass** - Clear one-sentence objective stating the utility function purpose
- Steps specific: **Pass** - Each step names exact files (.orchestrator/core/config.py, .orchestrator/core/__init__.py), specific functions (read_config, _load_json), and implementation details (CONFIG_DIR, _config_cache)
- Verification included: **Pass** - Three concrete test scenarios with expected behaviors

## Summary
Plan is well-structured with specific file targets, clear function signatures, and testable verification criteria. Ready for implementation.
