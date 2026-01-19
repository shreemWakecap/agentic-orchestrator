"""
Job Service - Core business logic for job management.

Provides high-level operations for creating, querying, and managing jobs.
All database operations go through this service.
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Job, JobEvent, Checkpoint, QueueMetrics,
    JobStatus, JobType, utcnow
)

logger = logging.getLogger(__name__)


class JobServiceError(Exception):
    """Base exception for job service errors."""
    pass


class JobNotFoundError(JobServiceError):
    """Job not found."""
    pass


class InvalidJobStateError(JobServiceError):
    """Invalid job state transition."""
    pass


class JobService:
    """
    Service class for job management operations.

    Usage:
        async with async_session_maker() as session:
            service = JobService(session)
            job = await service.create_job(...)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Job Creation
    # =========================================================================

    async def create_job(
        self,
        job_type: JobType,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
        priority: int = 3,
        timeout_seconds: int = 3600,
        parent_job_id: Optional[str] = None,
    ) -> Job:
        """
        Create a new job.

        Args:
            job_type: Type of job (plan, build, etc.)
            parameters: Job-specific parameters
            user_id: Owner of the job (for filtering/authz)
            priority: Queue priority (1=high, 5=low)
            timeout_seconds: Maximum execution time
            parent_job_id: If this is a retry/resume of another job

        Returns:
            Created Job instance
        """
        job_id = uuid.uuid4().hex

        job = Job(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            parameters=parameters,
            user_id=user_id,
            priority=priority,
            timeout_seconds=timeout_seconds,
            parent_job_id=parent_job_id,
            created_at=utcnow(),
        )

        self.session.add(job)
        await self.session.flush()

        logger.info(f"Created job {job_id} of type {job_type.value}")
        return job

    # =========================================================================
    # Job Queries
    # =========================================================================

    async def get_job(
        self,
        job_id: str,
        include_events: bool = False,
        include_checkpoints: bool = False,
    ) -> Optional[Job]:
        """
        Get a job by ID.

        Args:
            job_id: Job identifier
            include_events: Load related events
            include_checkpoints: Load related checkpoints

        Returns:
            Job instance or None if not found
        """
        query = select(Job).where(Job.id == job_id)

        if include_events:
            query = query.options(selectinload(Job.events))
        if include_checkpoints:
            query = query.options(selectinload(Job.checkpoints))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_job_or_raise(self, job_id: str, **kwargs) -> Job:
        """Get job by ID or raise JobNotFoundError."""
        job = await self.get_job(job_id, **kwargs)
        if not job:
            raise JobNotFoundError(f"Job {job_id} not found")
        return job

    async def list_jobs(
        self,
        user_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        statuses: Optional[List[JobStatus]] = None,
        job_type: Optional[JobType] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Job], int]:
        """
        List jobs with filtering and pagination.

        Args:
            user_id: Filter by owner
            status: Filter by single status
            statuses: Filter by multiple statuses
            job_type: Filter by job type
            since: Created after this time
            until: Created before this time
            limit: Max results
            offset: Pagination offset
            order_by: Field to order by
            order_desc: Descending order

        Returns:
            Tuple of (jobs list, total count)
        """
        # Build filter conditions
        conditions = []

        if user_id:
            conditions.append(Job.user_id == user_id)
        if status:
            conditions.append(Job.status == status)
        if statuses:
            conditions.append(Job.status.in_(statuses))
        if job_type:
            conditions.append(Job.job_type == job_type)
        if since:
            conditions.append(Job.created_at >= since)
        if until:
            conditions.append(Job.created_at <= until)

        # Count query
        count_query = select(func.count(Job.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Data query
        query = select(Job)
        if conditions:
            query = query.where(and_(*conditions))

        # Ordering
        order_column = getattr(Job, order_by, Job.created_at)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Pagination
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        jobs = list(result.scalars().all())

        return jobs, total

    async def get_active_jobs(self) -> List[Job]:
        """Get all jobs that are currently running or queued."""
        result = await self.session.execute(
            select(Job).where(
                Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING])
            )
        )
        return list(result.scalars().all())

    async def get_queued_jobs(self, limit: int = 10) -> List[Job]:
        """Get pending jobs ordered by priority and creation time."""
        result = await self.session.execute(
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Job Status Updates
    # =========================================================================

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        exit_code: Optional[int] = None,
        result_data: Optional[Dict] = None,
    ) -> Job:
        """
        Update job status with optional completion data.

        Args:
            job_id: Job identifier
            status: New status
            error_message: Error message (for FAILED status)
            exit_code: Process exit code
            result_data: Result data (for SUCCEEDED status)

        Returns:
            Updated job
        """
        job = await self.get_job_or_raise(job_id)

        # Validate state transition
        valid_transitions = {
            JobStatus.PENDING: [JobStatus.QUEUED, JobStatus.CANCELLED],
            JobStatus.QUEUED: [JobStatus.RUNNING, JobStatus.CANCELLED],
            JobStatus.RUNNING: [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.RESUMABLE],
            JobStatus.FAILED: [JobStatus.PENDING],  # For retry
            JobStatus.RESUMABLE: [JobStatus.PENDING],  # For resume
        }

        allowed = valid_transitions.get(job.status, [])
        if status not in allowed and job.status != status:
            raise InvalidJobStateError(
                f"Cannot transition from {job.status.value} to {status.value}"
            )

        # Update timestamps based on status
        now = utcnow()
        if status == JobStatus.QUEUED and not job.queued_at:
            job.queued_at = now
        elif status == JobStatus.RUNNING and not job.started_at:
            job.started_at = now
        elif status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.RESUMABLE]:
            job.completed_at = now

        job.status = status
        if error_message is not None:
            job.error_message = error_message
        if exit_code is not None:
            job.exit_code = exit_code
        if result_data is not None:
            job.result_data = result_data

        await self.session.flush()
        logger.info(f"Job {job_id} status updated to {status.value}")
        return job

    async def mark_job_queued(self, job_id: str) -> Job:
        """Mark job as queued for execution."""
        return await self.update_job_status(job_id, JobStatus.QUEUED)

    async def mark_job_running(self, job_id: str, pid: Optional[int] = None) -> Job:
        """Mark job as running with optional process ID."""
        job = await self.update_job_status(job_id, JobStatus.RUNNING)
        if pid:
            job.pid = pid
            await self.session.flush()
        return job

    async def mark_job_succeeded(
        self,
        job_id: str,
        exit_code: int = 0,
        result_data: Optional[Dict] = None,
    ) -> Job:
        """Mark job as successfully completed."""
        return await self.update_job_status(
            job_id,
            JobStatus.SUCCEEDED,
            exit_code=exit_code,
            result_data=result_data,
        )

    async def mark_job_failed(
        self,
        job_id: str,
        error_message: str,
        exit_code: Optional[int] = None,
        has_checkpoint: bool = False,
    ) -> Job:
        """Mark job as failed, optionally as resumable if checkpoint exists."""
        status = JobStatus.RESUMABLE if has_checkpoint else JobStatus.FAILED
        return await self.update_job_status(
            job_id,
            status,
            error_message=error_message,
            exit_code=exit_code,
        )

    async def mark_job_cancelled(self, job_id: str, reason: str = "User cancelled") -> Job:
        """Mark job as cancelled."""
        return await self.update_job_status(
            job_id,
            JobStatus.CANCELLED,
            error_message=reason,
        )

    async def cancel_job(self, job_id: str, reason: str = "User cancelled") -> Job:
        """Alias for mark_job_cancelled."""
        return await self.mark_job_cancelled(job_id, reason)

    # =========================================================================
    # Progress Updates
    # =========================================================================

    async def update_progress(
        self,
        job_id: str,
        phase: str,
        percent: int,
        message: Optional[str] = None,
    ) -> Job:
        """
        Update job progress.

        Args:
            job_id: Job identifier
            phase: Current phase name
            percent: Progress percentage (0-100)
            message: Optional progress message
        """
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                progress_phase=phase,
                progress_percent=min(100, max(0, percent)),
                progress_message=message,
            )
        )
        await self.session.flush()
        return await self.get_job(job_id)

    # =========================================================================
    # Checkpoints
    # =========================================================================

    async def save_checkpoint(
        self,
        job_id: str,
        checkpoint_id: str,
        phase: str,
        percent: int,
        state_data: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """
        Save a checkpoint for a job.

        Args:
            job_id: Job identifier
            checkpoint_id: Unique checkpoint identifier
            phase: Current phase name
            percent: Progress percentage (0-100)
            state_data: State data to restore on resume

        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint(
            id=checkpoint_id,
            job_id=job_id,
            created_at=utcnow(),
            phase=phase,
            progress_percent=percent,
            state_data=state_data or {},
        )
        self.session.add(checkpoint)

        # Update job's last checkpoint reference
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(last_checkpoint_id=checkpoint_id)
        )

        await self.session.flush()
        logger.info(f"Saved checkpoint {checkpoint_id} for job {job_id}")
        return checkpoint

    # =========================================================================
    # Retry and Resume
    # =========================================================================

    async def retry_job(self, job_id: str) -> Job:
        """
        Retry a failed job.

        Creates a new job with same parameters, linking to original.
        """
        original = await self.get_job_or_raise(job_id)

        if original.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
            raise InvalidJobStateError(
                f"Cannot retry job in {original.status.value} state"
            )

        if original.retry_count >= original.max_retries:
            raise InvalidJobStateError(
                f"Job has exceeded max retries ({original.max_retries})"
            )

        # Create new job
        new_job = await self.create_job(
            job_type=original.job_type,
            parameters=original.parameters,
            user_id=original.user_id,
            priority=original.priority,
            timeout_seconds=original.timeout_seconds,
            parent_job_id=original.id,
        )

        # Increment retry count on new job
        new_job.retry_count = original.retry_count + 1
        await self.session.flush()

        logger.info(f"Created retry job {new_job.id} for {job_id}")
        return new_job

    async def resume_job(self, job_id: str, checkpoint_id: str) -> Job:
        """
        Resume a failed job from a checkpoint.

        Args:
            job_id: Original job ID
            checkpoint_id: Checkpoint to resume from

        Returns:
            New job configured for resume
        """
        original = await self.get_job_or_raise(job_id, include_checkpoints=True)

        if original.status != JobStatus.RESUMABLE:
            raise InvalidJobStateError(
                f"Job {job_id} is not resumable (status: {original.status.value})"
            )

        # Find checkpoint
        checkpoint = None
        for cp in original.checkpoints:
            if cp.id == checkpoint_id:
                checkpoint = cp
                break

        if not checkpoint:
            raise JobNotFoundError(f"Checkpoint {checkpoint_id} not found")

        # Create new job with resume parameters
        resume_params = {
            **original.parameters,
            "_resume_from_checkpoint": checkpoint_id,
            "_resume_state": checkpoint.state_data,
        }

        new_job = await self.create_job(
            job_type=original.job_type,
            parameters=resume_params,
            user_id=original.user_id,
            priority=original.priority,
            timeout_seconds=original.timeout_seconds,
            parent_job_id=original.id,
        )

        logger.info(f"Created resume job {new_job.id} from checkpoint {checkpoint_id}")
        return new_job

    # =========================================================================
    # Cleanup and Maintenance
    # =========================================================================

    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Delete completed jobs older than specified days.

        Returns number of jobs deleted.
        """
        cutoff = utcnow() - timedelta(days=days)

        result = await self.session.execute(
            delete(Job).where(
                and_(
                    Job.status.in_([JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]),
                    Job.completed_at < cutoff,
                )
            )
        )
        await self.session.flush()

        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    async def mark_orphaned_jobs(self) -> int:
        """
        Mark running jobs as failed on startup (they were orphaned).

        Returns number of jobs marked as orphaned.
        """
        result = await self.session.execute(
            select(Job).where(Job.status == JobStatus.RUNNING)
        )
        orphans = list(result.scalars().all())

        for job in orphans:
            # Check if job has a checkpoint
            has_checkpoint = job.last_checkpoint_id is not None
            status = JobStatus.RESUMABLE if has_checkpoint else JobStatus.FAILED

            job.status = status
            job.error_message = "Orphaned - portal restarted"
            job.completed_at = utcnow()

        await self.session.flush()

        if orphans:
            logger.warning(f"Marked {len(orphans)} orphaned jobs")
        return len(orphans)

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_job_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get job statistics."""
        conditions = []
        if user_id:
            conditions.append(Job.user_id == user_id)

        # Count by status
        status_counts = {}
        for status in JobStatus:
            query = select(func.count(Job.id)).where(Job.status == status)
            if conditions:
                query = query.where(and_(*conditions))
            result = await self.session.execute(query)
            status_counts[status.value] = result.scalar_one()

        # Recent activity
        one_hour_ago = utcnow() - timedelta(hours=1)
        recent_query = select(func.count(Job.id)).where(Job.created_at > one_hour_ago)
        if conditions:
            recent_query = recent_query.where(and_(*conditions))
        recent_result = await self.session.execute(recent_query)

        return {
            "by_status": status_counts,
            "total": sum(status_counts.values()),
            "active": status_counts.get("running", 0) + status_counts.get("queued", 0) + status_counts.get("pending", 0),
            "created_last_hour": recent_result.scalar_one(),
        }
