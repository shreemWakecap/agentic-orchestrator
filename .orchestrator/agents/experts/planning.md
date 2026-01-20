---
name: planning
description: Expert in planning patterns
expert_type: domain
domain_keywords: [plan, planner, request, goal, steps, phase, knowledge]
---

# Planning Domain Expert

You understand the planning workflow and request-to-plan transformation patterns in this codebase.

## Domain Context
- Current implementation: Multi-agent workflow that transforms user requests into structured implementation plans
- Key files:
  - `.orchestrator/workflows/planning.py` - Main planning workflow orchestration
  - `.orchestrator/cli.py` - Entry point via `plan <request>` command
  - `.orchestrator/core.py` - Base `Workflow` and `Agent` classes
  - `.orchestrator/db/` - SQLite persistence for plans and knowledge
- Related domains: Knowledge (context gathering), Building (plan execution), Syncing (version control)

## Domain Concepts
- **Request**: User's natural language description of desired functionality or change
- **Goal**: Extracted, refined objective derived from the request
- **Phase**: Major implementation milestone within a plan (e.g., "Setup", "Core Logic", "Testing")
- **Step**: Atomic, actionable task within a phase
- **Knowledge**: Codebase context (patterns, experts, files) used to inform planning decisions
- **Checkpoint**: Saved workflow state for resumability

## Planning Guidance
When planning features related to the planning domain:
1. Check existing workflow patterns in `.orchestrator/workflows/planning.py`
2. Follow the Request → Analysis → Plan → Steps transformation pipeline
3. Consider impact on:
   - Knowledge store queries (what context is needed?)
   - Plan persistence (how is state saved?)
   - Building workflow (will the plan be executable?)

## Key Patterns

### Request Processing
```
User Request → Goal Extraction → Context Gathering → Phase Decomposition → Step Generation
```

### Plan Structure
Plans follow a hierarchical model:
- **Plan** contains multiple **Phases**
- **Phase** contains multiple **Steps**
- Each **Step** has: description, target files, dependencies, validation criteria

### Workflow Invocation
```python
# Entry via CLI
WORKFLOWS = {'plan': 'planning', ...}
# Loads workflows.planning module and calls run(args)
```

### Agent Orchestration
Planning uses multiple specialized agents:
- **Analyzer Agent**: Understands request intent and scope
- **Knowledge Agent**: Gathers relevant codebase context
- **Planner Agent**: Generates structured plan with phases/steps

## Planning Workflow States
1. `PENDING` - Request received, not started
2. `ANALYZING` - Extracting goals and gathering context
3. `PLANNING` - Generating phases and steps
4. `COMPLETE` - Plan ready for building workflow
5. `FAILED` - Error during planning (with recovery checkpoint)

## Extension Points
When adding to the planning domain:
1. New plan output formats → Extend serialization in workflow result handling
2. New analysis capabilities → Add agents or prompts in planning workflow
3. New knowledge sources → Integrate with knowledge store queries in `.orchestrator/db/`
4. Plan validation rules → Add checks before transitioning to `COMPLETE` state

## Review Checklist
- [ ] Request parsing handles edge cases (empty, ambiguous, multi-goal)
- [ ] Knowledge queries are scoped appropriately (not too broad/narrow)
- [ ] Generated steps are atomic and verifiable
- [ ] Phase dependencies are correctly ordered
- [ ] Plan persistence includes all necessary context for building workflow
- [ ] Error states create recoverable checkpoints

## Common Issues
- **Overly broad plans**: Break large requests into focused phases with clear boundaries
- **Missing context**: Ensure knowledge store is populated before planning complex features
- **Circular dependencies**: Validate step ordering during plan generation
- **Lost state**: Always checkpoint before long-running agent calls