"""Run-related API routes."""
import asyncio
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from db import RunRepository
from portal.dependencies import get_run_repo
from portal.schemas.requests import ForceStopRunRequest
from portal.schemas.responses import (
    RunResponse,
    RunListResponse,
    ForceStopRunResponse,
    StuckRunsResponse,
    StuckRunInfo,
)
from portal.services.run_management_service import get_run_management_service

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _extract_phase_info(run: dict) -> dict:
    """Extract phase tracking information from run data.

    Args:
        run: Raw run dict from repository

    Returns:
        Dict with current_phase_name, phase_progress, phases_total
    """
    data = run.get("data") or {}

    # Extract phase info from run data
    current_phase_name = data.get("current_phase_name") or data.get("current_phase")
    phase_progress = data.get("phase_progress", 0)
    phases_total = data.get("phases_total", 0)

    # If workflow has steps, derive phase info from them
    if not current_phase_name and "current_step" in data:
        current_phase_name = data.get("current_step")

    # Derive from status if not explicitly set
    if not current_phase_name:
        status = run.get("status", "")
        if status == "running":
            current_phase_name = "Executing"
        elif status == "pending":
            current_phase_name = "Pending"
        elif status == "completed":
            current_phase_name = "Completed"
        elif status == "failed":
            current_phase_name = "Failed"

    return {
        "current_phase_name": current_phase_name,
        "phase_progress": int(phase_progress),
        "phases_total": int(phases_total),
    }


def _get_activity_log(run_repo: RunRepository, run_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get the most recent activity log entries for a run.

    Args:
        run_repo: RunRepository instance
        run_id: The run ID to get events for
        limit: Maximum number of entries to return (default 5)

    Returns:
        List of activity log entries with type, message, and timestamp
    """
    events = run_repo.get_events(run_id, since_id=0)

    # Sort by timestamp descending and take the most recent
    events_sorted = sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)
    recent_events = events_sorted[:limit]

    # Format as activity log entries
    activity_log = []
    for event in reversed(recent_events):  # Return in chronological order
        event_data = event.get("data") or {}
        log_entry = {
            "type": event.get("event_type", "unknown"),
            "timestamp": event.get("timestamp"),
            "message": event_data.get("message") or event_data.get("description") or event.get("event_type"),
        }
        # Include additional context if available
        if "step" in event_data:
            log_entry["step"] = event_data["step"]
        if "phase" in event_data:
            log_entry["phase"] = event_data["phase"]
        if "progress" in event_data:
            log_entry["progress"] = event_data["progress"]

        activity_log.append(log_entry)

    return activity_log


def _enrich_run_response(run: dict, run_repo: RunRepository) -> dict:
    """Enrich run data with phase info and activity log.

    Args:
        run: Raw run dict from repository
        run_repo: RunRepository for fetching events

    Returns:
        Enriched run dict ready for RunResponse
    """
    # Extract phase information
    phase_info = _extract_phase_info(run)

    # Get recent activity log
    activity_log = _get_activity_log(run_repo, run["run_id"])

    # Merge into run dict
    enriched = {**run, **phase_info, "activity_log": activity_log}
    return enriched


@router.get("/stuck", response_model=StuckRunsResponse)
async def list_stuck_runs(
    stale_minutes: int = 30,
    run_repo: RunRepository = Depends(get_run_repo),
) -> StuckRunsResponse:
    """List workflow runs that appear to be stuck.

    Returns runs that have been in 'running' or 'pending' status
    for longer than the specified threshold.

    Args:
        stale_minutes: Minutes threshold to consider a run stuck (default 30)

    Returns:
        List of stuck runs with metadata
    """
    service = get_run_management_service()
    stuck_runs = service.get_stuck_runs(stale_minutes=stale_minutes)

    # Convert to response format
    runs_info = []
    for run in stuck_runs:
        run_data = run.get("data") or {}
        runs_info.append(
            StuckRunInfo(
                run_id=run.get("run_id", ""),
                workflow=run.get("workflow", "unknown"),
                status=run.get("status", "unknown"),
                started_at=run.get("started_at"),
                minutes_stuck=run.get("stuck_duration_minutes", 0.0),
            )
        )

    return StuckRunsResponse(
        runs=runs_info,
        count=len(runs_info),
    )


@router.get("", response_model=RunListResponse)
async def list_runs(
    status: Optional[str] = None,
    run_repo: RunRepository = Depends(get_run_repo),
) -> RunListResponse:
    """List all active runs with optional status filter.

    Args:
        status: Optional filter by status (pending, running, completed, failed)
    """
    runs = run_repo.list_active(status) if status else run_repo.list_active()

    # Enrich each run with phase info and activity log
    enriched_runs = [_enrich_run_response(run, run_repo) for run in runs]

    # Calculate counts from all runs (not filtered)
    all_runs = run_repo.list_active()
    counts = {
        "running": len([r for r in all_runs if r.get("status") == "running"]),
        "completed": len([r for r in all_runs if r.get("status") == "completed"]),
        "failed": len([r for r in all_runs if r.get("status") == "failed"]),
        "pending": len([r for r in all_runs if r.get("status") == "pending"]),
    }

    return RunListResponse(runs=enriched_runs, counts=counts)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
) -> RunResponse:
    """Get run status with phase information and activity log."""
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Enrich with phase info and activity log
    enriched_run = _enrich_run_response(run, run_repo)
    return RunResponse(**enriched_run)


@router.post("/{run_id}/force-stop", response_model=ForceStopRunResponse)
async def force_stop_run(
    run_id: str,
    request: ForceStopRunRequest,
    run_repo: RunRepository = Depends(get_run_repo),
) -> ForceStopRunResponse:
    """Force stop a stuck workflow run.

    This is a dangerous action that forcefully terminates a workflow run.
    Requires explicit confirmation by providing confirmation_text="I understand".

    WARNING: This action cannot be undone. The user takes full responsibility
    for stopping the task.

    Args:
        run_id: The run ID to force stop
        request: Request containing confirmation_text

    Returns:
        ForceStopRunResponse with result details

    Raises:
        HTTPException 404: If run not found
        HTTPException 400: If confirmation invalid or run cannot be stopped
    """
    # Validate confirmation text (Pydantic validator handles this, but double-check)
    if request.confirmation_text != "I understand":
        raise HTTPException(
            status_code=400,
            detail="confirmation_text must be exactly 'I understand' to proceed with force-stop",
        )

    # Verify run exists
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    previous_status = run.get("status", "unknown")

    # Use the service to force stop
    service = get_run_management_service()
    result = service.force_stop_run(run_id)

    if not result.get("success"):
        # Determine appropriate error code
        error_msg = result.get("error", "Unknown error")
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

    return ForceStopRunResponse(
        status="stopped",
        run_id=run_id,
        previous_status=previous_status,
        new_status=result.get("new_status", "force_stopped"),
        message=result.get("message", "Run has been force stopped."),
    )


@router.get("/{run_id}/events")
async def stream_events(
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
) -> StreamingResponse:
    """Stream events from a running workflow via SSE."""
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_event_id = 0
        while True:
            run = run_repo.get(run_id)
            if not run:
                break

            # Send new events from database
            events = run_repo.get_events(run_id, since_id=last_event_id)
            for event in events:
                # Update last_event_id
                if event.get("id", 0) > last_event_id:
                    last_event_id = event["id"]
                # Format event for SSE
                event_data = {
                    "type": event.get("event_type", "unknown"),
                    "timestamp": event.get("timestamp"),
                    **event.get("data", {}),
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            # Check if done
            if run.get("status") in ["completed", "failed"]:
                yield f"data: {json.dumps({'type': 'done', 'status': run.get('status')})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _format_log_entry(event: dict) -> Dict[str, Any]:
    """Format an event as a log entry with timestamp, level, and message.

    Args:
        event: Raw event dict from repository

    Returns:
        Formatted log entry with timestamp, level, and message
    """
    event_type = event.get("event_type", "unknown")
    event_data = event.get("data") or {}
    timestamp = event.get("timestamp")

    # Determine log level based on event type
    level_map = {
        "error": "error",
        "warning": "warn",
        "start": "info",
        "complete": "info",
        "step": "info",
        "phase_transition": "info",
        "activity_log": "debug",
    }
    level = level_map.get(event_type, "info")

    # Extract message from various possible fields
    message = (
        event_data.get("message")
        or event_data.get("activity")
        or event_data.get("description")
        or event_data.get("step")
        or event_type
    )

    # Add phase/progress context if available
    if event_type == "phase_transition":
        phase = event_data.get("phase", "")
        progress = event_data.get("progress", 0)
        message = f"[{phase}] {message} ({progress}%)"

    return {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "type": event_type,
    }


@router.get("/{run_id}/logs/recent")
async def get_recent_logs(
    run_id: str,
    limit: int = 50,
    run_repo: RunRepository = Depends(get_run_repo),
) -> Dict[str, Any]:
    """Get recent log lines for a run.

    Args:
        run_id: The run ID to get logs for
        limit: Maximum number of log entries to return (default 50)

    Returns:
        Dict with logs array and run status info
    """
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get all events and format as log entries
    events = run_repo.get_events(run_id, since_id=0)

    # Sort by timestamp and take the most recent
    events_sorted = sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)
    recent_events = events_sorted[:limit]

    # Format as log entries in chronological order
    logs = [_format_log_entry(event) for event in reversed(recent_events)]

    return {
        "run_id": run_id,
        "status": run.get("status"),
        "logs": logs,
        "total_count": len(events),
    }


@router.get("/{run_id}/logs")
async def stream_run_logs(
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
) -> StreamingResponse:
    """Stream workflow log lines in real-time via SSE.

    Tails the run's log output and emits log line events with
    timestamp, level, and message fields.

    Args:
        run_id: The run ID to stream logs for

    Returns:
        SSE stream of log line events
    """
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def log_generator():
        last_event_id = 0

        # First, send existing log entries as initial batch
        existing_events = run_repo.get_events(run_id, since_id=0)
        for event in sorted(existing_events, key=lambda e: e.get("timestamp", "")):
            if event.get("id", 0) > last_event_id:
                last_event_id = event["id"]
            log_entry = _format_log_entry(event)
            yield f"data: {json.dumps(log_entry)}\n\n"

        # Then stream new logs as they arrive
        while True:
            run = run_repo.get(run_id)
            if not run:
                break

            # Get new events since last check
            new_events = run_repo.get_events(run_id, since_id=last_event_id)
            for event in sorted(new_events, key=lambda e: e.get("timestamp", "")):
                if event.get("id", 0) > last_event_id:
                    last_event_id = event["id"]
                log_entry = _format_log_entry(event)
                yield f"data: {json.dumps(log_entry)}\n\n"

            # Check if run is complete
            if run.get("status") in ["completed", "failed"]:
                # Send completion marker
                yield f"data: {json.dumps({'type': 'stream_end', 'status': run.get('status')})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
