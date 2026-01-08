---
description: Manually implement a specific subplan from a run
argument-hint: [run-id] [subplan-id]
---

# Orchestrator Implement

Manually implement a specific subplan from an existing run. Use this when you want to implement subplans one at a time with full control, or to re-implement a failed subplan.

## Variables

RUN_ID: $1
SUBPLAN_ID: $2
SUBPLAN_PATH: `orchistrator/runs/<RUN_ID>/plan/subplans/<SUBPLAN_ID>-*.md`

## Instructions

- **IMPORTANT**: If `RUN_ID` or `SUBPLAN_ID` is missing, STOP and ask the user to provide them
- Read the subplan file thoroughly before implementing
- Follow the subplan's steps exactly—no scope creep
- Write tests first (TDD approach)
- Run tests and fix failures until green
- Use the `implementer` agent or `tdd-implementation` skill

## Workflow

1. **Validate input**: Check both RUN_ID and SUBPLAN_ID are provided
2. **Find subplan file**:
   ```bash
   ls orchistrator/runs/<RUN_ID>/plan/subplans/<SUBPLAN_ID>-*.md
   ```
3. **Read the subplan**: Load the full subplan markdown
4. **Check for prior attempts**: Look in `orchistrator/runs/<RUN_ID>/subplan-results/<SUBPLAN_ID>/`
5. **Load memory** (if exists): Read any previous attempt summaries
6. **Implement**:
   - Extract scope, files, steps from subplan
   - Write/update unit tests first
   - Implement minimal code to pass tests
   - Run test command from subplan
   - Fix failures until green
7. **Save results**: Write output to `orchistrator/runs/<RUN_ID>/subplan-results/<SUBPLAN_ID>/attempt-XX/`

## Subplan Structure Reference

The subplan file should contain:
- **Scope**: In/out scope boundaries
- **Files**: Files to create/modify
- **Steps**: Numbered implementation steps
- **Unit Tests**: Test cases with test command
- **Acceptance Criteria**: Success criteria
- **Rollback Notes**: How to undo

## Report

After implementation:

```
Implementation Complete

Run ID: <RUN_ID>
Subplan: <SUBPLAN_ID> - <title>
Status: [SUCCESS | PARTIAL | BLOCKED]

Files Changed:
- <file1>: +X/-Y lines
- <file2>: +X/-Y lines

Tests:
- Command: <test command>
- Result: [PASSING | FAILING]
- Passed: X/Y

Acceptance Criteria:
- [x] Criterion 1
- [x] Criterion 2
- [ ] Criterion 3 (reason if incomplete)

Next: Run `/orch-test <RUN_ID> <SUBPLAN_ID>` to verify, then `/orch-review <RUN_ID>` to review
```

## Notes

- This command implements ONE subplan only
- For full automated workflow, use `/orch-run` instead
- Results are saved for later review
