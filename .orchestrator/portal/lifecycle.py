"""
Application Lifecycle Management

Handles startup and shutdown procedures:
- Database initialization
- Worker pool startup/shutdown
- Orphan recovery
- Event collector management
- SSE manager lifecycle
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from contextlib import asynccontextmanager

from .models import (
    init_db, close_db, async_session_maker,
    Job, JobStatus, utcnow
)
from .services import (
    JobService,
    init_worker_pool, shutdown_worker_pool, get_worker_pool,
    init_process_executor, get_process_executor,
    init_event_collector, shutdown_event_collector, get_event_collector,
)
from .streaming import (
    init_sse_manager, shutdown_sse_manager, setup_sse_publishing
)

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Manages application startup and shutdown.

    Usage:
        lifecycle = LifecycleManager()

        # In FastAPI app:
        @asynccontextmanager
        async def lifespan(app):
            await lifecycle.startup()
            yield
            await lifecycle.shutdown()

        app = FastAPI(lifespan=lifespan)
    """

    def __init__(
        self,
        max_workers: int = 4,
        graceful_timeout: float = 30.0,
        orphan_recovery: bool = True,
    ):
        """
        Initialize lifecycle manager.

        Args:
            max_workers: Maximum concurrent workers
            graceful_timeout: Timeout for graceful shutdown (seconds)
            orphan_recovery: Whether to recover orphaned jobs on startup
        """
        self.max_workers = max_workers
        self.graceful_timeout = graceful_timeout
        self.orphan_recovery = orphan_recovery

        self._shutdown_event = asyncio.Event()
        self._startup_complete = False

    # =========================================================================
    # Startup
    # =========================================================================

    async def startup(self) -> None:
        """Initialize all services on application startup."""
        logger.info("Starting application lifecycle...")

        try:
            # 1. Initialize database
            logger.info("Initializing database...")
            await init_db()

            # 2. Handle orphaned jobs
            if self.orphan_recovery:
                await self._recover_orphaned_jobs()

            # 3. Initialize process executor
            logger.info("Initializing process executor...")
            init_process_executor()

            # 4. Initialize event collector
            logger.info("Initializing event collector...")
            await init_event_collector()

            # 5. Initialize SSE manager
            logger.info("Initializing SSE manager...")
            await init_sse_manager()
            await setup_sse_publishing()

            # 6. Initialize and start worker pool
            logger.info(f"Initializing worker pool with {self.max_workers} workers...")
            await init_worker_pool(max_workers=self.max_workers)
            pool = get_worker_pool()
            pool.set_executor(self._execute_job)
            await pool.start()

            # 7. Re-queue any pending jobs
            await self._requeue_pending_jobs()

            self._startup_complete = True
            logger.info("Application startup complete")

        except Exception as e:
            logger.error(f"Startup failed: {e}")
            await self.shutdown()
            raise

    async def _recover_orphaned_jobs(self) -> None:
        """Mark any running jobs from previous run as orphaned."""
        logger.info("Checking for orphaned jobs...")

        async with async_session_maker() as session:
            service = JobService(session)
            count = await service.mark_orphaned_jobs()
            await session.commit()

            if count > 0:
                logger.warning(f"Marked {count} orphaned jobs as failed/resumable")

    async def _requeue_pending_jobs(self) -> None:
        """Re-submit pending/queued jobs to the worker pool."""
        logger.info("Re-queuing pending jobs...")

        async with async_session_maker() as session:
            service = JobService(session)
            jobs = await service.get_queued_jobs(limit=100)

            pool = get_worker_pool()
            requeued = 0

            for job in jobs:
                if await pool.submit(job.id, priority=job.priority):
                    requeued += 1

            if requeued > 0:
                logger.info(f"Re-queued {requeued} pending jobs")

    # =========================================================================
    # Shutdown
    # =========================================================================

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Starting graceful shutdown...")

        self._shutdown_event.set()

        try:
            # 1. Stop accepting new jobs (worker pool stops picking up)
            pool = get_worker_pool()
            if pool and pool.is_running:
                logger.info("Stopping worker pool...")
                await pool.shutdown(timeout=self.graceful_timeout)

            # 2. Cancel running processes
            await self._cancel_running_processes()

            # 3. Shutdown SSE manager (close all connections)
            logger.info("Shutting down SSE manager...")
            await shutdown_sse_manager()

            # 4. Shutdown event collector (flush pending events)
            logger.info("Shutting down event collector...")
            await shutdown_event_collector()

            # 5. Mark any remaining running jobs as orphaned
            await self._mark_interrupted_jobs()

            # 6. Close database connections
            logger.info("Closing database connections...")
            await close_db()

            logger.info("Graceful shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            raise

    async def _cancel_running_processes(self) -> None:
        """Cancel all running CLI processes."""
        executor = get_process_executor()
        if not executor:
            return

        running = executor.get_running_jobs()
        if not running:
            return

        logger.info(f"Cancelling {len(running)} running processes...")

        for job_id in running:
            try:
                await executor.cancel(job_id)
            except Exception as e:
                logger.error(f"Failed to cancel process for job {job_id}: {e}")

    async def _mark_interrupted_jobs(self) -> None:
        """Mark any jobs that were interrupted by shutdown."""
        try:
            async with async_session_maker() as session:
                from sqlalchemy import select

                # Find jobs that are still marked as running
                result = await session.execute(
                    select(Job).where(Job.status == JobStatus.RUNNING)
                )
                running_jobs = result.scalars().all()

                for job in running_jobs:
                    has_checkpoint = job.last_checkpoint_id is not None
                    if has_checkpoint:
                        job.status = JobStatus.RESUMABLE
                        job.error_message = "Interrupted by shutdown - resumable"
                    else:
                        job.status = JobStatus.FAILED
                        job.error_message = "Interrupted by shutdown"
                    job.completed_at = utcnow()

                await session.commit()

                if running_jobs:
                    logger.warning(f"Marked {len(running_jobs)} interrupted jobs")
        except Exception as e:
            logger.error(f"Error marking interrupted jobs: {e}")

    # =========================================================================
    # Job Executor (used by worker pool)
    # =========================================================================

    async def _execute_job(self, job_id: str) -> None:
        """
        Execute a job - called by worker pool.

        This is the main job execution function that:
        1. Loads job details
        2. Runs the CLI process
        3. Collects events
        4. Handles completion
        """
        logger.info(f"Executing job {job_id}")

        # Load job details
        async with async_session_maker() as session:
            service = JobService(session)
            job = await service.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            job_type = job.job_type.value
            parameters = job.parameters
            timeout = job.timeout_seconds

        # Get services
        executor = get_process_executor()
        collector = get_event_collector()

        # Define output callback
        async def output_callback(jid: str, line: str):
            await collector.process_line(jid, line)

        try:
            # Execute the process
            result = await executor.execute(
                job_id=job_id,
                job_type=job_type,
                parameters=parameters,
                output_callback=output_callback,
                timeout_seconds=timeout,
            )

            # Finalize the job
            error_msg = result.error_message if result.state.value != 'completed' else None
            await collector.finalize_job(
                job_id,
                exit_code=result.exit_code or (0 if result.state.value == 'completed' else 1),
                error_message=error_msg,
            )

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            await collector.finalize_job(job_id, exit_code=-1, error_message="Cancelled")
            raise

        except Exception as e:
            logger.exception(f"Job {job_id} failed with exception")
            await collector.finalize_job(job_id, exit_code=1, error_message=str(e))
            raise

    # =========================================================================
    # State Queries
    # =========================================================================

    @property
    def is_started(self) -> bool:
        """Check if startup completed successfully."""
        return self._startup_complete

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()


# Global lifecycle manager
_lifecycle: Optional[LifecycleManager] = None


def get_lifecycle_manager() -> Optional[LifecycleManager]:
    """Get the global lifecycle manager."""
    return _lifecycle


def set_lifecycle_manager(manager: LifecycleManager) -> None:
    """Set the global lifecycle manager."""
    global _lifecycle
    _lifecycle = manager


@asynccontextmanager
async def lifespan_context(max_workers: int = 4, graceful_timeout: float = 30.0):
    """
    Context manager for FastAPI lifespan.

    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with lifespan_context(max_workers=4):
                yield

        app = FastAPI(lifespan=lifespan)
    """
    global _lifecycle
    _lifecycle = LifecycleManager(
        max_workers=max_workers,
        graceful_timeout=graceful_timeout,
    )
    await _lifecycle.startup()
    try:
        yield _lifecycle
    finally:
        await _lifecycle.shutdown()
        _lifecycle = None
