"""
Job Management API - REST endpoints for job operations.
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Query, Depends, status
from fastapi.responses import JSONResponse

from ..models import (
    async_session_maker, Job, JobEvent, JobStatus, JobType,
)
from ..services import (
    JobService, JobNotFoundError, InvalidJobStateError,
    get_worker_pool, get_process_executor, get_event_collector,
)
from ..streaming import get_sse_manager
from .schemas import (
    JobCreateRequest, JobCancelRequest, JobRetryRequest, JobResumeRequest,
    JobResponse, JobListResponse, JobSubmittedResponse,
    JobCheckpointsResponse, CheckpointResponse,
    JobLogsResponse, JobLogEntry,
    WorkerPoolStatus, ErrorResponse,
    JobStatusEnum, JobTypeEnum, ProgressInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def build_job_urls(job_id: str) -> dict:
    """Build standard URLs for a job."""
    return {
        "status_url": f"/api/jobs/{job_id}",
        "stream_url": f"/api/jobs/{job_id}/stream",
        "cancel_url": f"/api/jobs/{job_id}/cancel",
        "logs_url": f"/api/jobs/{job_id}/logs",
    }


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response schema."""
    urls = build_job_urls(job.id)
    return JobResponse(
        job_id=job.id,
        job_type=JobTypeEnum(job.job_type.value),
        status=JobStatusEnum(job.status.value),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=ProgressInfo(
            phase=job.progress_phase,
            percent=job.progress_percent,
            message=job.progress_message,
        ) if job.progress_phase else None,
        exit_code=job.exit_code,
        error=job.error_message,
        parameters=job.parameters,
        parent_job_id=job.parent_job_id,
        retry_count=job.retry_count,
        **urls,
    )


# ============================================================================
# Job Submission
# ============================================================================

@router.post(
    "",
    response_model=JobSubmittedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Job submitted successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "Queue full"},
    },
)
async def create_job(request: JobCreateRequest):
    """
    Submit a new job for execution.

    The job is queued and will be executed by a worker when available.
    Returns immediately with job ID and URLs for tracking.
    """
    async with async_session_maker() as session:
        service = JobService(session)

        # Create job
        job = await service.create_job(
            job_type=JobType(request.job_type.value),
            parameters=request.parameters,
            priority=request.priority,
            timeout_seconds=request.timeout_seconds,
        )
        await session.commit()

        # Submit to worker pool
        pool = get_worker_pool()
        submitted = await pool.submit(job.id, priority=request.priority)

        if not submitted:
            # Queue full, but job is created - mark as pending
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job queue is full. Please try again later."
            )

        # Get queue position
        queue_position = pool.get_queue_position(job.id)

        urls = build_job_urls(job.id)
        return JobSubmittedResponse(
            job_id=job.id,
            status=JobStatusEnum.PENDING,
            created_at=job.created_at,
            queue_position=queue_position,
            status_url=urls["status_url"],
            stream_url=urls["stream_url"],
            cancel_url=urls["cancel_url"],
        )


# ============================================================================
# Job Status
# ============================================================================

@router.get(
    "/{job_id}",
    response_model=JobResponse,
    responses={
        200: {"description": "Job found"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_job(job_id: str):
    """Get current status of a job."""
    async with async_session_maker() as session:
        service = JobService(session)

        try:
            job = await service.get_job_or_raise(job_id)
            return job_to_response(job)
        except JobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )


# ============================================================================
# Job Listing
# ============================================================================

@router.get(
    "",
    response_model=JobListResponse,
)
async def list_jobs(
    status: Optional[JobStatusEnum] = Query(None, description="Filter by status"),
    job_type: Optional[JobTypeEnum] = Query(None, description="Filter by type"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List jobs with optional filtering."""
    async with async_session_maker() as session:
        service = JobService(session)

        status_filter = JobStatus(status.value) if status else None
        type_filter = JobType(job_type.value) if job_type else None

        jobs, total = await service.list_jobs(
            status=status_filter,
            job_type=type_filter,
            limit=limit,
            offset=offset,
        )

        return JobListResponse(
            jobs=[job_to_response(j) for j in jobs],
            total=total,
            limit=limit,
            offset=offset,
        )


# ============================================================================
# Job Control
# ============================================================================

@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    responses={
        200: {"description": "Job cancelled"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Cannot cancel job"},
    },
)
async def cancel_job(job_id: str, request: JobCancelRequest):
    """Cancel a running or pending job."""
    async with async_session_maker() as session:
        service = JobService(session)

        try:
            job = await service.get_job_or_raise(job_id)

            # Check if cancellable
            if job.status not in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel job in {job.status.value} state"
                )

            # Cancel process if running
            if job.status == JobStatus.RUNNING:
                executor = get_process_executor()
                await executor.cancel(job_id)

            # Update status
            await service.mark_job_cancelled(job_id, request.reason)
            await session.commit()

            job = await service.get_job(job_id)
            return job_to_response(job)

        except JobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )


@router.post(
    "/{job_id}/retry",
    response_model=JobSubmittedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Retry job created"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Cannot retry job"},
    },
)
async def retry_job(job_id: str):
    """Retry a failed or cancelled job."""
    async with async_session_maker() as session:
        service = JobService(session)

        try:
            new_job = await service.retry_job(job_id)
            await session.commit()

            # Submit to worker pool
            pool = get_worker_pool()
            await pool.submit(new_job.id, priority=new_job.priority)

            urls = build_job_urls(new_job.id)
            return JobSubmittedResponse(
                job_id=new_job.id,
                status=JobStatusEnum.PENDING,
                created_at=new_job.created_at,
                queue_position=pool.get_queue_position(new_job.id),
                status_url=urls["status_url"],
                stream_url=urls["stream_url"],
                cancel_url=urls["cancel_url"],
            )

        except JobNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        except InvalidJobStateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@router.post(
    "/{job_id}/resume",
    response_model=JobSubmittedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_job(job_id: str, request: JobResumeRequest):
    """Resume a job from a checkpoint."""
    async with async_session_maker() as session:
        service = JobService(session)

        try:
            new_job = await service.resume_job(job_id, request.checkpoint_id)
            await session.commit()

            pool = get_worker_pool()
            await pool.submit(new_job.id, priority=new_job.priority)

            urls = build_job_urls(new_job.id)
            return JobSubmittedResponse(
                job_id=new_job.id,
                status=JobStatusEnum.PENDING,
                created_at=new_job.created_at,
                queue_position=pool.get_queue_position(new_job.id),
                status_url=urls["status_url"],
                stream_url=urls["stream_url"],
                cancel_url=urls["cancel_url"],
            )

        except (JobNotFoundError, InvalidJobStateError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


# ============================================================================
# Logs and Checkpoints
# ============================================================================

@router.get(
    "/{job_id}/logs",
    response_model=JobLogsResponse,
)
async def get_job_logs(
    job_id: str,
    level: Optional[str] = Query(None, description="Filter by level"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get log entries for a job."""
    from sqlalchemy import select, func

    async with async_session_maker() as session:
        # Verify job exists
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Build query
        query = select(JobEvent).where(
            JobEvent.job_id == job_id,
            JobEvent.event_type.in_(["log", "raw", "error"])
        )

        if level:
            query = query.where(JobEvent.log_level == level)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_query)).scalar_one()

        # Get data
        query = query.order_by(JobEvent.sequence).offset(offset).limit(limit)
        result = await session.execute(query)
        events = result.scalars().all()

        return JobLogsResponse(
            job_id=job_id,
            logs=[
                JobLogEntry(
                    sequence=e.sequence,
                    timestamp=e.timestamp,
                    level=e.log_level or "info",
                    message=e.data.get("message", str(e.data)),
                )
                for e in events
            ],
            total_lines=total,
            offset=offset,
            limit=limit,
        )


@router.get(
    "/{job_id}/checkpoints",
    response_model=JobCheckpointsResponse,
)
async def get_job_checkpoints(job_id: str):
    """Get checkpoints for a job."""
    from sqlalchemy import select
    from ..models import Checkpoint

    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        result = await session.execute(
            select(Checkpoint)
            .where(Checkpoint.job_id == job_id)
            .order_by(Checkpoint.created_at)
        )
        checkpoints = result.scalars().all()

        return JobCheckpointsResponse(
            job_id=job_id,
            checkpoints=[
                CheckpointResponse(
                    id=cp.id,
                    job_id=cp.job_id,
                    created_at=cp.created_at,
                    phase=cp.phase,
                    progress_percent=cp.progress_percent,
                )
                for cp in checkpoints
            ],
        )


# ============================================================================
# Streaming (delegates to SSE manager)
# ============================================================================

@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str, request: Request):
    """
    Stream job events via Server-Sent Events.

    Connect using EventSource:
    ```javascript
    const es = new EventSource('/api/jobs/{job_id}/stream');
    es.addEventListener('progress', (e) => console.log(JSON.parse(e.data)));
    ```
    """
    # Verify job exists
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    manager = get_sse_manager()
    return await manager.create_stream(job_id, request)


# ============================================================================
# Worker Pool Status
# ============================================================================

@router.get(
    "/pool/status",
    response_model=WorkerPoolStatus,
    tags=["admin"],
)
async def get_pool_status():
    """Get worker pool status (admin endpoint)."""
    pool = get_worker_pool()
    pool_status = pool.get_status()

    return WorkerPoolStatus(
        running=pool_status["running"],
        max_workers=pool_status["max_workers"],
        active_workers=pool_status["active_workers"],
        idle_workers=pool_status["idle_workers"],
        queue_size=pool_status["queue_size"],
        total_completed=pool_status["total_completed"],
        total_failed=pool_status["total_failed"],
    )
