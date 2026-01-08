---
description: View logs, debug info, and detailed history for an orchestrator run
argument-hint: [run-id] [subplan-id?]
---

# Orchestrator Logs

View detailed logs, debug information, and history for an orchestrator run. Can show overall run logs or drill down into specific subplan attempts.

## Variables

RUN_ID: $1
SUBPLAN_ID: $2 (optional)
RUN_DIR: `orchistrator/runs/<RUN_ID>/`

## Instructions

- **IMPORTANT**: If no `RUN_ID` is provided, STOP and ask the user to provide it
- If only RUN_ID: Show run overview and summary of all subplans
- If RUN_ID + SUBPLAN_ID: Show detailed logs for that subplan's attempts
- Include timestamps, tool usage, and key decision points

## Workflow

### Run Overview (RUN_ID only)

1. **Load run metadata**:
   - Read `goal.md` for original goal
   - Read `plan/plan.json` for subplan list
   - Check for `FINAL.md` to determine completion status
2. **Load global logs**:
   - Read `logs/01-plan.json` for planning phase output
   - List all files in `logs/` directory
3. **Summarize subplan results**:
   - For each subplan, count attempts
   - Show final status (APPROVED/REJECTED/PENDING)
   - Note any blockers from latest review
4. **Display formatted output**

### Subplan Detail (RUN_ID + SUBPLAN_ID)

1. **Find attempt directories**:
   ```
   orchistrator/runs/<RUN_ID>/subplan-results/<SUBPLAN_ID>/attempt-*/
   ```
2. **For each attempt, load**:
   - `implementer.txt` - Implementation output
   - `tests.txt` - Test execution output
   - `review.json` - Review verdict
3. **Load memory packet** (if exists):
   - `memory/<SUBPLAN_ID>.md`
4. **Display chronological history**

## Report

### Run Overview Format

```
Orchestrator Run Logs

Run ID: <RUN_ID>
Goal: <goal text>
Status: [COMPLETE | IN_PROGRESS | FAILED]
Created: <timestamp>

Plan Phase:
- Subplans created: X
- Planning output: logs/01-plan.json

Subplan Summary:
| ID | Title | Status | Attempts | Last Activity |
|----|-------|--------|----------|---------------|
| 001 | Add user model | APPROVED | 1 | 2024-01-15 10:30 |
| 002 | Add auth API | REJECTED | 3 | 2024-01-15 11:45 |
| 003 | Add middleware | PENDING | 0 | - |

Latest Blockers (Subplan 002):
- Missing test for token expiration
- Error handling returns wrong status code

Log Files:
- logs/01-plan.json (45 KB)
- logs/02-implement-001.json (12 KB)
- ...
```

### Subplan Detail Format

```
Subplan Logs: <SUBPLAN_ID> - <title>

Run ID: <RUN_ID>
Total Attempts: 3
Final Status: REJECTED

--- Attempt 1 (2024-01-15 10:00) ---

Implementation:
<summary of implementer.txt>

Tests:
- Command: npm test -- auth
- Result: 2/3 passing
- Failures:
  - should reject invalid token: expected 401, got 500

Review:
- Approved: false
- Blockers:
  1. Error handling returns wrong status
  2. Missing edge case test

--- Attempt 2 (2024-01-15 10:30) ---
...

--- Memory Packet ---
<contents of memory file>
```

## Notes

- Logs are stored in JSONL format for easy parsing
- Use this command to debug failed runs
- Memory packets help understand context between attempts
