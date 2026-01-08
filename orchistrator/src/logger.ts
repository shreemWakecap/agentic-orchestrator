/**
 * Structured logging for the orchestrator workflow
 */

import fs from "node:fs/promises";
import path from "node:path";
import type { WorkflowEvent, WorkflowEventType } from "./types.js";

export type LogLevel = "debug" | "info" | "warn" | "error";

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: Record<string, unknown>;
}

export class Logger {
  private runDir: string;
  private logFile: string;
  private eventFile: string;
  private consoleEnabled: boolean;

  constructor(runDir: string, consoleEnabled = true) {
    this.runDir = runDir;
    this.logFile = path.join(runDir, "logs", "workflow.jsonl");
    this.eventFile = path.join(runDir, "logs", "events.jsonl");
    this.consoleEnabled = consoleEnabled;
  }

  async init(): Promise<void> {
    await fs.mkdir(path.join(this.runDir, "logs"), { recursive: true });
  }

  private formatConsole(level: LogLevel, message: string): string {
    const icons: Record<LogLevel, string> = {
      debug: "🔍",
      info: "ℹ️ ",
      warn: "⚠️ ",
      error: "❌",
    };
    const colors: Record<LogLevel, string> = {
      debug: "\x1b[90m",  // gray
      info: "\x1b[36m",   // cyan
      warn: "\x1b[33m",   // yellow
      error: "\x1b[31m",  // red
    };
    const reset = "\x1b[0m";
    const time = new Date().toISOString().substring(11, 19);
    return `${colors[level]}${icons[level]} [${time}] ${message}${reset}`;
  }

  private async appendToFile(filePath: string, data: unknown): Promise<void> {
    try {
      await fs.appendFile(filePath, JSON.stringify(data) + "\n", "utf8");
    } catch {
      // Ignore file write errors
    }
  }

  async log(level: LogLevel, message: string, data?: Record<string, unknown>): Promise<void> {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      data,
    };

    // Console output
    if (this.consoleEnabled) {
      console.log(this.formatConsole(level, message));
      if (data && level !== "debug") {
        console.log("   ", JSON.stringify(data, null, 2).split("\n").join("\n    "));
      }
    }

    // File output
    await this.appendToFile(this.logFile, entry);
  }

  async debug(message: string, data?: Record<string, unknown>): Promise<void> {
    await this.log("debug", message, data);
  }

  async info(message: string, data?: Record<string, unknown>): Promise<void> {
    await this.log("info", message, data);
  }

  async warn(message: string, data?: Record<string, unknown>): Promise<void> {
    await this.log("warn", message, data);
  }

  async error(message: string, data?: Record<string, unknown>): Promise<void> {
    await this.log("error", message, data);
  }

  async event(
    type: WorkflowEventType,
    runId: string,
    extra?: { subplanId?: string; attemptNumber?: number; data?: Record<string, unknown> }
  ): Promise<void> {
    const event: WorkflowEvent = {
      type,
      runId,
      timestamp: new Date().toISOString(),
      ...extra,
    };

    await this.appendToFile(this.eventFile, event);

    // Also log to console with appropriate level
    const eventMessages: Partial<Record<WorkflowEventType, { level: LogLevel; msg: string }>> = {
      workflow_started: { level: "info", msg: `Workflow started: ${runId}` },
      workflow_completed: { level: "info", msg: `Workflow completed: ${runId}` },
      workflow_failed: { level: "error", msg: `Workflow failed: ${runId}` },
      plan_started: { level: "info", msg: "Planning phase started" },
      plan_completed: { level: "info", msg: "Planning phase completed" },
      subplan_started: { level: "info", msg: `Subplan started: ${extra?.subplanId}` },
      subplan_attempt_started: { level: "info", msg: `Attempt ${extra?.attemptNumber} started` },
      subplan_approved: { level: "info", msg: `Subplan approved: ${extra?.subplanId}` },
      subplan_rejected: { level: "warn", msg: `Subplan rejected: ${extra?.subplanId}` },
      subplan_failed: { level: "error", msg: `Subplan failed: ${extra?.subplanId}` },
    };

    const logInfo = eventMessages[type];
    if (logInfo) {
      await this.log(logInfo.level, logInfo.msg, extra?.data);
    }
  }

  // Progress display helpers
  async phase(name: string): Promise<void> {
    if (this.consoleEnabled) {
      console.log(`\n${"=".repeat(60)}`);
      console.log(`  ${name.toUpperCase()}`);
      console.log(`${"=".repeat(60)}\n`);
    }
  }

  async subphase(name: string): Promise<void> {
    if (this.consoleEnabled) {
      console.log(`\n--- ${name} ---\n`);
    }
  }

  async progress(current: number, total: number, label: string): Promise<void> {
    if (this.consoleEnabled) {
      const pct = Math.round((current / total) * 100);
      const filled = Math.round(pct / 5);
      const bar = "█".repeat(filled) + "░".repeat(20 - filled);
      console.log(`[${bar}] ${pct}% - ${label}`);
    }
  }
}
