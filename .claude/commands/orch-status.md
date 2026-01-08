---
description: Show status of orchestrator runs by inspecting the runs folder
argument-hint: [run-id?]
---

# Orchestrator Status

Display the status of orchestrator runs. Shows all runs if no run-id specified, or detailed status for a specific run.

## Variables

RUN_ID: $ARGUMENTS (optional)
RUNS_DIR: `orchistrator/runs/`

## Instructions

- If no RUN_ID provided, list all runs with summary status
- If RUN_ID provided, show detailed status for that run
- Check for existence of key artifacts to determine status
- Show progress through subplans if run is in progress

## Workflow

### All Runs (no RUN_ID)

1. List directories in `orchistrator/runs/`
2. For each run, check:
   - Does `plan/plan.json` exist? (planning complete)
   - Does `subplan-results/` have content? (implementation started)
   - Does `FINAL.md` exist? (run complete)
3. Display summary table

### Specific Run (RUN_ID provided)

1. Load `orchistrator/runs/<RUN_ID>/plan/plan.json`
2. Check status of each subplan:
   - Find latest attempt in `subplan-results/<id>/`
   - Check for `review.json` and its `approved` field
3. Display detailed progress

## Report

### All Runs View

```
Orchestrator Runs

| Run ID | Status | Subplans | Created |
|--------|--------|----------|---------|
| 2024-01-15T10-30-00 | COMPLETE | 3/3 | 2024-01-15 |
| 2024-01-14T15-20-00 | IN_PROGRESS | 1/2 | 2024-01-14 |
| 2024-01-13T09-00-00 | FAILED | 2/3 | 2024-01-13 |

Total: 3 runs
```

### Specific Run View

```
Run: 2024-01-15T10-30-00

Goal: Implement user authentication

Status: IN_PROGRESS

Subplans:
| ID | Title | Status | Attempts |
|----|-------|--------|----------|
| 001 | Add user model | APPROVED | 1 |
| 002 | Add auth endpoints | IN_PROGRESS | 2 |
| 003 | Add JWT middleware | PENDING | 0 |

Progress: 1/3 complete

Latest Activity:
- Subplan 002, Attempt 2: Review rejected
  - Blocker: Missing test for token expiration

Artifacts:
- Plan: orchistrator/runs/2024-01-15T10-30-00/plan/
- Results: orchistrator/runs/2024-01-15T10-30-00/subplan-results/
```

## Status Definitions

- **PENDING**: Not yet started
- **IN_PROGRESS**: Currently being worked on
- **APPROVED**: Review passed
- **REJECTED**: Review failed, needs fixes
- **COMPLETE**: All subplans approved
- **FAILED**: Max attempts reached without approval
