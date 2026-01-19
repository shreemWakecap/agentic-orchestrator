"""
API Schemas - Pydantic models for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class JobTypeEnum(str, Enum):
    PLAN = "plan"
    BUILD = "build"
    REVIEW = "review"
    FIX = "fix"
    SYNC = "sync"
    DOCS = "docs"
    EXPERTS = "experts"


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMABLE = "resumable"


# ============================================================================
# Request Models
# ============================================================================

class JobCreateRequest(BaseModel):
    """Request to create a new job."""
    job_type: JobTypeEnum = Field(..., description="Type of job to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Job-specific parameters")
    priority: int = Field(default=3, ge=1, le=5, description="Priority (1=high, 5=low)")
    timeout_seconds: int = Field(default=3600, ge=60, le=86400, description="Max execution time")

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "plan",
                "parameters": {
                    "spec_id": "feat-001"
                },
                "priority": 2,
                "timeout_seconds": 3600
            }
        }


class JobCancelRequest(BaseModel):
    """Request to cancel a job."""
    reason: str = Field(default="User cancelled", description="Cancellation reason")


class JobRetryRequest(BaseModel):
    """Request to retry a failed job."""
    pass  # No additional parameters needed


class JobResumeRequest(BaseModel):
    """Request to resume a job from checkpoint."""
    checkpoint_id: str = Field(..., description="Checkpoint ID to resume from")


# ============================================================================
# Response Models
# ============================================================================

class ProgressInfo(BaseModel):
    """Progress information."""
    phase: Optional[str] = None
    percent: Optional[int] = None
    message: Optional[str] = None


class JobResponse(BaseModel):
    """Standard job response with URLs."""
    job_id: str
    job_type: JobTypeEnum
    status: JobStatusEnum
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[ProgressInfo] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    parameters: Dict[str, Any] = {}

    # Standard URLs
    status_url: str
    stream_url: str
    cancel_url: str
    logs_url: str

    # Optional relationship info
    parent_job_id: Optional[str] = None
    retry_count: int = 0

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4e5f6",
                "job_type": "plan",
                "status": "running",
                "created_at": "2025-01-19T10:30:00Z",
                "started_at": "2025-01-19T10:30:01Z",
                "progress": {
                    "phase": "analyzing",
                    "percent": 25,
                    "message": "Analyzing requirements..."
                },
                "status_url": "/api/jobs/a1b2c3d4e5f6",
                "stream_url": "/api/jobs/a1b2c3d4e5f6/stream",
                "cancel_url": "/api/jobs/a1b2c3d4e5f6/cancel",
                "logs_url": "/api/jobs/a1b2c3d4e5f6/logs"
            }
        }


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class JobSubmittedResponse(BaseModel):
    """Response after job submission (202 Accepted)."""
    job_id: str
    status: JobStatusEnum = JobStatusEnum.PENDING
    created_at: datetime
    queue_position: Optional[int] = None

    # Standard URLs
    status_url: str
    stream_url: str
    cancel_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4e5f6",
                "status": "pending",
                "created_at": "2025-01-19T10:30:00Z",
                "queue_position": 3,
                "status_url": "/api/jobs/a1b2c3d4e5f6",
                "stream_url": "/api/jobs/a1b2c3d4e5f6/stream",
                "cancel_url": "/api/jobs/a1b2c3d4e5f6/cancel"
            }
        }


class CheckpointResponse(BaseModel):
    """Checkpoint information."""
    id: str
    job_id: str
    created_at: datetime
    phase: str
    progress_percent: int


class JobCheckpointsResponse(BaseModel):
    """List of checkpoints for a job."""
    job_id: str
    checkpoints: List[CheckpointResponse]


class JobLogEntry(BaseModel):
    """Single log entry."""
    sequence: int
    timestamp: datetime
    level: str
    message: str


class JobLogsResponse(BaseModel):
    """Paginated log entries."""
    job_id: str
    logs: List[JobLogEntry]
    total_lines: int
    offset: int
    limit: int


class WorkerPoolStatus(BaseModel):
    """Worker pool status."""
    running: bool
    max_workers: int
    active_workers: int
    idle_workers: int
    queue_size: int
    total_completed: int
    total_failed: int


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
