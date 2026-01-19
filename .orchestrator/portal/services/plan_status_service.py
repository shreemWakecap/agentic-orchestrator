"""Centralized Plan status management following aggregate root pattern.

Plan is the aggregate root. All status changes flow through Plan first,
then cascade to child entities (build_states).
"""
from typing import Optional

from db import PlanRepository, BuildStateRepository


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

    def update_status(self, plan_id: str, new_status: str) -> bool:
        """
        Update plan status (aggregate root) and cascade to build_states.

        This is the ONLY method that should be used to change plan status.
        It ensures both tables stay in sync.

        Args:
            plan_id: The plan identifier
            new_status: New status (pending, building, completed, failed, paused)

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

        return True

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
