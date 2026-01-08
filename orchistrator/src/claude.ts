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
