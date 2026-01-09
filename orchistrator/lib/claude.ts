/**
 * Claude CLI Wrapper
 * Spawns `claude -p` and streams output to console
 */

export interface ClaudeOptions {
  prompt: string;
  allowedTools?: string[];
  jsonSchema?: object;
  cwd?: string;
  timeout?: number;
}

export interface ClaudeResult {
  exitCode: number;
  output: string;
  json?: unknown;
}

/**
 * Run Claude in headless mode with streaming output
 */
export async function runClaude(options: ClaudeOptions): Promise<ClaudeResult> {
  const args: string[] = ['-p', options.prompt];

  // Add allowed tools for auto-approval
  if (options.allowedTools?.length) {
    args.push('--allowedTools', options.allowedTools.join(','));
  }

  // Add JSON schema for structured output
  if (options.jsonSchema) {
    args.push('--output-format', 'json');
    args.push('--json-schema', JSON.stringify(options.jsonSchema));
  }

  const proc = Bun.spawn(['claude', ...args], {
    cwd: options.cwd ?? process.cwd(),
    stdout: 'pipe',
    stderr: 'pipe',
  });

  // Stream stdout to console and capture
  let output = '';
  const decoder = new TextDecoder();

  // Read stdout stream
  const reader = proc.stdout.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    output += chunk;
    process.stdout.write(chunk); // Stream to console
  }

  // Wait for process to exit
  const exitCode = await proc.exited;

  // Capture stderr if any
  const stderrReader = proc.stderr.getReader();
  let stderr = '';
  while (true) {
    const { done, value } = await stderrReader.read();
    if (done) break;
    stderr += decoder.decode(value);
  }

  if (stderr) {
    console.error(stderr);
  }

  // Parse JSON if schema was provided
  let json: unknown;
  if (options.jsonSchema && output) {
    try {
      // Try to extract JSON from output
      const jsonMatch = output.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        json = JSON.parse(jsonMatch[0]);
      }
    } catch {
      // JSON parsing failed, leave undefined
    }
  }

  return { exitCode, output, json };
}
