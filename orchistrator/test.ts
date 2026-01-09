#!/usr/bin/env bun
/**
 * Test Workflow
 * Usage: bun test.ts "path/to/subplan.md"
 *
 * Runs tests for a subplan and fixes failures until green
 */

import { runClaude } from './lib/claude';
import { loadAgent } from './lib/prompts';

async function main() {
  // Parse subplan path from arguments
  const subplanPath = Bun.argv[2];

  if (!subplanPath) {
    console.error('Usage: bun test.ts "path/to/subplan.md"');
    console.error();
    console.error('Example:');
    console.error('  bun test.ts orchistrator/runs/xxx/plan/subplans/001-setup.md');
    process.exit(1);
  }

  // Read the subplan file
  const file = Bun.file(subplanPath);
  if (!(await file.exists())) {
    console.error(`File not found: ${subplanPath}`);
    process.exit(1);
  }

  const subplanContent = await file.text();

  console.log('='.repeat(60));
  console.log('TEST WORKFLOW');
  console.log('='.repeat(60));
  console.log(`Subplan: ${subplanPath}`);
  console.log('='.repeat(60));
  console.log();

  // Load the test-runner agent
  const agent = await loadAgent('test-runner');

  // Build the prompt
  const prompt = `${agent}

## Your Task

Run tests for the following subplan and fix any failures:

**SUBPLAN FILE:** ${subplanPath}

**SUBPLAN CONTENT:**
${subplanContent}

## Instructions

1. Find the test command in the subplan (look for "Test Command" or "Validation" section)
2. Run the tests
3. If tests pass, report success and exit
4. If tests fail:
   - Analyze error messages and stack traces
   - Diagnose root cause
   - Apply minimal fix to the implementation (NOT the tests)
   - Re-run tests
   - Repeat until green (max 5 attempts)

IMPORTANT: Never weaken tests to make them pass. Always fix the implementation.
`;

  // Run Claude
  const result = await runClaude({
    prompt,
    allowedTools: ['Read', 'Edit', 'Write', 'Glob', 'Grep', 'Bash'],
  });

  console.log();
  console.log('='.repeat(60));

  if (result.exitCode === 0) {
    console.log('TESTS COMPLETE');
  } else {
    console.error('TESTS FAILED');
    console.error(`Exit code: ${result.exitCode}`);
    process.exit(result.exitCode);
  }

  console.log('='.repeat(60));
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
