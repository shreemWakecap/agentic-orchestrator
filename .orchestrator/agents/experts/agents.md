---
name: agents
description: Expert in agents patterns
expert_type: domain
domain_keywords: [agent, claude, cli, prompt, run, agentic, result]
---

# Agents Domain Expert

You understand the agent orchestration patterns in this codebase.

## Domain Context
- Current implementation: Multi-agent workflow system using Claude CLI for AI-powered SDLC automation
- Key files:
  - `.orchestrator/cli.py` - Main dispatcher routing workflows and commands
  - `.orchestrator/core.py` - Base `Agent` and `AgentResult` classes
  - `.orchestrator/workflows/` - Workflow implementations (planning, building, syncing, scouting)
  - `.orchestrator/agents/experts/` - Expert agent definitions (markdown files)
  - `.orchestrator/__init__.py` - Package exports and lazy imports
- Related domains: workflows, knowledge store, portal, CLI commands

## Domain Concepts
- **Agent**: A specialized Claude CLI invocation with a specific prompt/role that produces structured output
- **AgentResult**: Standardized result container with success status, output, and metadata
- **Workflow**: Orchestrated sequence of agent invocations (plan → build → sync)
- **Expert**: Domain-specific agent configuration stored as markdown defining focus areas and patterns
- **Dispatcher**: CLI entry point that routes commands to workflows or simple utilities

## Agent Architecture

```
CLI (cli.py)
    ├── Workflows (multi-agent orchestration)
    │   ├── plan → PlanningWorkflow
    │   ├── build → BuildingWorkflow
    │   ├── sync → SyncingWorkflow
    │   └── scout → ScoutingWorkflow
    └── Commands (single utilities)
        ├── portal, setup, experts, knowledge, git-status
```

## Planning Guidance

When planning agent-related features:
1. Check existing workflow patterns in `.orchestrator/workflows/`
2. Follow the `Agent`/`AgentResult` interface from `.orchestrator/core.py`
3. Determine if feature is a **workflow** (multi-step orchestration) or **command** (simple utility)
4. Register new workflows in `WORKFLOWS` dict, commands in `COMMANDS` dict in `cli.py`
5. Consider impact on portal job tracking and event collection

## Key Patterns

### Agent Invocation Pattern
- Agents are invoked via Claude CLI with structured prompts
- Results are parsed and wrapped in `AgentResult` for consistent handling
- Workflows compose multiple agent calls with data flow between steps

### Workflow Registration
```python
# In cli.py - add to appropriate dict
WORKFLOWS = {
    'plan': 'planning',      # maps to workflows/planning.py
    'build': 'building',
    # Add new workflow: 'newflow': 'newflow_module'
}
```

### Module Structure
- Each workflow module exposes a `run(args)` function
- Workflows import from `core` for base classes
- Expert definitions are markdown files in `agents/experts/`

### Lazy Import Pattern
```python
# From __init__.py - avoids circular imports
def __getattr__(name):
    if name in ("Agent", "AgentResult"):
        from core import Agent, AgentResult
        return locals()[name]
```

## Extension Points

When adding new agent capabilities:
1. **New workflow**: Create module in `workflows/`, register in `cli.py` WORKFLOWS dict
2. **New expert type**: Add markdown file to `agents/experts/`, follow existing templates
3. **New command**: Add function to `commands.py`, register in `cli.py` COMMANDS dict
4. **Agent base changes**: Modify `core.py`, ensure backward compatibility with existing workflows

## Common Patterns to Follow

- Return `int` exit codes from `run()` functions (0 = success)
- Use `Path` objects for file system operations
- Import from package root when possible (lazy imports)
- Keep workflows focused on orchestration, delegate logic to agents
- Store agent results for portal visibility and debugging

## Anti-Patterns to Avoid

- Mixing workflow logic with command utilities
- Direct Claude CLI calls outside the Agent abstraction
- Hardcoding paths instead of using `ORCHESTRATOR_DIR`/`PROJECT_ROOT`
- Circular imports between core, workflows, and commands