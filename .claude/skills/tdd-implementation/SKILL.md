---
name: tdd-implementation
description: Implements code using Test-Driven Development with strict scope control. Use when implementing subplans, adding features with tests, or fixing bugs with regression tests.
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
---

# TDD Implementation Skill

Implement code using Test-Driven Development: write tests first, then implement minimal code to pass them.

## Instructions

- **Tests first**: Write or update tests before implementation
- **Red-Green-Refactor**: Ensure tests fail first (red), then pass (green), then refactor
- **Minimal code**: Write only the code needed to pass tests
- **No scope creep**: Implement exactly what's specified, nothing more
- **Don't weaken tests**: Never modify tests just to make them pass

## Workflow

### 1. Understand the Requirement

- Read the subplan or feature specification
- Identify the behavior to implement
- Note edge cases and error conditions

### 2. Write Tests First (Red Phase)

```typescript
// Example: Testing a new function
describe('validateEmail', () => {
  it('should return true for valid email', () => {
    expect(validateEmail('user@example.com')).toBe(true);
  });

  it('should return false for invalid email', () => {
    expect(validateEmail('invalid')).toBe(false);
  });

  it('should handle edge cases', () => {
    expect(validateEmail('')).toBe(false);
    expect(validateEmail(null)).toBe(false);
  });
});
```

- Run tests to confirm they fail:
  ```bash
  npm test -- --grep "validateEmail"
  ```

### 3. Implement Minimal Code (Green Phase)

- Write the simplest code that makes tests pass
- Don't add features not covered by tests
- Don't optimize prematurely

```typescript
// Minimal implementation
function validateEmail(email: string | null): boolean {
  if (!email) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
```

- Run tests to confirm they pass:
  ```bash
  npm test -- --grep "validateEmail"
  ```

### 4. Refactor (Optional)

- Only refactor if code is messy or duplicated
- Keep tests passing throughout
- Don't change behavior

### 5. Verify Full Test Suite

- Run all tests to check for regressions:
  ```bash
  npm test
  ```

## Test Categories

### Happy Path Tests
- Normal expected usage
- Valid inputs
- Success scenarios

### Edge Case Tests
- Boundary conditions
- Empty/null inputs
- Maximum/minimum values

### Error Handling Tests
- Invalid inputs
- Network failures
- Permission errors

### Integration Tests
- Component interactions
- API endpoints
- Database operations

## Examples

### Example 1: Adding a New Function

**Requirement**: Add function to calculate order total

**Step 1**: Write test
```typescript
describe('calculateTotal', () => {
  it('should sum item prices', () => {
    const items = [{ price: 10 }, { price: 20 }];
    expect(calculateTotal(items)).toBe(30);
  });

  it('should return 0 for empty array', () => {
    expect(calculateTotal([])).toBe(0);
  });
});
```

**Step 2**: Run test (should fail)
```bash
npm test -- calculateTotal
# ✗ should sum item prices
# ✗ should return 0 for empty array
```

**Step 3**: Implement
```typescript
function calculateTotal(items: { price: number }[]): number {
  return items.reduce((sum, item) => sum + item.price, 0);
}
```

**Step 4**: Run test (should pass)
```bash
npm test -- calculateTotal
# ✓ should sum item prices
# ✓ should return 0 for empty array
```

### Example 2: Fixing a Bug

**Bug**: Login fails silently when server returns 500

**Step 1**: Write regression test
```typescript
it('should throw error on server error', async () => {
  mockServer.respondWith(500);
  await expect(login('user', 'pass')).rejects.toThrow('Server error');
});
```

**Step 2**: Run test (should fail, proving bug exists)

**Step 3**: Fix the code
```typescript
if (response.status >= 500) {
  throw new Error('Server error');
}
```

**Step 4**: Run test (should pass)

## Best Practices

- **One assertion per test**: Makes failures clear
- **Descriptive test names**: `should return error when email is invalid`
- **Arrange-Act-Assert**: Structure tests clearly
- **Test behavior, not implementation**: Don't test private methods
- **Keep tests fast**: Mock external dependencies
- **Run tests frequently**: After every small change

## Common Test Commands

```bash
# Run all tests
npm test

# Run specific test file
npm test -- path/to/test.ts

# Run tests matching pattern
npm test -- --grep "pattern"

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```
