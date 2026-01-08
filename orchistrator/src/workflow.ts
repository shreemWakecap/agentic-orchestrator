/**
 * Core workflow logic: Plan → Implement → Test → Review → Iterate
 */

import fs from "node:fs/promises";
import path from "node:path";
import { runClaude } from "./claude.js";
import { Logger } from "./logger.js";
import type {
  Plan,
  ReviewResult,
  SubplanState,
  WorkflowConfig,
  WorkflowState,
  DEFAULT_CONFIG,
} from "./types.js";

// ============================================================================
// Schemas for structured output
// ============================================================================

const PLAN_SCHEMA = {
  type: "object",
  properties: {
    run_id: { type: "string" },
    goal: { type: "string" },
    assumptions: { type: "array", items: { type: "string" } },
    subplans: {
      type: "array",
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          title: { type: "string" },
          path: { type: "string" },
        },
        required: ["id", "title", "path"],
      },
    },
  },
  required: ["run_id", "goal", "subplans"],
};

const REVIEW_SCHEMA = {
  type: "object",
  properties: {
    approved: { type: "boolean" },
    blockers: { type: "array", items: { type: "string" } },
    notes: { type: "string" },
    next_actions: { type: "array", items: { type: "string" } },
  },
  required: ["approved", "blockers", "notes", "next_actions"],
};

// ============================================================================
// Workflow Class
// ============================================================================

export class Workflow {
  private repoRoot: string;
  private runId: string;
  private runDir: string;
  private config: WorkflowConfig;
  private logger: Logger;
  private state: WorkflowState;

  constructor(
    repoRoot: string,
    runId: string,
    goal: string,
    config: WorkflowConfig
  ) {
    this.repoRoot = repoRoot;
    this.runId = runId;
    this.runDir = path.join(repoRoot, "orchistrator", "runs", runId);
    this.config = config;
    this.logger = new Logger(this.runDir);
    this.state = {
      runId,
      goal,
      phase: "planning",
      plan: null,
      subplanStates: new Map(),
      currentSubplanId: null,
      startTime: new Date().toISOString(),
      endTime: null,
    };
  }

  // --------------------------------------------------------------------------
  // Directory Setup
  // --------------------------------------------------------------------------

  private async setupDirectories(): Promise<void> {
    const dirs = [
      path.join(this.runDir, "plan"),
      path.join(this.runDir, "plan", "subplans"),
      path.join(this.runDir, "logs"),
      path.join(this.runDir, "subplan-results"),
      path.join(this.runDir, "memory"),
    ];
    for (const dir of dirs) {
      await fs.mkdir(dir, { recursive: true });
    }
  }

  private async writeFile(relativePath: string, content: string): Promise<void> {
    const fullPath = path.join(this.runDir, relativePath);
    await fs.mkdir(path.dirname(fullPath), { recursive: true });
    await fs.writeFile(fullPath, content, "utf8");
  }

  private async readFile(relativePath: string): Promise<string> {
    const fullPath = path.join(this.runDir, relativePath);
    return fs.readFile(fullPath, "utf8");
  }

  private async readJson<T>(relativePath: string): Promise<T | null> {
    try {
      const content = await this.readFile(relativePath);
      return JSON.parse(content) as T;
    } catch {
      return null;
    }
  }

  // --------------------------------------------------------------------------
  // Planning Phase
  // --------------------------------------------------------------------------

  private async executePlanPhase(): Promise<Plan> {
    await this.logger.phase("Planning");
    await this.logger.event("plan_started", this.runId);

    const prompt = `
GOAL:
${this.state.goal}

RUN-ID:
${this.runId}

Create a planning folder at:
orchistrator/runs/${this.runId}/plan/

Write:
- plan.json (goal, assumptions, subplans[])
- overview.md (human-readable summary)
- subplans/*.md (atomic subplans with scope, files, steps, tests, acceptance criteria, rollback notes)

Use the planner subagent and atomic-planning skill if available.
Do NOT implement code—planning only.

Return structured output matching the JSON schema.
`.trim();

    const result = await runClaude({
      cwd: this.repoRoot,
      prompt,
      outputFormat: "json",
      jsonSchema: PLAN_SCHEMA,
      allowedTools: this.config.allowedToolsPlan,
    });

    await this.writeFile("logs/01-plan-output.json", result.stdout);

    if (result.exitCode !== 0) {
      throw new Error(`Planning failed: ${result.stderr}`);
    }

    // Extract structured output
    const parsed = result.parsedJson as { result?: Plan; structured_output?: Plan } | null;
    let plan: Plan | null = null;

    if (parsed) {
      plan = parsed.structured_output ?? parsed.result ?? (parsed as Plan);
    }

    // Prefer disk plan.json if it exists (Claude wrote it)
    const diskPlan = await this.readJson<Plan>("plan/plan.json");
    if (diskPlan) {
      plan = diskPlan;
    }

    if (!plan || !plan.subplans) {
      throw new Error("Planning did not produce valid plan.json");
    }

    await this.logger.info(`Plan created with ${plan.subplans.length} subplans`);
    await this.logger.event("plan_completed", this.runId, {
      data: { subplanCount: plan.subplans.length },
    });

    return plan;
  }

  // --------------------------------------------------------------------------
  // Implementation Phase
  // --------------------------------------------------------------------------

  private async executeImplementPhase(
    subplanState: SubplanState,
    attemptNumber: number
  ): Promise<string> {
    await this.logger.subphase(`Implement (Attempt ${attemptNumber})`);

    const subplanContent = await fs.readFile(
      path.join(this.repoRoot, subplanState.path),
      "utf8"
    );

    const prompt = `
RUN-ID: ${this.runId}
SUBPLAN: ${subplanState.id} - ${subplanState.title}

Subplan markdown:
${subplanContent}

Prior memory/feedback (if any):
${subplanState.memory || "None"}

Implement ONLY this subplan, including unit tests.
Follow the steps exactly. No scope creep.
If the plan is wrong, report what must change instead of implementing.

Use the implementer subagent and tdd-implementation skill if available.
`.trim();

    const result = await runClaude({
      cwd: this.repoRoot,
      prompt,
      outputFormat: "text",
      allowedTools: this.config.allowedToolsImplement,
    });

    const attemptDir = `subplan-results/${subplanState.id}/attempt-${String(attemptNumber).padStart(2, "0")}`;
    await this.writeFile(`${attemptDir}/implement.txt`, result.stdout);

    if (result.exitCode !== 0) {
      throw new Error(`Implementation failed: ${result.stderr}`);
    }

    await this.logger.event("subplan_implement_completed", this.runId, {
      subplanId: subplanState.id,
      attemptNumber,
    });

    return result.stdout;
  }

  // --------------------------------------------------------------------------
  // Test Phase
  // --------------------------------------------------------------------------

  private async executeTestPhase(
    subplanState: SubplanState,
    attemptNumber: number
  ): Promise<string> {
    await this.logger.subphase("Test");

    const prompt = `
RUN-ID: ${this.runId}
SUBPLAN: ${subplanState.id} - ${subplanState.title}

Run the subplan test command(s) and fix failures until green.
Use the test-runner subagent if available.
Summarize commands run and final results.
`.trim();

    const result = await runClaude({
      cwd: this.repoRoot,
      prompt,
      outputFormat: "text",
      allowedTools: this.config.allowedToolsTest,
    });

    const attemptDir = `subplan-results/${subplanState.id}/attempt-${String(attemptNumber).padStart(2, "0")}`;
    await this.writeFile(`${attemptDir}/test.txt`, result.stdout);

    if (result.exitCode !== 0) {
      throw new Error(`Test phase failed: ${result.stderr}`);
    }

    await this.logger.event("subplan_test_completed", this.runId, {
      subplanId: subplanState.id,
      attemptNumber,
    });

    return result.stdout;
  }

  // --------------------------------------------------------------------------
  // Review Phase
  // --------------------------------------------------------------------------

  private async executeReviewPhase(
    subplanState: SubplanState,
    attemptNumber: number,
    testOutput: string
  ): Promise<ReviewResult> {
    await this.logger.subphase("Review");

    const prompt = `
RUN-ID: ${this.runId}
SUBPLAN: ${subplanState.id} - ${subplanState.title}

Plan folder: orchistrator/runs/${this.runId}/plan/
Active subplan file: ${subplanState.path}

Test output:
${testOutput.substring(0, 5000)}

Do a strict plan-compliance review using the reviewer subagent and plan-compliance-review skill.
Return structured JSON with: approved (boolean), blockers (string[]), notes (string), next_actions (string[]).
`.trim();

    const result = await runClaude({
      cwd: this.repoRoot,
      prompt,
      outputFormat: "json",
      jsonSchema: REVIEW_SCHEMA,
      allowedTools: this.config.allowedToolsReview,
    });

    const attemptDir = `subplan-results/${subplanState.id}/attempt-${String(attemptNumber).padStart(2, "0")}`;
    await this.writeFile(`${attemptDir}/review.json`, result.stdout);

    // Extract review result
    const parsed = result.parsedJson as { structured_output?: ReviewResult; result?: ReviewResult } | null;
    let review: ReviewResult | null = null;

    if (parsed) {
      review = parsed.structured_output ?? parsed.result ?? (parsed as ReviewResult);
    }

    if (!review || typeof review.approved !== "boolean") {
      await this.logger.warn("Review output was not structured, treating as rejection");
      review = {
        approved: false,
        blockers: ["Review output was not valid JSON"],
        notes: result.stdout.substring(0, 500),
        next_actions: ["Re-run review with proper JSON output"],
      };
    }

    await this.logger.event("subplan_review_completed", this.runId, {
      subplanId: subplanState.id,
      attemptNumber,
      data: { approved: review.approved },
    });

    return review;
  }

  // --------------------------------------------------------------------------
  // Memory Phase
  // --------------------------------------------------------------------------

  private async generateMemory(
    subplanState: SubplanState,
    attemptNumber: number
  ): Promise<string> {
    const attemptDir = `subplan-results/${subplanState.id}/attempt-${String(attemptNumber).padStart(2, "0")}`;

    const prompt = `
Create a compact context packet (<250 tokens) for subplan ${subplanState.id}.
Include: changed files, test status, and any notes.

Read the attempt outputs at:
- orchistrator/runs/${this.runId}/${attemptDir}/implement.txt
- orchistrator/runs/${this.runId}/${attemptDir}/test.txt
- orchistrator/runs/${this.runId}/${attemptDir}/review.json

Use the memory-summarizer subagent if available.
`.trim();

    const result = await runClaude({
      cwd: this.repoRoot,
      prompt,
      outputFormat: "text",
      allowedTools: this.config.allowedToolsMemory,
    });

    await this.writeFile(`memory/${subplanState.id}.md`, result.stdout);
    return result.stdout;
  }

  // --------------------------------------------------------------------------
  // Subplan Execution Loop
  // --------------------------------------------------------------------------

  private async executeSubplan(subplanState: SubplanState): Promise<boolean> {
    await this.logger.info(`Starting subplan: ${subplanState.id} - ${subplanState.title}`);
    await this.logger.event("subplan_started", this.runId, {
      subplanId: subplanState.id,
    });

    subplanState.status = "in_progress";

    for (let attempt = 1; attempt <= this.config.maxAttemptsPerSubplan; attempt++) {
      await this.logger.event("subplan_attempt_started", this.runId, {
        subplanId: subplanState.id,
        attemptNumber: attempt,
      });

      try {
        // IMPLEMENT
        const implementOutput = await this.executeImplementPhase(subplanState, attempt);

        // TEST
        const testOutput = await this.executeTestPhase(subplanState, attempt);

        // REVIEW
        const review = await this.executeReviewPhase(subplanState, attempt, testOutput);

        // Record attempt
        subplanState.attempts.push({
          attemptNumber: attempt,
          implementOutput: implementOutput.substring(0, 1000),
          testOutput: testOutput.substring(0, 1000),
          reviewResult: review,
          timestamp: new Date().toISOString(),
        });

        if (review.approved) {
          subplanState.status = "approved";
          await this.generateMemory(subplanState, attempt);
          await this.logger.event("subplan_approved", this.runId, {
            subplanId: subplanState.id,
            attemptNumber: attempt,
          });
          return true;
        } else {
          // Build memory for next attempt
          subplanState.memory = `Review rejected (attempt ${attempt}).\n` +
            `Blockers:\n- ${review.blockers.join("\n- ")}\n` +
            `Next actions:\n- ${review.next_actions.join("\n- ")}\n` +
            `Notes: ${review.notes}`;

          await this.logger.event("subplan_rejected", this.runId, {
            subplanId: subplanState.id,
            attemptNumber: attempt,
            data: { blockers: review.blockers },
          });
        }
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        await this.logger.error(`Attempt ${attempt} error: ${errMsg}`);
        subplanState.memory = `Attempt ${attempt} failed with error: ${errMsg}`;
      }
    }

    subplanState.status = "failed";
    await this.logger.event("subplan_failed", this.runId, {
      subplanId: subplanState.id,
      data: { attempts: this.config.maxAttemptsPerSubplan },
    });
    return false;
  }

  // --------------------------------------------------------------------------
  // Main Execution
  // --------------------------------------------------------------------------

  async execute(): Promise<void> {
    await this.setupDirectories();
    await this.logger.init();

    await this.logger.event("workflow_started", this.runId, {
      data: { goal: this.state.goal },
    });

    // Save goal
    await this.writeFile("goal.md", `# Goal\n\n${this.state.goal}\n`);

    try {
      // PLAN PHASE
      this.state.phase = "planning";
      this.state.plan = await this.executePlanPhase();

      // Initialize subplan states
      for (const sp of this.state.plan.subplans) {
        this.state.subplanStates.set(sp.id, {
          id: sp.id,
          title: sp.title,
          path: sp.path,
          status: "pending",
          attempts: [],
          memory: "",
        });
      }

      // EXECUTION PHASE
      this.state.phase = "executing";
      await this.logger.phase("Execution");

      const total = this.state.plan.subplans.length;
      let completed = 0;

      for (const sp of this.state.plan.subplans) {
        const subplanState = this.state.subplanStates.get(sp.id)!;
        this.state.currentSubplanId = sp.id;

        await this.logger.progress(completed, total, `${sp.id} - ${sp.title}`);

        const success = await this.executeSubplan(subplanState);

        if (!success) {
          this.state.phase = "failed";
          this.state.endTime = new Date().toISOString();
          await this.writeFile("FAILED.md", `# FAILED\n\nSubplan ${sp.id} failed after ${this.config.maxAttemptsPerSubplan} attempts.\n`);
          await this.logger.event("workflow_failed", this.runId, {
            data: { failedSubplan: sp.id },
          });
          throw new Error(`Subplan ${sp.id} failed after ${this.config.maxAttemptsPerSubplan} attempts`);
        }

        completed++;
      }

      // COMPLETE
      this.state.phase = "complete";
      this.state.endTime = new Date().toISOString();
      await this.writeFile("FINAL.md", `# DONE\n\nRun ${this.runId} completed successfully.\n`);

      await this.logger.phase("Complete");
      await this.logger.info(`Workflow completed: ${this.runId}`);
      await this.logger.event("workflow_completed", this.runId);

    } catch (error) {
      this.state.phase = "failed";
      this.state.endTime = new Date().toISOString();
      await this.logger.error(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  // --------------------------------------------------------------------------
  // Getters
  // --------------------------------------------------------------------------

  getRunDir(): string {
    return this.runDir;
  }

  getState(): WorkflowState {
    return this.state;
  }
}
