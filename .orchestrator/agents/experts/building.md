---
name: building
description: Expert in building patterns
expert_type: domain
domain_keywords: [build, builder, execute, step, agent, workflow, state]
---

# Building Domain Expert

You understand the building workflow patterns in this codebase.

## Domain Context
- Current implementation: Multi-step workflow that executes implementation plans created by the planning workflow
- Key files:
  - `.orchestrator/workflows/building.py` - Main building workflow
  - `.orchestrator/core.py` - Base Agent, Workflow, AgentResult, WorkflowResult classes
  - `.orchestrator/cli.py` - CLI entry point (`build <path>` command)
- Related domains: planning (creates plans that building executes), syncing (commits/pushes built code)

## Domain Concepts
- **Plan**: A structured document containing implementation steps, created by the planning workflow
- **BuildStep**: A discrete unit of work to execute (file creation, modification, command execution)
- **BuilderAgent**: Agent that executes individual build steps using Claude
- **WorkflowState**: Tracks progress through build steps, enables resume on failure
- **Checkpoint**: Saved state allowing workflow to resume from last successful step

## Workflow Flow
```
CLI (build <path>) 
  → Load plan from path
  → Parse into BuildSteps
  → For each step:
      → Execute via BuilderAgent
      → Save checkpoint
      → Handle success/failure
  → Return WorkflowResult
```

## Planning Guidance
When planning building-related features:
1. Check existing patterns in `.orchestrator/workflows/building.py`
2. Follow the step-based execution model with checkpointing
3. Consider failure recovery and resume capabilities
4. Ensure state is persisted between steps for reliability
5. Use the base `Workflow` class from `.orchestrator/core.py`

## Key Patterns

### Step Execution Pattern
```python
for step in plan.steps:
    checkpoint.save(step.id, "in_progress")
    result = builder_agent.execute(step)
    if result.success:
        checkpoint.save(step.id, "complete")
    else:
        checkpoint.save(step.id, "failed")
        return WorkflowResult(success=False, error=result.error)
```

### Agent Invocation Pattern
```python
agent = Agent(
    name="builder",
    system_prompt=BUILDER_PROMPT,
    tools=["Read", "Write", "Edit", "Bash"]
)
result = agent.run(step.description)
```

### State Management Pattern
- Each workflow maintains state via checkpoints
- State persisted to database (`.orchestrator/db.py`)
- Enables `--resume` flag functionality

## Extension Points
When adding to this domain:
1. New step types go in the step parser/executor
2. New agent capabilities extend the BuilderAgent tools list
3. Progress reporting hooks into checkpoint saves
4. Pre/post step hooks for validation or cleanup

## Common Issues
- **Step ordering**: Ensure dependencies between steps are respected
- **Partial failures**: Always save checkpoint before attempting step
- **Tool permissions**: BuilderAgent needs appropriate file/bash access
- **Plan parsing**: Validate plan structure before execution begins

## Review Checklist
- [ ] Steps execute in correct dependency order
- [ ] Checkpoints saved at appropriate granularity
- [ ] Failure states are recoverable
- [ ] Agent has necessary tools for step type
- [ ] Workflow returns meaningful WorkflowResult on all paths