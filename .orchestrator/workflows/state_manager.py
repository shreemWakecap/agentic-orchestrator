"""Centralized workflow state management.

This module provides a unified interface for persisting and loading
workflow state, replacing the 30+ manual save calls scattered throughout
the BuildingWorkflow class.

Benefits:
- Single point for all state persistence
- Consistent state handling
- Easier testing through mocking
- Reduced code duplication
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from db import get_build_state_repository, BuildStateRepository

logger = logging.getLogger(__name__)


class WorkflowStateManager:
    """Manages persistence of workflow state.

    Provides a clean interface for saving and loading build state,
    abstracting away the database details from workflows.
    """

    def __init__(self, build_state_repo: Optional[BuildStateRepository] = None):
        """Initialize state manager.

        Args:
            build_state_repo: Repository for build state. If None, uses default.
        """
        self._repo = build_state_repo or get_build_state_repository()

    def create(self, plan_id: str, total_steps: int = 0) -> int:
        """Create initial build state for a plan.

        Args:
            plan_id: The plan ID
            total_steps: Total number of steps in the plan

        Returns:
            ID of the created build state record
        """
        return self._repo.create(plan_id, total_steps)

    def save(self, plan_id: str, state: "BuildState") -> None:
        """Save complete build state atomically.

        This replaces the many individual update calls with a single
        method that persists all state at once.

        Args:
            plan_id: The plan ID
            state: The BuildState object to persist
        """
        try:
            # Update main state
            self._repo.update(
                plan_id=plan_id,
                status=state.status,
                current_phase=state.current_phase,
                current_step=state.current_step,
                total_steps=state.total_steps,
                completed_steps=state.completed_steps,
                failed_steps=state.failed_steps,
                skipped_steps=getattr(state, 'skipped_steps', []),
                files_created=state.files_created,
                files_modified=state.files_modified,
                last_error=state.last_error,
            )

            # Update step states
            for step_id, step_data in state.step_states.items():
                self.save_step_state(plan_id, step_id, step_data)

        except Exception as e:
            logger.error(f"Failed to save build state for {plan_id}: {e}")
            raise

    def save_step_state(
        self, plan_id: str, step_id: str, step_data: Dict[str, Any]
    ) -> None:
        """Save state for a single step.

        Args:
            plan_id: The plan ID
            step_id: The step ID
            step_data: Step state data dict
        """
        self._repo.set_step_state(
            plan_id=plan_id,
            step_id=step_id,
            status=step_data.get('status', 'pending'),
            started_at=step_data.get('started_at'),
            completed_at=step_data.get('completed_at'),
            error=step_data.get('error'),
            retry_count=step_data.get('retry_count', 0),
            output=step_data.get('output'),
            agent_used=step_data.get('agent_used'),
        )

    def load(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Load build state from database.

        Args:
            plan_id: The plan ID

        Returns:
            Build state as dict, or None if not found
        """
        data = self._repo.get(plan_id)
        if not data:
            return None

        # Load step states
        step_states = self._repo.get_step_states(plan_id)
        data['step_states'] = {s['step_id']: s for s in step_states}

        return data

    def load_or_create(
        self, plan_id: str, total_steps: int = 0
    ) -> Dict[str, Any]:
        """Load existing build state or create new one.

        Args:
            plan_id: The plan ID
            total_steps: Total steps if creating new state

        Returns:
            Build state as dict
        """
        existing = self.load(plan_id)
        if existing:
            return existing

        self.create(plan_id, total_steps)
        return self.load(plan_id)

    def update_status(self, plan_id: str, status: str) -> None:
        """Update just the status field.

        Args:
            plan_id: The plan ID
            status: New status value
        """
        self._repo.update(plan_id=plan_id, status=status)

    def update_current_step(
        self, plan_id: str, step_id: Optional[str], phase: int = None
    ) -> None:
        """Update the current step being executed.

        Args:
            plan_id: The plan ID
            step_id: Current step ID or None if between steps
            phase: Current phase number
        """
        kwargs = {"current_step": step_id}
        if phase is not None:
            kwargs["current_phase"] = phase
        self._repo.update(plan_id=plan_id, **kwargs)

    def mark_step_completed(self, plan_id: str, step_id: str) -> None:
        """Mark a step as completed and add to completed list.

        Args:
            plan_id: The plan ID
            step_id: The completed step ID
        """
        state = self.load(plan_id)
        if state:
            completed = state.get('completed_steps', [])
            if step_id not in completed:
                completed.append(step_id)
            self._repo.update(plan_id=plan_id, completed_steps=completed)

    def mark_step_failed(
        self, plan_id: str, step_id: str, error: str = None
    ) -> None:
        """Mark a step as failed and add to failed list.

        Args:
            plan_id: The plan ID
            step_id: The failed step ID
            error: Error message if any
        """
        state = self.load(plan_id)
        if state:
            failed = state.get('failed_steps', [])
            if step_id not in failed:
                failed.append(step_id)
            self._repo.update(
                plan_id=plan_id,
                failed_steps=failed,
                last_error=error,
            )

    def add_files_created(self, plan_id: str, files: List[str]) -> None:
        """Add files to the created files list.

        Args:
            plan_id: The plan ID
            files: List of file paths that were created
        """
        state = self.load(plan_id)
        if state:
            created = state.get('files_created', [])
            for f in files:
                if f not in created:
                    created.append(f)
            self._repo.update(plan_id=plan_id, files_created=created)

    def add_files_modified(self, plan_id: str, files: List[str]) -> None:
        """Add files to the modified files list.

        Args:
            plan_id: The plan ID
            files: List of file paths that were modified
        """
        state = self.load(plan_id)
        if state:
            modified = state.get('files_modified', [])
            for f in files:
                if f not in modified:
                    modified.append(f)
            self._repo.update(plan_id=plan_id, files_modified=modified)

    def get_step_state(self, plan_id: str, step_id: str) -> Optional[Dict]:
        """Get state for a specific step.

        Args:
            plan_id: The plan ID
            step_id: The step ID

        Returns:
            Step state dict or None
        """
        step_states = self._repo.get_step_states(plan_id)
        for s in step_states:
            if s.get('step_id') == step_id:
                return s
        return None

    def can_retry_step(
        self, plan_id: str, step_id: str, max_retries: int = 3
    ) -> bool:
        """Check if a step can be retried.

        Args:
            plan_id: The plan ID
            step_id: The step ID
            max_retries: Maximum number of retries allowed

        Returns:
            True if step can be retried
        """
        step_state = self.get_step_state(plan_id, step_id)
        if not step_state:
            return True
        return step_state.get('retry_count', 0) < max_retries

    def increment_retry_count(self, plan_id: str, step_id: str) -> int:
        """Increment retry count for a step.

        Args:
            plan_id: The plan ID
            step_id: The step ID

        Returns:
            New retry count
        """
        step_state = self.get_step_state(plan_id, step_id)
        current_count = step_state.get('retry_count', 0) if step_state else 0
        new_count = current_count + 1

        self._repo.set_step_state(
            plan_id=plan_id,
            step_id=step_id,
            retry_count=new_count,
        )

        return new_count
