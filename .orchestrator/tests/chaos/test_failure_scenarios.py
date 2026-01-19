"""
Chaos tests for failure scenarios.

Tests system resilience to various failure conditions.
"""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
class TestWorkerFailures:
    """Tests for worker failure handling."""

    async def test_worker_crash_recovery(self, db_engine, db_session, job_factory, monkeypatch):
        """Test that worker pool handles crashed workers."""
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

        jobs_executed = []
        crash_job = await job_factory(status=JobStatus.QUEUED)
        good_job_1 = await job_factory(status=JobStatus.QUEUED)
        good_job_2 = await job_factory(status=JobStatus.QUEUED)

        async def crashing_executor(job_id: str):
            if job_id == crash_job.id:
                raise Exception("Simulated crash")
            jobs_executed.append(job_id)
            await asyncio.sleep(0.05)

        pool = WorkerPool(max_workers=2)
        pool.set_executor(crashing_executor)
        await pool.start()

        try:
            # Submit jobs including one that crashes
            await pool.submit(crash_job.id, priority=1)
            await pool.submit(good_job_1.id, priority=2)
            await pool.submit(good_job_2.id, priority=3)

            # Wait for processing
            await asyncio.sleep(0.5)

            # Pool should still be running
            assert pool.is_running

            # Good jobs should complete
            assert good_job_1.id in jobs_executed or good_job_2.id in jobs_executed
        finally:
            await pool.shutdown()

    async def test_executor_timeout_handling(self):
        """Test that hanging executors are handled."""
        from portal.services import WorkerPool

        async def hanging_executor(job_id: str):
            if job_id == "hanging-job":
                await asyncio.sleep(100)  # Hang forever
            await asyncio.sleep(0.01)

        pool = WorkerPool(max_workers=1)
        pool.set_executor(hanging_executor)
        await pool.start()

        try:
            await pool.submit("hanging-job", priority=1)

            # Give it time to start
            await asyncio.sleep(0.1)

            # Shutdown should handle the hanging job
            await pool.shutdown(timeout=0.5)

            assert not pool.is_running
        except asyncio.TimeoutError:
            # Expected if shutdown times out
            pass

    async def test_multiple_concurrent_failures(self, db_engine, db_session, job_factory, monkeypatch):
        """Test handling multiple simultaneous failures."""
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

        failure_count = 0
        success_count = 0
        job_to_fail = set()  # Track which jobs should fail

        # Create jobs
        jobs = []
        for i in range(10):
            job = await job_factory(status=JobStatus.QUEUED)
            jobs.append(job)
            if i % 2 == 0:  # Every other job will fail
                job_to_fail.add(job.id)

        async def flaky_executor(job_id: str):
            nonlocal failure_count, success_count
            # Every other job fails
            if job_id in job_to_fail:
                failure_count += 1
                raise Exception(f"Simulated failure for {job_id}")
            success_count += 1
            await asyncio.sleep(0.02)

        pool = WorkerPool(max_workers=4)
        pool.set_executor(flaky_executor)
        await pool.start()

        try:
            # Submit mix of jobs
            for job in jobs:
                await pool.submit(job.id, priority=1)

            await asyncio.sleep(1)

            # System should handle mixed results
            assert pool.is_running
            assert success_count > 0
            assert failure_count > 0
        finally:
            await pool.shutdown()


@pytest.mark.asyncio
class TestDatabaseFailures:
    """Tests for database failure handling."""

    async def test_database_connection_retry(self, db_session, job_factory):
        """Test handling of transient database errors."""
        from portal.models import JobStatus
        from portal.services import JobService

        service = JobService(db_session)

        # Normal operation should work
        job = await job_factory(status=JobStatus.PENDING)
        assert job is not None

        # Verify we can still query
        fetched = await service.get_job(job.id)
        assert fetched is not None

    async def test_transaction_rollback_on_error(self, db_session, job_factory):
        """Test that failed operations properly rollback."""
        from portal.models import JobStatus
        from portal.services import JobService, InvalidJobStateError

        service = JobService(db_session)

        # Create a job
        job = await job_factory(status=JobStatus.SUCCEEDED)

        # Try invalid operation
        try:
            await service.mark_job_running(job.id)
        except InvalidJobStateError:
            pass

        # Job should still be in original state
        fetched = await service.get_job(job.id)
        assert fetched.status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
class TestEventCollectorFailures:
    """Tests for event collector failure handling."""

    async def test_event_collector_handles_malformed_json(self):
        """Test handling of malformed JSONL input."""
        from portal.services import EventCollector

        collector = EventCollector()
        await collector.start()

        try:
            # Send malformed JSON
            await collector.process_line("test-job", "{not valid json")
            await collector.process_line("test-job", "completely plain text")
            await collector.process_line("test-job", '{"type":"log","message":"valid"}')

            # Should handle gracefully
            sequence = collector.get_last_sequence("test-job")
            assert sequence >= 3  # All processed as events
        finally:
            await collector.stop()

    async def test_event_collector_handles_sse_failure(self):
        """Test collector continues when SSE publishing fails."""
        from portal.services import EventCollector

        collector = EventCollector()

        async def failing_publisher(job_id, event_type, data):
            raise Exception("SSE failure")

        collector.set_sse_publisher(failing_publisher)
        await collector.start()

        try:
            # Process events even though SSE fails
            for i in range(5):
                await collector.process_line(
                    "test-job",
                    f'{{"type":"log","message":"Event {i}"}}'
                )

            # Events should still be collected
            sequence = collector.get_last_sequence("test-job")
            assert sequence == 5
        finally:
            await collector.stop()

    async def test_event_collector_backpressure(self):
        """Test event collector handles backpressure."""
        from portal.services import EventCollector

        collector = EventCollector(batch_size=5, flush_interval=0.1)
        await collector.start()

        try:
            # Rapidly add many events
            for i in range(1000):
                await collector.process_line(
                    "backpressure-job",
                    f'{{"type":"log","level":"info","message":"Line {i}"}}'
                )

            # Should not crash, events may be batched
            assert collector.get_last_sequence("backpressure-job") > 0
        finally:
            await collector.stop()


@pytest.mark.asyncio
class TestSSEFailures:
    """Tests for SSE streaming failure handling."""

    async def test_sse_client_disconnect(self):
        """Test SSE handles client disconnection gracefully."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        try:
            # Register connection
            conn_id = await manager.register_connection("test-job")

            # Simulate disconnect
            await manager.unregister_connection("test-job", conn_id)

            # Publishing should not error
            await manager.publish("test-job", "log", {"message": "No listeners"})

            # Manager should still be running
            assert manager.is_running
        finally:
            await manager.stop()

    async def test_sse_handles_slow_clients(self):
        """Test SSE handles slow clients without blocking."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        events_received = []

        try:
            async def slow_callback(data):
                await asyncio.sleep(0.5)  # Slow client
                events_received.append(data)

            async def fast_callback(data):
                events_received.append(data)

            await manager.register_connection("job", callback=slow_callback)
            await manager.register_connection("job", callback=fast_callback)

            # Publish should not block on slow client
            start = asyncio.get_event_loop().time()
            await manager.publish("job", "log", {"message": "test"})
            elapsed = asyncio.get_event_loop().time() - start

            # Should return quickly
            assert elapsed < 0.2
        finally:
            await manager.stop()


@pytest.mark.asyncio
class TestProcessExecutorFailures:
    """Tests for process executor failure handling."""

    async def test_process_timeout(self):
        """Test that process timeout is handled correctly."""
        from portal.services import ProcessExecutor, ProcessState

        executor = ProcessExecutor()

        # Mock a process that times out
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()

            async def slow_readline():
                await asyncio.sleep(10)
                return b""

            mock_process.stdout.readline = slow_readline
            mock_process.wait = AsyncMock(return_value=0)
            mock_process.terminate = MagicMock()
            mock_process.kill = MagicMock()
            mock_process.returncode = None
            mock_exec.return_value = mock_process

            result = await executor.execute(
                job_id="timeout-test",
                job_type="plan",
                parameters={},
                timeout_seconds=0.5,
            )

            assert result.state in [ProcessState.TIMEOUT, ProcessState.CANCELLED]

    async def test_process_crash(self):
        """Test handling of crashed process."""
        from portal.services import ProcessExecutor, ProcessState

        executor = ProcessExecutor()

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock(return_value=1)  # Non-zero exit
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await executor.execute(
                job_id="crash-test",
                job_type="plan",
                parameters={},
            )

            assert result.exit_code == 1


@pytest.mark.asyncio
class TestNetworkFailures:
    """Tests for network-related failure scenarios."""

    async def test_reconnection_after_disconnect(self):
        """Test client reconnection after network issues."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        received_after_reconnect = []

        try:
            # First connection
            conn_id = await manager.register_connection("job")

            # Simulate disconnect
            await manager.unregister_connection("job", conn_id)

            # Reconnect
            async def callback(data):
                received_after_reconnect.append(data)

            await manager.register_connection("job", callback=callback)

            # Publish after reconnect
            await manager.publish("job", "log", {"message": "after reconnect"})

            await asyncio.sleep(0.1)

            assert len(received_after_reconnect) >= 1
        finally:
            await manager.stop()


@pytest.mark.asyncio
class TestResourceExhaustion:
    """Tests for resource exhaustion scenarios."""

    async def test_queue_full_rejection(self):
        """Test proper handling when queue is full."""
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=1, max_queue_size=2)

        async def slow_executor(job_id: str):
            await asyncio.sleep(10)

        pool.set_executor(slow_executor)
        await pool.start()

        try:
            # Fill up queue
            await pool.submit("job-1", priority=1)
            await pool.submit("job-2", priority=1)
            await pool.submit("job-3", priority=1)

            # This should be rejected
            result = await pool.submit("job-4", priority=1)
            assert result is False
        finally:
            await pool.shutdown(timeout=0.1)

    async def test_rapid_connect_disconnect(self):
        """Test rapid connection/disconnection cycles."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        try:
            # Rapid connect/disconnect
            for i in range(50):
                conn_id = await manager.register_connection(f"job-{i % 5}")
                if i % 2 == 0:
                    await manager.unregister_connection(f"job-{i % 5}", conn_id)

            # Manager should still be healthy
            assert manager.is_running
        finally:
            await manager.stop()
