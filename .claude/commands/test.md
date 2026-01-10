---
description: SDLC Test phase - run tests and validate implementation
argument-hint: [spec-path (optional)]
---

# Test

Run tests for the current implementation. Validates that the build phase produced working code.

## Variables

SPEC_PATH: $1

## Instructions

- If SPEC_PATH is provided, read the spec to understand what should be tested
- Detect the testing framework used in the project
- Check `.orchestrator/experts/` for any domain-specific testing patterns
- Run existing tests first to establish baseline
- Create new tests if the spec requires coverage that doesn't exist
- Report results clearly with pass/fail counts

## Workflow

1. **Detect Test Framework**
   - Look for: pytest.ini, jest.config.*, vitest.config.*, go.mod, Cargo.toml, etc.
   - Identify existing test directories and patterns

2. **Check Domain Expertise**
   - Read `.orchestrator/registry.json` to see available experts
   - Load relevant expertise for testing patterns

3. **Run Existing Tests**
   - Execute the test suite with the appropriate command
   - Capture results and any failures

4. **Analyze Coverage**
   - If SPEC_PATH provided, check if spec requirements are covered
   - Identify gaps in test coverage

5. **Create Missing Tests (if needed)**
   - Write tests for uncovered requirements
   - Follow existing test patterns and conventions

6. **Final Test Run**
   - Run complete test suite
   - Ensure all tests pass

## Report

```
Test Phase Results

Framework: <detected framework>
Spec: <spec path or "None">

Test Run:
- Total: <count>
- Passed: <count>
- Failed: <count>
- Skipped: <count>

<if new tests created>
New Tests Created:
- <file>: <test names>
</if>

<if failures>
Failures:
1. <test>: <reason>
</if>

Status: <PASS / FAIL>
Next: <run /review or fix issues>
```
