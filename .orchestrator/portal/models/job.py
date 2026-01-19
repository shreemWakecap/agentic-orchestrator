"""
Job-related database models.

Models:
- Job: Main job record with status, progress, and metadata
- JobEvent: Structured events emitted during job execution
- Checkpoint: Checkpoint data for job recovery
"""
import enum
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, JSON,
    Enum, ForeignKey, Index, Float
)
from sqlalchemy.orm import relationship

from .base import Base, utcnow


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"         # Created, waiting in queue
    QUEUED = "queued"           # In queue, waiting for worker
    RUNNING = "running"         # Currently executing
    SUCCEEDED = "succeeded"     # Completed successfully
    FAILED = "failed"           # Failed (may be retryable)
    CANCELLED = "cancelled"     # User cancelled
    RESUMABLE = "resumable"     # Failed but has checkpoint for resume


class JobType(str, enum.Enum):
    """Supported job types (maps to CLI commands)."""
    PLAN = "plan"
    BUILD = "build"
    REVIEW = "review"
    FIX = "fix"
    SYNC = "sync"
    DOCS = "docs"
    EXPERTS = "experts"


class Job(Base):
    """
    Main job record.

    Tracks the full lifecycle of a job from creation to completion,
    including progress updates, checkpoints, and final results.
    """
    __tablename__ = "jobs"

    # Primary key - 32 char hex string (UUID without dashes)
    id = Column(String(32), primary_key=True)

    # Job classification
    job_type = Column(Enum(JobType), nullable=False, index=True)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utcnow)
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Execution details
    pid = Column(Integer, nullable=True)  # OS process ID when running
    exit_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Progress tracking (updated from JSONL events)
    progress_phase = Column(String(100), nullable=True)
    progress_percent = Column(Integer, nullable=True, default=0)
    progress_message = Column(Text, nullable=True)

    # Configuration
    parameters = Column(JSON, nullable=False, default=dict)
    timeout_seconds = Column(Integer, nullable=False, default=3600)  # 1 hour default

    # Queue management
    priority = Column(Integer, nullable=False, default=3)  # 1=high, 5=low
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Relationships and ownership
    user_id = Column(String(100), nullable=True, index=True)
    parent_job_id = Column(String(32), ForeignKey("jobs.id"), nullable=True)
    last_checkpoint_id = Column(String(50), nullable=True)

    # Result data (for completed jobs)
    result_data = Column(JSON, nullable=True)

    # Relationships
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="job", cascade="all, delete-orphan")
    child_jobs = relationship("Job", backref="parent_job", remote_side=[id])

    # Indices for common queries
    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_user_status", "user_id", "status"),
        Index("ix_jobs_type_status", "job_type", "status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "job_id": self.id,
            "job_type": self.job_type.value if self.job_type else None,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": {
                "phase": self.progress_phase,
                "percent": self.progress_percent,
                "message": self.progress_message,
            } if self.progress_phase else None,
            "exit_code": self.exit_code,
            "error": self.error_message,
            "parameters": self.parameters,
            "retry_count": self.retry_count,
            "parent_job_id": self.parent_job_id,
        }


class JobEvent(Base):
    """
    Structured event emitted during job execution.

    Events are parsed from CLI JSONL output and stored for:
    - Real-time streaming via SSE
    - Historical log viewing
    - Debugging and audit
    """
    __tablename__ = "job_events"

    # Auto-incrementing ID for global ordering
    # Note: Using Integer instead of BigInteger for SQLite compatibility
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Job reference
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)

    # Event ordering within job
    sequence = Column(Integer, nullable=False)

    # Event classification
    event_type = Column(String(50), nullable=False, index=True)
    # Types: start, progress, log, checkpoint, error, complete, cancelled

    # Timestamp from event (may differ from insertion time)
    timestamp = Column(DateTime, nullable=False, default=utcnow)

    # Event payload (structure depends on event_type)
    data = Column(JSON, nullable=False, default=dict)

    # For log events
    log_level = Column(String(20), nullable=True)  # debug, info, warn, error

    # Relationship
    job = relationship("Job", back_populates="events")

    # Composite index for efficient streaming queries
    __table_args__ = (
        Index("ix_job_events_job_seq", "job_id", "sequence"),
        Index("ix_job_events_job_type", "job_id", "event_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for SSE/API responses."""
        return {
            "id": self.id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "data": self.data,
            "log_level": self.log_level,
        }


class Checkpoint(Base):
    """
    Checkpoint data for job recovery.

    Checkpoints allow resuming failed jobs from a known good state
    rather than starting from scratch.
    """
    __tablename__ = "checkpoints"

    # Checkpoint ID (generated by CLI)
    id = Column(String(50), primary_key=True)

    # Job reference
    job_id = Column(String(32), ForeignKey("jobs.id"), nullable=False, index=True)

    # When checkpoint was created
    created_at = Column(DateTime, nullable=False, default=utcnow)

    # Progress at checkpoint time
    phase = Column(String(100), nullable=False)
    progress_percent = Column(Integer, nullable=False)

    # CLI-specific state data for resume
    # This is opaque to the portal - CLI knows how to interpret it
    state_data = Column(JSON, nullable=False, default=dict)

    # Relationship
    job = relationship("Job", back_populates="checkpoints")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "phase": self.phase,
            "progress_percent": self.progress_percent,
        }


class QueueMetrics(Base):
    """
    Track queue performance metrics over time.
    Used for monitoring and capacity planning.
    """
    __tablename__ = "queue_metrics"

    # Note: Using Integer instead of BigInteger for SQLite compatibility
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=utcnow, index=True)

    # Queue state
    queue_depth = Column(Integer, nullable=False, default=0)
    active_workers = Column(Integer, nullable=False, default=0)

    # Throughput
    jobs_completed_last_minute = Column(Integer, nullable=False, default=0)
    jobs_failed_last_minute = Column(Integer, nullable=False, default=0)

    # Latency
    avg_wait_time_seconds = Column(Float, nullable=True)
    avg_execution_time_seconds = Column(Float, nullable=True)
