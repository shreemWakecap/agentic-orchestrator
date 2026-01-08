---
description: Resume a failed or incomplete orchestrator run from where it left off
argument-hint: [run-id]
---

# Orchestrator Resume

Resume an incomplete or failed orchestrator run. Analyzes the current state, identifies where the run stopped, and continues from that point.

## Variables

RUN_ID: $ARGUMENTS
RUN_DIR: `orchistrator/runs/<RUN_ID>/`

## Instructions

- **IMPORTANT**: If no `RUN_ID` is provided, STOP and ask the user to provide it
- Analyze the run state to determine where it stopped
- Load any memory/context from previous attempts
- Continue the workflow from the appropriate phase
- Don't re-implement already-approved subplans

## Workflow

1. **Validate input**: Check RUN_ID is provided
2. **Check run exists**:
   ```bash
   ls orchistrator/runs/<RUN_ID>/
   ```
3. **Analyze current state**:
   - Read `plan/plan.json` for subplan list
   - Check `subplan-results/` for attempt history
   - Identify which subplans are: APPROVED, REJECTED, IN_PROGRESS, PENDING
4. **Determine resume point**:
   - If no plan exists: Start from PLAN phase
   - If plan exists but no results: Start from first subplan IMPLEMENT
   - If some subplans approved: Continue from first non-approved subplan
   - If subplan has failed attempts: Load memory and retry
5. **Load context**:
   - Read `memory/<subplan-id>.md` for approved subplans
   - Read latest attempt's review feedback for failed subplans
6. **Resume execution**:
   - For each remaining subplan: IMPLEMENT → TEST → REVIEW → (ITERATE if needed)
7. **Complete run**: Write `FINAL.md` when all subplans approved

## State Detection

```
RUN STATE ANALYSIS

Plan Phase:
- plan.json exists? [YES/NO]
- overview.md exists? [YES/NO]
- subplans count: X

Subplan Status:
| ID | Title | Status | Attempts | Last Result |
|----|-------|--------|----------|-------------|
| 001 | ... | APPROVED | 1 | Passed |
| 002 | ... | REJECTED | 2 | Blockers: ... |
| 003 | ... | PENDING | 0 | - |

Resume Point: Subplan 002, Attempt 3
```

## Report

After resuming:

```
Run Resumed

Run ID: <RUN_ID>
Original Goal: <goal from goal.md>

Previous State:
- Subplans: X total
- Approved: Y
- Failed/Pending: Z

Resumed From: Subplan <ID> - <title>
Action: [IMPLEMENT | TEST | REVIEW]

Progress:
[Updates as work progresses]

Final Status: [COMPLETE | FAILED | IN_PROGRESS]
```

## Notes

- Use `/orch-status <run-id>` first to see current state
- Memory from previous attempts is preserved
- Max 5 attempts per subplan still applies
- If a subplan has already hit max attempts, it will be skipped with FAILED status
