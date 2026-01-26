"""Pydantic request models for API endpoints."""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PlanRequest(BaseModel):
    """Request to create a new plan via planning workflow."""
    description: str = Field(..., min_length=1, description="Description of what to plan")


class BuildRequest(BaseModel):
    """Request to start a build workflow."""
    plan_path: str = Field(..., description="Plan ID to build (legacy name kept for compatibility)")


class MovePlanRequest(BaseModel):
    """Request to move a plan between states."""
    target_state: str = Field(..., pattern="^(pending|failed)$", description="Target state: pending or failed")


class UpdatePlanRequest(BaseModel):
    """Request to update a plan's content (only allowed when status is pending)."""
    goal: Optional[str] = Field(None, min_length=1, description="Updated goal/title for the plan")
    request: Optional[str] = Field(None, min_length=1, description="Updated request description")
    raw_content: Optional[str] = Field(None, min_length=1, description="Updated raw plan content/markdown")


class BudgetUpdateRequest(BaseModel):
    """Request to update budget settings."""
    daily_limit: Optional[float] = Field(None, ge=0, description="Daily spending limit in USD")
    weekly_limit: Optional[float] = Field(None, ge=0, description="Weekly spending limit in USD")
    monthly_limit: Optional[float] = Field(None, ge=0, description="Monthly spending limit in USD")
    per_workflow_limit: Optional[float] = Field(None, ge=0, description="Per-workflow spending limit in USD")


class ScoutingRequest(BaseModel):
    """Request to trigger knowledge scouting workflow."""
    scan_type: Optional[str] = Field(
        "quick",
        pattern="^(full|quick)$",
        description="Scan type: 'full' for comprehensive scan, 'quick' for targeted scan"
    )
    target_paths: Optional[List[str]] = Field(
        None,
        description="List of specific paths to focus scouting on"
    )
    target_keywords: Optional[List[str]] = Field(
        None,
        description="List of keywords to search for during scouting"
    )
    target_tech: Optional[List[str]] = Field(
        None,
        description="List of technologies to detect (e.g., 'fastapi', 'react', 'postgresql')"
    )
    generate_experts: Optional[bool] = Field(
        True,
        description="Whether to generate expert profiles from discovered knowledge"
    )


class PathScoutRequest(BaseModel):
    """Request to scout a single path for knowledge extraction."""
    path: str = Field(..., min_length=1, description="Path to scout for knowledge")


class KeywordScoutRequest(BaseModel):
    """Request to scout based on keywords for knowledge extraction."""
    keywords: str = Field(..., min_length=1, description="Keywords to search for during scouting")


class FileScoutRequest(BaseModel):
    """Request to scout a single file for knowledge extraction."""
    file_path: str = Field(..., min_length=1, description="Path to the file to scout for knowledge")


class SyncRemoteRequest(BaseModel):
    """Request to sync with remote repository."""
    auto_merge: Optional[bool] = Field(
        True,
        description="Whether to automatically merge after fetching (default True)"
    )


class ImproveRequestRequest(BaseModel):
    """Request to improve a draft feature request using AI."""
    draft: str = Field(..., min_length=1, max_length=5000, description="Draft request text to improve")


class ResumeBuildRequest(BaseModel):
    """Request to resume a build workflow from a specific step."""
    from_step: Optional[str] = Field(
        None,
        description="Step ID to resume from. If not provided, resumes from last incomplete step."
    )


class RecoverPlanRequest(BaseModel):
    """Request to recover a plan that failed or was interrupted during building."""
    action: str = Field(
        ...,
        pattern="^(resume|restart|cancel)$",
        description="Recovery action: 'resume' to continue from last step, 'restart' to start over, 'cancel' to abort"
    )
    from_step: Optional[str] = Field(
        None,
        description="Step ID to resume from (only used when action is 'resume'). If not provided, resumes from last incomplete step."
    )


class ForceStopRunRequest(BaseModel):
    """Request to force-stop a stuck workflow run.

    Requires explicit user confirmation to proceed with this dangerous action.
    The confirmation_text must be exactly 'I understand' to acknowledge the risks.
    """
    confirmation_text: str = Field(
        ...,
        description="Must be exactly 'I understand' to confirm the dangerous action"
    )

    @field_validator('confirmation_text')
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        """Validate that confirmation text is exactly 'I understand'."""
        if v != "I understand":
            raise ValueError("confirmation_text must be exactly 'I understand' to proceed with force-stop")
        return v


class ForceStopRunResponse(BaseModel):
    """Response after force-stopping a workflow run."""
    status: str = Field(..., description="Result status: 'stopped', 'deleted', or 'failed'")
    run_id: str = Field(..., description="ID of the run that was force-stopped")
    previous_status: str = Field(..., description="Status of the run before force-stop")
    message: str = Field(..., description="Human-readable message describing the result")


class StuckRunInfo(BaseModel):
    """Information about a single stuck workflow run."""
    run_id: str = Field(..., description="Unique identifier for the run")
    workflow: str = Field(..., description="Type of workflow: plan, build, scout, sync")
    status: str = Field(..., description="Current status: in_progress, running")
    started_at: Optional[str] = Field(None, description="ISO timestamp when run started")
    minutes_stuck: float = Field(..., description="Minutes since last activity")
    progress: int = Field(0, description="Last known progress percentage (0-100)")
    current_phase: Optional[str] = Field(None, description="Last known phase name")
    error: Optional[str] = Field(None, description="Last error message if any")
    data: Optional[dict] = Field(None, description="Additional run data/context")


class StuckRunsResponse(BaseModel):
    """Response for listing stuck workflow runs."""
    runs: List[StuckRunInfo] = Field(default_factory=list, description="List of stuck runs")
    count: int = Field(0, description="Total number of stuck runs")
    threshold_minutes: float = Field(30.0, description="Minutes threshold used to determine stuck status")


