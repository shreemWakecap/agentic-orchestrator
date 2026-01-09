#!/usr/bin/env bun
/**
 * Review Workflow
 * Usage: bun review.ts "run-id"
 *
 * Reviews implementation against plan with strict pass/fail judgment
 */

import { runClaude } from './lib/claude';
import { loadAgent } from './lib/prompts';
import { getRunDir } from './lib/state';
import { join } from 'path';

// JSON schema for review output
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    approved: { type: 'boolean' },
    blockers: {
      type: 'array',
      items: { type: 'string' },
    },
    notes: { type: 'string' },
    next_actions: {
      type: 'array',
      items: { type: 'string' },
    },
  },
  required: ['approved', 'blockers', 'notes', 'next_actions'],
};

async function main() {
  // Parse run ID from arguments
  const runId = Bun.argv[2];

  if (!runId) {
    console.error('Usage: bun review.ts "run-id"');
    console.error();
    console.error('Example:');
    console.error('  bun review.ts 2024-01-15T10-30-00');
    process.exit(1);
  }

  const runDir = getRunDir(runId);
  const planPath = join(runDir, 'plan', 'plan.json');

  // Read the plan file
  const file = Bun.file(planPath);
  if (!(await file.exists())) {
    console.error(`Plan not found: ${planPath}`);
    console.error(`Run ID "${runId}" may not exist or has no plan.`);
    process.exit(1);
  }

  const planContent = await file.text();

  console.log('='.repeat(60));
  console.log('REVIEW WORKFLOW');
  console.log('='.repeat(60));
  console.log(`Run ID: ${runId}`);
  console.log(`Plan: ${planPath}`);
  console.log('='.repeat(60));
  console.log();

  // Load the reviewer agent
  const agent = await loadAgent('reviewer');

  // Build the prompt
  const prompt = `${agent}

## Your Task

Review the implementation for run "${runId}" against the plan.

**RUN ID:** ${runId}
**PLAN PATH:** ${planPath}

**PLAN CONTENT:**
${planContent}

## Instructions

1. Read the plan and all subplans in orchistrator/runs/${runId}/plan/subplans/
2. For each subplan, verify:
   - All acceptance criteria are met
   - Required files exist and are implemented correctly
   - Tests exist and cover the planned behavior
   - No scope creep (only what was planned)
   - Code quality (no obvious bugs, security issues, or maintainability problems)

3. Generate a verdict:
   - APPROVED if ALL criteria are met
   - REJECTED if ANY criteria are not met

4. Return structured JSON with your verdict.

You are READ-ONLY. Do NOT modify any files.
`;

  // Run Claude with JSON schema
  const result = await runClaude({
    prompt,
    allowedTools: ['Read', 'Glob', 'Grep'],
    jsonSchema: REVIEW_SCHEMA,
  });

  console.log();
  console.log('='.repeat(60));

  // Save review result
  const reviewPath = join(runDir, 'review.json');
  if (result.json) {
    await Bun.write(reviewPath, JSON.stringify(result.json, null, 2));
    console.log(`Review saved: ${reviewPath}`);

    const review = result.json as { approved: boolean; blockers: string[] };
    if (review.approved) {
      console.log('REVIEW: APPROVED');
    } else {
      console.log('REVIEW: REJECTED');
      console.log('Blockers:');
      review.blockers.forEach((b) => console.log(`  - ${b}`));
    }
  } else {
    console.log('REVIEW COMPLETE (no structured output)');
  }

  if (result.exitCode !== 0) {
    console.error(`Exit code: ${result.exitCode}`);
    process.exit(result.exitCode);
  }

  console.log('='.repeat(60));
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
