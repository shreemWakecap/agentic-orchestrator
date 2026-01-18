"""Run-related API routes."""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from db import RunRepository, BuildStateRepository, PlanRepository
from portal.dependencies import get_run_repo, get_build_state_repo, get_plan_repo
from portal.schemas.responses import RunResponse, RunListResponse

router = APIRouter(prefix="/api/runs", tags=["runs"])


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

    # Calculate counts from all runs (not filtered)
    all_runs = run_repo.list_active()
    counts = {
        "running": len([r for r in all_runs if r.get("status") == "running"]),
        "completed": len([r for r in all_runs if r.get("status") == "completed"]),
        "failed": len([r for r in all_runs if r.get("status") == "failed"]),
        "pending": len([r for r in all_runs if r.get("status") == "pending"]),
    }

    return RunListResponse(runs=runs, counts=counts)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
) -> RunResponse:
    """Get run status."""
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse(**run)


@router.get("/{run_id}/events")
async def stream_events(
    run_id: str,
    run_repo: RunRepository = Depends(get_run_repo),
    build_state_repo: BuildStateRepository = Depends(get_build_state_repo),
    plan_repo: PlanRepository = Depends(get_plan_repo),
) -> StreamingResponse:
    """Stream events from a running workflow via SSE."""
    run = run_repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get plan_id from run to fetch steps
    plan_id = run.get("plan_id")

    async def event_generator():
        last_event_id = 0
        last_heartbeat = time.time()
        heartbeat_interval = 15  # seconds

        # Emit init event with full step list on connection start
        if plan_id:
            steps = plan_repo.get_steps(plan_id)
            step_states = build_state_repo.get_step_states(plan_id)
            step_status_map = {s["step_id"]: s.get("status", "pending") for s in step_states}

            init_steps = []
            for step in steps:
                step_id = step.get("step_id")
                label = step.get("description", step_id)
                status = step_status_map.get(step_id, "pending")
                init_steps.append({
                    "step_id": step_id,
                    "label": label,
                    "status": status,
                })

            init_event = {
                "type": "init",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "steps": init_steps,
            }
            yield f"data: {json.dumps(init_event)}\n\n"

        try:
            while True:
                try:
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

                    # Send heartbeat every 15 seconds to keep connection alive
                    current_time = time.time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        heartbeat_data = {
                            "type": "heartbeat",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = current_time

                    await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
