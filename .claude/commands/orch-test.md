---
description: Run tests for a specific subplan and fix failures until green
argument-hint: [run-id] [subplan-id]
---

# Orchestrator Test

Run the test command for a specific subplan and fix any failures until all tests pass. Uses the test-runner agent behavior.

## Variables

RUN_ID: $1
SUBPLAN_ID: $2
SUBPLAN_PATH: `orchistrator/runs/<RUN_ID>/plan/subplans/<SUBPLAN_ID>-*.md`

## Instructions

- **IMPORTANT**: If `RUN_ID` or `SUBPLAN_ID` is missing, STOP and ask the user to provide them
- Extract the test command from the subplan
- Run tests and analyze failures
- Fix implementation (not tests) until green
- Maximum 5 fix attempts before reporting blockers
- Never weaken tests to make them pass

## Workflow

1. **Validate input**: Check both RUN_ID and SUBPLAN_ID are provided
2. **Load subplan**: Read the subplan file
3. **Extract test command**: Find the `**Test Command:**` section
4. **Run initial tests**:
   ```bash
   <test command from subplan>
   ```
5. **If tests pass**: Report success and exit
6. **If tests fail**: Enter fix loop:
   - Analyze error messages and stack traces
   - Identify failing test and root cause
   - Apply minimal fix to implementation
   - Re-run tests
   - Repeat until green or max attempts (5)
7. **Save results**: Write output to results directory

## Test Fix Loop

For each failure:

```
1. ANALYZE
   - Read error message
   - Identify failing assertion
   - Find relevant code

2. DIAGNOSE
   - Logic error?
   - Missing edge case?
   - Type mismatch?
   - Import issue?

3. FIX
   - Edit only necessary lines
   - Keep changes minimal
   - Don't weaken tests

4. VERIFY
   - Re-run test suite
   - Check for regressions
```

## Report

After test execution:

```
Test Results

Run ID: <RUN_ID>
Subplan: <SUBPLAN_ID> - <title>
Final Status: [ALL PASSING | FAILURES REMAIN]
Attempts: X/5

Test Output:
<final test output>

Fixes Applied:
| # | File:Line | Issue | Fix |
|---|-----------|-------|-----|
| 1 | src/auth.ts:45 | Wrong status code | Changed 500 to 401 |

Remaining Issues:
- [List any unresolved issues]

Next: Run `/orch-review <RUN_ID>` to review implementation
```

## Notes

- This command focuses on making tests pass
- Use `/orch-implement` first if tests don't exist yet
- For failing tests that indicate plan issues, stop and report
