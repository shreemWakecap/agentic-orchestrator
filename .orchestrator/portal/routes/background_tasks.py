"""Unified background task API routes with SSE support.

Provides REST endpoints and Server-Sent Events streaming for
real-time background task monitoring.

Thread Safety:
- Uses thread-safe queue.Queue from TaskManager for cross-thread communication
- SSE endpoints bridge sync queues to async using asyncio.to_thread()
"""
import asyncio
import json
import queue
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from portal.services.task_manager import TaskManager, get_task_manager

router = APIRouter(prefix="/api/background-tasks", tags=["background-tasks"])


def _get_from_queue(q: queue.Queue, timeout: float = 1.0):
    """Get item from thread-safe queue with timeout.

    Helper function to be run in executor for async bridging.
    Returns None on timeout (Empty exception).
    """
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return None


@router.get("")
async def list_background_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    task_manager: TaskManager = Depends(get_task_manager),
):
    """List all background tasks with optional filters.

    Args:
        status: Filter by status (pending, running, completed, failed)
        task_type: Filter by task type (plan, build, sync, etc.)

    Returns:
        Dictionary with tasks list and status counts
    """
    tasks = task_manager.list_all_tasks()

    # Apply filters
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if task_type:
        tasks = [t for t in tasks if t.get("task_type") == task_type]

    # Calculate counts from all tasks (not filtered)
    all_tasks = task_manager.list_all_tasks()
    counts = {
        "pending": len([t for t in all_tasks if t["status"] == "pending"]),
        "running": len([t for t in all_tasks if t["status"] == "running"]),
        "completed": len([t for t in all_tasks if t["status"] == "completed"]),
        "failed": len([t for t in all_tasks if t["status"] == "failed"]),
        "total": len(all_tasks),
    }

    return {"tasks": tasks, "counts": counts}


@router.get("/events")
async def stream_all_tasks(
    task_manager: TaskManager = Depends(get_task_manager),
):
    """SSE stream for all task updates (global stream).

    Returns a Server-Sent Events stream that emits:
    - initial: Initial state with all current tasks
    - task_added: When a new task is created
    - task_updated: When a task's status or progress changes
    - task_completed: When a task completes successfully
    - task_failed: When a task fails
    - task_cancelled: When a task is cancelled
    - heartbeat: Periodic keepalive (every 5s)

    Uses thread-safe queue.Queue bridged to async via asyncio.to_thread().
    """

    async def event_generator():
        q = task_manager.subscribe_global()
        heartbeat_counter = 0
        try:
            # Send initial state
            tasks = task_manager.list_all_tasks()
            initial = {
                "type": "initial",
                "tasks": tasks,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            yield f"data: {json.dumps(initial)}\n\n"

            # Stream updates using thread-safe queue
            while True:
                # Use asyncio.to_thread to bridge sync queue to async
                # Short timeout (1s) to allow heartbeats and responsiveness
                event = await asyncio.to_thread(_get_from_queue, q, 1.0)

                if event is not None:
                    yield f"data: {json.dumps(event)}\n\n"
                    heartbeat_counter = 0
                else:
                    # No event, increment counter
                    heartbeat_counter += 1
                    # Send heartbeat every 5 seconds (5 x 1s timeout)
                    if heartbeat_counter >= 5:
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }
                        yield f"data: {json.dumps(heartbeat)}\n\n"
                        heartbeat_counter = 0
        finally:
            task_manager.unsubscribe_global(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    """Get details of a specific task.

    Args:
        task_id: The task's unique identifier

    Returns:
        Task details dictionary

    Raises:
        404: If task not found
    """
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/stream")
async def stream_task(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    """SSE stream for a specific task.

    Returns a Server-Sent Events stream that emits updates
    for the specified task until it completes or fails.

    Uses thread-safe queue.Queue bridged to async via asyncio.to_thread().

    Args:
        task_id: The task's unique identifier

    Raises:
        404: If task not found
    """
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        q = task_manager.subscribe_to_task(task_id)
        heartbeat_counter = 0
        try:
            # Send initial state
            current = task_manager.get_task_status(task_id)
            if current:
                yield f"data: {json.dumps({'type': 'task_status', **current})}\n\n"

            while True:
                # Check if task is done
                current = task_manager.get_task_status(task_id)
                if not current:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Task not found'})}\n\n"
                    break

                if current["status"] in ["completed", "failed"]:
                    yield f"data: {json.dumps({'type': 'task_done', **current})}\n\n"
                    break

                # Use asyncio.to_thread to bridge sync queue to async
                event = await asyncio.to_thread(_get_from_queue, q, 1.0)

                if event is not None:
                    yield f"data: {json.dumps(event)}\n\n"
                    heartbeat_counter = 0
                else:
                    heartbeat_counter += 1
                    # Send heartbeat every 5 seconds
                    if heartbeat_counter >= 5:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        heartbeat_counter = 0
        finally:
            task_manager.unsubscribe_from_task(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
):
    """Cancel a task.

    Only pending tasks can be cancelled. Running tasks cannot be interrupted.

    Args:
        task_id: The task's unique identifier

    Returns:
        Success message with task_id

    Raises:
        404: If task not found
        400: If task cannot be cancelled (already completed/failed)
    """
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel task with status: {task['status']}"
        )

    success = task_manager.cancel_task(task_id)
    if success:
        return {"success": True, "task_id": task_id, "message": "Task cancelled"}
    else:
        raise HTTPException(status_code=400, detail="Failed to cancel task")
