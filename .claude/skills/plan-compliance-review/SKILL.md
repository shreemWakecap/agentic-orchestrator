---
name: plan-compliance-review
description: Reviews implementation against plan specifications with strict pass/fail criteria. Use when validating that code matches requirements, checking acceptance criteria, or performing quality gates.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# Plan Compliance Review Skill

Review implementation against a plan with strict pass/fail judgment. This is a READ-ONLY review—no file modifications.

## Instructions

- **Read only**: Never modify files during review
- **Be strict**: Reject if any acceptance criteria aren't met
- **Check everything**: Verify all requirements, tests, and quality
- **Provide specifics**: Include file paths, line numbers, and concrete issues
- **Output JSON**: Final output must be valid JSON

## Workflow

### 1. Load the Plan

- Read `plan.json` for overall structure
- Read each subplan file for detailed requirements
- Extract all acceptance criteria

```bash
# Example paths
orchistrator/runs/<run-id>/plan/plan.json
orchistrator/runs/<run-id>/plan/subplans/*.md
```

### 2. Review Implementation

For each subplan:

**a. Check file existence**
- Verify all specified files exist
- Check files were created/modified as planned

**b. Verify acceptance criteria**
- Read each criterion from the subplan
- Find evidence in the code that criterion is met
- Document any missing criteria

**c. Review test coverage**
- Check that specified tests exist
- Verify tests cover planned behavior
- Check test results (passing/failing)

**d. Check for scope creep**
- Identify any changes outside the plan
- Flag unplanned features or modifications
- Note if extra work is beneficial or problematic

**e. Assess code quality**
- Look for obvious bugs
- Check for security issues
- Evaluate maintainability

### 3. Generate Verdict

Compile findings into structured JSON:

```json
{
  "approved": false,
  "blockers": [
    "Acceptance criterion 'X' not implemented (subplan 001)",
    "Missing unit test for edge case Y (subplan 002)",
    "Scope creep: added feature Z not in plan"
  ],
  "notes": "Implementation is 80% complete. Main issues are missing tests.",
  "next_actions": [
    "Implement criterion X in src/auth.ts",
    "Add test for edge case Y in tests/auth.test.ts",
    "Remove or document feature Z"
  ]
}
```

## Review Checklist

### Acceptance Criteria
- [ ] All criteria from subplan are implemented
- [ ] Implementation matches specification exactly
- [ ] No partial implementations

### Test Coverage
- [ ] Tests exist for all specified test cases
- [ ] Tests cover happy path
- [ ] Tests cover edge cases
- [ ] Tests cover error handling
- [ ] All tests are passing

### Scope Compliance
- [ ] Only planned files were modified
- [ ] No unplanned features added
- [ ] Changes match subplan steps

### Code Quality
- [ ] No obvious bugs
- [ ] No security vulnerabilities
- [ ] Code is maintainable
- [ ] Follows codebase conventions

## Rejection Criteria

Reject (approved: false) if ANY of these are true:

1. **Incomplete acceptance criteria**: Any criterion not fully implemented
2. **Missing tests**: Required tests don't exist or are incomplete
3. **Failing tests**: Any specified tests are failing
4. **Scope creep**: Significant changes outside the plan
5. **Quality issues**: Obvious bugs, security problems, or unmaintainable code
6. **Missing files**: Required files not created

## Examples

### Example 1: Approved Review

```json
{
  "approved": true,
  "blockers": [],
  "notes": "All acceptance criteria met. Tests passing. Clean implementation.",
  "next_actions": []
}
```

### Example 2: Rejected Review

```json
{
  "approved": false,
  "blockers": [
    "Criterion 'API returns 401 for invalid token' not implemented - returns 500 instead (src/auth.ts:45)",
    "Missing test: 'should reject expired tokens' specified in subplan but not found",
    "Scope creep: Added rate limiting feature not in plan (src/middleware/rateLimit.ts)"
  ],
  "notes": "Core functionality works but error handling needs work. Rate limiting should be a separate subplan.",
  "next_actions": [
    "Fix error handling in validateToken() to return 401 for invalid tokens",
    "Add test case for expired token scenario",
    "Remove rate limiting or create separate subplan for it"
  ]
}
```

## Output Schema

```json
{
  "type": "object",
  "required": ["approved", "blockers", "notes", "next_actions"],
  "properties": {
    "approved": {
      "type": "boolean",
      "description": "true if all criteria met, false otherwise"
    },
    "blockers": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of issues preventing approval (empty if approved)"
    },
    "notes": {
      "type": "string",
      "description": "Summary of review findings"
    },
    "next_actions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Specific actions to address blockers (empty if approved)"
    }
  }
}
```
