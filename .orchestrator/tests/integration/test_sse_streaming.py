"""
Integration tests for SSE streaming.

Tests the Server-Sent Events streaming functionality.
"""
import asyncio
import pytest


@pytest.mark.asyncio
class TestSSEStreaming:
    """Tests for SSE streaming functionality."""

    async def test_sse_manager_lifecycle(self):
        """Test SSE manager can start and stop."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        assert manager.is_running

        await manager.stop()

        assert not manager.is_running

    async def test_sse_connection_registration(self):
        """Test registering SSE connections."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        try:
            # Register a connection for a job
            connection_id = await manager.register_connection("test-job-id")

            assert connection_id is not None

            # Should have one connection for the job
            assert manager.get_connection_count("test-job-id") == 1

            # Unregister
            await manager.unregister_connection("test-job-id", connection_id)

            assert manager.get_connection_count("test-job-id") == 0
        finally:
            await manager.stop()

    async def test_sse_publish_event(self):
        """Test publishing events to SSE connections."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        received_events = []

        try:
            # Register connection with callback
            async def event_callback(event_data):
                received_events.append(event_data)

            await manager.register_connection(
                "test-job-id",
                callback=event_callback
            )

            # Publish an event
            await manager.publish(
                "test-job-id",
                event_type="log",
                data={"message": "Test log message"}
            )

            # Wait for async delivery
            await asyncio.sleep(0.1)

            # Should have received the event
            assert len(received_events) >= 1
        finally:
            await manager.stop()

    async def test_sse_broadcast_to_multiple_connections(self):
        """Test broadcasting to multiple connections."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        received_by_conn1 = []
        received_by_conn2 = []

        try:
            async def callback1(data):
                received_by_conn1.append(data)

            async def callback2(data):
                received_by_conn2.append(data)

            await manager.register_connection("test-job", callback=callback1)
            await manager.register_connection("test-job", callback=callback2)

            assert manager.get_connection_count("test-job") == 2

            # Publish
            await manager.publish("test-job", "progress", {"percent": 50})

            await asyncio.sleep(0.1)

            # Both should receive
            assert len(received_by_conn1) >= 1
            assert len(received_by_conn2) >= 1
        finally:
            await manager.stop()

    async def test_sse_isolated_jobs(self):
        """Test that events are isolated per job."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        job1_events = []
        job2_events = []

        try:
            async def job1_callback(data):
                job1_events.append(data)

            async def job2_callback(data):
                job2_events.append(data)

            await manager.register_connection("job-1", callback=job1_callback)
            await manager.register_connection("job-2", callback=job2_callback)

            # Publish to job-1 only
            await manager.publish("job-1", "log", {"message": "Job 1 event"})

            await asyncio.sleep(0.1)

            # Only job-1 should receive
            assert len(job1_events) >= 1
            assert len(job2_events) == 0
        finally:
            await manager.stop()

    async def test_sse_connection_cleanup_on_disconnect(self):
        """Test connection cleanup when client disconnects."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        try:
            conn_id = await manager.register_connection("test-job")

            assert manager.get_connection_count("test-job") == 1

            # Simulate disconnect
            await manager.unregister_connection("test-job", conn_id)

            assert manager.get_connection_count("test-job") == 0

            # Publishing should not error
            await manager.publish("test-job", "log", {"message": "No listeners"})
        finally:
            await manager.stop()

    async def test_sse_heartbeat(self):
        """Test SSE heartbeat functionality."""
        from portal.streaming import SSEManager

        manager = SSEManager(heartbeat_interval=0.1)
        await manager.start()

        heartbeats = []

        try:
            async def callback(data):
                if data.get("type") == "heartbeat":
                    heartbeats.append(data)

            await manager.register_connection("test-job", callback=callback)

            # Wait for heartbeats
            await asyncio.sleep(0.35)

            # Should have received heartbeats
            assert len(heartbeats) >= 2
        finally:
            await manager.stop()

    async def test_sse_replay_missed_events(self):
        """Test replaying events for reconnecting clients."""
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        try:
            # Add events while no client connected
            await manager.publish("test-job", "log", {"message": "Event 1"}, persist=True)
            await manager.publish("test-job", "log", {"message": "Event 2"}, persist=True)

            received = []

            async def callback(data):
                received.append(data)

            # Connect with last_event_id to get replay
            await manager.register_connection(
                "test-job",
                callback=callback,
                last_event_id=0
            )

            await asyncio.sleep(0.1)

            # Should receive replayed events
            assert len(received) >= 2
        finally:
            await manager.stop()


@pytest.mark.asyncio
class TestSSEIntegrationWithEventCollector:
    """Tests for SSE integration with EventCollector."""

    async def test_event_collector_publishes_to_sse(self):
        """Test that EventCollector publishes events to SSE."""
        from portal.services import EventCollector
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        # Use a long flush interval to avoid database writes during test
        collector = EventCollector(flush_interval=60.0)

        # Wire up SSE publishing
        async def sse_publisher(job_id, event_type, data):
            await manager.publish(job_id, event_type, data)

        collector.set_sse_publisher(sse_publisher)
        await collector.start()

        received = []

        try:
            async def callback(data):
                received.append(data)

            await manager.register_connection("test-job", callback=callback)

            # Process events through collector (using log event to avoid DB operations)
            await collector.process_line(
                "test-job",
                '{"type":"log","level":"info","message":"Test log message"}'
            )

            await asyncio.sleep(0.2)

            # SSE should have received the event
            assert len(received) >= 1
        finally:
            # Clear pending events to avoid database operations on stop
            collector._pending_events.clear()
            await collector.stop()
            await manager.stop()
