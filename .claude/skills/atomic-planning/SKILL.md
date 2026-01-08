---
name: atomic-planning
description: Creates structured planning folders with atomic, independently testable subplans. Use when breaking down features, projects, or tasks into implementation plans with acceptance criteria and test commands.
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---

# Atomic Planning Skill

Create comprehensive planning folders with atomic subplans that can be implemented and tested independently.

## Instructions

- **Atomic means independently executable**: Each subplan should be implementable without depending on other subplans being complete
- **Testable means verifiable**: Each subplan must have specific test commands and acceptance criteria
- **Include all required sections**: Scope, files, steps, tests, acceptance criteria, rollback notes
- **Use consistent naming**: Zero-padded IDs (001, 002) with kebab-case slugs
- **Document assumptions**: Write assumptions explicitly instead of leaving gaps

## Workflow

### 1. Analyze the Goal

- Parse the user's request to understand scope and constraints
- Identify the core problem and desired outcome
- Note any explicit requirements or preferences

### 2. Explore the Codebase

- Use Glob to find relevant files and understand structure
- Use Grep to find patterns, conventions, and related code
- Read key files to understand architecture

### 3. Design Subplans

Break work into atomic units that:
- Can be implemented in isolation
- Have clear inputs and outputs
- Are testable with specific commands
- Can be rolled back if needed

### 4. Create Planning Folder

```
orchistrator/runs/<run-id>/plan/
├── plan.json          # Machine-readable metadata
├── overview.md        # Human-readable summary
└── subplans/
    ├── 001-<slug>.md  # First atomic subplan
    ├── 002-<slug>.md  # Second atomic subplan
    └── ...
```

### 5. Write plan.json

```json
{
  "run_id": "<run-id>",
  "goal": "<original goal>",
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "subplans": [
    {
      "id": "001",
      "title": "Descriptive title",
      "path": "orchistrator/runs/<run-id>/plan/subplans/001-slug.md"
    }
  ]
}
```

### 6. Write Subplan Files

Each subplan must include:

```markdown
# Subplan [ID]: [Title]

## Scope

**In Scope:**
- Specific item to implement
- Another item

**Out of Scope:**
- What this subplan does NOT cover
- Deferred to other subplans

## Files

- `path/to/file.ts` - Create - Description of what this file does
- `path/to/existing.ts` - Modify - What changes are needed

## Steps

1. **First step**: Detailed description of what to do
2. **Second step**: Next action with specific details
3. **Third step**: Continue until complete

## Unit Tests

- [ ] Test happy path: description
- [ ] Test edge case: description
- [ ] Test error handling: description

**Test Command:** `npm test -- path/to/test`

## Acceptance Criteria

- [ ] Criterion 1: Specific, measurable outcome
- [ ] Criterion 2: Another verifiable requirement
- [ ] Criterion 3: Final check

## Rollback Notes

To undo this subplan:
1. Delete created files: [list]
2. Revert changes to: [list]
3. Any cleanup needed
```

## Examples

### Example 1: API Endpoint Feature

Goal: "Add a user profile endpoint"

Subplans created:
1. `001-user-model.md` - Add User model with profile fields
2. `002-profile-endpoint.md` - Create GET /api/profile endpoint
3. `003-profile-tests.md` - Add integration tests

### Example 2: Refactoring Task

Goal: "Extract auth logic into separate module"

Subplans created:
1. `001-create-auth-module.md` - Create new auth module structure
2. `002-migrate-functions.md` - Move functions to new module
3. `003-update-imports.md` - Update all import statements
4. `004-cleanup.md` - Remove old code, verify tests

## Best Practices

- **Order subplans logically**: Foundation first, then dependent features
- **Keep subplans small**: Aim for 1-2 hours of work each
- **Be specific about tests**: Include exact test commands
- **Consider rollback**: Always document how to undo changes
- **Include file paths**: Use absolute paths from repo root
