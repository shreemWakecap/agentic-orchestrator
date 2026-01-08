---
description: Execute the full orchestrator workflow (Plan → Implement → Test → Review → Iterate)
argument-hint: [goal...]
---

# Orchestrator Run

Execute the full deterministic workflow: Plan → Implement → Test → Review → Iterate.

## Variables

GOAL: $ARGUMENTS

## Instructions

- **IMPORTANT**: If no `GOAL` is provided, STOP and ask the user to provide it
- Build and run the TypeScript orchestrator
- The orchestrator handles the full workflow automatically
- Monitor output for progress and errors

## Workflow

1. **Validate input**: If no GOAL provided, stop and request it
2. **Build orchestrator**:
   ```bash
   npm --prefix orchistrator install && npm --prefix orchistrator run build
   ```
3. **Execute workflow**:
   ```bash
   node orchistrator/dist/index.js "GOAL"
   ```
4. **Report results** when complete

## Report

After execution, show:
- Run ID
- Final status (SUCCESS/FAILED)
- Artifacts location
- Any errors encountered
