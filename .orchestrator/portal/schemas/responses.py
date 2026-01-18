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

    class Config:
        from_attributes = True


class PlanDetailResponse(PlanResponse):
    """Detailed plan information including content."""
    content: Optional[str] = None
    complexity: Optional[str] = None


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
