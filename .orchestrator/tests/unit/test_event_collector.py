"""
Unit tests for EventCollector.
"""
import asyncio
import pytest


@pytest.mark.asyncio
class TestEventCollector:
    """Tests for EventCollector operations."""

    async def test_collector_starts_and_stops(self):
        """Test that collector can start and stop cleanly."""
        from portal.services import EventCollector

        collector = EventCollector(batch_size=5, flush_interval=0.5)
        await collector.start()

        # Should be running
        assert collector._flush_task is not None

        await collector.stop()

        # Should be stopped
        assert collector._flush_task is None or collector._flush_task.done()

    async def test_process_jsonl_line(self, event_collector):
        """Test processing a JSONL line."""
        line = '{"type":"log","level":"info","message":"Test message"}'

        await event_collector.process_line("test-job", line)

        # Event should be in the buffer
        sequence = event_collector.get_last_sequence("test-job")
        assert sequence >= 1

    async def test_process_progress_event(self, event_collector):
        """Test that progress events are processed."""
        line = '{"type":"progress","phase":"analyzing","percent":50,"message":"Halfway"}'

        await event_collector.process_line("test-job", line)

        sequence = event_collector.get_last_sequence("test-job")
        assert sequence >= 1

    async def test_process_checkpoint_event(self, event_collector):
        """Test that checkpoint events are processed."""
        line = '{"type":"checkpoint","id":"chk_001","phase":"test","percent":50,"state":{"items":10}}'

        await event_collector.process_line("test-job", line)

        sequence = event_collector.get_last_sequence("test-job")
        assert sequence >= 1

    async def test_process_raw_text(self, event_collector):
        """Test processing plain text output."""
        line = "Some plain text output"

        await event_collector.process_line("test-job", line)

        sequence = event_collector.get_last_sequence("test-job")
        assert sequence >= 1

    async def test_empty_line_ignored(self, event_collector):
        """Test that empty lines are ignored."""
        await event_collector.process_line("test-job", "")
        await event_collector.process_line("test-job", "   ")

        sequence = event_collector.get_last_sequence("test-job")
        assert sequence == 0

    async def test_get_events_since(self, event_collector):
        """Test getting events since a sequence number."""
        for i in range(5):
            line = f'{{"type":"log","level":"info","message":"Message {i}"}}'
            await event_collector.process_line("test-job", line)

        # Get events since sequence 2
        events = event_collector.get_events_since("test-job", 2)

        # Should get events 3, 4, 5 (0-indexed: 2, 3, 4)
        assert len(events) >= 2

    async def test_multiple_jobs(self, event_collector):
        """Test collecting events for multiple jobs."""
        await event_collector.process_line("job-1", '{"type":"log","message":"Job 1 event"}')
        await event_collector.process_line("job-2", '{"type":"log","message":"Job 2 event"}')
        await event_collector.process_line("job-1", '{"type":"log","message":"Job 1 second event"}')

        seq1 = event_collector.get_last_sequence("job-1")
        seq2 = event_collector.get_last_sequence("job-2")

        assert seq1 == 2  # Two events for job-1
        assert seq2 == 1  # One event for job-2

    async def test_sse_publisher_callback(self, event_collector):
        """Test that SSE publisher is called."""
        published_events = []

        async def mock_publisher(job_id: str, event_type: str, data: dict):
            published_events.append((job_id, event_type, data))

        event_collector.set_sse_publisher(mock_publisher)

        await event_collector.process_line(
            "test-job",
            '{"type":"log","level":"info","message":"Test"}'
        )

        # Wait a bit for async processing
        await asyncio.sleep(0.1)

        assert len(published_events) >= 1
        assert published_events[0][0] == "test-job"

    async def test_finalize_job_success(self, event_collector, db_session):
        """Test finalizing a successful job."""
        from portal.models import Job, JobType, JobStatus
        import uuid

        # Create a job in the database first
        job_id = uuid.uuid4().hex
        job = Job(
            id=job_id,
            job_type=JobType.PLAN,
            status=JobStatus.RUNNING,
            parameters={"spec_id": "test-001"},
        )
        db_session.add(job)
        await db_session.commit()

        published_events = []

        async def mock_publisher(job_id: str, event_type: str, data: dict):
            published_events.append((job_id, event_type, data))

        event_collector.set_sse_publisher(mock_publisher)

        # Process some events first
        await event_collector.process_line(
            job_id,
            '{"type":"log","message":"Working..."}'
        )

        # Finalize - this publishes to SSE, not the buffer
        await event_collector.finalize_job(job_id, exit_code=0)

        # Check SSE published the status event
        status_events = [e for e in published_events if e[1] == "status"]
        assert len(status_events) >= 1
        assert status_events[-1][2].get("status") == "succeeded"
        assert status_events[-1][2].get("exit_code") == 0

    async def test_finalize_job_failure(self, event_collector, db_session):
        """Test finalizing a failed job."""
        from portal.models import Job, JobType, JobStatus
        import uuid

        # Create a job in the database first
        job_id = uuid.uuid4().hex
        job = Job(
            id=job_id,
            job_type=JobType.PLAN,
            status=JobStatus.RUNNING,
            parameters={"spec_id": "test-001"},
        )
        db_session.add(job)
        await db_session.commit()

        published_events = []

        async def mock_publisher(job_id: str, event_type: str, data: dict):
            published_events.append((job_id, event_type, data))

        event_collector.set_sse_publisher(mock_publisher)

        await event_collector.finalize_job(
            job_id,
            exit_code=1,
            error_message="Something went wrong"
        )

        # Check SSE published the status event with failure
        status_events = [e for e in published_events if e[1] == "status"]
        assert len(status_events) >= 1
        assert status_events[-1][2].get("status") == "failed"
        assert status_events[-1][2].get("exit_code") == 1
        assert status_events[-1][2].get("error") == "Something went wrong"

    async def test_buffer_max_size(self):
        """Test that buffer respects max size."""
        from portal.services import EventCollector

        collector = EventCollector(buffer_size=10, batch_size=5, flush_interval=0.5)
        await collector.start()

        try:
            # Add more events than buffer size
            for i in range(20):
                await collector.process_line(
                    "test-job",
                    f'{{"type":"log","message":"Event {i}"}}'
                )

            # Buffer should be trimmed
            events = collector.get_events_since("test-job", 0)
            assert len(events) <= 10
        finally:
            await collector.stop()

    async def test_high_throughput(self, event_collector):
        """Test handling high event throughput."""
        # Rapidly add many events
        for i in range(100):
            await event_collector.process_line(
                "test-job",
                f'{{"type":"log","level":"info","message":"Line {i}"}}'
            )

        # Should handle without error
        sequence = event_collector.get_last_sequence("test-job")
        assert sequence == 100

    async def test_concurrent_jobs_processing(self, event_collector):
        """Test processing events for multiple jobs concurrently."""
        async def process_job_events(job_id: str, count: int):
            for i in range(count):
                await event_collector.process_line(
                    job_id,
                    f'{{"type":"log","message":"Event {i}"}}'
                )
                await asyncio.sleep(0.001)

        # Process events for 3 jobs concurrently
        await asyncio.gather(
            process_job_events("job-a", 20),
            process_job_events("job-b", 20),
            process_job_events("job-c", 20),
        )

        # All jobs should have their events
        assert event_collector.get_last_sequence("job-a") == 20
        assert event_collector.get_last_sequence("job-b") == 20
        assert event_collector.get_last_sequence("job-c") == 20
