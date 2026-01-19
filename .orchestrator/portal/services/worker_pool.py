"""
Worker Pool - Manages bounded concurrent job execution.

The worker pool:
1. Maintains a fixed number of worker slots
2. Queues jobs when all workers are busy
3. Executes jobs in priority order
4. Handles graceful shutdown
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Callable, Awaitable, Any, List
from dataclasses import dataclass, field
from enum import Enum

from ..models import Job, JobStatus, async_session_maker
from .job_service import JobService

logger = logging.getLogger(__name__)


class WorkerState(str, Enum):
    """Worker state."""
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"


@dataclass
class WorkerInfo:
    """Information about a worker."""
    id: int
    state: WorkerState = WorkerState.IDLE
    current_job_id: Optional[str] = None
    jobs_completed: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueuedJob:
    """Job in the queue with priority."""
    job_id: str
    priority: int
    queued_at: datetime

    def __lt__(self, other):
        # Lower priority number = higher priority
        # If same priority, earlier queued_at wins
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.queued_at < other.queued_at


# Type for the job executor function
JobExecutor = Callable[[str], Awaitable[None]]


class WorkerPool:
    """
    Manages a pool of workers for job execution.

    Usage:
        pool = WorkerPool(max_workers=4)
        pool.set_executor(my_execute_function)
        await pool.start()

        # Submit jobs
        await pool.submit(job_id, priority=2)

        # Shutdown
        await pool.shutdown()
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 100,
    ):
        """
        Initialize worker pool.

        Args:
            max_workers: Maximum concurrent jobs
            max_queue_size: Maximum jobs in queue (0 = unlimited)
        """
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        # Job queue (priority queue)
        self._queue: asyncio.PriorityQueue[QueuedJob] = asyncio.PriorityQueue()

        # Worker tracking
        self._workers: Dict[int, WorkerInfo] = {}
        self._worker_tasks: Dict[int, asyncio.Task] = {}

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_workers)

        # Job executor function (set externally)
        self._executor: Optional[JobExecutor] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Metrics
        self._total_jobs_submitted = 0
        self._total_jobs_completed = 0
        self._total_jobs_failed = 0

    def set_executor(self, executor: JobExecutor):
        """Set the job executor function."""
        self._executor = executor

    @property
    def is_running(self) -> bool:
        """Check if pool is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    @property
    def active_workers(self) -> int:
        """Number of workers currently executing jobs."""
        return sum(1 for w in self._workers.values() if w.state == WorkerState.BUSY)

    @property
    def idle_workers(self) -> int:
        """Number of idle workers."""
        return self.max_workers - self.active_workers

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self):
        """Start the worker pool."""
        if self._running:
            logger.warning("Worker pool already running")
            return

        if not self._executor:
            raise RuntimeError("No executor set. Call set_executor() first.")

        logger.info(f"Starting worker pool with {self.max_workers} workers")
        self._running = True
        self._shutdown_event.clear()

        # Initialize workers
        for i in range(self.max_workers):
            self._workers[i] = WorkerInfo(id=i)
            task = asyncio.create_task(self._worker_loop(i))
            self._worker_tasks[i] = task

        logger.info("Worker pool started")

    async def shutdown(self, timeout: float = 30.0):
        """
        Gracefully shutdown the worker pool.

        Args:
            timeout: Max seconds to wait for jobs to complete
        """
        if not self._running:
            return

        logger.info("Shutting down worker pool...")
        self._running = False
        self._shutdown_event.set()

        # Mark all workers as stopping
        for worker in self._workers.values():
            if worker.state == WorkerState.IDLE:
                worker.state = WorkerState.STOPPING

        # Wait for workers to finish current jobs
        if self._worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._worker_tasks.values(), return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown timeout after {timeout}s, cancelling workers")
                for task in self._worker_tasks.values():
                    task.cancel()

        self._workers.clear()
        self._worker_tasks.clear()
        logger.info("Worker pool shutdown complete")

    # =========================================================================
    # Job Submission
    # =========================================================================

    async def submit(self, job_id: str, priority: int = 3) -> bool:
        """
        Submit a job for execution.

        Args:
            job_id: Job identifier
            priority: Priority (1=high, 5=low)

        Returns:
            True if submitted, False if queue full
        """
        if not self._running:
            raise RuntimeError("Worker pool not running")

        # Check queue capacity
        if self.max_queue_size > 0 and self._queue.qsize() >= self.max_queue_size:
            logger.warning(f"Queue full, rejecting job {job_id}")
            return False

        queued_job = QueuedJob(
            job_id=job_id,
            priority=priority,
            queued_at=datetime.utcnow()
        )

        await self._queue.put(queued_job)
        self._total_jobs_submitted += 1

        logger.debug(f"Job {job_id} queued with priority {priority}")
        return True

    def get_queue_position(self, job_id: str) -> Optional[int]:
        """
        Get position of a job in the queue.

        Returns None if not in queue (may be running or not submitted).
        Note: This is approximate as queue may change.
        """
        # Convert queue to list (expensive, use sparingly)
        items = list(self._queue._queue)  # Access internal deque
        for i, item in enumerate(items):
            if item.job_id == job_id:
                return i + 1
        return None

    # =========================================================================
    # Worker Loop
    # =========================================================================

    async def _worker_loop(self, worker_id: int):
        """Main loop for a worker."""
        worker = self._workers[worker_id]
        logger.debug(f"Worker {worker_id} started")

        while self._running or not self._queue.empty():
            try:
                # Wait for a job with timeout (allows checking shutdown)
                try:
                    queued_job = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Execute the job
                worker.state = WorkerState.BUSY
                worker.current_job_id = queued_job.job_id

                try:
                    async with self._semaphore:
                        await self._execute_job(worker_id, queued_job.job_id)
                        worker.jobs_completed += 1
                        self._total_jobs_completed += 1
                except Exception as e:
                    logger.error(f"Worker {worker_id} job {queued_job.job_id} failed: {e}")
                    self._total_jobs_failed += 1
                finally:
                    worker.state = WorkerState.IDLE
                    worker.current_job_id = None
                    self._queue.task_done()

            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                logger.exception(f"Worker {worker_id} unexpected error: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on errors

        worker.state = WorkerState.STOPPING
        logger.debug(f"Worker {worker_id} stopped")

    async def _execute_job(self, worker_id: int, job_id: str):
        """Execute a single job."""
        logger.info(f"Worker {worker_id} executing job {job_id}")

        # Update job status to running
        async with async_session_maker() as session:
            service = JobService(session)
            await service.mark_job_running(job_id)
            await session.commit()

        # Call the executor
        try:
            await self._executor(job_id)
        except Exception as e:
            # Mark job as failed
            async with async_session_maker() as session:
                service = JobService(session)
                await service.mark_job_failed(job_id, str(e))
                await session.commit()
            raise

    # =========================================================================
    # Monitoring
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get pool status."""
        return {
            "running": self._running,
            "max_workers": self.max_workers,
            "active_workers": self.active_workers,
            "idle_workers": self.idle_workers,
            "queue_size": self.queue_size,
            "max_queue_size": self.max_queue_size,
            "total_submitted": self._total_jobs_submitted,
            "total_completed": self._total_jobs_completed,
            "total_failed": self._total_jobs_failed,
            "workers": [
                {
                    "id": w.id,
                    "state": w.state.value,
                    "current_job": w.current_job_id,
                    "jobs_completed": w.jobs_completed,
                }
                for w in self._workers.values()
            ]
        }

    def get_worker_status(self, worker_id: int) -> Optional[Dict[str, Any]]:
        """Get status of a specific worker."""
        worker = self._workers.get(worker_id)
        if not worker:
            return None
        return {
            "id": worker.id,
            "state": worker.state.value,
            "current_job": worker.current_job_id,
            "jobs_completed": worker.jobs_completed,
            "started_at": worker.started_at.isoformat(),
        }


# Singleton instance
_pool: Optional[WorkerPool] = None


def get_worker_pool() -> WorkerPool:
    """Get the global worker pool instance."""
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool


async def init_worker_pool(
    max_workers: int = 4,
    executor: Optional[JobExecutor] = None,
) -> WorkerPool:
    """Initialize and start the global worker pool."""
    global _pool
    _pool = WorkerPool(max_workers=max_workers)
    if executor:
        _pool.set_executor(executor)
    return _pool


async def shutdown_worker_pool():
    """Shutdown the global worker pool."""
    global _pool
    if _pool:
        await _pool.shutdown()
        _pool = None
