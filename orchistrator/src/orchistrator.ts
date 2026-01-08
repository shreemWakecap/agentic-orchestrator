import fs from "node:fs/promises";
import path from "node:path";
import { runClaude, extractStructuredOutput } from "./claude.js";

type RunWorkflowInput = { goal: string };

function safeRunId(): string {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

async function ensureDir(p: string) {
  await fs.mkdir(p, { recursive: true });
}

async function writeText(p: string, content: string) {
  await ensureDir(path.dirname(p));
  await fs.writeFile(p, content, "utf8");
}

async function readJson<T>(p: string): Promise<T | null> {
  try {
    return JSON.parse(await fs.readFile(p, "utf8")) as T;
  } catch {
    return null;
  }
}

export async function runWorkflow(input: RunWorkflowInput): Promise<void> {
  const repoRoot = process.cwd();
  const runId = safeRunId();

  const runDir = path.join(repoRoot, "orchistrator", "runs", runId);
  const planDir = path.join(runDir, "plan");
  const logsDir = path.join(runDir, "logs");
  const resultsDir = path.join(runDir, "subplan-results");
  const memoryDir = path.join(runDir, "memory");

  await ensureDir(planDir);
  await ensureDir(logsDir);
  await ensureDir(resultsDir);
  await ensureDir(memoryDir);

  await writeText(path.join(runDir, "goal.md"), `# Goal\n\n${input.goal}\n`);

  // -----------------------------
  // 1) PLAN (structured output)
  // -----------------------------
  const planSchema = {
    type: "object",
    properties: {
      run_id: { type: "string" },
      goal: { type: "string" },
      subplans: {
        type: "array",
        items: {
          type: "object",
          properties: {
            id: { type: "string" },
            title: { type: "string" },
            path: { type: "string" }
          },
          required: ["id", "title", "path"]
        }
      }
    },
    required: ["run_id", "goal", "subplans"]
  };

  const planPrompt = `
GOAL:
${input.goal}

RUN-ID:
${runId}

Create a planning folder at:
orchistrator/runs/${runId}/plan/

Write:
- plan.json (goal, assumptions, subplans[])
- overview.md
- subplans/*.md (atomic subplans)

Use the planner subagent and atomic-planning skill if available.
Do NOT implement code.

Return ONLY structured output matching the JSON schema.
`.trim();

  const planRes = await runClaude({
    cwd: repoRoot,
    prompt: planPrompt,
    outputFormat: "json",
    jsonSchema: planSchema,
    allowedTools: "Read,Write,Glob,Grep,Task,Skill"
  });

  await writeText(path.join(logsDir, "01-plan.json"), planRes.stdout);
  if (planRes.exitCode !== 0) throw new Error(`Plan failed:\n${planRes.stderr}`);

  const planOut = extractStructuredOutput(planRes.parsedJson);
  if (!planOut) throw new Error("Plan did not return structured_output.");

  // Prefer disk plan.json if it exists
  const diskPlan = await readJson<any>(path.join(planDir, "plan.json"));
  const plan = diskPlan ?? planOut;

  // -----------------------------
  // 2) EXECUTE subplans with retry loop
  // -----------------------------
  const maxAttempts = 5;

  for (const sp of plan.subplans) {
    const subplanPath = path.join(repoRoot, sp.path);
    const subplanText = await fs.readFile(subplanPath, "utf8");

    let approved = false;
    let memory = "";

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const attemptDir = path.join(resultsDir, sp.id, `attempt-${String(attempt).padStart(2, "0")}`);
      await ensureDir(attemptDir);

      // IMPLEMENT
      const implementPrompt = `
RUN-ID: ${runId}
SUBPLAN: ${sp.id} - ${sp.title}

Subplan markdown:
${subplanText}

Prior memory/feedback (if any):
${memory}

Implement ONLY this subplan, including unit tests.
If the plan is wrong, report what must change in the plan instead of implementing.

(Headless note: do not invoke slash commands; just do the task.)
`.trim();

      const impl = await runClaude({
        cwd: repoRoot,
        prompt: implementPrompt,
        outputFormat: "text",
        allowedTools: "Read,Edit,Write,Glob,Grep,Bash,Task,Skill"
      });
      await writeText(path.join(attemptDir, "implementer.txt"), impl.stdout);
      if (impl.exitCode !== 0) throw new Error(`Implement failed for ${sp.id}:\n${impl.stderr}`);

      // TEST
      const testPrompt = `
RUN-ID: ${runId}
SUBPLAN: ${sp.id} - ${sp.title}

Run the subplan test command(s) and fix failures until green.
Summarize commands run and final results.
`.trim();

      const test = await runClaude({
        cwd: repoRoot,
        prompt: testPrompt,
        outputFormat: "text",
        allowedTools: "Read,Edit,Write,Glob,Grep,Bash,Task,Skill"
      });
      await writeText(path.join(attemptDir, "tests.txt"), test.stdout);
      if (test.exitCode !== 0) throw new Error(`Tests step failed for ${sp.id}:\n${test.stderr}`);

      // REVIEW (strict JSON)
      const reviewSchema = {
        type: "object",
        properties: {
          approved: { type: "boolean" },
          blockers: { type: "array", items: { type: "string" } },
          notes: { type: "string" },
          next_actions: { type: "array", items: { type: "string" } }
        },
        required: ["approved", "blockers", "notes", "next_actions"]
      };

      const reviewPrompt = `
RUN-ID: ${runId}
SUBPLAN: ${sp.id} - ${sp.title}

Plan folder: orchistrator/runs/${runId}/plan/
Active subplan file: ${sp.path}

Test output:
${test.stdout}

Do a strict plan-compliance review and return structured JSON.
`.trim();

      const review = await runClaude({
        cwd: repoRoot,
        prompt: reviewPrompt,
        outputFormat: "json",
        jsonSchema: reviewSchema,
        allowedTools: "Read,Glob,Grep,Task,Skill"
      });

      await writeText(path.join(attemptDir, "review.json"), review.stdout);

      const reviewOut = extractStructuredOutput(review.parsedJson);
      if (!reviewOut) {
        memory = `Reviewer output was not structured. Raw:\n${review.stdout}`;
        continue;
      }

      if (reviewOut.approved) {
        approved = true;
        // Write a memory packet for audit / next steps
        const memPrompt = `
Create a compact context packet (<250 tokens) for subplan ${sp.id}.
Include: changed files (best guess), test status, and any remaining notes.
Use the last attempt outputs:
- implementer summary: (see ${attemptDir}/implementer.txt)
- tests: (see ${attemptDir}/tests.txt)
- review: (see ${attemptDir}/review.json)
`.trim();

        const mem = await runClaude({
          cwd: repoRoot,
          prompt: memPrompt,
          outputFormat: "text",
          allowedTools: "Read"
        });

        await writeText(path.join(memoryDir, `${sp.id}.md`), mem.stdout);
        break;
      } else {
        // Backtrack loop: feed blockers back into next implement attempt
        memory = `Review rejected.\nBlockers:\n- ${reviewOut.blockers.join("\n- ")}\nNext actions:\n- ${reviewOut.next_actions.join("\n- ")}\nNotes:\n${reviewOut.notes}`;
      }
    }

    if (!approved) {
      throw new Error(`Subplan ${sp.id} failed after ${maxAttempts} attempts. See ${resultsDir}/${sp.id}/`);
    }
  }

  await writeText(path.join(runDir, "FINAL.md"), `# DONE\nRun ${runId} completed.\n`);
  console.log(`DONE. Artifacts in: orchistrator/runs/${runId}/`);
}
