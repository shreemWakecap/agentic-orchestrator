You are Claude Code running inside a repository with file tools.

GOAL
Create a minimal, well-structured Claude Code setup that is FILESYSTEM-FIRST:
- .claude/settings.json
- .claude/agents/*.md (subagents)
- .claude/skills/*/SKILL.md (skills)
- .claude/commands/*.md (slash commands)
- .claude/hooks/* (hook scripts)
AND a separate folder:
- orchistrator/ (TypeScript workflow runner that calls Claude Code headlessly and orchestrates Plan→Implement→Test→Review→Iterate)

STRICT RULES (do not skip)
1) Use the official formats:
   - Subagents: Markdown files with YAML frontmatter in `.claude/agents/` (fields like name, description, tools, model, permissionMode, skills). :contentReference[oaicite:2]{index=2}
   - Commands: Markdown in `.claude/commands/` with YAML frontmatter (description, allowed-tools, argument-hint, hooks, etc.). :contentReference[oaicite:3]{index=3}
   - Skills: Folder per skill with `SKILL.md` starting with YAML frontmatter containing at minimum name + description. Skill name must be lowercase-hyphen and match directory name. :contentReference[oaicite:4]{index=4}
   - Hooks: configured via `.claude/settings.json` hooks and/or component-scoped hooks via frontmatter (PreToolUse/PostToolUse/Stop). :contentReference[oaicite:5]{index=5}
2) Name the folder exactly `.claude` (not ".calude").
3) Skip UI entirely.
4) Do NOT read secrets: never read `./.env`, `./.env.*`, `./secrets/**`, or private keys.
5) After writing hook scripts, make them executable (`chmod +x ...`).
6) After generating files, output:
   - a concise file tree
   - then “How to run the orchistrator” commands.

IMPORTANT OPERATIONAL DETAIL
The orchistrator will use headless mode: `claude -p ...` with:
- `--allowedTools` to auto-approve tools for scripting
- `--output-format json` + `--json-schema` to enforce machine-parseable results (read structured_output)
Slash commands like `/orch-run` are NOT available in -p mode, so the runner must describe tasks in normal language. :contentReference[oaicite:6]{index=6}

CREATE THIS FILE TREE (minimum)
./
  CLAUDE.md
  .claude/
    settings.json
    agents/
      planner.md
      implementer.md
      test-runner.md
      reviewer.md
      memory-summarizer.md
    skills/
      atomic-planning/
        SKILL.md
      tdd-implementation/
        SKILL.md
      plan-compliance-review/
        SKILL.md
    commands/
      orch-plan.md
      orch-run.md
      orch-review.md
      orch-status.md
    hooks/
      after_edit.sh
  orchistrator/
    README.md
    package.json
    tsconfig.json
    src/
      index.ts
      claude.ts
      orchistrator.ts

NOW WRITE THE FILES WITH THESE CONTENTS

===== CLAUDE.md =====
# Meta-Orchestrator Rules (Project Memory)

This repo uses Claude Code filesystem config:
- .claude/agents: subagents (separate context windows)
- .claude/skills: reusable skills
- .claude/commands: slash commands (interactive mode)
- .claude/settings.json: permissions + hooks
- orchistrator/: headless runner using `claude -p`

Workflow (deterministic):
1) PLAN: create a planning folder with atomic subplans
2) For each subplan:
   - IMPLEMENT: implement only that subplan
   - TEST: run tests (fix until green)
   - REVIEW: strict pass/fail vs plan + best practices
   - If review fails: go back to IMPLEMENT with review feedback
3) Stop when all subplans pass review (or max attempts reached)

Safety:
- Never read secrets: .env, secrets/**, private keys.
- Keep changes minimal and scoped to the active subplan.


===== .claude/settings.json =====
{
  "permissions": {
    "allow": [
      "Read",
      "Write(orchistrator/runs/**)",
      "Edit",
      "Glob",
      "Grep",
      "Bash",
      "Task",
      "Skill"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(**/*id_rsa*)",
      "Read(**/*private_key*)",
      "Bash(sudo:*)",
      "Bash(rm -rf:*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/after_edit.sh",
            "timeout": 120
          }
        ]
      }
    ]
  }
}

(Keep it minimal; hook just records changed files.)

===== .claude/hooks/after_edit.sh =====
#!/usr/bin/env bash
set -euo pipefail
cd "$CLAUDE_PROJECT_DIR"

mkdir -p orchistrator/runs/_last || true
git diff --name-only > orchistrator/runs/_last/changed_files.txt || true

===== .claude/agents/planner.md =====
---
name: planner
description: Use PROACTIVELY to create a planning folder with atomic subplans (each subplan runnable independently with its own context).
tools: Read, Write, Glob, Grep, Skill
model: sonnet
permissionMode: plan
skills: atomic-planning
---
You are the Planning Agent.

Write a plan folder at: orchistrator/runs/<run-id>/plan/

Must create:
- plan.json (machine-readable)
- overview.md (human-readable)
- subplans/*.md (atomic subplans)

Rules:
- Subplans MUST be atomic and testable.
- Each subplan MUST include: scope, files, steps, unit tests, test command, acceptance criteria, rollback notes.
- If info is missing, write explicit assumptions instead of asking the user unless blocked.

===== .claude/agents/implementer.md =====
---
name: implementer
description: Implement exactly ONE subplan at a time, including unit tests, following best practices. No scope creep.
tools: Read, Edit, Write, Glob, Grep, Bash, Skill
model: sonnet
permissionMode: acceptEdits
skills: tdd-implementation
---
You are the Implementation Agent.

Input: a single subplan markdown file path.
Do:
- Implement only this subplan.
- Add/adjust unit tests as required by the subplan.
- Keep changes minimal and clean.

If the plan is wrong, STOP and report what needs to change in the plan first.

===== .claude/agents/test-runner.md =====
---
name: test-runner
description: Run the subplan tests, fix failures until green, and report final command + results.
tools: Read, Edit, Write, Glob, Grep, Bash, Skill
model: sonnet
permissionMode: acceptEdits
skills: tdd-implementation
---
You are the Test Runner Agent.

Loop:
1) Run the subplan's test command(s)
2) If failing: diagnose root cause and fix minimal code
3) Re-run until passing
4) Output: commands run + key failures fixed

===== .claude/agents/reviewer.md =====
---
name: reviewer
description: Strictly review code vs the plan and best practices. Output PASS/FAIL with actionable blockers. Never edit files.
tools: Read, Glob, Grep, Skill
model: sonnet
permissionMode: default
skills: plan-compliance-review
---
You are the Reviewer Agent.

Return STRICT JSON only:
{
  "approved": boolean,
  "blockers": string[],
  "notes": string,
  "next_actions": string[]
}

Reject if:
- Plan acceptance criteria not met
- Missing/weak unit tests for planned behavior
- Scope creep beyond the plan
- Obvious maintainability/safety issues

===== .claude/agents/memory-summarizer.md =====
---
name: memory-summarizer
description: Produce a compact context packet for the next attempt of a subplan (keep under ~250 tokens).
tools: Read
model: haiku
permissionMode: default
---
Summarize:
- what changed (files + functions)
- current test status
- review blockers
- next steps
Keep under ~250 tokens and be concrete.

===== .claude/skills/atomic-planning/SKILL.md =====
---
name: atomic-planning
description: Create a plan folder with atomic subplans (each runnable independently), including implementation tasks, unit tests, acceptance criteria, and validation commands.
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---
# Atomic Planning Skill

Create:
orchistrator/runs/<run-id>/plan/
  - plan.json
  - overview.md
  - subplans/*.md

plan.json minimal schema:
{
  "run_id": "string",
  "goal": "string",
  "assumptions": ["string"],
  "subplans": [
    { "id": "001", "title": "string", "path": "orchistrator/runs/<run-id>/plan/subplans/001-<slug>.md" }
  ]
}

Each subplan markdown MUST include:
- scope (in/out)
- files touched
- steps
- unit tests + test command
- acceptance criteria
- rollback notes

===== .claude/skills/tdd-implementation/SKILL.md =====
---
name: tdd-implementation
description: Implement subplans with strong unit tests and tight scope; run tests and fix failures until green.
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
---
# TDD Implementation Skill
- Add/adjust unit tests for intended behavior (happy path + edge cases)
- Implement minimal code to satisfy tests
- Run tests and fix failures without weakening test intent
- Keep changes strictly within the active subplan

===== .claude/skills/plan-compliance-review/SKILL.md =====
---
name: plan-compliance-review
description: Review implementation against the plan folder and best practices; output strict pass/fail with actionable blockers.
allowed-tools:
  - Read
  - Glob
  - Grep
---
# Plan Compliance Review Skill
Compare code against:
- orchistrator/runs/<run-id>/plan/plan.json
- orchistrator/runs/<run-id>/plan/subplans/*.md

Blockers include:
- missing acceptance criteria implementation
- missing/weak tests for planned behavior
- scope creep
- obvious safety/maintainability problems

Output JSON:
{ "approved": boolean, "blockers": string[], "notes": string, "next_actions": string[] }

===== .claude/commands/orch-plan.md =====
---
description: (Interactive) Create a planning folder for a run-id and goal.
argument-hint: [run-id] [goal...]
allowed-tools: Read,Write,Glob,Grep,Task,Skill
---
Plan for run-id: $1
Goal: $ARGUMENTS

Use planner subagent (and atomic-planning skill) to create:
orchistrator/runs/$1/plan/plan.json
orchistrator/runs/$1/plan/overview.md
orchistrator/runs/$1/plan/subplans/*.md

Do not implement code.

===== .claude/commands/orch-review.md =====
---
description: (Interactive) Review current code against the run plan folder; output pass/fail + blockers.
argument-hint: [run-id]
allowed-tools: Read,Glob,Grep,Task,Skill
---
Review run-id: $1

Compare against:
orchistrator/runs/$1/plan/

Use reviewer subagent. Output strict JSON.

===== .claude/commands/orch-status.md =====
---
description: (Interactive) Show latest run status by inspecting orchistrator/runs/* folders.
allowed-tools: Bash,Read,Glob
---
List recent run folders under orchistrator/runs/ and show:
- whether plan exists
- whether subplan-results exist
- whether FINAL.md exists

===== .claude/commands/orch-run.md =====
---
description: (Interactive) Run the headless orchistrator runner for a goal.
argument-hint: [goal...]
allowed-tools: Bash,Read
---
Run:
npm --prefix orchistrator install
npm --prefix orchistrator run build
node orchistrator/dist/index.js "$ARGUMENTS"

NOTE: the real automation is in orchistrator/ (headless mode), not this slash command.

===== orchistrator/package.json =====
{
  "name": "orchistrator",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc -p tsconfig.json"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.6.0"
  }
}

===== orchistrator/tsconfig.json =====
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}

===== orchistrator/README.md =====
# orchistrator

Headless workflow runner that drives Claude Code step-by-step:
Plan → Implement → Test → Review → Iterate

Artifacts:
- orchistrator/runs/<run-id>/

Run:
- npm --prefix orchistrator install
- npm --prefix orchistrator run build
- node orchistrator/dist/index.js "your goal here"

===== orchistrator/src/index.ts =====
import { runWorkflow } from "./orchistrator.js";

const goal = process.argv.slice(2).join(" ").trim();
if (!goal) {
  console.error('Usage: node dist/index.js "<goal>"');
  process.exit(1);
}

runWorkflow({ goal }).catch((err) => {
  console.error(err instanceof Error ? err.stack : err);
  process.exit(1);
});

===== orchistrator/src/claude.ts =====
import { spawn } from "node:child_process";

export type RunClaudeOptions = {
  cwd: string;
  prompt: string;
  allowedTools?: string;         // e.g. "Bash,Read,Edit,Write,Glob,Grep,Task,Skill"
  outputFormat?: "text" | "json";
  jsonSchema?: unknown;
  appendSystemPrompt?: string;
  continueMostRecent?: boolean;
  resumeSessionId?: string;
};

export type ClaudeRunResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
  parsedJson?: any;
};

/**
 * Calls Claude Code headlessly via `claude -p`.
 * Supports:
 * - --allowedTools for auto-approving tools
 * - --output-format json + --json-schema for structured_output
 */
export async function runClaude(opts: RunClaudeOptions): Promise<ClaudeRunResult> {
  const args: string[] = ["-p", opts.prompt];

  const fmt = opts.outputFormat ?? "text";
  if (fmt !== "text") args.push("--output-format", fmt);

  if (opts.allowedTools) args.push("--allowedTools", opts.allowedTools);

  if (opts.jsonSchema) args.push("--json-schema", JSON.stringify(opts.jsonSchema));

  if (opts.appendSystemPrompt) args.push("--append-system-prompt", opts.appendSystemPrompt);

  if (opts.continueMostRecent) args.push("--continue");
  else if (opts.resumeSessionId) args.push("--resume", opts.resumeSessionId);

  return await new Promise((resolve) => {
    const p = spawn("claude", args, { cwd: opts.cwd, stdio: ["ignore", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";
    p.stdout.on("data", (d) => (stdout += d.toString("utf8")));
    p.stderr.on("data", (d) => (stderr += d.toString("utf8")));

    p.on("close", (code) => {
      const exitCode = code ?? 1;
      let parsedJson: any | undefined;
      if (fmt === "json") {
        try { parsedJson = JSON.parse(stdout); } catch {}
      }
      resolve({ exitCode, stdout, stderr, parsedJson });
    });
  });
}

export function extractStructuredOutput(parsedJson: any): any {
  if (!parsedJson || typeof parsedJson !== "object") return undefined;
  if ("structured_output" in parsedJson) return parsedJson.structured_output;
  return undefined;
}

===== orchistrator/src/orchistrator.ts =====
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

FINALIZE
- Actually create all directories and files above.
- chmod +x .claude/hooks/after_edit.sh
- Print a concise file tree.
- Print how to run:
  npm --prefix orchistrator install
  npm --prefix orchistrator run build
  node orchistrator/dist/index.js "your goal"
