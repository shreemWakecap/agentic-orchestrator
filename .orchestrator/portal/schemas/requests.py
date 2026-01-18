"""Pydantic request models for API endpoints."""
from typing import List, Optional
from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    """Request to create a new plan via planning workflow."""
    description: str = Field(..., min_length=1, description="Description of what to plan")


class BuildRequest(BaseModel):
    """Request to start a build workflow."""
    plan_path: str = Field(..., description="Plan ID to build (legacy name kept for compatibility)")


class MovePlanRequest(BaseModel):
    """Request to move a plan between states."""
    target_state: str = Field(..., pattern="^(pending|failed)$", description="Target state: pending or failed")


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


class SyncRemoteRequest(BaseModel):
    """Request to sync with remote repository."""
    auto_merge: Optional[bool] = Field(
        True,
        description="Whether to automatically merge after fetching (default True)"
    )
