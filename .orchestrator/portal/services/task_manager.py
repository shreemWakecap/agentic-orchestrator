"""Thread-safe task manager service using ThreadPoolExecutor.

Provides centralized management for background tasks with:
- Configurable thread pool size
- Task registry for tracking active tasks by ID
- Status querying and progress tracking
- Graceful shutdown support
- SSE (Server-Sent Events) subscriber support for real-time updates

Thread Safety:
- Uses threading.Lock for task registry access
- Each task runs in its own thread from the pool
- Thread-safe state updates via locked operations
- Uses thread-safe queue.Queue for cross-thread SSE communication
"""
import logging
import queue
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status states for managed tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    """Information about a managed task.

    Attributes:
        task_id: Unique identifier for the task
        name: Human-readable task name
        task_type: Type of task (e.g., "plan", "build", "sync")
        status: Current task status
        start_time: When the task was submitted
        end_time: When the task completed (if finished)
        progress: Optional progress percentage (0-100)
        result: Task result if completed successfully
        error: Error message if task failed
        metadata: Additional task-specific metadata
    """
    task_id: str
    name: str
    task_type: str = "task"
    status: TaskStatus = TaskStatus.PENDING
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    progress: Optional[int] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task info to dictionary for serialization.

        Returns frontend-compatible field names.
        """
        return {
            # Primary fields
            "task_id": self.task_id,
            "id": self.task_id,  # Frontend alias
            "name": self.name,
            "task_type": self.task_type,
            "type": self.task_type,  # Frontend alias
            "status": self.status.value,
            # Timestamps - dual format for compatibility
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "startedAt": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "completedAt": self.end_time.isoformat() if self.end_time else None,
            # Progress and message
            "progress": self.progress or 0,
            "message": self.metadata.get("message", ""),
            # Results
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """Thread-safe manager for background tasks using ThreadPoolExecutor.

    Provides methods to submit tasks, query their status, list active tasks,
    perform graceful shutdown, and support SSE subscribers for real-time updates.

    Example:
        manager = TaskManager(max_workers=4)
        task_id = manager.submit_task(my_function, args=(arg1,), name="My Task")
        status = manager.get_task_status(task_id)
        manager.shutdown()
    """

    def __init__(self, max_workers: int = 4):
        """Initialize the task manager.

        Args:
            max_workers: Maximum number of concurrent worker threads
        """
        self._max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tasks: Dict[str, TaskInfo] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._shutdown = False

        # SSE subscriber infrastructure (using thread-safe queue.Queue)
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._global_subscribers: List[queue.Queue] = []

        logger.info(f"TaskManager initialized with max_workers={max_workers}")

    def _ensure_executor(self) -> ThreadPoolExecutor:
        """Ensure executor is initialized (lazy initialization).

        Returns:
            The ThreadPoolExecutor instance
        """
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="task_manager"
            )
        return self._executor

    def _generate_task_id(self) -> str:
        """Generate a unique task ID.

        Returns:
            Unique string identifier
        """
        return str(uuid.uuid4())

    # SSE Subscriber Methods (using thread-safe queue.Queue)

    def subscribe_to_task(self, task_id: str) -> queue.Queue:
        """Subscribe to updates for a specific task.

        Thread-safe: Can be called from any thread.

        Args:
            task_id: The task to subscribe to

        Returns:
            Thread-safe Queue that will receive task update events
        """
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(q)
        return q

    def unsubscribe_from_task(self, task_id: str, q: queue.Queue) -> None:
        """Unsubscribe from task updates.

        Thread-safe: Can be called from any thread.

        Args:
            task_id: The task to unsubscribe from
            q: The queue to remove
        """
        with self._lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(q)
                except ValueError:
                    pass

    def subscribe_global(self) -> queue.Queue:
        """Subscribe to all task updates (for global SSE stream).

        Thread-safe: Can be called from any thread.

        Returns:
            Thread-safe Queue that will receive all task update events
        """
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._global_subscribers.append(q)
        return q

    def unsubscribe_global(self, q: queue.Queue) -> None:
        """Unsubscribe from global updates.

        Thread-safe: Can be called from any thread.

        Args:
            q: The queue to remove
        """
        with self._lock:
            try:
                self._global_subscribers.remove(q)
            except ValueError:
                pass

    def _notify_subscribers(self, task_id: str, event: Dict[str, Any]) -> None:
        """Notify all subscribers about a task update.

        Thread-safe: Can be called from any thread (worker threads or main thread).
        Uses thread-safe queue.Queue for cross-thread communication.

        Args:
            task_id: The task that was updated
            event: The event data to send
        """
        with self._lock:
            # Notify task-specific subscribers
            for q in self._subscribers.get(task_id, []):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    logger.debug(f"Queue full for task {task_id}, skipping event")

            # Notify global subscribers
            for q in self._global_subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    logger.debug("Global subscriber queue full, skipping event")

    def _wrap_task(
        self,
        task_id: str,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> Callable:
        """Wrap a task function with status tracking and SSE notifications.

        Args:
            task_id: The task's unique identifier
            func: The function to wrap
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function

        Returns:
            Wrapped function that updates task status and notifies subscribers
        """
        def wrapped():
            task_data = None
            try:
                # Mark as running
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.RUNNING
                        task_data = self._tasks[task_id].to_dict()

                logger.debug(f"Task {task_id} started execution")

                # Notify subscribers: task started
                if task_data:
                    self._notify_subscribers(task_id, {
                        "type": "task_updated",
                        "task_id": task_id,
                        "task": task_data,
                        "timestamp": datetime.now().isoformat()
                    })

                # Execute the actual function
                result = func(*args, **kwargs)

                # Mark as completed
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.COMPLETED
                        self._tasks[task_id].end_time = datetime.now()
                        self._tasks[task_id].result = result
                        self._tasks[task_id].progress = 100
                        task_data = self._tasks[task_id].to_dict()

                logger.debug(f"Task {task_id} completed successfully")

                # Notify subscribers: task completed
                if task_data:
                    self._notify_subscribers(task_id, {
                        "type": "task_completed",
                        "task_id": task_id,
                        "task": task_data,
                        "timestamp": datetime.now().isoformat()
                    })

                return result

            except Exception as e:
                # Mark as failed
                with self._lock:
                    if task_id in self._tasks:
                        self._tasks[task_id].status = TaskStatus.FAILED
                        self._tasks[task_id].end_time = datetime.now()
                        self._tasks[task_id].error = str(e)
                        task_data = self._tasks[task_id].to_dict()

                logger.exception(f"Task {task_id} failed: {e}")

                # Notify subscribers: task failed
                if task_data:
                    self._notify_subscribers(task_id, {
                        "type": "task_failed",
                        "task_id": task_id,
                        "task": task_data,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })

                raise

        return wrapped

    def submit_task(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        name: str = "Unnamed Task",
        task_id: Optional[str] = None,
        task_type: str = "task",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a task for background execution.

        Args:
            func: The callable to execute
            args: Positional arguments for the callable
            kwargs: Keyword arguments for the callable
            name: Human-readable name for the task
            task_id: Optional custom task ID (generated if not provided)
            task_type: Type of task (e.g., "plan", "build", "sync")
            metadata: Optional additional metadata to attach to task

        Returns:
            The task ID for tracking

        Raises:
            RuntimeError: If the task manager has been shut down
        """
        if self._shutdown:
            raise RuntimeError("TaskManager has been shut down")

        kwargs = kwargs or {}
        task_id = task_id or self._generate_task_id()

        # Create task info
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            task_type=task_type,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
            metadata=metadata or {}
        )

        # Register the task
        with self._lock:
            self._tasks[task_id] = task_info

        # Notify subscribers: task added
        self._notify_subscribers(task_id, {
            "type": "task_added",
            "task_id": task_id,
            "task": task_info.to_dict(),
            "timestamp": datetime.now().isoformat()
        })

        # Create wrapped function and submit
        wrapped = self._wrap_task(task_id, func, args, kwargs)
        executor = self._ensure_executor()
        future = executor.submit(wrapped)

        with self._lock:
            self._futures[task_id] = future

        logger.info(f"Task '{name}' submitted with ID: {task_id}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task.

        Args:
            task_id: The task's unique identifier

        Returns:
            Dictionary with task info, or None if task not found
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if task_info:
                return task_info.to_dict()
        return None

    def update_task_progress(self, task_id: str, progress: int) -> bool:
        """Update the progress of a running task.

        Args:
            task_id: The task's unique identifier
            progress: Progress percentage (0-100)

        Returns:
            True if update succeeded, False if task not found
        """
        task_data = None
        with self._lock:
            task_info = self._tasks.get(task_id)
            if task_info:
                task_info.progress = max(0, min(100, progress))
                task_data = task_info.to_dict()

        if task_data:
            self._notify_subscribers(task_id, {
                "type": "task_updated",
                "task_id": task_id,
                "task": task_data,
                "timestamp": datetime.now().isoformat()
            })
            return True
        return False

    def update_task_message(self, task_id: str, message: str) -> bool:
        """Update the current step/message of a running task.

        Args:
            task_id: The task's unique identifier
            message: Status message describing current step

        Returns:
            True if update succeeded, False if task not found
        """
        task_data = None
        with self._lock:
            task_info = self._tasks.get(task_id)
            if task_info:
                task_info.metadata["message"] = message
                task_data = task_info.to_dict()

        if task_data:
            self._notify_subscribers(task_id, {
                "type": "task_updated",
                "task_id": task_id,
                "task": task_data,
                "timestamp": datetime.now().isoformat()
            })
            return True
        return False

    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks that are pending or running.

        Returns:
            List of task info dictionaries for active tasks
        """
        with self._lock:
            return [
                task.to_dict()
                for task in self._tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    def list_all_tasks(self) -> List[Dict[str, Any]]:
        """List all tracked tasks regardless of status.

        Returns:
            List of all task info dictionaries
        """
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a pending task.

        Note: Running tasks cannot be interrupted, only pending tasks can be cancelled.

        Args:
            task_id: The task's unique identifier

        Returns:
            True if cancellation succeeded, False otherwise
        """
        task_data = None
        with self._lock:
            future = self._futures.get(task_id)
            task_info = self._tasks.get(task_id)

            if future and future.cancel():
                if task_info:
                    task_info.status = TaskStatus.FAILED
                    task_info.end_time = datetime.now()
                    task_info.error = "Cancelled by user"
                    task_data = task_info.to_dict()
                logger.info(f"Task {task_id} cancelled")

        if task_data:
            self._notify_subscribers(task_id, {
                "type": "task_cancelled",
                "task_id": task_id,
                "task": task_data,
                "timestamp": datetime.now().isoformat()
            })
            return True

        return False

    def clear_completed_tasks(self) -> int:
        """Remove completed and failed tasks from the registry.

        Returns:
            Number of tasks removed
        """
        with self._lock:
            to_remove = [
                task_id
                for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            ]

            for task_id in to_remove:
                del self._tasks[task_id]
                self._futures.pop(task_id, None)

            logger.debug(f"Cleared {len(to_remove)} completed tasks")
            return len(to_remove)

    def shutdown(self, wait: bool = True, timeout: Optional[float] = 5.0) -> None:
        """Shutdown the task manager gracefully.

        Args:
            wait: If True, wait for running tasks to complete
            timeout: Timeout in seconds when waiting (default 5 seconds)
        """
        if self._shutdown:
            return

        self._shutdown = True
        logger.info("TaskManager shutting down...")

        # Clear all subscriber queues to unblock waiting threads
        with self._lock:
            # Send None to all queues to signal shutdown
            for q in list(self._global_subscribers):
                try:
                    q.put_nowait(None)
                except Exception:
                    pass
            self._global_subscribers.clear()

            for queues in list(self._subscribers.values()):
                for q in list(queues):
                    try:
                        q.put_nowait(None)
                    except Exception:
                        pass
            self._subscribers.clear()

        if self._executor:
            # Use wait=False with cancel_futures=True for faster shutdown
            # This cancels pending futures and doesn't wait for running ones
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Python < 3.9 doesn't have cancel_futures
                self._executor.shutdown(wait=False)
            logger.info("TaskManager executor shutdown initiated")

        logger.info("TaskManager shutdown complete")

    @property
    def is_shutdown(self) -> bool:
        """Check if the task manager has been shut down."""
        return self._shutdown

    @property
    def active_count(self) -> int:
        """Get the number of active (pending or running) tasks."""
        with self._lock:
            return sum(
                1 for task in self._tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            )


# Global task manager instance (lazy initialization)
_task_manager: Optional[TaskManager] = None
_manager_lock = threading.Lock()


def get_task_manager(max_workers: int = 4) -> TaskManager:
    """Get or create the global TaskManager instance.

    Thread-safe singleton access to the task manager.

    Args:
        max_workers: Maximum workers (only used on first initialization)

    Returns:
        The global TaskManager instance
    """
    global _task_manager

    if _task_manager is None:
        with _manager_lock:
            if _task_manager is None:
                _task_manager = TaskManager(max_workers=max_workers)

    return _task_manager


def shutdown_task_manager(wait: bool = True) -> None:
    """Shutdown the global task manager if it exists.

    Args:
        wait: If True, wait for running tasks to complete
    """
    global _task_manager

    if _task_manager is not None:
        with _manager_lock:
            if _task_manager is not None:
                _task_manager.shutdown(wait=wait)
                _task_manager = None
