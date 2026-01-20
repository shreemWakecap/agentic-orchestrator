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


# ==================== Codebase Exploration Schemas ====================

class ExploreCodebaseRequest(BaseModel):
    """Request to explore and understand the codebase."""
    query: str = Field(..., min_length=1, max_length=2000, description="The exploration query/question about the codebase")
    scope: Optional[str] = Field(
        "all",
        pattern="^(architecture|files|patterns|dependencies|all)$",
        description="Exploration scope: 'architecture' for system design, 'files' for file-level analysis, 'patterns' for code patterns, 'dependencies' for dependency analysis, 'all' for comprehensive exploration"
    )
    include_snippets: Optional[bool] = Field(
        True,
        description="Whether to include code snippets in the response"
    )
    max_results: Optional[int] = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of results to return (1-50)"
    )


class CodeSnippet(BaseModel):
    """A code snippet extracted from the codebase."""
    file_path: str = Field(..., description="Path to the source file")
    start_line: int = Field(..., description="Starting line number of the snippet")
    end_line: int = Field(..., description="Ending line number of the snippet")
    content: str = Field(..., description="The code snippet content")
    language: Optional[str] = Field(None, description="Programming language of the snippet")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance score (0.0 to 1.0)")


class FileReference(BaseModel):
    """A reference to a file in the codebase."""
    file_path: str = Field(..., description="Path to the file")
    description: str = Field(..., description="Brief description of the file's purpose or relevance")
    file_type: Optional[str] = Field(None, description="Type of file (e.g., 'module', 'config', 'test')")
    relevance: Optional[str] = Field(None, description="Why this file is relevant to the query")


class RelatedTopic(BaseModel):
    """A related topic for further exploration."""
    topic: str = Field(..., description="The related topic or concept")
    description: str = Field(..., description="Brief description of the topic")
    suggested_query: Optional[str] = Field(None, description="Suggested query to explore this topic")


class ExplorationResultResponse(BaseModel):
    """Response model for codebase exploration results."""
    id: str = Field(..., description="Unique exploration result identifier")
    query: str = Field(..., description="The original exploration query")
    scope: str = Field(..., description="The scope used for exploration")
    explanation: str = Field(..., description="Detailed explanation answering the query")
    file_references: List[FileReference] = Field(default_factory=list, description="Relevant files in the codebase")
    code_snippets: List[CodeSnippet] = Field(default_factory=list, description="Relevant code snippets")
    related_topics: List[RelatedTopic] = Field(default_factory=list, description="Related topics for further exploration")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score for the exploration result")
    sources_used: List[str] = Field(default_factory=list, description="Knowledge sources used to generate the response")
    created_at: str = Field(..., description="ISO timestamp when exploration was performed")

    class Config:
        from_attributes = True


class ExplorationHistoryResponse(BaseModel):
    """Response model for a single exploration history entry (summary view)."""
    id: str = Field(..., description="Unique exploration identifier")
    query: str = Field(..., description="The exploration query")
    scope: str = Field(..., description="The scope used for exploration")
    file_count: int = Field(0, description="Number of files referenced")
    snippet_count: int = Field(0, description="Number of code snippets included")
    created_at: str = Field(..., description="ISO timestamp when exploration was performed")

    class Config:
        from_attributes = True


class ExplorationListResponse(BaseModel):
    """Response model for listing exploration history with pagination."""
    explorations: List[ExplorationHistoryResponse] = Field(default_factory=list, description="List of exploration results")
    total: int = Field(0, description="Total number of explorations matching filters")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")
    has_more: bool = Field(False, description="Whether there are more pages available")
