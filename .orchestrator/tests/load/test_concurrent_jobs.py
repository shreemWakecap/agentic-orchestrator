"""
Load tests for concurrent job processing.

Tests system behavior under high concurrency and load.
"""
import asyncio
import time
import pytest


@pytest.mark.asyncio
class TestConcurrentJobProcessing:
    """Tests for high-concurrency job processing."""

    async def test_many_concurrent_submissions(self, db_engine, db_session, job_factory, monkeypatch):
        """Test submitting many jobs concurrently."""
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

        processed_jobs = []
        pool = WorkerPool(max_workers=4, max_queue_size=100)

        async def executor(job_id: str):
            await asyncio.sleep(0.01)
            processed_jobs.append(job_id)

        pool.set_executor(executor)
        await pool.start()

        try:
            # Create many jobs
            jobs = []
            for i in range(50):
                job = await job_factory(status=JobStatus.QUEUED)
                jobs.append(job)

            # Submit all concurrently
            submit_tasks = [
                pool.submit(job.id, priority=1)
                for job in jobs
            ]
            results = await asyncio.gather(*submit_tasks)

            # All should be accepted
            accepted = sum(1 for r in results if r)
            assert accepted >= 50  # All should be accepted

            # Wait for processing
            await asyncio.sleep(2)

            # All should be processed
            assert len(processed_jobs) == 50
        finally:
            await pool.shutdown()

    async def test_burst_job_submission(self, db_engine, db_session, job_factory, monkeypatch):
        """Test burst submission handling."""
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

        pool = WorkerPool(max_workers=2, max_queue_size=20)
        processed = []

        async def executor(job_id: str):
            processed.append(job_id)
            await asyncio.sleep(0.05)

        pool.set_executor(executor)
        await pool.start()

        try:
            # Burst of submissions
            jobs = [await job_factory(status=JobStatus.QUEUED) for _ in range(20)]

            start = time.time()

            for job in jobs:
                await pool.submit(job.id, priority=1)

            # Wait for completion
            while len(processed) < 20 and (time.time() - start) < 10:
                await asyncio.sleep(0.1)

            # Should complete in reasonable time
            elapsed = time.time() - start
            assert elapsed < 10  # Should complete within 10 seconds
            assert len(processed) == 20
        finally:
            await pool.shutdown()

    async def test_concurrent_event_processing(self):
        """Test event collector handles concurrent events."""
        from portal.services import EventCollector

        collector = EventCollector(batch_size=10, flush_interval=0.5)
        await collector.start()

        try:
            # Process events from multiple jobs concurrently
            async def send_events(job_id: str, count: int):
                for i in range(count):
                    await collector.process_line(
                        job_id,
                        f'{{"type":"log","message":"Event {i}"}}'
                    )
                    await asyncio.sleep(0.001)

            # 10 jobs each sending 100 events
            await asyncio.gather(*[
                send_events(f"job-{j}", 100)
                for j in range(10)
            ])

            # Verify all events received
            total_events = sum(
                collector.get_last_sequence(f"job-{j}")
                for j in range(10)
            )
            assert total_events == 1000
        finally:
            await collector.stop()

    async def test_high_throughput_event_streaming(self):
        """Test SSE under high event throughput."""
        from portal.streaming import SSEManager
        from portal.services import EventCollector

        manager = SSEManager()
        await manager.start()

        collector = EventCollector()
        collector.set_sse_publisher(
            lambda jid, et, d: manager.publish(jid, et, d)
        )
        await collector.start()

        received_counts = {}

        try:
            # Setup listeners for 5 jobs
            for j in range(5):
                job_id = f"throughput-job-{j}"
                received_counts[job_id] = 0

                async def make_callback(jid):
                    async def callback(data):
                        received_counts[jid] += 1
                    return callback

                await manager.register_connection(
                    job_id,
                    callback=await make_callback(job_id)
                )

            # Send many events per job
            for j in range(5):
                job_id = f"throughput-job-{j}"
                for i in range(50):
                    await collector.process_line(
                        job_id,
                        f'{{"type":"log","message":"High throughput event {i}"}}'
                    )

            # Wait for delivery
            await asyncio.sleep(1)

            # Each job should have received events
            for job_id, count in received_counts.items():
                assert count >= 40  # Allow some tolerance
        finally:
            await collector.stop()
            await manager.stop()

    async def test_database_under_load(self, db_session, job_factory):
        """Test database operations under concurrent load."""
        from portal.models import JobStatus, JobType
        from portal.services import JobService

        service = JobService(db_session)

        # Create many jobs concurrently
        async def create_jobs(count: int):
            jobs = []
            for i in range(count):
                job = await service.create_job(
                    job_type=JobType.PLAN,
                    parameters={"spec_id": f"load-test-{i}"},
                )
                jobs.append(job)
            return jobs

        # Create in batches
        all_jobs = []
        for batch in range(5):
            jobs = await create_jobs(10)
            all_jobs.extend(jobs)
            await db_session.commit()

        assert len(all_jobs) == 50

        # List operations under load
        for _ in range(10):
            jobs, total = await service.list_jobs(limit=20)
            assert len(jobs) <= 20

    async def test_graceful_degradation_under_load(self, db_engine, db_session, job_factory, monkeypatch):
        """Test system degrades gracefully under excessive load."""
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

        pool = WorkerPool(max_workers=2, max_queue_size=5)
        processed = []
        rejected = 0

        async def slow_executor(job_id: str):
            processed.append(job_id)
            await asyncio.sleep(0.5)  # Slow processing

        pool.set_executor(slow_executor)
        await pool.start()

        try:
            # Create jobs and try to submit more than queue can hold
            for i in range(20):
                job = await job_factory(status=JobStatus.QUEUED)
                result = await pool.submit(job.id, priority=1)
                if not result:
                    rejected += 1

            # Some should be rejected
            assert rejected > 0  # Queue should have filled up

            # System should still be functioning
            await asyncio.sleep(2)
            assert len(processed) > 0
        finally:
            await pool.shutdown(timeout=0.5)


@pytest.mark.asyncio
class TestMemoryAndResourceUsage:
    """Tests for memory and resource management under load."""

    async def test_event_buffer_memory_bounded(self):
        """Test that event buffers don't grow unbounded."""
        from portal.services import EventCollector

        # Small buffer size
        collector = EventCollector(buffer_size=100, batch_size=5, flush_interval=0.1)
        await collector.start()

        try:
            # Send many more events than buffer size
            for i in range(1000):
                await collector.process_line(
                    "memory-test-job",
                    f'{{"type":"log","message":"Event {i}"}}'
                )

            # Buffer should be bounded
            events = collector.get_events_since("memory-test-job", 0)
            assert len(events) <= 100
        finally:
            await collector.stop()

    async def test_worker_cleanup_after_many_jobs(self):
        """Test workers clean up properly after many jobs."""
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=2)
        executed = 0

        async def executor(job_id: str):
            nonlocal executed
            executed += 1
            await asyncio.sleep(0.01)

        pool.set_executor(executor)
        await pool.start()

        try:
            # Process many jobs
            for i in range(100):
                await pool.submit(f"cleanup-test-{i}", priority=1)

            # Wait for all to complete
            await asyncio.sleep(3)

            status = pool.get_status()
            # Workers should be idle after processing
            assert status.get("active_jobs", 0) == 0 or status.get("queue_size", 0) == 0
        finally:
            await pool.shutdown()
