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


class CreateQuestionRequest(BaseModel):
    """Request to create a new question."""
    question: str = Field(..., min_length=1, max_length=2000, description="The question text to ask")
    source_preference: Optional[str] = Field(
        "auto",
        pattern="^(knowledge_base|code_exploration|auto)$",
        description="Preferred source for answer: 'knowledge_base' for scouting results, 'code_exploration' for codebase analysis, 'auto' for automatic selection"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Optional tags for categorizing the question"
    )


class UpdateQuestionRequest(BaseModel):
    """Request to update an existing question."""
    question: Optional[str] = Field(None, min_length=1, max_length=2000, description="Updated question text")
    status: Optional[str] = Field(
        None,
        pattern="^(pending|answered|archived)$",
        description="Question status: 'pending', 'answered', or 'archived'"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated tags for the question"
    )


class CreateAnswerRequest(BaseModel):
    """Request to create an answer for a question."""
    content: str = Field(..., min_length=1, max_length=10000, description="The answer content")
    source: str = Field(
        ...,
        pattern="^(knowledge_base|code_exploration|manual)$",
        description="Answer source: 'knowledge_base', 'code_exploration', or 'manual'"
    )
    source_references: Optional[List[str]] = Field(
        None,
        description="References to source files or knowledge entries used for the answer"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for the answer (0.0 to 1.0)"
    )


class UpdateAnswerRequest(BaseModel):
    """Request to update an existing answer."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000, description="Updated answer content")
    is_obsolete: Optional[bool] = Field(None, description="Mark the answer as obsolete/outdated")
    obsolete_reason: Optional[str] = Field(None, max_length=500, description="Reason why the answer is marked obsolete")


class AnswerResponse(BaseModel):
    """Response model for a single answer."""
    id: str = Field(..., description="Unique answer identifier")
    question_id: str = Field(..., description="ID of the parent question")
    content: str = Field(..., description="The answer content")
    source: str = Field(..., description="Answer source: 'knowledge_base', 'code_exploration', or 'manual'")
    source_references: List[str] = Field(default_factory=list, description="References to source files or knowledge entries")
    confidence: Optional[float] = Field(None, description="Confidence score for the answer (0.0 to 1.0)")
    is_obsolete: bool = Field(False, description="Whether the answer is marked as obsolete")
    obsolete_reason: Optional[str] = Field(None, description="Reason why the answer is obsolete")
    created_at: str = Field(..., description="ISO timestamp when answer was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when answer was last updated")

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    """Response model for a single question (summary view)."""
    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text")
    status: str = Field(..., description="Question status: 'pending', 'answered', or 'archived'")
    source_preference: str = Field("auto", description="Preferred source for answer")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the question")
    answer_count: int = Field(0, description="Number of answers for this question")
    created_at: str = Field(..., description="ISO timestamp when question was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when question was last updated")

    class Config:
        from_attributes = True


class QuestionDetailResponse(BaseModel):
    """Response model for a single question with full details including answers."""
    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text")
    status: str = Field(..., description="Question status: 'pending', 'answered', or 'archived'")
    source_preference: str = Field("auto", description="Preferred source for answer")
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the question")
    answers: List[AnswerResponse] = Field(default_factory=list, description="List of answers for this question")
    created_at: str = Field(..., description="ISO timestamp when question was created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when question was last updated")

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    """Response model for listing questions with pagination."""
    questions: List[QuestionResponse] = Field(default_factory=list, description="List of questions")
    total: int = Field(0, description="Total number of questions matching filters")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")
    has_more: bool = Field(False, description="Whether there are more pages available")
