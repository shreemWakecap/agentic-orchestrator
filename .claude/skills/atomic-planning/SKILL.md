---
name: atomic-planning
description: Creates structured planning folders with atomic, independently testable subplans. Optimizes for context window protection by embedding required patterns and minimizing implementer exploration. Use when breaking down features, projects, or tasks into implementation plans with acceptance criteria and test commands.
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---

# Atomic Planning Skill

Create comprehensive planning folders with atomic subplans that can be implemented and tested independently. **Context-optimized**: plans front-load all exploration so implementers execute directly without burning context on discovery.

## Core Philosophy

> **The planner explores once. Implementers execute directly.**

Every file read, grep, or pattern search by an implementer wastes context tokens. Smart atomic plans embed everything the implementer needs, eliminating exploration overhead and protecting the context window from compaction.

## Instructions

- **Atomic means independently executable**: Each subplan should be implementable without depending on other subplans being complete
- **Testable means verifiable**: Each subplan must have specific test commands and acceptance criteria
- **Self-contained means no exploration**: Embed all patterns, types, and context - implementer should never search
- **Include all required sections**: Context budget, scope, prerequisites, patterns, files, steps, tests, acceptance criteria, rollback notes
- **Use consistent naming**: Zero-padded IDs (001, 002) with kebab-case slugs
- **Document assumptions**: Write assumptions explicitly instead of leaving gaps
- **Respect token budgets**: Each subplan should enable implementation in <15,000 tokens
- **Embed, don't reference vaguely**: Instead of "follow patterns", embed the actual code snippets

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

## Context Budget

| Item | Tokens | Notes |
|------|--------|-------|
| This subplan | ~X | - |
| Files to read | ~X | [list files] |
| Files to modify | ~X | [list files] |
| Embedded snippets | ~X | [count] |
| **Estimated total** | ~X | Target: <15,000 |

## Scope

**In Scope:**
- Specific item to implement
- Another item

**Out of Scope:**
- What this subplan does NOT cover
- Deferred to other subplans

## Prerequisites

**Required Context (embedded below):**
- Type definitions needed
- Patterns to follow
- Related function signatures

**Files Implementer Must Read:**
- `exact/path/file.ts:10-50` - Reason (only specific lines, not full file)

## Code Patterns to Follow

### Pattern Name (from source/file.ts:XX-YY)
```typescript
// Embed actual code snippet here
// Implementer should copy this style exactly
```

## Files

- `path/to/file.ts` - Create - Description of what this file does
- `path/to/existing.ts:45-60` - Modify - What changes are needed (specific lines)

## Steps

1. **First step**: Detailed description of what to do
   - Exact file: `path/to/file.ts`
   - Use pattern: [reference embedded pattern above]
2. **Second step**: Next action with specific details
3. **Third step**: Continue until complete

## Unit Tests

- [ ] Test happy path: description
- [ ] Test edge case: description
- [ ] Test error handling: description

**Test Command:** `npm test -- path/to/test`

**Test Pattern to Follow (from tests/example.test.ts:10-30):**
```typescript
// Embed the test pattern here
```

## Acceptance Criteria

- [ ] Criterion 1: Specific, measurable outcome
- [ ] Criterion 2: Another verifiable requirement
- [ ] Criterion 3: Final check

## Rollback Notes

To undo this subplan:
1. Delete created files: [list]
2. Revert changes to: [list]
3. Any cleanup needed

## Implementation Notes

**DO NOT:**
- Search for patterns (all embedded above)
- Explore for file locations (all paths explicit)
- Read files not listed in "Files Implementer Must Read"

**JUST EXECUTE:**
- Follow the steps sequentially
- Use embedded patterns directly
- Run test command when done
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

## Context Window Protection

**Critical Principle**: Each subplan must be **self-contained** so the implementer can execute without additional exploration, file reads, or context gathering. The planner pays the context cost once; implementers should operate with minimal overhead.

### Why This Matters

- Context window is finite (~200K tokens) and expensive to refill
- Every file read, grep, or exploration by implementer consumes tokens
- If implementer needs to "figure out" context, tokens are wasted and risk of compaction increases
- Smart plans front-load context discovery to the planning phase

### Context Budget Strategy

| Component | Max Token Budget | Purpose |
|-----------|------------------|---------|
| Subplan file itself | ~2,000 tokens | Instructions and criteria |
| Embedded code snippets | ~3,000 tokens | Critical patterns to follow |
| File reference list | ~500 tokens | Exact paths, no searching needed |
| Test commands | ~200 tokens | Copy-paste ready commands |
| **Total per subplan** | **~6,000 tokens** | Keeps implementation lean |

### Embedding Context in Subplans

Instead of saying "follow existing patterns", **embed the patterns directly**:

```markdown
## Code Patterns to Follow

### Import Style (from src/utils/logger.ts:1-5)
```typescript
import { Logger } from '@/core/logger';
import type { LogLevel } from '@/types';
```

### Error Handling Pattern (from src/api/handlers.ts:42-58)
```typescript
try {
  const result = await operation();
  return { success: true, data: result };
} catch (error) {
  logger.error('Operation failed', { error });
  return { success: false, error: error.message };
}
```
```

### What to Embed vs Reference

**EMBED directly in subplan:**
- Import patterns and style conventions
- Type definitions the implementer will use
- Related function signatures (not full implementations)
- Error handling patterns
- Test patterns and assertions style
- Config file formats/schemas

**REFERENCE with exact path + line numbers:**
- Large files (>100 lines) - provide path and relevant line ranges
- External dependencies - link to docs
- Full test files - reference, don't copy

### Self-Contained Checklist

Before finalizing a subplan, verify:

- [ ] **No exploration needed**: All file paths are explicit, no "find the..." language
- [ ] **No pattern hunting**: Code patterns embedded or referenced with exact locations
- [ ] **No type guessing**: All relevant type definitions included or referenced
- [ ] **No convention discovery**: Style/naming conventions stated explicitly
- [ ] **No test setup research**: Test commands are copy-paste ready
- [ ] **No dependency investigation**: Required imports listed explicitly

### Anti-Patterns to Avoid

| Bad (Forces Exploration) | Good (Self-Contained) |
|--------------------------|----------------------|
| "Follow existing patterns" | "Use the error pattern from `src/utils/errors.ts:15-30` (embedded above)" |
| "Update the relevant config" | "Update `tsconfig.json` line 24: add `"strict": true`" |
| "Add tests similar to others" | "Create test in `__tests__/feature.test.ts` using pattern from `__tests__/user.test.ts:10-40` (embedded above)" |
| "Use appropriate types" | "Use `UserProfile` type from `src/types/user.ts:12-18` (definition embedded above)" |
| "Handle errors properly" | "Wrap in try/catch using pattern X (embedded), log with `logger.error()`" |

### Subplan Size Limits

To protect context during implementation:

- **Max 3 files to create**: More files = split into separate subplan
- **Max 5 files to modify**: More changes = split into separate subplan
- **Max 200 lines of new code**: Larger changes = split into separate subplan
- **Max 3 embedded code snippets**: More context = create a context-bundle file

### Context Bundle Pattern

For complex subplans requiring extensive context, create a companion bundle:

```
subplans/
├── 003-complex-feature.md        # The subplan
└── 003-complex-feature.context/  # Context bundle
    ├── types.ts.snippet          # Relevant type definitions
    ├── patterns.md               # Code patterns to follow
    └── related-apis.md           # API signatures needed
```

Reference in subplan:
```markdown
## Context Bundle

Load context from `subplans/003-complex-feature.context/`:
- `types.ts.snippet` - Type definitions for this feature
- `patterns.md` - Code patterns to follow
- `related-apis.md` - Existing APIs this integrates with
```

### Estimating Implementation Context Cost

When designing subplans, estimate the implementer's context usage:

```
Subplan file:           ~2,000 tokens
Files to read:          ~X files × ~1,000 tokens = ~X,000 tokens
Files to modify:        ~Y files × ~1,500 tokens = ~Y,500 tokens
Test file creation:     ~1,000 tokens
Safety buffer:          ~2,000 tokens
─────────────────────────────────────────────────
Total estimated:        Should stay under 15,000 tokens
```

If estimate exceeds 15,000 tokens, split the subplan.

## Best Practices

- **Order subplans logically**: Foundation first, then dependent features
- **Keep subplans small**: Aim for 1-2 hours of work each
- **Be specific about tests**: Include exact test commands
- **Consider rollback**: Always document how to undo changes
- **Include file paths**: Use absolute paths from repo root
- **Embed critical context**: Don't make implementers hunt for patterns
- **Respect token budgets**: Split large subplans to protect context window
- **Front-load discovery**: Planner explores once, implementers execute directly
