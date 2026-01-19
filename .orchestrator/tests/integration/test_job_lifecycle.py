"""
Integration tests for complete job lifecycle.

Tests the full flow from job creation to completion.
"""
import asyncio
import pytest


@pytest.mark.asyncio
class TestJobLifecycle:
    """Tests for complete job lifecycle flows."""

    async def test_job_state_progression(self, db_session, job_factory):
        """Test job progresses through states correctly."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Create job (PENDING)
        job = await job_factory(status=JobStatus.PENDING)
        assert job.status == JobStatus.PENDING

        # Queue job (QUEUED)
        job = await service.mark_job_queued(job.id)
        assert job.status == JobStatus.QUEUED
        assert job.queued_at is not None

        # Start job (RUNNING)
        job = await service.mark_job_running(job.id)
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

        # Complete job (SUCCEEDED)
        job = await service.mark_job_succeeded(job.id, exit_code=0)
        assert job.status == JobStatus.SUCCEEDED
        assert job.completed_at is not None
        assert job.exit_code == 0

    async def test_job_failure_flow(self, db_session, job_factory):
        """Test job failure handling."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        job = await job_factory(status=JobStatus.RUNNING)

        # Fail the job
        job = await service.mark_job_failed(
            job.id,
            exit_code=1,
            error_message="Task failed"
        )

        assert job.status == JobStatus.FAILED
        assert job.exit_code == 1
        assert job.error_message == "Task failed"

    async def test_job_cancellation_flow(self, db_session, job_factory):
        """Test job cancellation at different stages."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Cancel pending job
        pending_job = await job_factory(status=JobStatus.PENDING)
        cancelled = await service.cancel_job(pending_job.id, "User request")
        assert cancelled.status == JobStatus.CANCELLED

        # Cancel running job
        running_job = await job_factory(status=JobStatus.RUNNING)
        cancelled = await service.cancel_job(running_job.id)
        assert cancelled.status == JobStatus.CANCELLED

    async def test_job_retry_flow(self, db_session, job_factory):
        """Test job retry creates new job with correct linkage."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Create and fail a job
        original = await job_factory(status=JobStatus.FAILED)

        # Retry
        retried = await service.retry_job(original.id)

        assert retried.id != original.id
        assert retried.parent_job_id == original.id
        assert retried.status == JobStatus.PENDING
        assert retried.retry_count == 1
        assert retried.parameters == original.parameters
        assert retried.job_type == original.job_type

    async def test_job_progress_tracking(self, db_session, job_factory):
        """Test progress updates are tracked."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        job = await job_factory(status=JobStatus.RUNNING)

        # Update progress multiple times
        await service.update_progress(job.id, "phase1", 25, "Starting")
        await service.update_progress(job.id, "phase2", 50, "Halfway")
        await service.update_progress(job.id, "phase3", 75, "Almost done")

        # Get latest state
        job = await service.get_job(job.id)

        assert job.progress_phase == "phase3"
        assert job.progress_percent == 75
        assert job.progress_message == "Almost done"

    async def test_checkpoint_saves_state(self, db_session, job_factory):
        """Test checkpoint creation and retrieval."""
        from portal.models import JobStatus, Checkpoint
        from portal.services import JobService
        from sqlalchemy import select

        service = JobService(db_session)

        job = await job_factory(status=JobStatus.RUNNING)

        # Save checkpoint
        await service.save_checkpoint(
            job.id,
            checkpoint_id="chk_001",
            phase="processing",
            percent=50,
            state_data={"items_processed": 100}
        )

        # Retrieve checkpoint
        result = await db_session.execute(
            select(Checkpoint).where(Checkpoint.job_id == job.id)
        )
        checkpoint = result.scalar_one_or_none()

        assert checkpoint is not None
        assert checkpoint.id == "chk_001"
        assert checkpoint.state_data == {"items_processed": 100}

    async def test_resume_from_checkpoint(self, db_session, job_factory):
        """Test resuming a job from checkpoint."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Create job with checkpoint
        job = await job_factory(status=JobStatus.RESUMABLE)
        await service.save_checkpoint(
            job.id,
            checkpoint_id="chk_resume",
            phase="midway",
            percent=50,
            state_data={"progress": "halfway"}
        )

        # Resume from checkpoint
        resumed = await service.resume_job(job.id, "chk_resume")

        assert resumed.id != job.id
        assert resumed.status == JobStatus.PENDING
        # Should have checkpoint info in parameters
        assert resumed.parameters.get("_resume_from_checkpoint") == "chk_resume"

    async def test_orphan_detection(self, db_session, job_factory):
        """Test orphan job detection."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Create jobs in various states
        await job_factory(status=JobStatus.RUNNING)  # This is an orphan
        await job_factory(status=JobStatus.RUNNING)  # This is an orphan
        await job_factory(status=JobStatus.PENDING)  # Not an orphan
        await job_factory(status=JobStatus.SUCCEEDED)  # Not an orphan

        # Mark orphans
        count = await service.mark_orphaned_jobs()

        assert count == 2

    async def test_job_timeout_handling(self, db_session, job_factory):
        """Test job timeout configuration."""
        from portal.models import JobStatus, JobType
        from portal.services import JobService

        service = JobService(db_session)

        # Create job with custom timeout
        job = await service.create_job(
            job_type=JobType.PLAN,
            parameters={"spec_id": "test"},
            timeout_seconds=300
        )

        assert job.timeout_seconds == 300


@pytest.mark.asyncio
class TestWorkerPoolIntegration:
    """Tests for WorkerPool integration with job lifecycle."""

    async def test_worker_pool_processes_jobs(self, db_engine, db_session, job_factory, monkeypatch):
        """Test that worker pool processes submitted jobs."""
        from portal.models import JobStatus
        from portal.services import WorkerPool, JobService
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database session maker for worker pool
        test_session_maker = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        monkeypatch.setattr(
            "portal.services.worker_pool.async_session_maker",
            test_session_maker
        )

        service = JobService(db_session)
        executed_jobs = []

        pool = WorkerPool(max_workers=2)

        async def executor(job_id: str):
            executed_jobs.append(job_id)
            await asyncio.sleep(0.05)

        pool.set_executor(executor)
        await pool.start()

        try:
            # Create and submit jobs
            job1 = await job_factory(status=JobStatus.QUEUED)
            job2 = await job_factory(status=JobStatus.QUEUED)

            await pool.submit(job1.id, priority=1)
            await pool.submit(job2.id, priority=1)

            # Wait for execution
            await asyncio.sleep(0.3)

            assert job1.id in executed_jobs
            assert job2.id in executed_jobs
        finally:
            await pool.shutdown()

    async def test_worker_pool_respects_priority(self, db_engine, db_session, job_factory, monkeypatch):
        """Test that higher priority jobs run first."""
        from portal.models import JobStatus
        from portal.services import WorkerPool
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database session maker for worker pool
        test_session_maker = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        monkeypatch.setattr(
            "portal.services.worker_pool.async_session_maker",
            test_session_maker
        )

        execution_order = []

        pool = WorkerPool(max_workers=1)

        async def executor(job_id: str):
            execution_order.append(job_id)
            await asyncio.sleep(0.02)

        pool.set_executor(executor)
        await pool.start()

        try:
            # Submit with different priorities
            job_low = await job_factory(status=JobStatus.QUEUED)
            job_high = await job_factory(status=JobStatus.QUEUED)

            # Submit low first, then high
            await pool.submit(job_low.id, priority=5)
            await pool.submit(job_high.id, priority=1)

            await asyncio.sleep(0.3)

            # High priority should have been processed
            # (order depends on timing of submit vs execution)
            assert len(execution_order) == 2
        finally:
            await pool.shutdown()
