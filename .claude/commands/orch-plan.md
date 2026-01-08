---
description: Create a structured planning folder with atomic subplans for a goal
argument-hint: [goal...]
---

# Orchestrator Plan

Create a comprehensive planning folder with atomic subplans based on the user's goal. This command analyzes requirements, explores the codebase, and produces a structured plan ready for implementation.

## Variables

GOAL: $ARGUMENTS
RUN_ID: Auto-generated timestamp (YYYY-MM-DDTHH-MM-SS)
PLAN_OUTPUT_DIR: `orchistrator/runs/<RUN_ID>/plan/`

## Instructions

- **IMPORTANT**: If no `GOAL` is provided, STOP and ask the user to provide it
- Analyze the goal thoroughly to understand the core problem and desired outcome
- Explore the codebase to understand existing patterns and architecture
- Break the work into atomic, independently testable subplans
- Each subplan must include: scope, files, steps, tests, acceptance criteria, rollback notes
- Write assumptions explicitly instead of asking questions unless blocked
- Do NOT implement any code—planning only

## Workflow

1. **Validate input**: If no GOAL provided, stop and request it
2. **Generate run ID**: Create timestamp-based run ID
3. **Explore codebase**: Use Glob/Grep/Read to understand existing patterns
4. **Analyze requirements**: Parse the GOAL to identify scope and constraints
5. **Design subplans**: Break work into atomic, testable units
6. **Create plan folder**:
   ```
   orchistrator/runs/<RUN_ID>/plan/
   ├── plan.json
   ├── overview.md
   └── subplans/
       ├── 001-<slug>.md
       ├── 002-<slug>.md
       └── ...
   ```
7. **Write plan.json** with schema:
   ```json
   {
     "run_id": "<RUN_ID>",
     "goal": "<GOAL>",
     "assumptions": ["..."],
     "subplans": [
       { "id": "001", "title": "...", "path": "orchistrator/runs/<RUN_ID>/plan/subplans/001-<slug>.md" }
     ]
   }
   ```
8. **Write subplan files** with required sections

## Subplan Template

Each subplan file must include:

```markdown
# Subplan [ID]: [Title]

## Scope
**In Scope:**
- [item]

**Out of Scope:**
- [item]

## Files
- `[path]` - [action: create/modify] - [description]

## Steps
1. [Step description]
2. [Step description]

## Unit Tests
- [ ] Test case 1: [description]
- [ ] Test case 2: [description]

**Test Command:** `[command]`

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Rollback Notes
[How to undo these changes if needed]
```

## Report

After creating the plan:

```
Plan Created

Run ID: <RUN_ID>
Goal: <GOAL>
Subplans: <count>

Artifacts:
- orchistrator/runs/<RUN_ID>/plan/plan.json
- orchistrator/runs/<RUN_ID>/plan/overview.md
- orchistrator/runs/<RUN_ID>/plan/subplans/*.md

Next: Run `/orch-run <RUN_ID>` to execute the plan
```
