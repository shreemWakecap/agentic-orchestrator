"""Task-related API routes for dashboard widgets."""
from typing import Optional
from fastapi import APIRouter, Depends

from portal.services.task_manager import TaskManager, get_task_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/planning")
async def get_planning_tasks(
    task_manager: TaskManager = Depends(get_task_manager),
):
    """Get tasks currently in planning phase.

    Returns tasks that are of type 'plan' and status 'pending' or 'running'.
    These represent plans being generated or analyzed.

    Returns:
        Dictionary with tasks list
    """
    all_tasks = task_manager.list_all_tasks()

    # Filter for planning tasks (task_type = 'plan' and active status)
    planning_tasks = [
        {
            "id": t.get("task_id", t.get("id", "")),
            "name": t.get("name", t.get("description", "Planning workflow...")),
            "description": t.get("description", "Analyzing requirements and generating plan..."),
            "status": t.get("status", "pending"),
            "progress": t.get("progress", 0),
            "created_at": t.get("created_at"),
        }
        for t in all_tasks
        if t.get("task_type") == "plan" and t.get("status") in ["pending", "running"]
    ]

    return {"tasks": planning_tasks}
