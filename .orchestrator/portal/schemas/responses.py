"""Pydantic response models for API endpoints."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    """Basic plan information for list views."""
    id: str
    name: str
    state: str
    modified: str
    request: Optional[str] = None
    goal: Optional[str] = None
    files: List[str] = Field(default_factory=list)
    is_stuck: bool = Field(False, description="Whether the plan is stuck in building/in-progress state")
    last_update: Optional[str] = Field(None, description="Last update timestamp from build state")
    recovery_options: List[str] = Field(default_factory=list, description="Available recovery actions: reset, resume, retry_step, skip_step")

    class Config:
        from_attributes = True


class PlanCostEstimate(BaseModel):
    """Cost estimation for a plan."""
    estimated_tokens: int = Field(0, description="Estimated total tokens for implementation")
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")
    planning_tokens: Optional[int] = Field(None, description="Actual tokens used during planning")
    planning_cost_usd: Optional[float] = Field(None, description="Actual planning cost in USD")
    implementation_tokens: Optional[int] = Field(None, description="Actual tokens used during implementation")
    implementation_cost_usd: Optional[float] = Field(None, description="Actual implementation cost in USD")
    confidence: str = Field("medium", description="Estimate confidence: high, medium, low")
    breakdown: Optional[Dict[str, Any]] = Field(None, description="Cost breakdown by agent/phase")


class PlanDetailResponse(PlanResponse):
    """Detailed plan information including content."""
    content: Optional[str] = None
    complexity: Optional[str] = None
    cost_estimate: Optional[PlanCostEstimate] = Field(None, description="Token cost estimate for this plan")
    estimated_implementation_cost: Optional[float] = Field(None, description="Estimated token cost in USD for implementing this plan")
    actual_planning_cost: Optional[float] = Field(None, description="Actual token cost in USD consumed during the planning process")


class PlanListResponse(BaseModel):
    """Response for plan list endpoint."""
    plans: List[PlanResponse]


class PlanFileResponse(BaseModel):
    """Response for plan file content."""
    plan_id: str
    filename: str
    content: str
    state: str


class PlanStateResponse(BaseModel):
    """Response for plan state/build-state endpoints."""
    plan_id: str
    status: str
    folder_state: str
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    current_phase: int = 0
    current_step: Optional[str] = None
    total_steps: int = 0
    completed_steps: List[str] = Field(default_factory=list)
    failed_steps: List[str] = Field(default_factory=list)
    step_states: Dict[str, Any] = Field(default_factory=dict)
    files_created: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    last_error: Optional[str] = None
    # Recovery-related fields
    is_stuck: bool = Field(False, description="Whether the plan is stuck in building/in-progress state")
    minutes_since_update: Optional[float] = Field(None, description="Minutes since last update")
    can_resume: bool = Field(False, description="Whether the plan can be resumed from current state")
    can_cancel: bool = Field(False, description="Whether the plan can be cancelled")
    recovery_options: List[str] = Field(default_factory=list, description="Available recovery actions: reset, resume, retry_step, cancel")


class BuildStateResponse(PlanStateResponse):
    """Extended build state with progress percentage."""
    progress_percentage: float = 0.0


class RunResponse(BaseModel):
    """Run information."""
    run_id: str
    workflow: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    # Phase tracking fields for real-time visibility
    current_phase_name: Optional[str] = Field(None, description="Name of the current execution phase")
    phase_progress: int = Field(0, description="Progress within current phase (0-100)")
    phases_total: int = Field(0, description="Total number of phases in the workflow")
    activity_log: List[Dict[str, Any]] = Field(default_factory=list, description="Recent activity log entries with timestamps")

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """Response for runs list endpoint."""
    runs: List[RunResponse]
    counts: Dict[str, int]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float


class WorkflowStartResponse(BaseModel):
    """Response when starting a workflow."""
    run_id: str
    status: str = "started"
    plan_id: Optional[str] = None


class CostEstimateResponse(BaseModel):
    """Cost estimation response."""
    workflow: str
    estimated_tokens: int
    estimated_cost_usd: float
    breakdown: Optional[Dict[str, Any]] = None


class CostSummaryResponse(BaseModel):
    """Cost summary for dashboard."""
    daily: Dict[str, Any]
    weekly: Dict[str, Any]
    monthly: Dict[str, Any]
    budget: Dict[str, Any]


class BudgetResponse(BaseModel):
    """Budget status response."""
    daily_limit: Optional[float] = None
    weekly_limit: Optional[float] = None
    monthly_limit: Optional[float] = None
    per_workflow_limit: Optional[float] = None
    daily_used: float = 0.0
    weekly_used: float = 0.0
    monthly_used: float = 0.0


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    status: str = "deleted"
    plan_id: str
    previous_state: str


class MoveResponse(BaseModel):
    """Response for move operations."""
    status: str
    plan_id: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    message: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response for sync to remote status information."""
    file_count: int
    files: List[str] = Field(default_factory=list)
    branch: str
    has_changes: bool
    diff_summary: str
    staged_count: int
    unstaged_count: int


class GitStatisticsResponse(BaseModel):
    """Response for git repository statistics."""
    commits_ahead: int = 0
    commits_behind: int = 0
    current_branch: str
    remote_branch: Optional[str] = None
    pr_status: str = "none"  # "open", "merged", "none"
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    last_commit_hash: Optional[str] = None
    last_commit_message: Optional[str] = None


class ImproveRequestResponse(BaseModel):
    """Response for AI request improvement."""
    improved: str = Field(..., description="The AI-improved request text")
    original: str = Field(..., description="The original draft text")
    success: bool = Field(True, description="Whether improvement succeeded")


class ImproveRequestTaskResponse(BaseModel):
    """Response when starting an improve request task asynchronously."""
    task_id: str = Field(..., description="Unique identifier for the background task")
    status: str = Field("started", description="Task status: started, pending, running")
    message: str = Field("Improve request task started", description="Human-readable status message")


class BackgroundTaskResponse(BaseModel):
    """Response for a single background task."""
    task_id: str = Field(..., description="Unique identifier for the task")
    status: str = Field(..., description="Current status: pending, running, completed, failed, cancelled")
    task_type: str = Field(..., description="Type of task: plan, build, sync, etc.")
    started_at: Optional[str] = Field(None, description="ISO timestamp when task started")
    progress: float = Field(0.0, description="Progress percentage (0.0 to 100.0)")

    class Config:
        from_attributes = True


class BackgroundTaskListResponse(BaseModel):
    """Response for listing background tasks."""
    tasks: List[BackgroundTaskResponse] = Field(default_factory=list)
    count: int = Field(0, description="Total number of tasks")


class TaskStatusResponse(BaseModel):
    """Detailed status response for a background task."""
    task_id: str = Field(..., description="Unique identifier for the task")
    status: str = Field(..., description="Current status: pending, running, completed, failed, cancelled")
    task_type: str = Field(..., description="Type of task: plan, build, sync, etc.")
    started_at: Optional[str] = Field(None, description="ISO timestamp when task started")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when task completed")
    progress: float = Field(0.0, description="Progress percentage (0.0 to 100.0)")
    current_step: Optional[str] = Field(None, description="Description of current step being executed")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data on success")
    error: Optional[str] = Field(None, description="Error message on failure")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")

    class Config:
        from_attributes = True


class RecoveryAction(BaseModel):
    """A single recovery action that can be taken."""
    action: str = Field(..., description="Action identifier: reset, resume, retry_step, skip_step")
    label: str = Field(..., description="Human-readable action label")
    description: str = Field(..., description="Description of what the action does")
    available: bool = Field(True, description="Whether this action is currently available")
    endpoint: str = Field(..., description="API endpoint to call for this action")
    method: str = Field("POST", description="HTTP method to use")


class RecoveryOptionsResponse(BaseModel):
    """Response for plan recovery options."""
    plan_id: str
    current_status: str
    can_recover: bool = Field(..., description="Whether any recovery action is available")
    actions: List[RecoveryAction] = Field(default_factory=list)
    last_error: Optional[str] = None
    failed_step: Optional[str] = None
    completed_steps_count: int = 0
    total_steps_count: int = 0


class ResetBuildResponse(BaseModel):
    """Response for build reset operation."""
    status: str = "reset"
    plan_id: str
    previous_status: str
    new_status: str = "pending"
    steps_cleared: int = 0
    message: str = "Build state reset successfully"


class StuckPlanInfo(BaseModel):
    """Information about a single stuck/recoverable plan."""
    plan_id: str = Field(..., description="Unique identifier for the plan")
    status: str = Field(..., description="Current status: building, in-progress, failed")
    minutes_stale: float = Field(..., description="Minutes since last update")
    progress_percent: float = Field(0.0, description="Build progress percentage (0.0 to 100.0)")
    last_error: Optional[str] = Field(None, description="Last error message if any")
    current_step: Optional[str] = Field(None, description="Current/last step being executed")
    can_resume: bool = Field(True, description="Whether the plan can be resumed")


class StuckPlansResponse(BaseModel):
    """Response for listing stuck/recoverable plans."""
    plans: List[StuckPlanInfo] = Field(default_factory=list, description="List of stuck plans")
    count: int = Field(0, description="Total number of stuck plans")


class RecoverPlanRequest(BaseModel):
    """Request schema for recovering a stuck plan."""
    action: str = Field(..., description="Recovery action: reset, resume, retry_step, skip_step, cancel")


class CancelBuildResponse(BaseModel):
    """Response for cancelling a build operation."""
    status: str = "cancelled"
    plan_id: str
    previous_status: str
    message: str = "Build cancelled successfully"
    steps_completed: int = 0
    steps_remaining: int = 0


class StuckRunInfo(BaseModel):
    """Information about a single stuck workflow run."""
    run_id: str = Field(..., description="Unique identifier for the run")
    workflow: str = Field(..., description="Workflow type: plan, build, sync, etc.")
    status: str = Field(..., description="Current status: in_progress, running")
    started_at: Optional[str] = Field(None, description="ISO timestamp when run started")
    minutes_stuck: float = Field(..., description="Minutes since last activity")


class StuckRunsResponse(BaseModel):
    """Response for listing stuck workflow runs."""
    runs: List[StuckRunInfo] = Field(default_factory=list, description="List of stuck runs")
    count: int = Field(0, description="Total number of stuck runs")


class ForceStopRunResponse(BaseModel):
    """Response for force-stopping a stuck workflow run."""
    status: str = Field(..., description="Operation status: stopped, deleted, error")
    run_id: str = Field(..., description="ID of the run that was force-stopped")
    previous_status: str = Field(..., description="Status before force-stop")
    new_status: str = Field(..., description="Status after force-stop: force_stopped, deleted")
    message: str = Field(..., description="Human-readable result message")


class UpdatePlanResponse(BaseModel):
    """Response for plan update operation."""
    status: str = "updated"
    plan_id: str
    updated_fields: List[str] = Field(default_factory=list, description="List of fields that were updated")
    message: str = "Plan updated successfully"


# Token Usage Analytics Models

class TokenUsageRecord(BaseModel):
    """Individual token usage record for a run or plan."""
    id: str = Field(..., description="Unique identifier for this usage record")
    plan_id: Optional[str] = Field(None, description="Associated plan ID if applicable")
    run_id: Optional[str] = Field(None, description="Associated run ID if applicable")
    event_type: str = Field(..., description="Type of event: plan_estimate, run_execution, etc.")
    timestamp: str = Field(..., description="ISO timestamp when usage was recorded")
    input_tokens: int = Field(0, description="Number of input tokens consumed")
    output_tokens: int = Field(0, description="Number of output tokens consumed")
    total_tokens: int = Field(0, description="Total tokens (input + output)")
    cost_usd: float = Field(0.0, description="Cost in USD for this usage")
    model: Optional[str] = Field(None, description="Model used for this operation")
    agent_type: Optional[str] = Field(None, description="Agent type: planner, builder, scout, etc.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        from_attributes = True


class TokenUsageSummary(BaseModel):
    """Aggregated token usage summary for a time period."""
    period_start: str = Field(..., description="ISO timestamp for period start")
    period_end: str = Field(..., description="ISO timestamp for period end")
    total_input_tokens: int = Field(0, description="Total input tokens in period")
    total_output_tokens: int = Field(0, description="Total output tokens in period")
    total_tokens: int = Field(0, description="Total tokens in period")
    total_cost_usd: float = Field(0.0, description="Total cost in USD for period")
    run_count: int = Field(0, description="Number of runs in period")
    plan_count: int = Field(0, description="Number of plans estimated in period")
    average_tokens_per_run: float = Field(0.0, description="Average tokens per run")
    average_cost_per_run: float = Field(0.0, description="Average cost per run in USD")
    by_agent_type: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Usage breakdown by agent type")
    by_model: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Usage breakdown by model")


class TokenComparison(BaseModel):
    """Comparison between estimated and actual token usage."""
    plan_id: str = Field(..., description="Plan ID for comparison")
    plan_name: Optional[str] = Field(None, description="Plan name for display")
    estimated_tokens: int = Field(0, description="Estimated tokens during planning")
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")
    actual_tokens: int = Field(0, description="Actual tokens consumed")
    actual_cost_usd: float = Field(0.0, description="Actual cost in USD")
    token_variance: int = Field(0, description="Difference: actual - estimated")
    cost_variance: float = Field(0.0, description="Cost difference in USD")
    variance_percentage: float = Field(0.0, description="Variance as percentage of estimate")
    accuracy_rating: str = Field("unknown", description="Accuracy: accurate, over_estimated, under_estimated")
    completed_at: Optional[str] = Field(None, description="When the plan was completed")


class ErrorRateMetrics(BaseModel):
    """Error rate calculations for token usage tracking."""
    period_start: str = Field(..., description="ISO timestamp for period start")
    period_end: str = Field(..., description="ISO timestamp for period end")
    total_runs: int = Field(0, description="Total number of runs")
    successful_runs: int = Field(0, description="Number of successful runs")
    failed_runs: int = Field(0, description="Number of failed runs")
    error_rate: float = Field(0.0, description="Error rate as decimal (0.0 to 1.0)")
    error_rate_percentage: float = Field(0.0, description="Error rate as percentage")
    tokens_wasted_on_failures: int = Field(0, description="Tokens consumed by failed runs")
    cost_wasted_on_failures: float = Field(0.0, description="Cost in USD wasted on failures")
    errors_by_type: Dict[str, int] = Field(default_factory=dict, description="Error count by error type")
    errors_by_agent: Dict[str, int] = Field(default_factory=dict, description="Error count by agent type")


class TokenTrendData(BaseModel):
    """Time-series trend data for token usage charts."""
    timestamp: str = Field(..., description="ISO timestamp for this data point")
    period_label: str = Field(..., description="Human-readable period label (e.g., 'Jan 15', 'Week 3')")
    total_tokens: int = Field(0, description="Total tokens for this period")
    total_cost_usd: float = Field(0.0, description="Total cost for this period")
    run_count: int = Field(0, description="Number of runs in this period")
    error_count: int = Field(0, description="Number of errors in this period")
    average_tokens_per_run: float = Field(0.0, description="Average tokens per run")


class TokenAnalyticsResponse(BaseModel):
    """Comprehensive token analytics response for dashboard."""
    summary: TokenUsageSummary = Field(..., description="Aggregated usage summary")
    trends: List[TokenTrendData] = Field(default_factory=list, description="Time-series trend data")
    comparisons: List[TokenComparison] = Field(default_factory=list, description="Estimated vs actual comparisons")
    error_metrics: ErrorRateMetrics = Field(..., description="Error rate metrics")
    recent_records: List[TokenUsageRecord] = Field(default_factory=list, description="Recent usage records")
    date_range: Dict[str, str] = Field(default_factory=dict, description="Applied date range filter")


# =============================================================================
# Task Tracking Models (for Claude Task tool integration)
# =============================================================================

class TaskNode(BaseModel):
    """A single task node in the dependency graph."""
    id: str = Field(..., description="Task ID (same as step_id)")
    subject: str = Field(..., description="Task subject/title")
    status: str = Field("pending", description="Task status: pending, in_progress, completed, failed")
    step_id: str = Field(..., description="Associated plan step ID")
    active_form: Optional[str] = Field(None, description="Present continuous form for spinner display")
    description: Optional[str] = Field(None, description="Full task description")
    session_task_id: Optional[str] = Field(None, description="Claude Task ID in current session")


class TaskEdge(BaseModel):
    """An edge representing a dependency between tasks."""
    from_task: str = Field(..., description="Source task ID (the blocking task)")
    to_task: str = Field(..., description="Target task ID (the blocked task)")
    relation: str = Field("blocks", description="Relation type: blocks, blockedBy")


class TaskStatusCounts(BaseModel):
    """Counts of tasks by status."""
    total: int = Field(0, description="Total number of tasks")
    pending: int = Field(0, description="Number of pending tasks")
    in_progress: int = Field(0, description="Number of in-progress tasks")
    completed: int = Field(0, description="Number of completed tasks")
    failed: int = Field(0, description="Number of failed tasks")
    blocked: int = Field(0, description="Number of tasks blocked by incomplete dependencies")


class PlanTaskStatusResponse(BaseModel):
    """Real-time task execution status for a plan with dependency information."""
    plan_id: str = Field(..., description="Plan ID")
    session_id: Optional[str] = Field(None, description="Current execution session ID")
    status_counts: TaskStatusCounts = Field(..., description="Task counts by status")
    current_task: Optional[str] = Field(None, description="Currently executing task ID")
    next_ready: List[str] = Field(default_factory=list, description="Tasks ready to execute (no blockers)")
    critical_path: List[str] = Field(default_factory=list, description="Longest dependency chain")
    tasks: List[TaskNode] = Field(default_factory=list, description="All tasks with their status")
    last_updated: Optional[str] = Field(None, description="ISO timestamp of last status update")


class TaskGraphResponse(BaseModel):
    """Task dependency graph for visualization (DAG format)."""
    plan_id: str = Field(..., description="Plan ID")
    nodes: List[TaskNode] = Field(default_factory=list, description="Task nodes")
    edges: List[TaskEdge] = Field(default_factory=list, description="Dependency edges (blockedBy relationships)")
    waves: List[List[str]] = Field(default_factory=list, description="Tasks grouped by execution wave/depth")
    root_tasks: List[str] = Field(default_factory=list, description="Tasks with no dependencies (wave 0)")