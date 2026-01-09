#!/usr/bin/env bun
/**
 * Full-Cycle Workflow
 * Usage: bun full-cycle.ts "your goal here"
 *
 * Chains: plan → build → test → review with retry loop
 */

import { join } from 'path';
import { generateRunId, initRun, getRunDir, saveState, loadState, markComplete } from './lib/state';

const MAX_ATTEMPTS = 5;

interface Subplan {
  id: string;
  title: string;
  path: string;
}

interface PlanJson {
  run_id: string;
  goal: string;
  subplans: Subplan[];
}

interface ReviewJson {
  approved: boolean;
  blockers: string[];
  notes: string;
  next_actions: string[];
}

async function runScript(script: string, args: string[]): Promise<{ exitCode: number; output: string }> {
  const scriptPath = join(import.meta.dir, script);
  const proc = Bun.spawn(['bun', scriptPath, ...args], {
    cwd: process.cwd(),
    stdout: 'inherit',
    stderr: 'inherit',
  });

  const exitCode = await proc.exited;
  return { exitCode, output: '' };
}

async function main() {
  // Parse goal from arguments
  const goal = Bun.argv.slice(2).join(' ').trim();

  if (!goal) {
    console.error('Usage: bun full-cycle.ts "your goal here"');
    console.error('Example: bun full-cycle.ts "Add user authentication with JWT"');
    process.exit(1);
  }

  console.log('='.repeat(60));
  console.log('FULL-CYCLE WORKFLOW');
  console.log('='.repeat(60));
  console.log(`Goal: ${goal}`);
  console.log('='.repeat(60));
  console.log();

  // Generate run ID
  const runId = generateRunId();
  await initRun(runId, goal);
  const runDir = getRunDir(runId);

  console.log(`Run ID: ${runId}`);
  console.log(`Run Dir: ${runDir}`);
  console.log();

  // ========== PHASE 1: PLAN ==========
  console.log('>>> PHASE 1: PLANNING');
  console.log();

  const planResult = await runScript('plan.ts', [goal]);
  if (planResult.exitCode !== 0) {
    console.error('Planning failed!');
    process.exit(1);
  }

  // Read plan.json to get subplans
  const planJsonPath = join(runDir, 'plan', 'plan.json');
  const planFile = Bun.file(planJsonPath);

  if (!(await planFile.exists())) {
    console.error('Plan was not created. Check plan.ts output.');
    process.exit(1);
  }

  const plan: PlanJson = JSON.parse(await planFile.text());
  const subplans = plan.subplans || [];

  if (subplans.length === 0) {
    console.error('No subplans found in plan.json');
    process.exit(1);
  }

  console.log();
  console.log(`Found ${subplans.length} subplan(s)`);
  subplans.forEach((sp) => console.log(`  - ${sp.id}: ${sp.title}`));
  console.log();

  // ========== PHASE 2: BUILD/TEST/REVIEW PER SUBPLAN ==========
  for (let i = 0; i < subplans.length; i++) {
    const subplan = subplans[i];
    const subplanPath = join(runDir, 'plan', 'subplans', `${subplan.id}.md`);

    console.log('='.repeat(60));
    console.log(`>>> SUBPLAN ${i + 1}/${subplans.length}: ${subplan.id}`);
    console.log(`    ${subplan.title}`);
    console.log('='.repeat(60));
    console.log();

    let approved = false;
    let attempt = 0;

    while (!approved && attempt < MAX_ATTEMPTS) {
      attempt++;
      console.log(`--- Attempt ${attempt}/${MAX_ATTEMPTS} ---`);
      console.log();

      // Update state
      await saveState(runId, {
        runId,
        goal,
        phase: 'implementing',
        currentSubplan: i,
        currentAttempt: attempt,
        updatedAt: new Date().toISOString(),
      });

      // BUILD
      console.log('>>> BUILD');
      const buildResult = await runScript('build.ts', [subplanPath]);
      if (buildResult.exitCode !== 0) {
        console.error(`Build failed on attempt ${attempt}`);
        if (attempt >= MAX_ATTEMPTS) {
          throw new Error(`Subplan ${subplan.id} failed after ${MAX_ATTEMPTS} build attempts`);
        }
        continue;
      }

      // TEST
      console.log();
      console.log('>>> TEST');
      const testResult = await runScript('test.ts', [subplanPath]);
      if (testResult.exitCode !== 0) {
        console.error(`Tests failed on attempt ${attempt}`);
        if (attempt >= MAX_ATTEMPTS) {
          throw new Error(`Subplan ${subplan.id} failed after ${MAX_ATTEMPTS} test attempts`);
        }
        continue;
      }

      // REVIEW
      console.log();
      console.log('>>> REVIEW');
      const reviewResult = await runScript('review.ts', [runId]);

      // Read review result
      const reviewPath = join(runDir, 'review.json');
      const reviewFile = Bun.file(reviewPath);

      if (await reviewFile.exists()) {
        const review: ReviewJson = JSON.parse(await reviewFile.text());

        if (review.approved) {
          approved = true;
          console.log();
          console.log(`SUBPLAN ${subplan.id} APPROVED`);
        } else {
          console.log();
          console.log(`SUBPLAN ${subplan.id} REJECTED`);
          console.log('Blockers:');
          review.blockers.forEach((b) => console.log(`  - ${b}`));
          console.log('Next actions:');
          review.next_actions.forEach((a) => console.log(`  - ${a}`));

          if (attempt >= MAX_ATTEMPTS) {
            throw new Error(
              `Subplan ${subplan.id} failed review after ${MAX_ATTEMPTS} attempts.\n` +
              `Blockers: ${review.blockers.join(', ')}`
            );
          }
        }
      } else {
        // No review file - treat as failure
        console.warn('No review.json found, treating as failed');
        if (attempt >= MAX_ATTEMPTS) {
          throw new Error(`Subplan ${subplan.id} failed - no review output`);
        }
      }

      console.log();
    }

    if (!approved) {
      throw new Error(`Subplan ${subplan.id} not approved after ${MAX_ATTEMPTS} attempts`);
    }
  }

  // ========== PHASE 3: COMPLETE ==========
  console.log('='.repeat(60));
  console.log('>>> ALL SUBPLANS APPROVED');
  console.log('='.repeat(60));
  console.log();

  await markComplete(runId);
  await saveState(runId, {
    runId,
    goal,
    phase: 'completed',
    completedAt: new Date().toISOString(),
  });

  console.log(`Run ${runId} completed successfully!`);
  console.log(`Output: ${runDir}/FINAL.md`);
  console.log('='.repeat(60));
}

main().catch((err) => {
  console.error();
  console.error('='.repeat(60));
  console.error('FULL-CYCLE FAILED');
  console.error('='.repeat(60));
  console.error(err.message);
  process.exit(1);
});
