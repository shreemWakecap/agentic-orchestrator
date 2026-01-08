---
description: Review implementation against a run's plan folder with strict pass/fail judgment
argument-hint: [run-id]
---

# Orchestrator Review

Perform a strict plan-compliance review comparing the current implementation against a run's plan folder. Outputs a structured pass/fail judgment with specific blockers.

## Variables

RUN_ID: $ARGUMENTS
PLAN_DIR: `orchistrator/runs/<RUN_ID>/plan/`

## Instructions

- **IMPORTANT**: If no `RUN_ID` is provided, STOP and ask the user to provide it
- Load the plan.json and all subplan files from the plan directory
- Compare implementation against every acceptance criterion
- Check that tests exist and are passing for planned behavior
- Flag any scope creep beyond the plan
- Output strict JSON verdict

## Workflow

1. **Validate input**: If no RUN_ID provided, stop and request it
2. **Load plan**: Read `orchistrator/runs/<RUN_ID>/plan/plan.json`
3. **Load subplans**: Read all `orchistrator/runs/<RUN_ID>/plan/subplans/*.md`
4. **For each subplan**:
   - Extract acceptance criteria
   - Identify files that should exist/be modified
   - Read implementation files
   - Check if criteria are met
   - Verify tests exist and pass
   - Check for scope creep
5. **Generate verdict**: Compile results into JSON output

## Review Checklist

For each subplan, verify:

- [ ] All acceptance criteria are implemented
- [ ] Required files exist with correct content
- [ ] Unit tests exist for planned behavior
- [ ] Tests are passing
- [ ] No scope creep (changes outside plan)
- [ ] Code quality meets standards
- [ ] No obvious bugs or security issues

## Report

Output strict JSON only:

```json
{
  "run_id": "<RUN_ID>",
  "overall_status": "PASS" | "FAIL",
  "subplan_results": [
    {
      "id": "001",
      "title": "...",
      "approved": true | false,
      "blockers": [],
      "notes": "..."
    }
  ],
  "summary": {
    "total": 3,
    "passed": 2,
    "failed": 1
  },
  "next_actions": [
    "Fix blocker X in subplan 002",
    "..."
  ]
}
```

## Rejection Criteria

Mark subplan as rejected if ANY of these are true:
- Plan acceptance criteria not fully met
- Missing or weak unit tests for planned behavior
- Scope creep beyond the plan
- Obvious bugs, security issues, or maintainability problems
- Tests are failing
- Required files not created/modified
