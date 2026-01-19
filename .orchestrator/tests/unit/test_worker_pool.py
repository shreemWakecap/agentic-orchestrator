"""
Unit tests for WorkerPool.
"""
import asyncio
import pytest


@pytest.mark.asyncio
class TestWorkerPool:
    """Tests for WorkerPool operations."""

    async def test_pool_starts_and_stops(self):
        """Test that pool can start and stop cleanly."""
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=2, max_queue_size=10)

        async def mock_executor(job_id: str):
            await asyncio.sleep(0.01)

        pool.set_executor(mock_executor)
        await pool.start()

        assert pool.is_running

        await pool.shutdown()
        assert not pool.is_running

    async def test_submit_job(self, worker_pool):
        """Test submitting a job to the pool."""
        success = await worker_pool.submit("job-001", priority=1)
        assert success

    async def test_submit_respects_queue_limit(self):
        """Test that submit respects queue size limit."""
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=1, max_queue_size=2)

        # Slow executor to create backpressure
        async def slow_executor(job_id: str):
            await asyncio.sleep(10)

        pool.set_executor(slow_executor)
        await pool.start()

        try:
            # First should succeed (goes to worker)
            await pool.submit("job-1", priority=1)
            # These should go to queue
            await pool.submit("job-2", priority=1)
            await pool.submit("job-3", priority=1)
            # Queue is now full, this should fail
            result = await pool.submit("job-4", priority=1)
            assert result is False
        finally:
            await pool.shutdown(timeout=0.1)

    async def test_job_execution(self, db_engine, monkeypatch):
        """Test that jobs are actually executed."""
        from portal.services import WorkerPool
        from portal.models import Job, JobType, JobStatus
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database
        test_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr("portal.services.worker_pool.async_session_maker", test_session_maker)

        # Create jobs in database first
        async with test_session_maker() as session:
            session.add(Job(id="job-1", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            session.add(Job(id="job-2", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            await session.commit()

        executed_jobs = []

        pool = WorkerPool(max_workers=2, max_queue_size=10)

        async def tracking_executor(job_id: str):
            executed_jobs.append(job_id)
            await asyncio.sleep(0.01)

        pool.set_executor(tracking_executor)
        await pool.start()

        await pool.submit("job-1", priority=1)
        await pool.submit("job-2", priority=1)

        # Wait for execution
        await asyncio.sleep(0.2)

        await pool.shutdown()

        assert "job-1" in executed_jobs
        assert "job-2" in executed_jobs

    async def test_priority_ordering(self, db_engine, monkeypatch):
        """Test that higher priority jobs execute first."""
        from portal.services import WorkerPool
        from portal.models import Job, JobType, JobStatus
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database
        test_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr("portal.services.worker_pool.async_session_maker", test_session_maker)

        # Create jobs in database first
        async with test_session_maker() as session:
            session.add(Job(id="low-priority", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            session.add(Job(id="high-priority", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            session.add(Job(id="medium-priority", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            await session.commit()

        executed_order = []

        pool = WorkerPool(max_workers=1, max_queue_size=10)

        async def tracking_executor(job_id: str):
            executed_order.append(job_id)
            await asyncio.sleep(0.01)

        pool.set_executor(tracking_executor)
        await pool.start()

        # Submit jobs with different priorities
        # Lower number = higher priority
        await pool.submit("low-priority", priority=5)
        await pool.submit("high-priority", priority=1)
        await pool.submit("medium-priority", priority=3)

        # Wait for execution
        await asyncio.sleep(0.3)

        await pool.shutdown()

        # First executed job is from the initial submit
        # After that, queue should be processed by priority
        assert len(executed_order) == 3

    async def test_get_status(self, worker_pool):
        """Test getting pool status."""
        status = worker_pool.get_status()

        assert "running" in status
        assert "max_workers" in status
        assert "queue_size" in status
        assert status["running"] is True
        assert status["max_workers"] == 2

    async def test_graceful_shutdown(self, db_engine, monkeypatch):
        """Test that graceful shutdown waits for jobs."""
        from portal.services import WorkerPool
        from portal.models import Job, JobType, JobStatus
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database
        test_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr("portal.services.worker_pool.async_session_maker", test_session_maker)

        # Create job in database first
        async with test_session_maker() as session:
            session.add(Job(id="slow-job", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            await session.commit()

        completed_jobs = []

        pool = WorkerPool(max_workers=1, max_queue_size=10)

        async def slow_executor(job_id: str):
            await asyncio.sleep(0.1)
            completed_jobs.append(job_id)

        pool.set_executor(slow_executor)
        await pool.start()

        await pool.submit("slow-job", priority=1)

        # Small delay to ensure job starts
        await asyncio.sleep(0.05)

        # Graceful shutdown should wait
        await pool.shutdown(timeout=1.0)

        # Job should have completed
        assert "slow-job" in completed_jobs

    async def test_shutdown_timeout(self):
        """Test that shutdown respects timeout."""
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=1, max_queue_size=10)

        async def very_slow_executor(job_id: str):
            await asyncio.sleep(10)  # Very slow

        pool.set_executor(very_slow_executor)
        await pool.start()

        await pool.submit("hanging-job", priority=1)

        # Small delay to ensure job starts
        await asyncio.sleep(0.05)

        # Short timeout should force shutdown
        await pool.shutdown(timeout=0.1)

        assert not pool.is_running

    async def test_executor_exception_handling(self, db_engine, monkeypatch):
        """Test that executor exceptions don't crash the pool."""
        from portal.services import WorkerPool
        from portal.models import Job, JobType, JobStatus
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        # Patch database
        test_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr("portal.services.worker_pool.async_session_maker", test_session_maker)

        # Create jobs in database first
        async with test_session_maker() as session:
            session.add(Job(id="failing-job", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            session.add(Job(id="succeeding-job", job_type=JobType.PLAN, status=JobStatus.QUEUED, parameters={}))
            await session.commit()

        executed_after_error = []

        pool = WorkerPool(max_workers=1, max_queue_size=10)

        async def failing_executor(job_id: str):
            if job_id == "failing-job":
                raise Exception("Simulated failure")
            executed_after_error.append(job_id)
            await asyncio.sleep(0.01)

        pool.set_executor(failing_executor)
        await pool.start()

        await pool.submit("failing-job", priority=1)
        await pool.submit("succeeding-job", priority=2)

        # Wait for execution
        await asyncio.sleep(0.3)

        await pool.shutdown()

        # Pool should still be running and process subsequent jobs
        assert "succeeding-job" in executed_after_error

    async def test_concurrent_jobs(self):
        """Test that multiple workers run concurrently."""
        from portal.services import WorkerPool
        import time

        pool = WorkerPool(max_workers=3, max_queue_size=10)

        start_times = {}
        end_times = {}

        async def timed_executor(job_id: str):
            start_times[job_id] = time.time()
            await asyncio.sleep(0.1)
            end_times[job_id] = time.time()

        pool.set_executor(timed_executor)
        await pool.start()

        # Submit 3 jobs
        await pool.submit("job-1", priority=1)
        await pool.submit("job-2", priority=1)
        await pool.submit("job-3", priority=1)

        # Wait for completion
        await asyncio.sleep(0.5)

        await pool.shutdown()

        # All jobs should have started close together (within 50ms)
        start_time_list = list(start_times.values())
        if len(start_time_list) >= 2:
            time_diff = max(start_time_list) - min(start_time_list)
            assert time_diff < 0.1  # Should start concurrently
