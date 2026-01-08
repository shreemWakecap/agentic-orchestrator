---
description: Build/implement code based on an existing plan file
argument-hint: [path-to-plan]
---

# Build

Implement code based on an existing plan file. Reads the plan, executes each step in order, and validates the work.

## Variables

PATH_TO_PLAN: $ARGUMENTS

## Instructions

- **IMPORTANT**: If no `PATH_TO_PLAN` is provided, STOP and ask the user to provide it
- Implement the plan top to bottom, in order
- Do not skip any steps
- Do not stop between steps—complete the entire plan
- Make best-guess judgments based on the plan details
- End with running validation commands
- If validation fails, fix issues before stopping

## Workflow

1. **Validate input**: If no PATH_TO_PLAN provided, stop and request it
2. **Read the plan**:
   - Load the plan file at PATH_TO_PLAN
   - Understand the goal, scope, and steps
   - Note any validation commands
3. **Analyze the plan**:
   - Identify all files to create/modify
   - Understand dependencies between steps
   - Note test requirements
4. **Implement each step**:
   - Follow steps in order, top to bottom
   - Write tests before implementation (TDD)
   - Keep changes minimal and focused
   - Don't add features not in the plan
5. **Run validation**:
   - Execute all validation commands from the plan
   - Fix any failures
   - Re-run until passing
6. **Report completion**

## Plan File Format

The plan file should contain:

```markdown
# Plan: <title>

## Objective
<what will be accomplished>

## Relevant Files
- `path/to/file.ts` - <description>

## Step by Step Tasks

### 1. <First Task>
- <action>
- <action>

### 2. <Second Task>
- <action>
- <action>

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Validation Commands
- `npm test` - Run tests
- `npm run build` - Verify build
```

## Report

After building:

```
Build Complete

Plan: <plan title>
Status: [SUCCESS | FAILED]

Work Summary:
- <bullet point summary of what was done>
- <bullet point summary>
- <bullet point summary>

Files Changed:
<output of git diff --stat>

Validation Results:
- `<command1>`: [PASS | FAIL]
- `<command2>`: [PASS | FAIL]

Acceptance Criteria:
- [x] Criterion 1
- [x] Criterion 2
- [ ] Criterion 3 (reason if incomplete)

Issues Encountered:
- <any issues, or "None">

Next Steps:
- <recommendations>
```

## Examples

### Example: Building from a spec file

```
/build specs/add-user-profile.md
```

This will:
1. Read the plan at `specs/add-user-profile.md`
2. Implement each step in order
3. Run validation commands
4. Report results

## Notes

- This command is for plans outside the orchestrator workflow
- For orchestrator runs, use `/orch-implement` instead
- The plan file can be in `specs/`, `plans/`, or any location
- Use `/plan [goal]` to create a plan file first
