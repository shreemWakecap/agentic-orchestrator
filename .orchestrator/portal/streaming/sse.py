"""
SSE Streaming - Server-Sent Events implementation for job updates.

Provides real-time event streaming to browser clients with:
- Connection management
- Event replay on reconnect
- Automatic cleanup
- Backpressure handling
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Set, AsyncIterator, Any
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ..models import async_session_maker, Job, JobStatus
from ..services import get_event_collector, JobService

logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """Represents a client SSE connection."""
    id: str
    job_id: str
    queue: asyncio.Queue
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_event_id: int = 0
    closed: bool = False
    callback: Optional[Any] = None  # Optional async callback for programmatic use


class SSEManager:
    """
    Manages SSE connections and event distribution.

    Usage:
        manager = SSEManager()

        # In FastAPI route:
        @app.get("/jobs/{job_id}/stream")
        async def stream(job_id: str, request: Request):
            return await manager.create_stream(job_id, request)

        # Publishing events:
        await manager.publish(job_id, "progress", {...})
    """

    def __init__(
        self,
        max_connections_per_job: int = 100,
        queue_size: int = 100,
        heartbeat_interval: float = 30.0,
    ):
        """
        Initialize SSE manager.

        Args:
            max_connections_per_job: Max concurrent SSE connections per job
            queue_size: Event queue size per connection
            heartbeat_interval: Seconds between heartbeat comments
        """
        self.max_connections_per_job = max_connections_per_job
        self.queue_size = queue_size
        self.heartbeat_interval = heartbeat_interval

        # Connection tracking
        self._connections: Dict[str, Dict[str, SSEConnection]] = defaultdict(dict)
        self._connection_counter = 0

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Persisted events buffer for replay (job_id -> list of events)
        self._persisted_events: Dict[str, list] = defaultdict(list)
        self._event_sequence: Dict[str, int] = defaultdict(int)

    @property
    def is_running(self) -> bool:
        """Check if the SSE manager is running."""
        return self._heartbeat_task is not None and not self._heartbeat_task.done()

    async def start(self):
        """Start the SSE manager."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("SSE manager started")

    async def stop(self):
        """Stop the SSE manager and close all connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Close all connections
        for job_id in list(self._connections.keys()):
            for conn in list(self._connections[job_id].values()):
                await self._close_connection(conn)

        logger.info("SSE manager stopped")

    # =========================================================================
    # Connection Management
    # =========================================================================

    def _generate_connection_id(self) -> str:
        """Generate unique connection ID."""
        self._connection_counter += 1
        return f"conn_{self._connection_counter}"

    async def _create_connection(
        self,
        job_id: str,
        last_event_id: int = 0,
    ) -> Optional[SSEConnection]:
        """Create a new SSE connection."""
        # Check connection limit
        if len(self._connections[job_id]) >= self.max_connections_per_job:
            logger.warning(f"Connection limit reached for job {job_id}")
            return None

        conn_id = self._generate_connection_id()
        conn = SSEConnection(
            id=conn_id,
            job_id=job_id,
            queue=asyncio.Queue(maxsize=self.queue_size),
            last_event_id=last_event_id,
        )

        self._connections[job_id][conn_id] = conn
        logger.debug(f"Created SSE connection {conn_id} for job {job_id}")
        return conn

    async def _close_connection(self, conn: SSEConnection):
        """Close an SSE connection."""
        conn.closed = True
        self._connections[conn.job_id].pop(conn.id, None)

        # Clean up empty job entries
        if not self._connections[conn.job_id]:
            del self._connections[conn.job_id]

        logger.debug(f"Closed SSE connection {conn.id} for job {conn.job_id}")

    def get_connection_count(self, job_id: str) -> int:
        """Get number of connections for a job."""
        return len(self._connections.get(job_id, {}))

    def get_total_connections(self) -> int:
        """Get total number of connections."""
        return sum(len(conns) for conns in self._connections.values())

    async def register_connection(
        self,
        job_id: str,
        callback: Optional[Any] = None,
        last_event_id: int = 0,
    ) -> Optional[str]:
        """
        Register a new SSE connection (public API).

        Args:
            job_id: Job identifier
            callback: Optional async callback function(data) for programmatic use
            last_event_id: Last received event ID for replay

        Returns:
            Connection ID if successful, None if at limit
        """
        conn = await self._create_connection(job_id, last_event_id)
        if conn is None:
            return None
        conn.callback = callback

        # Replay persisted events if callback is provided
        if callback is not None:
            persisted = self._persisted_events.get(job_id, [])
            for event in persisted:
                if event.get("sequence", 0) > last_event_id:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.warning(f"Replay callback error: {e}")

        return conn.id

    async def unregister_connection(self, job_id: str, connection_id: str):
        """
        Unregister an SSE connection.

        Args:
            job_id: Job identifier
            connection_id: Connection ID returned from register_connection
        """
        connections = self._connections.get(job_id, {})
        conn = connections.get(connection_id)
        if conn:
            await self._close_connection(conn)

    # =========================================================================
    # Event Publishing
    # =========================================================================

    async def publish(
        self,
        job_id: str,
        event_type: str,
        data: Dict[str, Any],
        persist: bool = False,
    ):
        """
        Publish an event to all connections for a job.

        Args:
            job_id: Job identifier
            event_type: Event type name
            data: Event data
            persist: Whether to persist for replay
        """
        # Assign sequence number
        self._event_sequence[job_id] += 1
        sequence = data.get("sequence", self._event_sequence[job_id])

        # Store persisted events for replay
        if persist:
            self._persisted_events[job_id].append({
                "type": event_type,
                "sequence": sequence,
                **data,
            })

        connections = self._connections.get(job_id, {})
        if not connections:
            return

        event_str = self._format_event(event_type, data, sequence)

        # Prepare callback data
        callback_data = {"type": event_type, "sequence": sequence, **data}

        for conn in list(connections.values()):
            if conn.closed:
                continue

            # Call callback if registered (for programmatic use)
            # Use create_task to avoid blocking on slow callbacks
            if conn.callback is not None:
                async def run_callback(callback, data, conn_id):
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except Exception as e:
                        logger.warning(f"Callback error for {conn_id}: {e}")

                asyncio.create_task(run_callback(conn.callback, callback_data.copy(), conn.id))

            # Queue for SSE streaming
            try:
                conn.queue.put_nowait(event_str)
            except asyncio.QueueFull:
                # Drop old events under backpressure
                try:
                    conn.queue.get_nowait()
                    conn.queue.put_nowait(event_str)
                except:
                    pass

    def _format_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: int = 0,
    ) -> str:
        """Format an SSE event string."""
        lines = []
        if event_id:
            lines.append(f"id: {event_id}")
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        lines.append("")  # Empty line terminates event
        return "\n".join(lines) + "\n"

    # =========================================================================
    # Streaming
    # =========================================================================

    async def create_stream(
        self,
        job_id: str,
        request: Request,
        last_event_id: Optional[int] = None,
    ) -> StreamingResponse:
        """
        Create an SSE streaming response for a job.

        Args:
            job_id: Job identifier
            request: FastAPI request object
            last_event_id: Last received event ID for replay

        Returns:
            StreamingResponse for SSE
        """
        # Parse Last-Event-ID header
        if last_event_id is None:
            header_value = request.headers.get("Last-Event-ID", "0")
            try:
                last_event_id = int(header_value)
            except ValueError:
                last_event_id = 0

        # Create connection
        conn = await self._create_connection(job_id, last_event_id)
        if not conn:
            # Return error response if at limit
            return StreamingResponse(
                content="event: error\ndata: {\"message\": \"Connection limit reached\"}\n\n",
                media_type="text/event-stream",
                status_code=503,
            )

        async def event_generator() -> AsyncIterator[str]:
            try:
                # Send initial connection event
                yield self._format_event("connected", {
                    "job_id": job_id,
                    "connection_id": conn.id,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                # Replay missed events
                async for event in self._replay_events(job_id, last_event_id):
                    if conn.closed:
                        break
                    yield event

                # Stream live events
                while not conn.closed:
                    try:
                        # Check if client disconnected
                        if await request.is_disconnected():
                            break

                        # Wait for next event with timeout
                        try:
                            event = await asyncio.wait_for(
                                conn.queue.get(),
                                timeout=self.heartbeat_interval
                            )
                            yield event
                        except asyncio.TimeoutError:
                            # Send heartbeat comment
                            yield f": heartbeat {datetime.utcnow().isoformat()}\n\n"

                    except asyncio.CancelledError:
                        break

            finally:
                await self._close_connection(conn)

        return StreamingResponse(
            content=event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    async def _replay_events(
        self,
        job_id: str,
        since_sequence: int,
    ) -> AsyncIterator[str]:
        """Replay events from buffer and database."""
        collector = get_event_collector()

        # First try in-memory buffer
        buffered = collector.get_buffered_events(job_id, since_sequence)

        if buffered:
            for event in buffered:
                yield self._format_event(
                    event.get("event_type", "log"),
                    event,
                    event.get("sequence", 0)
                )
        else:
            # Fall back to database
            db_events = await collector.get_events_from_db(job_id, since_sequence)
            for event in db_events:
                yield self._format_event(
                    event.get("event_type", "log"),
                    event,
                    event.get("sequence", 0)
                )

        # Send current job status
        async with async_session_maker() as session:
            service = JobService(session)
            job = await service.get_job(job_id)

            if job:
                yield self._format_event("status", {
                    "status": job.status.value,
                    "progress": {
                        "phase": job.progress_phase,
                        "percent": job.progress_percent,
                        "message": job.progress_message,
                    } if job.progress_phase else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                })

                # If job is terminal, send complete event
                if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    yield self._format_event("complete", {
                        "status": job.status.value,
                        "exit_code": job.exit_code,
                        "error": job.error_message,
                        "timestamp": job.completed_at.isoformat() if job.completed_at else None,
                    })

    # =========================================================================
    # Heartbeat
    # =========================================================================

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to all connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                # Send heartbeat to all connections with callbacks
                await self._send_heartbeats()
            except asyncio.CancelledError:
                break

    async def _send_heartbeats(self):
        """Send heartbeat to all connections with callbacks."""
        heartbeat_data = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
        }

        for job_id, connections in list(self._connections.items()):
            for conn in list(connections.values()):
                if conn.closed or conn.callback is None:
                    continue

                try:
                    if asyncio.iscoroutinefunction(conn.callback):
                        await conn.callback(heartbeat_data)
                    else:
                        conn.callback(heartbeat_data)
                except Exception as e:
                    logger.warning(f"Heartbeat callback error for {conn.id}: {e}")


# Singleton instance
_manager: Optional[SSEManager] = None


def get_sse_manager() -> SSEManager:
    """Get the global SSE manager instance."""
    global _manager
    if _manager is None:
        _manager = SSEManager()
    return _manager


async def init_sse_manager() -> SSEManager:
    """Initialize and start the global SSE manager."""
    global _manager
    _manager = SSEManager()
    await _manager.start()
    return _manager


async def shutdown_sse_manager():
    """Shutdown the global SSE manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None


# Connect SSE manager to event collector
async def setup_sse_publishing():
    """Wire up SSE manager to receive events from collector."""
    collector = get_event_collector()
    manager = get_sse_manager()

    async def sse_publisher(job_id: str, event_type: str, data: dict):
        await manager.publish(job_id, event_type, data)

    collector.set_sse_publisher(sse_publisher)
    logger.info("SSE publishing connected to event collector")
