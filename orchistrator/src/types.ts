/**
 * Type definitions for the orchestrator workflow
 */

// ============================================================================
// Plan Types
// ============================================================================

export interface Subplan {
  id: string;
  title: string;
  path: string;
}

export interface Plan {
  run_id: string;
  goal: string;
  assumptions: string[];
  subplans: Subplan[];
}

// ============================================================================
// Review Types
// ============================================================================

export interface ReviewResult {
  approved: boolean;
  blockers: string[];
  notes: string;
  next_actions: string[];
}

// ============================================================================
// Workflow State Types
// ============================================================================

export type SubplanStatus =
  | "pending"
  | "in_progress"
  | "approved"
  | "rejected"
  | "failed";

export interface SubplanAttempt {
  attemptNumber: number;
  implementOutput: string;
  testOutput: string;
  reviewResult: ReviewResult | null;
  timestamp: string;
}

export interface SubplanState {
  id: string;
  title: string;
  path: string;
  status: SubplanStatus;
  attempts: SubplanAttempt[];
  memory: string;
}

export interface WorkflowState {
  runId: string;
  goal: string;
  phase: "planning" | "executing" | "complete" | "failed";
  plan: Plan | null;
  subplanStates: Map<string, SubplanState>;
  currentSubplanId: string | null;
  startTime: string;
  endTime: string | null;
}

// ============================================================================
// Workflow Config Types
// ============================================================================

export interface WorkflowConfig {
  maxAttemptsPerSubplan: number;
  allowedToolsImplement: string;
  allowedToolsTest: string;
  allowedToolsReview: string;
  allowedToolsPlan: string;
  allowedToolsMemory: string;
}

export const DEFAULT_CONFIG: WorkflowConfig = {
  maxAttemptsPerSubplan: 5,
  allowedToolsImplement: "Read,Edit,Write,Glob,Grep,Bash,Task,Skill",
  allowedToolsTest: "Read,Edit,Write,Glob,Grep,Bash,Task,Skill",
  allowedToolsReview: "Read,Glob,Grep,Task,Skill",
  allowedToolsPlan: "Read,Write,Glob,Grep,Task,Skill",
  allowedToolsMemory: "Read",
};

// ============================================================================
// Event Types (for logging/hooks)
// ============================================================================

export type WorkflowEventType =
  | "workflow_started"
  | "workflow_completed"
  | "workflow_failed"
  | "plan_started"
  | "plan_completed"
  | "subplan_started"
  | "subplan_attempt_started"
  | "subplan_implement_completed"
  | "subplan_test_completed"
  | "subplan_review_completed"
  | "subplan_approved"
  | "subplan_rejected"
  | "subplan_failed";

export interface WorkflowEvent {
  type: WorkflowEventType;
  runId: string;
  timestamp: string;
  subplanId?: string;
  attemptNumber?: number;
  data?: Record<string, unknown>;
}

// ============================================================================
// Claude Runner Types
// ============================================================================

export interface ClaudeRunOptions {
  cwd: string;
  prompt: string;
  allowedTools?: string;
  outputFormat?: "text" | "json";
  jsonSchema?: unknown;
  appendSystemPrompt?: string;
  timeout?: number;
}

export interface ClaudeRunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  parsedJson?: unknown;
  durationMs: number;
}
