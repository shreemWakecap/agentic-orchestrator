/**
 * State Management
 * Generate run IDs, save/load workflow state
 */

import { join } from 'path';
import { mkdir } from 'fs/promises';

const RUNS_DIR = join(process.cwd(), 'orchistrator', 'runs');

/**
 * Generate a unique run ID based on timestamp
 */
export function generateRunId(): string {
  const now = new Date();
  return now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
}

/**
 * Get the directory path for a run
 */
export function getRunDir(runId: string): string {
  return join(RUNS_DIR, runId);
}

/**
 * Initialize a new run directory
 */
export async function initRun(runId: string, goal: string): Promise<string> {
  const runDir = getRunDir(runId);

  // Create directory structure
  await mkdir(join(runDir, 'plan', 'subplans'), { recursive: true });
  await mkdir(join(runDir, 'logs'), { recursive: true });

  // Write goal file
  await Bun.write(join(runDir, 'goal.md'), `# Goal\n\n${goal}\n`);

  // Initialize state
  await saveState(runId, {
    runId,
    goal,
    phase: 'pending',
    createdAt: new Date().toISOString(),
    subplans: [],
    currentSubplan: 0,
  });

  return runDir;
}

/**
 * Save workflow state to disk
 */
export async function saveState(runId: string, state: object): Promise<void> {
  const statePath = join(getRunDir(runId), 'state.json');
  await Bun.write(statePath, JSON.stringify(state, null, 2));
}

/**
 * Load workflow state from disk
 */
export async function loadState(runId: string): Promise<object | null> {
  const statePath = join(getRunDir(runId), 'state.json');
  const file = Bun.file(statePath);

  if (!(await file.exists())) {
    return null;
  }

  return JSON.parse(await file.text());
}

/**
 * List all runs
 */
export async function listRuns(): Promise<string[]> {
  const dir = Bun.file(RUNS_DIR);
  // Use readdir to list directories
  const { readdir } = await import('fs/promises');
  try {
    const entries = await readdir(RUNS_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
      .sort()
      .reverse();
  } catch {
    return [];
  }
}

/**
 * Mark a run as complete
 */
export async function markComplete(runId: string): Promise<void> {
  const finalPath = join(getRunDir(runId), 'FINAL.md');
  await Bun.write(
    finalPath,
    `# Complete\n\nRun ${runId} completed at ${new Date().toISOString()}\n`
  );
}
