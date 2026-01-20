"""Centralized Plan status management following aggregate root pattern.

Plan is the aggregate root. All status changes flow through Plan first,
then cascade to child entities (build_states).
"""
import asyncio
import logging
from typing import Optional

from db import PlanRepository, BuildStateRepository

logger = logging.getLogger(__name__)


class PlanStatusService:
    """
    Centralized service for Plan status management.

    All status changes MUST go through this service to ensure:
    - Plan.status is the authoritative source of truth
    - build_states.status is always synced with Plan.status

    This follows the DDD aggregate root pattern where Plan owns
    all status-related operations.
    """

    VALID_STATUSES = {"pending", "building", "completed", "failed", "paused"}

    def __init__(
        self,
        plan_repo: PlanRepository,
        build_state_repo: BuildStateRepository,
    ):
        self._plan_repo = plan_repo
        self._build_state_repo = build_state_repo

    def update_status(self, plan_id: str, new_status: str, broadcast: bool = True) -> bool:
        """
        Update plan status (aggregate root) and cascade to build_states.

        This is the ONLY method that should be used to change plan status.
        It ensures both tables stay in sync.

        Args:
            plan_id: The plan identifier
            new_status: New status (pending, building, completed, failed, paused)
            broadcast: Whether to broadcast status change via WebSocket (default True)

        Returns:
            True if update succeeded

        Raises:
            ValueError: If new_status is not a valid status
        """
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {self.VALID_STATUSES}")

        # 1. Update Plan (authoritative source of truth)
        self._plan_repo.update_status(plan_id, new_status)

        # 2. Cascade to build_states if exists
        if self._build_state_repo.exists(plan_id):
            self._build_state_repo.update(plan_id, status=new_status)

        # 3. Broadcast status change via WebSocket (async, fire-and-forget)
        if broadcast:
            self._broadcast_status_change(plan_id, new_status)

        return True

    def _broadcast_status_change(self, plan_id: str, new_status: str):
        """Broadcast plan status change via WebSocket (non-blocking)."""
        try:
            from portal.streaming.websocket import get_websocket_manager

            manager = get_websocket_manager()

            # Create async task for broadcasting
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    manager.broadcast_plan_status(plan_id, new_status)
                )
            else:
                # If no event loop, skip WebSocket broadcast
                logger.debug(f"No event loop for WebSocket broadcast: {plan_id} -> {new_status}")
        except Exception as e:
            # Don't fail status update if broadcast fails
            logger.warning(f"WebSocket broadcast failed for plan {plan_id}: {e}")

    def get_status(self, plan_id: str) -> str:
        """
        Get authoritative status from Plan (aggregate root).

        Args:
            plan_id: The plan identifier

        Returns:
            Current status or "unknown" if plan not found
        """
        plan = self._plan_repo.get_by_id(plan_id)
        return plan.get("status", "pending") if plan else "unknown"

    def sync_build_state_status(self, plan_id: str) -> bool:
        """
        Ensure build_states.status matches Plan.status.

        Use this to fix any existing inconsistencies.

        Args:
            plan_id: The plan identifier

        Returns:
            True if sync performed, False if no build_state exists
        """
        plan_status = self.get_status(plan_id)

        if plan_status == "unknown":
            return False

        if self._build_state_repo.exists(plan_id):
            self._build_state_repo.update(plan_id, status=plan_status)
            return True

        return False

    def broadcast_build_progress(
        self,
        plan_id: str,
        progress: int,
        current_step: Optional[str] = None,
        **extra_data
    ):
        """
        Broadcast build progress update via WebSocket.

        Args:
            plan_id: The plan identifier
            progress: Progress percentage (0-100)
            current_step: Current step being executed
            **extra_data: Additional data to include
        """
        try:
            from portal.streaming.websocket import get_websocket_manager

            manager = get_websocket_manager()

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    manager.broadcast_build_progress(plan_id, progress, current_step, **extra_data)
                )
        except Exception as e:
            logger.warning(f"WebSocket progress broadcast failed for plan {plan_id}: {e}")

    @staticmethod
    def broadcast_dashboard_stats():
        """
        Broadcast updated dashboard stats via WebSocket.

        Call this after any plan status change that affects counts.
        """
        try:
            from portal.streaming.websocket import get_websocket_manager
            from db import get_plan_repository

            plan_repo = get_plan_repository()
            counts = {
                "pending": len(plan_repo.list_by_status("pending")),
                "in_progress": len(plan_repo.list_by_status("building")),
                "completed": len(plan_repo.list_by_status("completed")),
                "failed": len(plan_repo.list_by_status("failed")),
            }

            manager = get_websocket_manager()

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(manager.broadcast_dashboard_stats(counts))
        except Exception as e:
            logger.warning(f"WebSocket dashboard stats broadcast failed: {e}")
