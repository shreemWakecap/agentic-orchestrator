"""
Event Collector - Orchestrates event parsing, persistence, and streaming.

The EventCollector is the central hub that:
1. Receives raw output lines from ProcessExecutor
2. Parses them into structured events
3. Persists events to the database
4. Updates job progress
5. Saves checkpoints
6. Publishes to SSE streams
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Awaitable, Set
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select, update

from ..models import Job, JobEvent, Checkpoint, JobStatus, async_session_maker, utcnow
from .jsonl_parser import (
    JSONLParser,
    Event,
    EventType,
    ProgressEvent,
    CheckpointEvent,
    CompleteEvent,
    ErrorEvent,
    event_to_db_dict,
    event_to_sse_dict,
)
from .job_service import JobService

logger = logging.getLogger(__name__)


# Type for SSE publish callback
SSEPublisher = Callable[[str, str, Dict[str, Any]], Awaitable[None]]  # (job_id, event_type, data) -> None


@dataclass
class EventBuffer:
    """Buffer for recent events (for SSE replay)."""
    events: List[Dict[str, Any]]
    max_size: int = 1000

    def add(self, event: Dict[str, Any]):
        """Add event to buffer."""
        self.events.append(event)
        if len(self.events) > self.max_size:
            self.events = self.events[-self.max_size:]

    def get_since(self, sequence: int) -> List[Dict[str, Any]]:
        """Get events since a sequence number."""
        return [e for e in self.events if e.get("sequence", 0) > sequence]


class EventCollector:
    """
    Collects, processes, and distributes job events.

    Usage:
        collector = EventCollector()
        collector.set_sse_publisher(my_sse_publish_func)

        # From ProcessExecutor output callback:
        await collector.process_line(job_id, line)

        # When job completes:
        await collector.finalize_job(job_id, exit_code)
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        batch_size: int = 10,
        flush_interval: float = 1.0,
    ):
        """
        Initialize event collector.

        Args:
            buffer_size: Max events to buffer per job for replay
            batch_size: Number of events before auto-flush to DB
            flush_interval: Seconds between auto-flushes
        """
        self.parser = JSONLParser()
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Per-job state
        self._sequences: Dict[str, int] = defaultdict(int)
        self._buffers: Dict[str, EventBuffer] = {}
        self._pending_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # SSE publisher callback
        self._sse_publisher: Optional[SSEPublisher] = None

        # Active jobs being collected
        self._active_jobs: Set[str] = set()

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None

    def set_sse_publisher(self, publisher: SSEPublisher):
        """Set the SSE publisher callback."""
        self._sse_publisher = publisher

    async def start(self):
        """Start the event collector background tasks."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("Event collector started")

    async def stop(self):
        """Stop the event collector."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Flush any remaining events
        for job_id in list(self._pending_events.keys()):
            await self._flush_events(job_id)

        logger.info("Event collector stopped")

    # =========================================================================
    # Event Processing
    # =========================================================================

    async def process_line(self, job_id: str, line: str):
        """
        Process a single output line from a job.

        Args:
            job_id: Job identifier
            line: Raw output line
        """
        # Parse the line
        event = self.parser.parse_line(line)
        if not event:
            return

        # Track job as active
        self._active_jobs.add(job_id)

        # Assign sequence number
        self._sequences[job_id] += 1
        sequence = self._sequences[job_id]

        # Convert to DB format
        db_event = event_to_db_dict(event, job_id, sequence)
        self._pending_events[job_id].append(db_event)

        # Convert to SSE format and buffer
        sse_event = event_to_sse_dict(event, sequence)
        sse_event["sequence"] = sequence

        if job_id not in self._buffers:
            self._buffers[job_id] = EventBuffer([], self.buffer_size)
        self._buffers[job_id].add(sse_event)

        # Publish to SSE immediately
        if self._sse_publisher:
            try:
                await self._sse_publisher(job_id, event.type.value, sse_event)
            except Exception as e:
                logger.error(f"SSE publish error: {e}")

        # Handle special events
        await self._handle_special_event(job_id, event, sequence)

        # Auto-flush if batch full
        if len(self._pending_events[job_id]) >= self.batch_size:
            await self._flush_events(job_id)

    async def _handle_special_event(self, job_id: str, event: Event, sequence: int):
        """Handle events that require additional processing."""
        async with async_session_maker() as session:
            if isinstance(event, ProgressEvent):
                # Update job progress
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        progress_phase=event.phase,
                        progress_percent=event.percent,
                        progress_message=event.message,
                    )
                )
                await session.commit()

            elif isinstance(event, CheckpointEvent):
                # Save checkpoint
                checkpoint = Checkpoint(
                    id=event.checkpoint_id,
                    job_id=job_id,
                    created_at=event.timestamp,
                    phase=event.phase,
                    progress_percent=event.percent,
                    state_data=event.state_data,
                )
                session.add(checkpoint)

                # Update job's last checkpoint reference
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(last_checkpoint_id=event.checkpoint_id)
                )
                await session.commit()
                logger.info(f"Saved checkpoint {event.checkpoint_id} for job {job_id}")

            elif isinstance(event, ErrorEvent):
                # Log error but don't update job status (let finalize handle it)
                logger.warning(f"Job {job_id} error: {event.message}")

    # =========================================================================
    # Job Finalization
    # =========================================================================

    async def finalize_job(
        self,
        job_id: str,
        exit_code: int,
        error_message: Optional[str] = None,
    ):
        """
        Finalize a job after process completes.

        Args:
            job_id: Job identifier
            exit_code: Process exit code
            error_message: Optional error message
        """
        # Flush any pending events
        await self._flush_events(job_id)

        # Update job status
        async with async_session_maker() as session:
            service = JobService(session)
            job = await service.get_job(job_id)

            if not job:
                logger.error(f"Cannot finalize unknown job {job_id}")
                return

            if exit_code == 0:
                await service.mark_job_succeeded(job_id, exit_code)
            else:
                # Check if job has checkpoint for resumable status
                has_checkpoint = job.last_checkpoint_id is not None
                await service.mark_job_failed(
                    job_id,
                    error_message or f"Exit code {exit_code}",
                    exit_code,
                    has_checkpoint=has_checkpoint,
                )

            await session.commit()

        # Publish final status event
        if self._sse_publisher:
            status = "succeeded" if exit_code == 0 else "failed"
            await self._sse_publisher(job_id, "status", {
                "status": status,
                "exit_code": exit_code,
                "error": error_message,
                "timestamp": utcnow().isoformat(),
            })

        # Cleanup
        self._active_jobs.discard(job_id)
        logger.info(f"Finalized job {job_id} with exit code {exit_code}")

    # =========================================================================
    # Database Persistence
    # =========================================================================

    async def _flush_events(self, job_id: str):
        """Flush pending events for a job to the database."""
        events = self._pending_events.pop(job_id, [])
        if not events:
            return

        try:
            async with async_session_maker() as session:
                for event_data in events:
                    event = JobEvent(
                        job_id=event_data["job_id"],
                        sequence=event_data["sequence"],
                        event_type=event_data["event_type"],
                        timestamp=event_data["timestamp"],
                        data=event_data["data"],
                        log_level=event_data.get("log_level"),
                    )
                    session.add(event)
                await session.commit()

            logger.debug(f"Flushed {len(events)} events for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to flush events for job {job_id}: {e}")
            # Put events back for retry
            self._pending_events[job_id] = events + self._pending_events.get(job_id, [])

    async def _flush_loop(self):
        """Background task to periodically flush events."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)

                # Flush all active jobs
                for job_id in list(self._pending_events.keys()):
                    if self._pending_events[job_id]:
                        await self._flush_events(job_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    # =========================================================================
    # Event Retrieval (for SSE replay)
    # =========================================================================

    def get_buffered_events(self, job_id: str, since_sequence: int = 0) -> List[Dict[str, Any]]:
        """
        Get buffered events for replay.

        Args:
            job_id: Job identifier
            since_sequence: Only return events after this sequence

        Returns:
            List of events for SSE streaming
        """
        buffer = self._buffers.get(job_id)
        if not buffer:
            return []
        return buffer.get_since(since_sequence)

    def get_events_since(self, job_id: str, since_sequence: int = 0) -> List[Dict[str, Any]]:
        """
        Alias for get_buffered_events for API compatibility.

        Args:
            job_id: Job identifier
            since_sequence: Only return events after this sequence

        Returns:
            List of events for SSE streaming
        """
        return self.get_buffered_events(job_id, since_sequence)

    async def get_events_from_db(
        self,
        job_id: str,
        since_sequence: int = 0,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get events from database.

        Args:
            job_id: Job identifier
            since_sequence: Only return events after this sequence
            limit: Maximum events to return

        Returns:
            List of events
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .where(JobEvent.sequence > since_sequence)
                .order_by(JobEvent.sequence)
                .limit(limit)
            )
            events = result.scalars().all()

            return [
                {
                    "sequence": e.sequence,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "data": e.data,
                    "log_level": e.log_level,
                }
                for e in events
            ]

    def is_job_active(self, job_id: str) -> bool:
        """Check if a job is currently being collected."""
        return job_id in self._active_jobs

    def get_last_sequence(self, job_id: str) -> int:
        """Get the last sequence number for a job."""
        return self._sequences.get(job_id, 0)


# Singleton instance
_collector: Optional[EventCollector] = None


def get_event_collector() -> EventCollector:
    """Get the global event collector instance."""
    global _collector
    if _collector is None:
        _collector = EventCollector()
    return _collector


async def init_event_collector() -> EventCollector:
    """Initialize and start the global event collector."""
    global _collector
    _collector = EventCollector()
    await _collector.start()
    return _collector


async def shutdown_event_collector():
    """Shutdown the global event collector."""
    global _collector
    if _collector:
        await _collector.stop()
        _collector = None
